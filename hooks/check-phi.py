#!/usr/bin/env python3
"""
Pre-commit hook: scan staged files for PHI (Protected Health Information) patterns.

Detects:
  - SSN (Social Security Numbers)
  - Member ID formats (healthcare insurance IDs)
  - Date of Birth (DOB) patterns and field markers
  - Patient name field markers

Add a  # phi-ok  comment at the end of a line to suppress a false positive.
"""
import re
import sys

# ---------------------------------------------------------------------------
# PHI pattern definitions  (pattern, human-readable name, re flags)
# ---------------------------------------------------------------------------
_PHI_PATTERNS_RAW = [
    # SSN: 123-45-6789
    (r"\b\d{3}-\d{2}-\d{4}\b", "SSN", 0),
    # Member ID field markers  (member_id =, memberID:, etc.)
    (
        r"\bmember[_\s-]?id\s*[:=]\s*['\"]?[A-Za-z0-9\-]+",
        "Member ID field",
        re.IGNORECASE,
    ),
    # Bare member ID tokens typical in healthcare  AET-889221, UHC304821, CIG557731
    (r"\b(?:AET|UHC|CIG|MED|HUM|BCB|OPT|ANT)[A-Z0-9\-]{4,12}\b", "Member ID token", 0),
    # DOB field markers  (dob =, date_of_birth:, dateOfBirth =, etc.)
    (r"\bdob\s*[:=]\s*\S", "DOB field marker", re.IGNORECASE),
    (r"\bdate[_\s-]?of[_\s-]?birth\s*[:=]\s*\S", "Date of birth field", re.IGNORECASE),
    # Date literals  MM/DD/YYYY or MM-DD-YYYY in a PHI-likely context
    # (preceded by "DOB", "born", "birthday", "birth date" on the same line)
    (
        r"(?:dob|born|birthday|birth\s*date).{0,30}?\b(0[1-9]|1[0-2])[/\-](0[1-9]|[12]\d|3[01])[/\-]\d{4}\b",  # noqa: E501
        "DOB date literal",
        re.IGNORECASE,
    ),
    # Patient / member name markers
    (r"\bpatient[_\s-]?name\s*[:=]\s*['\"]?[A-Z]", "Patient name field", re.IGNORECASE),
]

# Regex for a suppression comment
_PHI_OK = re.compile(r"#\s*phi-ok", re.IGNORECASE)

# Files whose paths match these patterns are skipped entirely
_SKIP_PATH_RE = re.compile(
    r"(?x)"
    r"(^|\/)test[s]?[\/._]"  # tests/ directory or test_ prefix
    r"|_test\.py$"
    r"|\.pre-commit-config\.yaml$"
    r"|requirements.*\.txt$"
    r"|^hooks\/"  # the hook scripts themselves
    r"|\.md$"
)


def _compile_patterns():
    compiled = []
    for pattern, name, flags in _PHI_PATTERNS_RAW:
        compiled.append((re.compile(pattern, flags), name))
    return compiled


def _scan_file(filepath, compiled_patterns):
    findings = []
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as fh:
            for lineno, line in enumerate(fh, 1):
                if _PHI_OK.search(line):
                    continue
                for regex, name in compiled_patterns:
                    if regex.search(line):
                        findings.append((lineno, name, line.rstrip()))
                        break  # one finding per line is enough
    except OSError as exc:
        print(f"  [PHI-CHECK] Could not read {filepath}: {exc}", file=sys.stderr)
    return findings


def main(argv=None):
    files = argv if argv is not None else sys.argv[1:]
    if not files:
        return 0

    compiled = _compile_patterns()
    found_phi = False

    for filepath in files:
        if _SKIP_PATH_RE.search(filepath):
            continue

        findings = _scan_file(filepath, compiled)
        if findings:
            found_phi = True
            print(f"\n[PHI-CHECK] Potential PHI in: {filepath}")
            for lineno, name, line in findings:
                preview = line[:120] + ("..." if len(line) > 120 else "")
                print(f"  Line {lineno:4d} [{name}]: {preview}")

    if found_phi:
        print()
        print("[PHI-CHECK] BLOCKED — remove or mask PHI before committing.")
        print(
            "            Use env vars / secrets manager, or add  # phi-ok  to suppress false positives."  # noqa: E501
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
