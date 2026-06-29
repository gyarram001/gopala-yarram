# AI Learning Summary
**Started:** June 14, 2026 | **Last Updated:** June 26, 2026

---

## Core Concepts Learned

### LLM vs Model vs Agent

**LLM (Large Language Model)** — the AI trained on massive text data that understands and generates language. Claude Sonnet, GPT-4, Llama are all LLMs. Text in, text out.

**Model** — same thing as LLM in everyday usage. Broader term technically (image models, voice models exist too) but used interchangeably for language tasks.

**Agent** — a program you write that uses an LLM to make decisions and take actions. The LLM is just one part of it.

> LLM = the brain. Agent = the person (brain + hands + ability to act).

---

### Where Does the Model Live?

- The `openai` or `boto3` package on your machine is just an HTTP client — it sends requests and receives responses
- The actual model runs on **cloud servers** (OpenAI's, Azure's, or AWS's)
- **Amazon Bedrock** is a platform (not a model itself) that hosts multiple models inside AWS:
  - Claude (Anthropic)
  - Llama (Meta)
  - Titan (Amazon)
  - Mistral, Cohere, and others
- **GPT is not on Bedrock** — it only exists on OpenAI or Azure OpenAI

```
Your Lambda / EC2
    ↓ HTTPS (stays inside AWS)
Amazon Bedrock → runs Claude Sonnet
    ↓
Response back to your code
```

---

### Why Bedrock for Your Company

| Option | Model Lives | PHI Leaves AWS? | Verdict |
|---|---|---|---|
| `openai` package | OpenAI's servers | Yes — risk | Avoid for PHI |
| Azure OpenAI | Azure's servers | Yes — cross-cloud | Avoid if servers are on AWS |
| Amazon Bedrock | Inside AWS | No | Best fit |

Your servers are on AWS EC2. Bedrock keeps data inside your AWS account, uses IAM role auth (no API keys), and is covered under AWS's HIPAA BAA.

---

### When to Use AI vs Code

**Proved with real numbers:**

| Approach | Time for 4 transactions | Result |
|---|---|---|
| Claude via Bedrock | 8.01 seconds | Correct |
| Plain if/else Python | 0.017 milliseconds | Correct |

**470,000x slower for the same result** — when the input is structured.

**The rule:**

| Situation | Use |
|---|---|
| Input is structured, rules are known | Code |
| Input is unstructured (free text, PDFs, notes) | AI |
| Logic has too many edge cases | AI |
| Output needs to be human-readable language | AI |
| Speed and cost are critical | Code |
| Auditability required (healthcare!) | Code where possible |

**Real example that proved it:**
- Routing by payer name in a structured field → code wins (regex worked fine)
- Extracting service date from a phone call note like *"knee surgery next Tuesday"* → AI wins (regex grabbed the DOB instead, Claude understood context)

---

### Your Eligibility Router — Does It Need AI?

**No.** Your current use case (check Aetna, United, Cigna before Officeally) is pure routing logic with structured EDI input. Code handles it perfectly:

```python
for payer in [aetna, united, cigna]:
    response = payer.check_eligibility(transaction_270)
    if response.coverage_found:
        return response
return officeally.check_eligibility(transaction_270)
```

AI would add cost, latency, and unpredictability for no benefit here.

---

### Where AI Does Add Value in Your Pipeline

| Task | Why AI |
|---|---|
| Normalize inconsistent payer response formats | Unstructured, varies by payer |
| Parse free-text phone notes into structured data | Language understanding needed |
| Claims denial analysis + appeal drafts | Judgment + language generation |
| Prior authorization from clinical notes | Free text, complex rules |
| EDI error resolution | Error messages are human-readable text |
| Payer policy change monitoring | PDF documents, context required |
| Patient-friendly eligibility explanation | Language generation |
| Audit & anomaly detection | Too many edge case patterns for rules |

---

## What You Built

### 1. First Bedrock API Call (`bedrock_hello.py`)
- Called Claude Sonnet on Amazon Bedrock using the Converse API
- Used `boto3` with your existing local AWS credentials
- Sent an eligibility transaction question and got a real AI response

### 2. Eligibility Router Comparison
- Built an AI-powered router using Bedrock
- Built the same router with plain if/else Python
- Measured both — proved code is 470,000x faster for structured input

### 3. Free Text Extraction
- Showed AI extracting structured data from a messy phone call note
- Regex grabbed the wrong date (DOB instead of service date)
- Claude correctly identified "knee surgery next Tuesday" as the service date

### 4. GitHub Push
- Initialized git, connected to GitHub repo
- Set up Personal Access Token (PAT) authentication
- Resolved merge conflict with `--allow-unrelated-histories`
- Pushed code to `github.com/gyarram001/gopala-yarram`

### 5. Pre-commit Hooks with AI Review
Full hook pipeline running on every `git commit`:

```
git commit
    ↓
├── Trailing whitespace & file fixes
├── YAML / JSON validation
├── Private key detection
├── AWS credential scanner
├── PHI pattern scanner (SSN, member IDs, DOBs)
├── Black (Python formatter)
├── Flake8 (Python linter)
├── Commit message format enforcer (FEAT:, FIX:, etc.)
└── AI Code Review → Bedrock → Claude Sonnet
       CRITICAL issues → commit blocked
       Warnings → printed, commit allowed
```

---

## Key Takeaways

1. **AI is a tool, not a replacement for code** — use it only where code genuinely breaks down
2. **Bedrock is a platform, not a model** — you pick which model (Claude, Llama, etc.) per API call
3. **Your AWS stack is already AI-ready** — Lambda + Bedrock + IAM roles = no extra infrastructure needed
4. **Git hooks are scripts that run automatically** — pre-commit runs before every commit, can block it if checks fail
5. **The pre-commit framework** manages hooks as config in the repo — every developer gets the same hooks

---

---

## Session 2 — June 15, 2026

### New Concepts Learned

**CDK Bootstrap**
One-time setup per AWS account/region that creates the CDKToolkit CloudFormation stack. Creates an S3 bucket (for Lambda assets), ECR repo, and IAM roles CDK needs to deploy on your behalf. Like building a post office before you can ship packages — set up once, used forever.

**IAM User for CLI (never use root)**
Root account credentials should never be used for CLI access. Always create a dedicated IAM user (e.g. `cdk-dev`) with scoped permissions and use AWS profiles to switch between accounts.

**SQS + Lambda Integration**
- SQS queues up messages reliably — if Lambda fails, message returns to queue and retries automatically
- `batch_size=1` means one message per Lambda invocation — keeps processing isolated and simple
- Visibility timeout on SQS should match Lambda timeout so messages don't reappear while Lambda is still processing

**Why AI handles missing/invalid data better than code**
Sending a transaction with empty `service_date` and `service_type` to Claude returned a detailed analysis of what was missing and why it matters for eligibility. Writing code to catch every possible missing/invalid field combination across different payer requirements would take weeks — Claude handled it in seconds.

---

### What You Built — Eligibility AI Agent (CDK)

Full AWS AI agent deployed with CDK:

```
eligibility-agent/
    app.py                 ← CDK app entry point
    eligibility_stack.py   ← SQS + Lambda + DynamoDB + IAM
    lambda/
        handler.py         ← calls Bedrock, saves to DynamoDB
    requirements.txt
    cdk.json
```

**Architecture:**
```
SQS message (eligibility transaction)
        ↓  triggers automatically
Lambda (Python 3.12, 30s timeout)
        ↓  calls Bedrock Converse API
Claude Sonnet analyzes transaction
        ↓  saves result
DynamoDB (transaction + AI analysis, keyed by transaction_id)
        ↓
CloudWatch (structured JSON audit log)
```

**IAM permissions scoped tightly:**
- `bedrock:InvokeModel`
- `dynamodb:PutItem` (specific table only)
- `sqs:ReceiveMessage`, `DeleteMessage`, `GetQueueAttributes` (specific queue only)

**Tested with:**
- Valid transaction → Claude analyzed and saved to DynamoDB
- Invalid transaction (empty fields) → Claude identified missing fields and explained impact

---

### Git Hooks Architecture for Multiple Teams

**Central hooks repo pattern:**
- One repo (`company-git-hooks`) owned by Security team contains all shared hooks
- Each team repo's `.pre-commit-config.yaml` references the central repo by version
- Fix a hook once → all repos get the update automatically

**Per-team hook selection:**
```yaml
# Dev repos: PHI scanner, AI review, linting
# Infra repos: CDK security checks, IAM policy review
# All repos: secret scanning
```

**Two layers of enforcement:**
1. Local pre-commit hooks — catch issues before code leaves the laptop
2. Azure DevOps pipeline — runs same checks on push, can't be bypassed with `--no-verify`

**Ownership model:**
- Security team owns security hooks (PHI, secrets)
- Dev team owns code quality hooks (linting, AI review)
- Infra team owns infrastructure hooks (CDK, IAM)

---

### Manager Meeting — Good Questions to Ask
- "What specific problems are we solving with AI — cost, speed, or accuracy?"
- "Since our infrastructure is on AWS and we have HIPAA requirements, have we considered Amazon Bedrock?"
- "Which pain point should we tackle first — claims denials, eligibility, prior auth?"
- "What does success look like for AI at our company in 12 months?"
- "Before we pick tools, do we have a specific use case we're targeting first?"

---

## Key Takeaways (Cumulative)

1. **AI is a tool, not a replacement for code** — use it only where code genuinely breaks down
2. **Bedrock is a platform, not a model** — you pick which model per API call
3. **Your AWS stack is already AI-ready** — Lambda + Bedrock + IAM roles = no extra infrastructure needed
4. **Git hooks are scripts that run automatically** — pre-commit framework manages them as config
5. **CDK bootstrap is a one-time setup** — creates infrastructure CDK needs to deploy
6. **Never use root account for CLI** — always use an IAM user with scoped permissions
7. **SQS makes Lambda reliable** — failed messages retry automatically, no transactions lost
8. **AI handles ambiguity, code handles structure** — proved with real numbers (470,000x speed difference)

---

---

## Session 3 — June 15, 2026 (continued)

### Prompt Engineering — 5 Core Techniques

**What is prompt engineering?**
Writing better instructions to the model to get more reliable, accurate, and consistent output. The quality of your prompt directly determines the quality of the agent.

---

**Technique 1 — Role Assignment**
Give Claude a specific identity before asking it anything. A specialist gives specialist answers.

```python
# BAD — generic response
"Review this transaction"

# GOOD — healthcare specialist response
system = "You are a senior healthcare eligibility specialist with 10 years
experience processing 270/271 transactions. You understand HIPAA compliance,
payer requirements, and common eligibility issues."
```

---

**Technique 2 — Specificity**
Vague in = vague out. Tell Claude exactly what to check.

```python
# BAD
"Is this transaction okay?"

# GOOD
"Review this eligibility transaction and identify:
1. Any missing required fields for a 270 transaction
2. Whether the diagnosis code format is valid
3. Whether the service date is within a reasonable range
4. Any payer-specific requirements for Aetna"
```

---

**Technique 3 — Output Format Control (most important for production)**
Force Claude to return structured JSON so your Python code can parse and act on it reliably. Never parse free text in production — it breaks unpredictably.

```python
"Return your analysis as JSON with exactly these fields:
is_valid (boolean), missing_fields (list), issues (list),
recommended_action (string)"

# Then in Python:
result = json.loads(response)
if not result["is_valid"]:
    block_transaction()
```

---

**Technique 4 — Few-Shot Examples**
Show Claude 2-3 examples of good output before the real input. Like showing a new employee a completed form before asking them to fill one out. Consistency improves significantly.

---

**Technique 5 — Chain of Thought**
Add "Think step by step:" to force the model to reason through the problem rather than jump to a conclusion. Reduces errors on complex multi-condition rules.

---

### Production-Ready Prompt (all 5 combined)

Output from the combined prompt on a knee surgery transaction:

```json
{
  "is_valid": true,
  "missing_fields": [],
  "issues": [
    "Knee surgery requires prior authorization from Aetna",
    "M17.11 specifies right knee — verify laterality matches surgical site"
  ],
  "prior_auth_required": true,
  "risk_level": "MEDIUM",
  "recommended_action": "Submit eligibility check, initiate prior auth immediately. Verify diagnosis laterality matches planned surgical site.",
  "reasoning": "Step 1: All required fields present... Step 2: M17.11 valid ICD-10-CM... Step 3: Service date reasonable... Step 4: Aetna requires prior auth for all orthopedic surgical procedures..."
}
```

**What Claude caught without any hardcoded rules:**
- Prior auth required for knee surgery (Aetna-specific knowledge)
- Laterality mismatch risk (M17.11 = right knee — must match surgical site)
- Risk level with full reasoning — fully auditable for HIPAA

**How this maps to your workflow:**
```python
if result["prior_auth_required"]:
    trigger_prior_auth_workflow()
if result["risk_level"] == "MEDIUM":
    route_to_human_review_queue()
# reasoning field → store in DynamoDB for audit trail
```

---

---

## Session 4 — June 16, 2026

### Advanced Prompt Engineering

---

**Temperature**
Controls how predictable vs creative the model is. Range: 0.0 to 1.0.

- `0.0` → identical response every run. Use for all clinical/compliance decisions
- `0.5` → balanced. Use for patient-facing summaries or explanations
- `1.0` → varied phrasing, same factual conclusion on factual questions

Key finding: at high temperature, Claude varies *how* it says something, not *what* it decides on factual questions. The core answer stayed locked — only phrasing changed.

Rule for healthcare agents: use `0.0` for anything that feeds a decision or gets stored in DynamoDB.

---

**Token limits**

- Every Bedrock response includes `usage.inputTokens`, `usage.outputTokens`, `usage.totalTokens`
- Every response includes `stopReason`: `end_turn` (normal) or `max_tokens` (cut off)
- `max_tokens` = incomplete response — never save to DynamoDB, handle as error
- Token limits are a safety ceiling — the prompt controls actual length
- Demo proved: tight prompt + right-sized limit beats tight limit alone

**Token optimization best practices:**
- Keep system prompts tight — every call includes them
- Send only needed fields, not full EDI files
- Ask for concise output explicitly in the prompt
- Let code handle formatting cleanup — don't waste tokens on format instructions
- Use prompt caching for system prompt + few-shot examples

**Prompt caching:**
- Cache system prompt + examples (anything static across calls)
- First call: 25% more expensive (cache write)
- All subsequent calls: 90% cheaper (cache read)
- Requires minimum 1,024 tokens to activate
- At 10,000 transactions/day: saves ~$1,000/month on system prompt tokens alone

```python
system=[{
    "text": "Your system prompt...",
    "cachePoint": {"type": "default"}
}]
```

---

**How Bedrock sends prompts to Claude**

Bedrock converts your Python objects into a single text block with XML-style tags:

```
<system>rules here</system>
<human>your message</human>
<assistant>   ← Claude writes from here
```

For multi-turn conversations, the full history is included every call:
```
<human>message 1</human>
<assistant>response 1</assistant>
<human>message 2</human>
<assistant>   ← Claude continues
```

Claude has no memory — your code carries the full conversation history forward on every call. This is why long conversations cost more tokens over time.

---

**Conversation roles**

| Role | Who writes it | When |
|---|---|---|
| `system` | You | Once per agent — rules, persona, output format |
| `user` | You | Every input, tool results, follow-ups |
| `assistant` | Claude (or you for few-shot) | Claude's responses |

System prompt is optional — only needed when you want consistent behavior across many calls (production agents always use it).

---

**Prompt chaining**

Breaking a complex task into focused sequential steps. Output of each step feeds the next.

4-step eligibility chain built and tested:

```
Step 1: Validate fields          161 input tokens
Step 2: Check payer requirements  89 input tokens (step 1 output was small)
Step 3: Risk assessment          242 input tokens (steps 1+2 accumulated)
Step 4: Recommended action       417 input tokens (all previous accumulated)
Total: 909 tokens across 4 calls
```

Key insight: tight outputs in early steps = lower token cost in later steps.

Why chaining beats one big prompt:
- Stop early if step 1 fails (saves tokens on invalid transactions)
- Different specialist role per step
- Add business logic between steps (code controls the flow)
- Debug each step independently
- Maps directly to Step Functions — one state per step

---

**Negative instructions**

Telling Claude what NOT to do — as important as what to do.

Without negative instructions: verbose output (396 tokens), markdown fences, prose mixed with JSON — `json.loads()` fails.

With negative instructions: structured output (328 tokens), uncertainty expressed inside JSON.

Important finding: Claude doesn't always follow formatting instructions perfectly (still added markdown fences despite being told not to). Solution — two layers:

```
Layer 1: Negative instructions in prompt  → reduces occurrence
Layer 2: Defensive parsing in code        → catches what slips through
```

```python
def parse_bedrock_json(raw_text):
    cleaned = re.sub(r"```json\s*|\s*```", "", raw_text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        log_error(raw_text)
        return {"error": "parse_failed"}
```

Key insight: if code can handle it reliably, don't use prompt tokens for it. Let code clean up formatting, let prompts focus on content and rules.

---

**Guardrails — 3 levels**

**Level 1 — Prompt guardrails:**
Rules in system prompt. Off-topic input returned `{"error": "out_of_scope"}` in 13 tokens. Works well but Claude isn't perfect at following every instruction.

**Level 2 — Code guardrails:**
Validate Claude's output before using it. Caught non-JSON response from vague prompt — blocked DynamoDB write without crashing. Most reliable layer — code is deterministic.

**Level 3 — Bedrock guardrails (AWS managed):**
Sit between your code and Claude. Intercept every request AND response. Six protection types:
- Content filters (hate, violence, sexual, misconduct)
- PII detection — BLOCK or ANONYMIZE SSNs, names, emails, phones
- Denied topics — block medical advice, legal advice
- Word filters — block "guaranteed coverage" language
- Grounding — verify response matches source documents
- Custom contextual grounding

Guardrail versions: `DRAFT` for development, published versions (v1, v2) for production. Pin Lambda to specific version so security changes don't surprise production.

**Team ownership:**
| Team | Responsibility |
|---|---|
| Security | Creates, versions, approves, monitors guardrails |
| Dev | References guardrail ID in Lambda via env variable |
| Infra | Deploys guardrails CDK stack via Azure DevOps |

Security team has IAM permissions to create/modify guardrails. Dev team has read-only access — references ID only.

AWS logs every guardrail intervention automatically — built-in HIPAA audit trail with no extra code.

---

## Key Takeaways (Cumulative)

1. **AI is a tool, not a replacement for code** — use it only where code genuinely breaks down
2. **Bedrock is a platform, not a model** — you pick which model per API call
3. **Your AWS stack is already AI-ready** — Lambda + Bedrock + IAM roles = no extra infrastructure needed
4. **Git hooks are scripts that run automatically** — pre-commit framework manages them as config
5. **CDK bootstrap is a one-time setup** — creates infrastructure CDK needs to deploy
6. **Never use root account for CLI** — always use an IAM user with scoped permissions
7. **SQS makes Lambda reliable** — failed messages retry automatically, no transactions lost
8. **AI handles ambiguity, code handles structure** — proved with real numbers (470,000x speed difference)
9. **Output format control is the most important prompt technique** — always force JSON in production agents
10. **Good prompts = role + specificity + format + examples + chain of thought**
11. **Use temperature 0.0 for all clinical/compliance decisions** — consistency over creativity
12. **Token limits are a safety net, not a solution** — prompt controls length, limit catches edge cases
13. **Prompt caching saves ~90% on static content** — biggest cost optimization at scale
14. **Two layers of defense for JSON parsing** — negative instructions + defensive code
15. **Guardrails are infrastructure, not just prompts** — security team owns them, dev team uses them

---

---

## Session 5 — June 17, 2026

### Agentic Loops — Deep Dive

---

**Basic agentic loop pattern**

One-shot (what you had before):
```
Your code → sends prompt → Claude responds → done
```

Agentic loop (what agents actually do):
```
Your code → sends prompt → Claude responds → needs tool
        ↑                                         ↓
        └──── your code runs tool, sends result ──┘
              repeat until stopReason = "end_turn"
```

Claude drives the conversation. Your code executes what Claude asks for.

---

**Tool use — how it works**

You define tools as JSON schemas. Claude reads them and decides which to call:

```python
tools = [{
    "name": "check_payer_requirements",
    "description": "Check prior auth requirements for a payer and service",
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "payer_name": {"type": "string"},
                "service_type": {"type": "string"}
            },
            "required": ["payer_name", "service_type"]
        }
    }
}]
```

Claude doesn't call tools directly — it tells your code "call this with these parameters." Your code runs it and sends the result back as a user message.

---

**Key finding — Claude batches tool calls:**

Claude called all 3 tools in one turn instead of one at a time:
```
Turn 1: Claude requests all 3 tools at once (stopReason: tool_use)
Turn 2: Claude makes final decision with all results (stopReason: end_turn)
2 round trips instead of 4 — Claude optimized automatically
```

At 10,000 transactions/day: hours of saved processing time.

---

**Production agentic loop pattern:**

```python
MAX_ITERATIONS = 10
iteration = 0
messages = [initial_message]

while iteration < MAX_ITERATIONS:
    response = bedrock.converse(tools=tools, messages=messages)

    if response["stopReason"] == "end_turn":
        break
    elif response["stopReason"] == "tool_use":
        tool_results = []
        for tool_call in extract_tool_calls(response):
            try:
                result = run_tool(tool_call)
                tool_results.append({"status": "success", "result": result})
            except Exception as e:
                tool_results.append({"status": "error", "content": str(e)})
        messages.append(claude_response_message)
        messages.append(tool_results_message)
    iteration += 1

if iteration >= MAX_ITERATIONS:
    log_warning("Loop exceeded max iterations")
```

**Why `status: error` matters:**
Sending fake success when a tool fails makes Claude reason on bad data — confident but wrong. Sending real error lets Claude adjust, proceed with partial data, and flag the gap for review.

---

**Memory — 3 types**

**Short-term (conversation history):**
Lives in `messages` array. Cleared when Lambda restarts. Use for multi-turn conversations within one session. Token cost grows with every turn.

**Long-term (DynamoDB):**
Persists across sessions and Lambda restarts. Use for member history, past decisions, prior auth records. Inject into system prompt (not message history) for efficiency.

```python
member_history = dynamodb.get_item(Key={"pk": f"MEMBER#{member_id}"})
system = f"You are a healthcare eligibility specialist. Member context: {member_history}"
messages = [{"role": "user", "content": [{"text": transaction}]}]  # fresh history
```

Demo proved: 93 input tokens answered correctly from DynamoDB context vs accumulated history tokens from conversation history.

**Conversation summarization:**
When history gets long, summarize old turns to keep tokens bounded.

```
8 turns original:   476 tokens
Compressed to 4:    360 tokens
Saved:              116 tokens (24.4% reduction)
```

Savings compound dramatically over longer sessions (80%+ reduction at 50 turns). Claude retained full context after compression — key validation.

```python
MAX_HISTORY_TOKENS = 1000

def manage_memory(messages, system):
    if count_tokens(messages, system) > MAX_HISTORY_TOKENS:
        old_turns = messages[:len(messages)//2]
        recent_turns = messages[len(messages)//2:]
        summary = summarize(old_turns)
        messages = [
            {"role": "user", "content": [{"text": f"Previous context: {summary}"}]},
            *recent_turns
        ]
    return messages
```

---

**Production memory architecture:**

```
Member submits request
        ↓
Lambda retrieves long-term memory from DynamoDB
        ↓
Injects into system prompt (efficient)
        ↓
Agentic loop runs (short-term memory in messages)
        ↓
Every N turns → summarize old history (keeps tokens bounded)
        ↓
Final decision → save back to DynamoDB (updates long-term memory)
        ↓
Next request for same member → starts with full context
```

---

---

## Session 6 — June 19, 2026

### Agentic Loops — Continued

---

**Reflection + ReAct pattern**

**Reflection (two-pass):**
Agent reviews its own draft output before returning it. Pass 1 generates initial analysis. Pass 2 sends that back to Claude asking it to check for missed risk factors, generic vs payer-specific guidance, missing fields.

Cost/quality tradeoff from demo:
```
Baseline:    cheapest, generic — relies on training knowledge
Reflection:  4× tokens, Aetna-specific — catches missed edge cases
ReAct:       10× tokens, fully tool-grounded, auditable reasoning chain
```

**ReAct (Reason + Act):**
Claude explicitly writes its reasoning before every tool call or decision. Makes reasoning visible, debuggable, and more accurate.

```
Without ReAct: Input → [black box thinking] → answer
With ReAct:    Input → "I need to check X because Y" (Reason)
                     → tool call (Act)
                     → "Result shows Z, so I'll check W" (Reason)
                     → tool call (Act)
                     → final decision with full reasoning chain
```

**Why models don't think by default:**
LLMs generate tokens left to right immediately — predicting next most likely word. "Think step by step" forces intermediate reasoning tokens that condition better final tokens. The thinking IS the tokens — Claude reads its own reasoning as context.

**When to use each:**
- Simple tasks (field validation, routing) → baseline, fast + cheap
- Complex eligibility analysis → reflection, catches edge cases
- High-risk decisions (prior auth, $45k+ procedures) → ReAct, full audit trail

**Auditability value for HIPAA:** ReAct reasoning chain stored in DynamoDB = full explanation of every AI decision for dispute resolution and compliance audits.

---

**Parallel tool execution**

Claude batches tool calls naturally. Your code was running them sequentially — undoing Claude's optimization.

Sequential vs parallel with realistic latencies (1.2s, 0.8s, 0.6s tools):
```
Sequential:  1.2 + 0.8 + 0.6 = 2.6 seconds
Parallel:    max(1.2, 0.8, 0.6) = 1.2 seconds
             54% faster — always limited by slowest tool only
```

Code change — drop-in replacement:
```python
# before
for tool_call in tool_calls:
    result = run_tool(tool_call)
    results.append(result)

# after — 3 lines, every agent gets faster
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=len(tool_calls)) as executor:
    results = list(executor.map(run_tool, tool_calls))
```

Rule: only parallelize independent tools. Claude handles this automatically — it only batches tools that don't depend on each other.

At 10,000 transactions/day: ~3.9 hours saved Lambda compute/day.

---

**RAG — Retrieval Augmented Generation**

**The problem:**
Claude's training has a cutoff date. Payer policies change constantly. Claude gives outdated rules → wrong prior auth decisions.

**The solution:**
At query time, retrieve relevant sections from YOUR current documents and inject into prompt. Claude answers from your policy, not training knowledge.

```
Demo result:
No RAG:   "6-12 weeks PT" (generic, hedged with "verify with plan")
With RAG: "3 months PT minimum, operative report + X-rays within 6 months,
           5-7 business day SLA" (exact, from your 2026 Aetna policy)
Cosine similarity: 0.845 — decisive match to correct chunk
```

**How RAG works:**
```
Setup (one time):
PDF → split into chunks → embed with Titan model → store in vector DB

Query time:
Question → embed question → find similar chunks (cosine similarity)
         → inject top chunks into prompt → Claude answers from them
```

**Storage options for your company:**

| Option | Where vectors live | Best for |
|---|---|---|
| In memory | Lambda RAM | Demos only |
| OpenSearch Serverless | AWS managed | Production, full control |
| Bedrock Knowledge Bases | AWS managed OpenSearch | Production, zero ops |
| pgvector | RDS PostgreSQL | If already using RDS |

**Recommended: Bedrock Knowledge Bases** — point at S3 bucket, AWS handles chunking/embedding/storage/retrieval. One API call to retrieve:
```python
bedrock_agent.retrieve(
    knowledgeBaseId="kb-abc123",
    retrievalQuery={"text": "knee surgery prior auth requirements"}
)
```

**Chunking — critical for quality:**
- Bad: fixed character count — splits mid-sentence
- Good: semantic boundaries — complete thoughts per chunk
- Sweet spot: 300-500 tokens with 50-token overlap between chunks
- Bedrock Knowledge Bases handles this automatically

**Advanced RAG topics to know:**
- **Hybrid search** — vector + keyword (BM25). Critical for CPT codes — exact terms that vector search misses
- **Re-ranking** — retrieve top 10, re-rank by relevance, inject top 3. Removes noise
- **Low confidence handling** — if max score < 0.7, don't inject bad context (worse than no context)
- **Multi-tenant RAG** — separate knowledge bases per payer (Aetna KB, United KB, Cigna KB)
- **Source attribution** — log which chunks drove each decision (HIPAA audit trail)
- **Metadata filtering** — filter by payer/effective_date before similarity search
- **RAG vs fine-tuning** — use RAG when knowledge changes frequently (payer policies). Fine-tune only when style/format needs to change and you have 10,000+ labeled examples
- **Agentic RAG** — agent decides whether to retrieve, what to search, whether results are good enough

**Re-indexing pipeline:**
```
New Aetna PDF uploaded to S3
        ↓ S3 event triggers Lambda
        ↓ re-chunk + re-embed new document
        ↓ delete old chunks, store new ones
        ↓ agents automatically use updated policy
```

---

**Session 7 (June 22) — Multi-Agent Orchestration:**

Three coordination patterns built and run end-to-end against real Bedrock calls. File: `agentic-loop/multi-agent/multi_agent_demo.py`

**Pattern 1 — Orchestrator + Workers** (4,755 tokens | 45.06s)
- Orchestrator makes a *planning call first* — separates deciding what to do from doing it
- Returns a structured subtask list with priorities; workers execute sorted by priority
- Synthesiser receives all worker outputs and produces a unified decision
- Workers ran sequentially (priority 1→2→3); validator got `is_valid: true` — surface check only

**Pattern 2 — Sequential Pipeline** (9,511 tokens | 73.73s)
- Each agent's full output feeds the next; context accumulates across the chain
- Used 2× the tokens of Pattern 1 — the cost of richer context
- Validation agent caught 12 specific X12 EDI 270 compliance errors (compliance score: 12/100) that Pattern 1's validator missed entirely — because it had normalised fields from the intake agent to reason against
- Agent 4 (Decision) received all three prior outputs — final decision nodes need full context

**Pattern 3 — Parallel Specialists** (5,594 tokens | 9.83s parallel phase)
- Fan-out to 3 specialists simultaneously via ThreadPoolExecutor
- Sequential baseline immediately after: 24.98s → **2.54× speedup proved**
- Better than the 2.18× from `parallel_tools_demo.py` — full Bedrock round-trips (~8-10s each) maximise I/O-bound parallelism gains
- Merge orchestrator introduced `blocking: true/false` in consensus output — Claude added this structure unprompted, which is useful but would need to be locked down in production

**Bugs found via /review and fixed:**
- `inferenceConfig` with `temperature=0.0` was missing from every `call_agent` invocation — in multi-agent systems, each call is a fresh API call with its own inference parameters; there is no shared config that propagates from an outer loop
- Pattern 3 `total_tokens` was including sequential baseline tokens, inflating the reported cost
- Hardcoded `PROFILE` and `REGION` constants → externalized to `os.getenv`
- Unused `t_total` variable; PHI false positive on synthetic test ID; E501 long strings fixed via `setup.cfg` `per-file-ignores`

**Key dependency graph insight:** Pattern 1 encodes dependencies via priority numbers (orchestrator assigns 1, 2, 3). The orchestrator's task description for the risk assessor referenced Aetna's medical necessity criteria — meaning it knew the dependency existed and baked it into the task prompt. This works but is fragile: two agents with the same priority would run in arbitrary order. A proper dependency graph (`depends_on` field in the planning output) is the next extension.

---

---

## Session 8 — June 23, 2026

### Claude Code — Slash Commands, CLAUDE.md, Hooks

---

**What is Claude Code?**
Anthropic's official CLI tool for agentic coding. Runs in your terminal, reads your codebase, edits files, runs commands, and iterates — driven by natural language. Not a chat interface — an agent with direct access to your file system and shell.

---

**Slash Commands**

Built-in commands that control Claude Code's behavior mid-session. These are different from skills (user-invocable workflows like `/commit` or `/review`) — built-ins are always available, skills are defined separately.

| Command | What it does |
|---|---|
| `/help` | Show all available commands and keyboard shortcuts |
| `/clear` | Reset conversation context — start fresh without restarting the CLI |
| `/compact` | Compress conversation history to save context window space — Claude summarizes what happened so far |
| `/cost` | Show token usage and estimated cost for the current session |

**Key distinction — built-in commands vs skills:**
- Built-in commands (`/clear`, `/compact`, `/cost`) are always present — they control the tool itself
- Skills (`/commit`, `/review`) are invocable workflows that expand into full prompts — configurable per project
- Skills were not covered this session

**When to use `/compact`:**
Long sessions accumulate context. When Claude starts losing track of earlier edits or you see "context window filling" warnings, `/compact` compresses history while preserving the key facts. Use before starting a large new sub-task within the same session.

---

**CLAUDE.md**

A markdown file Claude Code reads automatically at the start of every session. Encodes project-specific instructions, conventions, and guardrails so you don't repeat them in every prompt.

**Scoping — three levels (inner scope wins):**
```
~/.claude/CLAUDE.md          ← global: applies to all projects on this machine
<repo-root>/CLAUDE.md        ← project: applies to this repo (what you have)
<subdirectory>/CLAUDE.md     ← local: applies only when working in that folder
```

**Your existing CLAUDE.md covers the right sections:**
```
# About Me        ← tells Claude who you are and how to communicate with you
# Structure       ← maps the repo so Claude navigates it correctly
# Commands        ← how to run, lint, format, deploy
# Conventions     ← temperature=0.0, parse_bedrock_json, AWS_PROFILE from env
# Never Do        ← hard guardrails (no hardcoded credentials, no PHI, no missing inferenceConfig)
# currentDate     ← injects today's date so Claude reasons about time correctly
```

**What CLAUDE.md does NOT do:**
- It does not persist between sessions automatically — Claude re-reads it fresh each session
- It does not replace good prompting — it sets defaults, not overrides for every situation
- It does not inject context into Bedrock agent calls — it only affects Claude Code behavior in the CLI

**What makes a good CLAUDE.md:**
- Commands section should be copy-paste runnable — Claude will use them literally
- Conventions should be specific (`temperature=0.0 in inferenceConfig set per call`) not vague (`use good defaults`)
- Never Do section should cover your real failure modes — things that actually went wrong (missing inferenceConfig, hardcoded credentials)
- Keep it short — Claude reads it every session; bloated files dilute signal

---

**Hooks (Claude Code hooks)**

Event-driven shell commands that run automatically in response to Claude Code actions. Separate from git pre-commit hooks — those run on `git commit`, these run on Claude Code tool calls.

**Configured in `.claude/settings.json`:**
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "black $CLAUDE_FILE_PATH"
          }
        ]
      }
    ]
  }
}
```

**Event types:**

| Event | When it fires |
|---|---|
| `PreToolUse` | Before Claude runs a tool — can inspect or block |
| `PostToolUse` | After Claude runs a tool — good for cleanup/validation |
| `UserPromptSubmit` | When you submit a message — can modify or gate the prompt |
| `Stop` | When Claude finishes a response |

**`PreToolUse` vs `PostToolUse`:**
- `PreToolUse` — runs before the action happens. Use to block dangerous operations (e.g., block `Bash` commands that match `rm -rf`)
- `PostToolUse` — runs after the action happens. Use for cleanup (e.g., auto-format after every file edit)

**Practical uses for your project:**
```
PostToolUse on Write/Edit  → run black + flake8 automatically after every file edit
PostToolUse on Write/Edit  → run PHI scanner on changed file before it hits git
PreToolUse on Bash         → block shell commands that contain destructive patterns
UserPromptSubmit           → enforce that prompts reference a ticket number for audit
```

**Not covered this session:**
- Skills (`/commit`, `/review` — user-invocable workflows)
- Best practices for prompting Claude Code effectively
- Multi-file edit strategies
- Git integration
- MCP servers in Claude Code
- Azure DevOps CI/CD integration

---

---

## Session 9 — June 24, 2026

### Claude Code — Skills, Best Practices, Multi-File Edits, Git, MCP, CI/CD

---

**Skills and Commands — same thing, two names**

"Skills" is the conceptual name. "Commands" is the folder name on disk. They refer to the same feature.

```
.claude/commands/teach.md    →  /teach   (project-level — checked into repo, shared with team)
.claude/commands/review.md   →  /review  (project-level)
~/.claude/commands/commit.md →  /commit  (personal — available across all projects)
```

The filename becomes the slash command. `review.md` → `/review`. Your existing `teach.md` and `review.md` files in `.claude/commands/` are skills — confirmed by reading the repo.

**Project-level vs personal:**
- `.claude/commands/` → checked into the repo, every developer gets the same skills (same principle as shared git hooks)
- `~/.claude/commands/` → personal, only on your machine, not in source control

**Skills vs built-in commands:**
- Built-ins (`/clear`, `/compact`, `/cost`) → baked into Claude Code, cannot be changed
- Skills → yours to write, version, and distribute per project

---

**Best Practices for Using Claude Code**

The core shift: Claude Code is not a chat assistant — it is an agent you delegate tasks to.

| Chat thinking | Agent delegation thinking |
|---|---|
| "Can you help me fix this bug?" | "Fix the null pointer in `handler.py:47`. Run the tests after." |
| "What should I do about auth?" | "Read `eligibility_stack.py`, add IAM role for Bedrock scoped to this account only." |
| "Here's my code, what do you think?" | "Review `multi_agent_demo.py` for missing `inferenceConfig` on any `converse()` call. List every occurrence." |

**Key practices:**
- Give it a target, not a question — "Fix", "Add", "Review", "Refactor" with specific scope
- Reference files by path — Claude Code will read them; don't paste code into the prompt
- Tell it what done looks like — "after the change, flake8 should pass" beats "make it cleaner"
- Use `/clear` between unrelated tasks — stale context from a previous task bleeds into the next
- Let it run commands — Claude Code can execute your test suite, see output, and self-correct; stopping it from running code removes half its value
- CLAUDE.md is your persistent briefing — anything you repeat across sessions belongs there

---

**Multi-File Edit Strategies**

Claude Code has no transaction model — if interrupted mid-task, you may have partial changes across files.

**Safe patterns:**
- Tell it the full scope upfront — "Rename `call_bedrock` to `invoke_agent` across all files in `agentic-loop/`" beats incremental requests that lose context
- Ask for a plan before edits — "List every file you'll need to change, then wait." Review the list, then proceed
- Use git as your safety net — commit clean state before a large multi-file task; `git checkout .` recovers everything if the result is wrong
- Verify with a command after — "Run `grep -r 'call_bedrock' .` to confirm no occurrences remain"
- Don't mix unrelated concerns in one prompt — split them into separate tasks with `/clear` between

---

**Git Integration**

What Claude Code can do with git natively:
- Read `git diff` and `git log` to understand what changed before writing a commit message
- Stage specific files (not `git add -A` which can accidentally include `.env`)
- Write commit messages that follow your `CATEGORY: description` format from CLAUDE.md
- Read PR diffs when given a branch or PR context

What it does not do automatically:
- Push to remote (must be asked explicitly)
- Create branches (you do that, or tell it to explicitly)
- Resolve merge conflicts without you reviewing

**Practical use:** Before a CDK deploy, `/commit` reads the diff, sees `eligibility_stack.py` changed, and writes `FEAT: add Bedrock IAM role to eligibility stack` — matching your convention without you thinking about it.

---

**MCP Servers in Claude Code**

Configured in `~/.claude/settings.json`. When Claude Code starts, it connects to those servers and their tools appear alongside built-in tools — file read, bash, etc. Claude can call them during any coding task.

**Dev-time vs runtime — critical distinction:**

| | MCP in Claude Code | Tool use in Lambda |
|---|---|---|
| When it runs | While you are writing code | When agent processes a transaction |
| Who calls it | Claude Code CLI | Your Lambda agentic loop |
| Purpose | Helps you code | Drives agent behavior in production |

Same protocol, completely separate setup.

**What this unlocks for your stack:** An MCP server exposing `get_member_history(member_id)` lets Claude Code call DynamoDB while helping you write code — it sees real data shapes before generating Lambda code.

---

**Azure DevOps CI/CD Integration**

Claude Code can run headlessly — no interactive terminal, no human in the loop. The `--print` flag outputs to stdout for pipeline consumption.

**Three pieces of a CI review system — where each lives:**

| Piece | Where it lives | Why |
|---|---|---|
| Instruction to Claude (what to look for) | Skill file (`.claude/commands/review-regions.md`) | Specific, bounded task; CLAUDE.md defines the convention but the skill gives Claude the CI task |
| Credential (`ANTHROPIC_API_KEY`) | Azure DevOps secret variable, referenced in YAML as `$(ANTHROPIC_API_KEY)` | Never hardcode credentials — same rule as `AWS_REGION` from `os.getenv()` |
| Enforcement (what blocks the PR) | Azure DevOps pipeline step reading Claude's stdout | Can't be bypassed; git hooks can be skipped with `--no-verify`, pipeline gates cannot |

**Common mistake corrected:** Git hooks run locally and can be bypassed. Pipeline steps are the hard enforcement gate — they run on push, not on commit, and developers cannot skip them.

**Two-layer enforcement pattern:**
```
Layer 1: git pre-commit hook   → catches it locally, developer can bypass with --no-verify
Layer 2: Azure DevOps pipeline → catches it on push, cannot be bypassed, produces audit log
```

Both layers run the same check. The pipeline is the authoritative gate.

---

## Key Takeaways (Cumulative)

1. **AI is a tool, not a replacement for code** — use it only where code genuinely breaks down
2. **Bedrock is a platform, not a model** — you pick which model per API call
3. **Your AWS stack is already AI-ready** — Lambda + Bedrock + IAM roles = no extra infrastructure needed
4. **Git hooks are scripts that run automatically** — pre-commit framework manages them as config
5. **CDK bootstrap is a one-time setup** — creates infrastructure CDK needs to deploy
6. **Never use root account for CLI** — always use an IAM user with scoped permissions
7. **SQS makes Lambda reliable** — failed messages retry automatically, no transactions lost
8. **AI handles ambiguity, code handles structure** — proved with real numbers (470,000x speed difference)
9. **Output format control is the most important prompt technique** — always force JSON in production agents
10. **Good prompts = role + specificity + format + examples + chain of thought**
11. **Use temperature 0.0 for all clinical/compliance decisions** — consistency over creativity
12. **Token limits are a safety net, not a solution** — prompt controls length, limit catches edge cases
13. **Prompt caching saves ~90% on static content** — biggest cost optimization at scale
14. **Two layers of defense for JSON parsing** — negative instructions + defensive code
15. **Guardrails are infrastructure, not just prompts** — security team owns them, dev team uses them
16. **Agentic loops = Claude drives, your code executes** — model decides what tools to call
17. **Claude batches tool calls automatically** — minimizes round trips without you asking
18. **Always send status: error on tool failure** — never lie to Claude with fake success
19. **Long-term memory in system prompt, short-term in messages** — most token-efficient pattern
20. **Summarize conversation history before it gets too long** — 24%+ token savings, context preserved
21. **Models don't think by default** — "think step by step" forces reasoning tokens that improve output
22. **ReAct = Reason + Act** — visible reasoning chain, essential for HIPAA-auditable decisions
23. **Parallelize independent tool calls** — 54% faster with ThreadPoolExecutor, zero correctness cost
24. **RAG grounds Claude in your current documents** — not training knowledge that may be outdated
25. **Bad retrieval is worse than no retrieval** — always threshold cosine score before injecting context
26. **Bedrock Knowledge Bases = zero-ops RAG** — point at S3, AWS handles everything underneath
27. **Pipeline depth trades cost for quality** — sequential pipeline used 2× tokens but found 12 EDI errors that coordinator-worker missed; choose topology based on how much context each agent needs
28. **Temperature must be set per agent call** — in multi-agent systems there is no shared inferenceConfig; every `converse()` call needs its own `temperature=0.0` or it defaults to non-deterministic
29. **Self-reported confidence is not calibrated probability** — Claude's `"confidence": 72` is introspective, not a calibrated score; never use it as a hard routing threshold without validation
30. **Parallel speedup scales with I/O-bound work** — full Bedrock round-trips gave 2.54× vs 2.18× for tool calls; the longer each task waits on network, the more parallelism pays off
31. **CLAUDE.md sets defaults, not overrides** — encodes project conventions once so every session starts with the right context; keep it short and specific
32. **Claude Code hooks are not git hooks** — git hooks run on `git commit`; Claude Code hooks run on tool calls (PreToolUse, PostToolUse); both layers are needed
33. **/compact compresses context, /clear resets it** — use /compact mid-session to stay within context limits while preserving history; use /clear only when starting a completely unrelated task
34. **Skills and commands are the same thing** — "skills" is the concept, "commands" is the folder name; `.claude/commands/teach.md` is a skill invoked as `/teach`
35. **Delegate to Claude Code, don't chat with it** — give it a target verb with specific scope ("Fix X in file Y, run tests after") not an open-ended question
36. **Commit clean state before any multi-file task** — Claude Code has no transaction model; git is your rollback mechanism
37. **MCP in Claude Code is dev-time, tool use in Lambda is runtime** — same protocol, completely separate setup and purpose
38. **CI enforcement belongs in the pipeline, not git hooks** — git hooks can be bypassed with `--no-verify`; Azure DevOps pipeline gates cannot
39. **Skill file vs CLAUDE.md for CI tasks** — CLAUDE.md defines the convention; the skill file gives Claude the specific bounded task to run in the pipeline
40. **MCP tool description is load-bearing** — Claude reads it to decide when to call the tool; vague description = wrong tool calls in production; treat it as code, not a comment
41. **tools/list is discovery, not configuration** — Claude learns available tools at connect time via protocol handshake, not from a static file
42. **asyncio.to_thread() is required for boto3 in async code** — boto3 is synchronous; calling it directly inside async def blocks the event loop; wrap every boto3 call with asyncio.to_thread()
43. **Transport determines deployment model** — stdio for Claude Code (local), Streamable HTTP for Lambda/team server; same server code, different mcp.run(transport=) argument
44. **MCP reusability follows microservice principles** — build the tool once, any agent connects; change it once, all agents get the update; description field replaces the REST API contract
45. **One server with client-side filtering beats many servers for small teams** — operational overhead of multiple servers outweighs token savings until you hit a real security boundary reason to split
46. **Step Functions = infrastructure orchestration; LangGraph = code-level agent workflows** — both model state machines but solve different problems; Step Functions handles retry/HITL/visibility across services, LangGraph handles agent loops and branching inside a single process
47. **Standard workflow for HITL, Express for high-volume short runs** — Standard supports pause-for-days and exactly-once semantics; Express caps at 5 minutes and doesn't support waitForTaskToken
48. **waitForTaskToken: the Lambda return value is ignored** — execution only resumes when `SendTaskSuccess` is called with the token; Lambda finishing has no effect on the paused execution
49. **`output_path="$.Payload"` unwraps the Lambda envelope** — without it the next state reads `$.Payload.risk_level` instead of `$.risk_level`; set it on every `LambdaInvoke`
50. **Choice default → Fail, not AutoApprove** — unknown risk level should fail loudly; a failed execution is investigable, a silently wrong auto-approval causes a real claim error
51. **Per-field regex validation prevents prompt injection at the source** — validate each allowlisted value against its expected pattern (`_FIELD_PATTERNS`) before it enters the prompt; XML delimiters add a second layer
52. **Never store member_id in audit records** — `transaction_id` is the audit key; member context belongs in the source system, fetched via separate authorized lookup
53. **Fail at synth time, not deploy time** — assert `CDK_DEFAULT_ACCOUNT` is set in `app.py`; if `self.account` resolves to `'*'`, Bedrock IAM policy silently becomes wildcard
54. **AI code review on truncated diff hallucinates bugs** — reviewer saw `"maxToken"` (14k cutoff mid-string) and called valid Python a syntax error; always ensure reviewers see complete context

---

---

## Session 10 — June 25, 2026

### LangChain — Abstractions Over Raw Bedrock

---

**Why LangChain exists**

Every AI application is a pipeline: input comes in → gets transformed by components → output comes out. LangChain gives you standardized, reusable components for each stage and a way to connect them with the `|` pipe operator (LCEL — LangChain Expression Language).

The raw Bedrock code you built in Sessions 3-6 works and is correct. LangChain removes the boilerplate — message dict construction, response parsing, inferenceConfig on every call — so you focus on the logic.

---

**The 4 components you need**

**1. `ChatBedrock` — model wrapper**

Replaces `bedrock.converse()`. Set `model_kwargs={"temperature": 0.0}` once on the object; applies to every call.

```python
from langchain_aws import ChatBedrock
llm = ChatBedrock(client=bedrock_client, model_id=MODEL_ID, model_kwargs={"temperature": 0.0})
```

**2. `ChatPromptTemplate` — reusable prompt structure**

Replaces manually building `messages = [{"role": "user", "content": [...]}]` every call. Define once, fill at call time via `chain.invoke({"key": value})`.

```python
from langchain_core.prompts import ChatPromptTemplate
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a healthcare eligibility specialist."),
    ("user", "Evaluate this transaction: {transaction}")
])
```

**3. `JsonOutputParser` — replaces `parse_bedrock_json()`**

Strips markdown fences, parses JSON, returns Python dict. Raises `OutputParserException` on failure instead of returning `{"error": "parse_failed"}` — catch in production.

**4. Chain — `|` operator connects all three**

```python
chain = prompt | llm | JsonOutputParser()
result = chain.invoke({"transaction": transaction})
# result is already a Python dict — no manual parsing
```

Output of left feeds input of right. LangChain manages data flow between steps automatically.

---

**The core LangChain vs LangGraph distinction**

| Pattern | Tool |
|---|---|
| A → B → C → D (straight line, no loops) | LangChain chain |
| A → loop until condition | LangGraph |
| A → fan-out to parallel branches → merge | LangGraph |
| A → decision → B or C (branching) | LangGraph |

**LangChain does NOT give you:** loops, state across steps, branching based on model output, or agents that decide what to do next. That is LangGraph's job.

From your existing work:
- Session 4 prompt chain (validate → payer check → risk → action) → LangChain
- Session 5 agentic loop (stopReason loop, tool use) → LangGraph
- Session 7 parallel specialists (fan-out → merge) → LangGraph

---

**Where LangChain earns its place**

The real value is model switching. To swap Claude for GPT-4:

```python
# Before — Claude on Bedrock
from langchain_aws import ChatBedrock
llm = ChatBedrock(model_id="us.anthropic.claude-sonnet-4-5...")

