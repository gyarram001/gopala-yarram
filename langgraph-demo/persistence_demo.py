"""
LangGraph Persistence Demo — Session 10

Proves that graph state survives a complete Python process restart.
Two separate process invocations share state via SqliteSaver.

Usage:
    # Terminal 1 — run Phase 1, process exits after interrupt
    AWS_PROFILE=cdk-dev python langchain-demo/persistence_demo.py phase1

    # Terminal 2 — new process, resumes from SqliteSaver
    AWS_PROFILE=cdk-dev python langchain-demo/persistence_demo.py phase2

    # Clean up
    AWS_PROFILE=cdk-dev python langchain-demo/persistence_demo.py clean

New concept vs hitl_graph.py:
    MemorySaver  → SqliteSaver  (state survives process restart)
    RAM          → checkpoints.db file on disk

Production equivalent:
    SqliteSaver  → PostgresSaver / custom DynamoDBSaver
    .db file     → RDS Aurora or DynamoDB table
    Two python   → Two separate Lambda invocations
    thread_id    → transaction_id from SQS message
"""

import json
import os
import sys
from typing import Annotated

import boto3
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

# ---------------------------------------------------------------------------
# SqliteSaver writes to this file.
# The file persists between Python processes — this is what MemorySaver
# cannot do. Lambda 1 writes here, Lambda 2 reads here.
# ---------------------------------------------------------------------------
DB_PATH = "langchain-demo/checkpoints.db"

# thread_id ties Phase 1 and Phase 2 together.
# In Lambda: use transaction_id from the SQS message body.
THREAD_ID = "tx-persist-demo-001"

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
    "MBR-2024-001": {  # phi-ok
        "member_id": "MBR-2024-001",  # phi-ok
        "plan": "Aetna PPO",
        "coverage_status": "active",
        "deductible_met": True,
        "prior_auths_approved": 2,
        "notes": "Member has history of orthopedic claims",
    }
}

MOCK_PAYER_REQUIREMENTS = {
    "aetna": {
        "payer": "Aetna",
        "prior_auth_required": True,
        "sla_business_days": 5,
        "required_documents": ["CPT code", "Clinical notes", "Operative report"],
        "high_risk_procedures": ["knee replacement", "spinal fusion"],
    }
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
        service_type: Medical service being requested

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
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    risk_level: str
    human_decision: str


# ---------------------------------------------------------------------------
# Nodes — same pattern as hitl_graph.py
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a healthcare eligibility specialist. "
    "Use tools to gather member history and payer requirements. "
    "Return your final answer as JSON with: "
    "eligible (bool), prior_auth_required (bool), "
    "risk_level (LOW or MEDIUM or HIGH), "
    "recommended_action (string). "
    "HIGH risk = service is in payer high_risk_procedures list. "
    "No markdown fences. JSON only."
)


def call_llm(state: AgentState) -> AgentState:
    response = llm_with_tools.invoke(state["messages"])
    print(f"  [call_llm] tool_calls={len(response.tool_calls)}")
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if last.tool_calls:
        return "run_tools"
    return "assess_risk"


tool_node = ToolNode(tools)


def assess_risk(state: AgentState) -> AgentState:
    import re

    raw = state["messages"][-1].content
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
    clean = match.group(1) if match else raw.strip()
    try:
        parsed = json.loads(clean)
        risk = parsed.get("risk_level", "LOW").upper()
    except (json.JSONDecodeError, AttributeError):
        risk = "LOW"
    print(f"  [assess_risk] risk_level={risk}")
    return {"risk_level": risk}


def route_on_risk(state: AgentState) -> str:
    return "high" if state.get("risk_level") == "HIGH" else "end"


def human_review(state: AgentState) -> AgentState:
    """
    Pauses here. State already saved to checkpoints.db by SqliteSaver
    before interrupt() returns. The Python process can exit safely —
    Phase 2 will reload this exact state from disk.
    """
    last = state["messages"][-1]
    decision = interrupt(
        {
            "risk_level": state["risk_level"],
            "recommendation": last.content[:400],
            "question": "HIGH-risk procedure. Approve or reject? (approved/rejected)",
        }
    )
    print(f"  [human_review] decision received: {decision}")
    return {
        "human_decision": decision,
        "messages": [HumanMessage(content=f"Human decision: {decision}")],
    }


