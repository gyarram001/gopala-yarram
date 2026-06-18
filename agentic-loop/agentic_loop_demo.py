"""
Agentic Loop Demo using Amazon Bedrock Converse API with Claude Sonnet.

Scenario: Claude acts as a healthcare eligibility agent that analyzes
a transaction by calling tools before making a final decision.

Production-safe features:
  - Tool errors are caught and reported back to Claude (no crash)
  - MAX_ITERATIONS guard prevents infinite loops
  - Token usage is tracked and printed across all iterations
"""

import json
import boto3

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
REGION = "us-east-1"
MAX_ITERATIONS = 10

SYSTEM_PROMPT = (
    "You are a healthcare eligibility specialist. "
    "Use the available tools to gather all information needed "
    "before making an eligibility decision. Always check payer "
    "requirements and member history before giving a final answer. "
    "If a tool returns an error, note the limitation and proceed "
    "with the information you do have."
)

TRANSACTION = {
    "member_id": "AET-889221",
    "payer_name": "Aetna",
    "service_date": "2026-06-20",
    "service_type": "knee surgery",
    "diagnosis_code": "M17.11",
}

# ---------------------------------------------------------------------------
# Mock tool implementations (no real API calls)
# ---------------------------------------------------------------------------

def check_payer_requirements(payer_name: str, service_type: str) -> dict:
    """Return payer-specific prior-auth requirements."""
    return {
        "prior_auth_required": True,
        "requirements": ["CPT code needed", "Clinical notes required"],
    }


def lookup_member_history(member_id: str) -> dict:
    """Return the member's claim and prior-auth history."""
    return {
        "previous_claims": 2,
        "last_service_date": "2025-12-01",
        "prior_auths_approved": 1,
    }


def get_diagnosis_info(diagnosis_code: str) -> dict:
    """Return clinical details for a diagnosis code.

    Simulates a downstream service outage for code M17.11.
    """
    if diagnosis_code == "M17.11":
        raise RuntimeError(
            "Diagnosis lookup service unavailable: connection timeout for code M17.11"
        )
    return {
        "description": "Unknown diagnosis",
        "commonly_requires_auth": False,
    }


# Map tool names to their Python implementations
TOOL_REGISTRY = {
    "check_payer_requirements": check_payer_requirements,
    "lookup_member_history": lookup_member_history,
    "get_diagnosis_info": get_diagnosis_info,
}

# ---------------------------------------------------------------------------
# Tool schema definitions for Bedrock Converse API
# ---------------------------------------------------------------------------

TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "check_payer_requirements",
                "description": (
                    "Check prior authorization requirements for a specific "
                    "payer and service type."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "payer_name": {
                                "type": "string",
                                "description": "Name of the insurance payer (e.g. Aetna).",
                            },
                            "service_type": {
                                "type": "string",
                                "description": "Type of medical service (e.g. knee surgery).",
                            },
                        },
                        "required": ["payer_name", "service_type"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "lookup_member_history",
                "description": (
                    "Retrieve a member's claim history and prior authorization records."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "member_id": {
                                "type": "string",
                                "description": "Unique member identifier.",
                            }
                        },
                        "required": ["member_id"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_diagnosis_info",
                "description": (
                    "Look up clinical details and authorization likelihood for an "
                    "ICD-10 diagnosis code."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "diagnosis_code": {
                                "type": "string",
                                "description": "ICD-10 diagnosis code (e.g. M17.11).",
                            }
                        },
                        "required": ["diagnosis_code"],
                    }
                },
            }
        },
    ]
}

# ---------------------------------------------------------------------------
# Helper: dispatch a tool call — catches exceptions and returns error payload
# ---------------------------------------------------------------------------

def dispatch_tool(tool_name: str, tool_input: dict) -> tuple[dict, bool]:
    """Call the matching Python function.

    Returns (result_dict, is_error).
    On exception, result_dict contains an 'error' key and is_error is True.
    """
    func = TOOL_REGISTRY.get(tool_name)
    if func is None:
        return {"error": f"Unknown tool: {tool_name}"}, True
    try:
        return func(**tool_input), False
    except Exception as exc:
        return {"error": str(exc)}, True


# ---------------------------------------------------------------------------
# Helper: extract all tool-use blocks from a Converse response
# ---------------------------------------------------------------------------

def extract_tool_uses(response: dict) -> list[dict]:
    """Return a list of tool-use content blocks from the model response."""
    tool_uses = []
    for block in response.get("output", {}).get("message", {}).get("content", []):
        if block.get("toolUse"):
            tool_uses.append(block["toolUse"])
    return tool_uses


# ---------------------------------------------------------------------------
# Helper: pretty-print the assistant's text content (if any)
# ---------------------------------------------------------------------------

