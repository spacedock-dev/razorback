---
id: bc1v7zy5raxvgvmjct78d4pa
title: Score strata preserve Harbor task identity
status: backlog
source: 2026-05-23 staff audit — ADE/Spider task-view fallback can pool task identity into benchmark-level strata
started:
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
mod-block:
---

## Problem

For Harbor task-view benchmarks such as ADE-Bench and Spider2-DBT, scoring must
preserve task identity. The staff audit found paths where fallback metadata can
emit `dataset = benchmark_kind` and then reduce by that label, pooling every
task under one benchmark-level stratum. That can hide per-task failures and
produce misleading benchmark summaries.

## Acceptance criteria

**AC-1 — Harbor task views choose task ids as strata.**
When a task-view manifest has `benchmark_task_id`, scoring uses that id as the
default stratum label unless an explicit richer stratum is present.
Verified by: score/load and runs/aggregate tests with ADE and Spider fixtures
produce one stratum per task id.

**AC-2 — DAB keeps dataset/query semantics.**
DAB summaries continue to use dataset/query metadata and batch fan-out behavior.
Verified by: existing DAB score/aggregate tests stay green.

**AC-3 — Reducers do not pool unrelated Harbor tasks.**
`rk score` and `rk runs aggregate` produce task-level rows for mixed completed,
failed, and errored ADE/Spider task-view trials.
Verified by: fixture-based tests assert the JSON and markdown output include
each task id separately.

**AC-4 — Existing run-dir compatibility is explicit.**
Older run dirs without task-view manifests either retain the old fallback with a
warning or fail with a clear message, rather than silently changing identity.
Verified by: compatibility tests cover missing-manifest behavior.
