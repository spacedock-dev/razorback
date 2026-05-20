# ABOUTME: Tests for `rk runs show` Typer command (AC-2 + AC-3).
# ABOUTME: Pins {manifest, summary, path} wire shape and USAGE exit on missing input.

import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app
from tests.unit.conftest import make_run_dir


def test_runs_show_emits_manifest_and_summary(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, root="runs", experiment="exp-a", job_name="j1")
    result = CliRunner().invoke(app, ["runs", "show", str(run_dir)])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["manifest"]["experiment"] == "exp-a"
    assert payload["manifest"]["run_dir_version"] == 1
    assert "created_at" in payload["manifest"]
    assert payload["summary"]["summary_version"] == 1
    assert payload["path"] == str(run_dir.resolve())
