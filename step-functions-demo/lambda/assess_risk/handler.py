import json
import os
import re
import boto3
from botocore.exceptions import ClientError

# AWS_REGION is auto-set by Lambda runtime; falls back for local testing
REGION = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

# boto3 client at module level — reused across Lambda warm invocations
bedrock = boto3.client("bedrock-runtime", region_name=REGION)

# Fields allowed in the Bedrock prompt — all other fields (member_id, transaction_id,
# validation_status, etc.) are excluded at the source by the allowlist below.
# If event gains new fields, they are blocked by default, not leaked to Bedrock logs.
PROMPT_FIELDS = frozenset({"service_type", "payer", "service_date"})

# Strict per-field allowlist — reject values that don't match expected shape.
# This prevents prompt injection: an attacker who can control field values
# cannot embed newlines, escape sequences, or instruction-looking text.
_FIELD_PATTERNS = {
    "service_type": re.compile(r"^[A-Za-z0-9 _/()-]{1,100}$"),
    "payer": re.compile(r"^[A-Za-z0-9 .&'()-]{1,100}$"),
    "service_date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
}

# Required fields that must be present in the Bedrock response
REQUIRED_ASSESSMENT_FIELDS = frozenset(
    {"risk_level", "risk_reason", "prior_auth_required"}
)


def parse_bedrock_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON — CLAUDE.md convention.

    Raises RuntimeError on parse failure so the caller doesn't need to inspect
    a return value for an error key — fail fast, let Step Functions Catch handle it.
    """
    cleaned = (
        raw.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Bedrock response as JSON: {e}") from e


def handler(event, context):
    """
    Step 2: call Bedrock to assess risk level of the transaction.

    Input:  validated transaction dict (from ValidateFields output)
    Output: same dict + risk_level, risk_reason, prior_auth_required

    The Choice state downstream reads $.risk_level to decide the branch:
    HIGH → HumanReview, LOW/MEDIUM → SaveDecision, else → UnknownRiskLevel (Fail)

    Design note: risk assessment belongs in AI, not code.
    Writing rules like "if CPT code starts with 27 → HIGH" is brittle —
    thousands of CPT codes, payer-specific exceptions, diagnosis combinations.
    Claude applies clinical knowledge the same way a senior specialist would.
    """
    # transaction_id is a system-generated correlation ID (TXN-2024-xxx / UUID),
    # not a patient identifier. Used here only for CloudWatch log correlation.
    txn_id = event.get("transaction_id")

    # Build prompt from allowlisted fields only — no member identifiers reach Bedrock.
    # Each value is validated against a strict regex before inclusion; values that
    # don't match are replaced with a safe placeholder rather than silently included.
    # This prevents prompt injection even if upstream validation were bypassed.
    prompt_data = {}
    for k, v in event.items():
        if k not in PROMPT_FIELDS:
            continue
        pattern = _FIELD_PATTERNS.get(k)
        safe_v = str(v)
        if pattern and not pattern.match(safe_v):
            safe_v = f"[INVALID_{k.upper()}]"
        prompt_data[k] = safe_v
    # XML tags delimit data from instructions — an established prompt-injection defense.
    # Even if a field value contained instruction-like text, it is clearly bounded
    # between <transaction_data> tags, making it much harder for injected text to
    # be treated as a new instruction by the model.
    #
    # Data-handling note: service_date + service_type + payer is sent to Bedrock.
    # This combination is NOT a direct patient identifier (no member_id, name, DOB).
    # In production, review AWS Bedrock's data handling policy for your compliance
    # posture and consider Bedrock Guardrails if re-identification is a concern.
    prompt = (
        "You are a healthcare eligibility specialist.\n\n"
        "Assess the risk level of the eligibility transaction below.\n\n"
        "<transaction_data>\n"
        f"{json.dumps(prompt_data, indent=2)}\n"
        "</transaction_data>\n\n"
        "Return ONLY a valid JSON object with exactly these fields:\n"
        '{"risk_level": "LOW" | "MEDIUM" | "HIGH", '
        '"risk_reason": "one sentence", '
        '"prior_auth_required": true | false}\n\n'
        "Risk criteria:\n"
        "- HIGH: surgical procedures, MRI/advanced imaging, expensive treatments "
        "(anything requiring prior authorization)\n"
        "- MEDIUM: specialist visits, physical therapy, outpatient procedures\n"
        "- LOW: routine preventive care, primary care, lab work\n\n"
        "Do not include markdown fences or any text outside the JSON object."
    )

    try:
        response = bedrock.converse(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"temperature": 0.0, "maxTokens": 200},
        )
    except ClientError as e:
        print(
            json.dumps(
                {
                    "level": "ERROR",
                    # "correlation_id" not "transaction_id" — logged value is a
                    # system-generated ID (TXN-xxx/UUID), never a patient identifier.
                    "correlation_id": txn_id,
                    "error_code": e.response["Error"]["Code"],
                    "message": str(e),
                }
            )
        )
        raise

    stop_reason = response["stopReason"]

    # CLAUDE.md rule: never save or act on a truncated response
    if stop_reason == "max_tokens":
        raise RuntimeError(
            "Bedrock response truncated — risk assessment incomplete, cannot proceed"
        )

    raw = response["output"]["message"]["content"][0]["text"]
    # parse_bedrock_json raises RuntimeError on failure — no error key to check
    assessment = parse_bedrock_json(raw)

    # Validate that Bedrock returned all required fields before merging into state
    missing = REQUIRED_ASSESSMENT_FIELDS - set(assessment.keys())
    if missing:
        raise RuntimeError(f"Bedrock response missing required fields: {missing}")

    print(
        json.dumps(
            {
                "level": "INFO",
                "correlation_id": txn_id,  # system-generated ID, not a patient ID
                "risk_level": assessment["risk_level"],
                "prior_auth_required": assessment["prior_auth_required"],
            }
        )
    )

    # Merge assessment fields into state — next state (Choice) reads $.risk_level
    return {**event, **assessment}
