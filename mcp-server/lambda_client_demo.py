"""
Lambda client demo — shows how an agentic loop uses MCP tools.

This demo imports the tool functions directly (same process).
In production, a Lambda would connect to the MCP server over HTTP.
The key point here is client-side filtering: Lambda only passes
the tools it needs to Claude, even though the server exposes more.

Run: AWS_PROFILE=cdk-dev python lambda_client_demo.py
"""

import asyncio
import json
import os

import boto3

# ---------------------------------------------------------------------------
# Import tool handlers directly from the MCP server module.
# In production with HTTP transport, these would be called via MCP client SDK.
# The tool logic is identical — only the transport changes.
# ---------------------------------------------------------------------------
from eligibility_server import check_payer_requirements, get_member_history

MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_PROFILE = os.getenv("AWS_PROFILE", "cdk-dev")

session = boto3.Session(profile_name=AWS_PROFILE, region_name=REGION)
bedrock = session.client("bedrock-runtime", region_name=REGION)

# ---------------------------------------------------------------------------
# Tool definitions for Bedrock converse() — still needed here.
# Difference from Sessions 5-6: these are GENERATED from the MCP server's
# tool schemas, not hand-written. In production with an MCP client library,
# you'd call tools/list and convert automatically.
#
# Client-side filtering in action: this Lambda only exposes the two tools
# it actually needs. If the MCP server adds a third tool later, this Lambda
# is unaffected until we explicitly add it here.
# ---------------------------------------------------------------------------
TOOLS_FOR_THIS_LAMBDA = [
    {
        "toolSpec": {
            "name": "get_member_history",
            "description": (
                "Retrieve eligibility and prior authorization history for a member. "
                "Call this before check_payer_requirements."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "member_id": {
                            "type": "string",
                            "description": "Member ID (format: MBR-YYYY-NNN)",
                        }
                    },
                    "required": ["member_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "check_payer_requirements",
            "description": (
                "Return prior auth requirements for a payer and service type. "
                "Call alongside get_member_history."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "payer_name": {"type": "string"},
                        "service_type": {"type": "string"},
                    },
                    "required": ["payer_name", "service_type"],
                }
            },
        }
    },
]


def parse_bedrock_json(raw_text: str) -> dict:
    """
    Extract and parse JSON from Claude's response. Two-layer defence (CLAUDE.md).

    Handles three formats Claude commonly returns:
      1. Pure JSON                      → parse directly
      2. ```json ... ```                → extract content between fences
      3. Prose then ```json ... ```     → find the fence block, ignore prose
    """
    import re

    # Try to extract content between ```json ... ``` fences first
    # re.DOTALL makes . match newlines so multi-line JSON is captured
    match = re.search(r"```json\s*(.*?)\s*```", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # No fences — try parsing the whole text as JSON
    try:
        return json.loads(raw_text.strip())
    except json.JSONDecodeError:
        return {"error": "parse_failed", "raw": raw_text[:200]}


async def run_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Route a tool call from Claude to the correct MCP tool handler.
    In production (HTTP transport), this would be an MCP client.call_tool() call.
    """
    if tool_name == "get_member_history":
        return await get_member_history(**tool_input)
    elif tool_name == "check_payer_requirements":
        return await check_payer_requirements(**tool_input)
    return {"error": "unknown_tool", "tool_name": tool_name}


async def run_eligibility_agent(transaction: dict) -> dict:
    """Agentic loop — same pattern as Session 5, tools now sourced from MCP server."""
    system_prompt = (
        "You are a healthcare eligibility specialist. "
        "Use the available tools to gather member history and payer requirements "
        "before making an eligibility decision. "
        "Return your final answer as JSON with keys: "
        "eligible (bool), prior_auth_required (bool), risk_level (LOW/MEDIUM/HIGH), "
        "recommended_action (string), reasoning (string)."
    )

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "text": (
                        "Evaluate this eligibility request:\n"
                        + json.dumps(transaction, indent=2)
                    )
                }
            ],
        }
    ]

    MAX_ITERATIONS = 10
    total_input_tokens = 0
    total_output_tokens = 0

    for iteration in range(MAX_ITERATIONS):
        response = bedrock.converse(
            modelId=MODEL_ID,
            system=[{"text": system_prompt}],
            messages=messages,
            inferenceConfig={"temperature": 0.0, "maxTokens": 1024},
            toolConfig={"tools": TOOLS_FOR_THIS_LAMBDA},
        )

        usage = response["usage"]
        total_input_tokens += usage["inputTokens"]
        total_output_tokens += usage["outputTokens"]
        stop_reason = response["stopReason"]

        print(
            f"  Turn {iteration + 1}: stopReason={stop_reason} | "
            f"tokens in={usage['inputTokens']} out={usage['outputTokens']}"
        )

        if stop_reason == "end_turn":
            # Extract Claude's final text response
            final_text = response["output"]["message"]["content"][0]["text"]
            result = parse_bedrock_json(final_text)
            result["_tokens"] = {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "total": total_input_tokens + total_output_tokens,
            }
            return result

        elif stop_reason == "max_tokens":
            # Response was cut off mid-generation — do not act on truncated output.
            # CLAUDE.md rule: never save to DynamoDB when stopReason is max_tokens.
            # Raise maxTokens in inferenceConfig or tighten the prompt if this fires.
            return {
                "error": "truncated_response",
                "stop_reason": "max_tokens",
                "message": (
                    "Claude response cut off. Raise maxTokens or shorten prompt."
                ),
                "_tokens": {
                    "input": total_input_tokens,
                    "output": total_output_tokens,
                    "total": total_input_tokens + total_output_tokens,
                },
            }

        elif stop_reason == "tool_use":
            # Claude wants to call tools — run them all (may be batched)
            # Bedrock Converse API wraps tool calls as {"toolUse": {...}}
            # not {"type": "toolUse", ...} — the key is "toolUse", not "type"
            tool_calls = [
                block["toolUse"]
                for block in response["output"]["message"]["content"]
                if "toolUse" in block
            ]

            async def call_one(tc):
                result = await run_tool(tc["name"], tc["input"])
                # Tool results also use "toolResult" key, not "type"
                return {
                    "toolResult": {
                        "toolUseId": tc["toolUseId"],
                        "content": [{"text": json.dumps(result)}],
                    }
                }

            tool_results = await asyncio.gather(*[call_one(tc) for tc in tool_calls])

            # Append Claude's tool_use message then our tool results
            messages.append(response["output"]["message"])
            messages.append({"role": "user", "content": list(tool_results)})

    return {"error": "max_iterations_reached", "iterations": MAX_ITERATIONS}


async def main():
    transaction = {
        "member_id": "MBR-2024-001",
        "payer_name": "Aetna",
        "service_date": "2026-06-24",
        "service_type": "knee surgery",
        "diagnosis_code": "M17.11",
    }

    print("=" * 60)
    print("Eligibility Agent — tools sourced from MCP server")
    print("=" * 60)
    print(f"Transaction: {json.dumps(transaction, indent=2)}\n")
    print("Agentic loop turns:")

    result = await run_eligibility_agent(transaction)

    print("\nFinal decision:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
