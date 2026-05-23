---
id: 5zen4f21w0ghy3kqwyggn9pa
title: Make strict audit enumerate manifest trial inventory
status: backlog
source: 2026-05-23 staff audit - strict audit can miss trials with no trace sentinel
started:
completed:
verdict:
score: 0.88
worktree:
issue:
pr:
mod-block:
---

## Problem

`rk audit --policy strict` discovers trials from trace sentinel files. A trial
directory with no `codex-output.jsonl`, `claude-output.jsonl`, or
`traces/manifest.json` can be skipped instead of reported as missing coverage.
That weakens the audit result because absent trace artifacts should be a visible
failure state, not a discovery filter.

## Acceptance criteria

**AC-1 - Manifest trial inventory is authoritative when present.**
Audit enumerates `manifest.json.per_trial_paths` before scanning trace
sentinels.
Verified by: a fixture run with one traced trial and one sentinel-less trial
reports both.

**AC-2 - Missing trace artifacts become coverage_missing.**
A trial listed in the run manifest but missing trace sentinel files is emitted
as `coverage_missing` under strict policy.
Verified by: unit tests assert the audit JSON and exit behavior.

**AC-3 - Filesystem fallback is explicit.**
For old run directories without manifest trial inventory, audit either
enumerates trial directories with a clear fallback warning or fails with a clear
message.
Verified by: compatibility tests cover old-layout run dirs.

**AC-4 - Existing taint checks remain intact.**
Codex and Claude trace scanning still detects tainted content when trace files
exist.
Verified by: existing audit tests stay green and include one positive taint
fixture.
