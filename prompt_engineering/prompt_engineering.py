"""
Prompt Engineering Techniques using Amazon Bedrock Converse API
Demonstrates 5 techniques applied to healthcare eligibility transactions.
"""

import json
import boto3

# ── Setup ────────────────────────────────────────────────────────────────────

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

TRANSACTION = {
    "member_id": "AET-889221",
    "payer_name": "Aetna",
    "service_date": "2026-06-20",
    "service_type": "knee surgery",
    "diagnosis_code": "M17.11",
    "provider_npi": "1234567890",
}

TRANSACTION_TEXT = "\n".join(f"  {k}: {v}" for k, v in TRANSACTION.items())


def call_bedrock(user_prompt: str, system_prompt: str = None) -> str:
    kwargs = {
        "modelId": MODEL_ID,
        "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
    }
    if system_prompt:
        kwargs["system"] = [{"text": system_prompt}]

    response = bedrock.converse(**kwargs)
    return response["output"]["message"]["content"][0]["text"]


def divider(title: str):
    print(f"\n{'═' * 70}")
    print(f"  {title}")
    print('═' * 70)


def sub(label: str):
    print(f"\n── {label} {'─' * (66 - len(label))}")


# ── Technique 1: Role Assignment ─────────────────────────────────────────────

def technique_1_role_assignment():
    divider("TECHNIQUE 1 — Role Assignment (BAD vs GOOD)")

    sub("BAD: No system prompt")
    bad_response = call_bedrock(
        f"Review this transaction:\n{TRANSACTION_TEXT}"
    )
    print(bad_response)

    sub("GOOD: Senior healthcare eligibility specialist persona")
    good_response = call_bedrock(
        user_prompt=f"Review this transaction:\n{TRANSACTION_TEXT}",
        system_prompt=(
            "You are a senior healthcare eligibility specialist with 10 years "
            "experience processing 270/271 transactions. You understand HIPAA "
            "compliance, payer requirements, and common eligibility issues."
        ),
    )
    print(good_response)

    sub("WHY IT MATTERS")
    print(
        "Without a role, Claude gives a generic response.\n"
        "With a domain-specific role, it applies 270/271 standards,\n"
        "HIPAA context, and payer-specific knowledge automatically."
    )


# ── Technique 2: Specificity ─────────────────────────────────────────────────

def technique_2_specificity():
    divider("TECHNIQUE 2 — Specificity (BAD vs GOOD)")

    sub("BAD: Vague question")
    bad_response = call_bedrock(
        f"Is this transaction okay?\n{TRANSACTION_TEXT}"
    )
    print(bad_response)

    sub("GOOD: Structured, specific questions")
    good_response = call_bedrock(
        f"Review this eligibility transaction:\n{TRANSACTION_TEXT}\n\n"
        "Identify:\n"
        "1. Any missing required fields for a 270 transaction\n"
        "2. Whether the diagnosis code format is valid (ICD-10-CM)\n"
        "3. Whether the service date is within a reasonable range\n"
        "4. Any payer-specific requirements for Aetna"
    )
    print(good_response)

    sub("WHY IT MATTERS")
    print(
        "A vague question gets a vague yes/no answer.\n"
        "Numbered, specific questions force Claude to address\n"
        "each dimension of eligibility validation explicitly."
    )


# ── Technique 3: Output Format Control ───────────────────────────────────────

def technique_3_output_format():
    divider("TECHNIQUE 3 — Output Format Control (Structured JSON)")

    prompt = (
        f"Analyze this eligibility transaction:\n{TRANSACTION_TEXT}\n\n"
        "Return ONLY a JSON object with exactly these fields:\n"
        "{\n"
        '  "is_valid": <boolean>,\n'
        '  "missing_fields": <list of strings>,\n'
        '  "issues": <list of strings describing each problem>,\n'
        '  "recommended_action": <string>\n'
        "}\n\n"
        "No explanation outside the JSON. No markdown code fences."
    )

    raw = call_bedrock(prompt)

    sub("Raw response from Claude")
    print(raw)

    sub("Parsed fields")
    try:
        # Strip markdown fences if Claude adds them despite the instruction
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        print(f"  is_valid          : {parsed['is_valid']}")
        print(f"  missing_fields    : {parsed['missing_fields']}")
        print(f"  issues            :")
        for issue in parsed["issues"]:
            print(f"    • {issue}")
        print(f"  recommended_action: {parsed['recommended_action']}")
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  [Parse error] {e}")

    sub("WHY IT MATTERS")
    print(
        "Structured output makes Claude's response machine-readable.\n"
        "Downstream systems can ingest the JSON directly without\n"
        "additional NLP or string parsing."
    )


