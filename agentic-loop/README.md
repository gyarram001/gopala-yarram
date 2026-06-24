# Agentic Loop Demos

Six demos building progressively from a basic tool-use loop to full RAG.
Each demo uses a healthcare eligibility scenario as the domain.

## Demos

| File | Pattern | Key concepts | Run |
|------|---------|-------------|-----|
| `agentic_loop_demo.py` | Tool use with error recovery | `stopReason == "tool_use"` loop, `MAX_ITERATIONS` guard, tool errors forwarded as `status: "error"` | `python agentic_loop_demo.py` |
| `memory_demo.py` | 4 memory strategies | No memory → short-term → DynamoDB long-term → summarization; token reduction measured | `python memory_demo.py` |
| `human_in_loop_demo.py` | Human-in-the-loop pause/resume | HIGH-risk → PENDING\_REVIEW in DynamoDB + SNS notification → polling → resume; LOW-risk auto-approves | `python human_in_loop_demo.py` |
| `reflection_react_demo.py` | Reflection + ReAct | Baseline vs 2-pass reflection vs tool-grounded ReAct; token cost tradeoff table | `python reflection_react_demo.py` |
| `parallel_tools_demo.py` | Parallel tool execution | `ThreadPoolExecutor` batches tool calls; proves 2.18× speedup over sequential with identical answers | `python parallel_tools_demo.py` |
| `rag_demo.py` | RAG with in-memory vector store | Titan Embed v2 → cosine similarity → inject top-2 chunks; No-RAG vs RAG comparison | `python rag_demo.py` |

## Run any demo

```bash
AWS_PROFILE=cdk-dev python agentic-loop/<filename>.py
```

## Pattern Descriptions

### Tool Use (`agentic_loop_demo.py`)
The fundamental Bedrock agentic loop: Claude requests tools → dispatcher
runs them → results appended to messages → loop until `end_turn`. Three tools
are registered; the third (`get_diagnosis_info`) injects a simulated outage
to demonstrate error recovery without crashing.

### Memory (`memory_demo.py`)
Compares four memory strategies side-by-side. Demo 3 (DynamoDB long-term)
persists member context across sessions — a new boto3 session retrieves
the saved context and injects it into the system prompt. Demo 4 shows how
an 8-turn conversation can be compressed to a single summary message,
reducing input tokens on subsequent calls.

### Human-in-the-Loop (`human_in_loop_demo.py`)
Introduces a decision gate: if Claude scores the transaction as HIGH risk,
execution pauses. The agent writes `PENDING_REVIEW` to DynamoDB and publishes
an SNS notification, then polls (1 s interval, 10 attempt max) waiting for
a human to flip the status. Once approved, the agent calls Bedrock again
for the final recommendation. LOW-risk transactions skip the gate entirely.

### Reflection + ReAct (`reflection_react_demo.py`)
Three-way comparison of answer quality vs token cost:
- **Baseline** (~290 tokens): single call, generic answer
- **Reflection** (~1,250 tokens): two-pass; Pass 2 explicitly critiques Pass 1 with a `changes_made` diff field
- **ReAct** (~3,000 tokens): Reason → Act loop; each tool call is preceded by explicit reasoning; final output includes an 8-step `reasoning_chain`

### Parallel Tools (`parallel_tools_demo.py`)
Bedrock can request multiple tools in one response. This demo dispatches
them concurrently via `ThreadPoolExecutor(max_workers=3)` and measures the
speedup (2.18×). The sequential baseline uses identical prompts — same
tokens, longer wall-clock time.

### RAG (`rag_demo.py`)
Five Aetna policy sections are embedded with Titan Embed v2 into a
pure-Python in-memory vector store (1024-dim vectors, cosine similarity,
no numpy). Top-2 chunks are injected into the prompt. Two queries are run
with and without RAG to show how grounded responses differ from
training-knowledge responses.

## AWS Services

| Service | Used by |
|---------|---------|
| Amazon Bedrock (Claude Sonnet) | All demos |
| Amazon Bedrock (Titan Embed v2) | `rag_demo.py` |
| Amazon DynamoDB | `memory_demo.py`, `human_in_loop_demo.py` |
| Amazon SNS | `human_in_loop_demo.py` |