# After — GPT-4
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o", temperature=0.0)
```

Everything below `llm =` — chain, prompt, parser — is identical. Without LangChain, switching models means rewriting the client, auth, message format, response parsing, and token extraction across every file.

Other scenarios where it pays off:
- Team sharing consistent patterns across multiple agents
- Adding LangSmith for automatic tracing (zero code change — just env vars)
- Rapid prototyping of multi-step pipelines

---

**What LangChain returns — the `AIMessage` object**

Instead of `response["output"]["message"]["content"][0]["text"]`, LangChain gives you:

```python
response.content           # the text
response.response_metadata # stopReason, token usage
```

Note: `langchain-aws` version differences can cause token metadata to return `None` — use LangSmith for reliable token tracking in production.

---

**LangSmith — observability layer (optional)**

Cloud platform that automatically captures every chain step — inputs, outputs, tokens, latency — as a visual trace. Zero code changes: enabled via environment variables only.

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=your_key
export LANGCHAIN_PROJECT=eligibility-demo
```

HIPAA note: traces go to LangChain's servers. Use self-hosted LangSmith Enterprise for production PHI. Fine for synthetic data.

---

**What was built — `langchain-demo/simple_chain.py`**

Reproduced Session 3 eligibility validation using LangChain:
- `ChatBedrock` wrapping boto3
- `ChatPromptTemplate` replacing manual message dicts
- `JsonOutputParser` replacing `parse_bedrock_json()`
- Full chain with `|` operator
- Side-by-side comparison showing what each LangChain component replaced

