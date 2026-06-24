# Prompt Engineering Demos

Six technique demos for writing better prompts with the Bedrock Converse API.
All examples use a healthcare eligibility transaction as the domain so the
techniques can be compared on the same type of input.

## Demos

| File | Technique | What it shows |
|------|-----------|--------------|
| `prompt_engineering.py` | 5 combined techniques | Role assignment, few-shot examples, chain-of-thought, output constraints, and negative instructions all in a single file |
| `temperature_demo.py` | Temperature control | `temperature=0` (deterministic) vs `0.7` vs `1.0` — same transaction, three different responses; shows variance in eligibility decisions |
| `token_limits_demo.py` | Token limits | How `maxTokens` truncates responses; demonstrates the cost vs completeness tradeoff with small, medium, and large token budgets |
| `prompt_chaining_demo.py` | Prompt chaining | 4-step pipeline: extract fields → validate → decide eligibility → format output for downstream system |
| `negative_instructions_demo.py` | Negative instructions | Compares "Do NOT output PHI" vs positive framing ("Output only the decision code"); shows which approach reduces hallucination |
| `guardrails_demo.py` | Guardrails | System-prompt guardrails for PHI filtering, tone enforcement, and topic boundary — shows what happens when the model tries to cross each boundary |

## Run

```bash
AWS_PROFILE=cdk-dev python prompt_engineering/<filename>.py
```

## Technique Notes

### Temperature
`temperature=0.0` is the only correct setting for production eligibility
decisions — identical inputs must produce identical outputs for audit trails.
The demo exists to show what goes wrong at `0.7` and `1.0` (inconsistent
decisions on the same transaction).

### Prompt Chaining
Each step's output becomes the next step's input. This is the simplest form
of multi-agent thinking — the state accumulates as structured JSON through
the chain rather than in a monolithic single prompt.

### Negative Instructions
"Do not include the member's date of birth" consistently underperforms
"Return only the decision code and reason code" — the model must imagine
what _not_ to do instead of knowing exactly what _to_ do. The demo measures
PHI leakage rate across 5 runs of each style.
