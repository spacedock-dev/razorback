---
id: n6cm8q5h37r7ws39nns0c204
title: PKG-20 — ade-bench env-definition synthesis (materializer Dockerfile/compose gap)
status: validation
source: PKG-19 follow-up — Goal 2 T0 probe FAILED 2026-05-20 (commit cc123ac on spacedock-ensign/goal2-ade-bench-haiku-baseline); harbor 0.6.6 contract surfaced gap
started: 2026-05-21T01:42:40Z
completed:
verdict:
score: 0.85
worktree: .worktrees/spacedock-ensign-pkg20-ade-bench-env-definition-synthesis
issue:
pr:
mod-block:
---

## Problem

PKG-19 closed the data half of the ade-bench bind-mount contract
(`materialize_local_task` synthesizes `task.toml`, `instruction.md`,
and selectively reflects task data via symlinks). It did not close
the **environment-definition** half: harbor 0.6.6's
`DockerEnvironment._validate_definition` requires
`environment/Dockerfile` or `environment/docker-compose.yaml` under
the materialized view-dir, and `materialize_local_task` synthesizes
neither.

ade-bench tasks ship NO per-task `environment/` directory upstream.
Instead, `~/git/ade-bench/shared/defaults/` carries the shared
compose files (`docker-compose.yaml`,
`docker-compose-duckdb-dbt.yaml`,
`docker-compose-snowflake-dbt.yaml`,
`docker-compose-snowflake-dbtf.yaml`). Tasks select among these
variants in their `task.yaml`.

Goal 2's T0 probe (Haiku × airbnb001 × N=1) bailed at Phase 2
(`rk run`) with this gap. T1+ matrix dispatch is blocked until
PKG-20 ships.

## Acceptance criteria

**AC-1 — `materialize_local_task` synthesizes `environment/` per
task.** The view-dir at `cache_root/<task_slug>/environment/`
contains exactly one of `Dockerfile` or `docker-compose.yaml`,
chosen by selecting the appropriate variant from
`<ade_bench_root>/shared/defaults/` based on task.yaml's variant
selector (default to `docker-compose.yaml` when task.yaml does
not name one).
Verified by: a unit test calling `materialize_local_task` against
a sample ade-bench task asserts the file's presence and that the
content matches the selected `shared/defaults/` source byte-for-byte
(symlinked under `materialize_mode="bind"`; copied under
`materialize_mode="copy"`).

**AC-2 — Variant selection matches ade-bench upstream behavior.**
For each compose variant in `shared/defaults/`
(`docker-compose-duckdb-dbt.yaml`, `docker-compose-snowflake-dbt.yaml`,
`docker-compose-snowflake-dbtf.yaml`, plus the default
`docker-compose.yaml`), `materialize_local_task` resolves the variant
that ade-bench upstream would have selected for that task. The
selection rule lives in one place and is testable.
Verified by: a unit test asserts the variant selection against a
known-good ade-bench task × variant mapping (at minimum 1 task per
variant).

**AC-3 — Harbor's `DockerEnvironment._validate_definition` passes.**
A live `rk run` against any ade-bench task through the materialized
view-dir does NOT trip the validator's compose/Dockerfile-missing
error. The same airbnb001 task that failed Goal 2 T0 now reaches
the agent.
Verified by: a re-run of `rk run` on a frozen Goal 2 spec (the
T0-FAILED airbnb001 spec at
`.worktrees/spacedock-ensign-goal2-ade-bench-haiku-baseline/runs/goal2-probe/`
or an equivalent) reaches Phase 3 (agent invocation) without
`_validate_definition` error.

**AC-4 — `exclude_globs` discipline preserved.** The
`solution__*.csv` exclusion already enforced for task data ALSO
applies inside the synthesized `environment/` if any compose
variant references solution files (they currently do not, but the
discipline must not regress).
Verified by: a unit test asserts that even when `exclude_globs`
matches an `environment/` entry, the entry is not reflected.