# ---------------------------------------------------------------------------
# Build graph
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
    {"high": "human_review", "end": END},
)
graph.add_edge("human_review", END)


# ---------------------------------------------------------------------------
# Phase 1 — run until interrupt(), then exit the process
#
# SqliteSaver.from_conn_string() opens (or creates) checkpoints.db.
# Every state transition is written to disk as it happens — not just at
# interrupt(). When interrupt() is called, the saved state is already there.
# Process exits safely. The DB file remains.
# ---------------------------------------------------------------------------
def phase1():
    print("=" * 60)
    print("PHASE 1 — New Python process starting")
    print(f"PID: {os.getpid()}")
    print("=" * 60)

    transaction = {
        "member_id": "MBR-2024-001",  # phi-ok
        "payer_name": "Aetna",
        "service_date": "2026-07-20",
        "service_type": "knee replacement",
        "diagnosis_code": "M17.11",
        "estimated_cost": 45000,
    }

    # SqliteSaver used as a context manager — connection closed cleanly on exit
    with SqliteSaver.from_conn_string(DB_PATH) as checkpointer:
        app = graph.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": THREAD_ID}}

        print("\nGraph execution:")
        result = app.invoke(
            {
                "messages": [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(
                        content="Evaluate this eligibility request:\n"
                        + json.dumps(transaction, indent=2)
                    ),
                ]
            },
            config=config,
        )

    # By this point interrupt() paused the graph and returned the result dict.
    # State is already written to checkpoints.db.
    print(f"\nPhase 1 complete. State saved to: {DB_PATH}")
    print(f"Thread ID: {THREAD_ID}")
    print(f"Risk level: {result.get('risk_level')}")
    print(f"Messages in state: {len(result['messages'])}")
    print("\nProcess exiting. Run phase2 to resume.")


# ---------------------------------------------------------------------------
# Phase 2 — completely new Python process, different PID
#
# Opens the same checkpoints.db. Loads saved state by thread_id.
# Resumes from exactly where Phase 1 paused — no re-running of tools,
# no repeat LLM calls. Just continues the human_review node.
# ---------------------------------------------------------------------------
def phase2():
    print("=" * 60)
    print("PHASE 2 — New Python process starting (simulating Lambda 2)")
    print(f"PID: {os.getpid()}")
    print("=" * 60)

    print(f"\nOpening checkpoints.db — loading state for thread: {THREAD_ID}")

    with SqliteSaver.from_conn_string(DB_PATH) as checkpointer:
        app = graph.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": THREAD_ID}}

        # Verify saved state exists before resuming
        saved = app.get_state(config)
        if not saved.values:
            print("ERROR: No saved state found. Run phase1 first.")
            return

        print("Saved state found.")
        print(f"Messages recovered: {len(saved.values.get('messages', []))}")
        print(f"Risk level recovered: {saved.values.get('risk_level')}")
        print(f"Next node to run: {saved.next}")

        # Simulate human reviewer sending their decision
        human_input = "approved"
        print(f"\nHuman reviewer submits decision: '{human_input}'")

        # Command(resume=) carries the human decision into human_review node.
        # Same thread_id → checkpointer finds the saved state → resumes.
        result = app.invoke(Command(resume=human_input), config=config)

    print("\n--- PHASE 2 complete ---")
    print(f"Human decision: {result.get('human_decision')}")
    print(f"Risk level:     {result.get('risk_level')}")
    print(f"Total messages: {len(result['messages'])}")
    print("\nState successfully persisted and resumed across two processes.")


# ---------------------------------------------------------------------------
# Clean up the SQLite file between demo runs
# ---------------------------------------------------------------------------
def clean():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Deleted {DB_PATH}")
    else:
        print(f"{DB_PATH} not found — nothing to clean")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("phase1", "phase2", "clean"):
        print("Usage: python persistence_demo.py [phase1|phase2|clean]")
        sys.exit(1)

    {"phase1": phase1, "phase2": phase2, "clean": clean}[sys.argv[1]]()
