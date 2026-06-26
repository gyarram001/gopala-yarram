import re

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_lambda as lambda_,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
)
from constructs import Construct


class EligibilityPipelineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Model ID from CDK context — set in cdk.json, overridable per environment.
        model_id = self.node.try_get_context("bedrock_model_id") or (
            "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        )

        # DynamoDB: audit records must survive stack teardown.
        # RETAIN always — use manual table deletion for demo cleanup.
        # AWS_MANAGED encryption satisfies HIPAA at-rest requirement at zero cost.
        table = dynamodb.Table(
            self,
            "EligibilityDecisions",
            partition_key=dynamodb.Attribute(
                name="transaction_id",
                type=dynamodb.AttributeType.STRING,
            ),
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # ── Lambda functions (per-function execution roles via CDK default) ──
        # CDK auto-creates a separate execution role per function with
        # AWSLambdaBasicExecutionRole. Specific permissions are added below
        # using grant_* and add_to_role_policy — least privilege per function.

        common_env = {
            "BEDROCK_MODEL_ID": model_id,
            "DYNAMODB_TABLE_NAME": table.table_name,
        }

        def make_fn(logical_id: str, asset_dir: str) -> lambda_.Function:
            # No explicit role — CDK creates a minimal per-function execution role
            return lambda_.Function(
                self,
                logical_id,
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="handler.handler",
                code=lambda_.Code.from_asset(f"lambda/{asset_dir}"),
                timeout=Duration.seconds(30),
                environment=common_env,
            )

        validate_fn = make_fn("ValidateFields", "validate_fields")
        assess_fn = make_fn("AssessRisk", "assess_risk")
        save_fn = make_fn("SaveDecision", "save_decision")
        human_review_fn = make_fn("HumanReview", "human_review")

        # validate_fn: needs nothing beyond CloudWatch Logs (in managed policy)

        # assess_fn: Bedrock only — scoped to the specific configured model.
        # Cross-region inference profiles use a different ARN format than base models.
        match = re.match(r"^(?:us|eu|ap)\.(.+)$", model_id)
        base_model_id = match.group(1) if match else model_id
        bedrock_prefix = f"arn:aws:bedrock:{self.region}"
        assess_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:Converse"],
                resources=[
                    f"{bedrock_prefix}::foundation-model/{base_model_id}",
                    f"{bedrock_prefix}:{self.account}:inference-profile/{model_id}",
                ],
            )
        )

        # save_fn: DynamoDB write only
        table.grant_write_data(save_fn)

        # human_review_fn: DynamoDB read+write; states granted after state machine
        table.grant_read_write_data(human_review_fn)

        # ── Fail states ────────────────────────────────────────────────────
        transaction_rejected = sfn.Fail(
            self,
            "TransactionRejected",
            error="ValidationFailed",
            cause="Transaction failed field validation — see Lambda logs",
        )

        # Default branch of the Choice state — fail loudly on unknown risk levels
        # rather than silently auto-approving anything not explicitly handled.
        unknown_risk = sfn.Fail(
            self,
            "UnknownRiskLevel",
            error="UnknownRiskLevel",
            cause="Unrecognized risk level — transaction blocked pending investigation",
        )

        # ── Task states ────────────────────────────────────────────────────

        validate_task = tasks.LambdaInvoke(
            self,
            "ValidateFieldsTask",
            lambda_function=validate_fn,
            # Unwrap Lambda's Payload envelope — next state reads $.risk_level
            output_path="$.Payload",
        )
        validate_task.add_retry(
            # Retry transient infra errors only — not application errors
            errors=["Lambda.ServiceException", "Lambda.TooManyRequestsException"],
            interval=Duration.seconds(2),
            max_attempts=3,
            backoff_rate=2,  # 2s → 4s → 8s exponential backoff
        )
        validate_task.add_catch(
            transaction_rejected,
            errors=["ValidationError"],  # matches the Python class name exactly
        )

        assess_risk_task = tasks.LambdaInvoke(
            self,
            "AssessRiskTask",
            lambda_function=assess_fn,
            output_path="$.Payload",
        )

        save_decision_task = tasks.LambdaInvoke(
            self,
            "SaveDecisionTask",
            lambda_function=save_fn,
            output_path="$.Payload",
        )

        # waitForTaskToken: Step Functions generates a token, passes it to Lambda,
        # then pauses — execution stays suspended with no cost until callback arrives.
        # heartbeat: fail the execution if the reviewer takes longer than 3 days.
        human_review_task = tasks.LambdaInvoke(
            self,
            "HumanReviewTask",
            lambda_function=human_review_fn,
            integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
            payload=sfn.TaskInput.from_object(
                {
                    "transaction": sfn.JsonPath.entire_payload,
                    # $$.Task.Token — unique per execution_id + state_name + retry
                    # Reviewer calls SendTaskSuccess with this exact token
                    "taskToken": sfn.JsonPath.task_token,
                }
            ),
            heartbeat=Duration.days(3),
        )
        human_review_task.next(save_decision_task)

        # ── Choice state ───────────────────────────────────────────────────
        risk_router = sfn.Choice(self, "RouteOnRisk")
        risk_router.when(
            sfn.Condition.string_equals("$.risk_level", "HIGH"),
            human_review_task,
        )
        risk_router.when(
            sfn.Condition.or_(
                sfn.Condition.string_equals("$.risk_level", "LOW"),
                sfn.Condition.string_equals("$.risk_level", "MEDIUM"),
            ),
            save_decision_task,
        )
        risk_router.otherwise(unknown_risk)

        # ── State machine ──────────────────────────────────────────────────
        definition = validate_task.next(assess_risk_task).next(risk_router)

        # Standard: supports pause-for-days (HITL), exactly-once semantics.
        # Express would be cheaper for short runs but can't pause for HITL.
        state_machine = sfn.StateMachine(
            self,
            "EligibilityPipeline",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            state_machine_type=sfn.StateMachineType.STANDARD,
            timeout=Duration.days(7),
        )

        # Grant states:SendTaskSuccess/Failure scoped to this state machine only.
        # CDK resolves the ARN at deploy time — avoids resources=["*"].
        state_machine.grant_task_response(human_review_fn)
