# ABOUTME: spider2-dbt duckdb_match comparator + eval-spec unit tests (AC-1/AC-2).
# ABOUTME: Builds tiny in-test DuckDB fixtures and drives the comparator directly.
import json
from pathlib import Path

import duckdb

from razorback.benchmarks.spider2_dbt.duckdb_match import compare_duckdb
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


def _build_db(path, tables: dict[str, tuple[list[str], list[tuple]]]):
    """tables: name -> (column_names, rows). Builds a tiny .duckdb file."""
    con = duckdb.connect(str(path))
    try:
        for name, (cols, rows) in tables.items():
            col_defs = ", ".join(f"{c} INTEGER" for c in cols)
            con.execute(f"CREATE TABLE {name} ({col_defs})")
            if rows:
                placeholders = ", ".join(
                    ["(" + ", ".join(["?"] * len(cols)) + ")"] * len(rows)
                )
                flat = [v for row in rows for v in row]
                con.execute(f"INSERT INTO {name} VALUES {placeholders}", flat)
    finally:
        con.close()


def test_spider2_dbt_verify_matching_db_scores_true(tmp_path):
    tables = {"orders": (["a", "b"], [(1, 2), (3, 4)])}
    _build_db(tmp_path / "pred.duckdb", tables)
    _build_db(tmp_path / "gold.duckdb", tables)
    spec = EvalSpec(condition_tabs=["orders"], condition_cols={}, ignore_orders=False)
    assert (
        compare_duckdb(
            predicted_db=tmp_path / "pred.duckdb",
            gold_db=tmp_path / "gold.duckdb",
            spec=spec,
        )
        is True
    )


def test_spider2_dbt_verify_mismatched_db_scores_false(tmp_path):
    _build_db(tmp_path / "pred.duckdb", {"orders": (["a", "b"], [(1, 2), (9, 9)])})
    _build_db(tmp_path / "gold.duckdb", {"orders": (["a", "b"], [(1, 2), (3, 4)])})
    spec = EvalSpec(condition_tabs=["orders"], condition_cols={}, ignore_orders=False)
    assert (
        compare_duckdb(
            predicted_db=tmp_path / "pred.duckdb",
            gold_db=tmp_path / "gold.duckdb",
            spec=spec,
        )
        is False
    )


def test_spider2_dbt_verify_all_tables_must_match(tmp_path):
    # One table matches, the other differs -> overall False (AND across tables).
    pred = {"t1": (["a"], [(1,)]), "t2": (["a"], [(2,)])}
    gold = {"t1": (["a"], [(1,)]), "t2": (["a"], [(99,)])}
    _build_db(tmp_path / "pred.duckdb", pred)
    _build_db(tmp_path / "gold.duckdb", gold)
    spec = EvalSpec(condition_tabs=["t1", "t2"], condition_cols={}, ignore_orders=False)
    assert (
        compare_duckdb(
            predicted_db=tmp_path / "pred.duckdb",
            gold_db=tmp_path / "gold.duckdb",
            spec=spec,
        )
        is False
    )


def test_spider2_dbt_verify_missing_predicted_table_scores_false(tmp_path):
    _build_db(tmp_path / "pred.duckdb", {"other": (["a"], [(1,)])})
    _build_db(tmp_path / "gold.duckdb", {"orders": (["a"], [(1,)])})
    spec = EvalSpec(condition_tabs=["orders"], condition_cols={}, ignore_orders=False)
    assert (
        compare_duckdb(
            predicted_db=tmp_path / "pred.duckdb",
            gold_db=tmp_path / "gold.duckdb",
            spec=spec,
        )
        is False
    )


def test_spider2_dbt_verify_non_condition_col_diff_ignored(tmp_path):
    # Column index 1 ("b") differs, but only index 0 ("a") is a condition_col
    # -> still a match (the non-condition column is not compared).
    _build_db(tmp_path / "pred.duckdb", {"orders": (["a", "b"], [(1, 100), (2, 200)])})
    _build_db(tmp_path / "gold.duckdb", {"orders": (["a", "b"], [(1, 7), (2, 8)])})
    spec = EvalSpec(
        condition_tabs=["orders"], condition_cols={"orders": [0]}, ignore_orders=False
    )
    assert (
        compare_duckdb(
            predicted_db=tmp_path / "pred.duckdb",
            gold_db=tmp_path / "gold.duckdb",
            spec=spec,
        )
        is True
    )


def test_spider2_dbt_verify_condition_col_diff_detected(tmp_path):
    # The SAME column data, but now index 1 ("b") IS a condition_col and differs
    # -> mismatch. Proves the subset actually restricts, not drops everything.
    _build_db(tmp_path / "pred.duckdb", {"orders": (["a", "b"], [(1, 100), (2, 200)])})
    _build_db(tmp_path / "gold.duckdb", {"orders": (["a", "b"], [(1, 7), (2, 8)])})
    spec = EvalSpec(
        condition_tabs=["orders"], condition_cols={"orders": [0, 1]}, ignore_orders=False
    )
    assert (
        compare_duckdb(
            predicted_db=tmp_path / "pred.duckdb",
            gold_db=tmp_path / "gold.duckdb",
            spec=spec,
        )
        is False
    )


def test_spider2_dbt_verify_row_reorder_matches_when_ignore_orders(tmp_path):
    _build_db(tmp_path / "pred.duckdb", {"orders": (["a"], [(2,), (1,)])})
    _build_db(tmp_path / "gold.duckdb", {"orders": (["a"], [(1,), (2,)])})
    spec = EvalSpec(condition_tabs=["orders"], condition_cols={}, ignore_orders=True)
    assert (
        compare_duckdb(
            predicted_db=tmp_path / "pred.duckdb",
            gold_db=tmp_path / "gold.duckdb",
            spec=spec,
        )
        is True
    )


def test_spider2_dbt_verify_row_reorder_mismatches_when_ordered(tmp_path):
    _build_db(tmp_path / "pred.duckdb", {"orders": (["a"], [(2,), (1,)])})
    _build_db(tmp_path / "gold.duckdb", {"orders": (["a"], [(1,), (2,)])})
    spec = EvalSpec(condition_tabs=["orders"], condition_cols={}, ignore_orders=False)
    assert (
        compare_duckdb(
            predicted_db=tmp_path / "pred.duckdb",
            gold_db=tmp_path / "gold.duckdb",
            spec=spec,
        )
        is False
    )


def test_spider2_dbt_verify_ignore_orders_still_counts_duplicates(tmp_path):
    # ignore_orders is a multiset compare, not a set compare: duplicate counts
    # must still match (Counter equality, not set equality).
    _build_db(tmp_path / "pred.duckdb", {"orders": (["a"], [(1,), (1,)])})
    _build_db(tmp_path / "gold.duckdb", {"orders": (["a"], [(1,)])})
    spec = EvalSpec(condition_tabs=["orders"], condition_cols={}, ignore_orders=True)
    assert (
        compare_duckdb(
            predicted_db=tmp_path / "pred.duckdb",
            gold_db=tmp_path / "gold.duckdb",
            spec=spec,
        )
        is False
    )
