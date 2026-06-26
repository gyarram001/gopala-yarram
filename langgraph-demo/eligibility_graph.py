"""
LangGraph Eligibility Agent — Session 10

Rebuilds the Session 5 agentic loop as a LangGraph graph.
Same behavior, explicit structure. Every manual piece from Session 5
is mapped to a LangGraph equivalent in the comments.

Graph structure:
    START → call_llm → should_continue → run_tools → call_llm (loop)
                              ↓
                             END

Run: AWS_PROFILE=cdk-dev python langchain-demo/eligibility_graph.py
"""

import json
import os
from typing import Annotated

import boto3
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

# ---------------------------------------------------------------------------
# Model setup — same as simple_chain.py
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
# Tools — defined with @tool decorator instead of manual toolSpec dicts.
#
# Session 5 equivalent:
#   tools = [{"toolSpec": {"name": ..., "description": ..., "inputSchema": ...}}]
#
# LangGraph reads the function name, docstring, and type hints automatically
# to build the tool schema. Same load-bearing docstring rule from MCP applies:
# Claude reads this to decide when and how to call the tool.
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
    "MBR-2024-002": {
        "member_id": "MBR-2024-002",  # phi-ok
        "plan": "United HMO",
        "coverage_status": "active",
        "deductible_met": False,
        "prior_auths_approved": 0,
        "notes": "No prior auth history",
    },
}

MOCK_PAYER_REQUIREMENTS = {
    "aetna": {
        "payer": "Aetna",
        "prior_auth_required": True,
        "sla_business_days": 5,
        "required_documents": ["CPT code", "Clinical notes", "Operative report"],
    },
    "united": {
        "payer": "United",
        "prior_auth_required": True,
        "sla_business_days": 7,
        "required_documents": ["CPT code", "Letter of medical necessity"],
    },
    "cigna": {
        "payer": "Cigna",
        "prior_auth_required": False,
        "sla_business_days": 0,
        "required_documents": [],
    },
}


@tool
def get_member_history(member_id: str) -> dict:  # phi-ok
    """
    Retrieve eligibility and prior authorization history for a member.

    Use this tool when you need to understand a member's current coverage
    status, deductible position, or prior auth history before making an
    eligibility decision. Always call this before check_payer_requirements.

    Args:
        member_id: The member identifier (format: MBR-YYYY-NNN)  # phi-ok

    Returns:
        Member coverage details including plan, status, and prior auth history.
    """
    history = MOCK_MEMBER_HISTORY.get(member_id)
    if history:
        return history
    return {"error": "member_not_found", "member_id": member_id}  # phi-ok


@tool
def check_payer_requirements(payer_name: str, service_type: str) -> dict:
    """
    Return prior authorization requirements for a specific payer and service.

    Use this tool to determine whether prior authorization is required,
    what documents must be submitted, and the expected SLA in business days.
    Call this alongside get_member_history when evaluating an eligibility request.

    Args:
        payer_name: Name of the insurance payer (e.g., 'Aetna', 'United', 'Cigna')
        service_type: Type of medical service (e.g., 'knee surgery')

    Returns:
        Prior auth requirements including required documents and SLA.
    """
    requirements = MOCK_PAYER_REQUIREMENTS.get(payer_name.lower())
    if requirements:
        return {**requirements, "service_type": service_type}
    return {"error": "payer_not_found", "payer_name": payer_name}


tools = [get_member_history, check_payer_requirements]

# ---------------------------------------------------------------------------
# bind_tools — replaces toolConfig={"tools": TOOLS} on every converse() call.
#
# Session 5 equivalent:
#   bedrock.converse(toolConfig={"tools": TOOLS_FOR_THIS_LAMBDA}, ...)
#
# Now: bind once, every llm_with_tools.invoke() includes the tool definitions.
# ---------------------------------------------------------------------------
llm_with_tools = llm.bind_tools(tools)