## Test plan

- **Unit:** `tests/benchmarks/ade_bench/test_tasks.py` adds cases for
  AC-1 (env synthesis), AC-2 (variant selection), AC-4
  (exclusion discipline). Existing PKG-19 tests stay green.
- **Integration:** A new test (or extension of an existing
  PKG-19 integration test) calls `materialize_local_task` against
  airbnb001 + Goal 2's spec shape and asserts harbor's
  `_validate_definition` accepts the view-dir.
- **Acceptance:** `rk run` re-execution of the T0-FAILED airbnb001
  spec (or sibling) reaches Phase 3.

## Out of scope

- Goal 2's matrix dispatch itself — Goal 2 implementation
  resumes against the same worktree after PKG-20 merges.
- Goal 2 plan revisions — the plan at
  `docs/razorback-implementation/plans/goal2-ade-bench-haiku-baseline.md`
  is unchanged; only `materialize_local_task` shifts.
- ade-bench upstream variant-selection logic — PKG-20 mirrors
  upstream's existing behavior; it does not invent new selection
  rules.
- Goal 1's DAB matrix — separate adapter, separate code path.

## Depends on

- PKG-19 (ade-bench data bind-mount) — shipped, this entity extends it
- harbor 0.6.6 `DockerEnvironment._validate_definition` — the
  contract this entity satisfies

## Resume hook

After PKG-20 merges to main, re-dispatch Goal 2's
implementation stage:
1. The Goal 2 worktree at
   `.worktrees/spacedock-ensign-goal2-ade-bench-haiku-baseline`
   still carries the T0 failure stage report (commit cc123ac);
   the implementation ensign reuses the worktree and restarts T0
   against the now-fixed materializer.
2. If T0 passes, the matrix dispatches the remaining 47 cells.

## Plan (inline)

### AC↔Task map

| AC | Task | Files touched | Spec cite |
| --- | --- | --- | --- |
| AC-1 | T1 — synthesize `environment/<compose>` | `src/razorback/benchmarks/ade_bench/tasks.py`; `tests/unit/test_ade_bench_materialize_local_task.py`; `tests/fixtures/ade_bench/fixture_local_task_minimal/shared/defaults/*` | "Acceptance criteria → AC-1" |
| AC-2 | T2 — variant selection rule | same `tasks.py`; new fixtures under `fixture_local_task_minimal/tasks/example001/task.yaml` extended + `fixture_variant_*` slugs | "Acceptance criteria → AC-2" |
| AC-3 | T4 — live `rk run` smoke against airbnb001 | none (validation only) | "Acceptance criteria → AC-3" |
| AC-4 | T3 — `exclude_globs` discipline over `environment/` | same `tasks.py`; same test file | "Acceptance criteria → AC-4" |

### Upstream variant-selection rule (PKG-20 mirror target)

