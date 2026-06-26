"""
LangGraph Conditional Branching Demo — Session 10

Extends hitl_graph.py with three distinct risk branches instead of two.
Each risk level routes to a different node with different behavior.

Graph structure:
    START → call_llm → should_continue → run_tools → call_llm (loop)
                              ↓ (end_turn)
                         assess_risk
                              ↓
              ┌───────────────┼───────────────┐
              ↓               ↓               ↓
            LOW            MEDIUM           HIGH
              ↓               ↓               ↓
        auto_approve      validate      human_review
              ↓               ↓          (interrupt)
             END             END             ↓
                                            END

New concepts vs hitl_graph.py:
  - Three-way conditional edge (LOW / MEDIUM / HIGH)
  - validate node — focused second Claude call using existing state context
  - auto_approve node — instant approval with no extra LLM calls
  - Running all three paths in one demo to see branching in action

Run: AWS_PROFILE=cdk-dev python langchain-demo/branching_graph.py
"""

import json
import os
from typing import Annotated

import boto3
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

# ---------------------------------------------------------------------------
# Model setup
# ---------------------------------------------------------------------------
AWS_PROFILE = os.getenv("AWS_PROFILE", "cdk-dev")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
bedrock_client = session.client("bedrock-runtime", region_name=AWS_REGION)

llm = ChatBedrock(
    client=bedrock_client,
    model_id=MODEL_ID,
    model_kwargs={"temperature": 0.0},
)

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
MOCK_MEMBER_HISTORY = {
    "MBR-2024-001": {  # phi-ok — synthetic ID, not real PHI
        "member_id": "MBR-2024-001",  # phi-ok
        "plan": "Aetna PPO",
        "coverage_status": "active",
        "deductible_met": True,
        "prior_auths_approved": 2,
        "notes": "Member has history of orthopedic claims",  # phi-ok
    },
}

MOCK_PAYER_REQUIREMENTS = {
    "aetna": {
        "payer": "Aetna",
        "prior_auth_required": True,
        "sla_business_days": 5,
        "required_documents": [
            "CPT code",
            "Clinical notes",
            "Operative report",
        ],
        "high_risk_procedures": [
            "knee replacement",
            "spinal fusion",
            "hip replacement",
        ],
    },
    "cigna": {
        "payer": "Cigna",
        "prior_auth_required": False,
        "sla_business_days": 0,
        "required_documents": [],
        "high_risk_procedures": [],
    },
}


@tool
def get_member_history(member_id: str) -> dict:  # phi-ok
    """
    Retrieve eligibility and prior authorization history for a member.
    Always call this before check_payer_requirements.

    Args:
        member_id: Member identifier (format: MBR-YYYY-NNN)  # phi-ok

    Returns:
        Member coverage details including plan, status, and prior auth history.
    """
    return MOCK_MEMBER_HISTORY.get(
        member_id,
        {"error": "member_not_found", "member_id": member_id},  # phi-ok
    )


@tool
def check_payer_requirements(payer_name: str, service_type: str) -> dict:
    """
    Return prior authorization requirements for a specific payer and service.
    Call this alongside get_member_history when evaluating an eligibility request.

    Args:
        payer_name: Insurance payer name (e.g., 'Aetna', 'United', 'Cigna')
        service_type: Medical service being requested (e.g., 'physical therapy')

    Returns:
        Prior auth requirements, required documents, SLA, high-risk procedures.
    """
    requirements = MOCK_PAYER_REQUIREMENTS.get(payer_name.lower())
    if requirements:
        return {**requirements, "service_type": service_type}
    return {"error": "payer_not_found", "payer_name": payer_name}


tools = [get_member_history, check_payer_requirements]
llm_with_tools = llm.bind_tools(tools)


# ---------------------------------------------------------------------------
# State
# Extended with branch_taken so we can report which path executed.
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    risk_level: str  # LOW | MEDIUM | HIGH
    branch_taken: str  # auto_approve | validate | human_review
    human_decision: str  # approved | rejected (HIGH path only)
    final_outcome: str  # summary of what happened


# ---------------------------------------------------------------------------
# System prompt — ask Claude to return risk_level in final JSON
#
# Risk level rules given explicitly so Claude applies them consistently:
#   LOW    = prior_auth_required is False
#   MEDIUM = prior_auth_required is True, service NOT in high_risk_procedures
#   HIGH   = service IS in payer's high_risk_procedures list
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a healthcare eligibility specialist. "
    "Use tools to gather member history and payer requirements. "
    "Return your final answer as JSON with these exact keys: "
    "eligible (bool), prior_auth_required (bool), "
    "risk_level (LOW or MEDIUM or HIGH), "
    "required_documents (list), recommended_action (string). "
    "Risk level rules: "
    "LOW = prior_auth_required is false. "
    "MEDIUM = prior_auth_required is true and service is NOT in high_risk_procedures. "
    "HIGH = service IS in the payer high_risk_procedures list. "
    "No markdown fences. JSON only."
)


