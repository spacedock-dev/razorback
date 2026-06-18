# ABOUTME: spider2-dbt verify.py CLI + materializer-emission tests (AC-3).
# ABOUTME: emit_reward writes harbor-shaped reward.json; the view carries verifier assets.
import json
from pathlib import Path

import duckdb

from razorback.benchmarks.spider2_dbt.harbor_view import (
    materialize_spider2_harbor_task_view,
)
from razorback.benchmarks.spider2_dbt.verify import emit_reward

_SOURCE = (
    Path(__file__).parent.parent
    / "fixtures"
    / "spider2_dbt"
    / "harbor_task_minimal"
    / "spider2-fixture-001"
)


def _build_db(path, rows):
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE TABLE orders (a INTEGER)")
        con.executemany("INSERT INTO orders VALUES (?)", [(r,) for r in rows])
    finally:
        con.close()


def _spec(path):
    path.write_text(
        json.dumps(
            {"condition_tabs": ["orders"], "condition_cols": {}, "ignore_orders": True}
        )
        + "\n"
    )
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


def test_spider2_dbt_verify_cli_missing_predicted_scores_zero(tmp_path):
    # A predicted DB the agent never produced is a 0.0 reward, not a crash.
    _build_db(tmp_path / "gold.duckdb", [1])
    reward_out = tmp_path / "logs" / "verifier" / "reward.json"
    emit_reward(
        predicted_db=tmp_path / "does-not-exist.duckdb",
        gold_db=tmp_path / "gold.duckdb",
        eval_spec=_spec(tmp_path / "spider2_eval.jsonl"),
        reward_out=reward_out,
    )
    assert json.loads(reward_out.read_text()) == {"reward": 0.0}


def test_spider2_dbt_verify_view_carries_verifier_assets(tmp_path):
    view = materialize_spider2_harbor_task_view(
        source_task_dir=_SOURCE,
        view_root=tmp_path / "views",
        task_slug="spider2-fixture-001",
    )
    tests = view / "tests"
    # comparator + cli + spec modules and gold data are present for the verifier
    for name in (
        "duckdb_match.py",
        "eval_spec.py",
        "verify.py",
        "gold.duckdb",
        "spider2_eval.jsonl",
        "test.sh",
    ):
        assert (tests / name).is_file(), f"missing verifier asset: {name}"
    # test.sh is executable
    assert (tests / "test.sh").stat().st_mode & 0o111
    # leakage-clean: no `gold/` path segment survived in the agent-facing view
    assert not (view / "tests" / "gold").exists()
    assert not list(view.rglob("gold/*"))


def test_spider2_dbt_verify_test_sh_uses_resolved_db_name(tmp_path):
    # RIDER: the emitted test.sh predicted-DB path must come from
    # resolve_spider2_db_name, NOT a hardcoded /app/spider2.duckdb. This
    # fixture ships no profiles.yml / *.duckdb, so the resolver falls back to
    # the task slug -> the predicted path is /app/<slug>.duckdb (a NON-spider2
    # db name), proving the resolver is consumed.
    view = materialize_spider2_harbor_task_view(
        source_task_dir=_SOURCE,
        view_root=tmp_path / "views",
        task_slug="not-spider2-slug",
    )
    test_sh = (view / "tests" / "test.sh").read_text()
    assert "/app/not-spider2-slug.duckdb" in test_sh
    assert "/app/spider2.duckdb" not in test_sh
