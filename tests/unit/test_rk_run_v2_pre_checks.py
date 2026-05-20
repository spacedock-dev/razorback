# ABOUTME: AC-2: rk run v2 wires alias-drift pre-check and surfaces harbor exit code as 30.
# ABOUTME: Mocks the provider API and the harbor subprocess invocation.

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from razorback.cli import app
from razorback.errors import ExitCode
from razorback.provenance.errors import AliasDriftError


FROZEN_SPEC_YAML = (
    "version: 1\n"
    "experiment: phase1-test\n"
    "agent:\n"
    "  kind: nop\n"
    "benchmark:\n"
    "  kind: local\n"
    "  task_paths: []\n"
    "trials: 1\n"
    "provenance:\n"
    "  model_resolved_version: claude-opus-4-5-20251022\n"
    "  harbor_version: 0.6.6\n"
)


@pytest.fixture
def frozen_spec_path(tmp_path: Path) -> Path:
    spec_yaml = tmp_path / "frozen.yaml"
    spec_yaml.write_text(FROZEN_SPEC_YAML)
    return spec_yaml


def test_alias_drift_refusal_exits_21(frozen_spec_path: Path, tmp_path: Path):
    with patch("razorback.cli.run._resolve_model_version") as resolve_mock, \
         patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._invoke_harbor"):
        resolve_mock.side_effect = AliasDriftError(
            model_alias="claude-opus-4-5",
            frozen="claude-opus-4-5-20251022",
            resolved="claude-opus-4-5-DRIFT",
        )
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            app,
            ["run", str(frozen_spec_path), "--runs-dir", str(tmp_path / "_runs")],
        )
        assert result.exit_code == ExitCode.ALIAS_DRIFT == 21, (
            result.stderr or result.stdout
        )


def test_allow_alias_drift_skips_refusal(frozen_spec_path: Path, tmp_path: Path):
    with patch("razorback.cli.run._resolve_model_version") as resolve_mock, \
         patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._invoke_harbor") as harbor_mock:
        resolve_mock.return_value = ("claude-opus-4-5-DRIFT", "2026-05-19")
        harbor_mock.return_value = 0
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            app,
            [
                "run",
                str(frozen_spec_path),
                "--runs-dir",
                str(tmp_path / "_runs"),
                "--allow-alias-drift",
            ],
        )
        assert result.exit_code == 0, result.stderr or result.stdout


def test_harbor_runtime_failure_surfaces_exit_30(frozen_spec_path: Path, tmp_path: Path):
    with patch("razorback.cli.run._resolve_model_version") as resolve_mock, \
         patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._invoke_harbor") as harbor_mock:
        resolve_mock.return_value = ("claude-opus-4-5-20251022", "2026-05-19")
        harbor_mock.return_value = 7
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            app,
            ["run", str(frozen_spec_path), "--runs-dir", str(tmp_path / "_runs")],
        )
        assert result.exit_code == ExitCode.HARBOR_RUNTIME == 30, (
            result.stderr or result.stdout
        )
