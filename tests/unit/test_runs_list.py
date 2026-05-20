# ABOUTME: Tests for `rk runs list` Typer command (AC-1).
# ABOUTME: Exercises JSON output, --experiment filter, and empty-root behavior.

import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app
from tests.unit.conftest import make_run_dir


def test_runs_list_emits_json_for_all_run_dirs(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="exp-a", job_name="j1")
    make_run_dir(tmp_path, root="runs", experiment="exp-b", job_name="j2")
    result = CliRunner().invoke(app, ["runs", "list", "--root", str(tmp_path / "runs")])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert len(payload) == 2


def test_runs_list_filters_by_experiment(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="exp-a", job_name="j1")
    make_run_dir(tmp_path, root="runs", experiment="exp-b", job_name="j2")
    result = CliRunner().invoke(
        app, ["runs", "list", "--root", str(tmp_path / "runs"), "--experiment", "exp-a"]
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert len(payload) == 1
    assert payload[0]["experiment"] == "exp-a"


def test_runs_list_empty_root_emits_empty_array(tmp_path: Path):
    (tmp_path / "runs").mkdir()
    result = CliRunner().invoke(app, ["runs", "list", "--root", str(tmp_path / "runs")])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == []
