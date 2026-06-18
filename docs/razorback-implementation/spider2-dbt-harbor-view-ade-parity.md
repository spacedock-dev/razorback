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
