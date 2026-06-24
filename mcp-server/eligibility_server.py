"""
MCP Server — Healthcare Eligibility Tools

Exposes two tools to any MCP-compatible client (Claude Code, Lambda agentic loop):
  - get_member_history      : retrieves member eligibility + prior auth history
  - check_payer_requirements: returns payer-specific prior auth rules

Transport: stdio (for Claude Code local use)
           swap to StreamableHTTP for Lambda/network clients

Session 10 — starts with mock data to validate the MCP structure.
Real DynamoDB calls use asyncio.to_thread() to avoid blocking the event loop.
"""

import asyncio
import os

import boto3
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Server instance
# FastMCP handles: tool/list responses, request routing, protocol framing
# The name appears in Claude Code's tool panel and in logs
# ---------------------------------------------------------------------------
mcp = FastMCP("eligibility-tools")

# ---------------------------------------------------------------------------
# DynamoDB client — created once, reused across tool calls
# Reads profile + region from environment, never hardcoded (CLAUDE.md rule)
# boto3 is synchronous — every call goes through asyncio.to_thread()
# ---------------------------------------------------------------------------
AWS_PROFILE = os.getenv("AWS_PROFILE", "cdk-dev")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
dynamodb = session.resource("dynamodb")

# ---------------------------------------------------------------------------
# Mock data — used when DynamoDB table does not exist yet
# Lets us validate the MCP server structure before deploying AWS resources
# ---------------------------------------------------------------------------
MOCK_MEMBER_HISTORY = {
    "MBR-2024-001": {
        "member_id": "MBR-2024-001",
        "plan": "Aetna PPO",
        "coverage_status": "active",
        "deductible_met": True,
        "prior_auths_approved": 2,
        "last_service_date": "2025-12-01",
        "notes": "Member has history of orthopedic claims",
    },
    "MBR-2024-002": {
        "member_id": "MBR-2024-002",
        "plan": "United HMO",
        "coverage_status": "active",
        "deductible_met": False,
        "prior_auths_approved": 0,
        "last_service_date": "2026-01-15",
        "notes": "No prior auth history",
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
            "Operative report if applicable",
        ],
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


# ---------------------------------------------------------------------------
# Tool 1: get_member_history
#
# The docstring becomes the tool description Claude reads to decide when
# to call this tool. Vague docstring = Claude calls it at the wrong time.
# Type hints become the JSON schema automatically — no inputSchema dict needed.
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_member_history(
    member_id: str,  # phi-ok — parameter name, not real PHI
) -> dict:
    """
    Retrieve eligibility and prior authorization history for a member.

    Use this tool when you need to understand a member's current coverage
    status, deductible position, or prior auth history before making an
    eligibility decision. Always call this before check_payer_requirements.

    Args:
        member_id: The member identifier (format: MBR-YYYY-NNN)  # phi-ok

    Returns:
        Member coverage details: plan, status, deductible, and prior auth history.
        Returns an error dict if member is not found.
    """
    # ------------------------------------------------------------------
    # In production: swap this block for a real DynamoDB call wrapped in
    # asyncio.to_thread() — see get_member_history_dynamo() below for
    # the pattern. Mock data lets us prove the MCP structure first.
    # ------------------------------------------------------------------
    history = MOCK_MEMBER_HISTORY.get(member_id)
    if history:
        return history
    return {
        "error": "member_not_found",
        "member_id": member_id,
        "message": f"No history found for member {member_id}",
    }


# ---------------------------------------------------------------------------
# Tool 2: check_payer_requirements
#
# Separate tool from get_member_history — single responsibility.
# Claude can call both in one turn (it batches them, as you saw in Session 5).
# ---------------------------------------------------------------------------
@mcp.tool()
async def check_payer_requirements(payer_name: str, service_type: str) -> dict:
    """
    Return prior authorization requirements for a specific payer and service type.

    Use this tool to determine whether prior authorization is required,
    what documents must be submitted, and what SLA to expect.
    Call this alongside get_member_history when evaluating an eligibility request.

    Args:
        payer_name: Name of the insurance payer (e.g., 'Aetna', 'United', 'Cigna')
        service_type: Type of medical service being requested (e.g., 'knee surgery')

    Returns:
        Prior auth requirements including required documents and SLA in business days.
    """
    requirements = MOCK_PAYER_REQUIREMENTS.get(payer_name.lower())
    if requirements:
        # Attach the service type so Claude has full context in the response
        return {**requirements, "service_type": service_type}
    return {
        "error": "payer_not_found",
        "payer_name": payer_name,
        "message": f"No requirements found for payer {payer_name}",
    }


# ---------------------------------------------------------------------------
# DynamoDB pattern — shown here for reference, not wired up yet
#
# asyncio.to_thread() runs the synchronous boto3 call in a background thread.
# The event loop stays unblocked — other tool calls can proceed during the wait.
# This is the ONLY safe way to call boto3 from inside async def.
#
# NOTE: This requires a separate MemberHistory table keyed by member_id.
# The EligibilityResults table in the CDK stack is keyed by transaction_id
# (one row per SQS decision) — that is a different access pattern entirely.
# A member history table stores all past claims/prior-auths for one member.
# ---------------------------------------------------------------------------
async def get_member_history_dynamo(
    member_id: str,  # phi-ok — param, not real PHI
) -> dict:
    """Production version — reads from DynamoDB instead of mock data."""
    table_name = os.getenv("MEMBER_HISTORY_TABLE", "MemberHistory")
    table = dynamodb.Table(table_name)

    def _get():
        # Key is member_id, not transaction_id — these are different tables
        return table.get_item(Key={"member_id": member_id}).get("Item", {})

    # asyncio.to_thread: runs _get() in a thread pool, awaits the result
    # without blocking the MCP server's event loop
    item = await asyncio.to_thread(_get)
    if item:
        return item
    return {"error": "member_not_found", "member_id": member_id}


# ---------------------------------------------------------------------------
# Entry point
# mcp.run() starts the server. No transport argument = defaults to stdio,
# which is what Claude Code expects for local MCP servers.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