# ---------------------------------------------------------------------------
# Node: call_llm
# ---------------------------------------------------------------------------
def call_llm(state: AgentState) -> AgentState:
    """Call the LLM with current message history."""
    response = llm_with_tools.invoke(state["messages"])
    print(f"  [call_llm] tool_calls={len(response.tool_calls)}")
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Conditional edge: should_continue
# Routes to run_tools if Claude has tool calls, otherwise to assess_risk.
# ---------------------------------------------------------------------------
def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "run_tools"
    return "assess_risk"


# ---------------------------------------------------------------------------
# Node: run_tools (ToolNode — unchanged)
# ---------------------------------------------------------------------------
tool_node = ToolNode(tools)


# ---------------------------------------------------------------------------
# Node: assess_risk
# Parses risk_level from Claude's final JSON and stores in state.
# ---------------------------------------------------------------------------
def assess_risk(state: AgentState) -> AgentState:
    """Extract risk_level from Claude's JSON response and store in state."""
    import re

    last_message = state["messages"][-1]
    raw = last_message.content
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
    clean = match.group(1) if match else raw.strip()

    try:
        parsed = json.loads(clean)
        risk = parsed.get("risk_level", "LOW").upper()
    except (json.JSONDecodeError, AttributeError):
        risk = "LOW"

    print(f"  [assess_risk] risk_level={risk}")
    return {"risk_level": risk}


# ---------------------------------------------------------------------------
# Three-way conditional edge: route_on_risk
#
# This is the core of Option B. Three return values → three different nodes.
# Each string maps to a node name in add_conditional_edges() below.
#
# Compare to hitl_graph.py which only had two branches:
#   "human_review" or "end"
# Here: "low", "medium", "high" → three completely different nodes.
# ---------------------------------------------------------------------------
def route_on_risk(state: AgentState) -> str:
    """Route to the correct node based on risk level."""
    risk = state.get("risk_level", "LOW")
    if risk == "HIGH":
        return "high"
    elif risk == "MEDIUM":
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Branch node: auto_approve (LOW risk)
#
# No extra LLM call needed. Pull the recommendation from state, format it,
# store the outcome. Done in one step — no network call.
#
# This is the key advantage of branching: LOW risk never pays the cost
# of a second LLM call or a human review delay.
# ---------------------------------------------------------------------------
def auto_approve(state: AgentState) -> AgentState:
    """
    Instantly approve LOW-risk transactions.
    No extra LLM call — reads recommendation already in state.
    """
    print("  [auto_approve] LOW risk — auto-approving")
    return {
        "branch_taken": "auto_approve",
        "final_outcome": "AUTO_APPROVED — no prior auth required",
    }


# ---------------------------------------------------------------------------
# Branch node: validate (MEDIUM risk)
#
# Makes a second focused Claude call with a narrow question:
# "Are the required documents present in the transaction?"
#
# Key point: this call uses context already in state (messages history
# has tool results). Claude doesn't need to call tools again — it already
# has the payer requirements from the first pass.
#
# This is more efficient than re-running the full analysis. The second call
# is cheap (small prompt, fast answer) because it's scoped to one question.
# ---------------------------------------------------------------------------
def validate(state: AgentState) -> AgentState:
    """
    Second focused Claude call for MEDIUM-risk cases.  # phi-ok
    Verifies required documents are present before approving.
    """
    print("  [validate] MEDIUM risk — running documentation check")

    # Build a narrow focused prompt using context already in state.
    # We don't re-run tools — the tool results are already in messages.
    validation_prompt = (
        "Based on the eligibility analysis already completed, "
        "check ONLY whether all required documents are present "
        "in the transaction details. "
        "Return JSON with: "
        "documents_complete (bool), "
        "missing_documents (list of strings), "
        "validation_decision (APPROVED or NEEDS_MORE_INFO). "
        "No markdown fences. JSON only."
    )

    # Append the validation request to existing message history.
    # Claude sees all prior tool results — no redundant tool calls.
    validation_messages = state["messages"] + [HumanMessage(content=validation_prompt)]

    # llm (not llm_with_tools) — no tools needed for this focused check
    response = llm.invoke(validation_messages)

    import re

    raw = response.content
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
    clean = match.group(1) if match else raw.strip()

    try:
        result = json.loads(clean)
        decision = result.get("validation_decision", "NEEDS_MORE_INFO")
    except (json.JSONDecodeError, AttributeError):
        decision = "NEEDS_MORE_INFO"

    print(f"  [validate] validation_decision={decision}")
    return {
        "branch_taken": "validate",
        "final_outcome": f"MEDIUM_RISK — validation result: {decision}",
        "messages": [response],
    }


