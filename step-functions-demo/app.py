#!/usr/bin/env python3
import os
import aws_cdk as cdk
from eligibility_pipeline_stack import EligibilityPipelineStack

app = cdk.App()

# Fail at synth time if account is unset — self.account would resolve to the
# CDK pseudo-token '*', silently granting wildcard Bedrock permissions.
_account = os.getenv("CDK_DEFAULT_ACCOUNT")
if not _account:
    raise ValueError(
        "CDK_DEFAULT_ACCOUNT must be set (run: export CDK_DEFAULT_ACCOUNT=$(aws sts "
        "get-caller-identity --query Account --output text))"
    )

EligibilityPipelineStack(
    app,
    "EligibilityPipelineStack",
    env=cdk.Environment(
        account=_account,
        region=os.getenv("AWS_REGION", "us-east-1"),
    ),
)

app.synth()
