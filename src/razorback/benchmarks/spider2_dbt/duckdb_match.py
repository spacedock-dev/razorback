# ABOUTME: spider2-dbt comparator faithfully reproducing Spider2 eval_utils.duckdb_match.
# ABOUTME: Column-containment over transposed column-vectors, math.isclose(1e-2), AND across tables.
from __future__ import annotations

import math
from pathlib import Path

import duckdb
import pandas as pd

try:
    from razorback.benchmarks.spider2_dbt.eval_spec import EvalSpec
except ModuleNotFoundError:  # running flat from /tests in the verifier container
    from eval_spec import EvalSpec  # type: ignore[no-redef]

# Spider2 eval_utils.compare_pandas_table numeric tolerance.
_TOLERANCE = 1e-2


def _vectors_match(v1, v2, *, tol: float = _TOLERANCE, ignore_order: bool = False) -> bool:
    """Port of Spider2 eval_utils.compare_pandas_table.vectors_match.

    Compares two column-vectors element-wise: NaN==NaN, numerics via
    math.isclose(abs_tol=tol), everything else by ``!=``. When ignore_order
    is set, both vectors are sorted first with Spider2's exact key.
    """
    try:
        if ignore_order:
            key = lambda x: (x is None, str(x), isinstance(x, (int, float)))
            v1 = sorted(v1, key=key)
            v2 = sorted(v2, key=key)
        if len(v1) != len(v2):
            return False
        for a, b in zip(v1, v2):
            if pd.isna(a) and pd.isna(b):
                continue
            elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if not math.isclose(float(a), float(b), abs_tol=tol):
                    return False
            elif a != b:
                return False
        return True
    except Exception:
        return False


def _compare_pandas_table(
    pred: pd.DataFrame,
    gold: pd.DataFrame,
    *,
    condition_cols: list[int],
    ignore_order: bool,
) -> bool:
    """Port of Spider2 eval_utils.compare_pandas_table.

    Column-CONTAINMENT (not positional row equality): restrict gold to
    ``condition_cols`` (all columns when empty), transpose both tables to
    column-vectors, and require that EVERY gold column-vector matches SOME
    pred column-vector. Extra pred columns are therefore tolerated.
    """
    if condition_cols:
        gold_cols = gold.iloc[:, condition_cols]
    else:
        gold_cols = gold
    pred_cols = pred

    t_gold_list = gold_cols.transpose().values.tolist()
    t_pred_list = pred_cols.transpose().values.tolist()

    for gold_vec in t_gold_list:
        if not any(
            _vectors_match(gold_vec, pred_vec, ignore_order=ignore_order)
            for pred_vec in t_pred_list
        ):
            return False
    return True


def _fetch_df(con: duckdb.DuckDBPyConnection, table: str) -> pd.DataFrame:
    """SELECT * FROM `table` as a DataFrame (mirrors Spider2 fetchdf())."""
    return con.execute(f'SELECT * FROM "{table}"').fetchdf()


def compare_duckdb(*, predicted_db: Path, gold_db: Path, spec: EvalSpec) -> bool:
    """Faithfully reproduce Spider2 eval_utils.duckdb_match.

    For each table in ``spec.condition_tabs``: load gold + predicted via
    ``SELECT *``, run column-containment with the table's
    ``spec.condition_cols[i]`` / ``spec.ignore_orders[i]``. Overall match is
    the AND across all tables. A missing/unreadable predicted table is a
    mismatch (Spider2 wraps the predicted-table fetch in try/except -> 0).
    """
    gold_con = duckdb.connect(str(gold_db), read_only=True)
    try:
        gold_tables = [_fetch_df(gold_con, t) for t in spec.condition_tabs]
    finally:
        gold_con.close()

    pred_con = duckdb.connect(str(predicted_db), read_only=True)
    try:
        try:
            pred_tables = [_fetch_df(pred_con, t) for t in spec.condition_tabs]
        except Exception:
            return False
    finally:
        pred_con.close()

    for i, (gold_df, pred_df) in enumerate(zip(gold_tables, pred_tables)):
        if not _compare_pandas_table(
            pred_df,
            gold_df,
            condition_cols=spec.condition_cols[i],
            ignore_order=spec.ignore_orders[i],
        ):
            return False
    return True
