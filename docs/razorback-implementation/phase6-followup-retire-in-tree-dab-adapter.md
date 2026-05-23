---
id: hcds9v8a9k8sgtzzkhn51cge
title: Phase 6 follow-up — retire in-tree DAB adapter
status: backlog
source: phase6-promote-v2-canonical validation — deferred AC-4 DAB sideline
started:
completed:
verdict:
score: 0.82
worktree:
issue:
pr:
mod-block:
---

## Problem

The core Phase 6 merge made active examples use `harbor_dab`, but
`src/razorback/translate.py` still imports `razorback.benchmarks.dab.prepare`.
The in-tree DAB adapter can only be retired after the plugin-backed path
owns all active DAB translation and materialization behavior.

## Acceptance criteria

**AC-1 — Active DAB specs route through the plugin-backed Harbor shape.**
`benchmark.kind: harbor_dab` and the DAB plugin own active DAB task
materialization; active translator code no longer imports
`razorback.benchmarks.dab`.
Verified by: `rg -n "razorback\\.benchmarks\\.dab|benchmarks/dab" src/razorback tests examples packages` returns only `_legacy`, docs, or plugin-package references.

**AC-2 — In-tree DAB adapter is legacy-only.**
`src/razorback/benchmarks/dab/` is moved to `_legacy/benchmarks/dab/`
or deleted after active imports are gone.
Verified by: `test -d src/razorback/benchmarks/dab` exits non-zero.

**AC-3 — DAB score/materialization tests still pass.**
The plugin-backed DAB tests and active example-generator tests pass.
Verified by: `uv run pytest packages/razorback-plugin-dab/tests tests/unit/test_spec_harbor_dab_block.py tests/unit/test_generate_matrix_specs.py tests/unit/test_codex_benchmark_spec_generator.py -q`.

## Notes

Coordinate with `dab-harbor-dataset-definition`; do not duplicate its
dataset-definition work.
