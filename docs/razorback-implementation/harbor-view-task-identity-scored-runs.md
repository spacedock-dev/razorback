---
id: b1fdqxbnr44efwjybdskqw47
title: harbor-view task identity through scored runs (spider2-dbt + generic)
status: done
source: Codex adversarial review of spider2-dbt-source-resolution-and-run-wiring (2026-06-18); cross-cutting follow-up
started: 2026-06-18T15:46:31Z
completed: 2026-06-19T17:05:24Z
verdict: PASSED
score:
worktree:
issue:
pr: "#16"
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

## Stage Report: plan

- DONE: Decide the discovery-root reconciliation direction (a/b/c) and record the trade-off and chosen direction explicitly.
  Chose **(b)** point both consumers at `tasks_root` (`run_dir/tasks`); trade-off table in plan. Root cause: single producer (translate.py:369 → `tasks_root`) vs two consumers scanning a dead `_razorback/task_views` root (spacedock_solver.py:340, aggregate.py:131-132). (a) breaks the orchestrator contract (harbor runs trials from `tasks_root`); (c) is the wrong layer (`trial_name_map` feeds DAB per-query rewiring, not manifest identity).
- DONE: Map each AC 1:1 to TDD checkpoints with file/spec cites (AC-1 / AC-2 / AC-3).
  AC↔task table at plan top: AC-1→Tasks 3+5, AC-2→Tasks 1+2, AC-3→Tasks 1+4. Verified `test_translate_harbor_block.py` baseline + that the generic path materializes no manifest (translate.py:403-404), so AC-3 is structurally safe.
- DONE: Sequence the riskiest contract first — tasks_root↔discovery-root agreement as the smallest end-to-end scored-run exercise.
  Task 5 (integration: fixture spider2-dbt → scored artifacts) is named as the riskiest-contract proof; Tasks 1-3 are its unit scaffolding, Task 4 the AC-3 guardrail.

### Summary

Wrote a STANDARD separate plan doc at `docs/razorback-implementation/plans/harbor-view-task-identity-scored-runs.md`. The linchpin decision is direction (b): a single shared `task_views_root(run_dir) -> run_dir/"tasks"` resolver in `harbor_tasks/manifest.py`, with `spacedock_solver.py:340` and `aggregate.py:132` migrated onto it — the lowest-risk reconciliation that aligns the two readers to where the producer + orchestrator already write, leaving the generic `kind: harbor` path untouched. Confirmed aggregator entry points (`aggregate_summary`, `write_per_trial_outcomes`, both `-> None` writing under `run_dir`) and the ADE fixture exist, so the plan rests on verified anchors rather than guesses. No production code written (plan stage).

## Stage Report: implementation

- DONE: Implement plan direction (b) TDD-first: add a shared `task_views_root(run_dir) -> run_dir/"tasks"` resolver in harbor_tasks/manifest.py and repoint both dead-root consumers — solver freeze-identity discovery (spacedock_solver.py:340) and the scoring aggregator (aggregate.py:131-132) — at it. Follow the 5 TDD tasks in plans/harbor-view-task-identity-scored-runs.md.
  Resolver added (38242bf); solver migrated (587029a, spacedock_solver.py now calls `task_views_root(run_dir)`); aggregator migrated (e18dfdf, `_resolve_stratum_from_task_view_manifest`). All 5 tasks done failing-test-first.
- DONE: Prove AC-1 end-to-end: an integration test running a fixture spider2-dbt job to scored artifacts asserts summary.json / per_trial_outcomes.json carry benchmark_kind=spider2-dbt and the correct per-task benchmark_task_id (not collapsed/default). Prove AC-2: the solver views_root scan resolves the materialized view manifests.
  AC-1: tests/integration/test_spider2_dbt_scored_run_identity.py (63109ea) — fixture producer materializes a view manifest under run_dir/tasks, scoring reads it, summary.json["trials"][0]["stratum"] and per_trial_outcomes.json["trials"][0] both carry benchmark_kind=spider2-dbt + task_id. Negative control verified: reverting the aggregator root makes it fail (KeyError benchmark_kind). AC-2: test_discovery_resolves_manifest_under_tasks_root asserts `_discover_task_identity_from_manifest()` resolves identity from run_dir/tasks.
