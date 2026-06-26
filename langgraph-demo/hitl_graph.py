"""
LangGraph Human-in-the-Loop Demo — Session 10

Extends eligibility_graph.py with a human review step for HIGH-risk decisions.
Replaces the DynamoDB polling pattern from Session 5 with LangGraph's native
interrupt/resume mechanism.

Two-phase execution:
  Phase 1: Graph runs, hits interrupt() on HIGH-risk → pauses, returns to caller
  Phase 2: Human reviews, calls app.invoke(Command(resume=decision)) → resumes

New concepts vs eligibility_graph.py:
  - MemorySaver   : checkpointer that saves graph state between phases
  - interrupt()   : pauses execution, surfaces context to human
  - Command()     : carries human decision back into the resumed graph
  - thread_id     : identifies a specific run so the resume finds the right state
  - AgentState    : extended with risk_level and human_decision fields

Run: AWS_PROFILE=cdk-dev python langchain-demo/hitl_graph.py
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
# Tools — same as eligibility_graph.py
# ---------------------------------------------------------------------------
MOCK_MEMBER_HISTORY = {
    "MBR-2024-001": {
        "member_id": "MBR-2024-001",  # phi-ok
        "plan": "Aetna PPO",
        "coverage_status": "active",
        "deductible_met": True,
        "prior_auths_approved": 2,
        "notes": "Member has history of orthopedic claims",
    },
}

MOCK_PAYER_REQUIREMENTS = {
    "aetna": {
        "payer": "Aetna",
        "prior_auth_required": True,
        "sla_business_days": 5,
        "required_documents": ["CPT code", "Clinical notes", "Operative report"],
        "high_risk_procedures": [
            "spinal fusion",
            "knee replacement",
            "hip replacement",
        ],
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
        service_type: Medical service being requested (e.g., 'knee replacement')

    Returns:
        Prior auth requirements, required documents, SLA, and high-risk procedures.
    """
    requirements = MOCK_PAYER_REQUIREMENTS.get(payer_name.lower())
    if requirements:
        return {**requirements, "service_type": service_type}
    return {"error": "payer_not_found", "payer_name": payer_name}


tools = [get_member_history, check_payer_requirements]
llm_with_tools = llm.bind_tools(tools)


# ---------------------------------------------------------------------------
# State — extended vs eligibility_graph.py
#
# Two new fields beyond messages:
#   risk_level     : set by assess_risk node, drives routing decision
#   human_decision : set by human_review node after interrupt() resumes
#
# These fields persist in the checkpointer between Phase 1 and Phase 2.
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    risk_level: str  # LOW | MEDIUM | HIGH — set by assess_risk node
    human_decision: str  # approved | rejected — set after interrupt() resumes


# ---------------------------------------------------------------------------
# Node 1: call_llm
# Same pattern as eligibility_graph.py — ask Claude to include risk_level
# in its final JSON response so assess_risk can extract it cleanly.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a healthcare eligibility specialist. "
    "Use the available tools to gather member history and payer requirements. "
    "Return your final answer as a JSON object with these exact keys: "
    "eligible (bool), prior_auth_required (bool), "
    "risk_level (LOW or MEDIUM or HIGH), "
    "recommended_action (string), reasoning (string). "
    "HIGH risk = procedure is in payer's high_risk_procedures list "
    "or estimated cost exceeds $20,000. "
    "No markdown fences. JSON only."
)


def call_llm(state: AgentState) -> AgentState:
    """Call the LLM with current message history."""
    response = llm_with_tools.invoke(state["messages"])
    print(f"  [call_llm] tool_calls={len(response.tool_calls)}")
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Conditional edge: should_continue
# Routes to run_tools if Claude has tool calls, otherwise to assess_risk.
# assess_risk replaces the direct END route from eligibility_graph.py.
# ---------------------------------------------------------------------------
def should_continue(state: AgentState) -> str:
    """Route to run_tools or assess_risk based on whether tools were called."""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "run_tools"
    return "assess_risk"


# ---------------------------------------------------------------------------
# Node 2: ToolNode — unchanged from eligibility_graph.py
# ---------------------------------------------------------------------------
tool_node = ToolNode(tools)


# ---------------------------------------------------------------------------
# Node 3: assess_risk
# Parses Claude's final JSON response to extract risk_level.
# Stores it in state so the conditional edge after this node can route on it.
#
# Session 5 equivalent: you read stopReason and manually checked risk level.
# Here: the graph reads state["risk_level"] — set once, routed automatically.
# ---------------------------------------------------------------------------
def assess_risk(state: AgentState) -> AgentState:
    """Extract risk_level from Claude's final JSON response and store in state."""
    last_message = state["messages"][-1]

    # Strip markdown fences if present — same two-layer defence from CLAUDE.md
    import re

    raw = last_message.content
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
    clean = match.group(1) if match else raw.strip()

    try:
        parsed = json.loads(clean)
        risk = parsed.get("risk_level", "LOW").upper()
    except (json.JSONDecodeError, AttributeError):
        risk = "LOW"  # default safe fallback if parsing fails

    print(f"  [assess_risk] risk_level={risk}")
    return {"risk_level": risk}


# ---------------------------------------------------------------------------
# Conditional edge: route_on_risk
# HIGH risk → human_review (will interrupt)
# LOW / MEDIUM → END (auto-approved)
# ---------------------------------------------------------------------------
def route_on_risk(state: AgentState) -> str:
    """Route HIGH-risk decisions to human review, approve LOW/MEDIUM automatically."""
    if state.get("risk_level") == "HIGH":
        return "human_review"
    return "end"


