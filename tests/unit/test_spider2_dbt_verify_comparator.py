# ABOUTME: spider2-dbt duckdb_match comparator + eval-spec unit tests (AC-1/AC-2).
# ABOUTME: Faithful to Spider2 eval_utils: column-containment, 1e-2 tolerance, per-table lists.
import json
from pathlib import Path

import duckdb
import pytest

from razorback.benchmarks.spider2_dbt.duckdb_match import compare_duckdb
from razorback.benchmarks.spider2_dbt.eval_spec import EvalSpec, load_eval_spec


# --------------------------------------------------------------------------
# eval-spec loader (real Spider2 evaluation.parameters shape)
# --------------------------------------------------------------------------


def test_spider2_dbt_verify_loads_eval_spec_real_shape(tmp_path: Path):
    # Real Spider2 gold line: instance_id + evaluation.parameters with
    # per-table List[List[int]] condition_cols and List[bool] ignore_orders.
    spec_path = tmp_path / "spider2_eval.jsonl"
    spec_path.write_text(
        json.dumps(
            {
                "instance_id": "task-001",
                "evaluation": {
                    "func": "duckdb_match",
                    "parameters": {
                        "gold": "gold.duckdb",
                        "condition_tabs": ["orders", "customers"],
                        "condition_cols": [[0, 2], []],
                        "ignore_orders": [True, False],
                    },
                },
            }
        )
        + "\n"
    )
    spec = load_eval_spec(spec_path)
    assert spec == EvalSpec(
        gold="gold.duckdb",
        condition_tabs=["orders", "customers"],
        condition_cols=[[0, 2], []],
        ignore_orders=[True, False],
    )


def test_spider2_dbt_verify_load_eval_spec_parses_gold_basename(tmp_path: Path):
    # Real Spider2 tasks name the gold DB per task (playbook.duckdb, tpch.duckdb,
    # ...). load_eval_spec must carry parameters.gold through so the verifier
    # scores against the NAMED file, not a hardcoded gold.duckdb.
    spec_path = tmp_path / "spider2_eval.jsonl"
    spec_path.write_text(
        json.dumps(
            {
                "instance_id": "playbook001",
                "evaluation": {
                    "func": "duckdb_match",
                    "parameters": {
                        "gold": "playbook.duckdb",
                        "condition_tabs": ["orders"],
                    },
                },
            }
        )
        + "\n"
    )
    spec = load_eval_spec(spec_path)
    assert spec.gold == "playbook.duckdb"


def test_spider2_dbt_verify_load_eval_spec_missing_gold_in_wrapped_spec_raises(
    tmp_path: Path,
):
    # A real wrapped (evaluation.func == duckdb_match) gold line MUST name its
    # gold DB. A missing/empty parameters.gold is a schema drift the verifier
    # cannot score against the right file -> fail closed.
    spec_path = tmp_path / "spider2_eval.jsonl"
    spec_path.write_text(
        json.dumps(
            {
                "instance_id": "t",
                "evaluation": {
                    "func": "duckdb_match",
                    "parameters": {"condition_tabs": ["orders"]},
                },
            }
        )
        + "\n"
    )
    with pytest.raises(ValueError):
        load_eval_spec(spec_path)


def test_spider2_dbt_verify_eval_spec_defaults(tmp_path: Path):
    # Missing condition_cols/ignore_orders default per-table to []/False
    # (mirrors Spider2 duckdb_match's None-handling).
    spec_path = tmp_path / "spider2_eval.jsonl"
    spec_path.write_text(
        json.dumps(
            {
                "evaluation": {
                    "func": "duckdb_match",
                    "parameters": {"gold": "g.duckdb", "condition_tabs": ["t1", "t2"]},
                }
            }
        )
        + "\n"
    )
    spec = load_eval_spec(spec_path)
    assert spec.condition_tabs == ["t1", "t2"]
    assert spec.condition_cols == [[], []]
    assert spec.ignore_orders == [False, False]


def test_spider2_dbt_verify_eval_spec_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        EvalSpec(condition_tabs=["a", "b"], condition_cols=[[0]], ignore_orders=[True])


# --------------------------------------------------------------------------
# Fail-closed: a zero-table / malformed gold spec MUST NOT score as a match
# (cycle-2 B1). compare_duckdb returns True on an empty condition_tabs loop,
# so an empty spec would silently award 1.0 -> reject it at load/construct time.
# --------------------------------------------------------------------------


def test_spider2_dbt_verify_eval_spec_rejects_empty_condition_tabs():
    # A zero-table spec is the fail-open hazard: compare_duckdb's AND-loop never
    # runs and returns True. EvalSpec must refuse to construct one.
    with pytest.raises(ValueError):
        EvalSpec(condition_tabs=[])


def test_spider2_dbt_verify_load_eval_spec_empty_file_raises(tmp_path: Path):
    # An empty / truncated spider2_eval.jsonl must NOT yield a zero-table spec.
    spec_path = tmp_path / "spider2_eval.jsonl"
    spec_path.write_text("")
    with pytest.raises(ValueError):
        load_eval_spec(spec_path)


