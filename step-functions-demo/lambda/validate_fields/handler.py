import json

REQUIRED_FIELDS = [
    "transaction_id",
    "member_id",
    "service_type",
    "payer",
    "service_date",
]


class ValidationError(Exception):
    """
    Raised when required fields are missing.

    Step Functions catches Lambda exceptions by class name.
    This class name must match the Catch block's ErrorEquals: ["ValidationError"]
    in the state machine definition exactly.

    If you raise Exception("...") instead, Step Functions sees "Exception" —
    the wrong catch block fires (or nothing catches it at all).
    """

    pass


def handler(event, context):
    """
    Step 1 in the pipeline: validate all required fields are present and non-empty.

    Input:  execution state JSON (the transaction dict)
    Output: same dict + validation_status — flows into AssessRisk as-is

    On failure: raises ValidationError → Step Functions Catch block routes
                to TransactionRejected (Fail state), pipeline ends here.
    """
    missing = [f for f in REQUIRED_FIELDS if not event.get(f)]

    if missing:
        # Class name "ValidationError" is what Step Functions matches in ErrorEquals
        raise ValidationError(f"Missing required fields: {missing}")

    print(
        json.dumps(
            {
                "level": "INFO",
                "message": "Validation passed",
                "transaction_id": event.get("transaction_id"),
            }
        )
    )

    # Output becomes the input to the next state.
    # output_path="$.Payload" in the CDK task definition unwraps Lambda's response
    # envelope so the next state sees this dict directly, not {"Payload": {...}}.
    return {**event, "validation_status": "PASSED"}
