# ABOUTME: AC-1/AC-2 — rk score's stratified_pass_at_1 equals summary.json's (single source of truth).
# ABOUTME: Round-trip: aggregate_summary -> read summary.json -> rk score -> assert equality.

from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app
from razorback.runs.aggregate import aggregate_summary

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "score"
DAB_FIXTURE = FIXTURE_ROOT / "mixed_trial_run_dir"
ADE_FIXTURE = FIXTURE_ROOT / "ade_bench_run_dir"
UNEQUAL_FIXTURE = FIXTURE_ROOT / "unequal_trials_run_dir"
DAB_BATCH_FIXTURE = FIXTURE_ROOT / "dab_batch_run_dir"


def _copy_trial_subdirs(src: Path, dst: Path) -> None:
    """Copy only the per-trial directories (skip pre-existing summary.json etc.)."""
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        if child.is_dir():
            shutil.copytree(child, dst / child.name)


def _run_score(run_dir: Path) -> dict:
    runner = CliRunner()
    result = runner.invoke(app, ["score", str(run_dir), "--format", "json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_rk_score_matches_summary_json_for_dab_fixture(tmp_path: Path) -> None:
    """AC-1 round-trip: rk score's stratified_pass_at_1 == summary.json's for a DAB run-dir."""
    work = tmp_path / "exp" / "job"
    _copy_trial_subdirs(DAB_FIXTURE, work)

    aggregate_summary(work)
    summary = json.loads((work / "summary.json").read_text())
    score = _run_score(work)

    assert score["stratified_pass_at_1"] == summary["stratified_pass_at_1"]


def test_rk_score_matches_summary_json_for_ade_bench_fixture(tmp_path: Path) -> None:
    """AC-2 round-trip: rk score's stratified_pass_at_1 == summary.json's for an ADE-bench run-dir."""
    work = tmp_path / "exp" / "job"
    _copy_trial_subdirs(ADE_FIXTURE, work)

    aggregate_summary(work)
    summary = json.loads((work / "summary.json").read_text())
    score = _run_score(work)

    assert score["stratified_pass_at_1"] == summary["stratified_pass_at_1"]


def test_rk_score_matches_summary_with_unequal_trials_per_query(tmp_path: Path) -> None:
    """The number-agreement contract holds when queries have unequal trial counts.

    Per-query: q1 = 1/2 = 0.5, q2 = 0/1 = 0.0 -> dataset mean = 0.25.
    Binary across completed trials: 1/3 = 0.333... -> the OLD path's answer.
    This case red-bars the binary reducer; both paths must agree on the
    per-query stratified mean.
    """
    work = tmp_path / "exp" / "job"
    _copy_trial_subdirs(UNEQUAL_FIXTURE, work)

    aggregate_summary(work)
    summary = json.loads((work / "summary.json").read_text())
    score = _run_score(work)

    assert summary["stratified_pass_at_1"] == 0.25
    assert score["stratified_pass_at_1"] == summary["stratified_pass_at_1"]


def test_rk_score_matches_summary_json_for_dab_batch_fixture(tmp_path: Path) -> None:
    """AC-4 round-trip on a DAB batch trial: composite reward 0.857 binarizes
    to 0 under the old reducer; the canonical reducer must report 6/7 from
    `reward_per_query.json` and both surfaces must agree byte-for-byte."""
    work = tmp_path / "exp" / "job"
    _copy_trial_subdirs(DAB_BATCH_FIXTURE, work)

    aggregate_summary(work)
    summary = json.loads((work / "summary.json").read_text())
    score = _run_score(work)

    assert summary["stratified_pass_at_1"] == 6 / 7
    assert score["stratified_pass_at_1"] == summary["stratified_pass_at_1"]