def test_spider2_dbt_verify_load_eval_spec_missing_condition_tabs_raises(tmp_path: Path):
    # evaluation.parameters present but no condition_tabs -> fail closed.
    spec_path = tmp_path / "spider2_eval.jsonl"
    spec_path.write_text(
        json.dumps(
            {
                "instance_id": "t",
                "evaluation": {"func": "duckdb_match", "parameters": {"gold": "g.duckdb"}},
            }
        )
        + "\n"
    )
    with pytest.raises(ValueError):
        load_eval_spec(spec_path)


def test_spider2_dbt_verify_load_eval_spec_wrong_func_raises(tmp_path: Path):
    # A non-duckdb_match evaluation func is a schema drift we must not score.
    spec_path = tmp_path / "spider2_eval.jsonl"
    spec_path.write_text(
        json.dumps(
            {
                "instance_id": "t",
                "evaluation": {
                    "func": "string_match",
                    "parameters": {"gold": "g.duckdb", "condition_tabs": ["orders"]},
                },
            }
        )
        + "\n"
    )
    with pytest.raises(ValueError):
        load_eval_spec(spec_path)


def test_spider2_dbt_verify_load_eval_spec_missing_evaluation_raises(tmp_path: Path):
    # A line with no evaluation wrapper and no condition_tabs must fail closed
    # rather than fall through to a zero-table (match-everything) spec.
    spec_path = tmp_path / "spider2_eval.jsonl"
    spec_path.write_text(json.dumps({"instance_id": "t"}) + "\n")
    with pytest.raises(ValueError):
        load_eval_spec(spec_path)


# --------------------------------------------------------------------------
# comparator fixtures
# --------------------------------------------------------------------------


def _build_db(path, tables: dict):
    """tables: name -> (column_names, column_types, rows). Builds a .duckdb."""
    con = duckdb.connect(str(path))
    try:
        for name, (cols, types, rows) in tables.items():
            col_defs = ", ".join(f"{c} {t}" for c, t in zip(cols, types))
            con.execute(f"CREATE TABLE {name} ({col_defs})")
            if rows:
                placeholders = ", ".join(
                    ["(" + ", ".join(["?"] * len(cols)) + ")"] * len(rows)
                )
                flat = [v for row in rows for v in row]
                con.execute(f"INSERT INTO {name} VALUES {placeholders}", flat)
    finally:
        con.close()


def _ints(names, rows):
    return (names, ["INTEGER"] * len(names), rows)


def _compare(tmp_path, *, pred, gold, spec):
    _build_db(tmp_path / "pred.duckdb", pred)
    _build_db(tmp_path / "gold.duckdb", gold)
    return compare_duckdb(
        predicted_db=tmp_path / "pred.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        spec=spec,
    )


# --------------------------------------------------------------------------
# AC-1: 1.0 on match, 0.0 on mismatch
# --------------------------------------------------------------------------


def test_spider2_dbt_verify_matching_db_scores_true(tmp_path):
    tables = {"orders": _ints(["a", "b"], [(1, 2), (3, 4)])}
    spec = EvalSpec(condition_tabs=["orders"])
    assert _compare(tmp_path, pred=tables, gold=tables, spec=spec) is True


def test_spider2_dbt_verify_mismatched_db_scores_false(tmp_path):
    spec = EvalSpec(condition_tabs=["orders"])
    assert (
        _compare(
            tmp_path,
            pred={"orders": _ints(["a", "b"], [(1, 2), (9, 9)])},
            gold={"orders": _ints(["a", "b"], [(1, 2), (3, 4)])},
            spec=spec,
        )
        is False
    )


def test_spider2_dbt_verify_all_tables_must_match(tmp_path):
    # One table matches, the other differs -> overall False (AND across tables).
    spec = EvalSpec(condition_tabs=["t1", "t2"])
    assert (
        _compare(
            tmp_path,
            pred={"t1": _ints(["a"], [(1,)]), "t2": _ints(["a"], [(2,)])},
            gold={"t1": _ints(["a"], [(1,)]), "t2": _ints(["a"], [(99,)])},
            spec=spec,
        )
        is False
    )


def test_spider2_dbt_verify_missing_predicted_table_scores_false(tmp_path):
    # Spider2 wraps the predicted-table fetch in try/except -> 0 on a
    # missing/unreadable table, not a crash.
    spec = EvalSpec(condition_tabs=["orders"])
    assert (
        _compare(
            tmp_path,
            pred={"other": _ints(["a"], [(1,)])},
            gold={"orders": _ints(["a"], [(1,)])},
            spec=spec,
        )
        is False
    )


# --------------------------------------------------------------------------
# AC-2 + reviewer's verdict-flipping cases
# --------------------------------------------------------------------------


def test_spider2_dbt_verify_float_within_tolerance_matches(tmp_path):
    # Reviewer case: a numeric column-vector within math.isclose(abs_tol=1e-2)
    # must still match. Row-tuple exact-== would have flipped this to a 0.
    spec = EvalSpec(condition_tabs=["m"])
    assert (
        _compare(
            tmp_path,
            pred={"m": (["v"], ["DOUBLE"], [(1.005,), (2.0,)])},
            gold={"m": (["v"], ["DOUBLE"], [(1.0,), (2.0,)])},
            spec=spec,
        )
        is True
    )


