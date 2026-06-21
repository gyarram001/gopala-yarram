import json
import os
import uuid
import boto3
from datetime import datetime, timezone

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]


def parse_bedrock_json(raw: str, transaction_id: str) -> dict:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(json.dumps({
            "level": "ERROR",
            "message": "Failed to parse Bedrock response as JSON",
            "transaction_id": transaction_id,
            "parse_error": str(e),
            "raw_response": raw,
        }))
        return {"parse_error": str(e), "raw_response": raw}


def handler(event, context):
    table = dynamodb.Table(TABLE_NAME)

    for record in event["Records"]:
        body = json.loads(record["body"])

        member_id = body.get("member_id")
        payer_name = body.get("payer_name")
        service_date = body.get("service_date")
        service_type = body.get("service_type")

        transaction_id = str(uuid.uuid4())

        prompt = (
            "Review this eligibility transaction and identify any missing "
            "fields, anomalies, or issues that need attention:\n\n"
            f"member_id: {member_id}\n"
            f"payer_name: {payer_name}\n"
            f"service_date: {service_date}\n"
            f"service_type: {service_type}"
        )

        response = bedrock.converse(
            modelId=MODEL_ID,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            inferenceConfig={
                "temperature": 0.0,
                "maxTokens": 500,
            },
        )

        stop_reason = response["stopReason"]
        raw_text = response["output"]["message"]["content"][0]["text"]

        if stop_reason == "max_tokens":
            print(json.dumps({
                "level": "WARNING",
                "message": "Bedrock response truncated — maxTokens limit reached",
                "transaction_id": transaction_id,
                "member_id": member_id,
                "stop_reason": stop_reason,
            }))

            item = {
                "transaction_id": transaction_id,
                "member_id": member_id,
                "payer_name": payer_name,
                "service_date": service_date,
                "service_type": service_type,
                "analysis_error": "TRUNCATED — Bedrock response hit maxTokens limit; output is incomplete",
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            analysis = parse_bedrock_json(raw_text, transaction_id)

            item = {
                "transaction_id": transaction_id,
                "member_id": member_id,
                "payer_name": payer_name,
                "service_date": service_date,
                "service_type": service_type,
                "analysis": json.dumps(analysis),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }

        table.put_item(Item=item)

        print(json.dumps({
            "transaction_id": transaction_id,
            "member_id": member_id,
            "stop_reason": stop_reason,
            "analysis": analysis if stop_reason != "max_tokens" else None,
        }))

    return {"statusCode": 200}
