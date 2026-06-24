"""
Guardrails Demo using Amazon Bedrock Converse API
Three layers of guardrails: prompt-level, code-level, and AWS Bedrock managed.
"""

import json
import boto3

bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-east-1")
bedrock_mgmt = boto3.client("bedrock", region_name="us-east-1")

MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

TRANSACTION = {
    "member_id": "AET-889221",  # phi-ok — synthetic test ID
    "payer_name": "Aetna",
    "service_date": "2026-06-20",
    "service_type": "knee surgery",
    "diagnosis_code": "M17.11",
}

TRANSACTION_TEXT = "\n".join(f"  {k}: {v}" for k, v in TRANSACTION.items())


# ── Shared helpers ────────────────────────────────────────────────────────────


def call_bedrock(
    user_prompt: str,
    system_prompt: str = None,
    guardrail_id: str = None,
    guardrail_version: str = "DRAFT",
) -> dict:
    kwargs = {
        "modelId": MODEL_ID,
        "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
        "inferenceConfig": {"temperature": 0.0, "maxTokens": 500},
    }
    if system_prompt:
        kwargs["system"] = [{"text": system_prompt}]
    if guardrail_id:
        kwargs["guardrailConfig"] = {
            "guardrailIdentifier": guardrail_id,
            "guardrailVersion": guardrail_version,
        }

    response = bedrock_runtime.converse(**kwargs)
    return {
        "text": response["output"]["message"]["content"][0]["text"],
        "stop_reason": response["stopReason"],
        "input_tokens": response["usage"]["inputTokens"],
        "output_tokens": response["usage"]["outputTokens"],
    }