---

### LangGraph — Stateful Agent Workflows

---

**What LangGraph adds over LangChain**

LangChain handles straight pipelines. LangGraph handles everything that needs a loop, branching, or state that persists across steps. It models your agent as a graph — nodes are actions, edges are routing decisions.

Three core concepts replace your Session 5 manual agentic loop entirely:

| Session 5 manual code | LangGraph replacement |
|---|---|
| `messages = []` + manual `.append()` | `AgentState` TypedDict + `add_messages` reducer |
| `while iteration < MAX_ITERATIONS` | `recursion_limit` in `app.invoke()` |
| `if stopReason == "tool_use"` | Conditional edge → `run_tools` node |
| `if stopReason == "end_turn": break` | Conditional edge → `END` |
| `run_tool()` dispatcher + `ThreadPoolExecutor` | `ToolNode(tools)` — parallel by default |
| `toolConfig={"tools": ...}` per call | `llm.bind_tools(tools)` once |

---

**The 4 LangGraph concepts**

**State (`TypedDict` + `add_messages` reducer)**

Typed dict that flows through the entire graph. Every node reads from it and writes to it. `add_messages` is a reducer — appends to the list instead of replacing it. Replaces the `messages` array you managed manually.

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    risk_level: str
```

**Nodes**

Plain Python functions. Take state in, return updated state out. Any single focused action — call LLM, run tools, parse risk, approve, pause for human — belongs in its own node.

**Edges + conditional edges**

Static edge: always go to this node next.
Conditional edge: inspect state, return a string, route to different nodes based on that string.

```python
graph.add_conditional_edges(
    "assess_risk",
    route_on_risk,                    # returns "low", "medium", or "high"
    {"low": "auto_approve", "medium": "validate", "high": "human_review"}
)
```

**Compile + run**

```python
app = graph.compile(checkpointer=checkpointer)
result = app.invoke({"messages": [...]}, config={"configurable": {"thread_id": "tx-001"}})
```

---

**Four demos built — `langgraph-demo/`**

**1. `eligibility_graph.py` — Basic agentic loop as a graph**

Rebuilt Session 5 agentic loop as a LangGraph graph. Same behavior, explicit structure. Proved Claude still batches tool calls automatically — two turns, both tools in turn 1. `ToolNode` replaced the manual tool dispatcher + `ThreadPoolExecutor`.

**2. `hitl_graph.py` — Human-in-the-loop**

Added `interrupt()` and `MemorySaver` checkpointer. HIGH-risk decisions pause the graph and surface context to a reviewer. `Command(resume=decision)` resumes from the exact pause point.

Replaced the Session 5 DynamoDB polling pattern:

| Session 5 | LangGraph HITL |
|---|---|
| Write PENDING_REVIEW to DynamoDB | `interrupt()` saves to checkpointer |
| `while True: poll every 1 second` | Gone — graph pauses natively |
| Human writes to DynamoDB | `Command(resume=decision)` |
| Lambda reads + continues | `app.invoke()` resumes from saved state |

**3. `branching_graph.py` — Three-way conditional branching**

Three risk branches, each a different node with different behavior:
- LOW → `auto_approve` — zero extra LLM calls, instant
- MEDIUM → `validate` — focused second Claude call to verify documentation
- HIGH → `human_review` — `interrupt()` pauses for human

Each branch pays exactly what it needs to. LOW risk never pays the cost of a second LLM call or human wait.

**4. `persistence_demo.py` — State survives process restart**

Replaced `MemorySaver` with `SqliteSaver`. Proved state survives a complete Python process restart — two different PIDs, one continuous graph execution.

Phase 1 (PID 52683): graph runs → hits interrupt → state written to `checkpoints.db` → process exits.
Phase 2 (PID 52731): opens same `checkpoints.db` → loads 6 messages + risk_level by `thread_id` → resumes `human_review` → finishes. Zero repeat tool calls, zero repeat LLM calls.

Production mapping:
- `SqliteSaver` → `PostgresSaver` (RDS Aurora) or custom `DynamoDBSaver`
- `thread_id` → `transaction_id` from SQS message
- Two Python processes → two separate Lambda invocations

---

**Graph visualization — two built-in methods**

```python
app.get_graph().print_ascii()   # terminal debugging — confirms wiring
app.get_graph().draw_mermaid()  # paste directly into README (requires grandalf)
```

`draw_mermaid()` output satisfies the CLAUDE.md requirement for Mermaid architecture diagrams in every project README.

---

**When LangGraph earns its place in production**

Use it when you have at least one of:
- Agent flow branches based on model output (LOW/MEDIUM/HIGH routing)
- Pause and resume across process boundaries (prior auth human review)
- 3+ nodes owned by different teams (explicit ownership boundaries)
- Audit trail required (checkpointer saves every state transition for HIPAA)

Do NOT use it for:
- Straight-line pipelines with no branching (use LangChain chain)
- Single agents that call tools and return an answer (raw Bedrock is simpler)
- Latency-critical paths (framework overhead, though minimal)

---

**`ToolNode` — parallel tool execution built in**

`ToolNode(tools)` replaces your Session 6 `ThreadPoolExecutor` pattern. Tools Claude batches in one turn are executed in parallel automatically. No threading code required.

Sequential tool execution is handled by Claude via docstrings — "Always call this before check_payer_requirements" tells Claude to call tools in separate turns when order matters.

---

**Key production insight — `thread_id` is the foreign key**

Links separate Lambda invocations to the same graph run. SQS `transaction_id` becomes `thread_id`. Checkpointer uses it to save and load state. Without it, no two invocations can share state.

---

---

## Weekly Review — June 26, 2026

### Commits this week (June 20–25)

**June 20 — repo bootstrap and agentic loop demos merged to main**
- Merged prior work: human-in-the-loop (DynamoDB/SNS polling), reflection + ReAct, parallel tool execution, RAG with Titan embeddings
- Added README covering all demos; set default branch to `main`

**June 21–22 — multi-agent orchestration (Session 7)**
- Built `multi_agent_demo.py` with three coordination patterns: orchestrator+workers, sequential pipeline, parallel specialists
- Fixed missing `inferenceConfig temperature=0.0` across all `call_agent` invocations (critical correctness bug)
- Moved pre-commit hooks and Claude commands to repo root; expanded `CLAUDE.md`

**June 23–24 — Claude Code tooling + MCP server (Sessions 8 & 9)**
- Expanded `CLAUDE.md` with full conventions, commands, and guardrails
- Built `mcp_server.py` exposing eligibility tools; fixed DynamoDB key bug; added `max_tokens` guard
- Made repo portfolio-ready: READMEs, badges, lint fixes

**June 25 — LangChain + LangGraph (Session 10)**
- `langchain-demo/simple_chain.py`: reproduced Session 3 eligibility validation using ChatBedrock + ChatPromptTemplate + JsonOutputParser + LCEL `|` pipe
- `langgraph-demo/`: four demos — basic agentic loop as graph, HITL with `interrupt()` + `MemorySaver`, three-way conditional branching, SqliteSaver persistence surviving process restart

### Curriculum items marked ✅ this week
- Item 9: MCP (Model Context Protocol)
- Item 10: LangChain + LangGraph

---

---

---

## Session 11 — June 26, 2026

### AWS Step Functions for Multi-Step Workflows

---

**What Step Functions is — and what it is NOT**

Step Functions is infrastructure-level orchestration. Lambda is code-level execution. LangGraph is code-level stateful agent workflows.

| Layer | Tool | What it handles |
|---|---|---|
| Infrastructure | Step Functions | Retry, pause for days, parallel branches, state machine visibility — all serverless |
| Code (agents) | LangGraph | Loops, branching based on model output, state that persists across calls |
| Compute | Lambda | The actual business logic — one focused job per function |

The key mental model: Step Functions is like a traffic controller for your Lambdas. Each Lambda does one thing well; Step Functions decides which runs when and what to do if it fails.

---

**ASL — Amazon States Language**

The JSON definition of a Step Functions state machine. Every state machine is a JSON document with two keys:

```json
{
  "StartAt": "ValidateFields",
  "States": {
    "ValidateFields": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:validate_fn",
      "Next": "AssessRisk",
      "Retry": [{"ErrorEquals": ["Lambda.ServiceException"], "MaxAttempts": 3}],
      "Catch": [{"ErrorEquals": ["ValidationError"], "Next": "TransactionRejected"}]
    }
  }
}
```

CDK generates the ASL from Python constructs — you don't write the JSON directly. `sfn.StateMachine`, `tasks.LambdaInvoke`, `sfn.Choice`, `sfn.Fail` compile down to ASL at `cdk synth` time.

---

**State types — five you need to know**

| State type | CDK construct | What it does |
|---|---|---|
| `Task` | `tasks.LambdaInvoke` | Calls Lambda (or any AWS service) |
| `Choice` | `sfn.Choice` + `sfn.Condition` | Branches based on a value in the state |
| `Parallel` | `sfn.Parallel` | Runs branches at the same time, waits for all |
| `Map` | (built-in) | Runs the same step over each item in a list |
| `Wait for Task Token` | `LambdaInvoke` with `IntegrationPattern.WAIT_FOR_TASK_TOKEN` | Pauses execution until a callback arrives |

**Choice vs Parallel — the distinction you got wrong in the quiz:**
- `Choice` = pick one branch OR another based on a condition — only one path runs
- `Parallel` = run multiple branches simultaneously — all paths run at the same time, results are merged

---

**waitForTaskToken — the HITL pattern**

The most important pattern for healthcare workflows. Execution pauses (no Lambda cost, no polling) until a reviewer calls `states:SendTaskSuccess` with the task token.

```
Step Functions generates unique token for this execution + state
        ↓
