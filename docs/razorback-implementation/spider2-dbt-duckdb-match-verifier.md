---
id: r5hpxtc97nws6qfjc2j8ewz3
title: spider2-dbt — duckdb_match verifier emitting binary reward.json
status: backlog
source: Spider2 evaluation_suite/eval_utils.duckdb_match + gold/spider2_eval.jsonl schema; harbor verifier reward.json contract
started:
completed:
verdict:
score:
worktree:
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
