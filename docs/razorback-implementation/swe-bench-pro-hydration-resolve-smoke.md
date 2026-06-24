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

## Stage Report: plan

- DONE: Map each of the 3 ACs 1:1 to concrete tasks with exact files + a TDD checkpoint (failing test first).
  AC↔task map table in the plan. AC-1→T1/T2/T3/T4/T4b (`translate.py:_build_harbor` + new `_is_swe_bench_pro_dataset`; fixture tree; manifest+leakage assertions); AC-2→T5 (env on view `task.toml`); AC-3→T6/T7 (fixture frozen spec + in-process `CliRunner --explain --explain-format json`). Each task's Step 1 writes the failing test.
- DONE: Riskiest-contract-first ordering — prove the new `_build_harbor` swe branch + `materialize_harbor_task_view` wiring BEFORE the CLI explain test and BEFORE the non-gating live smoke.
  T2 (family-dispatch branch + GENERIC materializer call with `environment_env` + `benchmark_kind="swe-bench-pro"`) is implemented + proven by T4/T4b/T5 before T7 (CLI explain) and T8 (live `harbor download`, non-gating).
- DONE: Name the fixture, the spec §-cite + code-surface cite per step, and the non-gating live smoke flag-shape.
  Fixture: `tests/fixtures/swe_bench_pro/harbor_task_minimal/{swe-bench-pro-fixture-001,-002}` + `specs/swe-bench-pro-fixture.frozen.yaml`. Every task carries spec/design §-cites + live-confirmed code-surface line cites. T8 confirmed `harbor download` flags live (harbor 0.6.6): `--export` IS the default mode (not a required value), `--cache` the alternative — so T8 uses `--output-dir`+`--overwrite`.
- DONE: Honor the three hard-won precision points.
  (1) env passed BY THE BRANCH as `environment_env`, MERGED by the materializer (never synthesized) — Global Constraints + design decision 2 + T2/T5. (2) explain assertion is nested `payload["prompt"]["task_paths"]` — T7 + cites `run_explain.py:254`+`:52`. (3) only spider2 has a `_build_harbor` branch today; ade uses the same materializer via its own helper; this plan ADDS the swe branch (generic materializer, no wrapper) — Architecture + design decision 3.
- DONE: Self-review for placeholders/contradictions.
  Self-Review § run: spec coverage, ordering, precision points, placeholder scan, type consistency, and 7 plan-time live/read verifications all recorded.

### Summary
Wrote a STANDARD separate plan at `docs/razorback-implementation/plans/swe-bench-pro-hydration-resolve-smoke.md` via superpowers:writing-plans. The single wiring point is `_build_harbor` in `translate.py`: the existing spider2-only branch (`translate.py:361-401`) is generalized into a small family dispatch so swe-bench-pro routes each resolved source dir through the GENERIC `materialize_harbor_task_view` (NOT a benchmark-specific wrapper, per the design Architecture decision), passing `benchmark_kind="swe-bench-pro"` + `environment_env={RAZORBACK_BENCHMARK_KIND, RAZORBACK_BENCHMARK_TASK_ID}`; the materializer merges that env into the view `task.toml` and writes `view_manifest.json`. Filter-before-materialize and the no-production-env-seam discipline are inherited from the merged spider2 cycle-1 fixes. Tests reuse the spider2 resolver-monkeypatch + in-process `CliRunner` seams; the suite is network-free. Default deny-globs only (swe-specific hardening is E2). Two open decisions flagged for the captain.

### Open decisions for the captain
1. **Exact `@<ref>` to pin** for `scale-ai/swe-bench-pro`. The fixture spec uses `@latest` (schema-valid, sufficient for the offline AC-3 gate since the resolver is monkeypatched). The live smoke (T8) and the E3 example spec need a real reproducible ref — recommend pinning a concrete published ref before validation runs T8, or confirm `@latest` is acceptable for the smoke.
2. **Fixture realism.** The minimal fixture is `task.toml` + `instruction.md` + `environment/Dockerfile` + a planted `solution/` deny-path file — no real git-repo checkout / gold patch / test patch / FAIL_TO_PASS (those drive E2 + the hydration concern, both out of scope). Sufficient to gate AC-1/2/3; flag in case a more repo-shaped fixture is wanted before E2.
