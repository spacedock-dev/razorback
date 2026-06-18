# ABOUTME: spider2-dbt comparator reproducing Spider2 eval_utils.duckdb_match.
# ABOUTME: per-table SELECT *, restrict to condition_cols, ignore_orders, AND across tables.
from __future__ import annotations

from collections import Counter
from pathlib import Path

import duckdb

try:
    from razorback.benchmarks.spider2_dbt.eval_spec import EvalSpec
except ModuleNotFoundError:  # running flat from /tests in the verifier container
    from eval_spec import EvalSpec  # type: ignore[no-redef]


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


def _rows_match(
    pred: list[tuple], gold: list[tuple], *, ignore_orders: bool
) -> bool:
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