def print_text_content(response: dict) -> None:
    for block in response.get("output", {}).get("message", {}).get("content", []):
        if "text" in block:
            print(block["text"])


# ---------------------------------------------------------------------------
# Main agentic loop
# ---------------------------------------------------------------------------

def run_agentic_loop() -> None:
    client = boto3.client("bedrock-runtime", region_name=REGION)

    initial_user_message = (
        "Please analyze this transaction and determine eligibility:\n\n"
        + json.dumps(TRANSACTION, indent=2)
    )

    messages = [{"role": "user", "content": [{"text": initial_user_message}]}]

    # Token counters (accumulated across all iterations)
    total_input_tokens = 0
    total_output_tokens = 0

    print("=" * 70)
    print("AGENTIC LOOP DEMO — Healthcare Eligibility Agent")
    print(f"(MAX_ITERATIONS={MAX_ITERATIONS}, tool fault injection: get_diagnosis_info)")
    print("=" * 70)
    print("\nTransaction submitted:")
    print(json.dumps(TRANSACTION, indent=2))
    print()

    iteration = 0

    while True:
        # ----------------------------------------------------------------
        # Safety guard: prevent infinite loops
        # ----------------------------------------------------------------
        if iteration >= MAX_ITERATIONS:
            print(f"WARNING: reached MAX_ITERATIONS ({MAX_ITERATIONS}). "
                  "Terminating loop to prevent runaway execution.")
            break

        iteration += 1
        print(f"{'─' * 70}")
        print(f"ITERATION {iteration} / {MAX_ITERATIONS}")
        print(f"{'─' * 70}")

        response = client.converse(
            modelId=MODEL_ID,
            system=[{"text": SYSTEM_PROMPT}],
            messages=messages,
            toolConfig=TOOL_CONFIG,
        )

        # ----------------------------------------------------------------
        # Accumulate token usage
        # ----------------------------------------------------------------
        usage = response.get("usage", {})
        iter_input  = usage.get("inputTokens", 0)
        iter_output = usage.get("outputTokens", 0)
        total_input_tokens  += iter_input
        total_output_tokens += iter_output
        print(f"  Tokens this call  : {iter_input} in / {iter_output} out")
        print(f"  Tokens cumulative : {total_input_tokens} in / {total_output_tokens} out")
        print()

        stop_reason = response.get("stopReason", "")
        print(f"  Stop reason: {stop_reason}\n")

        # Append assistant reply to conversation history
        assistant_message = response["output"]["message"]
        messages.append(assistant_message)

        # ----------------------------------------------------------------
        # Case 1: Claude wants to call one or more tools
        # ----------------------------------------------------------------
        if stop_reason == "tool_use":
            tool_uses = extract_tool_uses(response)
            tool_result_contents = []

            for tool_use in tool_uses:
                tool_use_id = tool_use["toolUseId"]
                tool_name   = tool_use["name"]
                tool_input  = tool_use.get("input", {})

                print(f"  Tool called : {tool_name}")
                print(f"  Tool input  : {json.dumps(tool_input, indent=4)}")

                result_obj, is_error = dispatch_tool(tool_name, tool_input)

                if is_error:
                    print(f"  *** TOOL ERROR (caught, forwarding to Claude) ***")
                    print(f"  Error detail: {result_obj['error']}")
                else:
                    print(f"  Tool result : {json.dumps(result_obj, indent=4)}")
                print()

                # Build the toolResult block.
                # The Converse API accepts an optional "status" field:
                #   "error"   → Claude receives the result tagged as a failure
                #   "success" → normal result (default)
                tool_result_block = {
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": result_obj}],
                    }
                }
                if is_error:
                    tool_result_block["toolResult"]["status"] = "error"

                tool_result_contents.append(tool_result_block)

            messages.append({"role": "user", "content": tool_result_contents})

        # ----------------------------------------------------------------
        # Case 2: Claude has finished — print final decision
        # ----------------------------------------------------------------
        elif stop_reason == "end_turn":
            print("FINAL ELIGIBILITY DECISION")
            print("─" * 70)
            print_text_content(response)
            print()
            break

        # ----------------------------------------------------------------
        # Unexpected stop reason
        # ----------------------------------------------------------------
        else:
            print(f"  Unexpected stop reason '{stop_reason}'. Exiting loop.")
            break

    # ----------------------------------------------------------------
    # Token usage summary
    # ----------------------------------------------------------------
    print("=" * 70)
    print("TOKEN USAGE SUMMARY")
    print("─" * 70)
    print(f"  Iterations completed : {iteration}")
    print(f"  Total input tokens   : {total_input_tokens}")
    print(f"  Total output tokens  : {total_output_tokens}")
    print(f"  Total tokens         : {total_input_tokens + total_output_tokens}")
    print("=" * 70)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_agentic_loop()
