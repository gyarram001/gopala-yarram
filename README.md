# AI Beginner Learning — Amazon Bedrock + Claude Demos

A hands-on learning repo for building AI-powered healthcare eligibility
applications with **Amazon Bedrock**, **Claude Sonnet**, and AWS services.
All demos use the `us-east-1` region and the `cdk-dev` AWS profile.

**Model used throughout:** `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
(Bedrock cross-region inference)

---

## Repository Structure

```
ai-beginner-learning/
├── first-agent/              # Hello world + first Bedrock call
├── prompt_engineering/       # 6 prompt engineering technique demos
├── eligibility-agent/        # Production CDK project (SQS → Lambda → DynamoDB)
└── agentic-loop/             # 6 advanced agentic pattern demos
```

---

## 1. First Agent — Hello World & Eligibility Routing

**Directory:** `first-agent/`

| File | What it does |
|------|-------------|
| `main.py` | Python hello world |
| `bedrock_hello.py` | First Bedrock API call; routes a healthcare 270 eligibility transaction to the correct payer endpoint using Claude as a classifier |

**Key concepts:** `bedrock-runtime` client, `converse()` API, system prompts,
routing with structured output.

---

## 2. Prompt Engineering

**Directory:** `prompt_engineering/`

Six demos covering the core techniques for writing better prompts.
All examples use a healthcare eligibility transaction as the domain.

| File | Technique | What it demonstrates |
|------|-----------|---------------------|
| `prompt_engineering.py` | 5 combined techniques | Role assignment, few-shot examples, chain-of-thought, output constraints, negative instructions — all in one file |
| `temperature_demo.py` | Temperature | Effect of `temperature=0` (deterministic) vs `0.7` vs `1.0` on eligibility decisions |
| `token_limits_demo.py` | Token limits | How `maxTokens` truncates responses; cost vs completeness tradeoff |
| `prompt_chaining_demo.py` | Prompt chaining | Multi-step pipeline: extract → validate → decide → format |
| `negative_instructions_demo.py` | Negative instructions | "Do NOT do X" vs positive framing; avoiding hallucination |
| `guardrails_demo.py` | Guardrails | Input/output filtering for PHI, tone, and topic boundaries |

---

## 3. Eligibility Agent — CDK Production Project

**Directory:** `eligibility-agent/`

A production-ready serverless pipeline deployed with AWS CDK.

```
SQS Queue → Lambda (Claude via Bedrock) → DynamoDB
```

| File | Purpose |
|------|---------|
| `eligibility_stack.py` | CDK stack: SQS queue, Lambda function, DynamoDB table, IAM roles |
| `app.py` | CDK app entry point |
| `lambda/handler.py` | Lambda handler — reads from SQS, calls Bedrock Converse API, writes decision to DynamoDB |
| `requirements.txt` | CDK + boto3 dependencies |

**AWS services used:** SQS, Lambda, DynamoDB, Bedrock, IAM

**Deploy:**
```bash
cd eligibility-agent
pip install -r requirements.txt
cdk deploy --profile cdk-dev
```

---

## 4. Agentic Loop Demos

**Directory:** `agentic-loop/`

Six demos building progressively from a basic tool-use loop to RAG.

---

### 4.1 Agentic Loop — Tool Use with Error Handling

**File:** `agentic_loop_demo.py`

Claude acts as a healthcare eligibility agent that calls three tools
before making a final decision. Demonstrates the core Bedrock agentic loop.

**Tools:** `check_payer_requirements`, `lookup_member_history`, `get_diagnosis_info`
(the third tool injects a simulated service outage to show error recovery)

**Key concepts:**
- `stopReason == "tool_use"` → dispatch tools → append results → loop
- `stopReason == "end_turn"` → print final decision
- `MAX_ITERATIONS` guard prevents runaway loops
- Tool errors caught and forwarded to Claude as `status: "error"` — no crash
- Cumulative token tracking across all iterations

```bash
python agentic_loop_demo.py
```

---

### 4.2 Memory Patterns — Four Strategies

**File:** `memory_demo.py`

Four memory patterns for multi-turn conversations, from stateless to
persistent long-term memory.

| Demo | Strategy | How it works |
|------|----------|-------------|
| Demo 1 | No memory | Fresh `messages` list every call — Claude forgets everything |
| Demo 2 | Short-term | Conversation history carried forward in-process |
| Demo 3 | Long-term | Member context persisted to / retrieved from **DynamoDB**, injected into system prompt in a new session |
| Demo 4 | Summarization | 8-turn conversation compressed to a summary message; shows token reduction |

**AWS services:** Bedrock Converse API, DynamoDB (`eligibility-decisions` table)

```bash
python memory_demo.py
```

---

### 4.3 Human-in-the-Loop — Agent Pause & Resume

**File:** `human_in_loop_demo.py`

Eligibility agent pauses for human review on HIGH-risk transactions
and auto-approves LOW-risk ones.

**Flow:**
```
Bedrock analysis
    ↓ HIGH risk → save PENDING_REVIEW to DynamoDB
                → publish SNS notification
                → poll DynamoDB every 1s (max 10 polls)
                → human approves → agent resumes
                → Bedrock final recommendation
    ↓ LOW risk  → auto-approve (no pause)
