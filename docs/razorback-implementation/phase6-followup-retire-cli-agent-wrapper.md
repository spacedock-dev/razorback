---
id: yhb5ej5g3gnr71sbgr2cv5jz
title: Phase 6 follow-up — retire standalone CLI agent wrapper
status: backlog
source: phase6-promote-v2-canonical validation — deferred AC-4 standalone CLI sideline
started:
completed:
verdict:
score: 0.78
worktree:
issue:
pr:
mod-block:
---

## Problem

Phase 6 core solver retirement left `src/razorback/agents/claude_cli.py`
active because `src/razorback/agents/_runtime/claude.py` still imports
`ClaudeCliAgent` for telemetry and tool-policy behavior. Retiring the
standalone wrapper needs a predecessor extraction, not a crude file move.

## Acceptance criteria

**AC-1 — Runtime adapter no longer imports the standalone wrapper.**
`src/razorback/agents/_runtime/claude.py` uses Harbor's installed
Claude agent or a v2-named local helper that is not the legacy
`ClaudeCliAgent`.
Verified by: `rg -n "ClaudeCliAgent|agents.claude_cli" src/razorback/agents/_runtime src/razorback/translate.py` returns no active hits.

**AC-2 — Standalone wrapper is legacy-only.**
`src/razorback/agents/claude_cli.py` is moved to `_legacy/agents/`
or deleted after active behavior is preserved elsewhere.
Verified by: `test -e src/razorback/agents/claude_cli.py` exits non-zero and focused runtime adapter tests pass.

**AC-3 — Tool policy and cost/audit behavior survive.**
The Claude runtime adapter still enforces proxy/tool restrictions and
emits the data required by score/audit surfaces.
Verified by: `uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_tools_denied_claude_hook.py -q`.

## Notes

Filed by first officer after auto-approved Phase 6 local merge. This
was a validation-approved follow-up, not human-gated.
