"""
rag_demo.py — Retrieval-Augmented Generation (RAG) with Amazon Bedrock.

Step 1 — Mock Aetna policy document (5 sections)
Step 2 — Build an in-memory vector store using Bedrock Titan embeddings
Step 3 — Cosine-similarity retrieval (no external vector DB)
Step 4 — RAG vs No-RAG comparison on two eligibility queries
"""

import json
import math

import boto3

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CLAUDE_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
EMBED_MODEL_ID  = "amazon.titan-embed-text-v2:0"
REGION          = "us-east-1"
PROFILE         = "cdk-dev"

session = boto3.Session(profile_name=PROFILE, region_name=REGION)
bedrock = session.client("bedrock-runtime")

# ---------------------------------------------------------------------------
# Step 1 — Mock Aetna 2026 prior auth policy document (5 sections)
# ---------------------------------------------------------------------------

POLICY_CHUNKS = [
    {
        "section": "Knee Surgery (CPT 27447)",
        "text": (
            "Aetna 2026 Policy — Knee Surgery (CPT 27447): Prior authorization is "
            "required for knee surgery under ALL Aetna plan types including PPO, HMO, "
            "and EPO. Required submissions: operative report or surgical plan, X-rays "
            "taken within the last 6 months, documentation of conservative treatment "
            "history (minimum 3 months of physical therapy), and BMI documentation. "
            "All four items must be submitted together or the request will be returned "
            "as incomplete. Standard processing time is 5–7 business days from receipt "
            "of a complete submission. Expedited review (24–72 hours) is available for "
            "urgent cases with physician attestation. Failure to obtain prior auth "
            "before surgery may result in claim denial regardless of medical necessity."
        ),
    },
    {
        "section": "Routine Physical Examination (CPT 99395)",
        "text": (
            "Aetna 2026 Policy — Routine Physical Examination (CPT 99395): No prior "
            "authorization is required for annual routine physical examinations. This "
            "service is covered at 100% (zero cost-sharing) on all Aetna PPO plans "
            "when performed by an in-network primary care provider. Annual limit is "
            "one (1) routine physical per calendar year per member. Additional "
            "preventive screenings performed during the same visit (e.g., blood panel, "
            "cholesterol screening) are also covered at 100% when billed with "
            "appropriate preventive CPT codes. Out-of-network providers may be subject "
            "to balance billing; member cost-sharing applies."
        ),
    },
    {
        "section": "Experimental and Investigational Treatments",
        "text": (
            "Aetna 2026 Policy — Experimental and Investigational Treatments: "
            "Experimental, investigational, or unproven treatments are not covered "
            "under standard Aetna benefit plans. Members may submit a formal appeal "
            "with supporting clinical trial documentation, peer-reviewed literature, "
            "and a letter of medical necessity from the treating physician. All appeals "
            "for experimental treatments require review by Aetna's Medical Director. "
            "Processing time for experimental treatment appeals is 15–30 calendar days. "
            "Compassionate use exceptions may be granted in rare cases at the Medical "
            "Director's discretion. Members enrolled in an IRB-approved clinical trial "
            "may be eligible for coverage of routine care costs associated with the trial "
            "under Aetna's Clinical Trial policy."
        ),
    },
    {
        "section": "Emergency Services",
        "text": (
            "Aetna 2026 Policy — Emergency Services: No prior authorization is required "
            "for emergency medical services. Emergency services are covered regardless "
            "of whether the facility is in-network or out-of-network, consistent with "
            "federal law. Members or their representative must notify Aetna within "
            "48 hours of an emergency hospital admission, or as soon as reasonably "
            "possible. Failure to notify within this window does not result in denial "
            "but may require additional documentation. Post-stabilization care that "
            "continues beyond the emergency may require prior authorization. Ambulance "
            "transport to the nearest appropriate facility is covered without prior auth."
        ),
    },
    {
        "section": "Mental Health Services (CPT 90837)",
        "text": (
            "Aetna 2026 Policy — Mental Health Services (CPT 90837 — Psychotherapy, "
            "60 minutes): The first 8 psychotherapy sessions per calendar year do not "
            "require prior authorization. Prior authorization is required beginning "
            "with the 9th session. To obtain authorization, the treating provider must "
            "submit a treatment plan including diagnosis, treatment goals, progress "
            "notes from sessions to date, and estimated number of additional sessions "
            "needed. Authorization is granted in increments of up to 8 additional "
            "sessions. Telehealth psychotherapy (audio-video) is covered at parity "
            "with in-person services. Audio-only telehealth requires a separate "
            "determination. Annual mental health deductible applies per plan design."
        ),
    },
]

# Full concatenated document (for reference / display)
AETNA_POLICY = "\n\n".join(
    f"[{chunk['section']}]\n{chunk['text']}" for chunk in POLICY_CHUNKS
)

# ---------------------------------------------------------------------------
# Step 2 — Build in-memory vector store using Titan embeddings
# ---------------------------------------------------------------------------

def embed(text: str) -> list[float]:
    """Generate an embedding vector using Bedrock Titan Embed v2."""
    response = bedrock.invoke_model(
        modelId=EMBED_MODEL_ID,
        body=json.dumps({"inputText": text}),
    )
    return json.loads(response["body"].read())["embedding"]


def build_vector_store(chunks: list[dict]) -> list[dict]:
    """
    Embed each policy chunk and return a vector store.

    Each entry: {"section": str, "text": str, "embedding": list[float]}
    """
    store = []
    for chunk in chunks:
        embedding = embed(chunk["text"])
        store.append({
            "section":   chunk["section"],
            "text":      chunk["text"],
            "embedding": embedding,
        })
        print(f"  Indexed: {chunk['section']}")
    return store


