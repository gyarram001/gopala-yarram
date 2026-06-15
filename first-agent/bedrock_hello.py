import boto3
import json
import re
import time
from datetime import datetime, timedelta

client = boto3.client("bedrock-runtime", region_name="us-east-1")
MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# ── Routing constants ────────────────────────────────────────────────────────

ROUTING_SYSTEM_PROMPT = """\
You are an eligibility transaction router for a healthcare clearinghouse.
Given a 270 eligibility transaction, decide which payer endpoint it should be routed to.

Routing rules:
- Aetna: payer names like "Aetna", "Aetna Health", "Aetna CVS"
- United: payer names like "United", "UnitedHealthcare", "UHC", "Optum"
- Cigna: payer names like "Cigna", "Cigna Healthcare", "Evernorth"
- Officeally: fallback for any unknown or unrecognized payer

Respond in this exact format:
ROUTE: <payer>
REASON: <one sentence explanation>"""

AETNA_NAMES = {"aetna", "aetna health", "aetna cvs"}
UNITED_NAMES = {"united", "unitedhealthcare", "uhc", "optum"}
CIGNA_NAMES = {"cigna", "cigna healthcare", "evernorth"}

# ── Extraction constants ─────────────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """You are a healthcare data extraction assistant.
Extract structured fields from free-text phone call notes about patient eligibility.

Always respond with valid JSON and nothing else, using this exact schema:
{
  "member_id": "<extracted ID or null>",
  "payer_name": "<insurance company name or null>",
  "service_date": "<YYYY-MM-DD or null>"
}

Rules:
- member_id — extract the alphanumeric member ID. Remove any dashes or spaces.
- payer_name: extract the insurance company name as stated.
- service_date: resolve relative dates like "next Tuesday" from today's date."""

PAYER_KEYWORDS = {
    "aetna": "Aetna",
    "united": "UnitedHealthcare",
    "unitedhealthcare": "UnitedHealthcare",
    "uhc": "UnitedHealthcare",
    "optum": "UnitedHealthcare",
    "cigna": "Cigna",
    "evernorth": "Cigna",
    "bluecross": "BlueCross BlueShield",
    "blue cross": "BlueCross BlueShield",
    "bcbs": "BlueCross BlueShield",
    "humana": "Humana",
    "medicare": "Medicare",
    "medicaid": "Medicaid",
}


# ── Routing functions (from Part 2) ─────────────────────────────────────────


