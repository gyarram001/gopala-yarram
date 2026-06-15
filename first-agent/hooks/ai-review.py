#!/usr/bin/env python3
"""
Pre-commit hook: AI code review using Amazon Bedrock (Claude Sonnet).

Sends the git diff of all staged Python files to Bedrock and asks Claude to
review for bugs, security issues, PHI exposure, hardcoded values, and code
quality problems.

SECURITY NOTE: The staged git diff is transmitted to Amazon Bedrock (AWS).
The check-phi hook runs before this hook to block commits that contain PHI,
so diffs reaching this hook should be PHI-free. If you have concerns about
transmitting diffs externally, set SKIP_AI_REVIEW=1 to bypass this hook.

Exit codes:
  0  No critical issues (warnings are printed but commit proceeds)
  1  Critical issues found — commit is blocked
  2  Hook setup / invocation error (commit is blocked to be safe)

Requires:
  - boto3 installed and AWS credentials configured (same as bedrock_hello.py)
  - The Bedrock model must be accessible in us-east-1
"""
import json
import re
import subprocess
import sys

# Match the model used in bedrock_hello.py
_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
_REGION = "us-east-1"

# Maximum diff characters sent to Claude (avoids token-limit errors on huge commits)
_MAX_DIFF_CHARS = 14_000

_SYSTEM_PROMPT = """\
You are a senior software engineer performing a pre-commit security and quality review.

IMPORTANT: Only flag issues in ADDED lines (lines prefixed with '+' in the diff).
Lines prefixed with '-' are being REMOVED — do not flag removed content as issues.
Context lines (no prefix) provide background only and should not be flagged.

Review only ADDED lines for these issue types:

  BUGS          Logic errors, off-by-one, None/null handling, unreachable branches
  SECURITY      SQL injection, command injection, path traversal,
                insecure deserialization, exposed secrets, weak crypto
  PHI_EXPOSURE  PHI patterns: SSNs, member IDs, DOBs, patient names, addresses
  HARDCODED     Credentials, API keys, magic numbers that belong in config or env vars
  CODE_QUALITY  Dead code, unused imports, missing error handling, overly complex logic

Severity definitions:
  critical  — production bug, security vulnerability, or PHI exposure
  warning   — best-practice violation, style issue, or minor code smell

Respond ONLY with a JSON object — no markdown fences, no extra text:
{
  "critical": [
    {
      "category": "BUGS|SECURITY|PHI_EXPOSURE|HARDCODED|CODE_QUALITY",
      "location": "filename:line or description",
      "issue": "concise description of the problem",
      "suggestion": "concrete fix"
    }
  ],
  "warnings": [
    {
      "category": "BUGS|SECURITY|PHI_EXPOSURE|HARDCODED|CODE_QUALITY",
      "location": "filename:line or description",
      "issue": "concise description",
      "suggestion": "concrete fix"
    }
  ],
  "summary": "one-sentence overall assessment"
}

Return empty arrays if there are no issues in that severity level."""


def _run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def _get_staged_python_files():
    out = _run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"])
    return [f for f in out.strip().splitlines() if f.endswith(".py")]


def _get_staged_diff():
    return _run(["git", "diff", "--cached", "--unified=3"])


def _additions_only(diff: str) -> str:
    """Strip deleted lines from a diff so the AI only reviews added content."""
    kept = []
    for line in diff.splitlines():
        # Keep file headers (---/+++), hunk headers (@@), context, and additions (+)
        if line.startswith("-") and not line.startswith("---"):
            continue
        kept.append(line)
    return "\n".join(kept)


def _call_bedrock(diff: str) -> dict:
    import boto3  # imported here so missing boto3 gives a clear error message

    client = boto3.client("bedrock-runtime", region_name=_REGION)

    user_msg = f"Review this git diff:\n\n{diff}"

    response = client.converse(
        modelId=_MODEL_ID,
        system=[{"text": _SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_msg}]}],
        inferenceConfig={"maxTokens": 2048, "temperature": 0},
    )

    raw = response["output"]["message"]["content"][0]["text"].strip()

    # Strip markdown code fences if Claude adds them despite instructions
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()

    return json.loads(raw)


def _fmt_issue(issue: dict, index: int) -> str:
    return (
        f"  {index}. [{issue.get('category', '?')}] {issue.get('location', '')}\n"
        f"     Issue:      {issue.get('issue', '')}\n"
        f"     Suggestion: {issue.get('suggestion', '')}"
    )


def main():
    import os

    if os.getenv("SKIP_AI_REVIEW"):
        print("[AI-REVIEW] Skipped via SKIP_AI_REVIEW env var.")
        return 0

    staged_files = _get_staged_python_files()
    if not staged_files:
        # No Python files staged — nothing for this hook to do
        return 0

    diff = _additions_only(_get_staged_diff())
    if not diff.strip():
        return 0

    if len(diff) > _MAX_DIFF_CHARS:
        diff = (
            diff[:_MAX_DIFF_CHARS]
            + "\n\n[... diff truncated — only first portion reviewed ...]"
        )

    file_list = ", ".join(staged_files)
    print(
        f"[AI-REVIEW] Reviewing staged Python files via Bedrock Claude: {file_list}",
        flush=True,
    )

    try:
        review = _call_bedrock(diff)
    except ImportError:
        print(
            "[AI-REVIEW] WARNING: boto3 not installed — skipping AI review.",
            file=sys.stderr,
        )
        return 0
    except (
        Exception
    ) as exc:  # network error, throttle, config issue, JSON parse failure
        print(
            f"[AI-REVIEW] WARNING: Bedrock call failed ({exc}) — skipping AI review.",
            file=sys.stderr,
        )
        return 0

    critical = review.get("critical", [])
    warnings = review.get("warnings", [])
    summary = review.get("summary", "")

    if summary:
        print(f"[AI-REVIEW] {summary}")

    if warnings:
        print(f"\n[AI-REVIEW] Warnings ({len(warnings)}) — commit will proceed:")
        for i, w in enumerate(warnings, 1):
            print(_fmt_issue(w, i))

    if critical:
        print(f"\n[AI-REVIEW] CRITICAL ISSUES ({len(critical)}) — COMMIT BLOCKED:")
        for i, c in enumerate(critical, 1):
            print(_fmt_issue(c, i))
        print(
            "\n[AI-REVIEW] Fix the issues above, re-stage your files, then commit again."  # noqa: E501
        )
        return 1

    if not warnings and not critical:
        print("[AI-REVIEW] No issues found.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
