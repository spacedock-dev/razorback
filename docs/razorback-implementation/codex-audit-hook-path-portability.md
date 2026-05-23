---
id: w79fcrymsz692phfc72ajxex
title: Codex audit hook paths are portable
status: backlog
source: 2026-05-23 staff audit — audit code hardcodes /home/exedev/.codex hook paths
started:
completed:
verdict:
score: 0.55
worktree:
issue:
pr:
mod-block:
---

## Problem

The audit trace discovery code has Codex hook paths hardcoded under
`/home/exedev/.codex`. That works in this VM but makes the audit surface
environment-specific and brittle for other users or CI.

## Acceptance criteria

**AC-1 — Codex hook paths derive from configuration.**
Audit trace discovery resolves hook paths from `$CODEX_HOME`, run metadata, or
an explicit config field. `/home/exedev` appears only in fixtures or archived
historical docs.
Verified by: unit tests cover custom `CODEX_HOME`, default home expansion, and
missing hook files.

**AC-2 — Existing audit behavior is preserved.**
The same trace files are discovered in this exe.dev VM when `CODEX_HOME` points
at the current Codex home.
Verified by: focused audit discovery tests pass and a fixture audit still
reports the expected scanned paths.

**AC-3 — Failure mode is clear.**
When no hook traces are present, audit reports missing coverage without raising
an unrelated filesystem/path error.
Verified by: negative-path test asserts the warning/coverage state.
