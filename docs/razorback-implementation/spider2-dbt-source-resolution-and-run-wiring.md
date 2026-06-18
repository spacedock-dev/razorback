---
id: egz5hdxxfzxxtjfq7zn81100
title: spider2-dbt — source resolution + rk run materialization wiring
status: validation
source: PKG-40 spike (notes/pkg40-spider2-harbor-surface.md) + ade_bench dataset-ref path as reference; captain chose the harbor-package source path
started: 2026-06-18T06:24:22Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-spider2-dbt-source-resolution-and-run-wiring
issue:
pr:
mod-block: merge:pr-merge
auto-approve: false
---

## Problem

`src/razorback/benchmarks/spider2_dbt/{harbor_view,plugin_args}.py`
exist but nothing in the `rk run` path invokes
`materialize_spider2_harbor_task_view`, so a spider2-dbt spec cannot
resolve into Harbor task views. This task wires spider2-dbt in as a
recognized benchmark family: a `kind: harbor` spec with
`dataset: spider2-dbt/spider2-dbt@1.0` resolves source task dirs
(captain-chosen harbor-package path, mirroring the ade-bench dataset-ref
flow in `translate.py:_resolve_harbor_dataset_tasks`), runs each through
the spider2 view materializer, and emits `TaskConfig(path=view_dir)`
entries. The fully-qualified `<org>/<name>@<ref>` form is mandatory:
`HarborBenchmarkBlock` rejects a bare ref at spec-parse time when
`plugin is None` (`spec/schema.py:209-226`), and Harbor's
`PackageReference.parse` raises on `spider2-dbt@1.0` (verified at plan
time) — so the bare ref can never be a valid spec dataset. Tests run
against a local fixture source tree so the suite stays deterministic;
the bare `spider2-dbt@1.0` form appears only as the live
`harbor download` CLI smoke, which is not a gating AC (the PKG-40 spike
recorded its git-checkout failure).

`auto-approve: false` — touches the spec/translate surface.

## Acceptance criteria

**AC-1 — A `kind: harbor` / `dataset: spider2-dbt/spider2-dbt@1.0` spec resolves to N spider2 task-view dirs.**
The fully-qualified ref is the user-facing contract (the bare
`spider2-dbt@1.0` is rejected by the schema validator and is reserved
for the live `harbor download` CLI smoke only).
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

## Stage Report: plan

- DONE: Map each of the 3 ACs to concrete modules with a TDD checkpoint per AC.
  AC↔task map table in the plan; AC-1→T1/T2/T3 (`translate.py:_build_harbor`), AC-2→T4 (`harbor_view.py:31-35`), AC-3→T5/T6 (`cli/run.py:307`, `cli/run_explain.py`). Resolver path = `translate.py:_resolve_harbor_dataset_tasks`; run-time call site = `cli/run.py:311` (`tasks_root=run_dir/"tasks"`); source tree = `tests/fixtures/spider2_dbt/`.
- DONE: Exercise the riskiest mechanism first; plan the live download smoke re-checking the PKG-40 blocker; name the raw-dataset-generator fallback decision.
  T2 (materialize-on-resolve, the load-bearing contract) is implemented+proven before the CLI test (T6) and before the non-gating live smoke (T7). T7 records exit/task-dir count, re-checks the `git checkout` exit-128 blocker, and names defer-vs-build the generator as the captain's call (recommend defer). Fixture-backed tests gate AC-1/2/3 either way.
- DONE: Write the plan as a standard separate doc with an AC-to-task map table and spec/reference cites per step.
  `docs/razorback-implementation/plans/spider2-dbt-source-resolution-and-run-wiring.md` — header, Global Constraints, AC↔task table, per-step §-cites, self-review.

### Summary
Wrote the implementation plan via superpowers:writing-plans. The single wiring point is `_build_harbor` in `translate.py`: detect the spider2-dbt family by `PackageReference.short_name`, then materialize each resolved source dir through `materialize_spider2_harbor_task_view` into the run's `tasks_root`, emitting view dirs as `TaskConfig.path`. Tests reuse the existing resolver-monkeypatch seam for determinism; an `RAZORBACK_SPIDER2_DBT_SOURCE_ROOT` offline seam keeps the `rk run --explain` integration test network-free. Three claims were verified live against the repo (PackageReference parse behavior for short vs qualified refs, the explain payload key path `prompt.task_paths`, and `parse_spec_file`'s location). One open item flagged for the implementer: whether `exclude_tasks`/`n_tasks` should filter on view-dir names or source slugs.

## Feedback Cycles

### Cycle 1 — plan gate REJECTED (2026-06-18)