Calls HumanReview Lambda with {"transaction": {...}, "taskToken": "AbCdEf..."}
        ↓
PAUSES — execution costs nothing while paused
        ↓
Lambda stores token in DynamoDB — returns {"status": "QUEUED"} → ignored
        ↓
Reviewer looks up token, approves/denies, calls:
    states.send_task_success(taskToken=token, output={"human_decision": "APPROVED"})
        ↓
Step Functions RESUMES → output flows to SaveDecision
```

Key insight: the Lambda's return value is completely ignored. The execution only resumes when `SendTaskSuccess` is called with the exact token — not when the Lambda finishes. This is why you set `heartbeat=Duration.days(3)` — if nothing calls the callback in 3 days, Step Functions fails the execution rather than waiting forever.

---

**Standard vs Express workflows**

| | Standard | Express |
|---|---|---|
| Max duration | 1 year | 5 minutes |
| Execution model | Exactly-once | At-least-once |
| HITL support | Yes — can pause for days | No — terminates at 5 min |
| Cost | Per state transition | Per duration + requests |
| Best for | HITL, long-running workflows | High-volume, short runs |

**Rule:** Healthcare prior auth workflows → Standard. High-volume short classification pipelines → Express.

---

**Pipeline built — eligibility authorization pipeline**

```
Input: eligibility transaction (member_id, service_type, payer, service_date)

