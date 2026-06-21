"""
human_in_loop_demo.py — Human-in-the-Loop pattern with Amazon Bedrock
Converse API, DynamoDB, and SNS.

Scenario: eligibility agent pauses for human review when risk is HIGH,
auto-approves when LOW or MEDIUM.

Flow:
  Step 1 — Bedrock analyzes the transaction and returns a risk assessment.
  Step 2 — HIGH risk: saves PENDING_REVIEW record to DynamoDB, publishes
            SNS notification, then simulates a human reviewer approving.
  Step 3 — Agent polls DynamoDB until status leaves PENDING_REVIEW, then
            calls Bedrock for final next steps.
  Step 4 — LOW risk: same Step 1, but requires_human_review=False so the
            agent auto-approves without pausing.
"""

import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import boto3

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL_ID       = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
REGION         = "us-east-1"
PROFILE        = "cdk-dev"
TABLE_NAME     = "eligibility-decisions"
SNS_TOPIC_NAME = "eligibility-human-review"

POLL_INTERVAL_SECONDS = 1
MAX_POLL_ATTEMPTS     = 10

# ---------------------------------------------------------------------------
# AWS session + clients
# ---------------------------------------------------------------------------
session         = boto3.Session(profile_name=PROFILE, region_name=REGION)
bedrock         = session.client("bedrock-runtime")
dynamodb        = session.resource("dynamodb")
dynamodb_client = session.client("dynamodb")
sns             = session.client("sns")

# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------
HIGH_RISK_TRANSACTION = {
    "member_id":      "AET-889221",
    "payer_name":     "Aetna",
    "service_date":   "2026-06-20",
    "service_type":   "experimental cancer treatment",
    "diagnosis_code": "C34.11",
    "estimated_cost": "$85,000",
}

LOW_RISK_TRANSACTION = {
    "member_id":      "UHC-445521",
    "payer_name":     "United",
    "service_date":   "2026-06-25",
    "service_type":   "routine physical",
    "diagnosis_code": "Z00.00",
    "estimated_cost": "$150",
}

ANALYSIS_SYSTEM_PROMPT = (
    "You are a healthcare eligibility specialist. "
    "Analyze the transaction and return ONLY a JSON object with this exact structure:\n"
    "{\n"
    '  "risk_level": "HIGH" | "MEDIUM" | "LOW",\n'
    '  "confidence": <float 0.0-1.0>,\n'
    '  "requires_human_review": <true | false>,\n'
    '  "reason": "<string>",\n'
    '  "recommended_action": "<string>"\n'
    "}\n"
    "Set requires_human_review=true if risk_level is HIGH or confidence < 0.8. "
    "Return ONLY the JSON object, no additional text."
)

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


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def expires_iso() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()


# ---------------------------------------------------------------------------
# Bedrock response helpers
# ---------------------------------------------------------------------------

def extract_text(response: dict) -> str:
    """Concatenate all text blocks from a Bedrock Converse response."""
    parts = []
    for block in response.get("output", {}).get("message", {}).get("content", []):
        if "text" in block:
            parts.append(block["text"])
    return "".join(parts).strip()


def parse_json_response(text: str) -> dict:
    """Parse JSON from a Bedrock text response, stripping any markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = lines[1:]                              # drop opening fence line
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]                         # drop closing fence line
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# DynamoDB helpers
# ---------------------------------------------------------------------------

def float_to_decimal(obj: object) -> object:
    """Recursively convert Python floats to Decimal for DynamoDB storage."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [float_to_decimal(v) for v in obj]
    return obj


def ensure_table():
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


# ---------------------------------------------------------------------------
# SNS helper
# ---------------------------------------------------------------------------

def ensure_sns_topic() -> str:
    """Return the SNS topic ARN, creating the topic if it does not exist."""
    resp = sns.create_topic(Name=SNS_TOPIC_NAME)   # idempotent
    arn  = resp["TopicArn"]
    print(f"  [setup] SNS topic ready: {arn}")
    return arn


# ---------------------------------------------------------------------------
# Step 1 — Bedrock transaction analysis
# ---------------------------------------------------------------------------

