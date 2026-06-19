---
id: b1fdqxbnr44efwjybdskqw47
title: harbor-view task identity through scored runs (spider2-dbt + generic)
status: validation
source: Codex adversarial review of spider2-dbt-source-resolution-and-run-wiring (2026-06-18); cross-cutting follow-up
started: 2026-06-18T15:46:31Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-harbor-view-task-identity-scored-runs
issue:
pr:
mod-block: merge:pr-merge
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

## Stage Report: plan

- DONE: Decide the discovery-root reconciliation direction (a/b/c) and record the trade-off and chosen direction explicitly.
  Chose **(b)** point both consumers at `tasks_root` (`run_dir/tasks`); trade-off table in plan. Root cause: single producer (translate.py:369 → `tasks_root`) vs two consumers scanning a dead `_razorback/task_views` root (spacedock_solver.py:340, aggregate.py:131-132). (a) breaks the orchestrator contract (harbor runs trials from `tasks_root`); (c) is the wrong layer (`trial_name_map` feeds DAB per-query rewiring, not manifest identity).
- DONE: Map each AC 1:1 to TDD checkpoints with file/spec cites (AC-1 / AC-2 / AC-3).
  AC↔task table at plan top: AC-1→Tasks 3+5, AC-2→Tasks 1+2, AC-3→Tasks 1+4. Verified `test_translate_harbor_block.py` baseline + that the generic path materializes no manifest (translate.py:403-404), so AC-3 is structurally safe.
- DONE: Sequence the riskiest contract first — tasks_root↔discovery-root agreement as the smallest end-to-end scored-run exercise.
  Task 5 (integration: fixture spider2-dbt → scored artifacts) is named as the riskiest-contract proof; Tasks 1-3 are its unit scaffolding, Task 4 the AC-3 guardrail.

### Summary

Wrote a STANDARD separate plan doc at `docs/razorback-implementation/plans/harbor-view-task-identity-scored-runs.md`. The linchpin decision is direction (b): a single shared `task_views_root(run_dir) -> run_dir/"tasks"` resolver in `harbor_tasks/manifest.py`, with `spacedock_solver.py:340` and `aggregate.py:132` migrated onto it — the lowest-risk reconciliation that aligns the two readers to where the producer + orchestrator already write, leaving the generic `kind: harbor` path untouched. Confirmed aggregator entry points (`aggregate_summary`, `write_per_trial_outcomes`, both `-> None` writing under `run_dir`) and the ADE fixture exist, so the plan rests on verified anchors rather than guesses. No production code written (plan stage).
