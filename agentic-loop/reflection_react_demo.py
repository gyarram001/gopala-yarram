"""
reflection_react_demo.py — Reflection and ReAct patterns with Amazon Bedrock
Converse API.

Demo 1 — Baseline   : single call, no reflection, no tools
Demo 2 — Reflection : two-pass self-critique and correction
Demo 3 — ReAct      : Reason + Act agentic loop with tool use
"""

import json
import boto3

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL_ID       = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
REGION         = "us-east-1"
PROFILE        = "cdk-dev"
MAX_ITERATIONS = 10

session = boto3.Session(profile_name=PROFILE, region_name=REGION)
bedrock = session.client("bedrock-runtime")

# ---------------------------------------------------------------------------
# Transaction (shared across all demos)
# ---------------------------------------------------------------------------
TRANSACTION = {
    "member_id":      "AET-889221",
    "payer_name":     "Aetna",
    "service_date":   "2026-06-20",
    "service_type":   "knee surgery",
    "diagnosis_code": "M17.11",
    "estimated_cost": "$45,000",
}

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
BASELINE_SYSTEM = (
    "You are a healthcare eligibility specialist. "
    "Analyze the transaction and return ONLY a JSON object:\n"
    "{\n"
    '  "is_valid": true | false,\n'
    '  "risk_level": "HIGH" | "MEDIUM" | "LOW",\n'
    '  "prior_auth_required": true | false,\n'
    '  "recommended_action": "string"\n'
    "}\n"
    "Return ONLY the JSON, no additional text."
)

REACT_SYSTEM = (
    "You are a healthcare eligibility specialist. "
    "Before calling any tool, write a brief paragraph explaining your reasoning — "
    "what you need to find out and why. "
    "Use the available tools to gather payer-specific information before deciding. "
    "Once you have all the information needed, return your final decision as JSON:\n"
    "{\n"
    '  "is_valid": true | false,\n'
    '  "risk_level": "HIGH" | "MEDIUM" | "LOW",\n'
    '  "prior_auth_required": true | false,\n'
    '  "recommended_action": "string",\n'
    '  "reasoning_chain": ["step 1 ...", "step 2 ...", ...]\n'
    "}\n"
    "Return ONLY the final JSON when done, no surrounding text."
)

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def check_payer_requirements(payer_name: str, service_type: str) -> dict:
    """Return payer-specific prior-auth requirements."""
    return {
        "prior_auth_required": True,
        "requirements": ["CPT code needed", "Clinical notes required"],
        "payer_notes": (
            f"{payer_name} requires prior authorization for all surgical "
            "procedures with estimated cost above $10,000."
        ),
    }


def get_cost_threshold(payer_name: str) -> dict:
    """Return auto-approve and senior-review cost thresholds for a payer."""
    thresholds = {
        "Aetna":  {"auto_approve_threshold": 5000,  "review_threshold": 25000},
        "United": {"auto_approve_threshold": 3000,  "review_threshold": 20000},
        "Cigna":  {"auto_approve_threshold": 4000,  "review_threshold": 22000},
    }
    return thresholds.get(
        payer_name, {"auto_approve_threshold": 5000, "review_threshold": 25000}
    )


TOOL_REGISTRY = {
    "check_payer_requirements": check_payer_requirements,
    "get_cost_threshold":       get_cost_threshold,
}

TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "check_payer_requirements",
                "description": (
                    "Check prior authorization requirements for a specific payer and "
                    "service type. Returns payer-specific rules, requirements list, "
                    "and authorization notes."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "payer_name": {
                                "type": "string",
                                "description": "Insurance payer name, e.g. Aetna.",
                            },
                            "service_type": {
                                "type": "string",
                                "description": "Medical service type, e.g. knee surgery.",
                            },
                        },
                        "required": ["payer_name", "service_type"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_cost_threshold",
                "description": (
                    "Get the auto-approve and senior-review cost thresholds for a "
                    "payer. Costs above review_threshold require senior review."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "payer_name": {
                                "type": "string",
                                "description": "Insurance payer name, e.g. Aetna.",
                            },
                        },
                        "required": ["payer_name"],
                    }
                },
            }
        },
    ]
}

# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def divider(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def subdiv(label: str) -> None:
    print()
    print(f"  {'─' * 64}")
    print(f"  {label}")
    print(f"  {'─' * 64}")


def print_json_block(obj: dict, indent: int = 4) -> None:
    for line in json.dumps(obj, indent=2).splitlines():
        print(" " * indent + line)


def print_token_usage(usage: dict, label: str = "") -> None:
    prefix = f"  [{label}]  " if label else "  "
    total  = usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
    print(
        f"{prefix}Tokens → "
        f"{usage.get('inputTokens', 0)} in / "
        f"{usage.get('outputTokens', 0)} out / "
        f"{total} total"
    )


# ---------------------------------------------------------------------------
# Bedrock response helpers
# ---------------------------------------------------------------------------

def extract_text(response: dict) -> str:
    """Concatenate all text blocks from a Bedrock Converse response."""
    parts = []
    for block in response.get("output", {}).get("message", {}).get("content", []):
        if "text" in block:
            parts.append(block["text"])
    return "".join(parts).strip()


def extract_texts_and_tool_uses(
    response: dict,
) -> tuple[list[str], list[dict]]:
    """Return (non-empty text strings, tool-use dicts) from a response."""
    texts, tool_uses = [], []
    for block in response.get("output", {}).get("message", {}).get("content", []):
        if "text" in block and block["text"].strip():
            texts.append(block["text"].strip())
        if block.get("toolUse"):
            tool_uses.append(block["toolUse"])
    return texts, tool_uses