def analyze_transaction(transaction: dict) -> dict:
    """Call Bedrock Converse to assess risk and return the parsed JSON analysis."""
    subdiv("Step 1 — Analyzing transaction with Bedrock")
    print(f"  Transaction:\n{json.dumps(transaction, indent=4)}\n")

    user_message = (
        "Analyze this transaction:\n\n"
        + json.dumps(transaction, indent=2)
    )

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": ANALYSIS_SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_message}]}],
    )

    raw_text = extract_text(response)
    analysis = parse_json_response(raw_text)

    usage = response.get("usage", {})
    print(f"  AI analysis:")
    print(f"    risk_level            : {analysis.get('risk_level')}")
    print(f"    confidence            : {analysis.get('confidence')}")
    print(f"    requires_human_review : {analysis.get('requires_human_review')}")
    print(f"    reason                : {analysis.get('reason')}")
    print(f"    recommended_action    : {analysis.get('recommended_action')}")
    print(
        f"  Tokens: {usage.get('inputTokens', 0)} in "
        f"/ {usage.get('outputTokens', 0)} out"
    )

    return analysis


# ---------------------------------------------------------------------------
# Step 2 — Save for human review + SNS notification
# ---------------------------------------------------------------------------

def save_for_review(
    table,
    sns_topic_arn: str,
    transaction: dict,
    analysis: dict,
) -> str:
    """Persist a PENDING_REVIEW record to DynamoDB and notify via SNS."""
    subdiv("Step 2 — Saving pending review to DynamoDB")

    transaction_id = f"REVIEW#{uuid.uuid4()}"

    item = float_to_decimal({
        "transaction_id": transaction_id,
        "status":         "PENDING_REVIEW",
        "transaction":    transaction,
        "ai_analysis":    analysis,
        "created_at":     now_iso(),
        "expires_at":     expires_iso(),
    })
    table.put_item(Item=item)

    print(f"  Transaction saved for human review: {transaction_id}")
    print(f"  Agent paused — waiting for human approval")

    # Notify the human reviewer
    sns.publish(
        TopicArn=sns_topic_arn,
        Subject="[Eligibility Agent] Human review required",
        Message=(
            f"A transaction requires your review.\n\n"
            f"Transaction ID : {transaction_id}\n"
            f"Member ID      : {transaction.get('member_id')}\n"
            f"Service type   : {transaction.get('service_type')}\n"
            f"Estimated cost : {transaction.get('estimated_cost')}\n"
            f"Risk level     : {analysis.get('risk_level')}\n"
            f"Reason         : {analysis.get('reason')}\n"
        ),
    )
    print(f"  SNS notification published to: {SNS_TOPIC_NAME}")

    return transaction_id


# ---------------------------------------------------------------------------
# Simulate human review  (pauses 2 s, then writes APPROVED to DynamoDB)
# ---------------------------------------------------------------------------

def simulate_human_approval(table, transaction_id: str) -> None:
    """Sleep 2 seconds to simulate human review latency, then approve."""
    subdiv("Simulating human review (sleeping 2 seconds...)")
    time.sleep(2)

    review_notes = "Verified patient eligibility, approved for review"

    table.update_item(
        Key={"transaction_id": transaction_id},
        UpdateExpression=(
            "SET #st = :status, reviewed_by = :reviewer, "
            "review_notes = :notes, reviewed_at = :ts"
        ),
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={
            ":status":   "APPROVED",
            ":reviewer": "john.smith@company.com",
            ":notes":    review_notes,
            ":ts":       now_iso(),
        },
    )
    print(f"  Human reviewer : john.smith@company.com")
    print(f"  Review notes   : {review_notes}")
    print(f"  DynamoDB status updated → APPROVED")


# ---------------------------------------------------------------------------
# Step 3a — Poll DynamoDB until status is no longer PENDING_REVIEW
# ---------------------------------------------------------------------------

def poll_for_decision(table, transaction_id: str) -> dict:
    """Poll every second (up to MAX_POLL_ATTEMPTS) until status changes."""
    subdiv(
        f"Step 3 — Polling DynamoDB every {POLL_INTERVAL_SECONDS}s "
        f"(max {MAX_POLL_ATTEMPTS} polls)"
    )

    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        resp   = table.get_item(Key={"transaction_id": transaction_id})
        record = resp.get("Item", {})
        status = record.get("status", "UNKNOWN")

        print(f"  Poll {attempt}/{MAX_POLL_ATTEMPTS}: status = {status}")

        if status != "PENDING_REVIEW":
            print(f"  Human approved — agent resuming")
            return record

        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        f"No decision received after {MAX_POLL_ATTEMPTS} polls "
        f"for transaction {transaction_id}"
    )


