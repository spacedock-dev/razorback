# ABOUTME: AC-3 — `uv run rk run examples/specs/ade-bench-claude.yaml` exits 0; summary.json has score.

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "examples" / "specs" / "ade-bench-claude.yaml"


@pytest.mark.skipif(
    not os.environ.get("RAZORBACK_RUN_DOCKER_TESTS"),
    reason="docker integration tests require RAZORBACK_RUN_DOCKER_TESTS=1",
)
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ade-bench claude acceptance requires ANTHROPIC_API_KEY",
)
def test_rk_run_ade_bench_claude_smoke(tmp_path):
    """AC-3: rk run exits 0 and summary.json carries a numeric `score`."""
    runs_dir = tmp_path / "_runs"
    result = subprocess.run(
        [
            "uv",
            "run",
            "rk",
            "run",
            str(SPEC),
            "--runs-dir",
            str(runs_dir),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, (
        f"rk run failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )

    run_dirs = list((runs_dir / "ade-bench-claude-airbnb001").iterdir())
    assert len(run_dirs) == 1
    summary_path = run_dirs[0] / "summary.json"
    assert summary_path.exists()
    data = json.loads(summary_path.read_text())
    assert "score" in data
    assert isinstance(data["score"], (int, float))
    assert data["benchmark_kind"] == "ade-bench"
    assert data["n_trials"] >= 1
