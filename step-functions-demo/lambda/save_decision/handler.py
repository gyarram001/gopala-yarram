import json
import os
import boto3
from datetime import datetime, timezone

REGION = os.getenv("AWS_REGION", "us-east-1")
TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "eligibility-pipeline-decisions")

dynamodb = boto3.resource("dynamodb", region_name=REGION)


def handler(event, context):
    """
    Final step: persist the decision to DynamoDB.

    Reached from two paths:
    1. LOW/MEDIUM risk → routed here directly from Choice state (no human review)
    2. HIGH risk → after HumanReview task token callback, human_decision is in state

    The human_decision field distinguishes these: None means auto-approved,
    "APPROVED" or "DENIED" means a human reviewed it.
    """
    table = dynamodb.Table(TABLE_NAME)

    human_decision = event.get("human_decision")
    # Absent human_decision = auto-approved by pipeline; "DENIED" = human denied
    final_status = "DENIED" if human_decision == "DENIED" else "APPROVED"

    # member_id is intentionally excluded — transaction_id is the audit key.
    # Callers look up member context via the source system using transaction_id.
    item = {
        "transaction_id": event["transaction_id"],
        "service_type": event["service_type"],
        "payer": event["payer"],
        "service_date": event["service_date"],
        "risk_level": event.get("risk_level"),
        "risk_reason": event.get("risk_reason", ""),
        "prior_auth_required": event.get("prior_auth_required", False),
        "human_decision": human_decision,
        "final_status": final_status,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    table.put_item(Item=item)

    print(
        json.dumps(
            {
                "level": "INFO",
                "message": "Decision saved",
                "transaction_id": item["transaction_id"],
                "final_status": final_status,
            }
        )
    )

    return {
        "status": "SAVED",
        "transaction_id": item["transaction_id"],
        "final_status": final_status,
    }
