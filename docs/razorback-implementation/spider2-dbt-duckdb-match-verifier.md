---
id: r5hpxtc97nws6qfjc2j8ewz3
title: spider2-dbt — duckdb_match verifier emitting binary reward.json
status: implementation
source: Spider2 evaluation_suite/eval_utils.duckdb_match + gold/spider2_eval.jsonl schema; harbor verifier reward.json contract
started: 2026-06-18T08:49:13Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-spider2-dbt-duckdb-match-verifier
issue:
pr:
mod-block:
---

## Problem

Spider2-dbt scoring is binary `duckdb_match`: for each task the gold
spec (`spider2_eval.jsonl`) names `condition_tabs`, `condition_cols`
(0-based column indices), and `ignore_orders`; the scorer compares the
agent-produced `.duckdb` against the gold `.duckdb` table-by-table on
those columns and awards 1.0 only if every table matches, else 0.0.
This task emits a Harbor verifier (`tests/test.sh` + a bundled Python
comparator) that reproduces that semantics and writes
`/logs/verifier/reward.json` in Harbor shape. The gold `.duckdb` + eval
spec live under verifier-only paths excluded from the agent view by the
deny-globs. The retired `src/razorback/_legacy/benchmarks/dab/verify.py`
is a reference for the comparison + reward shaping.

## Acceptance criteria

**AC-1 — The comparator scores 1.0 on a matching DB and 0.0 on a mismatch.**
Verified by: a unit test with two tiny DuckDB fixtures — one matching
gold on `condition_tabs`/`condition_cols`, one differing — asserting
reward 1.0 and 0.0 respectively.

**AC-2 — Column subsetting and `ignore_orders` honor duckdb_match semantics.**
Verified by: a unit test asserting (a) a row-reordered table still
scores 1.0 when `ignore_orders` is true, and (b) a difference in a
column NOT listed in `condition_cols` does not lower the score.

**AC-3 — The emitted `tests/test.sh` writes a Harbor-shaped reward.json.**
Verified by: a test running the emitted `test.sh` against a fixture view
and asserting `/logs/verifier/reward.json` parses to `{"reward": <float>}`.

## Test plan

Unit tests build small `.duckdb` fixtures (predicted + gold) and drive
the comparator directly, plus one test that executes the generated
`test.sh`. Validation acceptance command: `uv run pytest -k spider2_dbt_verify`.

## Out of scope

dbt build orchestration inside the container (the agent runs `dbt build`;
the verifier only compares outputs) — covered by
`spider2-dbt-harbor-view-ade-parity`. Multi-DB / non-DuckDB Spider2
answer types (`string_match`, `table_match`, BigQuery/Snowflake) — the
dbt track is DuckDB-only.

## Stage Report: plan

- DONE: Map the 3 ACs to concrete modules with a TDD checkpoint each
  Plan AC↔Task table maps AC-1→T1/T2 (`duckdb_match.py`+`eval_spec.py`), AC-2→T3/T4, AC-3→T5/T6/T7 (`verify.py` + materializer-emitted `tests/test.sh`); each task has failing-test-first steps. Comparator module = `src/razorback/benchmarks/spider2_dbt/duckdb_match.py`; `test.sh` emitted by `_ensure_verifier_assets` in `spider2_dbt/harbor_view.py`.
- DONE: Exercise the riskiest mechanism first (two tiny DuckDB fixtures + comparator reproducing duckdb_match) before wiring test.sh
  T2–T4 build in-test DuckDB fixtures and prove per-table SELECT */condition_cols subset/ignore_orders semantics before any test.sh plumbing (T5–T7); reward-shaping cites `_legacy/benchmarks/dab/verify.py:30-32`.
- DONE: Write a standard separate plan doc with an AC-to-task map and cites; keep gold .duckdb + eval spec on verifier-only paths excluded from the agent view
  Plan at `docs/razorback-implementation/plans/spider2-dbt-duckdb-match-verifier.md` cites Spider2 `eval_utils.duckdb_match` + `spider2_eval.jsonl` schema. Locked design: gold lives under source `tests/gold/` (stripped by `**/gold/**`), re-copied explicitly to view `tests/` (verifier-uploaded only). Verified live: `tests/gold/gold.duckdb` denied=True, `tests/gold.duckdb`/`tests/spider2_eval.jsonl` denied=False; `duckdb` 1.5.2 importable.

### Summary

Wrote a separate implementation plan (3 ACs, 7 tasks) for the spider2-dbt duckdb_match verifier. Riskiest-first: the comparator reproducing Spider2 `duckdb_match` (per-table SELECT *, condition_cols subset, ignore_orders multiset compare, all-tables-AND) is built and proven against in-test DuckDB fixtures before any test.sh wiring. Key locked decision: gold `.duckdb` + eval spec are verifier-only by placing them under the view's `tests/` dir (Harbor uploads `tests/` to the container only at verify time, removes it around the agent run), copied explicitly so the `**/gold/**` deny-glob keeps the agent-facing tree clean — confirmed live against the deny-globs and the harbor verifier/trial source. One open item flagged: the agent-produced DB's container path (`/app/spider2.duckdb`) in the emitted test.sh is a placeholder pending the `spider2-dbt-harbor-view-ade-parity` image/workdir contract; it does not affect the gating `uv run pytest -k spider2_dbt_verify` suite.