def parse_json(raw: str) -> dict | None:
    cleaned = (
        raw.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def divider(title: str):
    print(f"\n{'═' * 70}")
    print(f"  {title}")
    print("═" * 70)


def sub(label: str):
    print(f"\n  ── {label}")


# ── Demo 1: Prompt guardrails ─────────────────────────────────────────────────


def demo_1_prompt_guardrails():
    divider("DEMO 1 — Prompt Guardrails (system prompt rules)")

    system = (
        "You are a healthcare eligibility specialist. "
        "Never make definitive coverage guarantees. "
        "Always qualify eligibility findings with: "
        "'eligibility does not guarantee payment'. "
        "If asked anything outside eligibility analysis, respond with exactly: "
        '{"error": "out_of_scope"}'
    )

    # 1a: Normal eligibility transaction
    sub("1a — Normal eligibility transaction")
    prompt_a = f"Analyze this eligibility transaction:\n\n{TRANSACTION_TEXT}"
    result_a = call_bedrock(prompt_a, system_prompt=system)
    print(f"\n{result_a['text']}")
    print(
        f"\n  Tokens: {result_a['input_tokens']} in / {result_a['output_tokens']} out"
    )

    # 1b: Off-topic input
    sub("1b — Off-topic input: clinical question")
    prompt_b = "What is the best treatment for knee pain?"
    result_b = call_bedrock(prompt_b, system_prompt=system)
    print(f"\n{result_b['text']}")
    print(
        f"\n  Tokens: {result_b['input_tokens']} in / {result_b['output_tokens']} out"
    )

    parsed_b = parse_json(result_b["text"])
    if parsed_b and parsed_b.get("error") == "out_of_scope":
        print("\n  ✓ Out-of-scope guardrail triggered correctly")
    else:
        print("\n  ✗ Out-of-scope guardrail did NOT trigger as expected")

    print(
        "\n  OBSERVATION: Prompt guardrails are the first line of defence."
        "\n  The system prompt encodes scope boundaries and compliance qualifiers"
        "\n  that apply to every call — no application code needed."
    )


# ── Demo 2: Code guardrails (output validation) ───────────────────────────────

REQUIRED_FIELDS = ["is_valid", "risk_level", "recommended_action"]
VALID_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH"}


def validate_analysis(parsed: dict) -> list[str]:
    """Returns a list of validation failure messages. Empty list = all good."""
    failures = []

    for field in REQUIRED_FIELDS:
        if field not in parsed:
            failures.append(f"missing required field: '{field}'")

    if "risk_level" in parsed:
        if parsed["risk_level"] not in VALID_RISK_LEVELS:
            failures.append(
                f"risk_level '{parsed['risk_level']}' is not one of {VALID_RISK_LEVELS}"
            )

    if "recommended_action" in parsed:
        if (
            not isinstance(parsed["recommended_action"], str)
            or not parsed["recommended_action"].strip()
        ):
            failures.append("recommended_action must be a non-empty string")

    if "is_valid" in parsed:
        if not isinstance(parsed["is_valid"], bool):
            failures.append(
                f"is_valid must be boolean, got {type(parsed['is_valid']).__name__}: "
                f"'{parsed['is_valid']}'"
            )

    return failures


def demo_2_code_guardrails():
    divider("DEMO 2 — Code Guardrails (validate Claude's output)")

    # Vague prompt — likely to return prose or non-conforming JSON
    prompt = f"Analyze this transaction:\n\n{TRANSACTION_TEXT}"
    result = call_bedrock(prompt)

    sub("Raw response from vague prompt")
    print(f"\n{result['text']}")
    print(f"\n  Tokens: {result['input_tokens']} in / {result['output_tokens']} out")

    sub("Validation result")
    parsed = parse_json(result["text"])

    if parsed is None:
        print("\n  ✗ Response is not JSON — validation skipped, saving blocked")
        print(
            '  → {"error": "validation_failed", "details": ["response is not valid JSON"]}'  # noqa: E501
        )
        return

    failures = validate_analysis(parsed)

    if failures:
        print(f"\n  ✗ Validation failed — {len(failures)} issue(s):")
        for f in failures:
            print(f"    • {f}")
        error_result = {"error": "validation_failed", "details": failures}
        print(f"\n  Returning: {json.dumps(error_result)}")
        print("  DynamoDB write: BLOCKED")
    else:
        print("\n  ✓ All fields valid — safe to save to DynamoDB")
        print(f"  is_valid          : {parsed['is_valid']}")
        print(f"  risk_level        : {parsed['risk_level']}")
        print(f"  recommended_action: {parsed['recommended_action']}")

    print(
        "\n  OBSERVATION: Code guardrails catch schema violations before they"
        "\n  reach storage. A vague prompt rarely returns the exact fields your"
        "\n  application expects — validate before you save."
    )


# ── Demo 3: AWS Bedrock Guardrails ─────────────────────────────────────────────


def demo_3_bedrock_guardrails():
    divider("DEMO 3 — AWS Bedrock Managed Guardrails")

    sub("Creating guardrail via boto3")
    try:
        response = bedrock_mgmt.create_guardrail(
            name="eligibility-guardrail",
            description="Healthcare eligibility agent guardrail",
            contentPolicyConfig={
                "filtersConfig": [
                    {"type": "HATE", "inputStrength": "HIGH", "outputStrength": "HIGH"},
                    {
                        "type": "VIOLENCE",
                        "inputStrength": "HIGH",
                        "outputStrength": "HIGH",
                    },
                    {
                        "type": "SEXUAL",
                        "inputStrength": "HIGH",
                        "outputStrength": "HIGH",
                    },
                ]
            },
            sensitiveInformationPolicyConfig={
                "piiEntitiesConfig": [
                    {"type": "US_SOCIAL_SECURITY_NUMBER", "action": "BLOCK"},
                    {"type": "EMAIL", "action": "ANONYMIZE"},
                    {"type": "PHONE", "action": "ANONYMIZE"},
                ]
            },
            blockedInputMessaging="This input is not allowed in the eligibility system.",  # noqa: E501
            blockedOutputsMessaging="This output has been blocked for compliance reasons.",  # noqa: E501
        )

        guardrail_id = response["guardrailId"]
        guardrail_arn = response["guardrailArn"]
        print("\n  ✓ Guardrail created")
        print(f"    ID  : {guardrail_id}")
        print(f"    ARN : {guardrail_arn}")

    except bedrock_mgmt.exceptions.ConflictException:
        # Guardrail with this name already exists — look it up
        print("\n  Guardrail 'eligibility-guardrail' already exists — looking it up...")
        paginator = bedrock_mgmt.get_paginator("list_guardrails")
        guardrail_id = None
        for page in paginator.paginate():
            for g in page["guardrails"]:
                if g["name"] == "eligibility-guardrail":
                    guardrail_id = g["guardrailId"]
                    break
            if guardrail_id:
                break

        if not guardrail_id:
            print("  ✗ Could not find existing guardrail — skipping Demo 3")
            return

        print(f"  ✓ Found existing guardrail ID: {guardrail_id}")

    # Make a Bedrock call using the guardrail
    sub("Calling Bedrock with guardrailConfig")
    prompt = f"Analyze this eligibility transaction:\n\n{TRANSACTION_TEXT}"

    try:
        result = call_bedrock(
            prompt, guardrail_id=guardrail_id, guardrail_version="DRAFT"
        )
        print(f"\n{result['text']}")
        print(
            f"\n  Tokens    : {result['input_tokens']} in / {result['output_tokens']} out"  # noqa: E501
        )
        print(f"  Stop reason: {result['stop_reason']}")
        print("\n  ✓ Response passed through Bedrock guardrail without being blocked")
    except bedrock_runtime.exceptions.ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "ValidationException":
            print(f"\n  ✗ Bedrock rejected the call: {e}")
        else:
            raise

    print(
        "\n  OBSERVATION: AWS Bedrock guardrails are enforced at the API layer —"
        "\n  before Claude ever sees the prompt or after it generates output."
        "\n  They block harmful content and anonymise PII (SSN, email, phone)"
        "\n  without any application code. Use them alongside prompt and code"
        "\n  guardrails for defence-in-depth."
    )


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "█" * 70)
    print("  GUARDRAILS DEMO — Three Layers of Protection")
    print(f"  Model : {MODEL_ID}")
    print("█" * 70)

    demo_1_prompt_guardrails()
    demo_2_code_guardrails()
    demo_3_bedrock_guardrails()

    print("\n" + "█" * 70)
    print("  SUMMARY — Defence in Depth")
    print("█" * 70)
    print(
        "\n  Layer 1 — Prompt guardrails   : scope limits and compliance qualifiers"
        "\n                                   in the system prompt. Zero extra cost."
        "\n"
        "\n  Layer 2 — Code guardrails     : validate schema and field types before"
        "\n                                   saving. Catches prompt drift and model"
        "\n                                   formatting surprises."
        "\n"
        "\n  Layer 3 — Bedrock guardrails  : AWS-managed content filtering and PII"
        "\n                                   anonymisation at the API layer."
        "\n                                   Enforced even if prompt or code fails.\n"
    )