def route_with_claude(transaction: dict) -> tuple[str, str]:
    message = (
        f"Route this 270 eligibility transaction:\n"
        f"  Member ID:    {transaction['member_id']}\n"
        f"  Payer Name:   {transaction['payer_name']}\n"
        f"  Service Date: {transaction['service_date']}"
    )
    response = client.converse(
        modelId=MODEL_ID,
        system=[{"text": ROUTING_SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": message}]}],
        inferenceConfig={"maxTokens": 256, "temperature": 0},
    )
    reply = response["output"]["message"]["content"][0]["text"]
    route = next(
        (
            ln.split("ROUTE:")[-1].strip()
            for ln in reply.splitlines()
            if ln.startswith("ROUTE:")
        ),
        "Unknown",
    )
    reason = next(
        (
            ln.split("REASON:")[-1].strip()
            for ln in reply.splitlines()
            if ln.startswith("REASON:")
        ),
        "",
    )
    return route, reason


def route_with_code(transaction: dict) -> tuple[str, str]:
    name = transaction["payer_name"].lower()
    if name in AETNA_NAMES:
        return "Aetna", "Matched Aetna keyword list"
    if name in UNITED_NAMES:
        return "United", "Matched United keyword list"
    if name in CIGNA_NAMES:
        return "Cigna", "Matched Cigna keyword list"
    return "Officeally", "No keyword match — fallback to Officeally"


# ── Extraction functions (new) ───────────────────────────────────────────────


def extract_with_claude(note: str) -> dict:
    today = datetime.today().strftime("%Y-%m-%d")
    message = (
        f"Today's date is {today}.\n\n"
        f"Extract fields from this phone call note:\n\n{note}"
    )
    response = client.converse(
        modelId=MODEL_ID,
        system=[{"text": EXTRACTION_SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": message}]}],
        inferenceConfig={"maxTokens": 256, "temperature": 0},
    )
    raw = response["output"]["message"]["content"][0]["text"].strip()
    # strip markdown code fences if present (```json ... ``` or ``` ... ```)
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()
    return json.loads(raw)


def extract_with_code(note: str) -> dict:
    text = note.lower()

    # Search for payer member identifier patterns in the input note
    member_id = None  # phi-ok
    m = re.search(r"\b([A-Za-z]{2,4}[-\s]?\d{4,10})\b", note)
    if m:
        member_id = re.sub(r"[-\s]", "", m.group(1)).upper()  # phi-ok
    if not member_id:
        m = re.search(r"member\s+id[^\w]*([A-Za-z0-9\-]+)", text)
        if m:
            member_id = m.group(1).upper()  # phi-ok

    # payer_name: scan for known keywords
    payer_name = None
    for keyword, canonical in PAYER_KEYWORDS.items():
        if keyword in text:
            payer_name = canonical
            break

    # service_date: explicit MM/DD/YYYY or MM-DD-YYYY dates
    service_date = None
    m = re.search(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b", note)
    if m:
        try:
            service_date = datetime.strptime(
                m.group(0).replace("-", "/"), "%m/%d/%Y"
            ).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # relative date: "next <weekday>"
    if not service_date:
        m = re.search(
            r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", text
        )
        if m:
            target = [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ].index(m.group(1))
            today = datetime.today()
            days_ahead = (target - today.weekday() + 7) % 7 or 7
            service_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    return {
        "member_id": member_id,
        "payer_name": payer_name,
        "service_date": service_date,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

NOTES = [
    (
        "Called in for Mrs. Johnson, she's got coverage "
        "through her husband's Aetna plan, "
        "DOB 01/01/1900, checking if her knee surgery next Tuesday is covered, "  # phi-ok  # noqa: E501
        "member ID might be AET-889221"  # phi-ok
    ),
    (
        "Patient called — UnitedHealthcare member, ID UHC304821, wants to verify "  # phi-ok  # noqa: E501
        "coverage for physical therapy starting next Monday"
    ),
    (
        "Spoke with Mr. Rivera. He mentioned Cigna but wasn't sure of the plan type. "
        "His member number is CIG-557731. Appointment is 07/22/2025."  # phi-ok
    ),
]

print("=" * 70)
print("PART 1 — STRUCTURED ROUTING (clean input)")
print("=" * 70)

transactions = [
    {
        "member_id": "AET123456",  # phi-ok
        "payer_name": "Aetna Health",
        "service_date": "2025-07-01",
    },
    {
        "member_id": "UHC789012",  # phi-ok
        "payer_name": "UnitedHealthcare",
        "service_date": "2025-07-02",
    },
    {
        "member_id": "CIG345678",  # phi-ok
        "payer_name": "Cigna Healthcare",
        "service_date": "2025-07-03",
    },
    {
        "member_id": "UNK000001",
        "payer_name": "BlueCross BlueShield",
        "service_date": "2025-07-04",
    },
]

claude_results, code_results = [], []

t0 = time.perf_counter()
for txn in transactions:
    claude_results.append(route_with_claude(txn))
claude_route_elapsed = time.perf_counter() - t0

t0 = time.perf_counter()
for txn in transactions:
    code_results.append(route_with_code(txn))
code_route_elapsed = time.perf_counter() - t0

col = 42
print(f"\n{'CLAUDE (Bedrock)':<{col}}  {'IF/ELSE (Python)'}")
print("-" * (col * 2 + 2))
for txn, (c_route, c_reason), (p_route, p_reason) in zip(
    transactions, claude_results, code_results
):
    print(f"\n  member={txn['member_id']}  payer={txn['payer_name']}")
    print(f"  Route:  {c_route:<{col - 10}}  Route:  {p_route}")
    print(f"  Reason: {c_reason:<{col - 10}}  Reason: {p_reason}")
print()
print("-" * (col * 2 + 2))
print(
    f"  Total time: {claude_route_elapsed:.2f}s{'':<{col - 20}}  Total time: {code_route_elapsed * 1000:.3f}ms"  # noqa: E501
)

print()
print("=" * 70)
print("PART 2 — MESSY EXTRACTION (free-text phone notes)")
print("=" * 70)

for note in NOTES:
    print(f"\nNote: \"{note[:80]}{'...' if len(note) > 80 else ''}\"")

    t0 = time.perf_counter()
    claude_extracted = extract_with_claude(note)
    claude_extract_elapsed = time.perf_counter() - t0

    t0 = time.perf_counter()
    code_extracted = extract_with_code(note)
    code_extract_elapsed = time.perf_counter() - t0

    print(f"\n  {'Field':<14} {'Claude (Bedrock)':<28} {'Regex/Code'}")
    print(f"  {'-'*14} {'-'*27} {'-'*27}")
    for field in ("member_id", "payer_name", "service_date"):
        cv = str(claude_extracted.get(field) or "—")
        pv = str(code_extracted.get(field) or "—")
        print(f"  {field:<14} {cv:<28} {pv}")
    print(
        f"\n  Time: {claude_extract_elapsed:.2f}s (Claude)   {code_extract_elapsed * 1000:.3f}ms (code)"  # noqa: E501
    )
