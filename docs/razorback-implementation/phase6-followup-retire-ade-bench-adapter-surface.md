---
id: bn7bm980ef6egpb95v063y8m
title: Phase 6 follow-up — retire ADE-Bench adapter surface
status: backlog
source: phase6-promote-v2-canonical validation — deferred AC-4 ADE sideline
started:
completed:
verdict:
score: 0.84
worktree:
issue:
pr:
mod-block:
---

## Problem

The Phase 6 validation found active imports from
`src/razorback/benchmarks/ade_bench/`, especially task-view materializer
code used by current ADE smoke paths. Retiring the package requires
splitting reusable Harbor task-view code from the old adapter surface
before any move to `_legacy/`.

## Acceptance criteria

**AC-1 — Reusable task-view code has a v2-named home.**
ADE task-view materialization used by `translate.py` lives outside the
old in-tree adapter package.
Verified by: `rg -n "razorback\\.benchmarks\\.ade_bench" src/razorback/translate.py src/razorback/harbor_tasks src/razorback/benchmarks` shows no active translator dependency on the old package.

**AC-2 — Old ADE adapter surface is legacy-only.**
`src/razorback/benchmarks/ade_bench/` is moved to `_legacy/benchmarks/ade_bench/`
or trimmed to only non-adapter modules with explicit justification.
Verified by: validation report cites every remaining file under
`src/razorback/benchmarks/ade_bench/` or confirms the directory is gone.

**AC-3 — ADE task-view tests still pass.**
Existing ADE Harbor-view tests pass without ground-truth leakage.
Verified by: `uv run pytest tests/unit/test_ade_bench_harbor_view.py tests/unit/test_ade_bench_tasks_loader.py tests/unit/test_ade_bench_materialize_git_task.py -q`.

## Notes

Coordinate with `ade-bench-harbor-dataset-ref` and current ADE benchmark
runs. Do not break the task-view path to satisfy a mechanical sideline.
