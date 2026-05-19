# ABOUTME: M6 — pair two per_trial_outcomes.json files by (dataset, query_id, trial_index).

import json
from pathlib import Path

import pytest

from razorback.diff.pairing import load_run_outcomes, pair_outcomes


def _write(path: Path, trials: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"outcomes_version": 1, "trials": trials}))


def test_load_run_outcomes_reads_sidecar(tmp_path: Path) -> None:
    p = tmp_path / "run-1" / "per_trial_outcomes.json"
    _write(p, [{"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0}])
    outcomes = load_run_outcomes(tmp_path / "run-1")
    assert outcomes == [{"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0}]


def test_load_run_outcomes_refuses_unknown_version(tmp_path: Path) -> None:
    p = tmp_path / "run-1" / "per_trial_outcomes.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"outcomes_version": 999, "trials": []}))
    with pytest.raises(ValueError, match=r"outcomes_version"):
        load_run_outcomes(tmp_path / "run-1")


def test_pair_outcomes_matches_paired_keys() -> None:
    a = [
        {"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds", "query_id": 1, "trial_index": 1, "reward": 0.0},
    ]
    b = [
        {"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 0.0},
        {"dataset": "ds", "query_id": 1, "trial_index": 1, "reward": 1.0},
    ]
    paired = pair_outcomes(a, b)
    assert len(paired) == 2
    p0 = next(p for p in paired if p["trial_index"] == 0)
    assert (p0["a_reward"], p0["b_reward"]) == (1.0, 0.0)
    p1 = next(p for p in paired if p["trial_index"] == 1)
    assert (p1["a_reward"], p1["b_reward"]) == (0.0, 1.0)


def test_pair_outcomes_refuses_on_missing_key() -> None:
    a = [{"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0}]
    b = [{"dataset": "ds", "query_id": 1, "trial_index": 1, "reward": 1.0}]
    with pytest.raises(ValueError, match=r"(missing|key|A-only|B-only)"):
        pair_outcomes(a, b)
