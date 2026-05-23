---
id: 273s1xhb08me39xcev67vxgq
title: Goal 4 — ade-bench full-dataset Codex 1x score
status: backlog
source: Captain directive 2026-05-21 — "get 1x score for full dataset of DAB and ade-bench, using codex"
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

The second research target is a Codex score over the full ade-bench
task set at N=1. Razorback's canonical ADE-Bench source is now the
Harbor published dataset reference
`dbt-labs/ade-bench@sha256:2c1f9e6966d01b0a5de2235d1a0b64089c7eead42c85c3b7b61d0929405c2bd5`,
not an operator-local `ade_bench_root`. Dataset resolution feeds the
generic task-view materializer, which preserves Razorback's dbt image
override, leakage deny-globs, run-dir manifests, and per-task identity
metadata.

The known-working ADE Harbor setup is not a single image. It has two
roles: Harbor's `main` service runs the Razorback/DAB-style agent image
with Codex or Claude tooling, while ADE's canonical `client` service
contains the dbt project, DuckDB state, and upstream test runner. The
dataset-ref path must preserve that split, or an explicitly equivalent
shape, before this entity can produce a meaningful Codex score.

This is a score-run entity. It must not silently absorb adapter
development work. If the smoke probe finds a missing image, dataset
download, verifier, or Codex-runtime blocker, classify it and file a
separate follow-up instead of folding the fix into this score entity.

## Acceptance criteria

**AC-1 — All ADE-Bench dataset tasks dispatch at N=1 with Codex.**
The matrix resolves the canonical Harbor dataset ref, enumerates every
task package in that dataset, and emits one trial per task with
`agent.kind: spacedock_solver`, `runtime: codex`, `model: gpt-5.5`,
`reasoning_effort: xhigh`, and `trials: 1`.
Verified by: matrix dry-run prints the resolved dataset ref, resolved
task count, and one cell per task slug.

**AC-2 — Harbor task-view materialization is used.**
Specs use `benchmark.kind: ade-bench`, the canonical `dataset:` ref,
`tasks: [...]`, and `batch_mode: per-task`. They do not use
`tasks_root:` except for fixture/dev smoke specs. Materialized task
views include `view_manifest.json` with dataset ref, dataset content
hash, task content hash, transform name, and benchmark task id.
Verified by: a sampled generated spec and materialized task-view
manifest show dataset-ref source selection and task-view metadata.

**AC-3 — ADE dbt solver workflow is selected.**
The score specs use an ADE-specific dbt workflow such as
`examples/solver_workflows/codex-ade-dbt-minimal` or
`examples/solver_workflows/codex-ade-dbt-repair`, not the generic
DAB-style answer-artifact workflow.
Verified by: a sampled frozen spec carries the ADE dbt solver workflow
hash and the workflow text says the graded artifact is the repaired dbt
project state, not a separate answer file.

**AC-4 — Smoke probe gates the full matrix.**
A one-task Codex probe against `airbnb001` freezes and runs far enough
to either complete or classify the first infrastructure blocker. Required
preflight checks cover Codex auth, Docker/compose, dataset download, and
the known-working ADE environment split (`main` = Razorback agent image,
`client` = ADE dbt environment, verifier bridge intact).
Verified by: the probe run-dir or failure log is recorded with the exact
spec path, run command, and blocker classification.

**AC-5 — Runs complete or classify infrastructure failures.**
Each cell either exits 0 with a run-dir containing `result.json`, or
is recorded as a concrete infrastructure failure with the failing
command and log path. Known ADE image/setup/verifier failures must be
reported as such, not treated as Codex score data.
Verified by: dispatch ledger covers every discovered task with one
terminal status per task.

**AC-6 — `rk score` produces the ADE-Bench Codex number.**
The result doc reports per-task pass@1 and an aggregate headline
score for completed ade-bench cells. With N=1, per-task CIs are
named as degenerate rather than over-interpreted.
Verified by: `rk score` JSON artifacts exist for every completed
cell, `summary.json` and `rk score` agree, and the committed summary
document cites the run-dir paths.

**AC-7 — Audit, cost, and provenance are captured.**
Each completed cell has `rk audit --policy strict` output,
`spec.frozen.yaml`, `provenance.yaml`, `manifest.json`,
`summary.json`, and a budget ledger entry.
Verified by: sampled provenance parses the sealed-input fields and
the matrix budget ledger is at or below the declared cap.

## Prerequisite decision

The `1s` follow-up (`runs-aggregate-single-score-reducer`) is not
required before the single-task smoke probe or before launching a
mechanism-only dry-run. It should be completed before treating the full
Goal 4 score as publication-grade. If the captain chooses to run Goal 4
before `1s` lands, the result document must explicitly include a
temporary paired check that `rk score` and each completed run's
`summary.json` agree.

## Probe: 2026-05-23 airbnb001 Codex xhigh

Probe spec:
`/tmp/razorback-goal4-ade-probe-20260523170602/specs/ade-bench/airbnb001.frozen.yaml`.

Command:

```bash
uv run --frozen rk run /tmp/razorback-goal4-ade-probe-20260523170602/specs/ade-bench/airbnb001.frozen.yaml \
  --runs-dir /tmp/razorback-goal4-ade-probe-20260523170602/runs
```

Observed result:

- Dataset ref resolution and task-view materialization work. The run wrote
  `_razorback/task_views/ade-bench-airbnb001/view_manifest.json` with
  `dataset_ref`, `dataset_content_hash`, `task_content_hash`,
  `benchmark_task_id: airbnb001`, and transform
  `ade-bench-harbor-task-view`.
- The selected solver workflow was
  `examples/solver_workflows/codex-ade-dbt-minimal`; the frozen spec carries
  `model: gpt-5.5` and `reasoning_effort: xhigh`.
- The run stopped before any Codex solve. Docker compose tried to pull
  `shared-dbt-duckdb:latest` and failed with:
  `pull access denied for shared-dbt-duckdb, repository does not exist or may require 'docker login'`.
- `summary.json` reported `n_trials_completed: 0`,
  `n_trials_errored: 1`, `stratified_pass_at_1: null`, and
  `RuntimeError`.
- `rk score --format json` on the same run reported
  `stratified_pass_at_1: null`, `stratified_n_completed: 0`,
  `stratified_n_errored: 1`, and `error_reason: RuntimeError`.

Conclusion: `1s` is not the next blocker for running Goal 4. The next
required pre-run condition is to make the Harbor dataset-ref path preserve
the known-working ADE Harbor setup. The probe's task view patched
`[environment].docker_image = "shared-dbt-duckdb:latest"`, so Harbor used
the prebuilt single-`main` path and tried to pull that image before any
Codex solve. That is not the prior working setup where our agent image
runs alongside ADE's canonical `client` service and verifier bridge.

## Depends on

- `pkg26-codex-spacedock-solver-runtime`
- `pkg27-codex-benchmark-solver-workflow`
- `pkg39-benchmark-variant-spec-generation`
- `pkg40-harbor-task-view-materializer`
- `ade-bench-harbor-dataset-ref`
- `pkg23-harbor-shaped-compose-for-ade-bench`
- `pkg27-harbor-verifier-ade-bench-sql-tests-gap`
- A follow-up that ports the PKG-23/PKG-27 ADE `main` + `client`
  environment split to the Harbor dataset-ref task-view path.
- `runs-aggregate-single-score-reducer` for publication-grade scoring,
  or a documented temporary `rk score` versus `summary.json` agreement
  check for provisional scoring.
