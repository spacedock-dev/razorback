---
id: b1fdqxbnr44efwjybdskqw47
title: harbor-view task identity through scored runs (spider2-dbt + generic)
status: backlog
source: Codex adversarial review of spider2-dbt-source-resolution-and-run-wiring (2026-06-18); cross-cutting follow-up
started:
completed:
verdict:
score:
worktree:
issue:
pr:
mod-block:
auto-approve: false
---

## Problem

Materialized Harbor task views are written under `tasks_root`
(`run_dir/tasks/`, set by `cli/run.py:311`), so each view's
`view_manifest.json` lands at `run_dir/tasks/<view>/view_manifest.json`.
But the SpacedockSolverAgent's task-identity discovery scans a
*different* root — `run_dir/_razorback/task_views/*/view_manifest.json`
(`agents/spacedock_solver.py:340-343`). Nothing bridges the two, and the
spider2-dbt branch sets `trial_name_map = {}`, so a real spider2 scored
run has no identity fallback either. Result: a spider2-dbt run executes
but its `benchmark_kind` / `benchmark_task_id` may not propagate into
the solver freeze identity (and possibly scoring artifacts), undermining
comparable/auditable numbers. This is cross-cutting: the `tasks_root`
path is the run-orchestrator's contract and governs the generic
`kind: harbor` path too, and `materialize_ade_harbor_task_view` has no
production caller — so this looks like unfinished view→identity
integration, not a spider2-local bug. Found by Codex adversarial review
of the `spider2-dbt-source-resolution-and-run-wiring` entity; deferred
here by captain decision so the path-contract change gets its own
plan/test rigor.

`auto-approve: false` — touches the run-orchestrator path contract.

## Acceptance criteria

**AC-1 — A scored spider2-dbt run preserves benchmark task identity end-to-end.**
Verified by: an integration test that runs a fixture spider2-dbt job to
scored artifacts and asserts `summary.json` / `per_trial_outcomes.json`
carry the correct `benchmark_kind=spider2-dbt` and per-task
`benchmark_task_id` (not a collapsed/default identity).

**AC-2 — The solver freeze identity discovery finds materialized view manifests.**
Verified by: a test asserting `SpacedockSolverAgent`'s discovery
(`spacedock_solver.py` `views_root` scan) resolves the view manifests
produced for a spider2-dbt run — i.e. the materialize root and the
discovery root agree (whichever direction the fix takes).

**AC-3 — The generic `kind: harbor` path identity behavior is unchanged or consistently fixed.**
Verified by: the existing `test_translate_harbor_block` suite stays
green, and a test pins that the chosen root reconciliation does not
regress non-spider2 harbor identity.

## Test plan

Integration test driving a fixture spider2-dbt run through scoring;
unit tests on the discovery-root reconciliation; regression on the
generic harbor path. Decide in the plan whether to (a) materialize into
`_razorback/task_views`, (b) make discovery/scoring scan the actual
`tasks_root`, or (c) populate `trial_name_map` — with the trade-off
recorded.

## Out of scope

The spider2-dbt resolution + `--explain` wiring itself (shipped by
`spider2-dbt-source-resolution-and-run-wiring`). The dbt-deps/preflight
parity and the verifier (their own entities).
