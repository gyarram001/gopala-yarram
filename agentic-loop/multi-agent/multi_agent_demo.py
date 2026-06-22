#!/usr/bin/env python3
"""
Multi-Agent Demo — Amazon Bedrock Converse API with Claude Sonnet
Profile : cdk-dev  |  Region : us-east-1

Three patterns demonstrated:
  Pattern 1 — Orchestrator + Workers
  Pattern 2 — Sequential Pipeline
  Pattern 3 — Parallel Specialists
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
PROFILE  = "cdk-dev"
REGION   = "us-east-1"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

TRANSACTION = {
    "member_id":      "AET-889221",
    "payer_name":     "Aetna",
    "service_date":   "2026-06-20",
    "service_type":   "knee surgery",
    "diagnosis_code": "M17.11",
    "estimated_cost": "$45,000",
}


# ─────────────────────────────────────────────────────────────────────────────
# Bedrock client
# ─────────────────────────────────────────────────────────────────────────────
def make_client():
    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    return session.client("bedrock-runtime")


# ─────────────────────────────────────────────────────────────────────────────
# Core agent helper
# ─────────────────────────────────────────────────────────────────────────────
def call_agent(client, name: str, system: str, user_msg: str) -> dict:
    """
    Send one Bedrock Converse request.

    Returns:
        dict with keys: agent, output, tokens, elapsed
    """
    t0 = time.time()
    response = client.converse(
        modelId=MODEL_ID,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user_msg}]}],
    )
    elapsed = time.time() - t0

    text   = response["output"]["message"]["content"][0]["text"]
    usage  = response["usage"]
    tokens = usage.get("inputTokens", 0) + usage.get("outputTokens", 0)

    return {"agent": name, "output": text, "tokens": tokens, "elapsed": elapsed}


# ─────────────────────────────────────────────────────────────────────────────
# Print helpers
# ─────────────────────────────────────────────────────────────────────────────
def banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def section(label: str) -> None:
    print(f"\n{'─' * 65}")
    print(f"  {label}")
    print("─" * 65)


def print_result(r: dict) -> None:
    print(f"\n[{r['agent']}]  ({r['tokens']} tokens | {r['elapsed']:.2f}s)")
    print(r["output"])


def parse_json_output(text: str) -> dict:
    """Strip optional markdown fences and parse JSON."""
    raw = text.strip()
    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else parts[0]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ═════════════════════════════════════════════════════════════════════════════
# PATTERN 1 — Orchestrator + Workers
# ═════════════════════════════════════════════════════════════════════════════
def pattern1_orchestrator_workers(client: object) -> str:
    """
    Orchestrator plans → 3 workers execute → Orchestrator synthesises.

    Flow:
      Orchestrator-Planner  →  validator, payer_specialist, risk_assessor
                            →  Orchestrator-Synthesiser (final decision)
    """
    banner("PATTERN 1 — Orchestrator + Workers")
    tx_json      = json.dumps(TRANSACTION, indent=2)
    total_tokens = 0
    t_start      = time.time()

    # ── Step 1 · Orchestrator plans subtasks ─────────────────────────────
    section("Step 1 · Orchestrator — planning subtasks")
    plan_system = (
        "You are an eligibility workflow orchestrator. "
        "Break this transaction into 3 subtasks and assign each to the right specialist:\n"
        "  - validator: checks fields and formats\n"
        "  - payer_specialist: checks payer requirements\n"
        "  - risk_assessor: scores risk level\n"
        'Return ONLY valid JSON: {"subtasks": [{"agent": "...", "task": "...", "priority": 1}]}'
    )
    plan_r = call_agent(client, "Orchestrator-Planner", plan_system,
                        f"Plan subtasks for this eligibility transaction:\n{tx_json}")
    total_tokens += plan_r["tokens"]
    print_result(plan_r)

    plan = parse_json_output(plan_r["output"])

    # ── Step 2 · Workers run in priority order ───────────────────────────
    worker_systems = {
        "validator": (
            "You are a 270 transaction validator. Only validate field formats and completeness. "
            'Return ONLY valid JSON: {"is_valid": true, "missing_fields": [], "invalid_fields": []}'
        ),
        "payer_specialist": (
            "You are an Aetna payer requirements specialist. Only assess payer-specific requirements. "
            'Return ONLY valid JSON: {"prior_auth_required": true, "requirements": [], '
            '"estimated_processing_days": 5}'
        ),
        "risk_assessor": (
            "You are a healthcare risk assessor. Only assess financial and clinical risk. "
            'Return ONLY valid JSON: {"risk_level": "high", "risk_score": 85, "risk_factors": []}'
        ),
    }

    worker_outputs: dict[str, str] = {}
    for subtask in sorted(plan["subtasks"], key=lambda x: x["priority"]):
        agent_key  = subtask["agent"]
        task_desc  = subtask["task"]
        sys_prompt = worker_systems.get(agent_key,
                                        "You are a specialist agent. Analyse and respond.")
        section(f"Step 2 · Worker — {agent_key}  (priority {subtask['priority']})")
        wr = call_agent(client, agent_key, sys_prompt,
                        f"Transaction:\n{tx_json}\n\nYour specific task: {task_desc}")
        total_tokens            += wr["tokens"]
        worker_outputs[agent_key] = wr["output"]
        print_result(wr)

    # ── Step 3 · Orchestrator synthesises ────────────────────────────────
    section("Step 3 · Orchestrator — synthesising final decision")
    synthesis_input = (
        f"Original transaction:\n{tx_json}\n\n"
        f"Validator report:\n{worker_outputs.get('validator', 'N/A')}\n\n"
        f"Payer specialist report:\n{worker_outputs.get('payer_specialist', 'N/A')}\n\n"
        f"Risk assessor report:\n{worker_outputs.get('risk_assessor', 'N/A')}"
    )
    synth_system = (
        "You are an eligibility workflow orchestrator. "
        "Synthesise these specialist reports into a final eligibility decision. "
        'Return ONLY valid JSON: {"decision": "approved|denied|pending", "confidence": 90, '
        '"recommended_action": "...", "requires_human_review": false}'
    )
    synth_r = call_agent(client, "Orchestrator-Synthesiser", synth_system, synthesis_input)
    total_tokens += synth_r["tokens"]
    print_result(synth_r)

    elapsed = time.time() - t_start
    print(f"\nPattern 1 complete | total tokens: {total_tokens} | total time: {elapsed:.2f}s")
    return synth_r["output"]


# ═════════════════════════════════════════════════════════════════════════════
# PATTERN 2 — Sequential Pipeline
# ═════════════════════════════════════════════════════════════════════════════
def pattern2_sequential_pipeline(client: object) -> str:
    """
    Each agent's full output becomes the next agent's input.

    Flow:
      Intake → Validation → Enrichment → Decision
    """
    banner("PATTERN 2 — Sequential Pipeline")
    tx_json      = json.dumps(TRANSACTION, indent=2)
    total_tokens = 0
    t_start      = time.time()

    # ── Agent 1 · Intake ─────────────────────────────────────────────────
    section("Agent 1 · Intake — extract & normalise")
    a1 = call_agent(
        client, "Intake-Agent",
        (
            "You are a healthcare intake agent. Extract and normalise all fields from the "
            "eligibility transaction. Standardise dates to ISO-8601, costs to numeric USD, "
            "and diagnosis codes to uppercase. "
            'Return ONLY valid JSON: {"normalised_fields": {}, "extracted_metadata": {}}'
        ),
        f"Eligibility transaction to intake:\n{tx_json}",
    )
    total_tokens += a1["tokens"]
    print_result(a1)

    # ── Agent 2 · Validation ─────────────────────────────────────────────
    section("Agent 2 · Validation — validate normalised fields from Agent 1")
    a2 = call_agent(
        client, "Validation-Agent",
        (
            "You are a 270/271 transaction validator. Given normalised fields from the intake "
            "agent, check completeness and format compliance against X12 EDI standards. "
            'Return ONLY valid JSON: {"is_valid": true, "errors": [], "warnings": [], '
            '"compliance_score": 95}'
        ),
        f"Intake agent output:\n{a1['output']}",
    )
    total_tokens += a2["tokens"]
    print_result(a2)

    # ── Agent 3 · Enrichment ─────────────────────────────────────────────
    section("Agent 3 · Enrichment — add payer context using Agent 2 output")
    a3 = call_agent(
        client, "Enrichment-Agent",
        (
            "You are a payer-context enrichment agent. Using the validated transaction data, "
            "add relevant Aetna payer rules, prior-auth thresholds, and ICD-10 M17.11 "
            "clinical context (primary osteoarthritis, right knee). "
            'Return ONLY valid JSON: {"payer_rules": {}, "prior_auth_threshold": "$20000", '
            '"clinical_context": {}, "enriched_data": {}}'
        ),
        f"Validation output:\n{a2['output']}\n\nOriginal transaction:\n{tx_json}",
    )
    total_tokens += a3["tokens"]
    print_result(a3)

    # ── Agent 4 · Decision ───────────────────────────────────────────────
    section("Agent 4 · Decision — final eligibility ruling using all prior outputs")
    combined = (
        f"Intake:\n{a1['output']}\n\n"
        f"Validation:\n{a2['output']}\n\n"
        f"Enrichment:\n{a3['output']}"
    )
    a4 = call_agent(
        client, "Decision-Agent",
        (
            "You are a final eligibility decision agent. Using all pipeline outputs, "
            "produce a definitive eligibility ruling. "
            'Return ONLY valid JSON: {"decision": "approved|denied|pending", '
            '"eligibility_status": "...", "coverage_percentage": 80, '
            '"patient_responsibility": "$9000", "next_steps": [], '
            '"requires_human_review": false}'
        ),
        combined,
    )
    total_tokens += a4["tokens"]
    print_result(a4)

    elapsed = time.time() - t_start
    print(f"\nPattern 2 complete | total tokens: {total_tokens} | total time: {elapsed:.2f}s")
    return a4["output"]


# ═════════════════════════════════════════════════════════════════════════════
# PATTERN 3 — Parallel Specialists
# ═════════════════════════════════════════════════════════════════════════════
def pattern3_parallel_specialists(client: object) -> str:
    """
    Orchestrator fans out to 3 agents simultaneously via ThreadPoolExecutor,
    then merges results. Includes sequential baseline for speed comparison.

    Flow:
      Orchestrator ──┬── Validator-Agent   ─┐
                     ├── Payer-Agent        ─┤ (parallel)
                     └── Risk-Agent         ─┘
                          └── Merge-Orchestrator (final decision)
    """
    banner("PATTERN 3 — Parallel Specialists")
    tx_json      = json.dumps(TRANSACTION, indent=2)
    total_tokens = 0

    specialist_configs = [
        (
            "Validator-Agent",
            (
                "You are a 270 transaction validator. Validate all field formats and completeness. "
                'Return ONLY valid JSON: {"is_valid": true, "missing_fields": [], '
                '"invalid_fields": [], "compliance_notes": []}'
            ),
        ),
        (
            "Payer-Agent",
            (
                "You are an Aetna payer requirements specialist. "
                "Assess payer-specific requirements for this transaction. "
                'Return ONLY valid JSON: {"prior_auth_required": true, "requirements": [], '
                '"estimated_processing_days": 5, "payer_notes": []}'
            ),
        ),
        (
            "Risk-Agent",
            (
                "You are a healthcare risk assessor. Assess financial and clinical risk. "
                'Return ONLY valid JSON: {"risk_level": "high", "risk_score": 82, '
                '"risk_factors": [], "mitigation_suggestions": []}'
            ),
        ),
    ]

    # ── Parallel execution ────────────────────────────────────────────────
    section("Fanning out — 3 specialist agents running IN PARALLEL")
    t_parallel_start  = time.time()
    parallel_results: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(call_agent, client, name, sys_prompt,
                        f"Transaction:\n{tx_json}"): name
            for name, sys_prompt in specialist_configs
        }
        for future in as_completed(futures):
            name = futures[future]
            r    = future.result()
            parallel_results[name] = r
            print_result(r)
            total_tokens += r["tokens"]

    t_parallel = time.time() - t_parallel_start
    print(f"\n  Parallel wall-clock time : {t_parallel:.2f}s")

    # ── Sequential baseline (same prompts, same agents) ───────────────────
    section("Sequential baseline — same 3 agents run one-at-a-time")
    t_seq_start = time.time()
    seq_tokens  = 0
    for name, sys_prompt in specialist_configs:
        r = call_agent(client, f"{name}-seq", sys_prompt,
                       f"Transaction:\n{tx_json}")
        seq_tokens += r["tokens"]
        print(f"  [{r['agent']}]  {r['elapsed']:.2f}s")

    t_seq = time.time() - t_seq_start
    print(f"\n  Sequential wall-clock time : {t_seq:.2f}s")
    print(f"  Speedup from parallelism   : {t_seq / t_parallel:.2f}x")
    total_tokens += seq_tokens

    # ── Orchestrator merges parallel results ──────────────────────────────
    section("Orchestrator — merging parallel results into final decision")
    merge_input = "\n\n".join(
        f"[{name}]:\n{r['output']}"
        for name, r in parallel_results.items()
    )
    merge_r = call_agent(
        client, "Merge-Orchestrator",
        (
            "You are an eligibility workflow orchestrator. "
            "Merge these parallel specialist reports into a single final eligibility decision. "
            'Return ONLY valid JSON: {"decision": "approved|denied|pending", "confidence": 88, '
            '"specialist_consensus": {}, "recommended_action": "...", '
            '"requires_human_review": false}'
        ),
        f"Transaction:\n{tx_json}\n\nParallel specialist reports:\n{merge_input}",
    )
    total_tokens += merge_r["tokens"]
    print_result(merge_r)

    t_total = t_parallel + t_seq + merge_r["elapsed"]
    print(
        f"\nPattern 3 complete | total tokens: {total_tokens} | "
        f"parallel time: {t_parallel:.2f}s | seq baseline: {t_seq:.2f}s | "
        f"speedup: {t_seq / t_parallel:.2f}x"
    )
    return merge_r["output"]


# ═════════════════════════════════════════════════════════════════════════════
# Entry point
# ═════════════════════════════════════════════════════════════════════════════
def main() -> None:
    print("\n" + "#" * 70)
    print("  Multi-Agent Demo — Amazon Bedrock Converse API + Claude Sonnet")
    print(f"  Profile: {PROFILE}  |  Region: {REGION}  |  Model: {MODEL_ID}")
    print("#" * 70)
    print("\nEligibility Transaction:")
    print(json.dumps(TRANSACTION, indent=2))

    client = make_client()

    decision1 = pattern1_orchestrator_workers(client)
    decision2 = pattern2_sequential_pipeline(client)
    decision3 = pattern3_parallel_specialists(client)

    banner("SUMMARY — Final Decisions from All 3 Patterns")
    print("\nPattern 1 (Orchestrator + Workers):")
    print(decision1)
    print("\nPattern 2 (Sequential Pipeline):")
    print(decision2)
    print("\nPattern 3 (Parallel Specialists):")
    print(decision3)


if __name__ == "__main__":
    main()
