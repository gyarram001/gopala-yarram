#!/usr/bin/env python3
"""
Local simulation of the Step Functions eligibility pipeline.

Demonstrates:
- State flowing as JSON between steps (output of one = input of next)
- ValidationError caught by Catch block → Fail state
- Choice state routing on $.risk_level
- waitForTaskToken HITL pause/resume pattern

Calls Bedrock for real risk assessment output (assess_risk step).
DynamoDB steps are simulated — deploy the CDK stack for full end-to-end.

Run: AWS_PROFILE=cdk-dev python step-functions-demo/run_local.py
"""
import os
import json
import uuid
import importlib.util

# Must be set before handler modules load — boto3 clients are created at module
# level, so AWS_REGION and credentials must be in environment at import time.
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
)
os.environ.setdefault("DYNAMODB_TABLE_NAME", "eligibility-pipeline-decisions")

BASE = os.path.dirname(os.path.abspath(__file__))


def load_handler(module_name: str, rel_path: str):
    """
    Load a Lambda handler module from a file path.

    Can't use `import lambda.validate_fields.handler` because `lambda` is a
    Python keyword. importlib.util bypasses the naming collision.
    """
    path = os.path.join(BASE, rel_path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


validate_mod = load_handler("validate_fields", "lambda/validate_fields/handler.py")
assess_mod = load_handler("assess_risk", "lambda/assess_risk/handler.py")


class MockContext:
    """Minimal Lambda context — only the fields our handlers use."""

    function_name = "local-simulation"
    aws_request_id = "local-request"
    memory_limit_in_mb = 128


# ── Step simulation functions ───────────────────────────────────────────────


def step_validate(state: dict) -> dict | None:
    """
    Task state: ValidateFields

    Returns updated state on success.
    Returns None if ValidationError is raised (Catch block fires → Fail state).
    """
    print("\n  → [Task] ValidateFields Lambda")
    try:
        result = validate_mod.handler(dict(state), MockContext())
        print("    ✓ Validation PASSED")
        return result
    except Exception as exc:
        error_type = type(exc).__name__
        print(f"    ✗ {error_type}: {exc}")
        print("\n  [Step Functions Catch]")
        print(f'    ErrorEquals: ["{error_type}"]')
        print("    → routes to: TransactionRejected (Fail state)")
        print("    [EXECUTION FAILED] error=ValidationFailed")
        return None


def step_assess_risk(state: dict) -> dict:
    """Task state: AssessRisk — calls Bedrock, adds risk_level to state."""
    print("\n  → [Task] AssessRisk Lambda  (calling Bedrock...)")
    result = assess_mod.handler(dict(state), MockContext())
    print(f"    risk_level:          {result['risk_level']}")
    print(f"    risk_reason:         {result['risk_reason']}")
    print(f"    prior_auth_required: {result['prior_auth_required']}")
    return result


def step_choice(state: dict) -> str:
    """
    Choice state: RouteOnRisk

    Evaluates $.risk_level from execution state.
    Returns routing decision: "HIGH", "AUTO", or "UNKNOWN".
    """
    risk = state.get("risk_level", "UNKNOWN")
    print(f'\n  → [Choice] RouteOnRisk  ($.risk_level = "{risk}")')
    if risk == "HIGH":
        print("    Condition[0] string_equals('HIGH') → TRUE")
        print("    → next state: HumanReview")
        return "HIGH"
    elif risk in ("LOW", "MEDIUM"):
        print("    Condition[0] string_equals('HIGH') → FALSE")
        print("    Condition[1] or_(LOW, MEDIUM)      → TRUE")
        print("    → next state: SaveDecision")
        return "AUTO"
    else:
        print("    No condition matched → Default")
        print("    → next state: UnknownRiskLevel (Fail)")
        return "UNKNOWN"


def step_human_review(state: dict) -> str:
    """
    Task state: HumanReview (waitForTaskToken)

    Simulates the pause/resume pattern — no actual DynamoDB or Step Functions call.
    Returns the simulated human decision.
    """
    task_token = f"AQDKWFFlYWsK{uuid.uuid4().hex[:24]}"  # realistic token format
    print("\n  → [Task] HumanReview Lambda  (waitForTaskToken)")
    print(f"    [Step Functions] Generated task token: {task_token[:20]}...")
    print(f"    Lambda receives: transaction={{...}}, taskToken={task_token[:10]}...")
    print("    Lambda stores token in DynamoDB → returns")
    print("\n    [Step Functions] EXECUTION PAUSED")
    print("    State machine is now suspended — no compute cost while waiting.")
    print("    heartbeat timeout: 3 days")
    print("\n    [Reviewer opens case in UI, clicks Approve]")
    print("    Reviewer calls:")
    print("      states.send_task_success(")
    print("        taskToken = <stored token>,")
    print('        output    = {"human_decision": "APPROVED"}')
    print("      )")
    print("\n    [Step Functions] EXECUTION RESUMED")
    print('    State now includes: {...original state, "human_decision": "APPROVED"}')
    print("    → next state: SaveDecision")
    return "APPROVED"


def step_save_decision(state: dict, human_decision: str = None) -> None:
    """
    Task state: SaveDecision

    [LOCAL MODE] — prints what would be written to DynamoDB.
    """
    if human_decision:
        state = {**state, "human_decision": human_decision}

    final_status = "DENIED" if human_decision == "DENIED" else "APPROVED"
    # member_id excluded — matches production save_decision handler policy.
    # transaction_id is the audit key; member context lives in the source system.
    item = {
        "transaction_id": state["transaction_id"],
        "service_type": state["service_type"],
        "payer": state["payer"],
        "risk_level": state.get("risk_level"),
        "risk_reason": state.get("risk_reason"),
        "prior_auth_required": state.get("prior_auth_required"),
        "human_decision": human_decision,
        "final_status": final_status,
    }
    print("\n  → [Task] SaveDecision Lambda  [LOCAL — would write to DynamoDB]")
    print(f"    {json.dumps(item, indent=4)}")
    print(f"\n  [EXECUTION SUCCEEDED]  final_status: {final_status}")


# ── Scenario runner ─────────────────────────────────────────────────────────


def run_scenario(title: str, transaction: dict) -> None:
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print(f"{'=' * 65}")
    print("\nInput state:")
    print(f"  {json.dumps(transaction, indent=4)}")
    print("\n--- Execution begins ---")

    # Step 1: ValidateFields
    state = step_validate(transaction)
    if state is None:
        return

    # Step 2: AssessRisk
    state = step_assess_risk(state)

    # Step 3: Choice routing
    route = step_choice(state)

    # Step 4: Branch
    if route == "HIGH":
        human_decision = step_human_review(state)
        step_save_decision(state, human_decision)
    elif route == "AUTO":
        step_save_decision(state)
    else:
        print("\n  [EXECUTION FAILED] UnknownRiskLevel")
        print(f"  Transaction blocked — unknown risk level '{state.get('risk_level')}'")


# ── Scenarios ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Scenario 1: missing field → ValidationError → Fail state (no Bedrock call)
    run_scenario(
        "SCENARIO 1 — Missing field → ValidationError → TransactionRejected",
        {
            "transaction_id": "TXN-2024-001",
            "member_id": "MBR-2024-001",
            "payer": "Aetna",
            "service_date": "2026-07-15",
            # service_type intentionally omitted
        },
    )

    # Scenario 2: routine checkup → expect LOW → auto-approve
    run_scenario(
        "SCENARIO 2 — Routine checkup → LOW risk → AutoApprove",
        {
            "transaction_id": "TXN-2024-002",
            "member_id": "MBR-2024-002",
            "payer": "Aetna",
            "service_type": "Annual wellness visit / preventive care screening",
            "service_date": "2026-07-15",
        },
    )

    # Scenario 3: knee surgery → expect HIGH → HITL → approve
    run_scenario(
        "SCENARIO 3 — Knee surgery → HIGH risk → HumanReview → HITL",
        {
            "transaction_id": "TXN-2024-003",
            "member_id": "MBR-2024-003",
            "payer": "Aetna",
            "service_type": "Total knee replacement surgery (CPT 27447)",
            "service_date": "2026-07-20",
        },
    )
