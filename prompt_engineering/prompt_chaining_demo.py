"""
Prompt Chaining Demo using Amazon Bedrock Converse API
Processes an eligibility transaction through a 4-step chain.
Each step receives the outputs of all previous steps as context.
"""

import json
import time
import boto3

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

TRANSACTION = {
    "member_id": "AET-889221",
    "payer_name": "Aetna",
    "service_date": "2026-06-20",
    "service_type": "knee surgery",
    "diagnosis_code": "M17.11",
    "provider_npi": "1447362571",
}

TRANSACTION_TEXT = "\n".join(f"  {k}: {v}" for k, v in TRANSACTION.items())


def call_bedrock(system_prompt: str, user_prompt: str) -> dict:
    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"temperature": 0.0, "maxTokens": 500},
    )
    text = response["output"]["message"]["content"][0]["text"]
    usage = response["usage"]
    stop_reason = response["stopReason"]
    return {
        "text": text,
        "input_tokens": usage["inputTokens"],
        "output_tokens": usage["outputTokens"],
        "stop_reason": stop_reason,
    }


def parse_json(raw: str) -> dict:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)


def divider(title: str):
    print(f"\n{'═' * 70}")
    print(f"  {title}")
    print("═" * 70)


def print_step_result(step: int, label: str, result: dict, elapsed: float):
    print(f"\n  Response:")
    try:
        parsed = parse_json(result["text"])
        print(json.dumps(parsed, indent=4))
    except json.JSONDecodeError:
        print(result["text"])
    print(f"\n  Tokens  : {result['input_tokens']} in / {result['output_tokens']} out")
    print(f"  Stop    : {result['stop_reason']}")
    print(f"  Time    : {elapsed:.2f}s")