# ---------------------------------------------------------------------------
# Step 3b — Final Bedrock call after human approval
# ---------------------------------------------------------------------------

def get_final_recommendation(review_notes: str) -> str:
    """Call Bedrock to produce final next steps after human approval."""
    subdiv("Step 3 — Getting final recommendation from Bedrock")

    prompt = (
        f"The human reviewer approved this transaction with notes: "
        f'"{review_notes}". What are the final next steps?'
    )

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": "You are a healthcare eligibility specialist."}],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
    )

    text  = extract_text(response)
    usage = response.get("usage", {})
    print(
        f"  Final recommendation "
        f"(tokens: {usage.get('inputTokens', 0)} in "
        f"/ {usage.get('outputTokens', 0)} out):\n"
    )
    for line in text.splitlines():
        print(f"    {line}")

    return text


# ---------------------------------------------------------------------------
# Path A — HIGH risk (pauses for human review)
# ---------------------------------------------------------------------------

def run_high_risk_path(table, sns_topic_arn: str) -> None:
    divider("PATH A — HIGH RISK  |  experimental cancer treatment  |  $85,000")

    # Step 1 — analyze
    analysis = analyze_transaction(HIGH_RISK_TRANSACTION)

    if not analysis.get("requires_human_review"):
        # Unexpected — AI classified as not needing review; skip pause
        risk = analysis.get("risk_level", "UNKNOWN")
        print(f"\n  AI returned requires_human_review=False (risk={risk}). "
              "Auto-approving.\n")
        return

    # Step 2 — save to DynamoDB + SNS
    transaction_id = save_for_review(
        table, sns_topic_arn, HIGH_RISK_TRANSACTION, analysis
    )

    # Simulate human running concurrently (sequential in this demo)
    simulate_human_approval(table, transaction_id)

    # Step 3 — poll + final Bedrock call
    record       = poll_for_decision(table, transaction_id)
    review_notes = record.get("review_notes", "Approved.")
    get_final_recommendation(review_notes)

    print()
    print("  PATH A COMPLETE — HIGH risk transaction processed with human review.")


# ---------------------------------------------------------------------------
# Path B — LOW risk (auto-approves, no pause)
# ---------------------------------------------------------------------------

def run_low_risk_path(table) -> None:
    divider("PATH B — LOW RISK  |  routine physical  |  $150")

    # Step 1 — analyze
    analysis = analyze_transaction(LOW_RISK_TRANSACTION)

    if analysis.get("requires_human_review"):
        # Unexpected — AI flagged low-risk for review; handle gracefully
        print(
            "\n  AI unexpectedly flagged this LOW risk transaction for human review.\n"
            "  Routing to human review queue...\n"
        )
        return

    risk_level = analysis.get("risk_level", "UNKNOWN")
    action     = analysis.get("recommended_action", "Proceed.")

    subdiv("Step 4 — Auto-approving (no human review needed)")
    print(f"  Risk level : {risk_level}")
    print(f"  Confidence : {analysis.get('confidence')}")
    print(f"  Action     : {action}")
    print()
    print("  Agent completed without pausing for human review.")
    print()
    print("  PATH B COMPLETE — LOW risk transaction auto-approved.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("  HUMAN-IN-THE-LOOP DEMO")
    print("  Bedrock Converse API + DynamoDB + SNS  |  us-east-1  |  cdk-dev")
    print("=" * 70)

    table         = ensure_table()
    sns_topic_arn = ensure_sns_topic()

    run_high_risk_path(table, sns_topic_arn)
    run_low_risk_path(table)

    print()
    print("=" * 70)
    print("  Demo complete.")
    print("  PATH A (HIGH risk)  : paused for human review, then resumed.")
    print("  PATH B (LOW risk)   : auto-approved without human intervention.")
    print("=" * 70)
    print()