# ---------------------------------------------------------------------------
# Node 4: human_review
# This is the core of human-in-the-loop.
#
# interrupt() does three things:
#   1. Saves the full graph state to the checkpointer (MemorySaver)
#   2. Pauses execution and returns the interrupt payload to the caller
#   3. Waits — nothing runs until app.invoke(Command(resume=...)) is called
#
# The value passed to interrupt() is what your UI/code shows the reviewer.
# The value returned from interrupt() is whatever the human sent in resume=.
#
# Session 5 equivalent:
#   dynamodb.put_item(status=PENDING_REVIEW)
#   while True: poll DynamoDB every 1 second
#   decision = dynamodb.get_item(status)
# ---------------------------------------------------------------------------
def human_review(state: AgentState) -> AgentState:
    """
    Pause execution for human review of HIGH-risk decision.
    Resumes when caller invokes app.invoke(Command(resume=decision)).
    """
    last_message = state["messages"][-1]

    # Everything passed to interrupt() is surfaced to the reviewer.
    # This is what your UI would display while waiting for human input.
    decision = interrupt(
        {
            "risk_level": state["risk_level"],
            "agent_recommendation": last_message.content,
            "question": "HIGH-risk procedure detected. "
            "Approve or reject? (approved/rejected)",
        }
    )

    # Everything below runs AFTER the human sends Command(resume=decision)
    print(f"  [human_review] human decision received: {decision}")
    return {
        "human_decision": decision,
        "messages": [HumanMessage(content=f"Human reviewer decision: {decision}")],
    }


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------
graph = StateGraph(AgentState)

graph.add_node("call_llm", call_llm)
graph.add_node("run_tools", tool_node)
graph.add_node("assess_risk", assess_risk)
graph.add_node("human_review", human_review)

graph.add_edge(START, "call_llm")

graph.add_conditional_edges(
    "call_llm",
    should_continue,
    {"run_tools": "run_tools", "assess_risk": "assess_risk"},
)

graph.add_edge("run_tools", "call_llm")

graph.add_conditional_edges(
    "assess_risk",
    route_on_risk,
    {"human_review": "human_review", "end": END},
)

graph.add_edge("human_review", END)

# ---------------------------------------------------------------------------
# Compile with MemorySaver checkpointer.
#
# Without checkpointer: interrupt() has nowhere to save state → crash.
# MemorySaver = in-memory dict. Fine for this demo.
# Production: SqliteSaver (local) or PostgresSaver (Lambda + RDS).
#
# recursion_limit replaces MAX_ITERATIONS from Session 5.
# ---------------------------------------------------------------------------
checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)


if __name__ == "__main__":

    # -----------------------------------------------------------------------
    # Demo transaction — knee replacement is in Aetna's high_risk_procedures
    # so Claude should return risk_level=HIGH, triggering human review.
    # -----------------------------------------------------------------------
    transaction = {
        "member_id": "MBR-2024-001",  # phi-ok
        "payer_name": "Aetna",
        "service_date": "2026-07-15",
        "service_type": "knee replacement",
        "diagnosis_code": "M17.11",
        "estimated_cost": 45000,
    }

    # thread_id identifies this specific run.
    # Phase 1 saves state under this ID. Phase 2 loads it using the same ID.
    # In Lambda: use transaction_id from the SQS message as thread_id.
    config = {"configurable": {"thread_id": "tx-MBR-2024-001-001"}}

    print("=" * 60)
    print("LangGraph Human-in-the-Loop — Eligibility Agent")
    print("=" * 60)
    print(f"Transaction: {json.dumps(transaction, indent=2)}\n")

    # -----------------------------------------------------------------------
    # PHASE 1 — Run until interrupt()
    # app.invoke() returns when the graph hits interrupt() in human_review.
    # The return value contains the interrupt payload, not the final result.
    # -----------------------------------------------------------------------
    print("--- PHASE 1: Agent gathering information ---")
    system = SystemMessage(content=SYSTEM_PROMPT)
    user = HumanMessage(
        content="Evaluate this eligibility request:\n"
        + json.dumps(transaction, indent=2)
    )

    phase1_result = app.invoke(
        {"messages": [system, user]},
        config=config,
    )

    # After interrupt(), the last message in state is Claude's recommendation.
    # The graph is paused — human_review node is waiting.
    print("\n--- PHASE 1 complete: graph paused at human_review node ---")
    print(f"Risk level detected: {phase1_result.get('risk_level')}")
    print("\nAgent recommendation surfaced to reviewer:")
    # Find Claude's last substantive message before interrupt
    for msg in reversed(phase1_result["messages"]):
        if hasattr(msg, "content") and msg.content and not msg.tool_calls:
            print(msg.content[:500])
            break

    # -----------------------------------------------------------------------
    # PHASE 2 — Simulate human decision and resume
    # In production: this happens minutes or hours later when the reviewer acts.
    # The graph state was saved to MemorySaver — nothing is lost between phases.
    # -----------------------------------------------------------------------
    human_input = "approved"  # simulating human reviewer decision
    print(f"\n--- PHASE 2: Human reviewer sends decision: '{human_input}' ---")

    # Command(resume=value) carries the human decision into human_review node.
    # The same thread_id tells the checkpointer which saved state to resume.
    phase2_result = app.invoke(
        Command(resume=human_input),
        config=config,
    )

    print("\n--- PHASE 2 complete: graph finished ---")
    print(f"Human decision stored: {phase2_result.get('human_decision')}")
    print(f"Risk level:            {phase2_result.get('risk_level')}")
    print(f"Total messages in state: {len(phase2_result['messages'])}")
