# ABOUTME: AC-1 + AC-4 + AC-5: rk run --max-budget-usd-running CLI surface.
# ABOUTME: Mocks pre-checks + harbor; exercises gate decisions and append-on-completion.

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from razorback.cli import app
from razorback.errors import ExitCode


FROZEN_SPEC_YAML = (
    "version: 1\n"
    "experiment: exp-budget-test\n"
    "agent:\n"
    "  kind: nop\n"
    "benchmark:\n"
    "  kind: local\n"
    "  task_paths: []\n"
    "trials: 1\n"
    "experiment_meta:\n"
    "  max_budget_usd: 50.0\n"
    "  estimated_cost_usd: 30.0\n"
    "provenance:\n"
    "  model_resolved_version: claude-opus-4-5-20251022\n"
    "  harbor_version: 0.6.6\n"
)


@pytest.fixture
def frozen_spec_with_budget(tmp_path: Path) -> Path:
    spec_yaml = tmp_path / "frozen.yaml"
    spec_yaml.write_text(FROZEN_SPEC_YAML)
    return spec_yaml


def test_without_flag_behavior_unchanged(frozen_spec_with_budget: Path, tmp_path: Path):
    """AC-5: omitting --max-budget-usd-running runs unchanged from Phase 1."""
    with patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._resolve_model_version",
               return_value=("claude-opus-4-5-20251022", "2026-05-19")), \
         patch("razorback.cli.run._invoke_harbor", return_value=0), \
         patch("razorback.cli.run._write_provenance_artifacts"):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(app, [
            "run", str(frozen_spec_with_budget),
            "--runs-dir", str(tmp_path / "_runs"),
        ])
        assert result.exit_code == 0, result.stderr or result.stdout


def test_budget_gate_refuses_when_over(frozen_spec_with_budget: Path, tmp_path: Path):
    """AC-1 + AC-4: file already has 30 used; spec estimate 30; cap 50; refuse exit 22."""
    budget_file = tmp_path / "budget.json"
    budget_file.write_text(json.dumps({
        "version": 1, "experiment": "exp-budget-test", "max_budget_usd": 50.0,
        "invocations": [{
            "started_at": "2026-05-20T00:00:00Z",
            "completed_at": "2026-05-20T00:01:00Z",
            "estimate_usd": 30.0,
            "actual_usd": 30.0,
            "run_dir": "/prior",
            "cost_known": True,
        }],
    }))
    with patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._resolve_model_version",
               return_value=("claude-opus-4-5-20251022", "2026-05-19")), \
         patch("razorback.cli.run._invoke_harbor") as harbor_mock, \
         patch("razorback.cli.run._write_provenance_artifacts"):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(app, [
            "run", str(frozen_spec_with_budget),
            "--runs-dir", str(tmp_path / "_runs"),
            "--max-budget-usd-running", str(budget_file),
        ])
        assert result.exit_code == ExitCode.BUDGET_EXCEEDED == 22, (
            result.stderr or result.stdout
        )
        # AC-1: harbor NOT invoked when gate refuses.
        harbor_mock.assert_not_called()
        # AC-4: error message names cap, total, estimate.
        combined = (result.stderr or "") + (result.stdout or "")
        assert "50" in combined
        assert "30" in combined
        # AC-1: file unchanged on refusal.
        body_after = json.loads(budget_file.read_text())
        assert len(body_after["invocations"]) == 1


def test_budget_gate_allows_when_under_then_appends(
    frozen_spec_with_budget: Path, tmp_path: Path
):
    """AC-2: budget allows; harbor runs; actual cost appends to file."""
    budget_file = tmp_path / "budget.json"
    runs_dir = tmp_path / "_runs"

    def fake_harbor(job_config_yaml: Path, env: dict) -> int:
        # The run_dir is job_config_yaml's parent.
        run_dir = Path(job_config_yaml).parent
        (run_dir / "summary.json").write_text(json.dumps({"cost_usd": 25.0}))
        return 0

    with patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._resolve_model_version",
               return_value=("claude-opus-4-5-20251022", "2026-05-19")), \
         patch("razorback.cli.run._invoke_harbor", side_effect=fake_harbor), \
         patch("razorback.cli.run._write_provenance_artifacts"):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(app, [
            "run", str(frozen_spec_with_budget),
            "--runs-dir", str(runs_dir),
            "--max-budget-usd-running", str(budget_file),
        ])
        assert result.exit_code == 0, result.stderr or result.stdout
        body = json.loads(budget_file.read_text())
        assert len(body["invocations"]) == 1
        inv = body["invocations"][0]
        assert inv["actual_usd"] == 25.0
        assert inv["cost_known"] is True


def test_budget_gate_records_subscription_auth_null_cost(
    frozen_spec_with_budget: Path, tmp_path: Path
):
    """Phase 0 cost-telemetry-gap: harbor emits cost_usd: null; gate records cost_known=False."""
    budget_file = tmp_path / "budget.json"
    runs_dir = tmp_path / "_runs"

    def fake_harbor(job_config_yaml: Path, env: dict) -> int:
        run_dir = Path(job_config_yaml).parent
        (run_dir / "result.json").write_text(json.dumps({
            "stats": {"n_completed_trials": 1, "cost_usd": None}
        }))
        return 0

    with patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._resolve_model_version",
               return_value=("claude-opus-4-5-20251022", "2026-05-19")), \
         patch("razorback.cli.run._invoke_harbor", side_effect=fake_harbor), \
         patch("razorback.cli.run._write_provenance_artifacts"):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(app, [
            "run", str(frozen_spec_with_budget),
            "--runs-dir", str(runs_dir),
            "--max-budget-usd-running", str(budget_file),
        ])
        assert result.exit_code == 0, result.stderr or result.stdout
        body = json.loads(budget_file.read_text())
        inv = body["invocations"][0]
        assert inv["actual_usd"] is None
        assert inv["cost_known"] is False


def test_budget_gate_missing_estimated_cost_usd_raises_config_invalid(tmp_path: Path):
    """If spec lacks experiment_meta.estimated_cost_usd, the gate raises ConfigInvalid."""
    spec_yaml = tmp_path / "frozen.yaml"
    spec_yaml.write_text(
        "version: 1\n"
        "experiment: exp-1\n"
        "agent:\n"
        "  kind: nop\n"
        "benchmark:\n"
        "  kind: local\n"
        "  task_paths: []\n"
        "trials: 1\n"
        "experiment_meta:\n"
        "  max_budget_usd: 50.0\n"
        "provenance:\n"
        "  model_resolved_version: claude-opus-4-5-20251022\n"
        "  harbor_version: 0.6.6\n"
    )
    budget_file = tmp_path / "budget.json"
    with patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._resolve_model_version",
               return_value=("claude-opus-4-5-20251022", "2026-05-19")), \
         patch("razorback.cli.run._invoke_harbor") as harbor_mock, \
         patch("razorback.cli.run._write_provenance_artifacts"):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(app, [
            "run", str(spec_yaml),
            "--runs-dir", str(tmp_path / "_runs"),
            "--max-budget-usd-running", str(budget_file),
        ])
        assert result.exit_code == ExitCode.CONFIG_INVALID == 24, (
            result.stderr or result.stdout
        )
        harbor_mock.assert_not_called()
