# ABOUTME: Phase 4a t6 — pin top-level + per-run JSON key sets for rk runs cost (§3.3 semver).
# ABOUTME: CI fails on rename/removal; additive fields require updating both constants in one commit.

import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app
from tests.unit.conftest import make_run_dir

TOP_KEYS = {"total_usd", "n_runs", "n_known", "n_unknown", "runs", "warnings"}
RUN_KEYS = {"path", "experiment", "created_at", "cost_usd", "cost_unknown", "cost_source"}


def test_runs_cost_top_level_keys_stable(tmp_path: Path):
    make_run_dir(tmp_path, root="r", experiment="e", job_name="j", cost_in_summary=1.0)
    result = CliRunner().invoke(app, ["runs", "cost", "--root", str(tmp_path / "r")])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert set(doc) == TOP_KEYS, (
        f"rk runs cost top-level field set changed (§3.3 violation). "
        f"Got: {set(doc)}. Expected: {TOP_KEYS}."
    )


def test_runs_cost_per_run_keys_stable(tmp_path: Path):
    make_run_dir(tmp_path, root="r", experiment="e", job_name="j", cost_in_summary=1.0)
    result = CliRunner().invoke(app, ["runs", "cost", "--root", str(tmp_path / "r")])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert set(doc["runs"][0]) == RUN_KEYS, (
        f"rk runs cost per-run field set changed (§3.3 violation). "
        f"Got: {set(doc['runs'][0])}. Expected: {RUN_KEYS}."
    )
