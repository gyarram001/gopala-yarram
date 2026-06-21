from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_sqs as sqs,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_lambda_event_sources as event_sources,
    aws_iam as iam,
)
from constructs import Construct


class EligibilityStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # SQS Queue
        # Visibility timeout must be >= Lambda timeout (30s)
        queue = sqs.Queue(
            self,
            "EligibilityQueue",
            queue_name="eligibility-queue",
            visibility_timeout=Duration.seconds(30),
        )

        # DynamoDB Table
        table = dynamodb.Table(
            self,
            "EligibilityDecisions",
            table_name="eligibility-decisions",
            partition_key=dynamodb.Attribute(
                name="transaction_id",
                type=dynamodb.AttributeType.STRING,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # IAM Role for Lambda
        lambda_role = iam.Role(
            self,
            "EligibilityLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:Converse"],
                resources=["*"],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:PutItem"],
                resources=[table.table_arn],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes",
                ],
                resources=[queue.queue_arn],
            )
        )

        # Lambda Function
        fn = lambda_.Function(
            self,
            "EligibilityHandler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset("lambda"),
            role=lambda_role,
            timeout=Duration.seconds(30),
            environment={
                "BEDROCK_MODEL_ID": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "DYNAMODB_TABLE_NAME": table.table_name,
            },
        )

        # SQS event source — process one message at a time
        fn.add_event_source(
            event_sources.SqsEventSource(queue, batch_size=1)
        )
