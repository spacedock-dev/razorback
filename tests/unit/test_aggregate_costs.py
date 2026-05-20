# ABOUTME: Phase 4a t3 — aggregate_costs cumulative + per-run breakdown + cost-telemetry-gap surface.
# ABOUTME: Pins AC-4's "named, not silently dropped" invariant for unknown-cost runs.

from pathlib import Path

from razorback.runs.cost import aggregate_costs
from tests.unit.conftest import make_run_dir, make_trial_dir


def test_aggregate_three_run_dirs_sums_costs(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j1", cost_in_summary=1.50)
    make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j2", cost_in_summary=2.25)
    make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j3", cost_in_summary=0.75)
    doc = aggregate_costs(tmp_path / "runs")
    assert doc["total_usd"] == 4.50
    assert doc["n_runs"] == 3
    assert doc["n_known"] == 3
    assert doc["n_unknown"] == 0
    assert doc["warnings"] == []
    assert len(doc["runs"]) == 3


def test_aggregate_per_run_carries_required_fields(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j1", cost_in_summary=1.0)
    doc = aggregate_costs(tmp_path / "runs")
    entry = doc["runs"][0]
    for k in ("path", "experiment", "created_at", "cost_usd", "cost_unknown", "cost_source"):
        assert k in entry, f"missing key: {k}"


def test_aggregate_filters_by_experiment(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="foo", job_name="j", cost_in_summary=1.0)
    make_run_dir(tmp_path, root="runs", experiment="bar", job_name="j", cost_in_summary=99.0)
    doc = aggregate_costs(tmp_path / "runs", experiment="foo")
    assert doc["total_usd"] == 1.0
    assert doc["n_runs"] == 1


def test_aggregate_excludes_unknown_from_total(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j1", cost_in_summary=2.0)
    run2 = make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j2")
    make_trial_dir(run2, trial_name="t__a", agent_cost_usd=None)
    doc = aggregate_costs(tmp_path / "runs")
    assert doc["total_usd"] == 2.0
    assert doc["n_runs"] == 2
    assert doc["n_known"] == 1
    assert doc["n_unknown"] == 1
    assert len(doc["warnings"]) == 1
    assert "cost unknown" in doc["warnings"][0]


def test_aggregate_all_unknown_distinct_from_all_zero(tmp_path: Path):
    """AC-4: total_usd 0 + n_unknown N != total_usd 0 + n_unknown 0."""
    run = make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j")
    make_trial_dir(run, trial_name="t__a", agent_cost_usd=None)
    doc = aggregate_costs(tmp_path / "runs")
    assert doc["total_usd"] == 0.0
    assert doc["n_unknown"] == 1
    assert doc["warnings"] != []


def test_aggregate_empty_root(tmp_path: Path):
    (tmp_path / "runs").mkdir()
    doc = aggregate_costs(tmp_path / "runs")
    assert doc == {
        "total_usd": 0.0,
        "n_runs": 0,
        "n_known": 0,
        "n_unknown": 0,
        "runs": [],
        "warnings": [],
    }
