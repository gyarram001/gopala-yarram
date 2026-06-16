"""
Negative Instructions Demo using Amazon Bedrock Converse API
Shows how "do not" constraints shape output format, compliance, and safety.
"""

import json
import boto3

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

TRANSACTION = {
    "member_id": "AET-889221",
    "payer_name": "Aetna",
    "service_date": "2026-06-20",
    "service_type": "knee surgery",
    "diagnosis_code": "M17.11",
}

TRANSACTION_TEXT = "\n".join(f"  {k}: {v}" for k, v in TRANSACTION.items())


def call_bedrock(user_prompt: str, system_prompt: str = None) -> dict:
    kwargs = {
        "modelId": MODEL_ID,
        "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
        "inferenceConfig": {"temperature": 0.0, "maxTokens": 500},
    }
    if system_prompt:
        kwargs["system"] = [{"text": system_prompt}]

    response = bedrock.converse(**kwargs)
    return {
        "text": response["output"]["message"]["content"][0]["text"],
        "input_tokens": response["usage"]["inputTokens"],
        "output_tokens": response["usage"]["outputTokens"],
        "stop_reason": response["stopReason"],
    }


def try_parse_json(raw: str) -> tuple[bool, str]:
    """Returns (success, reason). Strips markdown fences before attempting parse."""
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        json.loads(cleaned)
        if raw.strip() != cleaned:
            return True, "PARSED (after stripping markdown fences)"
        return True, "PARSED (clean JSON — no fences to strip)"
    except json.JSONDecodeError as e:
        return False, f"FAILED — {e}"


def divider(title: str):
    print(f"\n{'═' * 70}")
    print(f"  {title}")
    print("═" * 70)


def print_parse_result(success: bool, reason: str):
    icon = "✓" if success else "✗"
    print(f"\n  {icon} json.loads() result: {reason}")


if __name__ == "__main__":
    json_results = {}

    print("\n" + "█" * 70)
    print("  NEGATIVE INSTRUCTIONS DEMO — Healthcare Eligibility")
    print(f"  Model : {MODEL_ID}")
    print("█" * 70)
    print(f"\n  Transaction:\n{TRANSACTION_TEXT}\n")

    # ── Demo 1: No negative instructions ─────────────────────────────────────
    divider("DEMO 1 — No Negative Instructions")
    print('  Prompt: "Analyze this eligibility transaction and return JSON"\n')

    prompt_1 = f"Analyze this eligibility transaction and return JSON:\n\n{TRANSACTION_TEXT}"
    result_1 = call_bedrock(prompt_1)

    print("  Raw response:")
    print("  " + "\n  ".join(result_1["text"].splitlines()))

    success_1, reason_1 = try_parse_json(result_1["text"])
    print_parse_result(success_1, reason_1)
    json_results["Demo 1 — No negative instructions"] = (success_1, reason_1)

    print(f"\n  Tokens: {result_1['input_tokens']} in / {result_1['output_tokens']} out")
    print(
        "\n  OBSERVATION: Without constraints, Claude may wrap JSON in markdown"
        "\n  code fences, add preamble text, or include trailing commentary —"
        "\n  all of which break a raw json.loads() call."
    )

    # ── Demo 2: With negative instructions ───────────────────────────────────
    divider("DEMO 2 — With Negative Instructions")
    print("  Prompt includes explicit 'do not' constraints.\n")

    prompt_2 = (
        f"Analyze this eligibility transaction:\n\n{TRANSACTION_TEXT}\n\n"
        "Return JSON only.\n"
        "Do not include any text outside the JSON.\n"
        "Do not add explanations, caveats, or suggestions.\n"
        "Do not use markdown code blocks.\n"
        "Do not say 'I' or refer to yourself.\n"
        "If uncertain, express it inside the JSON, not outside it."
    )
    result_2 = call_bedrock(prompt_2)

    print("  Raw response:")
    print("  " + "\n  ".join(result_2["text"].splitlines()))

    success_2, reason_2 = try_parse_json(result_2["text"])
    print_parse_result(success_2, reason_2)
    json_results["Demo 2 — With negative instructions"] = (success_2, reason_2)

    print(f"\n  Tokens: {result_2['input_tokens']} in / {result_2['output_tokens']} out")
    print(
        "\n  OBSERVATION: Each 'do not' closes a specific failure mode."
        "\n  No fences → raw json.loads() works. No self-references → cleaner"
        "\n  output. Uncertainty stays inside the JSON structure, not appended"
        "\n  as free text that breaks parsers."
    )

    # ── Demo 3: Healthcare-specific negative instructions ─────────────────────
    divider("DEMO 3 — Healthcare-Specific Negative Instructions")
    print("  System prompt encodes compliance and liability guardrails.\n")

    system_3 = (
        "You are a healthcare eligibility specialist. "
        "Never include member names, SSNs, or dates of birth in responses. "
        "Never make coverage guarantees — eligibility is not a guarantee of payment. "
        "Never recommend specific treatments or procedures. "
        "Never suggest the patient contact you directly. "
        "Always qualify eligibility findings with 'as of verification date'."
    )
    prompt_3 = (
        f"Analyze this transaction and summarize coverage for the front desk:\n\n"
        f"{TRANSACTION_TEXT}"
    )
    result_3 = call_bedrock(prompt_3, system_prompt=system_3)

    print("  Response:")
    print("  " + "\n  ".join(result_3["text"].splitlines()))

    print(f"\n  Tokens: {result_3['input_tokens']} in / {result_3['output_tokens']} out")
    print(
        "\n  OBSERVATION: Healthcare negative instructions act as a compliance"
        "\n  firewall. PHI stays out of responses. No coverage guarantees means"
        "\n  no liability exposure. No treatment recommendations keeps the AI"
        "\n  out of clinical decision-making."
    )

    # ── JSON parseability summary ─────────────────────────────────────────────
    divider("JSON PARSEABILITY SUMMARY")
    print()
    for demo, (success, reason) in json_results.items():
        icon = "✓" if success else "✗"
        print(f"  {icon}  {demo}")
        print(f"       {reason}\n")

    print("█" * 70)
    print("  TAKEAWAYS")
    print("█" * 70)
    print(
        "\n  1. No constraints    — Output format is unpredictable. Markdown fences,"
        "\n                         preamble text, and trailing commentary are common."
        "\n                         json.loads() likely fails on raw output."
        "\n"
        "\n  2. Format negatives  — Each 'do not' closes one failure mode. Together"
        "\n                         they guarantee clean, parseable JSON with no"
        "\n                         post-processing needed."
        "\n"
        "\n  3. Domain negatives  — Encode compliance rules as system-level constraints."
        "\n                         PHI protection, liability qualifiers, and scope"
        "\n                         limits belong in the system prompt, not the user"
        "\n                         prompt — they apply to every call, not just one.\n"
    )
