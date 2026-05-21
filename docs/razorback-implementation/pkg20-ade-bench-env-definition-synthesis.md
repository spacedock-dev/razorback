---
id: n6cm8q5h37r7ws39nns0c204
title: PKG-20 — ade-bench env-definition synthesis (materializer Dockerfile/compose gap)
status: plan
source: PKG-19 follow-up — Goal 2 T0 probe FAILED 2026-05-20 (commit cc123ac on spacedock-ensign/goal2-ade-bench-haiku-baseline); harbor 0.6.6 contract surfaced gap
started: 2026-05-21T01:42:40Z
completed:
verdict:
score: 0.85
worktree:
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
