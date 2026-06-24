# Pre-commit Hooks

Three custom hooks that enforce code safety and commit hygiene on every
`git commit`. They run in addition to standard pre-commit hooks (Black,
Flake8, detect-private-key, detect-aws-credentials).

## Hooks

| Hook | File | Stage | What it blocks |
|------|------|-------|---------------|
| PHI Pattern Scanner | `check-phi.py` | pre-commit | SSNs (`\d{3}-\d{2}-\d{4}`), real member ID formats (AET-, UHC-, CIG-, etc.), DOB field markers, patient name fields |
| Commit Message Format | `check-commit-msg.py` | commit-msg | Commit messages that don't match `CATEGORY: description`; valid categories: FEAT FIX CHORE DOCS SECURITY REFACTOR TEST STYLE |
| AI Code Review | `ai-review.py` | pre-commit | CRITICAL severity issues (bugs, security, PHI exposure, hardcoded values); warnings are printed but do not block |

## Install

```bash
pip install pre-commit boto3
pre-commit install                        # registers the pre-commit stage hook
pre-commit install --hook-type commit-msg # registers the commit-msg stage hook
```

## Run manually

```bash
pre-commit run --all-files          # run all hooks against every file
pre-commit run check-phi            # PHI scanner only
pre-commit run ai-review            # AI review only (stages Python files first)
```

## PHI false-positive suppression

Add `# phi-ok` at the end of a line to suppress a false positive. The scanner
skips any line containing that comment. Example:

```python
TRANSACTION = {"member_id": "AET-889221"}  # phi-ok — synthetic test ID
```

Files are skipped entirely if their path matches: `tests/`, `_test.py`,
`.pre-commit-config.yaml`, `requirements*.txt`, `hooks/`, `.md` files.

## AI review bypass

Set `SKIP_AI_REVIEW=1` to skip the Bedrock call (useful when AWS credentials
are unavailable or for CI environments without Bedrock access):

```bash
SKIP_AI_REVIEW=1 git commit -m "DOCS: update README"
```

The AI review hook uses `temperature=0` and `maxTokens=2048`. The staged diff
is truncated to 14,000 characters before sending to Bedrock. Only lines
prefixed with `+` (additions) are reviewed — removed lines are stripped from
the diff before the Bedrock call.

## Hook exit codes

| Code | Meaning |
|------|---------|
| 0 | No issues (or no Python files staged for AI review) |
| 1 | Issues found — commit blocked |
| 2 | Hook setup error (AI review only) — commit blocked to be safe |
