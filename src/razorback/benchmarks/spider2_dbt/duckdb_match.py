# ABOUTME: spider2-dbt comparator faithfully reproducing Spider2 eval_utils.duckdb_match.
# ABOUTME: Column-containment over column-vectors, math.isclose(1e-2), AND across tables.
# Depends ONLY on duckdb (the one library the verify-time image is guaranteed to
# have — the build-time preflight already imports it); no pandas, so the emitted
# verifier cannot crash-on-import in a task image that ships dbt-duckdb but not pandas.
from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

import duckdb

try:
    from razorback.benchmarks.spider2_dbt.eval_spec import EvalSpec
except ModuleNotFoundError:  # running flat from /tests in the verifier container
    from eval_spec import EvalSpec  # type: ignore[no-redef]

# Spider2 eval_utils.compare_pandas_table numeric tolerance.
_TOLERANCE = 1e-2


def _isna(x) -> bool:
    """stdlib stand-in for pandas.isna over scalar cells fetched from DuckDB.

    DuckDB returns SQL NULL as Python ``None``; a float ``NaN`` is the only other
    NA-like scalar. Mirrors Spider2's ``pd.isna(...)`` NaN==NaN handling.
    """
    return x is None or (isinstance(x, float) and math.isnan(x))


def _vectors_match(v1, v2, *, tol: float = _TOLERANCE, ignore_order: bool = False) -> bool:
    """Port of Spider2 eval_utils.compare_pandas_table.vectors_match.

    Compares two column-vectors element-wise: NA==NA, numerics via
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
            if _isna(a) and _isna(b):
                continue
            elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if not math.isclose(float(a), float(b), abs_tol=tol):
                    return False
            elif a != b:
                return False
        return True
    except Exception:
        return False


def _compare_table(
    pred_cols: list[list],
    gold_cols: list[list],
    *,
    condition_cols: list[int],
    ignore_order: bool,
) -> bool:
    """Port of Spider2 eval_utils.compare_pandas_table.

    Column-CONTAINMENT (not positional row equality): restrict gold to
    ``condition_cols`` (all columns when empty), then require that EVERY gold
    column-vector matches SOME pred column-vector. Extra pred columns are
    therefore tolerated. Inputs are already transposed to column-vectors.
    """
    if condition_cols:
        gold_vecs = [gold_cols[c] for c in condition_cols]
    else:
        gold_vecs = gold_cols

    for gold_vec in gold_vecs:
        if not any(
            _vectors_match(gold_vec, pred_vec, ignore_order=ignore_order)
            for pred_vec in pred_cols
        ):
            return False
    return True


def _quote_ident(name: str) -> str:
    """Quote a SQL identifier, doubling embedded double-quotes.

    ``condition_tabs`` table names come from the external eval spec, so a value
    like ``realt"; select 999; --`` would otherwise break out of the quoted
    identifier and DuckDB would execute the injected statement, letting a hostile
    spec rig gold/pred fetches to return identical rows and award reward 1.0.
    Doubling keeps the value a single (bogus) identifier; it then fails to
    resolve and the fetch raises -> emit_reward scores 0 (fail-closed).
    """
    return '"' + name.replace('"', '""') + '"'


def _fetch_columns(con: duckdb.DuckDBPyConnection, table: str) -> list[list]:
    """``SELECT * FROM `table``` as a list of column-vectors (transposed rows).

    Replaces Spider2's ``fetchdf().transpose().values.tolist()``: DuckDB's
    ``.fetchall()`` yields native Python scalars in row order (NULL -> None),
    and ``.description`` fixes the column count so a zero-row table still
    yields one empty vector per column.
    """
    cur = con.execute(f"SELECT * FROM {_quote_ident(table)}")
    rows = cur.fetchall()
    ncols = len(cur.description)
    return [[_normalize(row[j]) for row in rows] for j in range(ncols)]


def _normalize(v):
    """Mirror Spider2's pandas fetchdf() DECIMAL->float64 coercion.

    DuckDB native fetchall() returns ``decimal.Decimal`` for DECIMAL/NUMERIC,
    but Decimal is ``numbers.Number`` yet NOT ``numbers.Real``, so it would skip
    ``_vectors_match``'s tolerance branch and a within-1e-2 DECIMAL match would
    wrongly score 0. Normalize to float in one place so downstream compares see
    the same scalar types Spider2's pandas path produced.
    """
    return float(v) if isinstance(v, Decimal) else v


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
        gold_tables = [_fetch_columns(gold_con, t) for t in spec.condition_tabs]
    finally:
        gold_con.close()

    pred_con = duckdb.connect(str(predicted_db), read_only=True)
    try:
        try:
            pred_tables = [_fetch_columns(pred_con, t) for t in spec.condition_tabs]
        except Exception:
            return False
    finally:
        pred_con.close()

    for i, (gold_cols, pred_cols) in enumerate(zip(gold_tables, pred_tables)):
        if not _compare_table(
            pred_cols,
            gold_cols,
            condition_cols=spec.condition_cols[i],
            ignore_order=spec.ignore_orders[i],
        ):
            return False
    return True
