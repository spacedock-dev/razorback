---
id: egz5hdxxfzxxtjfq7zn81100
title: spider2-dbt — source resolution + rk run materialization wiring
status: plan
source: PKG-40 spike (notes/pkg40-spider2-harbor-surface.md) + ade_bench dataset-ref path as reference; captain chose the harbor-package source path
started: 2026-06-18T06:24:22Z
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

`src/razorback/benchmarks/spider2_dbt/{harbor_view,plugin_args}.py`
exist but nothing in the `rk run` path invokes
`materialize_spider2_harbor_task_view`, so a spider2-dbt spec cannot
resolve into Harbor task views. This task wires spider2-dbt in as a
recognized benchmark family: a `kind: harbor` spec with
`dataset: spider2-dbt@1.0` resolves source task dirs (captain-chosen
harbor-package path, mirroring the ade-bench dataset-ref flow in
`translate.py:_resolve_harbor_dataset_tasks`), runs each through the
spider2 view materializer, and emits `TaskConfig(path=view_dir)`
entries. Tests run against a local fixture source tree so the suite
stays deterministic; the live `spider2-dbt@1.0` download is a smoke,
not a gating AC (the PKG-40 spike recorded its git-checkout failure).

`auto-approve: false` — touches the spec/translate surface.

## Acceptance criteria

**AC-1 — A `kind: harbor` / `dataset: spider2-dbt@1.0` spec resolves to N spider2 task-view dirs.**
Verified by: an integration test that runs the resolver against
`tests/fixtures/spider2_dbt/` and asserts each emitted dir contains
`task.toml` and that `rg -l 'gold|expected|golden'` over the view
returns no matches (leakage-clean).

**AC-2 — Each materialized view carries the spider2-dbt benchmark env.**
Verified by: a test asserting the emitted task carries
`RAZORBACK_BENCHMARK_KIND=spider2-dbt` and `RAZORBACK_BENCHMARK_TASK_ID`
(per `materialize_spider2_harbor_task_view`).

**AC-3 — `rk run --explain` on a fixture spider2-dbt spec lists the resolved tasks.**
Verified by: `uv run rk run <fixture-spec>.frozen.yaml --explain` exits 0
and prints one task line per fixture instance.

## Test plan

Unit + integration around the resolver and view emission, fixture-backed.
A documented (non-gating) live smoke re-runs
`uv run harbor download spider2-dbt@1.0 --export` and records exit
status + task-dir count in the validation report (re-checking the
PKG-40 checkout blocker). Acceptance command for validation:
`uv run rk run <fixture-spec>.frozen.yaml --explain`.

## Out of scope

The dbt-deps image layer / preflight (covered by
`spider2-dbt-harbor-view-ade-parity`) and the verifier
(`spider2-dbt-duckdb-match-verifier`). A local raw-dataset generator
fallback if the harbor package stays unusable — deferred unless the
live smoke fails.
