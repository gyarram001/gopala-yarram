"""
parallel_tools_demo.py — Sequential vs parallel tool execution with
Amazon Bedrock Converse API.

Demo 1 — Sequential : tool batch dispatched with a for-loop; time ≈ sum of latencies
Demo 2 — Parallel   : tool batch dispatched with ThreadPoolExecutor; time ≈ max latency

Both demos run the identical agentic loop and must produce the same final decision.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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
# Transaction
# ---------------------------------------------------------------------------
TRANSACTION = {
    "member_id":      "AET-889221",
    "payer_name":     "Aetna",
    "service_type":   "knee surgery",
    "diagnosis_code": "M17.11",
}

SYSTEM_PROMPT = (
    "You are a healthcare eligibility specialist. "
    "Use ALL available tools to gather payer requirements, member history, "
    "and diagnosis details before making your decision. "
    "Return your final answer as JSON:\n"
    "{\n"
    '  "is_eligible": true | false,\n'
    '  "risk_level": "HIGH" | "MEDIUM" | "LOW",\n'
    '  "prior_auth_required": true | false,\n'
    '  "recommended_action": "string"\n'
    "}\n"
    "Return ONLY the JSON when done."
)

# ---------------------------------------------------------------------------
# Tool implementations  (realistic latency via time.sleep)
# ---------------------------------------------------------------------------

def check_payer_requirements(payer_name: str, service_type: str) -> dict:
    """Simulate a slow payer-rules API call (1.2 s)."""
    time.sleep(1.2)
    return {
        "prior_auth_required": True,
        "requirements": ["CPT code needed", "Clinical notes required"],
        "payer_notes": (
            f"{payer_name} requires prior authorization for all "
            "surgical procedures with estimated cost above $10,000."
        ),
    }


def lookup_member_history(member_id: str) -> dict:
    """Simulate a member-history DB lookup (0.8 s)."""
    time.sleep(0.8)
    return {
        "previous_claims": 2,
        "last_service_date": "2025-12-01",
        "prior_auths_approved": 1,
        "member_status": "active",
    }


def get_diagnosis_info(diagnosis_code: str) -> dict:
    """Simulate a clinical-codes lookup (0.6 s)."""
    time.sleep(0.6)
    return {
        "description": "Unilateral primary osteoarthritis, right knee",
        "commonly_requires_auth": True,
        "typical_treatment": "Total or partial knee replacement",
        "icd10_category": "Arthropathies",
    }


TOOL_REGISTRY = {
    "check_payer_requirements": check_payer_requirements,
    "lookup_member_history":    lookup_member_history,
    "get_diagnosis_info":       get_diagnosis_info,
}

EXPECTED_LATENCIES = {
    "check_payer_requirements": 1.2,
    "lookup_member_history":    0.8,
    "get_diagnosis_info":       0.6,
}

TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "check_payer_requirements",
                "description": (
                    "Check prior authorization requirements for a specific payer "
                    "and service type. Returns payer-specific rules and documentation "
                    "requirements."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "payer_name":   {"type": "string", "description": "Insurance payer name, e.g. Aetna."},
                            "service_type": {"type": "string", "description": "Medical service, e.g. knee surgery."},
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
                            "member_id": {"type": "string", "description": "Unique member identifier."},
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
                            "diagnosis_code": {"type": "string", "description": "ICD-10 code, e.g. M17.11."},
                        },
                        "required": ["diagnosis_code"],
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


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def extract_text(response: dict) -> str:
    parts = []
    for block in response.get("output", {}).get("message", {}).get("content", []):
        if "text" in block:
            parts.append(block["text"])
    return "".join(parts).strip()


def extract_tool_uses(response: dict) -> list[dict]:
    return [
        block["toolUse"]
        for block in response.get("output", {}).get("message", {}).get("content", [])
        if block.get("toolUse")
    ]


def dispatch_tool(name: str, tool_input: dict) -> tuple[dict, bool]:
    func = TOOL_REGISTRY.get(name)
    if func is None:
        return {"error": f"Unknown tool: {name}"}, True
    try:
        return func(**tool_input), False
    except Exception as exc:
        return {"error": str(exc)}, True


def build_tool_result(tool_use_id: str, result: dict, is_error: bool) -> dict:
    block = {"toolResult": {"toolUseId": tool_use_id, "content": [{"json": result}]}}
    if is_error:
        block["toolResult"]["status"] = "error"
    return block


def parse_json_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Tool executors
# ---------------------------------------------------------------------------

def sequential_executor(tool_uses: list[dict]) -> tuple[list[dict], float]:
    """Run tools one at a time; return (results, wall_clock_seconds)."""
    wall_start = time.perf_counter()
    results    = []

    for i, tu in enumerate(tool_uses, 1):
        t0 = time.perf_counter()
        result, is_error = dispatch_tool(tu["name"], tu.get("input", {}))
        elapsed = time.perf_counter() - t0
        expected = EXPECTED_LATENCIES.get(tu["name"], 0)
        print(f"    [{i}/{len(tool_uses)}] {tu['name']:<35s} {elapsed:.2f}s  "
              f"(expected ~{expected:.1f}s)")
        results.append(build_tool_result(tu["toolUseId"], result, is_error))

    wall_elapsed = time.perf_counter() - wall_start
    return results, wall_elapsed


def parallel_executor(tool_uses: list[dict]) -> tuple[list[dict], float]:
    """Run tools concurrently; return (results, wall_clock_seconds)."""
    names = "  +  ".join(tu["name"] for tu in tool_uses)
    print(f"    Running concurrently: {names}")

    # Pre-allocate results list to preserve ordering by tool_uses index
    results  = [None] * len(tool_uses)
    id_to_idx = {tu["toolUseId"]: i for i, tu in enumerate(tool_uses)}

    wall_start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=len(tool_uses)) as executor:
        future_map = {
            executor.submit(dispatch_tool, tu["name"], tu.get("input", {})): tu
            for tu in tool_uses
        }
        for future in as_completed(future_map):
            tu               = future_map[future]
            result, is_error = future.result()
            idx              = id_to_idx[tu["toolUseId"]]
            results[idx]     = build_tool_result(tu["toolUseId"], result, is_error)

    wall_elapsed = time.perf_counter() - wall_start
    print(f"    All {len(tool_uses)} tools completed in {wall_elapsed:.2f}s  "
          f"(expected ~{max(EXPECTED_LATENCIES[tu['name']] for tu in tool_uses):.1f}s)")
    return results, wall_elapsed


# ---------------------------------------------------------------------------
# Generic agentic loop
# ---------------------------------------------------------------------------

def run_agentic_loop(
    demo_label: str,
    executor,
) -> tuple[str, float, int, int]:
    """
    Run the full Bedrock Converse agentic loop.

    Parameters
    ----------
    demo_label : str
        Human-readable label for progress printing.
    executor   : callable(tool_uses) -> (results, elapsed_seconds)
        Tool execution strategy (sequential or parallel).

    Returns
    -------
    (final_text, total_tool_time_s, total_input_tokens, total_output_tokens)
    """
    messages = [{
        "role":    "user",
        "content": [{"text": "Analyze this transaction:\n\n" + json.dumps(TRANSACTION, indent=2)}],
    }]

    total_tool_time   = 0.0
    total_input_tok   = 0
    total_output_tok  = 0
    iteration         = 0
    batch_num         = 0

    while True:
        if iteration >= MAX_ITERATIONS:
            print(f"  WARNING: MAX_ITERATIONS ({MAX_ITERATIONS}) reached. Stopping.")
            break

        iteration += 1

        response = bedrock.converse(
            modelId=MODEL_ID,
            system=[{"text": SYSTEM_PROMPT}],
            messages=messages,
            toolConfig=TOOL_CONFIG,
            inferenceConfig={"maxTokens": 1024, "temperature": 0},
        )

        usage             = response.get("usage", {})
        total_input_tok  += usage.get("inputTokens",  0)
        total_output_tok += usage.get("outputTokens", 0)
        stop_reason       = response.get("stopReason", "")
        assistant_message = response["output"]["message"]
        messages.append(assistant_message)

        # ── Claude wants to call tools ────────────────────────────────────────
        if stop_reason == "tool_use":
            tool_uses = extract_tool_uses(response)
            batch_num += 1
            print(f"\n  Batch {batch_num}: Claude called {len(tool_uses)} tool(s)")

            tool_results, elapsed = executor(tool_uses)
            total_tool_time += elapsed
            print(f"  Batch {batch_num} wall-clock time: {elapsed:.2f}s")

            messages.append({"role": "user", "content": tool_results})

        # ── Claude finished ───────────────────────────────────────────────────
        elif stop_reason == "end_turn":
            final_text = extract_text(response)
            return final_text, total_tool_time, total_input_tok, total_output_tok

        else:
            print(f"  Unexpected stop_reason '{stop_reason}'. Exiting.")
            break

    return "", total_tool_time, total_input_tok, total_output_tok


# ---------------------------------------------------------------------------
# Demo 1 — Sequential
# ---------------------------------------------------------------------------

def demo_sequential() -> tuple[str, float, int, int]:
    divider("DEMO 1 — Sequential tool execution  (for-loop, one at a time)")
    print("  Expected wall-clock ≈ 1.2 + 0.8 + 0.6 = 2.6 s per batch\n")
    print("  Transaction:")
    print_json_block(TRANSACTION)

    final_text, tool_time, in_tok, out_tok = run_agentic_loop(
        "Sequential", sequential_executor
    )

    subdiv("Final answer")
    try:
        print_json_block(parse_json_response(final_text))
    except json.JSONDecodeError:
        for line in final_text.splitlines():
            print(f"    {line}")

    print()
    print(f"  Total tool wall-clock time : {tool_time:.2f}s")
    print(f"  Tokens                     : {in_tok} in / {out_tok} out / {in_tok + out_tok} total")

    return final_text, tool_time, in_tok, out_tok


# ---------------------------------------------------------------------------
# Demo 2 — Parallel
# ---------------------------------------------------------------------------

def demo_parallel() -> tuple[str, float, int, int]:
    divider("DEMO 2 — Parallel tool execution  (ThreadPoolExecutor, max_workers=3)")
    print("  Expected wall-clock ≈ max(1.2, 0.8, 0.6) = 1.2 s per batch\n")
    print("  Transaction:")
    print_json_block(TRANSACTION)

    final_text, tool_time, in_tok, out_tok = run_agentic_loop(
        "Parallel", parallel_executor
    )

    subdiv("Final answer")
    try:
        print_json_block(parse_json_response(final_text))
    except json.JSONDecodeError:
        for line in final_text.splitlines():
            print(f"    {line}")

    print()
    print(f"  Total tool wall-clock time : {tool_time:.2f}s")
    print(f"  Tokens                     : {in_tok} in / {out_tok} out / {in_tok + out_tok} total")

    return final_text, tool_time, in_tok, out_tok


# ---------------------------------------------------------------------------
# Comparison summary
# ---------------------------------------------------------------------------

def print_comparison(
    seq_text: str, seq_time: float, seq_in: int, seq_out: int,
    par_text: str, par_time: float, par_in: int, par_out: int,
) -> None:
    divider("COMPARISON SUMMARY")

    speedup = seq_time / par_time if par_time > 0 else float("inf")
    time_saved = seq_time - par_time

    print(f"  {'Metric':<35s}  {'Sequential':>12s}  {'Parallel':>12s}")
    print(f"  {'─' * 63}")
    print(f"  {'Tool wall-clock time':<35s}  {seq_time:>11.2f}s  {par_time:>11.2f}s")
    print(f"  {'Speed improvement':<35s}  {'—':>12s}  {speedup:>10.2f}x")
    print(f"  {'Time saved':<35s}  {'—':>12s}  {time_saved:>10.2f}s")
    print(f"  {'Input tokens':<35s}  {seq_in:>12d}  {par_in:>12d}")
    print(f"  {'Output tokens':<35s}  {seq_out:>12d}  {par_out:>12d}")
    print(f"  {'Total tokens':<35s}  {seq_in + seq_out:>12d}  {par_in + par_out:>12d}")

    # Decision comparison
    subdiv("Final decision — identical?")
    try:
        seq_json = parse_json_response(seq_text)
        par_json = parse_json_response(par_text)
        fields   = ["is_eligible", "risk_level", "prior_auth_required", "recommended_action"]
        all_match = True
        for field in fields:
            sv, pv   = seq_json.get(field), par_json.get(field)
            match    = sv == pv
            marker   = "MATCH  " if match else "DIFFER "
            print(f"  {marker}  {field}: {sv!r}")
            if not match:
                all_match = False
                print(f"           parallel had: {pv!r}")
        print()
        if all_match:
            print("  ✓ Both demos produced identical final decisions.")
        else:
            print("  ✗ Decisions differed (non-determinism at temperature > 0).")
    except json.JSONDecodeError:
        identical = seq_text.strip() == par_text.strip()
        print(f"  Raw text identical: {identical}")

    subdiv("Theoretical vs actual speedup")
    expected_seq = sum(EXPECTED_LATENCIES.values())
    expected_par = max(EXPECTED_LATENCIES.values())
    print(f"  Expected sequential  : ~{expected_seq:.1f}s  (sum of all latencies)")
    print(f"  Actual  sequential   :  {seq_time:.2f}s")
    print(f"  Expected parallel    : ~{expected_par:.1f}s  (slowest single tool)")
    print(f"  Actual  parallel     :  {par_time:.2f}s")
    print(f"  Theoretical speedup  : {expected_seq / expected_par:.2f}x")
    print(f"  Actual speedup       : {speedup:.2f}x")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("  PARALLEL TOOLS DEMO")
    print("  Bedrock Converse API  |  us-east-1  |  cdk-dev")
    print("=" * 70)
    print()
    print("  Tool latencies:")
    for name, lat in EXPECTED_LATENCIES.items():
        print(f"    {name:<35s} {lat:.1f}s")

    seq_text, seq_time, seq_in, seq_out = demo_sequential()
    par_text, par_time, par_in, par_out = demo_parallel()

    print_comparison(
        seq_text, seq_time, seq_in, seq_out,
        par_text, par_time, par_in, par_out,
    )

    print()
    print("=" * 70)
    print("  Demo complete.")
    print("=" * 70)
    print()
