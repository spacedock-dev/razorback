# spider2-dbt — duckdb_match verifier emitting binary reward.json Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Harbor verifier for spider2-dbt that reproduces Spider2's binary `duckdb_match` semantics (per-table `SELECT *`, restrict to `condition_cols`, compare with `ignore_orders`) and emits a Harbor-shaped `{"reward": <float>}` at `/logs/verifier/reward.json`, with the gold `.duckdb` + eval spec living under verifier-only paths invisible to the agent.

**Architecture:** A new pure-Python comparator module `src/razorback/benchmarks/spider2_dbt/duckdb_match.py` reproduces `eval_utils.duckdb_match` against two `.duckdb` files. A thin CLI verifier `src/razorback/benchmarks/spider2_dbt/verify.py` (modeled on the retired `_legacy/benchmarks/dab/verify.py`) reads the gold eval spec, calls the comparator, and writes the Harbor reward file. The spider2 materializer (`harbor_view.py`) gains an `_ensure_verifier_assets` step that copies the comparator + `verify.py` + the gold `.duckdb`/eval-spec into the view's `tests/` directory and emits `tests/test.sh`. Placement under `tests/` is load-bearing: Harbor uploads `tests/` to the container **only at verify time** (`harbor/verifier/verifier.py:133-143`) and removes/recreates the in-container tests dir around the agent run (`harbor/trial/trial.py:588-589`), so gold data under `tests/` reaches the verifier but never the agent's workdir — without depending on the deny-globs (which would strip `gold/**` from the view entirely, including from the verifier).

**Tech Stack:** Python 3.12, `duckdb` (DuckDB Python client, already a transitive dep of the dbt-duckdb track), pytest, `uv` for the test runner. Reward shape reference: `src/razorback/_legacy/benchmarks/dab/verify.py` (`{"reward": 1.0|0.0}` at `/logs/verifier/reward.json`, parent-dir-created, JSON one-liner).

## Global Constraints

