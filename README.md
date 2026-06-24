# Amazon Bedrock Demos — Claude + AWS AI Engineering

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)
![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock-FF9900?style=flat-square&logo=amazonaws&logoColor=white)
![AWS CDK](https://img.shields.io/badge/AWS-CDK-FF9900?style=flat-square&logo=amazonaws&logoColor=white)
![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=flat-square&logo=pre-commit&logoColor=white)
![Claude Sonnet](https://img.shields.io/badge/Claude-Sonnet_4.6-7B2FBE?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)

Hands-on demos for building AI-powered applications with **Amazon Bedrock**,
**Claude Sonnet**, and AWS services. Domain: healthcare eligibility (270/271
transactions, prior-auth decisions, payer routing). All demos use structured
JSON output, `temperature=0.0`, and a PHI-safe pre-commit pipeline.

**Model:** `us.anthropic.claude-sonnet-4-6` (Bedrock cross-region inference)

---

## Quick Navigation

| Project | What it demonstrates | AWS Services | Level |
|---------|---------------------|--------------|-------|
| [`first-agent/`](first-agent/) | First Bedrock API call, prompt routing | Bedrock | Beginner |
| [`prompt_engineering/`](prompt_engineering/) | 6 technique demos: temperature, chaining, guardrails | Bedrock | Beginner |
| [`eligibility-agent/`](eligibility-agent/) | Production CDK pipeline | SQS, Lambda, DynamoDB, Bedrock, CDK | Intermediate |
| [`agentic-loop/`](agentic-loop/) | 6 patterns: tool use, memory, RAG, reflection, parallel, human-in-loop | Bedrock, DynamoDB, SNS | Intermediate |
| [`agentic-loop/multi-agent/`](agentic-loop/multi-agent/) | 3 orchestration patterns | Bedrock | Advanced |
| [`mcp-server/`](mcp-server/) | MCP server with 2 tools + Lambda client demo | Bedrock, DynamoDB | Advanced |
| [`hooks/`](hooks/) | Pre-commit: PHI scanner, commit enforcer, AI code review | Bedrock | Tooling |

---

## Code Quality and Safety

Three custom pre-commit hooks run on every `git commit`. They are the
operational safety layer for this repo — not just config files.

| Hook | Stage | What it blocks | Tool |
|------|-------|---------------|------|
| `check-phi` | pre-commit | SSNs, real member IDs, DOBs, patient names in staged files | Python regex |
| `check-commit-msg` | commit-msg | Commit messages that don't match `CATEGORY: description` format | Python regex |
| `ai-review` | pre-commit | Critical bugs, security issues, PHI exposure (CRITICAL severity) | Bedrock Claude |

**Also runs:** Black (formatter), Flake8 (linter), `detect-private-key`,
`detect-aws-credentials`, file-size guard (500 KB max).

PHI false-positive suppression: add `# phi-ok` to the end of a line.
AI review bypass (e.g., no AWS access): `SKIP_AI_REVIEW=1 git commit ...`

```bash
# First-time setup
pip install pre-commit boto3
pre-commit install                        # installs pre-commit hook
pre-commit install --hook-type commit-msg # installs commit-msg hook
```

---

## AWS Services Used

| Service | Used in |
|---------|---------|
| Amazon Bedrock (Claude Sonnet) | All demos |
| Amazon Bedrock (Titan Embed v2) | `agentic-loop/rag_demo.py` |
| Amazon DynamoDB | `agentic-loop/memory_demo.py`, `agentic-loop/human_in_loop_demo.py`, CDK project |
| Amazon SNS | `agentic-loop/human_in_loop_demo.py` |
| Amazon SQS | `eligibility-agent/` |
| AWS Lambda | `eligibility-agent/` |
| AWS CDK | `eligibility-agent/` |

---

## Getting Started

```bash
git clone https://github.com/gyarram001/amazon-bedrock-demos.git
cd amazon-bedrock-demos
```

### Prerequisites

```bash
# AWS credentials configured for cdk-dev profile
aws configure --profile cdk-dev

# Python dependencies (all demos)
pip install boto3

# Pre-commit hooks
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg

# CDK project only
pip install aws-cdk-lib constructs
```

### Run any demo

```bash
AWS_PROFILE=cdk-dev python agentic-loop/multi-agent/multi_agent_demo.py
AWS_PROFILE=cdk-dev python agentic-loop/rag_demo.py
AWS_PROFILE=cdk-dev python prompt_engineering/temperature_demo.py
```

---

## 1. First Agent — Hello World & Eligibility Routing

**Directory:** [`first-agent/`](first-agent/)

| File | What it does |
|------|-------------|
| `main.py` | Python hello world |
| `bedrock_hello.py` | First Bedrock API call; routes a healthcare 270 eligibility transaction to the correct payer endpoint using Claude as a classifier |

**Key concepts:** `bedrock-runtime` client, `converse()` API, system prompts,
routing with structured output.

---

## 2. Prompt Engineering

**Directory:** [`prompt_engineering/`](prompt_engineering/)

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

**Directory:** [`eligibility-agent/`](eligibility-agent/)

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

**Directory:** [`agentic-loop/`](agentic-loop/)

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
AWS_PROFILE=cdk-dev python agentic-loop/agentic_loop_demo.py
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
AWS_PROFILE=cdk-dev python agentic-loop/memory_demo.py
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
AWS_PROFILE=cdk-dev python agentic-loop/human_in_loop_demo.py
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
AWS_PROFILE=cdk-dev python agentic-loop/reflection_react_demo.py
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
AWS_PROFILE=cdk-dev python agentic-loop/parallel_tools_demo.py
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

**Embedding model:** `amazon.titan-embed-text-v2:0`

```bash
AWS_PROFILE=cdk-dev python agentic-loop/rag_demo.py
```

---

## Repository Structure

```
amazon-bedrock-demos/
├── first-agent/              # Hello world + first Bedrock call
├── prompt_engineering/       # 6 prompt engineering technique demos
├── eligibility-agent/        # Production CDK project (SQS → Lambda → DynamoDB)
├── agentic-loop/             # 6 advanced agentic pattern demos
│   └── multi-agent/          # 3 multi-agent orchestration patterns
├── hooks/                    # Pre-commit hooks (PHI, commit-msg, AI review)
└── docs/                     # Learning summary, AI engineer plan
```
