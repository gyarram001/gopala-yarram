import json
import os
import uuid
import boto3
from datetime import datetime, timezone

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]


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
        )

        analysis = response["output"]["message"]["content"][0]["text"]

        item = {
            "transaction_id": transaction_id,
            "member_id": member_id,
            "payer_name": payer_name,
            "service_date": service_date,
            "service_type": service_type,
            "analysis": analysis,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

        table.put_item(Item=item)

        print(json.dumps({
            "transaction_id": transaction_id,
            "member_id": member_id,
            "analysis": analysis,
        }))

    return {"statusCode": 200}
