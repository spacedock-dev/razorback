---
id: sapf12faaz8fcy34s4c3dfb0
title: Spacedock workflow solver invokes first officer
status: implementation
source: Captain directive 2026-05-23 — true Spacedock workflow variant
started: 2026-05-23T21:43:32Z
completed:
verdict:
score: 0.96
worktree: .worktrees/spacedock-ensign-spacedock-workflow-invokes-first-officer
issue:
pr:
mod-block:
---

## Problem

The current `spacedock_solver` path reads a workflow `README.md`, prepends it
to the benchmark task instruction, and delegates to an inner runtime adapter.
It does not actually boot the Spacedock first-officer contract or dispatch
ensigns/workers. Results from that path are therefore structured+freeze runs,
not true Spacedock workflow runs.

## Acceptance criteria

**AC-1 — The true Spacedock workflow variant has an explicit spec surface.**
Verified by: schema/translator tests cover an explicit true-workflow shape
without making existing structured+freeze specs silently change semantics.
The implemented surface may be a new `agent.kind` or an explicit mode field,
but tests must make the naming distinction visible.

**AC-2 — The solver boots the first-officer contract, not just README prose.**
Verified by: unit tests use a fake inner runtime or harness capture to assert
the delegated initial instruction invokes `spacedock:first-officer` or the
packaged first-officer contract with a concrete workflow directory and bounded
benchmark-output objective, and does not merely prepend the README as generic
instructions.

**AC-3 — Runtime feasibility is proven or fail-closed.**
Verified by: a focused smoke or fixture demonstrates the selected runtime can
see the required Spacedock skill/workflow assets and can produce a benchmark
terminal artifact through the FO path; if the Harbor-installed runtime cannot
actually expose first-officer dispatch tools inside a trial, the solver must
fail closed with a clear error instead of reporting a fake Spacedock run.

**AC-4 — Existing structured+freeze behavior remains available.**
Verified by: existing `spacedock_solver` tests still pass, or a replacement
structured+freeze kind/mode is added and examples are migrated without losing
freeze/resume coverage.

## Notes

Coordinate with `direct-codex-minimal-agent-kind` but do not edit
`docs/agent-run-architecture.md` unless necessary to keep it technically
accurate after code changes. That task owns the primary doc update.