ValidateFields Lambda          ← checks required fields, raises ValidationError on failure
        ↓
AssessRisk Lambda               ← calls Bedrock (Claude), returns risk_level
        ↓
RouteOnRisk (Choice state)      ← reads $.risk_level
    ├── HIGH   → HumanReview (waitForTaskToken — pauses up to 3 days)
    │                   ↓
    └── LOW/MEDIUM → SaveDecision (DynamoDB write)
            ↑ (human review path merges here after callback)

TransactionRejected (Fail)  ← ValidationError Catch target
UnknownRiskLevel (Fail)     ← Choice default — fails loudly on unexpected risk values
```

**The `output_path="$.Payload"` detail:** Lambda wraps its return value in a `Payload` envelope. Without `output_path="$.Payload"`, the next state sees `$.Payload.risk_level` instead of `$.risk_level`. Setting it on `LambdaInvoke` unwraps the envelope automatically.

**Choice default → Fail, not AutoApprove:** When risk_level is anything other than LOW/MEDIUM/HIGH (e.g., Bedrock hallucinated "UNKNOWN"), the `otherwise` branch hits a `Fail` state. Failing loudly is always safer than silently auto-approving. A human can investigate a failed execution; a silently wrong approval causes a real claim error.

---

**What you gain and give up vs a single Lambda**

| Gain | Lose |
|---|---|
| Retry with backoff per step, isolated — one step's retry doesn't restart the whole pipeline | Latency overhead per state transition (~100ms per hop) |
| Pause for days (HITL) — Lambda max is 15 minutes | Cost per state transition (small but not zero) |
| Visual execution graph in AWS console — see exactly where a failure happened | Local testing complexity — no local Step Functions emulator; must use AWS or simulate step by step |
| Exactly-once semantics for each step (Standard) | More moving parts to deploy and maintain |
| Dead letter queue built in — failed executions are retained | |
| Each Lambda has one job — easier to test, debug, and own | |

The single-Lambda approach fails when: any step takes > 15 minutes, you need HITL with a human reviewer, or you need granular retry/visibility per step.

---

**CDK Step Functions constructs — key patterns**

```python
# Choice state with OR condition
risk_router = sfn.Choice(self, "RouteOnRisk")
risk_router.when(
    sfn.Condition.string_equals("$.risk_level", "HIGH"),
    human_review_task,
)
risk_router.when(
    sfn.Condition.or_(
        sfn.Condition.string_equals("$.risk_level", "LOW"),
        sfn.Condition.string_equals("$.risk_level", "MEDIUM"),
    ),
    save_decision_task,
)
risk_router.otherwise(unknown_risk)   # Fail state — never silently auto-approve

