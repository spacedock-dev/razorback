# ABOUTME: rk score CLI subcommand — --alpha, --format, --against-constant wiring.
# ABOUTME: AC-1 + AC-4 + AC-7 wiring tests.

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app

FIXTURE_ROOT = Path(__file__).parent.parent / "fixtures" / "score"
MIXED = FIXTURE_ROOT / "mixed_trial_run_dir"


def test_score_command_returns_exit_zero_and_valid_json() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["score", str(MIXED)])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert parsed["score_version"] == 1
    assert "bookreview" in parsed["strata"]


def test_score_command_alpha_flag_passes_through() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["score", str(MIXED), "--alpha", "0.10"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["alpha"] == 0.10


def test_score_command_against_constant_adds_verdict_block() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["score", str(MIXED), "--against-constant", "paper=0.577"],
    )
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert "against_constant" in parsed
    assert parsed["against_constant"]["name"] == "paper"
    assert parsed["against_constant"]["value"] == 0.577


def test_score_command_invalid_against_constant_format_errors() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["score", str(MIXED), "--against-constant", "paper"])
    assert result.exit_code != 0


def test_score_command_markdown_format_returns_table() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["score", str(MIXED), "--format", "markdown"])
    assert result.exit_code == 0, result.output
    assert "| stratum" in result.output
    assert "bookreview" in result.output


def test_score_command_invalid_format_errors() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["score", str(MIXED), "--format", "yaml"])
    assert result.exit_code != 0


def test_score_command_missing_run_dir_errors(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["score", str(tmp_path / "missing")])
    assert result.exit_code != 0