# ---------------------------------------------------------------------------
# State — replaces the `messages` list you managed manually in Session 5.
#
# Session 5 equivalent:
#   messages = []
#   messages.append(claude_response)
#   messages.append(tool_results)
#
# add_messages is a reducer: instead of replacing the list, it appends.
# LangGraph manages this automatically — no manual .append() calls needed.
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# ---------------------------------------------------------------------------
# Node 1: call_llm
# Reads messages from state, calls the model, returns the response.
#
# Session 5 equivalent:
#   response = bedrock.converse(messages=messages, ...)
#   messages.append(response["output"]["message"])
#
# LangGraph equivalent: return {"messages": [response]}
# add_messages handles the append automatically.
# ---------------------------------------------------------------------------
def call_llm(state: AgentState) -> AgentState:
    """Call the LLM with current message history. Maps to bedrock.converse()."""
    response = llm_with_tools.invoke(state["messages"])
    print(
        f"  [call_llm] stopReason={response.response_metadata.get('stopReason')} "
        f"| tool_calls={len(response.tool_calls)}"
    )
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Conditional edge: should_continue
# Inspects the last message — if it has tool calls, route to run_tools.
# If not, route to END.
#
# Session 5 equivalent:
#   if response["stopReason"] == "end_turn": break
#   elif response["stopReason"] == "tool_use": run_tools(...)
#
# The difference: LangGraph makes this routing decision explicit and visible
# as a named function with clear return values.
# ---------------------------------------------------------------------------
def should_continue(state: AgentState) -> str:
    """Route to run_tools if Claude requested tool calls, otherwise end."""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "run_tools"
    return "end"


# ---------------------------------------------------------------------------
# Node 2: ToolNode (built-in)
# Reads tool calls from the last AIMessage, executes them, appends results.
#
# Session 5 equivalent — the entire run_tool() dispatcher you wrote manually:
#   tool_calls = extract_tool_calls(response)
#   for tc in tool_calls:
#       result = run_tool(tc["name"], tc["input"])
#       tool_results.append({...})
#   messages.append(tool_results_message)
#
# ToolNode does all of this in one line. It also runs tool calls in parallel
# by default — the ThreadPoolExecutor pattern from Session 6 is built in.
# ---------------------------------------------------------------------------
tool_node = ToolNode(tools)

# ---------------------------------------------------------------------------
# Build the graph
#
# StateGraph takes the state type — LangGraph validates that every node
# reads and writes fields that exist in AgentState.
# ---------------------------------------------------------------------------
graph = StateGraph(AgentState)

# Add nodes
graph.add_node("call_llm", call_llm)
graph.add_node("run_tools", tool_node)

# Add edges
graph.add_edge(START, "call_llm")  # entry point

graph.add_conditional_edges(  # routing decision
    "call_llm",
    should_continue,
    {
        "run_tools": "run_tools",  # tool call → execute tools
        "end": END,  # no tool call → done
    },
)

graph.add_edge("run_tools", "call_llm")  # after tools → back to LLM

# ---------------------------------------------------------------------------
# Compile — produces a runnable. recursion_limit replaces MAX_ITERATIONS.
#
# Session 5 equivalent:
#   if iteration >= MAX_ITERATIONS: log_warning(...)
#
# LangGraph raises GraphRecursionError automatically at the limit.
# ---------------------------------------------------------------------------
app = graph.compile()


def run_eligibility_graph(transaction: dict) -> str:
    """Run the eligibility transaction through the LangGraph agent."""
    system = SystemMessage(
        content=(
            "You are a healthcare eligibility specialist. "
            "Use the available tools to gather member history and payer requirements "
            "before making a final eligibility decision. "
            "Return your final answer as plain text with: eligible status, "
            "prior auth required, risk level, and recommended action."
        )
    )
    user = HumanMessage(
        content=(
            "Evaluate this eligibility request:\n" + json.dumps(transaction, indent=2)
        )
    )

    result = app.invoke(
        {"messages": [system, user]},
        config={"recursion_limit": 10},
    )

    # Final answer is the last message in state
    return result["messages"][-1].content


if __name__ == "__main__":
    transaction = {
        "member_id": "MBR-2024-001",  # phi-ok
        "payer_name": "Aetna",
        "service_date": "2026-06-25",
        "service_type": "knee surgery",
        "diagnosis_code": "M17.11",
    }

    print("=" * 60)
    print("LangGraph Eligibility Agent")
    print("=" * 60)
    print(f"Transaction: {json.dumps(transaction, indent=2)}\n")
    print("Graph execution:")

    final = run_eligibility_graph(transaction)

    print("\nFinal decision:")
    print(final)
