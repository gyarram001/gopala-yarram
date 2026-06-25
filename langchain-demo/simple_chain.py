"""
LangChain Simple Chain Demo — Session 10

Reproduces the Session 3 eligibility validation using LangChain components.
Side-by-side with raw Bedrock so you can see exactly what LangChain abstracts.

Run: AWS_PROFILE=cdk-dev python langchain-demo/simple_chain.py
"""

import json
import os

import boto3
from langchain_aws import ChatBedrock
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

# ---------------------------------------------------------------------------
# Model configuration
# ChatBedrock is LangChain's wrapper around boto3's bedrock-runtime client.
# It speaks the LangChain interface (invoke, stream, batch) instead of
# the raw boto3 converse() interface.
#
# model_kwargs replaces inferenceConfig — same values, different key name.
# temperature=0.0 set here once, applies to every chain.invoke() call.
# CLAUDE.md rule: temperature always explicit, never rely on defaults.
# ---------------------------------------------------------------------------
AWS_PROFILE = os.getenv("AWS_PROFILE", "cdk-dev")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
bedrock_client = session.client("bedrock-runtime", region_name=AWS_REGION)

llm = ChatBedrock(
    client=bedrock_client,
    model_id=MODEL_ID,
    model_kwargs={"temperature": 0.0},  # replaces inferenceConfig
)

# ---------------------------------------------------------------------------
# Prompt Template
# ChatPromptTemplate.from_messages() defines the message structure once.
# {transaction} is a placeholder filled at call time via chain.invoke().
#
# Compare to raw Bedrock where you built this dict manually every call:
#   messages = [{"role": "user", "content": [{"text": f"Evaluate: {transaction}"}]}]
# ---------------------------------------------------------------------------
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a senior healthcare eligibility specialist. "
            "Analyze the transaction and return ONLY a JSON object "
            "with these exact keys: "
            "is_valid (boolean), missing_fields (list of strings), "
            "issues (list of strings), recommended_action (string). "
            "No markdown fences. No prose. JSON only.",
        ),
        ("user", "Evaluate this eligibility transaction:\n{transaction}"),
    ]
)

# ---------------------------------------------------------------------------
# Output Parser
# JsonOutputParser replaces parse_bedrock_json() from your lambda_client_demo.
# It strips markdown fences and parses JSON automatically.
# If parsing fails it raises OutputParserException instead of returning
# {"error": "parse_failed"} — you'd catch that in production.
# ---------------------------------------------------------------------------
output_parser = JsonOutputParser()

# ---------------------------------------------------------------------------
# Chain — the | operator connects components left to right:
#   prompt.invoke(inputs) → formatted messages
#   llm.invoke(messages)  → AIMessage with raw text content
#   output_parser.invoke(AIMessage) → Python dict
#
# chain.invoke(inputs) runs all three in sequence automatically.
# ---------------------------------------------------------------------------
chain = prompt | llm | output_parser


def run_langchain_chain(transaction: dict) -> dict:
    """Run the eligibility transaction through the LangChain chain."""
    return chain.invoke({"transaction": json.dumps(transaction, indent=2)})


# ---------------------------------------------------------------------------
# What does LangChain actually return before the output parser?
# This shows the raw AIMessage object so you understand what's underneath.
# ---------------------------------------------------------------------------
def inspect_raw_llm_response(transaction: dict):
    """Show the raw AIMessage LangChain returns before output parsing."""
    # Chain without the output parser — stops at the llm stage
    raw_chain = prompt | llm
    response = raw_chain.invoke({"transaction": json.dumps(transaction, indent=2)})

    print("--- Raw AIMessage object ---")
    print(f"Type:              {type(response)}")
    print(f"Content:           {response.content[:200]}")

    # response_metadata is where LangChain puts token usage and stop reason —
    # the same information boto3 puts in response['usage'] and response['stopReason']
    print(f"Stop reason:       {response.response_metadata.get('stopReason')}")
    usage = response.response_metadata.get("usage", {})
    print(f"Input tokens:      {usage.get('inputTokens')}")
    print(f"Output tokens:     {usage.get('outputTokens')}")
    print()


if __name__ == "__main__":
    transaction = {
        "member_id": "MBR-2024-001",
        "payer_name": "Aetna",
        "service_date": "2026-06-24",
        "service_type": "knee surgery",
        "diagnosis_code": "M17.11",
    }

    print("=" * 60)
    print("LangChain Simple Chain — Eligibility Validation")
    print("=" * 60)
    print(f"Input: {json.dumps(transaction, indent=2)}\n")

    # Step 1 — show what the raw LangChain LLM response looks like
    # before the output parser touches it
    print("Step 1: Raw AIMessage (before output parser)")
    inspect_raw_llm_response(transaction)

    # Step 2 — run the full chain with output parser
    print("Step 2: Full chain result (after output parser)")
    result = run_langchain_chain(transaction)
    print(json.dumps(result, indent=2))

    # Step 3 — what you would have written with raw Bedrock
    print("\n--- Raw Bedrock equivalent (for comparison) ---")
    print(
        """
bedrock.converse(
    modelId=MODEL_ID,
    system=[{"text": "You are a healthcare eligibility specialist..."}],
    messages=[{"role": "user", "content": [{"text": f"Evaluate: {transaction}"}]}],
    inferenceConfig={"temperature": 0.0}
)
→ response["output"]["message"]["content"][0]["text"]
→ parse_bedrock_json(raw_text)
    """
    )
    print("LangChain collapses all of that into: chain.invoke({'transaction': ...})")