- DONE: Pin AC-3 regression: the generic kind:harbor path identity is unchanged — test_translate_harbor_block stays green and a test confirms the root reconciliation does not regress non-spider2 harbor identity.
  test_translate_harbor_block.py: all 7 baseline tests green + new test_harbor_local_path_writes_no_view_manifest (e8fa458) pins that harbor-local emits TaskConfig(path=source), materializes no manifest under run_dir/tasks, and trial_name_map stays empty.

### Summary

Implemented direction (b): one shared `task_views_root(run_dir) -> run_dir/"tasks"` resolver in `src/razorback/harbor_tasks/manifest.py`, consumed by both `agents/spacedock_solver.py` (freeze-identity discovery) and `runs/aggregate.py` (scoring stratum), aligning the two dead-root readers with the producer/orchestrator's `tasks_root`. 5 atomic TDD commits; full identity surface is 24/24 green (non-live). Deviation (raised to FO): `tests/unit/test_task_identity_scoring.py` was uncollectable on the base — commit 97b375b (May 23) referenced `razorback.score.load.load_run_dir` that 1f7592d (May 22) had deleted; I removed the dead import and its redundant assertion block (invariance is still proven by the per_trial_outcomes.json outcome_set comparison). One unrelated pre-existing failure remains (`test_codex_runtime_dispatch_constructs_inner_agent` needs `RAZORBACK_SPACEDOCK_PLUGIN_DIR`); confirmed it fails identically on the base commit.

## Stage Report: validation

- DONE: Rerun the identity test surface from a clean checkout of the worktree branch with ACTUAL output, mapping PASS/FAIL to each AC.
  23/24 pass on branch (clean tree). AC-1 PASS (test_spider2_dbt_scored_run_identity.py + test_task_identity_scoring.py — artifacts carry benchmark_kind=spider2-dbt + correct benchmark_task_id), AC-2 PASS (test_discovery_resolves_manifest_under_tasks_root resolves run_dir/tasks manifests), AC-3 PASS (test_translate_harbor_block 8/8 incl. new no-view-manifest regression). Did not trust the implementation self-report — reran every clause.
- DONE: Run superpowers:requesting-code-review against the worktree branch (base main); classify every finding blocking/non-blocking.
  Reviewer found 0 Critical, 0 Important, 2 Minor (both pre-existing/out-of-scope). (a) Resolver: traced producer cli/run.py:311 -> translate.py:369 -> materialize.py:95 writes under run_dir/tasks; both consumers (spacedock_solver.py:341, aggregate.py:133) call task_views_root -> run_dir/tasks; they agree. (b) Dead-import: confirmed razorback.score.load never existed on base, test file was uncollectable on base, removed block used nonexistent load_run_dir so lost no executable coverage (invariance still proven by outcome_set comparison). Verdict: Ready to merge.
- DONE: Write the validation report with PASS/FAIL per AC + exact command/output, code-review findings, gate decision; note pre-existing unrelated failures confirmed on base.
  Report at docs/razorback-implementation/validation/harbor-view-task-identity-scored-runs.md. Pre-existing failure test_codex_runtime_dispatch_constructs_inner_agent (RAZORBACK_SPACEDOCK_PLUGIN_DIR unset) confirmed failing identically on a detached worktree at main (08449cc; src/tests identical to merge-base 773fb5f) — NOT a regression.

### Summary

Independently validated all three ACs from a clean checkout of the branch: 23/24 identity-surface tests pass with the real producer/scoring code paths exercised against committed fixtures; the lone failure is the pre-existing, env-var-gated codex test, confirmed to fail identically on base. Code review surfaced no blocking findings — both Minor findings (a 32-char trial<->view match heuristic and absent backward-compat for the dead _razorback/task_views root) are pre-existing and out of scope. Gate decision: APPROVE to done.