# waitForTaskToken — passes generated token to Lambda
human_review_task = tasks.LambdaInvoke(
    self, "HumanReviewTask",
    lambda_function=human_review_fn,
    integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
    payload=sfn.TaskInput.from_object({
        "transaction": sfn.JsonPath.entire_payload,
        "taskToken": sfn.JsonPath.task_token,   # Step Functions injects this
    }),
    heartbeat=Duration.days(3),
)

# Chain definition
definition = validate_task.next(assess_risk_task).next(risk_router)
```

---

**Security patterns the AI code review enforced (8 rounds)**

The AI code review hook (built in Session 8) found real security issues across 8 rounds of commits. Each finding was legitimate:

| Finding | Fix | Why it matters |
|---|---|---|
| `resources=["*"]` on Bedrock IAM | Scoped ARN to specific model/inference-profile via regex parse | Compromised Lambda can't invoke every Bedrock model in the account |
| Shared Lambda role | Per-function CDK `grant_*` — auto-creates minimal role per function | Blast radius isolation — one function's role can't be used by another |
| `json.dumps(event)` in Bedrock prompt | `PROMPT_FIELDS` frozenset allowlist | PHI (member_id, validation_status) never reaches Bedrock or its logs |
| `member_id` written to DynamoDB | Removed from audit records in both handlers | `transaction_id` is the audit key; member context belongs in the source system |
| Prompt injection via field values | Per-field regex (`_FIELD_PATTERNS`) + XML delimiters around data in prompt | defense-in-depth: regex blocks malformed values; XML tags prevent instruction smuggling |
| `self.account` might be `'*'` | Fail-fast assertion in `app.py` if `CDK_DEFAULT_ACCOUNT` unset | Silent wildcard IAM permissions are worse than a failed deploy |
| 14k diff limit in hook | Raised `_MAX_DIFF_CHARS` from 14k to 40k | Truncated diff caused AI to see `"maxToken"` and hallucinate "syntax error" — the bug was in the reviewer, not the code |

**The meta-lesson:** An AI reviewer reading truncated content will hallucinate bugs that don't exist — the same way an LLM given a truncated context window produces confidently wrong answers. Always ensure your AI tools see complete context.

---

---

---

## Session 12 — June 28, 2026

### Classical ML Fundamentals

---

**The three learning paradigms**

**Supervised learning** — you provide labeled historical data `(X, y)`. The model learns to map input features → correct output. Requires labels you already know (e.g. past claims with denial outcomes). Used for: logistic regression, decision trees, random forests, neural networks.

**Unsupervised learning** — no labels. Only raw input `X`. The model finds structure in the data itself: clusters, patterns, anomalies. Used for: k-means clustering, member segmentation.

**Reinforcement learning** — agent learns by taking actions and receiving rewards or penalties. No dataset. Rarely tested on AIF-C01 beyond knowing what it is.

---

**Common algorithms**

**Logistic regression** — fits a line (hyperplane) through feature space to separate classes. Outputs a probability (0–1) via sigmoid function. Despite the name, it classifies — output is a category, not a number. Learns which side of the line each class falls on.

**Decision tree** — learns a series of if/else splits on features. Each split maximizes purity (reduces how mixed the labels are at each node). Intuitive and auditable. Grows too deep → memorizes training data (overfits).

**Random forest** — trains 100+ decision trees, each on a random subset of data and features. Final prediction = majority vote. Averaging many high-variance trees reduces variance without increasing bias. Better than any single tree. Bonus: outputs feature importance scores.

**k-Means** — unsupervised. Place k centroids, assign each point to nearest centroid, move centroids to mean of assigned points, repeat until stable. You choose k in advance. Use the elbow method to pick k (plot inertia vs k values, look for the bend).

**Linear regression** — supervised, continuous output (a number). Fits a line minimizing average squared error between predictions and true values. Output is a dollar amount, count, or any continuous value — not a category.

**Neural networks** — layers of weighted connections. Forward pass: input flows through layers to produce a prediction. Backward pass (backpropagation): error propagates back to update weights via gradient descent. LLMs are an extreme version of this. Not tested in depth on AIF-C01.

---

**Evaluation metrics — the full map**

Start with the confusion matrix:

```
                     Predicted Positive   Predicted Negative
