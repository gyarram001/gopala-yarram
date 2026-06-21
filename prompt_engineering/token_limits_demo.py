"""
Token Limits Demo using Amazon Bedrock Converse API
Shows the effect of maxTokens on response length, completeness, and cutoff.
"""

import boto3

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

TRANSACTION = """{
  "member_id": "AET-889221",
  "payer_name": "Aetna",
  "service_date": "2026-06-20",
  "service_type": "knee surgery",
  "diagnosis_code": "M17.11"
}"""


def call_bedrock(prompt: str, max_tokens: int = None) -> dict:
    kwargs = {
        "modelId": MODEL_ID,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
    }
    if max_tokens is not None:
        kwargs["inferenceConfig"] = {"maxTokens": max_tokens}

    response = bedrock.converse(**kwargs)

    text = response["output"]["message"]["content"][0]["text"]
    usage = response["usage"]
    stop_reason = response["stopReason"]

    return {
        "text": text,
        "input_tokens": usage["inputTokens"],
        "output_tokens": usage["outputTokens"],
        "stop_reason": stop_reason,
    }


def divider(title: str):
    print(f"\n{'═' * 70}")
    print(f"  {title}")
    print("═" * 70)


def print_token_usage(result: dict, max_tokens: int = None):
    limit_str = str(max_tokens) if max_tokens else "none"
    print(f"\n  --- Token Usage ---")
    print(f"  Input tokens  : {result['input_tokens']}")
    print(f"  Output tokens : {result['output_tokens']}")
    print(f"  Max tokens    : {limit_str}")
    print(f"  Stop reason   : {result['stop_reason']}")
    if result["stop_reason"] == "max_tokens":
        print("  ⚠  Response was CUT OFF — model hit the token limit mid-generation")
    elif result["stop_reason"] == "end_turn":
        print("  ✓  Response completed naturally")


if __name__ == "__main__":
    print("\n" + "█" * 70)
    print("  TOKEN LIMITS DEMO — Healthcare Eligibility")
    print(f"  Model : {MODEL_ID}")
    print("█" * 70)

    # ── Demo 1: No token limit ────────────────────────────────────────────────
    divider("DEMO 1 — No Token Limit")
    print("  Prompt: Fully analyze this eligibility transaction and explain everything relevant.\n")

    prompt_1 = (
        f"Fully analyze this eligibility transaction and explain everything relevant:\n\n"
        f"{TRANSACTION}"
    )

    result_1 = call_bedrock(prompt_1)
    print(result_1["text"])
    print_token_usage(result_1)

    print(
        "\n  OBSERVATION: No limit = Claude writes as much as it wants."
        "\n  Useful for exploratory analysis but unpredictable in production."
    )

    # ── Demo 2: Tight token limit (100 tokens) ────────────────────────────────
    divider("DEMO 2 — Tight Token Limit (maxTokens=100)")
    print("  Same prompt, hard cap at 100 output tokens.\n")

    result_2 = call_bedrock(prompt_1, max_tokens=100)
    print(result_2["text"])
    print_token_usage(result_2, max_tokens=100)

    print(
        "\n  OBSERVATION: Response likely cuts off mid-sentence."
        "\n  The model had more to say but was stopped by the token ceiling."
        "\n  Never use a limit this tight for analysis tasks."
    )

    # ── Demo 3: Right-sized limit (300 tokens) ────────────────────────────────
    divider("DEMO 3 — Right-Sized Limit (maxTokens=300, concise prompt)")
    print("  Rewritten prompt asking for 3 bullet points max. Cap at 300 tokens.\n")

    prompt_3 = (
        f"Analyze this eligibility transaction in 3 bullet points max — "
        f"be concise and focus only on the most important findings:\n\n"
        f"{TRANSACTION}"
    )

    result_3 = call_bedrock(prompt_3, max_tokens=300)
    print(result_3["text"])
    print_token_usage(result_3, max_tokens=300)

    print(
        "\n  OBSERVATION: Concise prompt + right-sized limit = complete, useful response."
        "\n  The prompt does the work of constraining length; maxTokens acts as a safety net."
    )

    # ── Summary comparison ────────────────────────────────────────────────────
    divider("SUMMARY — Token Usage Comparison")
    print(f"  {'Demo':<35} {'Input':>8} {'Output':>8} {'Max':>8} {'Stop Reason'}")
    print(f"  {'-'*35} {'-------':>8} {'-------':>8} {'-------':>8} {'-----------'}")
    print(f"  {'Demo 1 — No limit':<35} {result_1['input_tokens']:>8} {result_1['output_tokens']:>8} {'none':>8}  {result_1['stop_reason']}")
    print(f"  {'Demo 2 — Tight (100)':<35} {result_2['input_tokens']:>8} {result_2['output_tokens']:>8} {100:>8}  {result_2['stop_reason']}")
    print(f"  {'Demo 3 — Right-sized (300)':<35} {result_3['input_tokens']:>8} {result_3['output_tokens']:>8} {300:>8}  {result_3['stop_reason']}")

    print("\n" + "█" * 70)
    print("  TAKEAWAYS")
    print("█" * 70)
    print(
        "\n  1. No limit     — Model writes freely. Unpredictable cost and length."
        "\n                    Use only for exploration."
        "\n"
        "\n  2. Tight limit  — Truncates mid-response. Produces incomplete, broken output."
        "\n                    Never use for analysis or structured responses."
        "\n"
        "\n  3. Right-sized  — Pair a concise prompt with a reasonable ceiling."
        "\n                    Model completes naturally; maxTokens is a safety net."
        "\n                    This is the production pattern.\n"
    )
