# ABOUTME: End-to-end test for `rk run examples/specs/bookreview-nop.yaml`.
# ABOUTME: AC-7: summary.json carries stratified pass@1 (numeric) against the real bookreview dataset.

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "examples" / "specs" / "bookreview-nop.yaml"
DAB_DATA = Path(
    os.environ.get("DATAAGENTBENCH_DATA_ROOT", "~/dataagentbench/data")
).expanduser() / "query_bookreview"


@pytest.fixture
def runs_root(colima_safe_tmp_path):
    return colima_safe_tmp_path / "_runs"


@pytest.mark.skipif(
    not os.environ.get("RAZORBACK_RUN_DOCKER_TESTS") or not DAB_DATA.exists(),
    reason="DAB bookreview Docker smoke requires RAZORBACK_RUN_DOCKER_TESTS=1 and data",
)
def test_rk_run_bookreview_nop_writes_stratified_summary(runs_root):
    env = {**os.environ}
    result = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(SPEC), "--runs-dir", str(runs_root)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"

    experiment_dir = runs_root / "m2-bookreview-nop"
    run_dirs = list(experiment_dir.iterdir())
    assert len(run_dirs) == 1, run_dirs
    run_dir = run_dirs[0]

    summary_path = run_dir / "summary.json"
    assert summary_path.is_file(), f"missing summary.json in {run_dir}"
    summary = json.loads(summary_path.read_text())

    # AC-7: stratified pass@1 line exists and is numeric.
    assert "stratified_pass_at_1" in summary
    assert isinstance(summary["stratified_pass_at_1"], (int, float))

    # The nop agent always answers wrong, so every query's pass@1 is 0.0.
    book = summary["datasets"]["bookreview"]
    assert book["n_queries"] == 3
    for q in book["queries"]:
        assert q["pass_at_1"] == 0.0


@pytest.mark.skipif(
    not os.environ.get("RAZORBACK_RUN_DOCKER_TESTS") or not DAB_DATA.exists(),
    reason="DAB bookreview Docker smoke requires RAZORBACK_RUN_DOCKER_TESTS=1 and data",
)
def test_rk_run_bookreview_nop_preserves_run_dir_layout(runs_root):
    env = {**os.environ}
    result = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(SPEC), "--runs-dir", str(runs_root)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    run_dir = next((runs_root / "m2-bookreview-nop").iterdir())

    # M1's run-dir layout still holds.
    for name in ("spec.frozen.yaml", "manifest.json", "events.jsonl", "summary.json", "lock.json"):
        assert (run_dir / name).is_file(), f"missing {name}"
    # M2-specific: the materialized tasks_root.
    assert (run_dir / "tasks" / "bookreview" / "bookreview-q1" / "task.toml").is_file()
    assert not list((run_dir / "tasks").rglob("ground_truth.csv")), (
        "ground_truth.csv leaked into task dirs"
    )
