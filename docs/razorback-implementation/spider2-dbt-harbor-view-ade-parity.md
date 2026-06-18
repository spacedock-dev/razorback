---
id: nygs3pzdz4dx5hzwn6dsm0qa
title: spider2-dbt — harbor_view dbt+DuckDB parity with ade-bench
status: plan
source: ade_bench/harbor_view.py + ade_bench/preflight.py as reference; spider2-dbt is a dbt+DuckDB benchmark like ade-bench
started: 2026-06-18T08:49:13Z
completed:
verdict:
score:
worktree:
issue:
pr:
mod-block:
---

## Problem

`materialize_spider2_harbor_task_view` is minimal — it applies
deny-globs but skips the dbt+DuckDB harness work ade-bench already
solved. spider2-dbt tasks are dbt projects on DuckDB, so the view must
install declared dbt packages at image-build time, validate the source
`.duckdb` before agent runtime, and reuse preinstalled packages at
verify time (no registry access mid-verify). This task ports the
ade-bench patterns (`_ensure_dbt_deps_image_layer`,
`_ensure_workspace_preflight_image_layer`,
`_ensure_dbt_deps_test_setup_uses_preinstalled_packages`) into the
spider2 view + a new `spider2_dbt/preflight.py`.

## Acceptance criteria

**AC-1 — Views with a `packages.yml` get a dbt-deps image layer.**
Verified by: a test (mirroring `test_ade_bench_harbor_view`) asserting
the dbt-deps marker + `dbt deps` line appear in the view's
`environment/Dockerfile` when `packages.yml` is present, and are absent
when it is not.

**AC-2 — A preflight validates the source DuckDB before agent runtime.**
Verified by: `tests/unit/test_spider2_dbt_workspace_preflight.py`
asserting `spider2_dbt/preflight.py` passes on a present/readable
`.duckdb` and fails with a named error on a missing/corrupt one.

**AC-3 — The agent view excludes gold/solution paths.**
Verified by: a test asserting `gold/**`, `expected/**`, `golden/**`,
and the shared solution deny-globs are absent from the materialized
view (extends the existing `SPIDER2_DBT_DENY_GLOBS`).

## Test plan

Unit tests mirroring `tests/unit/test_ade_bench_harbor_view.py` and
`test_ade_bench_workspace_preflight.py`, against a
`tests/fixtures/spider2_dbt/` dbt task with a `packages.yml` and a
small `.duckdb`. Validation acceptance command: `uv run pytest -k spider2_dbt`.

## Out of scope

Source resolution / run wiring (`spider2-dbt-source-resolution-and-run-wiring`)
and the `duckdb_match` verifier (`spider2-dbt-duckdb-match-verifier`).
Building/pulling a real shared dbt-duckdb image — manifests record the
authored tag and leave the digest null when unresolved (per PKG-40).

## Stage Report: plan

- DONE: Map the 3 ACs to concrete modules with a TDD checkpoint each
  AC↔task table in `plans/spider2-dbt-harbor-view-ade-parity.md`: AC-2→`spider2_dbt/preflight.py` (Task 1), AC-1→`_ensure_dbt_deps_image_layer` (Task 2), AC-2 image-side→`_ensure_workspace_preflight_image_layer` (Task 3), AC-3→`SPIDER2_DBT_DENY_GLOBS` lock (Task 4). Each task names the ade_bench reference ported and a failing-test-first checkpoint.
- DONE: Name exactly which ade_bench patterns port over and what differs for spider2
  Per-task "Port from"/"What differs" lines with verified cites: `ade_bench/preflight.py:23,77,97-101,199,249,266`; `ade_bench/harbor_view.py:20,62,69,76,92,116,140,149,279`. Key divergence pinned: spider2 uses `dbt_project/packages.yml` (not ade-bench `project/…`); no family contracts; db-metadata/gdown layer not ported.
- DONE: Define the image/workdir contract for spider2-dbt task views
  "Image/workdir contract" § (Task 0): dbt project root = `/app`, agent-produced DuckDB = `/app/<db_name>.duckdb`, preflight script at `/tmp/razorback_spider2_preflight.py`. Marked as the stable invariant r5 (`spider2-dbt-duckdb-match-verifier`) depends on.
- DONE: Write a standard separate plan doc with an AC-to-task map and cites to the ade_bench reference modules; keep generic materializer + non-spider2 behavior unchanged
  `docs/razorback-implementation/plans/spider2-dbt-harbor-view-ade-parity.md` written. Explicit "Build order & rationale" notes `harbor_tasks/materialize.py` and `harbor_tasks/leakage.py` are NOT modified; all spider2 behavior added under `benchmarks/spider2_dbt/`.

### Summary

Produced a separate plan doc (standard flow, per the FO dispatch) mapping AC-1/AC-2/AC-3 to four code tasks plus a Task-0 written contract. The riskiest surface — the `/app` + `/app/<db_name>.duckdb` image/workdir contract the r5 verifier depends on — is pinned first as prose; the riskiest mechanism (AC-2 preflight's real DuckDB open / fail-closed) is built first with a real `duckdb.connect` round-trip test. All ade_bench reference cites were verified against the source files. AC-3 is noted as mostly already satisfied (deny-globs present at `spider2_dbt/harbor_view.py:10-21`), so its task is a locking test. Key spider2 divergence flagged: `dbt_project/` layout vs ade-bench `project/`.
