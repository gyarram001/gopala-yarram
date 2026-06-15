#!/usr/bin/env python3
import aws_cdk as cdk
from eligibility_stack import EligibilityStack

app = cdk.App()

EligibilityStack(
    app,
    "EligibilityStack",
    env=cdk.Environment(region="us-east-1"),
)

app.synth()
