#!/usr/bin/env python3
"""
Pre-commit hook (commit-msg stage): enforce commit message format.

Required format:  <CATEGORY>: <description>

Valid categories:
  FEAT      New feature or capability
  FIX       Bug fix
  CHORE     Maintenance, dependencies, tooling
  DOCS      Documentation only
  SECURITY  Security fix or hardening
  REFACTOR  Code restructuring without behaviour change
  TEST      Test additions or changes
  STYLE     Formatting, whitespace (no logic change)

Examples:
  FEAT: add patient eligibility check endpoint
  FIX: handle missing member_id in routing response
  SECURITY: remove hardcoded AWS region from config
  CHORE: update pre-commit hook versions
"""
import re
import sys

VALID_CATEGORIES = [
    "FEAT",
    "FIX",
    "CHORE",
    "DOCS",
    "SECURITY",
    "REFACTOR",
    "TEST",
    "STYLE",
]

# Matches  CATEGORY: <at least one non-space char>
_FORMAT_RE = re.compile(
    r"^(" + "|".join(VALID_CATEGORIES) + r"):\s+\S",
    re.IGNORECASE,
)


def main():
    if len(sys.argv) < 2:
        print("[COMMIT-MSG] No commit message file provided.", file=sys.stderr)
        return 1

    msg_file = sys.argv[1]
    try:
        with open(msg_file, encoding="utf-8") as fh:
            # Strip comment lines (added by git) before checking
            lines = [ln for ln in fh if not ln.startswith("#")]
        msg = "".join(lines).strip()
    except OSError as exc:
        print(f"[COMMIT-MSG] Could not read {msg_file}: {exc}", file=sys.stderr)
        return 1

    if not msg:
        print("[COMMIT-MSG] BLOCKED — commit message is empty.", file=sys.stderr)
        return 1

    first_line = msg.splitlines()[0].strip()

    if _FORMAT_RE.match(first_line):
        return 0

    cats = ", ".join(VALID_CATEGORIES)
    print("[COMMIT-MSG] BLOCKED — invalid commit message format.")
    print(f'  Got:      "{first_line}"')
    print("  Expected: <CATEGORY>: <short description>")
    print(f"  Valid categories: {cats}")
    print("  Example:  FEAT: add patient eligibility check endpoint")
    return 1


if __name__ == "__main__":
    sys.exit(main())
