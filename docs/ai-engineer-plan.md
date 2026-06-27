# Gen AI Engineer Transition — 6-Month Plan & Claude Tooling Workflow

**Goal:** Transition into a Gen AI Engineer role; begin applying in ~6 months.
**Assumed pace:** ~10 hrs/week (weekday afternoons + weekends). Adjust the week numbers if that's off.
**Head start you already have:** AWS Certified Developer – Associate. That earns you a **50% discount on your next AWS exam** and lets you **skip the foundational cloud courses** — go straight to the AI/ML prep.

---

## Part 1 — Certification Sequence

Quick reality check first: the **AWS ML Specialty (MLS-C01) retired on March 31, 2026**, so if it was on an older roadmap, it's gone. The current path is role-based and directly aligned to Gen AI Engineer.

| Phase | Weeks | Certification | Cost (with your 50% off) | Why it's here |
|---|---|---|---|---|
| 1 | 1–4 | **AWS Certified AI Practitioner** (AIF-C01) | ~$50 | Fast win + résumé signal; common AI/ML/GenAI vocabulary. Exam: July 10. |
| 2 | 5–14 | **AWS GenAI Developer – Professional** (AIP-C01) | ~$150 | **The core target** — directly maps to Gen AI Engineer work: RAG, Bedrock, foundation models, vector DBs, agents |
| 3 | 15–18 | **Claude Certified Architect – Foundations** | ~$99 | Differentiator; validates exactly what you've built in Sessions 1–11. Low additional prep needed. |
| Later | optional | **AWS ML Engineer – Associate** (MLA-C01) | ~$75 | Pursue if you move toward MLOps / ML Platform Engineer roles specifically. Heavy SageMaker + classical ML — less relevant to Gen AI day-to-day. |

### Phase 1 — Foundation & quick win (Weeks 1–4) 🎯 Exam: July 10
**AWS Certified AI Practitioner.** Foundational, covers AI/ML, generative AI, and responsible AI. Exam scheduled July 10. Study items 12–16 in curriculum cover the gaps (classical ML fundamentals, AWS AI service portfolio, responsible AI, ML governance).
- *Resources:* free AWS Skill Builder Exam Prep Plan, plus your work Udemy sub.

### Phase 2 — The core target (Weeks 5–14)
**AWS GenAI Developer – Professional.** This is the cert that maps directly to Gen AI Engineer roles. Covers: RAG architectures, Bedrock Knowledge Bases and Agents, foundation model selection, vector databases, prompt engineering at scale, evaluation of GenAI systems, cost optimization, responsible AI for GenAI. Your sessions 1–11 + curriculum items 17–20 give you a strong head start — focused additional prep on Bedrock Agents, embeddings, and advanced RAG.
- **Start applying to roles around Week 12** — AI Practitioner done + GenAI Developer in progress + real portfolio is a credible package.

### Phase 3 — Differentiator (Weeks 15–18)
**Claude Certified Architect – Foundations.** You're unusually well-positioned: its exam domains (agentic architecture, Claude Code workflows, MCP integration, prompt engineering, context management) are almost exactly what your learning summary already covers. It's closed-book, so the hands-on work you've logged is what carries you. Few people hold it yet, which makes it a strong résumé differentiator for healthcare AI roles.

### Optional — later
**AWS ML Engineer Associate.** Heavy on SageMaker training jobs, feature engineering, and classical ML pipelines — not your day-to-day as a Gen AI Engineer. Pursue this if you shift toward MLOps or ML Platform Engineering specifically, or if a role you want lists it explicitly. Don't let it block your job search.

### Portfolio (runs in parallel — certs alone don't land ML jobs)
You already have strong raw material. Polish 2–3 flagship GitHub projects:
1. **Eligibility AI agent** (CDK: SQS → Lambda → Bedrock → DynamoDB) — you built it. Add a clear README, an architecture diagram, and eval results.
2. **A RAG system** (Bedrock Knowledge Base or OpenSearch) over a healthcare document set.
3. **An evaluation / test harness** for an agent — rare and genuinely impressive for MLOps roles.

Commit daily. Your "production systems engineer learning ML" angle is the real edge — most ML applicants can't deploy or operate anything. You can.

### Cost control on your personal AWS account
- Use the **AWS Free Tier** and **SageMaker Studio Lab** (free, separate from your AWS account) for notebooks.
- The #1 surprise ML charge is **leaving SageMaker inference endpoints running** — always tear them down after a lab.
- Set an **AWS Budgets alarm at a low threshold** ($5–10) so nothing sneaks up on you.

---

## Part 2 — Claude Tooling Workflow (Desktop + Claude Code + Cowork)

Three tools, three distinct jobs. The trap is using one for everything; the win is a *loop* between them.

### The roles

**Claude Desktop (chat) = your tutor + thinking space.**
Concept explanations ("teach me how gradient descent actually updates weights"), design discussions, cert Q&A, sanity-checking your understanding. Use a **Project per focus area** (one for MLA-C01, one for the Claude cert) so the context persists across sessions. This is where most of your tutor-mode time lives.

**Claude Code = your hands-on lab.**
This is the "practice" two-thirds of your 1:2 watch-to-practice ratio. Building projects, running code, debugging. The key move is configuring it to *teach* rather than just hand you finished code — see the learning setup below.

**Cowork = your project manager + living memory.**
It already maintains your `learning-summary.md`. Keep using it to update that running summary after each session, organize study materials, and run multi-step tasks across files. It's the layer that keeps everything coherent week over week.

### The weekly loop
1. **Learn** a concept in Desktop chat (tutor mode) — short and focused.
2. **Build** it in Claude Code (roughly 2× the time) — hands-on, explain-first.
3. **Capture** what clicked back into the Cowork summary.
4. **Commit** the code to GitHub.

### Configuring Claude Code for *learning* (not just shipping)
Most Claude Code advice optimizes for shipping fast — "don't micromanage, just say 'fix it.'" For learning you want the **opposite**: visible reasoning. Two levers do most of the work.

**1. A learning-tuned `CLAUDE.md`** at your project root (Claude reads it at the start of every session). Something like:

> I'm a senior software developer transitioning into ML/AI. Optimize for my understanding, not speed of delivery. Before writing code, explain your approach and the ML-specific reasoning. Use plan mode by default. Show evidence — run the code and show real output, never just assert it works. Comment the non-obvious ML decisions (why this loss function, why this metric, why this train/test split).

Keep it lean — every line should earn its place. Run `/init` once to generate a starter, then trim it.

**2. Plan mode** (press `Shift+Tab` twice, or `/plan`). Claude researches and proposes an approach — read-only — until you approve it. For learning this is gold: you see and can question the plan *before* any code appears, instead of receiving a finished black box.

Two more habits:
- **Evidence before claims.** Make it show test output / printed results, not "this works." Left alone, it will confidently claim success without running anything.
- **`/model`.** Use the strongest model for conceptual and architectural work; lighter models are fine for routine edits.

### When you're further along
**Subagents** run in their own context window and report back a summary, keeping your main session clean during big research tasks. Not needed in week 1 — but worth knowing it's there once projects get large.

---

### Docs to bookmark
- Claude Code: https://docs.claude.com/en/docs/claude-code/overview
- AWS certification prep: AWS Skill Builder (Exam Prep Plans are free)
