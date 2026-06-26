import json
import os
import boto3
from datetime import datetime, timezone

REGION = os.getenv("AWS_REGION", "us-east-1")
TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "eligibility-pipeline-decisions")

dynamodb = boto3.resource("dynamodb", region_name=REGION)


def handler(event, context):
    """
    HITL step: receive task token from Step Functions, store it for the reviewer.

    How waitForTaskToken works:
    1. Step Functions generates a unique token for this execution + state
    2. Calls this Lambda with {"transaction": {...}, "taskToken": "AbCdEf..."}
    3. PAUSES the state machine — it does NOT wait for this Lambda to return
    4. This Lambda stores the token in DynamoDB keyed by transaction_id
    5. A reviewer (via API/UI) looks up the token, reviews the case, calls:
         states.send_task_success(
             taskToken=token, output={"human_decision": "APPROVED"}
         )
    6. Step Functions RESUMES from the paused state, output flows to SaveDecision

    Key insight: this Lambda's RETURN VALUE is ignored by Step Functions.
    The execution only resumes when SendTaskSuccess/SendTaskFailure is called
    with the task token — not when this Lambda finishes.

    The heartbeat=Duration.days(3) in CDK means Step Functions will fail
    the execution if nothing calls the callback within 3 days.
    """
    task_token = event["taskToken"]
    transaction = event["transaction"]

    table = dynamodb.Table(TABLE_NAME)

    # Store the pending status and task token for the reviewer queue.
    # member_id is NOT stored here — the reviewer fetches the full case via
    # transaction_id if needed (separate lookup, enforces authorization there).
    # Storing only the fields the reviewer needs to triage avoids unnecessary
    # PHI exposure at the queue layer.
    table.put_item(
        Item={
            "transaction_id": transaction["transaction_id"],
            "status": "PENDING_HUMAN_REVIEW",
            "task_token": task_token,  # reviewer needs this to resume execution
            "risk_level": transaction["risk_level"],
            "risk_reason": transaction["risk_reason"],
            "prior_auth_required": transaction.get("prior_auth_required", False),
            "service_type": transaction["service_type"],
            "payer": transaction["payer"],
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    print(
        json.dumps(
            {
                "level": "INFO",
                "message": "Transaction queued for human review — execution paused",
                "transaction_id": transaction["transaction_id"],
                "risk_level": transaction["risk_level"],
            }
        )
    )

    # Return value ignored — Step Functions is waiting for the task token callback,
    # not for this invocation to complete.
    return {"status": "QUEUED_FOR_REVIEW"}
