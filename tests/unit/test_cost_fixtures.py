# ABOUTME: Phase 4a t1 — exercises cost-bearing kwargs on the make_run_dir factory.
# ABOUTME: Pins the four-shape fixture surface (summary cost, result.stats cost, null, per-trial).

import json
from pathlib import Path

from tests.unit.conftest import make_run_dir, make_trial_dir


def test_make_run_dir_writes_cost_in_summary(tmp_path: Path):
    run_dir = make_run_dir(
        tmp_path, root="runs", experiment="e", job_name="j",
        cost_in_summary=2.25,
    )
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["cost_usd"] == 2.25


def test_make_run_dir_writes_cost_in_result_stats(tmp_path: Path):
    run_dir = make_run_dir(
        tmp_path, root="runs", experiment="e", job_name="j",
        cost_in_result_stats=1.50,
    )
    result = json.loads((run_dir / "result.json").read_text())
    assert result["stats"]["cost_usd"] == 1.50


def test_make_run_dir_writes_null_cost_in_result_stats(tmp_path: Path):
    run_dir = make_run_dir(
        tmp_path, root="runs", experiment="e", job_name="j",
        cost_in_result_stats=None,
        write_result_stats=True,
    )
    result = json.loads((run_dir / "result.json").read_text())
    assert result["stats"]["cost_usd"] is None


def test_make_trial_dir_writes_per_trial_agent_cost(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, root="runs", experiment="e", job_name="j")
    trial = make_trial_dir(run_dir, trial_name="t__abc", agent_cost_usd=0.30)
    body = json.loads((trial / "result.json").read_text())
    assert body["step_results"][0]["agent_result"]["cost_usd"] == 0.30
