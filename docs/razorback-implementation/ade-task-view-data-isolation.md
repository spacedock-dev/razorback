---
id: kcns444rns45420fe4g0jaza
title: ADE task-view data isolation preflight
status: plan
source: Goal 4 invalid full-run blocker 2026-05-23
started: 2026-05-23T20:43:23Z
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
mod-block:
---

## Problem

The first guarded full ADE Codex run was cancelled after 8 completed trials
because an F1 task observed a `/app/f1.duckdb` workspace whose source tables
looked like another dataset family. That makes the score run invalid until the
ADE dataset-ref task-view path proves task-specific project data isolation
across distinct ADE task families before launching expensive agents.

## Acceptance criteria

**AC-1 — ADE task views preserve task-specific dbt data.**
Sampled ADE dataset-ref tasks from at least three distinct families materialize
with the expected task project and database/source tables, without cross-task
contamination.
Verified by: a focused test or smoke command that materializes at least
`airbnb001`, `f1001`, and `quickbooks001` and checks their workspace database
tables against task-family expectations before any agent runs.

**AC-2 — Mismatched ADE workspace data fails before Codex starts.**
The ADE run path detects missing or obviously wrong task source data during
setup/preflight and reports an infrastructure failure rather than burning a
solver trial.
Verified by: a unit/integration test covering the fail-closed preflight path,
plus a captured smoke log where the preflight runs before `codex exec`.

**AC-3 — Goal 4 can restart from a valid multi-family smoke.**
A small ADE Codex/spacedock smoke using the canonical dataset ref, no stale
image override, public-lookup enforcement, and at least two task families
reaches normal verifier scoring with strict audit output.
Verified by: `rk run`, `rk score`, and `rk audit --policy strict` artifacts
from the smoke run, with the run-dir path recorded in the stage report.

## Test plan

Run focused unit/integration tests around ADE task-view materialization and
preflight, then run a small canonical ADE smoke before restarting Goal 4.

## Out of scope

Improving Codex's dbt repair quality or running the full 48-task ADE matrix.
Those remain in `goal4-ade-bench-codex-full-dataset-1x-score` after this
setup blocker is closed.
