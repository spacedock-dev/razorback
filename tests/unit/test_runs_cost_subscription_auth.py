# ABOUTME: Phase 4a t5 — AC-4 regression guard: subscription-auth cost-telemetry gap surfaces as cost_unknown.
# ABOUTME: Pins the "named, not silently dropped" guarantee end-to-end through rk runs cost.

import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app
from tests.unit.conftest import make_run_dir, make_trial_dir


def test_subscription_auth_run_dir_surfaces_as_unknown(tmp_path: Path):
    """Phase 0 finding: subscription-billed Claude leaves agent_result.cost_usd=null.
    rk runs cost must report this as cost_unknown, not silent-zero."""
    run = make_run_dir(
        tmp_path, root="runs", experiment="m3-bookreview-claude", job_name="bxxx",
    )
    make_trial_dir(run, trial_name="bookreview-q1__a", agent_cost_usd=None)
    make_trial_dir(run, trial_name="bookreview-q2__b", agent_cost_usd=None)
    make_trial_dir(run, trial_name="bookreview-q3__c", agent_cost_usd=None)

    result = CliRunner().invoke(app, ["runs", "cost", "--root", str(tmp_path / "runs")])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["n_runs"] == 1
    assert doc["n_known"] == 0
    assert doc["n_unknown"] == 1
    assert doc["total_usd"] == 0.0
    assert len(doc["warnings"]) == 1
    assert doc["runs"][0]["cost_unknown"] is True
    assert doc["runs"][0]["cost_usd"] is None


def test_mixed_known_and_unknown_runs(tmp_path: Path):
    """Realistic mixed-mode experiment: one API-key run + one subscription run."""
    make_run_dir(
        tmp_path, root="runs", experiment="e", job_name="api-keyed", cost_in_summary=2.50,
    )
    sub_run = make_run_dir(tmp_path, root="runs", experiment="e", job_name="subscription")
    make_trial_dir(sub_run, trial_name="t__x", agent_cost_usd=None)

    result = CliRunner().invoke(app, ["runs", "cost", "--root", str(tmp_path / "runs")])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["total_usd"] == 2.50
    assert doc["n_known"] == 1
    assert doc["n_unknown"] == 1
    assert len(doc["warnings"]) == 1