Resolved from `ade_bench/handlers/trial_handler.py` lines 292-314 (`docker_compose_path` property). The rule, applied to one `variant_config` dict (one entry of `task.yaml`'s `variants:` list):

```
if   db_type == "snowflake" and project_type == "dbt-fusion":  docker-compose-snowflake-dbtf.yaml
elif db_type == "snowflake" and project_type == "dbt":         docker-compose-snowflake-dbt.yaml
elif db_type == "duckdb":                                      docker-compose-duckdb-dbt.yaml
else:                                                          docker-compose.yaml
```

Two upstream short-circuits PKG-20 inherits but does NOT need today:
- `task.env_name` (steers to `shared/environments/<env_name>/docker-compose.yaml`) — no ade-bench task currently sets `env_name`; PKG-20 may ignore until a task uses it.
- in-task `<task_dir>/docker-compose.yaml` (task-local override) — no upstream ade-bench task currently ships one; PKG-20 mirrors the override hook but does not need a fixture for it.

### Which `variants[]` entry does PKG-20 select?

Upstream selects via `(db_filter, project_type_filter)` passed to the harness (`harness.py:1383-1391`). Razorback's spec has no equivalent today. The plan resolves this by:

1. Extending `AdeBenchBenchmarkBlock` (in `src/razorback/spec/schema.py`) with two optional fields: `db_type: Literal["duckdb", "snowflake"] | None = None` and `project_type: Literal["dbt", "dbt-fusion"] | None = None`. Both default `None` to preserve PKG-19 callers.
2. When both are set, `materialize_local_task` selects the matching entry from `variants[]`; if no entry matches, raises `ValueError` naming the task + filter pair.
3. When unset (Goal 2's spec today), `materialize_local_task` uses `variants[0]` (the first entry, which by ade-bench convention is the duckdb-dbt baseline). Goal 2's airbnb001 baseline therefore lands on duckdb-dbt without spec changes.
4. When `task.yaml` has no `variants:` block at all (the minimal test fixture), `materialize_local_task` falls through to the default compose (`docker-compose.yaml`).

This keeps the materializer correct for Goal 2 baseline (no spec churn) and gives the matrix driver a single field to set per cell when we later run snowflake variants.

### Task ordering (TDD-ordered, riskiest-contract-first)

**T0 — write the failing AC-1 unit test FIRST.** New test
`test_view_dir_has_environment_compose` in
`tests/unit/test_ade_bench_materialize_local_task.py`: calls
`materialize_local_task` against `fixture_local_task_minimal`
(which has no `variants:`), asserts
`(materialized / "environment" / "docker-compose.yaml").exists()`
and that its content is byte-for-byte the `shared/defaults/
docker-compose.yaml` from a sibling fixture path. Add a sibling
fixture tree `tests/fixtures/ade_bench/fixture_local_task_minimal/
shared/defaults/docker-compose.yaml` (one-line YAML stub: `services: {}`)
to avoid coupling tests to `~/git/ade-bench`. Run; confirm RED.

**T1 — implement AC-1 (env synthesis).** In `materialize_local_task`,
after the existing entry-reflection loop, add an `environment/`
synthesis step:
- Resolve the compose source path: `ade_bench_root / "shared" / "defaults" / <variant_compose>` (variant selection deferred to T2 — for T1, default to `docker-compose.yaml`).
- `mkdir target_dir / "environment"`; reflect the chosen compose file as `target_dir / "environment" / "docker-compose.yaml"` using the same `_reflect` helper (so `materialize_mode="bind"` → symlink; `"copy"` → content copy).
- If `shared/defaults/<chosen>` is missing, raise `FileNotFoundError` with the path + a hint that `ade_bench_root` may be a stale checkout.

Run T0; confirm GREEN.

**T2 — write the failing AC-2 unit test, then implement variant selection.**
- Extend `fixture_local_task_minimal/tasks/example001/task.yaml` to add a `variants:` block with one duckdb-dbt entry; assert the materialized env file equals `docker-compose-duckdb-dbt.yaml`.
- Add a second fixture slug `example002` with snowflake-dbtf as the first variant; assert it picks `docker-compose-snowflake-dbtf.yaml`.
- (Optional but cheap) third slug `example003` with snowflake-dbt → `docker-compose-snowflake-dbt.yaml`.
- Confirm RED.
- Implement: factor a private helper `_select_compose_variant(task_yaml: dict, *, db_type: str | None, project_type: str | None) -> str` that returns the bare filename per the upstream rule above. Call it in `materialize_local_task`; pass the chosen filename into the existing env synthesis from T1. Confirm GREEN.

**T3 — write the failing AC-4 exclusion test, then implement.**
- Add `tests/fixtures/ade_bench/fixture_local_task_minimal/shared/defaults/docker-compose-secret.yaml` (any content); pass `exclude_globs=("environment/docker-compose-secret.yaml",)` AND configure the variant rule to pick `docker-compose-secret.yaml`. Assert the file is NOT reflected.
- Confirm RED.
- Implement: thread `exclude_globs` through the env synthesis path so the same exclusion check the data path uses also gates the env reflection. Confirm GREEN.

**T4 — AC-3 live `rk run` smoke (the riskiest-contract verification).**
After T1-T3 land and unit tests pass, run a one-trial `rk run` against the frozen Goal 2 spec at `.worktrees/spacedock-ensign-goal2-ade-bench-haiku-baseline/runs/goal2-probe/.../spec.frozen.yaml` (or a sibling re-frozen against the new code). Pass criterion: `rk run` proceeds past `_validate_definition` into Phase 3 (agent invocation). The trial does not need to succeed end-to-end — only that the validator no longer raises.

### Risk-ordered note (matches "smallest end-to-end exercise of the riskiest contract first")

The riskiest contract is harbor's `_validate_definition` against the materialized view-dir. The cheapest exercise of it is a unit test that asserts `(view_dir / "environment" / "docker-compose.yaml").exists()` after `materialize_local_task` returns — exactly what T0/T1 ship in minutes. The expensive comprehensive run (`rk run` against airbnb001) lands at T4, after the mechanism is proven.

### Schema-extension note (optional this stage)

`AdeBenchBenchmarkBlock` extension (`db_type` + `project_type` fields) is OPTIONAL for AC-1/AC-3 — Goal 2's spec uses `variants[0]` by default. It becomes load-bearing only when a future spec needs to pin a non-default variant (e.g., a snowflake-dbt matrix cell). Plan keeps the schema extension as a separate sub-task inside T2 so it can be deferred or shipped alongside. If deferred, file a follow-up to track.

### Out of scope (re-confirmed)

- Goal 2's matrix dispatch (resumes after merge).
- Any change to ade-bench upstream.
- DAB / harbor-DAB env synthesis — unrelated adapter.
- Adding `env_name`/`shared/environments` support — no current ade-bench task uses it.

## Stage Report: plan

- DONE: AC-2 variant-selection rule resolves to a concrete mechanism.
  Resolved from `ade_bench/handlers/trial_handler.py:292-314` (`docker_compose_path` property) and cross-checked against 5 task.yaml files (airbnb001/003, analytics_engineering001, asana001, f1001) — all carry an ordered `variants:` list whose entries expose `db_type` + `project_type`; upstream picks ONE entry via a harness-level (db_filter, project_type_filter). PKG-20 mirrors the same `(db_type, project_type) → compose-filename` mapping; selection of WHICH variant entry uses `variants[0]` as the default (matches Goal 2's airbnb001 baseline) and exposes `(db_type, project_type)` filter fields on `AdeBenchBenchmarkBlock` for later matrix cells.
- DONE: Plan size — INLINE per workflow rules.
  4 ACs, single source file (`src/razorback/benchmarks/ade_bench/tasks.py`) + tests + fixtures; no separate `docs/razorback-implementation/plans/pkg20-*.md` created.
- DONE: Plan TDD-orders failing unit test FIRST, then implementation, then variant test, then exclusion test, then live `rk run` smoke at the end.
  T0 (failing AC-1 unit) → T1 (impl AC-1) → T2 (AC-2 RED + impl) → T3 (AC-4 RED + impl) → T4 (AC-3 live `rk run` smoke). Riskiest contract (`_validate_definition`) exercised cheapest in T0; expensive run lands at T4.

### Summary

Plan is inline. The AC-2 mechanism is upstream's `docker_compose_path` rule mirrored verbatim against `shared/defaults/`; variant-entry selection defaults to `variants[0]` (Goal 2 baseline is duckdb-dbt without spec churn), with optional `db_type`/`project_type` filter fields proposed on `AdeBenchBenchmarkBlock` for future matrix cells. Implementation is one helper (`_select_compose_variant`) plus an env-synthesis block appended after the existing entry-reflection loop in `materialize_local_task`. Live `rk run` smoke against the frozen Goal 2 probe spec is the gate to merge, not a unit-test substitute.
