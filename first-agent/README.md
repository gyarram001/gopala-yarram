# First Agent — Hello World & Eligibility Routing

Two files: a Python hello world and the first real Bedrock API call. The
Bedrock demo routes a healthcare 270 eligibility transaction to the correct
payer endpoint using Claude as a classifier.

## Files

| File | What it does |
|------|-------------|
| `main.py` | Python hello world — no AWS, just confirms Python environment works |
| `bedrock_hello.py` | First Bedrock Converse API call; routes an eligibility transaction to the correct payer (Aetna, UHC, or Cigna) using Claude as a zero-shot classifier |

## What `bedrock_hello.py` demonstrates

- Creating a `bedrock-runtime` boto3 client with an explicit region
- Calling `client.converse()` with `modelId`, `messages`, and `inferenceConfig`
- Using a system prompt to constrain Claude's output to a specific JSON schema
- Extracting the response text from `response["output"]["message"]["content"][0]["text"]`
- Structured output: Claude returns `{"payer": "aetna", "endpoint": "...", "confidence": 0.97}`

## Run

```bash
AWS_PROFILE=cdk-dev python first-agent/bedrock_hello.py
```

## Prerequisites

```bash
pip install boto3
aws configure --profile cdk-dev
```

The IAM user/role for `cdk-dev` needs `bedrock:InvokeModel` permission on
the Claude Sonnet model in `us-east-1`.
