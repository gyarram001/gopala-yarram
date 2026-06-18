"""
memory_demo.py — Four memory patterns with Amazon Bedrock Converse API.

Demo 1: No memory       — fresh messages list on every call (stateless)
Demo 2: Short-term mem  — conversation history carried forward in-process
Demo 3: Long-term mem   — member context persisted to / retrieved from DynamoDB
Demo 4: Summarization   — compress old turns to control token growth
"""

import json
import boto3
from boto3.dynamodb.conditions import Key

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL_ID  = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
REGION    = "us-east-1"
PROFILE   = "cdk-dev"
TABLE_NAME = "eligibility-decisions"
MEMBER_PK  = "MEMBER#AET-889221"          # stored in the table's pk field

session  = boto3.Session(profile_name=PROFILE, region_name=REGION)
bedrock  = session.client("bedrock-runtime")
dynamodb     = session.resource("dynamodb")
dynamodb_client = session.client("dynamodb")


def ensure_table() -> "boto3.resources.factory.dynamodb.Table":
    """Return the DynamoDB table, creating it first if it does not exist."""
    existing = dynamodb_client.list_tables().get("TableNames", [])
    if TABLE_NAME not in existing:
        print(f"  [setup] Table '{TABLE_NAME}' not found — creating it...")
        dynamodb_client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "transaction_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "transaction_id", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        waiter = dynamodb_client.get_waiter("table_exists")
        waiter.wait(TableName=TABLE_NAME)
        print(f"  [setup] Table '{TABLE_NAME}' is now active.\n")
    return dynamodb.Table(TABLE_NAME)


table = ensure_table()

# ---------------------------------------------------------------------------
# Thin wrapper around Bedrock Converse
# ---------------------------------------------------------------------------

def converse(messages: list[dict], system: str = "") -> tuple[str, dict]:
    """Call Bedrock Converse and return (reply_text, usage_dict)."""
    kwargs = dict(modelId=MODEL_ID, messages=messages)
    if system:
        kwargs["system"] = [{"text": system}]
    resp   = bedrock.converse(**kwargs)
    text   = ""
    for block in resp["output"]["message"]["content"]:
        if "text" in block:
            text += block["text"]
    return text.strip(), resp.get("usage", {})


def user_msg(text: str) -> dict:
    return {"role": "user", "content": [{"text": text}]}


def assistant_msg(text: str) -> dict:
    return {"role": "assistant", "content": [{"text": text}]}


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


# ===========================================================================
# DEMO 1 — No memory (stateless)
# ===========================================================================

def demo_no_memory() -> None:
    divider("DEMO 1 — No Memory (Stateless)")
    print("  Each call gets a brand-new messages list. Claude has no\n"
          "  knowledge of previous calls.\n")

    prompts = [
        "My member ID is AET-889221 and I have Aetna insurance.",
        "What is my member ID?",
        "What insurance do I have?",
    ]

    for i, prompt in enumerate(prompts, 1):
        subdiv(f"Call {i}")
        print(f"  User : {prompt}")
        # Fresh list every time — no history
        reply, _ = converse([user_msg(prompt)])
        print(f"  Claude: {reply}")


# ===========================================================================
# DEMO 2 — Short-term memory (in-process conversation history)
# ===========================================================================

def demo_short_term_memory() -> None:
    divider("DEMO 2 — Short-Term Memory (Conversation History)")
    print("  Each call appends to a shared messages list. Claude\n"
          "  remembers everything said earlier in this session.\n")

    messages: list[dict] = []

    prompts = [
        "My member ID is AET-889221 and I have Aetna insurance.",
        "What is my member ID?",
        "What insurance do I have?",
    ]

    for i, prompt in enumerate(prompts, 1):
        subdiv(f"Call {i}  (messages in history: {len(messages)})")
        print(f"  User : {prompt}")
        messages.append(user_msg(prompt))
        reply, usage = converse(messages)
        messages.append(assistant_msg(reply))
        print(f"  Claude: {reply}")
        if i == len(prompts):
            print()
            print(f"  >> Call {i} token usage (shows history accumulation):")
            print(f"     Input tokens  : {usage.get('inputTokens', 0)}")
            print(f"     Output tokens : {usage.get('outputTokens', 0)}")
            print(f"     Total tokens  : {usage.get('inputTokens', 0) + usage.get('outputTokens', 0)}")


