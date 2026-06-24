"""
Temperature Effects Demo using Amazon Bedrock Converse API
Shows how temperature (0.0, 0.5, 1.0) affects consistency vs variation.
"""

import boto3

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

PROMPT = (
    "A 270 eligibility transaction came in for knee surgery with Aetna. "
    "Is prior authorization required? Answer in one sentence."
)

TEMPERATURES = [0.0, 0.5, 1.0]
RUNS_PER_TEMP = 3


def call_bedrock(prompt: str, temperature: float) -> str:
    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": temperature},
    )
    return response["output"]["message"]["content"][0]["text"]


def divider(title: str):
    print(f"\n{'═' * 70}")
    print(f"  {title}")
    print("═" * 70)


if __name__ == "__main__":
    print("\n" + "█" * 70)
    print("  TEMPERATURE EFFECTS DEMO — Healthcare Eligibility")
    print(f"  Model : {MODEL_ID}")
    print("█" * 70)
    print(f'\nPrompt: "{PROMPT}"\n')

    for temp in TEMPERATURES:
        divider(f"Temperature = {temp}")

        if temp == 0.0:
            note = "Deterministic — responses should be near-identical"
        elif temp == 0.5:
            note = "Balanced — some variation in phrasing"
        else:
            note = "Creative — expect the most variation"
        print(f"  ({note})\n")

        for run in range(1, RUNS_PER_TEMP + 1):
            response = call_bedrock(PROMPT, temp)
            print(f"  Run {run}: {response}")

    print("\n" + "█" * 70)
    print("  TAKEAWAYS")
    print("█" * 70)
    print(
        "\n  temp=0.0  Responses are highly consistent (same or near-same wording)."
        "\n            Best for deterministic tasks: data extraction, JSON output."
        "\n"
        "\n  temp=0.5  Moderate variation in phrasing, meaning stays stable."
        "\n            Good for conversational replies and structured summaries."
        "\n"
        "\n  temp=1.0  Most variation — wording, emphasis, and detail can shift."
        "\n            Best for brainstorming, drafting, or creative generation.\n"
    )