# ---------------------------------------------------------------------------
# Branch node: human_review (HIGH risk)
# Same interrupt() pattern from hitl_graph.py — pauses for human decision.
# ---------------------------------------------------------------------------
def human_review(state: AgentState) -> AgentState:
    """Pause for human review of HIGH-risk decisions."""
    last_message = state["messages"][-1]
    decision = interrupt(
        {
            "risk_level": state["risk_level"],
            "agent_recommendation": last_message.content[:300],
            "question": "HIGH-risk procedure. Approve or reject? (approved/rejected)",
        }
    )
    print(f"  [human_review] human decision: {decision}")
    return {
        "branch_taken": "human_review",
        "human_decision": decision,
        "final_outcome": f"HIGH_RISK — human decision: {decision}",
        "messages": [HumanMessage(content=f"Human decision: {decision}")],
    }


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------
graph = StateGraph(AgentState)

graph.add_node("call_llm", call_llm)
graph.add_node("run_tools", tool_node)
graph.add_node("assess_risk", assess_risk)
graph.add_node("auto_approve", auto_approve)
graph.add_node("validate", validate)
graph.add_node("human_review", human_review)

graph.add_edge(START, "call_llm")

graph.add_conditional_edges(
    "call_llm",
    should_continue,
    {"run_tools": "run_tools", "assess_risk": "assess_risk"},
)

graph.add_edge("run_tools", "call_llm")

# Three-way branch — this is the new piece vs hitl_graph.py
graph.add_conditional_edges(
    "assess_risk",
    route_on_risk,
    {
        "low": "auto_approve",
        "medium": "validate",
        "high": "human_review",
    },
)

graph.add_edge("auto_approve", END)
graph.add_edge("validate", END)
graph.add_edge("human_review", END)

checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Helper: run one transaction through the graph
# ---------------------------------------------------------------------------
def run_transaction(transaction: dict, thread_id: str) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    system = SystemMessage(content=SYSTEM_PROMPT)
    user = HumanMessage(
        content="Evaluate this eligibility request:\n"
        + json.dumps(transaction, indent=2)
    )
    return app.invoke({"messages": [system, user]}, config=config)


if __name__ == "__main__":

    # -----------------------------------------------------------------------
    # THREE TRANSACTIONS — one per branch
    # Each shows a different path through the graph.
    # -----------------------------------------------------------------------

    transactions = [
        {
            "label": "LOW risk — Cigna, no prior auth required",
            "thread_id": "tx-low-001",
            "data": {
                "member_id": "MBR-2024-001",  # phi-ok
                "payer_name": "Cigna",
                "service_date": "2026-07-01",
                "service_type": "annual physical",
                "diagnosis_code": "Z00.00",
            },
        },
        {
            "label": "MEDIUM risk — Aetna, prior auth required, standard procedure",
            "thread_id": "tx-medium-001",
            "data": {
                "member_id": "MBR-2024-001",  # phi-ok
                "payer_name": "Aetna",
                "service_date": "2026-07-10",
                "service_type": "physical therapy",
                "diagnosis_code": "M54.5",
            },
        },
        {
            "label": "HIGH risk — Aetna, knee replacement (in high_risk_procedures)",
            "thread_id": "tx-high-001",
            "data": {
                "member_id": "MBR-2024-001",  # phi-ok
                "payer_name": "Aetna",
                "service_date": "2026-07-20",
                "service_type": "knee replacement",
                "diagnosis_code": "M17.11",
                "estimated_cost": 45000,
            },
        },
    ]

    for tx in transactions:
        print("\n" + "=" * 60)
        print(f"Transaction: {tx['label']}")
        print("=" * 60)

        if tx["thread_id"].startswith("tx-high"):
            # HIGH risk — two-phase execution (interrupt + resume)
            print("Graph execution (Phase 1):")
            result = run_transaction(tx["data"], tx["thread_id"])

            print("\nPhase 1 paused — simulating human approval...")
            config = {"configurable": {"thread_id": tx["thread_id"]}}
            result = app.invoke(Command(resume="approved"), config=config)
        else:
            # LOW and MEDIUM — single-phase execution
            print("Graph execution:")
            result = run_transaction(tx["data"], tx["thread_id"])

        print(f"\nBranch taken:  {result.get('branch_taken')}")
        print(f"Risk level:    {result.get('risk_level')}")
        print(f"Final outcome: {result.get('final_outcome')}")