Codex adversarial review (`--base HEAD~3`) surfaced three design-level
defects; captain rejected the plan gate and chose **option B** (change
the dataset-ref contract). Rework brief for the next plan pass:

1. **[high] Dataset-ref contract (captain decision: B).** Amend the
   user-facing contract to the fully-qualified `spider2-dbt/spider2-dbt@1.0`
   ref **everywhere** — update AC-1 and the Problem § in this entity, and
   the plan's fixture spec / detection prose. The bare `spider2-dbt@1.0`
   form stays only as the `harbor download` CLI smoke (T7). Do NOT add
   schema support for the bare ref (that was option A, declined).
2. **[high] Env-override hijack.** The proposed
   `RAZORBACK_SPIDER2_DBT_SOURCE_ROOT` branch at the top of
   `_resolve_harbor_dataset_tasks` ignores `dataset_ref`, so a leaked env
   var could route any `kind: harbor` dataset to the spider2 fixture
   tree. Remove the production-resolver seam: keep the offline test seam
   as pytest monkeypatch only (preferred), or if an env seam is truly
   needed, guard it with `_is_spider2_dbt_dataset(dataset_ref)` so it
   never captures non-spider2 datasets.
3. **[medium] `exclude_tasks` semantics.** Apply `exclude_tasks` /
   `n_tasks` to **source paths before materialization** (or carry an
   explicit source-task-id map), so selectors stay bound to original
   Harbor task names rather than the post-materialization
   `<benchmark_kind>-<task_slug>` view names. Add a test where
   `exclude_tasks=[source_slug]` proves the excluded spider2 task is not
   emitted. Resolve this in the plan — do not defer it to the implementer.

## Stage Report: plan (cycle 1)

- DONE: Amend the dataset-ref contract to the fully-qualified `spider2-dbt/spider2-dbt@1.0` everywhere (AC-1 + Problem § in the entity, and the plan's fixture spec + detection prose); keep bare `spider2-dbt@1.0` only as the harbor-download CLI smoke. Do NOT add schema support for the bare ref.
  Entity Problem § + AC-1 now use the qualified ref and cite the schema-validator rejection of the bare form (`spec/schema.py:209-226`). Plan goal/architecture/design/fixture-spec (line 553) all use the qualified ref; bare ref kept only in T7 + the live-smoke constraint. Re-verified live: `PackageReference.parse("spider2-dbt@1.0")` raises, `"spider2-dbt/spider2-dbt@1.0"` parses (short_name=="spider2-dbt").
- DONE: Remove the global production-resolver env seam: keep the offline test seam as a pytest monkeypatch only (preferred), or guard any env seam with `_is_spider2_dbt_dataset`.
  `RAZORBACK_SPIDER2_DBT_SOURCE_ROOT` removed entirely; `_resolve_harbor_dataset_tasks` untouched. T6 rewritten to invoke `rk run --explain` in-process via Typer `CliRunner` (pattern: `tests/unit/test_rk_run_harbor_cache_dir.py`) and monkeypatch the resolver. Verified live: `--explain` returns before `_invoke_harbor` (`cli/run.py:335-346`); fixture spec has no `provenance:` so drift checks skip; `_resolve_harbor_dataset_tasks` is a monkeypatchable module attr.
- DONE: Apply `exclude_tasks`/`n_tasks` to source paths BEFORE materialization, decide it in the plan, and add a test proving `exclude_tasks=[source_slug]` drops the excluded spider2 task.
  T2 hoists selectors onto `source_paths` via a new `_apply_task_selectors`, then materializes survivors (spider2 branch returns early; generic path byte-identical). New T3b proves `exclude_tasks=["spider2-fixture-001"]` drops that source and its `spider2-dbt-<slug>` view; pins ordering against regression. Root cause confirmed live: `materialize.py:_view_name` yields `spider2-dbt-<slug>`, so a post-materialize `p.name` filter can never match a source slug.

### Summary
Reworked both the entity (Problem § + AC-1) and the plan doc to resolve the three Codex-surfaced defects per captain option B. Contract is now the fully-qualified `spider2-dbt/spider2-dbt@1.0` everywhere with no schema change; the bare ref is the `harbor download` CLI smoke only. The env-override hijack is eliminated by removing the production-resolver seam and driving the AC-3 `--explain` test in-process via `CliRunner` so a pytest monkeypatch reaches the resolver. `exclude_tasks`/`n_tasks` now filter source paths before materialization (decided in-plan, not deferred), with a dedicated T3b regression test. Every changed contract assumption was re-verified live against the repo (PackageReference.parse, schema validator shape, `_view_name`, the explain short-circuit, and the CliRunner/monkeypatch surface).