```

**AWS services:** Bedrock Converse API, DynamoDB, SNS

```bash
python human_in_loop_demo.py
```

---

### 4.4 Reflection + ReAct — Self-Critique and Reasoning

**File:** `reflection_react_demo.py`

Three-demo comparison showing how reflection and tool-grounded reasoning
improve answer quality over a single baseline call.

| Demo | Pattern | Description |
|------|---------|-------------|
| Demo 1 | Baseline | Single call — generic, no payer verification |
| Demo 2 | Reflection | Two-pass: Pass 1 initial analysis → Pass 2 self-critique with `changes_made` field; field-level diff printed |
| Demo 3 | ReAct | Reason + Act loop — Claude explains reasoning before each tool call, grounded 8-step `reasoning_chain` in final JSON |

**Token cost tradeoff:**

| Pattern | Tokens | Quality |
|---------|--------|---------|
| Baseline | ~290 | Generic |
| Reflection | ~1,250 | Payer-specific, catches mistakes |
| ReAct | ~3,000 | Fully tool-grounded + auditable chain |

```bash
python reflection_react_demo.py
```

---

### 4.5 Parallel Tools — Sequential vs Concurrent Execution

**File:** `parallel_tools_demo.py`

Proves that running batched tool calls in parallel cuts wall-clock time
from the **sum** of latencies to the **max** of latencies — with
identical final answers and token counts.

**Tools with simulated latency:**

| Tool | Sleep |
|------|-------|
| `check_payer_requirements` | 1.2 s |
| `lookup_member_history` | 0.8 s |
| `get_diagnosis_info` | 0.6 s |

**Results:**

| | Sequential | Parallel |
|-|-----------|---------|
| Tool time | ~2.6 s | ~1.2 s |
| Speedup | — | **2.18×** |
| Final answer | ✓ identical | ✓ identical |
| Tokens | 2,639 | 2,639 |

**Implementation:** `ThreadPoolExecutor(max_workers=3)` with
`concurrent.futures.as_completed()`.

```bash
python parallel_tools_demo.py
```

---

### 4.6 RAG — Retrieval-Augmented Generation

**File:** `rag_demo.py`

Demonstrates RAG using Bedrock Titan embeddings and a pure in-memory
vector store (no external vector database).

**Architecture:**
```
Aetna policy text (5 sections)
    → Titan Embed v2 (1024-dim vectors)
    → in-memory list (Python)
    → cosine similarity retrieval (pure Python, no numpy)
    → inject top-2 chunks into Claude prompt
```

**Policy sections indexed:**
1. Knee Surgery (CPT 27447) — prior auth requirements
2. Routine Physical (CPT 99395) — no prior auth, 100% coverage
3. Experimental Treatments — not covered, appeal process
4. Emergency Services — no prior auth, 48h notification
5. Mental Health Services (CPT 90837) — prior auth after 8 sessions

**Queries compared (No-RAG vs RAG):**
1. "What are the prior auth requirements for knee surgery with Aetna?"
2. "Is prior auth needed for a routine physical with Aetna?"

RAG responses are grounded in exact policy text (with cosine scores printed);
No-RAG responses rely on Claude's general training knowledge.

**Embedding model:** `amazon.titan-embed-text-v2:0`

```bash
python rag_demo.py
```

---

## Prerequisites

```bash
# AWS credentials configured for cdk-dev profile
aws configure --profile cdk-dev

# Python dependencies
pip install boto3

# For the CDK project only
pip install aws-cdk-lib constructs
```

---

## AWS Services Used

| Service | Used in |
|---------|---------|
| Amazon Bedrock (Claude Sonnet) | All demos |
| Amazon Bedrock (Titan Embed v2) | `rag_demo.py` |
| Amazon DynamoDB | `memory_demo.py`, `human_in_loop_demo.py`, CDK project |
| Amazon SNS | `human_in_loop_demo.py` |
| Amazon SQS | CDK project |
| AWS Lambda | CDK project |
| AWS CDK | `eligibility-agent/` |