# ── Technique 4: Few-Shot Examples ───────────────────────────────────────────

def technique_4_few_shot():
    divider("TECHNIQUE 4 — Few-Shot Examples")

    few_shot_prompt = (
        "You are a healthcare eligibility analyst. "
        "Here are two examples of how to analyse eligibility transactions:\n\n"

        "--- EXAMPLE 1 ---\n"
        "Transaction:\n"
        "  member_id: BCBS-112233\n"
        "  payer_name: BlueCross\n"
        "  service_date: 2026-01-15\n"
        "  service_type: annual physical\n"
        "  diagnosis_code: Z00.00\n"
        "  provider_npi: 9876543210\n\n"
        "Analysis:\n"
        "  VALID: All required 270 fields present.\n"
        "  Diagnosis Z00.00 (Encounter for general adult medical exam) is correct\n"
        "  for a preventive annual physical.\n"
        "  Service date 2026-01-15 is within acceptable range.\n"
        "  BlueCross typically covers annual physicals at 100% under preventive care.\n"
        "  Recommended action: Submit for eligibility check — likely to approve.\n\n"

        "--- EXAMPLE 2 ---\n"
        "Transaction:\n"
        "  member_id: UHC-445566\n"
        "  payer_name: UnitedHealth\n"
        "  service_date: 2023-03-01\n"
        "  service_type: MRI brain\n"
        "  diagnosis_code: \n"
        "  provider_npi: 1112223334\n\n"
        "Analysis:\n"
        "  INVALID: Missing diagnosis_code — required for imaging authorisation.\n"
        "  Service date 2023-03-01 is over 3 years in the past; likely stale.\n"
        "  UnitedHealth requires prior authorisation for brain MRIs.\n"
        "  Recommended action: Obtain diagnosis code and confirm service date\n"
        "  before submitting.\n\n"

        "--- NOW ANALYSE THIS TRANSACTION ---\n"
        f"{TRANSACTION_TEXT}\n\n"
        "Follow the same pattern as the examples above."
    )

    response = call_bedrock(few_shot_prompt)

    sub("Response (guided by two examples)")
    print(response)

    sub("WHY IT MATTERS")
    print(
        "Few-shot examples show Claude the exact output format and\n"
        "reasoning style expected. It learns the pattern — including\n"
        "payer-specific nuances — from the examples, not from instructions alone."
    )


# ── Technique 5: Chain of Thought ────────────────────────────────────────────

def technique_5_chain_of_thought():
    divider("TECHNIQUE 5 — Chain of Thought (with vs without)")

    base_question = (
        f"Evaluate whether this eligibility transaction should be approved:\n"
        f"{TRANSACTION_TEXT}"
    )

    sub("WITHOUT chain of thought")
    without_cot = call_bedrock(base_question)
    print(without_cot)

    sub("WITH chain of thought  (\"Think step by step:\")")
    with_cot = call_bedrock(base_question + "\n\nThink step by step:")
    print(with_cot)

    sub("WHY IT MATTERS")
    print(
        "Without CoT, Claude jumps to a conclusion.\n"
        "With 'Think step by step:', it externalises its reasoning —\n"
        "checking each field in sequence before reaching a verdict.\n"
        "This reduces errors and makes the decision auditable."
    )


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "█" * 70)
    print("  PROMPT ENGINEERING TECHNIQUES — Healthcare Eligibility")
    print("  Model :", MODEL_ID)
    print("█" * 70)

    technique_1_role_assignment()
    technique_2_specificity()
    technique_3_output_format()
    technique_4_few_shot()
    technique_5_chain_of_thought()

    print("\n" + "█" * 70)
    print("  All 5 techniques complete.")
    print("█" * 70 + "\n")
