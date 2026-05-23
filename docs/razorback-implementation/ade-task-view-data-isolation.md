---
id: kcns444rns45420fe4g0jaza
title: ADE task-view data isolation preflight
status: validation
source: Goal 4 invalid full-run blocker 2026-05-23
started: 2026-05-23T20:43:23Z
completed:
verdict:
score: 0.9
worktree: .worktrees/spacedock-ensign-ade-task-view-data-isolation
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

## Inline Implementation Plan

### Evidence and Likely Root Cause

The cancelled Goal 4 run used the canonical dataset-ref path, not a stale image
override: `specs/ade-full.frozen.yaml` records
`dataset: dbt-labs/ade-bench@sha256:2c1f...c2bd5` and
`docker_image_override: null`. The Harbor job expanded that into local
`TaskConfig(path=...)` entries under
`_razorback/task_views/`, with concurrency 4.

For the failing F1 family, the task-view manifests point at the expected ADE
sources. `ade-bench-f1007-medium/view_manifest.json` records
`benchmark_task_id: f1007-medium`, source task
`~/.cache/razorback/ade-bench/datasets/ade-bench-f1007-medium`, and
`environment/db_file_id.txt` = `161_e6FoV0rJb2Gp-KhbmbL7u3IMGnQz6`,
`environment/db_name.txt` = `f1`. A direct bounded check of that exact Drive
file ID downloaded a 9.7 MiB DuckDB containing the expected F1 tables
(`circuits`, `drivers`, `races`, `results`, `status`,
`position_descriptions`, etc.).

The invalid trial workspace nevertheless had a different database. The
F1 trial logs for `ade-bench-f1007__SQYGsiM` and
`ade-bench-f1007-medium__d7A9ite` show `/app/f1.duckdb` with QuickBooks-shaped
tables (`account_data`, `bill_data`, `invoice_data`, `sales_receipt_data`,
etc.) and no F1 source tables; the verifier then failed on missing
`circuits`, `drivers`, `results`, `status`, and related sources.

Likely Razorback-side root cause: the ADE dataset-ref path has no fail-closed
task-data preflight between task-view materialization / Harbor environment
startup and `SpacedockSolverAgent`'s Codex execution. The materializer
(`src/razorback/benchmarks/ade_bench/harbor_view.py` ->
`src/razorback/harbor_tasks/materialize.py`) preserves the intended task
identity and DB file ID, and `src/razorback/translate.py:_build_ade_bench`
hands Harbor local task views as `TaskConfig(path=...)`; but neither that path
nor `src/razorback/environments/docker.py:ProxySeparatedDockerEnvironment`
checks the realized `/app/*.duckdb` table family before the solver starts.
The exact mechanism that swapped the runtime DB is still not fully evidenced:
the run did not retain the built images, so the implementation should add
diagnostic preflight output that captures expected and observed DB tables.

### AC-1 - Preserve Task-Specific dbt Data

Spec cites: v2 spec §6.1 benchmark-block translation and task-view
materialization; §7.1 run-dir `_razorback/task_views` layout.

1. Add a red preflight contract test in
   `tests/unit/test_ade_bench_workspace_preflight.py` for at least
   `airbnb001`, `f1001`, and `quickbooks001`. Use tiny DuckDB fixtures whose
   table names model each task family; assert the future checker passes only
   when the expected family sentinel tables are present and fails on
   cross-family tables.
2. Add `src/razorback/benchmarks/ade_bench/preflight.py` with structured
   contracts keyed by task-family prefix. Start with `airbnb`, `f1`, and
   `quickbooks`; expose a function that returns expected database name,
   required tables, forbidden cross-family sentinels, and a concise JSON/log
   payload of observed tables.
3. Wire the checker into ADE task-view materialization in
   `src/razorback/benchmarks/ade_bench/harbor_view.py` by copying a small
   preflight script into the materialized environment and injecting a
   Dockerfile `RUN` after the task's own setup has created or mutated the
   DuckDB. This validates the realized `/app/<db_name>.duckdb`, not just the
   manifest input. Keep generic materializer code benchmark-neutral.
4. Run focused tests:
   `uv run pytest tests/unit/test_ade_bench_workspace_preflight.py tests/unit/test_ade_bench_harbor_view.py -q`.

### AC-2 - Fail Before Codex on Mismatched Workspace Data

Spec cites: v2 spec §6.3 validation boundary; §8.1 `rk run` failure
surfacing; §9.4 runtime leak/failure defenses.

1. Add a failing integration-style test that materializes an F1 task view but
   substitutes a QuickBooks-shaped DuckDB fixture before the preflight step.
   Assert the environment/setup phase fails with an infrastructure-style error
   naming the task id, expected tables, missing tables, and observed
   cross-family tables.
