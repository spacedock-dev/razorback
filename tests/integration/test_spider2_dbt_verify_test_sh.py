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
    / "fixtures"
    / "spider2_dbt"
    / "harbor_task_minimal"
    / "spider2-fixture-001"
)


def _build_predicted_matching_gold(path: Path) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE TABLE orders (id INTEGER, amount INTEGER)")
        # rows reordered vs gold; ignore_orders=True -> still a match
        con.executemany("INSERT INTO orders VALUES (?, ?)", [(2, 200), (1, 100)])
    finally:
        con.close()


def test_spider2_dbt_verify_emitted_assets_write_reward_json(tmp_path):
    view = materialize_spider2_harbor_task_view(
        source_task_dir=_SOURCE,
        view_root=tmp_path / "views",
        task_slug="spider2-fixture-001",
    )
    tests = view / "tests"
    predicted = tmp_path / "spider2-fixture-001.duckdb"
    _build_predicted_matching_gold(predicted)
    reward_out = tmp_path / "logs" / "verifier" / "reward.json"

    result = subprocess.run(
        [
            sys.executable,
            str(tests / "verify.py"),
            "--predicted-db",
            str(predicted),
            "--gold-db",
            str(tests / "gold.duckdb"),
            "--eval-spec",
            str(tests / "spider2_eval.jsonl"),
            "--reward-out",
            str(reward_out),
        ],
        capture_output=True,
        text=True,
        cwd=str(tests),  # flat-import fallback resolves duckdb_match/eval_spec here
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(reward_out.read_text())
    assert set(payload) == {"reward"}
    assert isinstance(payload["reward"], float)
    assert payload["reward"] == 1.0  # reordered rows match under ignore_orders


def test_spider2_dbt_verify_emitted_test_sh_is_runnable(tmp_path):
    # Proves the emitted test.sh is a valid shell script with the right shape:
    # it references verify.py, the resolved /app/<db_name>.duckdb predicted path,
    # and the harbor reward path. A full container run is out of scope (no docker
    # in unit/integration); this checks the contract.
    view = materialize_spider2_harbor_task_view(
        source_task_dir=_SOURCE,
        view_root=tmp_path / "v",
        task_slug="spider2-fixture-001",
    )
    text = (view / "tests" / "test.sh").read_text()
    assert "verify.py" in text
    assert "/logs/verifier/reward.json" in text
    # RIDER: predicted path is the resolver's /app/<db_name>.duckdb, not hardcoded
    assert "/app/spider2-fixture-001.duckdb" in text
    assert "/app/spider2.duckdb" not in text
    # the script is syntactically valid sh
    check = subprocess.run(
        ["sh", "-n", str(view / "tests" / "test.sh")],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stderr