# ===========================================================================
# DEMO 3 — Long-term memory (DynamoDB)
# ===========================================================================

def demo_long_term_memory() -> None:
    divider("DEMO 3 — Long-Term Memory (DynamoDB)")
    print("  Step A: Save member info to DynamoDB after the first conversation.")
    print("  Step B: Start a completely fresh session, load context from")
    print("          DynamoDB, inject into system prompt, then ask about member.\n")

    # ------------------------------------------------------------------
    # Step A: simulate end of a prior session — persist member context
    # ------------------------------------------------------------------
    subdiv("Step A — Persisting member info to DynamoDB")
    member_context = {
        "transaction_id": MEMBER_PK,       # table's partition key
        "member_id": "AET-889221",
        "insurance": "Aetna",
        "plan_type": "PPO",
        "service_history": "knee surgery requested 2026-06-20",
    }
    table.put_item(Item=member_context)
    print(f"  Saved to DynamoDB table '{TABLE_NAME}':")
    print(f"  {json.dumps(member_context, indent=4)}")

    # ------------------------------------------------------------------
    # Step B: brand-new session — retrieve context and inject into prompt
    # ------------------------------------------------------------------
    subdiv("Step B — Fresh session: loading context from DynamoDB")
    db_resp = table.get_item(Key={"transaction_id": MEMBER_PK})
    retrieved = db_resp.get("Item", {})
    print(f"  Retrieved from DynamoDB:")
    print(f"  {json.dumps(retrieved, indent=4, default=str)}")

    # Build system prompt that carries the long-term context
    system_prompt = (
        "You are a healthcare eligibility specialist. "
        f"Known member context: {json.dumps(retrieved, default=str)}"
    )

    # Fresh messages — no conversation history at all
    fresh_messages = [
        user_msg("What insurance does member AET-889221 have?")
    ]

    subdiv("Step B — Asking Claude (empty conversation history)")
    print(f"  System : {system_prompt}")
    print()
    print(f"  User   : {fresh_messages[0]['content'][0]['text']}")
    reply, usage = converse(fresh_messages, system=system_prompt)
    print(f"  Claude : {reply}")
    print()
    print(f"  >> Token usage:")
    print(f"     Input tokens  : {usage.get('inputTokens', 0)}")
    print(f"     Output tokens : {usage.get('outputTokens', 0)}")


# ===========================================================================
# DEMO 4 — Conversation summarization
# ===========================================================================

# Scripted 8-turn eligibility conversation (user lines only).
# Claude's replies are real Bedrock calls; user lines are pre-written
# to keep the demo deterministic.
ELIGIBILITY_TURNS = [
    # Turn 1 — member intro
    "Hi, I'm a member with Aetna insurance. My member ID is AET-889221.",
    # Turn 3 — answer Claude's question about service type
    "I need knee surgery — specifically a total knee replacement.",
    # Turn 5 — answer Claude's question about prior auth history
    "Yes, I had one prior auth approved last December for a consultation. "
    "I've submitted 2 claims total with Aetna.",
    # Turn 7 — answer Claude's question about diagnosis
    "My diagnosis code is M17.11 — that's unilateral primary osteoarthritis "
    "of the right knee. My orthopedist says conservative treatment hasn't worked.",
]

ELIGIBILITY_SYSTEM = (
    "You are a healthcare eligibility specialist conducting an intake interview. "
    "After each member response, ask exactly ONE follow-up question to gather "
    "the next missing piece of information needed for an eligibility decision. "
    "Be concise — one short paragraph maximum per response."
)

SUMMARIZE_PROMPT = (
    "Summarize this conversation history concisely, preserving all key facts: "
    "member ID, payer, service details, and any decisions made."
)


def count_tokens_in_messages(messages: list[dict]) -> int:
    """Estimate tokens for a messages list via a Bedrock call with max_tokens=1."""
    # Bedrock reports inputTokens even when it generates nothing useful,
    # so we make a minimal completion call to get an accurate count.
    resp = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": ELIGIBILITY_SYSTEM}],
        messages=messages,
        inferenceConfig={"maxTokens": 1},
    )
    return resp.get("usage", {}).get("inputTokens", 0)