def parse_json_response(text: str) -> dict:
    """Parse JSON from a Bedrock text response, stripping markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines   = cleaned.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)


def dispatch_tool(name: str, tool_input: dict) -> tuple[dict, bool]:
    """Call the matching Python function; return (result, is_error)."""
    func = TOOL_REGISTRY.get(name)
    if func is None:
        return {"error": f"Unknown tool: {name}"}, True
    try:
        return func(**tool_input), False
    except Exception as exc:
        return {"error": str(exc)}, True


# ===========================================================================
# DEMO 1 — Baseline (no reflection, no tools)
# ===========================================================================

def demo_baseline() -> None:
    divider("DEMO 1 — Baseline  (single call, no reflection)")
    print("  Standard system prompt. One Bedrock call. No tools, no self-critique.\n")
    print("  Transaction:")
    print_json_block(TRANSACTION)

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": BASELINE_SYSTEM}],
        messages=[{
            "role":    "user",
            "content": [{"text": "Analyze this transaction:\n\n" + json.dumps(TRANSACTION, indent=2)}],
        }],
    )

    text  = extract_text(response)
    usage = response.get("usage", {})

    subdiv("Response")
    try:
        analysis = parse_json_response(text)
        print_json_block(analysis)
    except json.JSONDecodeError:
        print(f"    {text}")

    print()
    print_token_usage(usage, "Demo 1")

    subdiv("What reflection will improve")
    print("  - risk_level is generic; payer-specific thresholds not checked")
    print("  - prior_auth_required not verified against Aetna rules")
    print("  - $45,000 not compared against Aetna's $25,000 review threshold")
    print("  - recommended_action may lack payer-specific next steps")


# ===========================================================================
# DEMO 2 — Reflection (two-pass self-critique)
# ===========================================================================

def demo_reflection() -> None:
    divider("DEMO 2 — Reflection  (two-pass self-critique)")
    print("  Pass 1: initial analysis.")
    print("  Pass 2: Claude reviews its own output and returns a corrected JSON.\n")

    user_content = "Analyze this transaction:\n\n" + json.dumps(TRANSACTION, indent=2)

    # ── Pass 1 ───────────────────────────────────────────────────────────────
    subdiv("Pass 1 — Initial analysis")

    resp1 = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": BASELINE_SYSTEM}],
        messages=[{"role": "user", "content": [{"text": user_content}]}],
    )

    pass1_text = extract_text(resp1)
    usage1     = resp1.get("usage", {})

    try:
        pass1_json = parse_json_response(pass1_text)
        print_json_block(pass1_json)
    except json.JSONDecodeError:
        pass1_json = {}
        print(f"    {pass1_text}")

    print()
    print_token_usage(usage1, "Pass 1")

    # ── Pass 2 — Self-critique ────────────────────────────────────────────────
    subdiv("Pass 2 — Self-critique and correction")

    reflection_prompt = (
        f"Review your previous analysis:\n\n{pass1_text}\n\n"
        "Check for:\n"
        "1. Did you consider ALL risk factors "
        "(service type, diagnosis, cost vs. payer thresholds)?\n"
        "2. Is the prior_auth_required guidance Aetna-specific or generic?\n"
        "3. Are there any missing fields or assumptions made?\n"
        "4. Would you change anything given that $45,000 is significantly "
        "above a typical $25,000 senior-review threshold?\n\n"
        "Return a corrected JSON with a changes_made field listing what you "
        "updated and why. If nothing changed, set changes_made to [].\n\n"
        "{\n"
        '  "is_valid": true | false,\n'
        '  "risk_level": "HIGH" | "MEDIUM" | "LOW",\n'
        '  "prior_auth_required": true | false,\n'
        '  "recommended_action": "string",\n'
        '  "changes_made": ["change and reason", ...]\n'
        "}\n"
        "Return ONLY the JSON."
    )

    resp2 = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": BASELINE_SYSTEM}],
        messages=[
            {"role": "user",      "content": [{"text": user_content}]},
            {"role": "assistant", "content": [{"text": pass1_text}]},
            {"role": "user",      "content": [{"text": reflection_prompt}]},
        ],
    )

    pass2_text = extract_text(resp2)
    usage2     = resp2.get("usage", {})

    try:
        pass2_json = parse_json_response(pass2_text)
        print_json_block(pass2_json)
    except json.JSONDecodeError:
        pass2_json = {}
        print(f"    {pass2_text}")

    print()
    print_token_usage(usage2, "Pass 2")

    # ── Field-level diff ──────────────────────────────────────────────────────
    subdiv("Field-level diff  (Pass 1 → Pass 2)")
    fields = ["is_valid", "risk_level", "prior_auth_required", "recommended_action"]
    changed = False
    for field in fields:
        v1 = pass1_json.get(field, "<missing>")
        v2 = pass2_json.get(field, "<missing>")
        marker = "  CHANGED →" if v1 != v2 else "  unchanged"
        print(f"  {marker}  {field}: {v1!r}  →  {v2!r}")
        if v1 != v2:
            changed = True

    subdiv("What reflection changed")
    changes = pass2_json.get("changes_made", [])
    if changes:
        for i, change in enumerate(changes, 1):
            print(f"  {i}. {change}")
    elif not changed:
        print("  Claude reported no changes.")
    else:
        print("  Fields changed but no changes_made list returned.")

    total_in  = usage1.get("inputTokens",  0) + usage2.get("inputTokens",  0)
    total_out = usage1.get("outputTokens", 0) + usage2.get("outputTokens", 0)
    print()
    print_token_usage({"inputTokens": total_in, "outputTokens": total_out}, "Demo 2 total")


# ===========================================================================
# DEMO 3 — ReAct (Reason + Act agentic loop)
# ===========================================================================

def demo_react() -> None:
    divider("DEMO 3 — ReAct  (Reason + Act agentic loop with tool use)")
    print("  Claude reasons before each tool call, uses tools to gather")
    print("  payer-specific data, then produces a grounded final decision.\n")
    print("  Tools available:")
    print("    check_payer_requirements(payer_name, service_type)")
    print("    get_cost_threshold(payer_name)\n")
    print("  Transaction:")
    print_json_block(TRANSACTION)

    messages = [{
        "role":    "user",
        "content": [{"text": "Analyze this transaction:\n\n" + json.dumps(TRANSACTION, indent=2)}],
    }]

    total_input_tokens  = 0
    total_output_tokens = 0
    step = 0

    while True:
        if step >= MAX_ITERATIONS:
            print(f"\n  WARNING: reached MAX_ITERATIONS ({MAX_ITERATIONS}). Stopping.")
            break

        step += 1

        response = bedrock.converse(
            modelId=MODEL_ID,
            system=[{"text": REACT_SYSTEM}],
            messages=messages,
            toolConfig=TOOL_CONFIG,
        )

        usage               = response.get("usage", {})
        total_input_tokens  += usage.get("inputTokens",  0)
        total_output_tokens += usage.get("outputTokens", 0)

        stop_reason       = response.get("stopReason", "")
        assistant_message = response["output"]["message"]
        texts, tool_uses  = extract_texts_and_tool_uses(response)

        # Append the full assistant turn to history
        messages.append(assistant_message)

        # ── THOUGHT — Claude's reasoning before this action ──────────────────
        if texts:
            subdiv(f"Step {step}  THOUGHT")
            for paragraph in texts:
                for line in paragraph.splitlines():
                    print(f"    {line}")

        # ── TOOL CALLS ────────────────────────────────────────────────────────
        if stop_reason == "tool_use":
            tool_result_contents = []

            for tu in tool_uses:
                tool_use_id = tu["toolUseId"]
                tool_name   = tu["name"]
                tool_input  = tu.get("input", {})

                subdiv(f"Step {step}  ACTION  →  {tool_name}")
                print(f"    Input: {json.dumps(tool_input)}")

                result, is_error = dispatch_tool(tool_name, tool_input)

                subdiv(f"Step {step}  OBSERVATION  ←  {tool_name}")
                print_json_block(result)
                if is_error:
                    print("    *** tool returned an error ***")

                tool_result_contents.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content":   [{"json": result}],
                        **({"status": "error"} if is_error else {}),
                    }
                })

            messages.append({"role": "user", "content": tool_result_contents})

        # ── FINAL DECISION ────────────────────────────────────────────────────
        elif stop_reason == "end_turn":
            subdiv(f"Step {step}  FINAL DECISION")
            final_text = "\n".join(texts)
            try:
                final_json = parse_json_response(final_text)
                print_json_block(final_json)
                if final_json.get("reasoning_chain"):
                    print()
                    print("    Reasoning chain:")
                    for i, step_txt in enumerate(final_json["reasoning_chain"], 1):
                        print(f"      {i}. {step_txt}")
            except json.JSONDecodeError:
                for line in final_text.splitlines():
                    print(f"    {line}")
            break

        else:
            print(f"\n  Unexpected stop_reason: '{stop_reason}'. Exiting loop.")
            break

    print()
    print(f"  ReAct steps completed : {step}")
    print_token_usage(
        {"inputTokens": total_input_tokens, "outputTokens": total_output_tokens},
        "Demo 3 total",
    )


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  REFLECTION + ReAct DEMO")
    print("  Bedrock Converse API  |  us-east-1  |  cdk-dev")
    print("=" * 70)

    demo_baseline()
    demo_reflection()
    demo_react()

    print()
    print("=" * 70)
    print("  All demos complete.")
    print("  Demo 1  Baseline   : single call, no payer-specific verification")
    print("  Demo 2  Reflection : self-critique corrected risk / prior-auth")
    print("  Demo 3  ReAct      : tool-grounded reasoning with explicit chain")
    print("=" * 70)
    print()