def test_spider2_dbt_verify_float_beyond_tolerance_mismatches(tmp_path):
    # Just outside 1e-2 -> mismatch (proves the tolerance actually bounds).
    spec = EvalSpec(condition_tabs=["m"])
    assert (
        _compare(
            tmp_path,
            pred={"m": (["v"], ["DOUBLE"], [(1.5,)])},
            gold={"m": (["v"], ["DOUBLE"], [(1.0,)])},
            spec=spec,
        )
        is False
    )


def test_spider2_dbt_verify_column_reorder_matches_by_containment(tmp_path):
    # Reviewer case: pred has the SAME column data in a DIFFERENT column order.
    # Column-containment matches every gold column to SOME pred column, so a
    # reordered pred is still a match. Positional row-tuple == would have failed.
    spec = EvalSpec(condition_tabs=["t"])
    assert (
        _compare(
            tmp_path,
            pred={"t": _ints(["b", "a"], [(10, 1), (20, 2)])},
            gold={"t": _ints(["a", "b"], [(1, 10), (2, 20)])},
            spec=spec,
        )
        is True
    )


def test_spider2_dbt_verify_extra_pred_columns_tolerated(tmp_path):
    # Reviewer case: pred carries an EXTRA column not present in gold. Since
    # only gold's columns must be contained in pred, the extra is tolerated.
    spec = EvalSpec(condition_tabs=["t"])
    assert (
        _compare(
            tmp_path,
            pred={"t": _ints(["a", "extra"], [(1, 999), (2, 888)])},
            gold={"t": _ints(["a"], [(1,), (2,)])},
            spec=spec,
        )
        is True
    )


def test_spider2_dbt_verify_condition_cols_restricts_gold(tmp_path):
    # condition_cols=[[0]] restricts gold to column 0 only, so a difference in
    # gold column 1 is NOT compared -> still a match.
    spec = EvalSpec(condition_tabs=["orders"], condition_cols=[[0]])
    assert (
        _compare(
            tmp_path,
            pred={"orders": _ints(["a"], [(1,), (2,)])},
            gold={"orders": _ints(["a", "b"], [(1, 7), (2, 8)])},
            spec=spec,
        )
        is True
    )


def test_spider2_dbt_verify_condition_col_diff_detected(tmp_path):
    # condition_cols=[[0,1]] -> gold column 1 IS compared; its values are not
    # contained in any pred column -> mismatch. Proves subsetting restricts
    # without dropping everything.
    spec = EvalSpec(condition_tabs=["orders"], condition_cols=[[0, 1]])
    assert (
        _compare(
            tmp_path,
            pred={"orders": _ints(["a", "b"], [(1, 100), (2, 200)])},
            gold={"orders": _ints(["a", "b"], [(1, 7), (2, 8)])},
            spec=spec,
        )
        is False
    )


def test_spider2_dbt_verify_row_reorder_matches_when_ignore_orders(tmp_path):
    # Per-column ignore_order sorts each column-vector before compare.
    spec = EvalSpec(condition_tabs=["orders"], ignore_orders=[True])
    assert (
        _compare(
            tmp_path,
            pred={"orders": _ints(["a"], [(2,), (1,)])},
            gold={"orders": _ints(["a"], [(1,), (2,)])},
            spec=spec,
        )
        is True
    )


def test_spider2_dbt_verify_row_reorder_mismatches_when_ordered(tmp_path):
    # ignore_orders=False -> per-column positional compare; reordered -> mismatch.
    spec = EvalSpec(condition_tabs=["orders"], ignore_orders=[False])
    assert (
        _compare(
            tmp_path,
            pred={"orders": _ints(["a"], [(2,), (1,)])},
            gold={"orders": _ints(["a"], [(1,), (2,)])},
            spec=spec,
        )
        is False
    )


def test_spider2_dbt_verify_multi_table_gold_line_mismatch(tmp_path):
    # Real multi-table gold line: table 1 matches, table 2's condition column
    # genuinely differs -> overall 0.0 (proves the per-table lists are honored,
    # not a single flat dict + single bool).
    spec_path = tmp_path / "spider2_eval.jsonl"
    spec_path.write_text(
        json.dumps(
            {
                "instance_id": "multi-001",
                "evaluation": {
                    "func": "duckdb_match",
                    "parameters": {
                        "gold": "gold.duckdb",
                        "condition_tabs": ["orders", "customers"],
                        "condition_cols": [[0], [0]],
                        "ignore_orders": [True, False],
                    },
                },
            }
        )
        + "\n"
    )
    spec = load_eval_spec(spec_path)
    pred = {
        "orders": _ints(["id"], [(2,), (1,)]),  # reordered, ignore_orders[0]=True -> ok
        "customers": _ints(["id"], [(7,)]),  # differs from gold -> table 2 fails
    }
    gold = {
        "orders": _ints(["id"], [(1,), (2,)]),
        "customers": _ints(["id"], [(99,)]),
    }
    assert _compare(tmp_path, pred=pred, gold=gold, spec=spec) is False
