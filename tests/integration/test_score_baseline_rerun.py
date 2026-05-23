# ABOUTME: AC-5 — rk score end-to-end on baseline-rerun bookreview run-dir.
# ABOUTME: Goal 1+2 paper-reproduction readout shape against a real harbor run-dir.

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app

FIXTURE = (
    Path(__file__).parent.parent
    / "fixtures"
    / "score"
    / "baseline_rerun_bookreview"
)


def test_rk_score_baseline_rerun_against_paper_577_exits_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "score",
            str(FIXTURE),
            "--against-constant",
            "stratified_pass_at_1=0.577",
            "--alpha",
            "0.05",
        ],
    )
    assert result.exit_code == 0, result.output

    parsed = json.loads(result.output)
    bookreview = parsed["strata"]["bookreview"]
    assert bookreview["n_completed"] == 3
    assert bookreview["n_errored"] == 0
    assert bookreview["pass_at_1"] == 1.0

    verdict = parsed["against_constant"]["per_stratum"]["bookreview"]["verdict"]
    assert verdict in {"matches", "above", "below"}


def test_rk_score_baseline_rerun_markdown_format() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["score", str(FIXTURE), "--format", "markdown"])
    assert result.exit_code == 0, result.output
    assert "| stratum" in result.output
    assert "bookreview" in result.output
    assert "stratified pass@1:" in result.output