def messages_to_transcript(messages: list[dict]) -> str:
    """Flatten a messages list into a plain-text transcript for summarization."""
    lines = []
    for msg in messages:
        role = msg["role"].upper()
        for block in msg["content"]:
            if "text" in block:
                lines.append(f"{role}: {block['text']}")
    return "\n\n".join(lines)


def demo_summarization() -> None:
    divider("DEMO 4 — Conversation Summarization")
    print("  Simulate an 8-turn eligibility intake, then compress turns 1-6")
    print("  into a single summary message and show the token savings.\n")

    # ------------------------------------------------------------------
    # Phase 1: build up 8 turns of real conversation
    # ------------------------------------------------------------------
    subdiv("Phase 1 — Building 8-turn conversation")
    messages: list[dict] = []

    for turn_num, user_text in enumerate(ELIGIBILITY_TURNS, 1):
        real_turn = turn_num * 2 - 1          # turns 1, 3, 5, 7
        print(f"  [Turn {real_turn}] User  : {user_text}")
        messages.append(user_msg(user_text))

        reply, _ = converse(messages, system=ELIGIBILITY_SYSTEM)
        print(f"  [Turn {real_turn + 1}] Claude: {reply}")
        print()
        messages.append(assistant_msg(reply))

    # Token count with the full 8-turn history
    full_token_count = count_tokens_in_messages(messages)
    print(f"  >> Full 8-turn history input tokens : {full_token_count}")

    # ------------------------------------------------------------------
    # Phase 2: summarize turns 1-6, keep turns 7-8 verbatim
    # ------------------------------------------------------------------
    subdiv("Phase 2 — Summarizing turns 1-6 (keeping turns 7-8 intact)")

    old_turns   = messages[:6]   # turns 1-6  (3 user + 3 assistant)
    recent_turns = messages[6:]  # turns 7-8  (1 user + 1 assistant)

    transcript = messages_to_transcript(old_turns)
    summary_request = [
        user_msg(f"{SUMMARIZE_PROMPT}\n\n---\n{transcript}")
    ]
    summary_text, summary_usage = converse(summary_request)

    print(f"  Summarization call — input tokens : {summary_usage.get('inputTokens', 0)}")
    print(f"  Summary produced:\n")
    # indent each line of the summary
    for line in summary_text.splitlines():
        print(f"    {line}")
    print()

    # ------------------------------------------------------------------
    # Phase 3: build compressed history and measure savings
    # ------------------------------------------------------------------
    subdiv("Phase 3 — Compressed history vs original")

    compressed_messages = (
        [user_msg(f"[CONVERSATION SUMMARY]\n{summary_text}")]
        + [assistant_msg("Understood. I have the full context from our earlier discussion.")]
        + recent_turns
    )

    compressed_token_count = count_tokens_in_messages(compressed_messages)

    saved   = full_token_count - compressed_token_count
    pct     = (saved / full_token_count * 100) if full_token_count else 0

    print(f"  Original  history  ({len(messages)} messages) : {full_token_count:>5} input tokens")
    print(f"  Compressed history ({len(compressed_messages)} messages) : {compressed_token_count:>5} input tokens")
    print(f"  Tokens saved                          : {saved:>5}  ({pct:.1f}% reduction)")

    # ------------------------------------------------------------------
    # Phase 4: verify Claude still has full context after compression
    # ------------------------------------------------------------------
    subdiv("Phase 4 — Verification: does Claude still know everything?")

    verification_q = (
        "Based on our conversation, please confirm: "
        "what is my member ID, who is my payer, what procedure am I requesting, "
        "and what is my diagnosis code?"
    )
    print(f"  User   : {verification_q}\n")
    compressed_messages.append(user_msg(verification_q))
    final_reply, final_usage = converse(compressed_messages, system=ELIGIBILITY_SYSTEM)

    print(f"  Claude : {final_reply}")
    print()
    print(f"  >> Final call input tokens (compressed history) : "
          f"{final_usage.get('inputTokens', 0)}")


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    demo_no_memory()
    demo_short_term_memory()
    demo_long_term_memory()
    demo_summarization()

    print()
    print("=" * 70)
    print("  All demos complete.")
    print("=" * 70)
    print()