if __name__ == "__main__":
    print("\n" + "█" * 70)
    print("  PROMPT CHAINING DEMO — Healthcare Eligibility (4-Step Chain)")
    print(f"  Model : {MODEL_ID}")
    print("█" * 70)
    print(f"\n  Input transaction:\n{TRANSACTION_TEXT}\n")

    total_input_tokens = 0
    total_output_tokens = 0
    chain_start = time.time()

    # ── Step 1: Validation ────────────────────────────────────────────────────
    divider("STEP 1 — Validation")

    today = time.strftime("%Y-%m-%d")
    system_1 = "You are a healthcare data validator. Respond in JSON only."
    prompt_1 = (
        f"Today's date is {today}. "
        "Validate these fields for a 270 eligibility transaction. "
        "service_date is valid if it is within 90 days before or after today.\n\n"
        f"{TRANSACTION_TEXT}\n\n"
        "Return exactly:\n"
        '{"is_valid": <bool>, "missing_fields": [<strings>], "invalid_fields": [<strings>]}'
    )

    t0 = time.time()
    step1 = call_bedrock(system_1, prompt_1)
    elapsed_1 = time.time() - t0

    total_input_tokens += step1["input_tokens"]
    total_output_tokens += step1["output_tokens"]
    print_step_result(1, "Validation", step1, elapsed_1)

    try:
        step1_parsed = parse_json(step1["text"])
    except json.JSONDecodeError:
        print("\n  [CHAIN STOPPED] Step 1 returned invalid JSON — cannot continue.")
        raise SystemExit(1)

    if not step1_parsed.get("is_valid", False):
        print("\n" + "█" * 70)
        print("  CHAIN STOPPED AT STEP 1 — Transaction failed validation")
        print("█" * 70)
        print(f"\n  Missing fields  : {step1_parsed.get('missing_fields', [])}")
        print(f"  Invalid fields  : {step1_parsed.get('invalid_fields', [])}")
        print("\n  Fix the transaction and resubmit.\n")
        raise SystemExit(0)

    print("\n  ✓ Validation passed — proceeding to Step 2")

    # ── Step 2: Payer Requirements ────────────────────────────────────────────
    divider("STEP 2 — Payer Requirements")

    system_2 = "You are a payer requirements specialist. Respond in JSON only."
    prompt_2 = (
        f"Transaction validated:\n{step1['text']}\n\n"
        "Payer: Aetna\n"
        "Service: knee surgery\n\n"
        "Return exactly:\n"
        '{"prior_auth_required": <bool>, "auth_requirements": [<strings>]}'
    )

    t0 = time.time()
    step2 = call_bedrock(system_2, prompt_2)
    elapsed_2 = time.time() - t0

    total_input_tokens += step2["input_tokens"]
    total_output_tokens += step2["output_tokens"]
    print_step_result(2, "Payer Requirements", step2, elapsed_2)

    # ── Step 3: Risk Assessment ───────────────────────────────────────────────
    divider("STEP 3 — Risk Assessment")

    system_3 = "You are a healthcare risk assessor. Respond in JSON only."
    prompt_3 = (
        f"Validation result:\n{step1['text']}\n\n"
        f"Payer requirements:\n{step2['text']}\n\n"
        "Return exactly:\n"
        '{"risk_level": "<LOW|MEDIUM|HIGH>", "risk_reasons": [<strings>]}'
    )

    t0 = time.time()
    step3 = call_bedrock(system_3, prompt_3)
    elapsed_3 = time.time() - t0

    total_input_tokens += step3["input_tokens"]
    total_output_tokens += step3["output_tokens"]
    print_step_result(3, "Risk Assessment", step3, elapsed_3)

    # ── Step 4: Recommended Action ────────────────────────────────────────────
    divider("STEP 4 — Recommended Action")

    system_4 = "You are a healthcare operations specialist. Respond in JSON only."
    prompt_4 = (
        f"Validation:\n{step1['text']}\n\n"
        f"Payer requirements:\n{step2['text']}\n\n"
        f"Risk assessment:\n{step3['text']}\n\n"
        "Return exactly:\n"
        '{"recommended_action": "<string>", "immediate_steps": [<strings>]}'
    )

    t0 = time.time()
    step4 = call_bedrock(system_4, prompt_4)
    elapsed_4 = time.time() - t0

    total_input_tokens += step4["input_tokens"]
    total_output_tokens += step4["output_tokens"]
    print_step_result(4, "Recommended Action", step4, elapsed_4)

    # ── Summary ───────────────────────────────────────────────────────────────
    total_elapsed = time.time() - chain_start

    divider("CHAIN SUMMARY")
    print(f"\n  {'Step':<35} {'In':>6} {'Out':>6} {'Time':>8}")
    print(f"  {'-'*35} {'------':>6} {'------':>6} {'--------':>8}")
    print(f"  {'Step 1 — Validation':<35} {step1['input_tokens']:>6} {step1['output_tokens']:>6} {elapsed_1:>7.2f}s")
    print(f"  {'Step 2 — Payer Requirements':<35} {step2['input_tokens']:>6} {step2['output_tokens']:>6} {elapsed_2:>7.2f}s")
    print(f"  {'Step 3 — Risk Assessment':<35} {step3['input_tokens']:>6} {step3['output_tokens']:>6} {elapsed_3:>7.2f}s")
    print(f"  {'Step 4 — Recommended Action':<35} {step4['input_tokens']:>6} {step4['output_tokens']:>6} {elapsed_4:>7.2f}s")
    print(f"  {'-'*35} {'------':>6} {'------':>6} {'--------':>8}")
    print(f"  {'TOTAL':<35} {total_input_tokens:>6} {total_output_tokens:>6} {total_elapsed:>7.2f}s")

    print("\n" + "█" * 70)
    print("  TAKEAWAYS")
    print("█" * 70)
    print(
        "\n  Each step receives all prior outputs as context — the chain builds"
        "\n  progressively richer understanding without one mega-prompt."
        "\n"
        "\n  Early exit at Step 1 prevents wasted API calls on invalid data."
        "\n"
        "\n  Input tokens grow each step because prior outputs are forwarded."
        "\n  This is the cost of chaining — trade more tokens for focused steps.\n"
    )