Actual Positive           TP                    FN
Actual Negative           FP                    TN
```

**Classification:**
- **Accuracy** = (TP+TN)/total. Misleading on imbalanced data. A model predicting "never denied" on 94% not-denied data hits 94% accuracy while being useless.
- **Precision** = TP/(TP+FP). Of what you flagged, how many were real. Use when false positives are costly (wasted prior auth effort).
- **Recall** = TP/(TP+FN). Of all actual positives, how many you caught. Use when false negatives are costly (missed denial = uncollected revenue).
- **F1** = harmonic mean of precision and recall. Use when both matter and classes are imbalanced.
- **AUC-ROC** = area under the ROC curve. Threshold-independent. AUC=0.5 → random, AUC=1.0 → perfect. Use when comparing models across all thresholds.

**Regression (continuous output):**
- **RMSE** = root mean squared error. Same units as output. Penalizes large errors heavily (squared). Use when big errors are especially costly.
- **MAE** = mean absolute error. Average of absolute errors. More robust to outliers than RMSE. Use when all errors matter equally.

---

**Overfitting vs underfitting**

**Underfitting (high bias):** model too simple. Poor on both training and test data. The model hasn't learned enough.

**Overfitting (high variance):** model memorized training data including noise. Near-perfect on training, poor on test. The training-vs-test gap IS the overfit signal.

Diagnostic: compare training accuracy to test accuracy.
- No gap, both poor → underfitting
- Training great, test poor → overfitting
- Both good → well-fitted model

**Fixes for overfitting:** limit tree depth, regularization (L1/L2), more training data, dropout (neural nets), early stopping.

**Fixes for underfitting:** more complex model, more features, train longer.

**Proved with real numbers from the demo:**
```
Unlimited tree: Training=1.000, Test=0.900  ← gap of 0.10 = overfitting
Depth-5 tree:   Training=0.940, Test=0.820  ← smaller gap
Random forest:  Training=1.000, Test=0.945  AUC=0.971  ← best overall
```

---

**Bias-variance tradeoff**

Total prediction error = Bias² + Variance + Irreducible Noise

- **Bias** = systematic error. How wrong the model is on average. High-bias models underfit.
- **Variance** = sensitivity to training data. Retrain on a slightly different subset → predictions change a lot. High-variance models overfit.

You cannot eliminate both with a fixed amount of data. More complexity → less bias, more variance. Less complexity → more variance, less bias. Goal: the complexity level where Bias² + Variance is minimized.

Random forests reduce variance by averaging many high-variance trees. That's the entire point of ensemble methods.

Cross-validation measures variance directly: train and evaluate 5 times on different data subsets. High standard deviation across folds = high variance = the model is unstable.

---

**Train / validation / test split — the rules**

Three-way split: 60% train, 20% validation, 20% test.

- Training set: model learns from this. Use it freely.
- Validation set: tune hyperparameters here. Look at it as many times as needed.
- Test set: touch exactly once for final honest evaluation. Every peek leaks information.

`stratify=y` on the split ensures the minority class (denials) stays at the same ratio in all three splits. Without it, you could randomly get a test set with zero denials.

**Cross-validation** (when data is scarce): split training into 5 folds, train on 4, validate on 1, rotate until every fold has been the validation set once. Average the 5 scores. No static validation set needed. Test set still stays locked.

---

**Demo built — `ml-fundamentals/classical_ml_demo.py`**

Ran end-to-end on synthetic claim denial data (1,000 claims, 6.4% denial rate):

- Logistic regression with `class_weight="balanced"` to handle imbalance: Precision=0.16, Recall=0.69, F1=0.26, AUC=0.80
- Decision tree unlimited depth: train accuracy 1.00, test 0.90 → overfit proved
- Decision tree depth=5: gap shrinks, overfitting reduced
- Random forest 100 trees: AUC=0.971, best F1 of all models
- ROC curve: both classifiers plotted, random forest bows much further toward top-left
- k-Means: 3 member clusters found with no labels; elbow plot confirms k=3
- Linear regression: RMSE=51.56, MAE=42.02 on continuous output
- Bias-variance via 5-fold CV: unlimited tree std=0.179 (unstable), logistic reg std=0.059 (stable)

Charts saved: `overfit_curve.png`, `roc_curve.png`, `kmeans.png`

---

## Session 13 — June 29, 2026

### Deep Learning & Neural Networks

---

**Why neural networks exist — the XOR problem**

Logistic regression is a single linear classifier. A single straight line through feature space cannot separate XOR inputs — it achieves only 50% accuracy (random). You need a non-linear decision boundary. Adding hidden layers creates that non-linearity.

The two-layer net (Input→Hidden→Output) with ReLU activations solves XOR at 100%: the hidden layer first transforms the input space so that XOR becomes linearly separable, then the output layer draws the separating hyperplane.

---

**The three operations in every training step**

**Forward pass:** input flows layer by layer to produce a prediction.
```
Z = X · W + b       ← linear combination (dot product of inputs and weights)
A = activation(Z)   ← apply non-linearity (ReLU for hidden, sigmoid for output)
```

**Loss calculation:** measure how wrong the prediction is with a single scalar.
```
Binary cross-entropy: L = -[y·log(ŷ) + (1-y)·log(1-ŷ)]
Penalizes confident wrong answers heavily on a log scale.
```

**Backward pass (backpropagation):** apply the chain rule backwards through all layers to compute how much each weight contributed to the error.
```
dL/dW2 = A1ᵀ · dZ2            ← output layer gradient
dL/dW1 = Xᵀ · (dZ2·W2ᵀ * ReLU'(Z1))   ← hidden layer gradient (chain rule through ReLU)
W ← W − lr · dL/dW             ← gradient descent update
```

The ReLU derivative is 0 or 1 — it zeroes out the gradient for neurons that were inactive during that forward pass ("dead neurons"). This is why weight initialization matters: all-zero weights cause all neurons to be identical and learn the same thing.

---

**Activation functions**

| Function | Formula | When to use |
|----------|---------|-------------|
| ReLU | max(0, z) | Hidden layers — avoids vanishing gradient |
| Sigmoid | 1/(1+e^-z) | Binary output — squashes to (0,1) |
| Softmax | eᶻᵢ / Σeᶻⱼ | Multi-class output — probs sum to 1 |
| Tanh | (e^z−e^-z)/(e^z+e^-z) | RNNs — centered at 0, range (−1,1) |

---

**Optimizers**

**Vanilla SGD:** one global learning rate. Simple but slow — sensitive to bad learning rate choice.

**Adam:** maintains a running average of past gradients (momentum) and adapts the learning rate per parameter. Almost always outperforms vanilla SGD in practice. Default choice for neural nets.

---

**sklearn MLPClassifier on claims data**

- Architecture: Input(10) → Dense(64, ReLU) → Dense(32, ReLU) → Output
- Adam optimizer, early stopping with patience=15, feature scaling mandatory
- Test AUC: 0.564 vs Random Forest AUC: 0.971
- Random Forest wins — expected on small tabular data (1,000 rows)
- Key lesson: neural nets need scale (data volume, parameter count) to outperform tree ensembles on tabular data. For this dataset, the MLP has more parameters than samples — it simply doesn't have enough signal to learn.

---

**Feature scaling is mandatory for neural networks**

Neural nets use gradient descent. If feature A ranges 0–10,000 and feature B ranges 0–1, the gradient for weight_A will be ~10,000× larger than for weight_B. The optimizer overshoots for large-scale features and barely moves for small-scale ones. StandardScaler (mean=0, std=1) before training is non-negotiable.

Tree methods don't need scaling — splits are based on rank order, not magnitude.

---

**Self-attention mechanism — the core of transformers**

Every token in the sequence produces three learned projections:
- **Query (Q):** what information am I looking for?
- **Key (K):** what information do I contain?
- **Value (V):** what do I output if someone attends to me?

```
Attention(Q, K, V) = softmax( Q·Kᵀ / √d ) · V
```

- `Q·Kᵀ` produces a raw score matrix: how relevant is token j to token i?
- `/ √d` (√embedding_dim) scales scores down — prevents exploding softmax when d is large
- `softmax` normalizes each row to a probability distribution (rows sum to 1)
- `· V` computes a weighted blend of all value vectors — each token's output mixes in the context from all other tokens

Stacking 96 transformer blocks with attention between them = GPT-3. The scale is the architecture — the math is the same as this demo.

---

**What we built**

- Numpy neural net from scratch: Input(2)→Hidden(8, ReLU)→Output(1, Sigmoid), 10,000 epochs, loss=0.0002, accuracy=100% on XOR
- sklearn MLPClassifier: Input(10)→Dense(64)→Dense(32)→Output, Adam, early stopping
- Self-attention mechanism: Q/K/V projections, score matrix, softmax, weighted value blend
- Charts: `decision_boundary.png`, `loss_curve.png`, `mlp_training.png`, `attention_heatmap.png`

---

## Learning Curriculum (in order)

### Phase A — AWS AI Practitioner cert + GenAI core (items 1–20)
*Goal: cert by July 10 + foundational GenAI engineering skills*

#### Completed (Sessions 1–12)
1. ✅ LLM vs Model vs Agent
2. ✅ Bedrock + first API call
3. ✅ When to use AI vs code
4. ✅ CDK + Lambda + SQS + DynamoDB agent
5. ✅ Prompt engineering — all techniques
6. ✅ Agentic loops deep dive (tool use, memory, human-in-loop, reflection, parallel, RAG, multi-agent)
7. ✅ Multi-agent orchestration — orchestrator + workers, sequential pipeline, parallel specialists
8. ✅ Claude Code — slash commands, CLAUDE.md, hooks, skills, best practices, multi-file edits, git integration, MCP, CI/CD
9. ✅ MCP (Model Context Protocol) — building and connecting MCP servers
10. ✅ LangChain + LangGraph (LangChain for abstractions, LangGraph for stateful agent workflows)
11. ✅ Step Functions for multi-step workflows
12. ✅ Classical ML fundamentals — supervised / unsupervised / reinforcement learning; common algorithms (linear regression, decision trees, k-means, neural networks); evaluation metrics (accuracy, precision, recall, F1, AUC-ROC, RMSE); overfitting vs underfitting; bias-variance tradeoff
13. ✅ Deep learning & neural networks — forward pass, backpropagation, gradient descent, activation functions (ReLU/sigmoid/softmax), loss functions, Adam optimizer, feature scaling, MLPClassifier, self-attention mechanism (Q/K/V, softmax(QKᵀ/√d)·V), transformer architecture conceptual

#### AIF-C01 Exam Prep — complete by July 9 (exam July 10)
14. ⬜ AWS AI service portfolio — scenario-based: when to use Rekognition (image/video), Comprehend (NLP/sentiment), Textract (document extraction), Transcribe (speech-to-text), Polly (text-to-speech), Kendra (enterprise search), Personalize (recommendations), Forecast (time-series), Lex (chatbots), Translate — vs when to use Bedrock
15. ⬜ Responsible AI — AWS's 8 dimensions (fairness, explainability, privacy, robustness, safety, controllability, veracity, governance); bias types (data bias, algorithmic bias, measurement bias); model cards; SHAP / LIME concepts
16. ⬜ ML governance + security for AI — AWS KMS for encryption, VPC endpoints for Bedrock, AWS Audit Manager, model versioning and reproducibility, AWS Well-Architected Framework for ML (6 pillars applied to AI)

#### After exam — GenAI engineering depth
17. ⬜ Bedrock Agents (managed service vs DIY)
18. ⬜ Embeddings + vector search (OpenSearch on AWS)
19. ⬜ Advanced RAG patterns — query rewriting, HyDE, re-ranking, RAGAS evaluation
20. ⬜ Multi-source RAG — retrieving from multiple knowledge bases in one query

### Phase B — AWS GenAI Developer Professional cert (items 21–27)
*Goal: RAG architectures, Bedrock Agents, vector DBs, foundation model selection, advanced GenAI patterns*

21. ⬜ SageMaker fundamentals — training jobs, pipelines, endpoints, model registry
22. ⬜ Structured outputs / JSON schema enforcement
23. ⬜ Multi-modal — images + text with Claude Vision
24. ⬜ Streaming responses
25. ⬜ Fine-tuning vs prompting — when to use which
26. ⬜ Cost architecture — model selection strategy (Haiku vs Sonnet), semantic caching, Bedrock Batch API
27. ⬜ AI governance + HIPAA compliance for AI systems

### Phase C — Production readiness + job search (items 28–37)
*Goal: portfolio-quality projects + interview-ready on production AI topics*

28. ⬜ Reliability (retries, idempotency, dead letter queues)
29. ⬜ Security (prompt injection, PHI scrubbing)
30. ⬜ Evaluation + testing agents
31. ⬜ LLM-as-judge + prompt regression testing
32. ⬜ Harness engineering — building systematic test frameworks for AI agent evaluation
33. ⬜ Observability (tracing, cost monitoring) + data drift monitoring
34. ⬜ AWS Comprehend Medical — healthcare entity extraction paired with Bedrock
35. ⬜ Real use case: denial analysis or free-text eligibility parser
36. ⬜ Azure DevOps pipeline hooks
37. ⬜ n8n — build AI-powered workflows with no/low code

### Phase D — Claude Certified Architect (items 38–40)
*Goal: differentiator cert after AWS certs are done; builds on everything above*

38. ⬜ Claude Extended Thinking — built-in chain-of-thought vs prompt-level CoT; when to use each
39. ⬜ Claude Agent SDK — Anthropic's official SDK vs raw boto3/Bedrock; agent loop patterns
40. ⬜ Evaluation specific to Claude — LLM-as-judge using Claude to evaluate Claude outputs at scale

**LangGraph (added to item 10):**
LangChain's framework for building stateful, cyclical agent workflows as graphs. Where LangChain handles single-pass chains, LangGraph handles loops — agents that reason, act, check results, and loop back. Think of it as the code-level equivalent of Step Functions but for agent logic specifically. Pairs naturally with LangChain — learn both together.

**n8n (item 12):**
Open-source workflow automation platform (like Zapier but self-hostable and more powerful). Build AI-powered workflows visually — connect Bedrock, SQS, DynamoDB, payer APIs without writing all the glue code. Good for rapid prototyping of agent workflows before committing to full Lambda/Step Functions implementation. Can be self-hosted on EC2 — stays inside your AWS environment for HIPAA compliance.

**Harness engineering (item 24):**
Building systematic evaluation frameworks (test harnesses) for AI agents. Standard unit tests don't work for agents — outputs are non-deterministic. Harness engineering covers: defining evaluation datasets (input + expected output pairs), scoring functions (exact match, semantic similarity, human rating), regression suites that run on every prompt change, and CI/CD integration so prompt changes are automatically evaluated before deployment. Critical for production healthcare agents where wrong decisions have real consequences.

**Multi-agent orchestration (item 7):**
Goes beyond basic multi-agent patterns — focuses on how a central orchestrator agent coordinates multiple specialist agents at scale. Orchestrator receives a task, breaks it into subtasks, delegates to the right specialist, collects results, synthesizes final answer. Covers: agent communication protocols, handling partial failures across agents, state management between agents, when to use Step Functions vs code-based orchestration.
Fits here because it builds directly on multi-agent patterns (end of item 6) and sets up Step Functions (item 11) as the infrastructure layer.

**Multi-source RAG (item 14):**
Retrieving from multiple knowledge bases simultaneously in one query — e.g., Aetna KB + internal member history + clinical guidelines, all searched in parallel, results merged and ranked before injecting into prompt. Covers: federated search across KBs, result merging strategies, source weighting (trust your policy doc more than general knowledge), conflict resolution when sources disagree.
Fits right after basic embeddings + vector search (item 13) — natural progression from single-source to multi-source.

### Claude Code — What to Learn (item 7)

Claude Code is Anthropic's CLI tool for agentic coding. You've already been using it to generate files — but there's much more to it.

**Topics to cover:**

- **Core workflow** — how to give Claude Code effective prompts, when to be specific vs open-ended
- **Context management** — how Claude Code reads your codebase, what files it sees, how to guide it to the right context
- **Slash commands** — `/help`, `/clear`, `/compact`, `/cost` and other built-in commands
- **CLAUDE.md** — you already have one, but learn how to structure it so Claude Code uses it effectively across all tasks
- **Multi-file edits** — having Claude Code modify multiple files in one task safely
- **Running and testing code** — Claude Code can run your scripts, see output, and self-correct
- **Git integration** — Claude Code can read diffs, write commit messages, understand what changed
- **MCP servers** — extending Claude Code with custom tools (connects to your existing MCP knowledge)
- **Hooks** — Claude Code has its own hook system (separate from git hooks) for running checks after edits
- **Using it in your Azure DevOps pipeline** — running Claude Code headlessly in CI for automated tasks
- **Best practices** — what tasks Claude Code excels at vs where to stay hands-on

**Why this matters for your company:**
Your team uses GitHub Copilot today. Claude Code is a more powerful alternative for complex, multi-step coding tasks — especially useful for CDK infrastructure changes, Lambda refactoring, and building out your AI agent codebase.

## Curriculum — When Ready

**MCP (Model Context Protocol)**
Open standard by Anthropic for connecting AI models to external tools and data sources. Universal plug for AI — build a tool once, any Claude-powered application can use it.

Why it matters for your company:
- Build payer API connector once → every agent reuses it
- Build DynamoDB connector once → every agent reads/writes member history
- Standard protocol → works with Claude Code, your Lambdas, future agents
- You're already using MCP — Cowork uses it to give Claude file system access

vs tool use you built manually:
- Tool use = inline tools per Lambda (low reusability)
- MCP = shared server any agent connects to (high reusability)

Prerequisite: understand tool use in agentic loops (done ✅)

---

**LangChain**
Python framework that abstracts away raw API differences between providers. Write agent code once, swap model provider with one line. Learn after raw Bedrock APIs feel natural.

Why it matters:
- Pre-built components for memory, tools, prompt templates, chains
- Faster to build complex multi-step agents
- LangSmith (companion tool) for agent observability and evals

Prerequisite: comfortable with raw Bedrock APIs, prompt engineering, and basic agent patterns (done ✅)

---

**Embeddings + Vector Search**
Text converted to numbers (vectors) that capture semantic meaning. Similar meaning = similar numbers = close in vector space. Powers semantic search — find relevant documents by meaning, not exact keywords.
AWS service: OpenSearch Serverless with vector engine. Use for: finding relevant payer policies, similar past claims, semantic member history search.
Prerequisite: understand RAG (item 6 in curriculum)

---

**Structured Outputs / JSON Schema enforcement**
Formal way to enforce exact output schema at the API level — beyond just asking Claude to return JSON. Downstream code gets guaranteed field names and types, no defensive parsing needed.

---

**Streaming responses**
Stream tokens as Claude generates them instead of waiting for full response. Important for user-facing features where perceived speed matters. Not needed for background Lambda processing.

---

**Fine-tuning vs prompting**
Fine-tuning = training a model further on your own data. Prompting = better instructions to existing model.
Rule of thumb: prompting wins 90% of the time and is faster/cheaper. Fine-tune only when you have thousands of labeled examples and prompting has hit a ceiling.

---

**Cost architecture — model selection strategy**
Not every task needs Claude Sonnet. Match model to task complexity:
- Claude Haiku → simple classification, field extraction, routing (10x cheaper)
- Claude Sonnet → complex reasoning, prior auth decisions, denial analysis
- Design agents to use Haiku for simple steps, Sonnet only where needed

---

**AI Governance + HIPAA Compliance for AI Systems**
Healthcare-specific requirements for AI:
- Audit trail for every AI decision (who, what, when, why)
- Model version pinning — reproduce any past decision exactly
- Human oversight requirements for clinical decisions
- Documentation requirements for AI-assisted decisions
- Data residency — PHI must stay in approved AWS regions
- BAA coverage verification for every AI vendor in the chain
Learn early — shapes how you architect everything else.