# ---------------------------------------------------------------------------
# Step 3 — Cosine similarity retrieval
# ---------------------------------------------------------------------------

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors (pure Python, no numpy)."""
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def find_relevant_chunks(
    query: str,
    vector_store: list[dict],
    top_k: int = 2,
) -> list[dict]:
    """
    Embed the query and return the top_k most similar policy chunks.

    Each returned entry adds a "score" key with the cosine similarity.
    """
    query_vec = embed(query)
    scored = [
        {**entry, "score": cosine_similarity(query_vec, entry["embedding"])}
        for entry in vector_store
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def divider(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def subdiv(label: str) -> None:
    print()
    print(f"  {'─' * 64}")
    print(f"  {label}")
    print(f"  {'─' * 64}")


def wrap_print(text: str, indent: int = 4, width: int = 66) -> None:
    """Print text with left indent, wrapping at word boundaries."""
    prefix = " " * indent
    words  = text.split()
    line   = prefix
    for word in words:
        if len(line) + len(word) + 1 > width + indent:
            print(line.rstrip())
            line = prefix + word + " "
        else:
            line += word + " "
    if line.strip():
        print(line.rstrip())


# ---------------------------------------------------------------------------
# Step 4 — Claude calls (with and without RAG context)
# ---------------------------------------------------------------------------

def ask_claude(prompt: str, system: str = "") -> tuple[str, dict]:
    """Single Bedrock Converse call; returns (text, usage)."""
    kwargs = dict(
        modelId=CLAUDE_MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
    )
    if system:
        kwargs["system"] = [{"text": system}]
    response = bedrock.converse(**kwargs)
    text = "".join(
        block["text"]
        for block in response["output"]["message"]["content"]
        if "text" in block
    )
    return text.strip(), response.get("usage", {})


SPECIALIST_SYSTEM = (
    "You are a healthcare eligibility specialist with expertise in "
    "insurance prior authorization requirements. Be concise and specific."
)


def run_no_rag(query: str) -> tuple[str, dict]:
    """Ask Claude with no policy context — baseline."""
    return ask_claude(query, system=SPECIALIST_SYSTEM)


def run_with_rag(
    query: str,
    vector_store: list[dict],
    top_k: int = 2,
) -> tuple[str, dict, list[dict]]:
    """Retrieve relevant chunks, inject into prompt, ask Claude."""
    chunks = find_relevant_chunks(query, vector_store, top_k=top_k)

    context = "\n\n".join(
        f"[Policy section: {c['section']}]\n{c['text']}" for c in chunks
    )
    rag_prompt = (
        f"Answer based on these Aetna policy documents:\n\n"
        f"{context}\n\n"
        f"Question: {query}"
    )
    text, usage = ask_claude(rag_prompt, system=SPECIALIST_SYSTEM)
    return text, usage, chunks


# ---------------------------------------------------------------------------
# Demo runner — NO RAG vs WITH RAG for a single query
# ---------------------------------------------------------------------------

def run_comparison(query: str, vector_store: list[dict]) -> None:
    print(f"\n  Query: \"{query}\"\n")

    # ── No RAG ───────────────────────────────────────────────────────────────
    subdiv("NO RAG  (Claude with no policy context)")
    no_rag_text, no_rag_usage = run_no_rag(query)
    wrap_print(no_rag_text)
    print()
    total = no_rag_usage.get("inputTokens", 0) + no_rag_usage.get("outputTokens", 0)
    print(f"  Tokens: {no_rag_usage.get('inputTokens', 0)} in / "
          f"{no_rag_usage.get('outputTokens', 0)} out / {total} total")

    # ── With RAG ─────────────────────────────────────────────────────────────
    subdiv("WITH RAG  (Claude grounded in retrieved policy chunks)")
    rag_text, rag_usage, retrieved = run_with_rag(query, vector_store, top_k=2)
    wrap_print(rag_text)
    print()
    total = rag_usage.get("inputTokens", 0) + rag_usage.get("outputTokens", 0)
    print(f"  Tokens: {rag_usage.get('inputTokens', 0)} in / "
          f"{rag_usage.get('outputTokens', 0)} out / {total} total")

    subdiv("Retrieved chunks")
    for rank, chunk in enumerate(retrieved, 1):
        print(f"  Rank {rank}  score={chunk['score']:.4f}  [{chunk['section']}]")
        wrap_print(chunk["text"][:220] + "…", indent=8)
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("  RAG DEMO — Bedrock Titan Embeddings + Claude Converse API")
    print("  us-east-1  |  cdk-dev")
    print("=" * 70)

    # ── Step 2: build vector store ──────────────────────────────────────────
    divider("Step 2 — Building in-memory vector store")
    print(f"  Embedding model : {EMBED_MODEL_ID}")
    print(f"  Chunks to index : {len(POLICY_CHUNKS)}\n")

    vector_store = build_vector_store(POLICY_CHUNKS)
    print(f"\n  Vector store built: {len(vector_store)} chunks indexed")
    print(f"  Embedding dimension: {len(vector_store[0]['embedding'])}")

    # ── Step 4: RAG vs No-RAG comparisons ───────────────────────────────────
    divider("Step 4 — Query 1: Knee surgery prior auth")
    run_comparison(
        "What are the prior auth requirements for knee surgery with Aetna?",
        vector_store,
    )

    divider("Step 4 — Query 2: Routine physical prior auth")
    run_comparison(
        "Is prior auth needed for a routine physical with Aetna?",
        vector_store,
    )

    print()
    print("=" * 70)
    print("  Demo complete.")
    print("  No-RAG: Claude relies on general training knowledge (may hallucinate).")
    print("  RAG   : Claude answers from retrieved policy text (grounded).")
    print("=" * 70)
    print()
