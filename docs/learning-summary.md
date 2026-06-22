# AI Learning Summary
**Started:** June 14, 2026 | **Last Updated:** June 21, 2026

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

**Session 7 (June 22) — planned:**
- Multi-agent orchestration: orchestrator + specialist agent patterns at scale
- Skeleton started: `agentic-loop/multi-agent/multi_agent_demo.py`
- Topics to cover: coordinator-worker vs pipeline vs market topologies, agent-to-agent communication, token budget management across the full pipeline

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

---

## Learning Curriculum (in order)

1. ✅ LLM vs Model vs Agent
2. ✅ Bedrock + first API call
3. ✅ When to use AI vs code
4. ✅ CDK + Lambda + SQS + DynamoDB agent
5. ✅ Prompt engineering — all techniques
6. 🔄 Agentic loops deep dive (multi-agent patterns remaining)
7. ⬜ Multi-agent orchestration — orchestrator + specialist agents at scale
8. ⬜ Claude Code — how to use it effectively as a developer tool
9. ⬜ MCP (Model Context Protocol) — building and connecting MCP servers
10. ⬜ LangChain + LangGraph (LangChain for abstractions, LangGraph for stateful agent workflows)
11. ⬜ Step Functions for multi-step workflows
12. ⬜ n8n — build AI-powered workflows with no/low code
13. ⬜ Bedrock Agents (managed service vs DIY)
14. ⬜ Embeddings + vector search (OpenSearch on AWS)
15. ⬜ Multi-source RAG — retrieving from multiple knowledge bases in one query
16. ⬜ Structured outputs / JSON schema enforcement
17. ⬜ Streaming responses
18. ⬜ Fine-tuning vs prompting — when to use which
19. ⬜ Cost architecture — model selection strategy (Haiku vs Sonnet)
20. ⬜ AI governance + HIPAA compliance for AI systems
21. ⬜ Reliability (retries, idempotency, dead letter queues)
22. ⬜ Security (prompt injection, PHI scrubbing)
23. ⬜ Evaluation + testing agents
24. ⬜ Harness engineering — building systematic test frameworks for AI agent evaluation
25. ⬜ Observability (tracing, cost monitoring)
26. ⬜ Real use case: denial analysis or free-text eligibility parser
27. ⬜ Azure DevOps pipeline hooks

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