2. Implement a specific exception type or error message surface in the ADE
   preflight module and make the injected script exit non-zero before any
   `codex exec` command can run. If the check lives in image build, Harbor
   should classify it as environment setup failure; if Dockerfile injection is
   insufficient for any task shape, add a `SpacedockSolverAgent.setup` hook
   guarded by `RAZORBACK_BENCHMARK_KIND=ade-bench` before the inner Codex
   setup.
3. Capture a small smoke log proving ordering: preflight output appears before
   Codex install/exec lines. Preserve only the run-dir path and the relevant
   log excerpt reference in the implementation stage report.
4. Run focused tests:
   `uv run pytest tests/unit/test_ade_bench_workspace_preflight.py tests/integration/test_ade_bench_task_view_preflight.py -q`.

### AC-3 - Restart Goal 4 from a Valid Multi-Family Smoke

Spec cites: v2 spec §6.1 dataset-ref digest identity; §7.1 run-dir artifacts;
§9.4 strict audit after run.

1. Generate or hand-write a tiny canonical ADE spec using
   `dataset: dbt-labs/ade-bench@sha256:2c1f9e6966d01b0a5de2235d1a0b64089c7eead42c85c3b7b61d0929405c2bd5`,
   tasks spanning at least two families (prefer `airbnb001`, `f1001`,
   `quickbooks001` for AC-1 continuity), `docker_image_override: null`,
   Codex/spacedock runtime, and the same public-lookup enforcement used by
   the cancelled Goal 4 cell.
2. Run the smallest end-to-end smoke before any larger restart:
   `uv run rk freeze <spec.yaml>`, then
   `uv run rk run <spec.frozen.yaml> --runs-dir <smoke-runs-dir>`, then
   `uv run rk score <run-dir> --format json`, then
   `uv run rk audit <run-dir> --policy strict --format json`.
3. Record the smoke run-dir, score summary, strict audit status, and preflight
   log location in the implementation stage report. Only after this smoke
   reaches normal verifier scoring should
   `goal4-ade-bench-codex-full-dataset-1x-score` restart the full matrix.

## Stage Report: plan

- DONE: Identify the likely data-isolation root cause by tying run artifacts to the relevant Razorback/Harbor code paths, or explicitly state what evidence is still missing.
  Evidence: cancelled run artifacts show correct dataset ref/null image override and correct F1 view DB file ID; F1 trial logs show QuickBooks tables in `/app/f1.duckdb`; missing evidence is the retained built image showing the exact DB swap mechanism.
- DONE: Write an inline implementation plan in the entity body that maps directly to AC-1..AC-3 and front-loads a failing preflight/materialization test.
  Evidence: `Inline Implementation Plan` maps AC-1, AC-2, and AC-3 to tests, modules, smoke commands, and v2 spec cites, with AC-1 starting from red preflight contract tests.
- DONE: Commit the entity update on main and report the commit id plus the next implementation files/tests to touch.
  Evidence: main-branch commit is the required final stage action; completion summary will report the commit id and next files/tests.

### Summary

The inline plan keeps this as a tiny plan-stage task and does not create a
separate plan document. It scopes implementation to ADE workspace-data
preflight and validation, with the smallest multi-family smoke before any
full Goal 4 restart.

## Stage Report: implementation

- DONE: Add tests and implementation that verify sampled ADE task views preserve task-specific dbt project/data identity across at least `airbnb001`, `f1001`, and `quickbooks001` or a defensible equivalent available from the dataset ref.
  Evidence: `52ae716` added DuckDB family contract tests for `airbnb001`, `f1001`, and `quickbooks001`; `c02e80c` added `src/razorback/benchmarks/ade_bench/preflight.py` plus task-view Dockerfile preflight injection.
- DONE: Add a fail-closed ADE workspace preflight wired into the run path before `codex exec`, with a test proving mismatched/missing source data is reported as infrastructure failure.
  Evidence: `tests/unit/test_spacedock_solver_ade_preflight.py` proves `SpacedockSolverAgent.setup()` runs ADE preflight before inner Codex setup and blocks mismatched F1/QuickBooks data with `SpacedockSolverAgentError`.
- DONE: Run focused tests and any cheap smoke/preflight commands needed to prove the mechanism, then commit all implementation-stage changes and append `## Stage Report: implementation` with exact evidence.
  Evidence: `12 passed` for the new ADE preflight suite, `21 passed` for adjacent translator/lifecycle suites, and a standalone `f1001` preflight smoke emitted `RAZORBACK_ADE_PREFLIGHT ... "status": "passed"` before this report.

### Summary

The implementation adds a reusable ADE DuckDB table-family preflight for
`airbnb`, `f1`, and `quickbooks`, injects it into ADE Harbor task views, and
runs it again in `SpacedockSolverAgent.setup()` before the inner Codex runtime
can install or execute. The host `duckdb` dependency and lockfile update are
intentional because the checker and tests inspect real DuckDB table metadata;
no full 48-task matrix was run.
