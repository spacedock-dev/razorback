---
id: jryf2ezvxa5s7zpayf9568zz
title: swe-bench-pro — hydration + task-view materializer wiring smoke
status: plan
source: docs/superpowers/specs/2026-06-24-swe-bench-pro-on-harbor-design.md (E1); spider2-dbt-source-resolution-and-run-wiring as the family-branch reference; captain directive "use harbor's scale-ai/swe-bench-pro"
started: 2026-06-24T03:20:33Z
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

swe-bench-pro tasks ship a repo checkout plus a gold patch and test
patch, and scoring needs per-task strata — capabilities that exist only
on razorback's **task-view materializer** path
(`src/razorback/harbor_tasks/materialize.py:26`), not on the generic
`kind: harbor` pass-through (which hands source dirs straight to
`TaskConfig` at `translate.py:403-419` with no leakage stripping, no env,
no strata). This entity wires swe-bench-pro into `_build_harbor` as a
task-view family (the spider2 `_build_harbor` wiring pattern; ade uses the
same materializer via its own helper): a `kind: harbor` spec with
`dataset: scale-ai/swe-bench-pro@<ref>` resolves source task dirs, routes
each through the **generic** `materialize_harbor_task_view` with
`benchmark_kind="swe-bench-pro"` and
`environment_env={"RAZORBACK_BENCHMARK_KIND": "swe-bench-pro",
"RAZORBACK_BENCHMARK_TASK_ID": <slug>}` (the materializer merges that env
into the view's task.toml — it does not synthesize it, so the branch must
pass it, as `ade_bench`/`spider2_dbt` do), and emits the view dirs as
`TaskConfig(path=...)`. The fully-qualified `<org>/<name>@<ref>` form is
mandatory — `HarborBenchmarkBlock` rejects a bare ref at parse time when
`plugin is None` (`spec/schema.py:197-249`).

swe-bench-pro is git-repo-based (clone repo at a base commit), so harbor
package hydration is the top feasibility risk: spider2-dbt hit a
`git checkout exit-128` blocker (PKG-40) on the same surface. The live
`harbor download` smoke re-checks that blocker but is **non-gating** —
the ACs gate on a deterministic local fixture so the suite stays
network-free.

`auto-approve: false` — touches the spec/translate surface.

## Acceptance criteria

**AC-1 — A `kind: harbor` / `dataset: scale-ai/swe-bench-pro@<ref>` spec resolves to N materialized task-view dirs via a `_build_harbor` swe-bench-pro branch.**
Verified by: an integration test that runs the resolver against a local
`tests/fixtures/swe_bench_pro/` source tree (resolver monkeypatched for
determinism) and asserts each emitted `TaskConfig.path` contains
`task.toml` and a `view_manifest.json` whose `benchmark_kind ==
"swe-bench-pro"` — and that the swe-bench-pro ref takes the new
materializer branch, NOT the generic pass-through (which would emit source
paths with no manifest).

**AC-2 — Each materialized view carries the swe-bench-pro benchmark env.**
Verified by: a test asserting the emitted view's `task.toml` carries
`RAZORBACK_BENCHMARK_KIND=swe-bench-pro` and `RAZORBACK_BENCHMARK_TASK_ID`
(passed by the swe-bench-pro `_build_harbor` branch as `environment_env`
and merged into task.toml by `materialize_harbor_task_view`).

**AC-3 — `rk run --explain --explain-format json` lists the resolved task views.**
Verified by: an in-process `CliRunner` invocation of
`uv run rk run <fixture-spec>.frozen.yaml --explain --explain-format json`
(resolver monkeypatched) exits 0 and the JSON payload's
`prompt.task_paths` array (`cli/run_explain.py` nests it under `prompt`;
see `tests/integration/test_rk_run_spider2_dbt_explain.py`) has one entry
per fixture instance. (Default text `--explain` prints only
a task count + one sample task — `cli/run_explain.py:281-309` — so the
JSON format is the load-bearing surface.)

## Test plan

Unit + integration around the new `_build_harbor` swe-bench-pro branch and
the generic materializer call, fixture-backed and network-free (reuse the
spider2 resolver-monkeypatch + `CliRunner` seams). A documented
**non-gating** live smoke runs `uv run harbor download
scale-ai/swe-bench-pro@<ref>` (exact flags per `harbor download --help`)
and records exit status + task-dir count + the PKG-40-style `git checkout`
blocker status in the validation report. Acceptance command for
validation: `uv run rk run <fixture-spec>.frozen.yaml --explain
--explain-format json`.

## Out of scope

Swe-specific deny-glob hardening (`swe-bench-pro-leakage-audit-deny-globs`
— this entity uses the materializer's default deny-globs), the example
spec + scoring strata (`swe-bench-pro-example-spec-scoring-strata`), and
the full-dataset score (deferred goal entity). A benchmark-specific view
transform (like spider2's dbt wrapper) — the generic
`materialize_harbor_task_view` is sufficient unless a probe proves
otherwise.