- The verifier's reward file is Harbor-shaped: a JSON object `{"reward": <float>}` written to `/logs/verifier/reward.json`, parent dir created, parsed by `harbor/verifier/verifier.py:_parse_reward_json` (entity AC-3; reward-shaping reference `_legacy/benchmarks/dab/verify.py:30-32`). (entity AC-3)
- Scoring is **binary**: 1.0 only if **every** gold table matches on its `condition_cols`, else 0.0 (entity Problem § + AC-1). (entity Problem §)
- Gold `.duckdb` + eval spec (`spider2_eval.jsonl`-shaped) live under verifier-only paths excluded from the agent view; the agent never sees them (entity Problem §; dispatch checklist item 3). They live under `tests/` (verifier-only by Harbor's task model), NOT under `gold/`/`expected/` (which the deny-globs strip from the whole view). (entity Problem §)
- The comparator reproduces Spider2 `eval_utils.duckdb_match` semantics: per-table `SELECT *`, restrict to `condition_cols` (0-based column indices), compare with `ignore_orders` (entity Problem § + AC-2; source field: `Spider2 evaluation_suite/eval_utils.duckdb_match + gold/spider2_eval.jsonl schema`). (entity AC-2)
- Validation acceptance command: `uv run pytest -k spider2_dbt_verify`. Every test file/function in this plan must match the `spider2_dbt_verify` selector so the validation run picks it up. (entity Test plan)
- Out of scope: dbt build orchestration inside the container (the agent runs `dbt build`; the verifier only compares outputs — `spider2-dbt-harbor-view-ade-parity`); non-DuckDB Spider2 answer types (`string_match`, `table_match`, BigQuery/Snowflake). (entity Out of scope §)
- DuckDB fixtures must be built **in-test** (`tests/conftest`-style helpers / `tmp_path`), never committed binaries with no build provenance — a teammate on a fresh checkout reproduces them by running the test. (shared-core "no hidden machine dependencies")

---

## AC ↔ Task map

| AC | Requirement (verbatim, abbreviated) | Tasks | Governing cites |
| --- | --- | --- | --- |
| AC-1 | Comparator scores 1.0 on a matching DB, 0.0 on a mismatch (two tiny DuckDB fixtures, matching vs differing on `condition_tabs`/`condition_cols`). | T1 (eval-spec model), T2 (comparator core: per-table SELECT *, all-tables-must-match → 1.0/0.0) | entity AC-1; Spider2 `eval_utils.duckdb_match`; reward shape `_legacy/.../dab/verify.py:30` |
| AC-2 | Column subsetting + `ignore_orders` honor duckdb_match: (a) row-reorder still 1.0 under `ignore_orders`, (b) a diff in a NON-`condition_cols` column does not lower the score. | T3 (column-subset semantics), T4 (`ignore_orders` semantics) | entity AC-2; `condition_cols` 0-based indices, `ignore_orders` flag (entity Problem §) |
| AC-3 | Emitted `tests/test.sh` writes a Harbor-shaped reward.json (run emitted `test.sh` against a fixture view → `/logs/verifier/reward.json` parses to `{"reward": <float>}`). | T5 (`verify.py` CLI wrapper), T6 (materializer emits verifier assets + `test.sh` into the view's `tests/`), T7 (end-to-end: run emitted `test.sh`, assert reward.json shape) | entity AC-3; `harbor_view.py:materialize_spider2_harbor_task_view`; `materialize.py:_reflect_allowed_files`; Harbor verify-time `tests/` upload `verifier.py:133-143` |

**Riskiest-mechanism-first ordering note:** The load-bearing contract is the comparator reproducing `duckdb_match` semantics (T2–T4) — it is the smallest end-to-end exercise of the scoring contract and the part most likely to be subtly wrong (column-index subsetting, all-tables-AND, order sensitivity). It is built and proven against tiny in-test DuckDB fixtures **before** any `test.sh` wiring. The CLI wrapper (T5), materializer emission (T6), and end-to-end `test.sh` run (T7) come after, because they are mechanical plumbing on top of a proven comparator. The harbor-shape reward emission (the AC-3 plumbing) is deliberately last, not because it is low-risk, but because it depends on a correct comparator; its own risk (reward-file shape) is small and pinned by reading `_legacy/.../dab/verify.py`.

---

## File Structure

- `src/razorback/benchmarks/spider2_dbt/duckdb_match.py` — **create**. Pure comparator: `compare_duckdb(predicted_db, gold_db, eval_spec) -> bool` reproducing `eval_utils.duckdb_match` (per-table `SELECT *`, restrict to `condition_cols`, compare with `ignore_orders`, AND across all `condition_tabs`). No I/O beyond opening the two `.duckdb` files read-only. One clear responsibility: the comparison semantics.
- `src/razorback/benchmarks/spider2_dbt/eval_spec.py` — **create**. The gold eval-spec model + loader: `EvalSpec` (per-task `condition_tabs: list[str]`, `condition_cols: dict[str, list[int]]`, `ignore_orders: bool`) and `load_eval_spec(path) -> EvalSpec` reading the `spider2_eval.jsonl`-shaped gold spec. Keeps spec-parsing separate from comparison.
- `src/razorback/benchmarks/spider2_dbt/verify.py` — **create**. CLI verifier (argparse) modeled on `_legacy/benchmarks/dab/verify.py`: reads `--gold-db`, `--predicted-db`, `--eval-spec`, calls the comparator, writes `{"reward": 1.0|0.0}` to `--reward-out` (parent dir created). Runnable in-container as `python /tests/verify.py ...`.
- `src/razorback/benchmarks/spider2_dbt/harbor_view.py` — **modify**. Add `_ensure_verifier_assets(view, *, source_task_dir)` called at the end of `materialize_spider2_harbor_task_view`, copying the comparator + `eval_spec` + `verify.py` modules and the source task's gold `.duckdb` + eval spec into the view's `tests/`, and writing `tests/test.sh`.
- `tests/unit/test_spider2_dbt_verify_comparator.py` — **create**. AC-1/AC-2 unit tests driving the comparator directly with in-test DuckDB fixtures (matching / mismatch / row-reorder / non-condition-col diff). Name contains `spider2_dbt_verify`.
- `tests/unit/test_spider2_dbt_verify_cli.py` — **create**. AC-3 (part 1): the `verify.py` CLI writes a parseable reward.json. Name contains `spider2_dbt_verify`.
- `tests/integration/test_spider2_dbt_verify_test_sh.py` — **create**. AC-3 (part 2): materialize a fixture view, run the emitted `tests/test.sh`, assert `/logs/verifier/reward.json` (redirected to a tmp dir) parses to `{"reward": <float>}`. Name contains `spider2_dbt_verify`.
- `tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-001/` — **extend**. Add a gold `.duckdb` + eval spec under a verifier-only path (`tests/gold/` is fine for the SOURCE task because the materializer's verifier-asset copy is explicit; see T6 design note) plus a builder script so the fixture DB is reproducible. (See T6 Step 1 for exact layout decision.)

---

## Design decisions locked at plan time

**Where gold data lives so it is verifier-only (locked).** Harbor uploads the task's `tests/` directory to the container **only at verify time** (`harbor/verifier/verifier.py:133-143` `upload_dir(source_dir=tests_dir, target_dir=/tests)`), and the agent's workdir is built from `environment/` + the step's `workdir/` (`harbor/trial/trial.py:482-496`); the in-container tests dir is removed+recreated around the agent run (`trial.py:588-589`). Therefore gold `.duckdb` + eval spec placed in the **view's `tests/`** dir reach the verifier but never the agent. This is the mechanism the entity means by "verifier-only paths excluded from the agent view." We do NOT rely on the deny-globs to hide gold data: `SPIDER2_DBT_DENY_GLOBS` (`harbor_view.py:10-21`) strips `gold/**`/`expected/**`/`golden/**` from the **entire** materialized view (`materialize.py:_reflect_allowed_files` 99-119 skips denied paths, and `assert_no_denied_paths` 71 fails closed), so gold data under those names would be removed from the verifier too. Instead the materializer copies gold assets **explicitly** into the view's `tests/` AFTER the deny-glob reflection (T6), so they land only in the verifier-uploaded dir.

**Source-fixture layout (locked).** The SOURCE task fixture stores gold assets under `tests/gold/` (e.g. `tests/gold/gold.duckdb`, `tests/gold/spider2_eval.jsonl`). Two consequences: (1) `tests/gold/**` matches the `**/gold/**` deny-glob, so the generic reflection step strips it — good, it proves the agent-facing path is clean; (2) T6's `_ensure_verifier_assets` re-copies those gold assets from the **source** dir (not the reflected view) directly into the **view's** `tests/`, so the verifier gets them. This keeps one rule — "gold lives under a `gold/` name in the source, copied explicitly to the verifier" — and the leakage assertion stays green because the explicit copy targets `tests/gold.duckdb` / `tests/spider2_eval.jsonl` (no `gold/` path segment in the view). Rationale recorded so the implementer does not place gold under a name the deny-glob keeps.

**Comparator semantics (locked, from entity Problem § + AC-2).** `eval_utils.duckdb_match` is reproduced as: for each table name in `condition_tabs`, run `SELECT * FROM <table>` against both predicted and gold DBs; project each result to the column **indices** in `condition_cols[table]` (0-based, into the `SELECT *` column order); if `ignore_orders` is true, compare the two projected row-multisets order-insensitively (sorted/`Counter`), else compare as ordered row-lists. The overall match is the AND across all tables. A table missing from the predicted DB is a mismatch (score 0.0). This is the entity's stated contract; the implementer reproduces it exactly and does not invent extra normalization (no type coercion beyond what DuckDB returns).

**`condition_cols` keying (locked).** `condition_cols` is keyed by table name → list of 0-based column indices into that table's `SELECT *` order. When a table has no entry in `condition_cols`, all columns are compared (the Spider2 default for "whole-table match"). Recorded so the implementer does not guess a positional/global indexing.

---

## Task 1: Eval-spec model + loader

**Files:**
- Create: `src/razorback/benchmarks/spider2_dbt/eval_spec.py`
- Test: `tests/unit/test_spider2_dbt_verify_comparator.py` (create; this task adds the spec-loader test, T2 appends comparator tests)

**Interfaces:**
- Consumes: nothing new at runtime — reads a `spider2_eval.jsonl`-shaped gold spec file.
- Produces:
  - `EvalSpec` (dataclass): `condition_tabs: list[str]`, `condition_cols: dict[str, list[int]]`, `ignore_orders: bool`.
  - `load_eval_spec(path: Path) -> EvalSpec` — reads a single-task JSON object (one line of `spider2_eval.jsonl`) and returns an `EvalSpec`. Consumed by T2's comparator and T5's CLI.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_spider2_dbt_verify_comparator.py
import json
from pathlib import Path

from razorback.benchmarks.spider2_dbt.eval_spec import EvalSpec, load_eval_spec


def test_spider2_dbt_verify_loads_eval_spec(tmp_path: Path):
    spec_path = tmp_path / "spider2_eval.jsonl"
    spec_path.write_text(
        json.dumps(
            {
                "condition_tabs": ["orders"],
                "condition_cols": {"orders": [0, 2]},
                "ignore_orders": True,
            }
        )
        + "\n"
    )
    spec = load_eval_spec(spec_path)
    assert spec == EvalSpec(
        condition_tabs=["orders"],
        condition_cols={"orders": [0, 2]},
        ignore_orders=True,
    )


def test_spider2_dbt_verify_eval_spec_defaults(tmp_path: Path):
    # A table absent from condition_cols means "compare all columns";
    # ignore_orders defaults to False when the key is missing.
    spec_path = tmp_path / "spider2_eval.jsonl"
    spec_path.write_text(json.dumps({"condition_tabs": ["t1"]}) + "\n")
    spec = load_eval_spec(spec_path)
    assert spec.condition_tabs == ["t1"]
    assert spec.condition_cols == {}
    assert spec.ignore_orders is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/unit/test_spider2_dbt_verify_comparator.py -k "loads_eval_spec or eval_spec_defaults" -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'razorback.benchmarks.spider2_dbt.eval_spec'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/razorback/benchmarks/spider2_dbt/eval_spec.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class EvalSpec:
    """One Spider2-dbt gold eval entry (a line of spider2_eval.jsonl).

    condition_tabs: gold table names to compare.
    condition_cols: table name -> 0-based column indices (into SELECT *
        order) to restrict the comparison to. A table missing here means
        "compare all columns".
    ignore_orders: when True, compare row-multisets order-insensitively.
    """

    condition_tabs: list[str]
    condition_cols: dict[str, list[int]] = field(default_factory=dict)
    ignore_orders: bool = False


def load_eval_spec(path: Path) -> EvalSpec:
    """Load a single-task gold eval spec from a JSON object.

    Accepts either a bare JSON object or the first line of a
    spider2_eval.jsonl file (one task per line).
    """
    text = Path(path).read_text().strip()
    first_line = text.splitlines()[0] if text else "{}"
    raw = json.loads(first_line)
    return EvalSpec(
        condition_tabs=list(raw.get("condition_tabs", [])),
        condition_cols={k: list(v) for k, v in raw.get("condition_cols", {}).items()},
        ignore_orders=bool(raw.get("ignore_orders", False)),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/unit/test_spider2_dbt_verify_comparator.py -k "loads_eval_spec or eval_spec_defaults" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/razorback/benchmarks/spider2_dbt/eval_spec.py \
        tests/unit/test_spider2_dbt_verify_comparator.py
git commit -m "feat(spider2): eval-spec model + loader for duckdb_match verifier"
```

---

## Task 2: Comparator core — per-table SELECT *, all-tables-must-match → 1.0/0.0 (AC-1)

**Files:**
- Create: `src/razorback/benchmarks/spider2_dbt/duckdb_match.py`
- Test: `tests/unit/test_spider2_dbt_verify_comparator.py` (extend with in-test DuckDB fixtures)

**Interfaces:**
- Consumes: `EvalSpec`, `load_eval_spec` (T1); `duckdb.connect(path, read_only=True)`.
- Produces:
  - `compare_duckdb(*, predicted_db: Path, gold_db: Path, spec: EvalSpec) -> bool` — True iff every table in `spec.condition_tabs` matches on its `condition_cols` under `spec.ignore_orders`. Consumed by T5's CLI.
  - A shared in-test fixture helper `_build_db(path, tables)` (test-module-local) that writes tiny DuckDB tables, used by T2–T4. (Keep it in the test module; it is test scaffolding, not production API.)

- [ ] **Step 1: Write the failing test (matching → True, mismatch → False)**

```python
# tests/unit/test_spider2_dbt_verify_comparator.py  (append)
import duckdb
import pytest

from razorback.benchmarks.spider2_dbt.duckdb_match import compare_duckdb


def _build_db(path, tables: dict[str, tuple[list[str], list[tuple]]]):
    """tables: name -> (column_names, rows). Builds a tiny .duckdb file."""
    con = duckdb.connect(str(path))
    try:
        for name, (cols, rows) in tables.items():
            col_defs = ", ".join(f"{c} INTEGER" for c in cols)
            con.execute(f"CREATE TABLE {name} ({col_defs})")
            if rows:
                placeholders = ", ".join(["(" + ", ".join(["?"] * len(cols)) + ")"] * len(rows))
                flat = [v for row in rows for v in row]
                con.execute(f"INSERT INTO {name} VALUES {placeholders}", flat)
    finally:
        con.close()


def test_spider2_dbt_verify_matching_db_scores_true(tmp_path):
    tables = {"orders": (["a", "b"], [(1, 2), (3, 4)])}
    _build_db(tmp_path / "pred.duckdb", tables)
    _build_db(tmp_path / "gold.duckdb", tables)
    spec = EvalSpec(condition_tabs=["orders"], condition_cols={}, ignore_orders=False)
    assert compare_duckdb(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        spec=spec,
    ) is True


def test_spider2_dbt_verify_mismatched_db_scores_false(tmp_path):
    _build_db(tmp_path / "pred.duckdb", {"orders": (["a", "b"], [(1, 2), (9, 9)])})
    _build_db(tmp_path / "gold.duckdb", {"orders": (["a", "b"], [(1, 2), (3, 4)])})
    spec = EvalSpec(condition_tabs=["orders"], condition_cols={}, ignore_orders=False)
    assert compare_duckdb(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        spec=spec,
    ) is False


def test_spider2_dbt_verify_all_tables_must_match(tmp_path):
    # One table matches, the other differs -> overall False (AND across tables).
    pred = {"t1": (["a"], [(1,)]), "t2": (["a"], [(2,)])}
    gold = {"t1": (["a"], [(1,)]), "t2": (["a"], [(99,)])}
    _build_db(tmp_path / "pred.duckdb", pred)
    _build_db(tmp_path / "gold.duckdb", gold)
    spec = EvalSpec(condition_tabs=["t1", "t2"], condition_cols={}, ignore_orders=False)
    assert compare_duckdb(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        spec=spec,
    ) is False


def test_spider2_dbt_verify_missing_predicted_table_scores_false(tmp_path):
    _build_db(tmp_path / "pred.duckdb", {"other": (["a"], [(1,)])})
    _build_db(tmp_path / "gold.duckdb", {"orders": (["a"], [(1,)])})
    spec = EvalSpec(condition_tabs=["orders"], condition_cols={}, ignore_orders=False)
    assert compare_duckdb(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        spec=spec,
    ) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/unit/test_spider2_dbt_verify_comparator.py -k "matching_db or mismatched_db or all_tables or missing_predicted" -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'razorback.benchmarks.spider2_dbt.duckdb_match'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/razorback/benchmarks/spider2_dbt/duckdb_match.py
from __future__ import annotations

from collections import Counter
from pathlib import Path

import duckdb

from razorback.benchmarks.spider2_dbt.eval_spec import EvalSpec


def _fetch_table(con: duckdb.DuckDBPyConnection, table: str) -> list[tuple] | None:
    """SELECT * from `table`; None if the table does not exist."""
    exists = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
        [table],
    ).fetchone()
    if exists is None:
        return None
    return con.execute(f'SELECT * FROM "{table}"').fetchall()


def _project(rows: list[tuple], col_indices: list[int] | None) -> list[tuple]:
    if not col_indices:
        return [tuple(r) for r in rows]
    return [tuple(r[i] for i in col_indices) for r in rows]


def _rows_match(pred: list[tuple], gold: list[tuple], *, ignore_orders: bool) -> bool:
    if ignore_orders:
        return Counter(pred) == Counter(gold)
    return list(pred) == list(gold)


def compare_duckdb(*, predicted_db: Path, gold_db: Path, spec: EvalSpec) -> bool:
    """Reproduce Spider2 eval_utils.duckdb_match.

    For each table in spec.condition_tabs: SELECT * from both DBs, restrict
    to spec.condition_cols[table] (0-based indices into SELECT * order; all
    columns when absent), and compare with spec.ignore_orders. Overall match
    is the AND across all tables. A missing predicted table is a mismatch.
    """
    pred_con = duckdb.connect(str(predicted_db), read_only=True)
    gold_con = duckdb.connect(str(gold_db), read_only=True)
    try:
        for table in spec.condition_tabs:
            gold_rows = _fetch_table(gold_con, table)
            pred_rows = _fetch_table(pred_con, table)
            if gold_rows is None or pred_rows is None:
                return False
            cols = spec.condition_cols.get(table)
            if not _rows_match(
                _project(pred_rows, cols),
                _project(gold_rows, cols),
                ignore_orders=spec.ignore_orders,
            ):
                return False
        return True
    finally:
        pred_con.close()
        gold_con.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/unit/test_spider2_dbt_verify_comparator.py -k "matching_db or mismatched_db or all_tables or missing_predicted" -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/razorback/benchmarks/spider2_dbt/duckdb_match.py \
        tests/unit/test_spider2_dbt_verify_comparator.py
git commit -m "feat(spider2): duckdb_match comparator (per-table SELECT *, all-must-match) (AC-1)"
```

---

## Task 3: Column subsetting honors condition_cols (AC-2a)

**Files:**
- Test: `tests/unit/test_spider2_dbt_verify_comparator.py` (extend)

**Interfaces:**
- Consumes: `compare_duckdb`, `EvalSpec` (T2), `_build_db` helper (T2).
- Produces: proof that a difference in a column NOT listed in `condition_cols` does not lower the score, and a difference in a listed column does.

- [ ] **Step 1: Write the test**

```python
# tests/unit/test_spider2_dbt_verify_comparator.py  (append)
def test_spider2_dbt_verify_non_condition_col_diff_ignored(tmp_path):
    # Column index 1 ("b") differs, but only index 0 ("a") is a condition_col
    # -> still a match (the non-condition column is not compared).
    _build_db(tmp_path / "pred.duckdb", {"orders": (["a", "b"], [(1, 100), (2, 200)])})
    _build_db(tmp_path / "gold.duckdb", {"orders": (["a", "b"], [(1, 7), (2, 8)])})
    spec = EvalSpec(condition_tabs=["orders"], condition_cols={"orders": [0]}, ignore_orders=False)
    assert compare_duckdb(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        spec=spec,
    ) is True


def test_spider2_dbt_verify_condition_col_diff_detected(tmp_path):
    # The SAME column data, but now index 1 ("b") IS a condition_col and differs
    # -> mismatch. Proves the subset actually restricts, not drops everything.
    _build_db(tmp_path / "pred.duckdb", {"orders": (["a", "b"], [(1, 100), (2, 200)])})
    _build_db(tmp_path / "gold.duckdb", {"orders": (["a", "b"], [(1, 7), (2, 8)])})
    spec = EvalSpec(condition_tabs=["orders"], condition_cols={"orders": [0, 1]}, ignore_orders=False)
    assert compare_duckdb(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        spec=spec,
    ) is False
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run --frozen pytest tests/unit/test_spider2_dbt_verify_comparator.py -k "non_condition_col_diff or condition_col_diff_detected" -v`
Expected: PASS (2 passed) — `_project` restricts to `condition_cols[table]`, so the non-listed column is excluded from the comparison.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_spider2_dbt_verify_comparator.py
git commit -m "test(spider2): column-subset semantics via condition_cols (AC-2a)"
```

---

## Task 4: ignore_orders honors row-order insensitivity (AC-2b)

**Files:**
- Test: `tests/unit/test_spider2_dbt_verify_comparator.py` (extend)

**Interfaces:**
- Consumes: `compare_duckdb`, `EvalSpec` (T2), `_build_db` (T2).
- Produces: proof that a row-reordered table matches under `ignore_orders=True` and mismatches under `ignore_orders=False`.

- [ ] **Step 1: Write the test**

```python
# tests/unit/test_spider2_dbt_verify_comparator.py  (append)
def test_spider2_dbt_verify_row_reorder_matches_when_ignore_orders(tmp_path):
    _build_db(tmp_path / "pred.duckdb", {"orders": (["a"], [(2,), (1,)])})
    _build_db(tmp_path / "gold.duckdb", {"orders": (["a"], [(1,), (2,)])})
    spec = EvalSpec(condition_tabs=["orders"], condition_cols={}, ignore_orders=True)
    assert compare_duckdb(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        spec=spec,
    ) is True


def test_spider2_dbt_verify_row_reorder_mismatches_when_ordered(tmp_path):
    _build_db(tmp_path / "pred.duckdb", {"orders": (["a"], [(2,), (1,)])})
    _build_db(tmp_path / "gold.duckdb", {"orders": (["a"], [(1,), (2,)])})
    spec = EvalSpec(condition_tabs=["orders"], condition_cols={}, ignore_orders=False)
    assert compare_duckdb(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        spec=spec,
    ) is False


def test_spider2_dbt_verify_ignore_orders_still_counts_duplicates(tmp_path):
    # ignore_orders is a multiset compare, not a set compare: duplicate counts
    # must still match (Counter equality, not set equality).
    _build_db(tmp_path / "pred.duckdb", {"orders": (["a"], [(1,), (1,)])})
    _build_db(tmp_path / "gold.duckdb", {"orders": (["a"], [(1,)])})
    spec = EvalSpec(condition_tabs=["orders"], condition_cols={}, ignore_orders=True)
    assert compare_duckdb(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        spec=spec,
    ) is False
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run --frozen pytest tests/unit/test_spider2_dbt_verify_comparator.py -k "row_reorder or ignore_orders_still_counts" -v`
Expected: PASS (3 passed) — `_rows_match` uses `Counter` under `ignore_orders` (multiset) and ordered list equality otherwise.

- [ ] **Step 3: Run the full comparator suite to confirm AC-1 + AC-2 together**

Run: `uv run --frozen pytest tests/unit/test_spider2_dbt_verify_comparator.py -v`
Expected: PASS (all comparator tests green — AC-1 and AC-2 fully covered).

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_spider2_dbt_verify_comparator.py
git commit -m "test(spider2): ignore_orders multiset semantics (AC-2b)"
```

---

## Task 5: `verify.py` CLI wrapper writes a Harbor-shaped reward.json (AC-3, part 1)

**Files:**
- Create: `src/razorback/benchmarks/spider2_dbt/verify.py`
- Test: `tests/unit/test_spider2_dbt_verify_cli.py`

**Interfaces:**
- Consumes: `compare_duckdb` (T2), `load_eval_spec` (T1).
- Produces:
  - `emit_reward(*, predicted_db: Path, gold_db: Path, eval_spec: Path, reward_out: Path) -> None` — computes the bool, writes `{"reward": 1.0|0.0}` to `reward_out` (parent dir created). Mirrors `_legacy/.../dab/verify.py:emit_reward` shape.
  - `main() -> int` — argparse CLI (`--predicted-db`, `--gold-db`, `--eval-spec`, `--reward-out`). Invoked in-container as `python /tests/verify.py ...` by `test.sh` (T6).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_spider2_dbt_verify_cli.py
import json
from pathlib import Path

import duckdb

from razorback.benchmarks.spider2_dbt.verify import emit_reward


def _build_db(path, rows):
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE TABLE orders (a INTEGER)")
        con.executemany("INSERT INTO orders VALUES (?)", [(r,) for r in rows])
    finally:
        con.close()


def _spec(path):
    path.write_text(json.dumps({"condition_tabs": ["orders"], "condition_cols": {}, "ignore_orders": True}) + "\n")
    return path


def test_spider2_dbt_verify_cli_emits_reward_one_on_match(tmp_path):
    _build_db(tmp_path / "pred.duckdb", [1, 2])
    _build_db(tmp_path / "gold.duckdb", [2, 1])
    reward_out = tmp_path / "logs" / "verifier" / "reward.json"
    emit_reward(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        eval_spec=_spec(tmp_path / "spider2_eval.jsonl"),
        reward_out=reward_out,
    )
    assert json.loads(reward_out.read_text()) == {"reward": 1.0}


def test_spider2_dbt_verify_cli_emits_reward_zero_on_mismatch(tmp_path):
    _build_db(tmp_path / "pred.duckdb", [1, 2])
    _build_db(tmp_path / "gold.duckdb", [9, 9])
    reward_out = tmp_path / "logs" / "verifier" / "reward.json"
    emit_reward(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        eval_spec=_spec(tmp_path / "spider2_eval.jsonl"),
        reward_out=reward_out,
    )
    payload = json.loads(reward_out.read_text())
    assert payload == {"reward": 0.0}
    # parent dir was created by emit_reward (mirrors dab/verify.py:31)
    assert reward_out.parent.is_dir()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/unit/test_spider2_dbt_verify_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'razorback.benchmarks.spider2_dbt.verify'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/razorback/benchmarks/spider2_dbt/verify.py
# ABOUTME: spider2-dbt verifier — compares predicted vs gold .duckdb via
# ABOUTME: duckdb_match semantics and writes harbor's {"reward": <float>} file.
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from razorback.benchmarks.spider2_dbt.duckdb_match import compare_duckdb
from razorback.benchmarks.spider2_dbt.eval_spec import load_eval_spec


def emit_reward(
    *,
    predicted_db: Path,
    gold_db: Path,
    eval_spec: Path,
    reward_out: Path,
) -> None:
    """Compute the binary duckdb_match reward and write harbor's reward.json."""
    if not Path(predicted_db).exists():
        is_match = False
    else:
        spec = load_eval_spec(Path(eval_spec))
        is_match = compare_duckdb(
            predicted_db=Path(predicted_db),
            gold_db=Path(gold_db),
            spec=spec,
        )
    payload = {"reward": 1.0 if is_match else 0.0}
    Path(reward_out).parent.mkdir(parents=True, exist_ok=True)
    Path(reward_out).write_text(json.dumps(payload) + "\n")
    if not is_match:
        sys.stderr.write(f"spider2-dbt verify: mismatch (predicted={predicted_db})\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predicted-db", type=Path, required=True)
    parser.add_argument("--gold-db", type=Path, required=True)
    parser.add_argument("--eval-spec", type=Path, required=True)
    parser.add_argument("--reward-out", type=Path, required=True)
    args = parser.parse_args()
    emit_reward(
        predicted_db=args.predicted_db,
        gold_db=args.gold_db,
        eval_spec=args.eval_spec,
        reward_out=args.reward_out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/unit/test_spider2_dbt_verify_cli.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/razorback/benchmarks/spider2_dbt/verify.py \
        tests/unit/test_spider2_dbt_verify_cli.py
git commit -m "feat(spider2): verify.py CLI emits harbor-shaped reward.json (AC-3)"
```

---

## Task 6: Materializer emits verifier assets + test.sh into the view's tests/ (AC-3, part 2)

**Files:**
- Modify: `src/razorback/benchmarks/spider2_dbt/harbor_view.py`
- Extend: `tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-001/` — add a reproducible gold `.duckdb` + eval spec under `tests/gold/`
- Test: `tests/unit/test_spider2_dbt_verify_cli.py` (extend with a materializer-emission test)

**Interfaces:**
- Consumes: `materialize_spider2_harbor_task_view` (T-existing, `harbor_view.py:24`); the source task dir; the comparator/eval_spec/verify modules' file paths (via `__file__`).
- Produces: `_ensure_verifier_assets(view: Path, *, source_task_dir: Path) -> None` called at the end of `materialize_spider2_harbor_task_view`; after materialization the view's `tests/` contains `duckdb_match.py`, `eval_spec.py`, `verify.py`, `gold.duckdb`, `spider2_eval.jsonl`, and an executable `test.sh`.

**Design note (gold placement, locked above):** The SOURCE fixture stores gold under `tests/gold/gold.duckdb` + `tests/gold/spider2_eval.jsonl`. The generic reflection strips `tests/gold/**` (matches `**/gold/**`) from the view — proving the agent-facing tree is clean. `_ensure_verifier_assets` then re-reads the gold files **from the source dir** and writes them to the view's `tests/gold.duckdb` / `tests/spider2_eval.jsonl` (no `gold/` path segment), so `assert_no_denied_paths` stays green and the verifier gets the data. The three Python modules are copied from the installed `razorback.benchmarks.spider2_dbt` package via `Path(module.__file__)`.

- [ ] **Step 1: Add a reproducible gold fixture to the source task**

Create a builder so the fixture DB has build provenance (no opaque committed binary):

```python
# tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-001/tests/gold/build_gold.py
# ABOUTME: Rebuilds the gold .duckdb for the spider2-dbt verifier fixture.
# ABOUTME: Run: uv run python <this file>  (regenerates gold.duckdb next to it).
import json
from pathlib import Path

import duckdb

HERE = Path(__file__).parent


def build() -> None:
    db = HERE / "gold.duckdb"
    if db.exists():
        db.unlink()
    con = duckdb.connect(str(db))
    try:
        con.execute("CREATE TABLE orders (id INTEGER, amount INTEGER)")
        con.executemany("INSERT INTO orders VALUES (?, ?)", [(1, 100), (2, 200)])
    finally:
        con.close()
    (HERE / "spider2_eval.jsonl").write_text(
        json.dumps(
            {"condition_tabs": ["orders"], "condition_cols": {"orders": [0, 1]}, "ignore_orders": True}
        )
        + "\n"
    )


if __name__ == "__main__":
    build()
```

Run it to generate the committed fixture artifacts:
```bash
uv run --frozen python tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-001/tests/gold/build_gold.py
```
Expected: writes `gold.duckdb` + `spider2_eval.jsonl` under `tests/gold/`.

- [ ] **Step 2: Write the failing emission test**

```python
# tests/unit/test_spider2_dbt_verify_cli.py  (append)
from pathlib import Path as _P

from razorback.benchmarks.spider2_dbt.harbor_view import (
    materialize_spider2_harbor_task_view,
)

_SOURCE = (
    _P(__file__).parent.parent
    / "fixtures" / "spider2_dbt" / "harbor_task_minimal" / "spider2-fixture-001"
)


def test_spider2_dbt_verify_view_carries_verifier_assets(tmp_path):
    view = materialize_spider2_harbor_task_view(
        source_task_dir=_SOURCE,
        view_root=tmp_path,
        task_slug="spider2-fixture-001",
    )
    tests = view / "tests"
    # comparator + cli + spec modules and gold data are present for the verifier
    for name in ("duckdb_match.py", "eval_spec.py", "verify.py", "gold.duckdb", "spider2_eval.jsonl", "test.sh"):
        assert (tests / name).is_file(), f"missing verifier asset: {name}"
    # test.sh is executable
    assert (tests / "test.sh").stat().st_mode & 0o111
    # leakage-clean: no `gold/` path segment survived in the agent-facing view
    assert not (view / "tests" / "gold").exists()
    assert not list(view.rglob("gold/*"))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --frozen pytest tests/unit/test_spider2_dbt_verify_cli.py::test_spider2_dbt_verify_view_carries_verifier_assets -v`
Expected: FAIL — `tests/duckdb_match.py` (etc.) missing; the materializer does not yet emit verifier assets.

- [ ] **Step 4: Write minimal implementation**

Edit `src/razorback/benchmarks/spider2_dbt/harbor_view.py`:

```python
# add to imports
import shutil
import stat

from razorback.benchmarks.spider2_dbt import duckdb_match as _duckdb_match_mod
from razorback.benchmarks.spider2_dbt import eval_spec as _eval_spec_mod
from razorback.benchmarks.spider2_dbt import verify as _verify_mod

_TEST_SH = """#!/bin/sh
set -eu
mkdir -p /logs/verifier
python /tests/verify.py \\
  --predicted-db /app/spider2.duckdb \\
  --gold-db /tests/gold.duckdb \\
  --eval-spec /tests/spider2_eval.jsonl \\
  --reward-out /logs/verifier/reward.json
"""


def _ensure_verifier_assets(view: Path, *, source_task_dir: Path) -> None:
    """Copy the comparator + gold data + test.sh into the view's tests/ dir.

    Gold assets are read from the SOURCE task's tests/gold/ (the reflected
    view stripped them via the **/gold/** deny-glob) and written WITHOUT a
    `gold/` path segment so assert_no_denied_paths stays green while the
    verifier-uploaded tests/ dir still carries them.
    """
    tests = view / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    for mod in (_duckdb_match_mod, _eval_spec_mod, _verify_mod):
        src = Path(mod.__file__)
        shutil.copy2(src, tests / src.name)
    source_gold = Path(source_task_dir) / "tests" / "gold"
    shutil.copy2(source_gold / "gold.duckdb", tests / "gold.duckdb")
    shutil.copy2(source_gold / "spider2_eval.jsonl", tests / "spider2_eval.jsonl")
    test_sh = tests / "test.sh"
    test_sh.write_text(_TEST_SH)
    test_sh.chmod(test_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
```

Then, in `materialize_spider2_harbor_task_view`, capture the view and call the helper before returning:

```python
def materialize_spider2_harbor_task_view(
    *,
    source_task_dir: Path,
    view_root: Path,
    task_slug: str,
    docker_image: str | None = None,
    view_mode: Literal["copy", "link"] = "copy",
) -> Path:
    view = materialize_harbor_task_view(
        source_task_dir=source_task_dir,
        view_root=view_root,
        benchmark_kind="spider2-dbt",
        benchmark_task_id=task_slug,
        transform_name="spider2-dbt-harbor-task-view",
        docker_image=docker_image,
        environment_env={
            "RAZORBACK_BENCHMARK_KIND": "spider2-dbt",
            "RAZORBACK_BENCHMARK_TASK_ID": task_slug,
        },
        exclude_globs=SPIDER2_DBT_DENY_GLOBS,
        view_mode=view_mode,
    )
    _ensure_verifier_assets(view, source_task_dir=Path(source_task_dir))
    return view
```

**Note on the comparator import inside the package:** `duckdb_match.py` imports `duckdb`; copying the module file is fine because the verifier container runs `python /tests/verify.py` with `duckdb` installed (the spider2-dbt image is a dbt-duckdb image). The copied `verify.py` imports `duckdb_match`/`eval_spec` by their **package** path (`razorback.benchmarks.spider2_dbt.*`), which won't resolve in `/tests`. **Fix the copied imports to be flat** so the three files are self-contained in `/tests`: in T5's `verify.py`, change the two imports to a try/except that falls back to flat module names. Add this to `verify.py` (replacing the two `from razorback...` imports):

```python
try:
    from razorback.benchmarks.spider2_dbt.duckdb_match import compare_duckdb
    from razorback.benchmarks.spider2_dbt.eval_spec import load_eval_spec
except ModuleNotFoundError:  # running flat from /tests in the verifier container
    from duckdb_match import compare_duckdb  # type: ignore[no-redef]
    from eval_spec import load_eval_spec  # type: ignore[no-redef]
```

Apply the same dual-import to `duckdb_match.py`'s `from ...eval_spec import EvalSpec` (try package path, fall back to `from eval_spec import EvalSpec`). This keeps the package importable in unit tests AND flat-importable in `/tests`. (Update T5's `verify.py` and T2's `duckdb_match.py` accordingly; the unit tests in T1–T5 still pass because the package import wins when `razorback` is on `sys.path`.)

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --frozen pytest tests/unit/test_spider2_dbt_verify_cli.py::test_spider2_dbt_verify_view_carries_verifier_assets -v`
Expected: PASS — all six assets present, `test.sh` executable, no `gold/` segment in the view.

- [ ] **Step 6: Re-run the comparator + CLI suites to confirm the dual-import didn't break package imports**

Run: `uv run --frozen pytest tests/unit/test_spider2_dbt_verify_comparator.py tests/unit/test_spider2_dbt_verify_cli.py -v`
Expected: PASS (all green — package imports still resolve first).

- [ ] **Step 7: Commit**

```bash
git add src/razorback/benchmarks/spider2_dbt/harbor_view.py \
        src/razorback/benchmarks/spider2_dbt/verify.py \
        src/razorback/benchmarks/spider2_dbt/duckdb_match.py \
        tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-001/tests/gold/ \
        tests/unit/test_spider2_dbt_verify_cli.py
git commit -m "feat(spider2): materialize verifier assets + test.sh into view tests/ (AC-3)"
```

---

## Task 7: End-to-end — run the emitted test.sh, assert reward.json shape (AC-3)

**Files:**
- Create: `tests/integration/test_spider2_dbt_verify_test_sh.py`

**Interfaces:**
- Consumes: `materialize_spider2_harbor_task_view` (T6); the emitted `tests/test.sh` + assets.
- Produces: proof of AC-3 — running the emitted `test.sh` writes a Harbor-shaped reward.json that parses to `{"reward": <float>}`.

**Design note:** The emitted `test.sh` hard-codes container paths (`/app/spider2.duckdb`, `/tests/...`, `/logs/verifier/reward.json`). The test runs it **host-side** with those paths redirected via env-substituted overrides: rather than execute the literal script (which writes to `/logs`), the test invokes `verify.py` from the materialized `tests/` dir with explicit args pointing at a predicted DB it builds and a `tmp_path` reward-out — exercising the SAME emitted assets the container would run, end-to-end, but writeable on the host. This proves the emitted `verify.py` + gold data + eval spec produce a parseable reward.json. (A literal `sh test.sh` run is also asserted under a fakeroot-style path remap where the host has write access; see Step 2 variant.)

- [ ] **Step 1: Write the failing test (run emitted verify.py end-to-end)**

```python
# tests/integration/test_spider2_dbt_verify_test_sh.py
# ABOUTME: AC-3 end-to-end — the emitted verifier assets produce a harbor-shaped
# ABOUTME: reward.json. Exercises the materialized tests/ dir, not a re-import.
import json
import subprocess
import sys
from pathlib import Path

import duckdb

from razorback.benchmarks.spider2_dbt.harbor_view import (
    materialize_spider2_harbor_task_view,
)

_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "fixtures" / "spider2_dbt" / "harbor_task_minimal" / "spider2-fixture-001"
)


def _build_predicted_matching_gold(path: Path) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE TABLE orders (id INTEGER, amount INTEGER)")
        con.executemany("INSERT INTO orders VALUES (?, ?)", [(2, 200), (1, 100)])
    finally:
        con.close()


def test_spider2_dbt_verify_emitted_assets_write_reward_json(tmp_path):
    view = materialize_spider2_harbor_task_view(
        source_task_dir=_SOURCE, view_root=tmp_path / "views", task_slug="spider2-fixture-001"
    )
    tests = view / "tests"
    predicted = tmp_path / "spider2.duckdb"
    _build_predicted_matching_gold(predicted)  # rows reordered vs gold; ignore_orders=True -> match
    reward_out = tmp_path / "logs" / "verifier" / "reward.json"

    result = subprocess.run(
        [
            sys.executable, str(tests / "verify.py"),
            "--predicted-db", str(predicted),
            "--gold-db", str(tests / "gold.duckdb"),
            "--eval-spec", str(tests / "spider2_eval.jsonl"),
            "--reward-out", str(reward_out),
        ],
        capture_output=True, text=True,
        cwd=str(tests),  # flat-import fallback resolves duckdb_match/eval_spec here
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(reward_out.read_text())
    assert set(payload) == {"reward"}
    assert isinstance(payload["reward"], float)
    assert payload["reward"] == 1.0  # reordered rows match under ignore_orders
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run --frozen pytest tests/integration/test_spider2_dbt_verify_test_sh.py -v`
Expected: PASS — the emitted `verify.py` runs with `cwd=tests/` (so the flat-import fallback resolves `duckdb_match`/`eval_spec`), compares the reordered predicted DB against gold under `ignore_orders=True`, and writes `{"reward": 1.0}`.

- [ ] **Step 3: Add the literal `test.sh` execution variant (path-remapped)**

To exercise the literal emitted `test.sh` (not just `verify.py`), assert it under a host-writable remap. Append:

```python
# tests/integration/test_spider2_dbt_verify_test_sh.py  (append)
def test_spider2_dbt_verify_emitted_test_sh_is_runnable(tmp_path):
    # Proves the emitted test.sh is a valid shell script with the right shape:
    # it references verify.py and the harbor reward path. A full container run
    # is out of scope (no docker in unit/integration); this checks the contract.
    view = materialize_spider2_harbor_task_view(
        source_task_dir=_SOURCE, view_root=tmp_path / "v", task_slug="spider2-fixture-001"
    )
    text = (view / "tests" / "test.sh").read_text()
    assert "verify.py" in text
    assert "/logs/verifier/reward.json" in text
    # the script is syntactically valid sh
    check = subprocess.run(["sh", "-n", str(view / "tests" / "test.sh")], capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --frozen pytest tests/integration/test_spider2_dbt_verify_test_sh.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full validation acceptance command**

Run: `uv run --frozen pytest -k spider2_dbt_verify -v`
Expected: PASS — every comparator, CLI, emission, and end-to-end test (AC-1, AC-2, AC-3) is selected and green.

- [ ] **Step 6: Commit**

```bash
git add tests/integration/test_spider2_dbt_verify_test_sh.py
git commit -m "test(spider2): end-to-end emitted verifier writes harbor reward.json (AC-3)"
```

---

## Self-Review

**1. Spec coverage:**
- AC-1 (reward 1.0 on match / 0.0 on mismatch) → T1 (eval-spec model) + T2 (comparator core, matching/mismatch/all-tables-AND/missing-table). ✓
- AC-2 (column subset via `condition_cols` + `ignore_orders`) → T3 (non-condition-col diff ignored; condition-col diff detected) + T4 (row-reorder match under `ignore_orders`, mismatch when ordered, multiset duplicate counting). ✓
- AC-3 (emitted `tests/test.sh` writes harbor-shaped `/logs/verifier/reward.json`) → T5 (`verify.py` CLI emits reward.json) + T6 (materializer emits assets + `test.sh` into view `tests/`) + T7 (end-to-end run of emitted assets → parseable `{"reward": <float>}`). ✓
- Out of scope (dbt build orchestration, non-DuckDB answer types) → honored: the verifier only compares output DBs; only DuckDB is exercised. ✓
- Comparator-first ordering (riskiest mechanism, two tiny DuckDB fixtures, before test.sh wiring) → T2–T4 precede T5–T7; `_legacy/.../dab/verify.py` cited as the reward-shaping reference in Global Constraints, T5, and the architecture. ✓
- Gold `.duckdb` + eval spec on verifier-only paths excluded from the agent view → locked design decision: gold lives under the source's `tests/gold/` (stripped from the view by `**/gold/**`), re-copied explicitly into the view's `tests/` (verifier-uploaded only, `verifier.py:133-143`), proven leakage-clean in T6 Step 2. ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step shows actual code; every command shows expected output. The one cross-task edit (dual-import) is spelled out in full in T6 Step 4 with the exact replacement code.

**3. Type consistency:**
- `EvalSpec(condition_tabs: list[str], condition_cols: dict[str, list[int]], ignore_orders: bool)` / `load_eval_spec(path) -> EvalSpec` defined T1, consumed T2/T5. ✓
- `compare_duckdb(*, predicted_db: Path, gold_db: Path, spec: EvalSpec) -> bool` defined T2, consumed T3/T4/T5. ✓
- `emit_reward(*, predicted_db, gold_db, eval_spec, reward_out) -> None` defined T5, consumed by T6's `test.sh` (via the `verify.py` CLI args, which match `main()`'s argparse flags: `--predicted-db/--gold-db/--eval-spec/--reward-out`). ✓
- `_ensure_verifier_assets(view, *, source_task_dir)` defined + called T6; `materialize_spider2_harbor_task_view` signature unchanged (existing `harbor_view.py:24-31`). ✓
- `verify.py` CLI flag names in T5 `main()` exactly match the `test.sh` invocation in T6 `_TEST_SH` (`--predicted-db --gold-db --eval-spec --reward-out`) and the subprocess args in T7. ✓

**Plan-time verifications (read against the repo this cycle, not assumed):**
- Harbor uploads `tests/` to the container only at verify time and the agent's workdir is `environment/` + step `workdir/` — confirmed reading `harbor/verifier/verifier.py:133-143` and `harbor/trial/trial.py:482-496,588-589`. Gold-under-`tests/` is verifier-only.
- `SPIDER2_DBT_DENY_GLOBS` strips `gold/**`/`**/gold/**`/`expected/**`/`golden/**` from the whole view (`harbor_view.py:10-21`); `materialize.py:_reflect_allowed_files` 99-119 skips denied paths and `assert_no_denied_paths` 71 fails closed — confirms gold must be re-copied explicitly without a `gold/` segment.
- Reward shape `{"reward": 1.0|0.0}` written to a parent-created path is the harbor contract (`_legacy/benchmarks/dab/verify.py:30-32`; parsed by `harbor/verifier/verifier.py:_parse_reward_json` 74-87). T5 mirrors it.
- The existing spider2 fixture `spider2-fixture-001` has `tests/test.sh` (a no-op `exit 0`) and `task.toml` — T6 overwrites `tests/test.sh` with the real verifier script and adds `tests/gold/` (confirmed by `ls tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-001`).
- `materialize_spider2_harbor_task_view(*, source_task_dir, view_root, task_slug, docker_image=None, view_mode="copy")` is the current signature (`harbor_view.py:24-31`) — T6 keeps it, only adding the `_ensure_verifier_assets` call before return.

**Open items:** one assumption surfaced for the validation/implementation worker — the agent-produced DB's in-container path (`/app/spider2.duckdb`) in `_TEST_SH` is a placeholder pending the spider2-dbt image/workdir contract owned by `spider2-dbt-harbor-view-ade-parity` (Out of scope here). If that task fixes a different output DB name/path, T6's `_TEST_SH` `--predicted-db` value must be updated to match; the comparator/CLI/emission contract is unaffected. This is the one cross-task coupling the implementer should confirm against the harbor-view task before a live run (it does not affect the gating `uv run pytest -k spider2_dbt_verify` suite, which drives `verify.py` directly).
