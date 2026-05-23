---
id: hcds9v8a9k8sgtzzkhn51cge
title: Phase 6 follow-up — retire in-tree DAB adapter
status: implementation
source: phase6-promote-v2-canonical validation — deferred AC-4 DAB sideline
started: 2026-05-23T05:27:23Z
completed:
verdict:
score: 0.82
worktree: .worktrees/spacedock-ensign-phase6-followup-retire-in-tree-dab-adapter
issue:
pr:
mod-block: merge:pr-merge
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

## Stage Report: plan

- DONE: DONE if the plan inventories active imports/usages of `razorback.benchmarks.dab` and identifies the plugin-backed replacement path without duplicating `dab-harbor-dataset-definition`.
  Evidence: plan inventory names active `translate.py`, ADE default-image, schema/parse, and test imports; replacement is existing `harbor_dab` -> `razorback-plugin-dab generate`; dataset-definition scope is explicitly excluded.
- DONE: DONE if the plan gives commit boundaries and TDD checkpoints for removing active translator dependency, moving the in-tree DAB adapter to `_legacy`, and keeping plugin/example tests green.
  Evidence: plan commit boundaries split failing tests, translator cleanup, sideline move, and plugin/example regression checks; Tasks 1-5 include RED tests, focused pytest commands, and sideline commit discipline.
- DONE: DONE if the plan states exact validation commands and coordination risks with DAB dataset-definition work and benchmark scoring.
  Evidence: final validation lists the exact rg, `test -d`, required pytest command, focused guardrails, and full suite; risks call out `dab-harbor-dataset-definition`, scoring reducer/strata work, and ADE default-image coupling.

### Summary

Wrote the standard implementation plan at `docs/razorback-implementation/plans/phase6-followup-retire-in-tree-dab-adapter.md`. The plan maps work AC-by-AC, validates the plugin-backed path before moving the legacy adapter, and keeps dataset-definition and scoring redesigns out of this follow-up.
