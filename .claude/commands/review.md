---
description: Review the current diff against a plan — correctness, gaps, and ML pitfalls
argument-hint: [plan file path, or leave blank]
allowed-tools: Bash(git status:*), Bash(git diff:*)
---
## Context
- Status: !`git status --short`
- Uncommitted changes: !`git diff HEAD`

## Your task
Review the diff above as a fresh reviewer — assume you did NOT write this code and judge it on its own terms. This is read-only: do not edit anything.

Plan or goal to check against: $ARGUMENTS
(If that's a file path, read it. If it's blank, infer the intended goal from CLAUDE.md and the diff, and say so.)

Report, concisely and with specific file/line references:
1. Does the change actually accomplish the plan/goal? Note anything missing or out of scope.
2. Correctness bugs.
3. ML-specific pitfalls — data leakage, a bad train/test split, feature/label mismatch, a metric that doesn't match the objective, silent shape errors.
4. The one finding I'd most benefit from understanding — explain the "why" behind it.

End with a short, prioritized list of what to fix first.
