# ABOUTME: AC-3 — ade-bench summary.json contains a numeric `score` field.
# ABOUTME: score = mean reward across all trials (one task per spec is the M7 acceptance shape).

import json

import pytest

from razorback.benchmarks.ade_bench.aggregate import aggregate_synthetic


def test_score_is_mean_reward_across_trials(tmp_path):
    rows = [
        {"task_name": "ade-bench-fixture-001__a", "reward": 1.0},
        {"task_name": "ade-bench-fixture-001__b", "reward": 0.0},
        {"task_name": "ade-bench-fixture-001__c", "reward": 1.0},
    ]
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    data = json.loads(out.read_text())
    assert data["summary_version"] == 1
    assert isinstance(data["score"], float)
    assert data["score"] == pytest.approx(2 / 3)
    assert data["n_trials"] == 3
    assert data["n_correct"] == 2
    assert data["benchmark_kind"] == "ade-bench"


def test_score_is_zero_when_no_trials_pass(tmp_path):
    rows = [
        {"task_name": "x__a", "reward": 0.0},
        {"task_name": "x__b", "reward": 0.0},
    ]
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    data = json.loads(out.read_text())
    assert data["score"] == 0.0
    assert data["n_correct"] == 0


def test_score_handles_missing_reward(tmp_path):
    rows = [
        {"task_name": "x__a", "reward": 1.0},
        {"task_name": "x__b", "reward": None},
    ]
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    data = json.loads(out.read_text())
    assert data["score"] == pytest.approx(0.5)
    assert data["n_trials"] == 2


def test_summary_json_shape_is_minimal(tmp_path):
    """ade-bench summary.json must NOT carry DAB-only fields (datasets, queries)."""
    rows = [{"task_name": "x__a", "reward": 1.0}]
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    data = json.loads(out.read_text())
    assert "datasets" not in data
    assert "queries" not in data
    assert "stratified_pass_at_1" not in data
