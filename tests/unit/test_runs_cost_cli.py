# ABOUTME: Phase 4a t4 — rk runs cost Typer command end-to-end.
# ABOUTME: Pins AC-1, AC-2 (filter), AC-5 (exit 2 + error names missing path).

import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app
from tests.unit.conftest import make_run_dir


def test_runs_cost_emits_aggregate_json(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="e", job_name="j1", cost_in_summary=1.50)
    make_run_dir(tmp_path, root="runs", experiment="e", job_name="j2", cost_in_summary=2.25)
    result = CliRunner().invoke(app, ["runs", "cost", "--root", str(tmp_path / "runs")])
    assert result.exit_code == 0, result.stdout
    doc = json.loads(result.stdout)
    assert doc["total_usd"] == 3.75
    assert doc["n_runs"] == 2


def test_runs_cost_filters_by_experiment(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="foo", job_name="j", cost_in_summary=1.0)
    make_run_dir(tmp_path, root="runs", experiment="bar", job_name="j", cost_in_summary=99.0)
    result = CliRunner().invoke(
        app,
        ["runs", "cost", "--root", str(tmp_path / "runs"), "--experiment", "foo"],
    )
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["total_usd"] == 1.0


def test_runs_cost_usage_exit_on_missing_root(tmp_path: Path):
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        app,
        ["runs", "cost", "--root", str(tmp_path / "does-not-exist")],
    )
    assert result.exit_code == 2
    assert "does-not-exist" in (result.stderr + result.stdout)
