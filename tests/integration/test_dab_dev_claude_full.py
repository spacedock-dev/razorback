# ABOUTME: AC-6 — full DAB dev-tier run through Claude. Cost-bearing; gated by env var.
# ABOUTME: One trial per query across all 12 DAB datasets.

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


SPEC = Path(__file__).resolve().parents[2] / "examples" / "specs" / "dab-dev-claude.yaml"
FROZEN = SPEC.with_suffix(".frozen.yaml")
GATE = os.getenv("RAZORBACK_RUN_FULL_DAB_TEST") == "1"

TWELVE = {
    "agnews",
    "bookreview",
    "crmarenapro",
    "DEPS_DEV_V1",
    "GITHUB_REPOS",
    "googlelocal",
    "music_brainz_20k",
    "PANCANCER_ATLAS",
    "PATENTS",
    "stockindex",
    "stockmarket",
    "yelp",
}


@pytest.mark.skipif(
    not GATE,
    reason="full DAB dev-tier run is cost-bearing; set RAZORBACK_RUN_FULL_DAB_TEST=1",
)
def test_dab_dev_claude_full_writes_complete_summary(tmp_path):
    runs_dir = tmp_path / "_runs"
    project_root = Path(__file__).resolve().parents[2]

    freeze = subprocess.run(
        ["uv", "run", "rk", "spec", "freeze", str(SPEC)],
        capture_output=True,
        text=True,
        cwd=project_root,
    )
    assert freeze.returncode == 0, (
        f"freeze failed: stdout={freeze.stdout}\nstderr={freeze.stderr}"
    )
    assert FROZEN.exists(), f"freeze did not write {FROZEN}"
    assert (SPEC.parent / "provenance.yaml").exists()

    run = subprocess.run(
        ["uv", "run", "rk", "run", str(FROZEN), "--runs-dir", str(runs_dir)],
        capture_output=True,
        text=True,
        cwd=project_root,
    )
    assert run.returncode == 0, (
        f"run failed (exit {run.returncode}): stdout={run.stdout}\nstderr={run.stderr}"
    )

    experiment_dir = runs_dir / "m5-dab-dev-claude"
    run_dirs = list(experiment_dir.iterdir())
    assert len(run_dirs) == 1, (
        f"expected one run-dir under {experiment_dir}, got {run_dirs}"
    )
    summary_path = run_dirs[0] / "summary.json"
    assert summary_path.exists(), f"no summary.json under {run_dirs[0]}"
    summary = json.loads(summary_path.read_text())

    assert "stratified_pass_at_1" in summary
    assert isinstance(summary["stratified_pass_at_1"], (int, float))
    assert set(summary["datasets"].keys()) == TWELVE, (
        f"summary.json missing datasets: {TWELVE - set(summary['datasets'].keys())}; "
        f"extras: {set(summary['datasets'].keys()) - TWELVE}"
    )
    for slug, ds_block in summary["datasets"].items():
        assert "dataset_pass_at_1" in ds_block, f"{slug} missing dataset_pass_at_1"
        assert ds_block["n_queries"] >= 1
        assert all("pass_at_1" in q for q in ds_block["queries"])
