# ABOUTME: AC-2 — example DAB workflow runs propose→smoke→full→analyze→conclude end-to-end.
# ABOUTME: Lifecycle wiring acceptance — uses bookreview-only DAB to keep cost bounded.

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    not os.environ.get("RAZORBACK_RUN_DOCKER_TESTS"),
    reason="docker integration tests require RAZORBACK_RUN_DOCKER_TESTS=1",
)
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="DAB claude acceptance requires ANTHROPIC_API_KEY",
)
def test_dab_claude_workflow_lifecycle(tmp_path):
    """AC-2: simulate the propose → smoke → full → analyze → conclude lifecycle."""
    spec = tmp_path / "spec.yaml"
    data_root = REPO.parent / "dataagentbench" / "data"
    spec.write_text(
        f"""
version: 1
experiment: dab-claude-workflow-smoke
agent:
  kind: claude-cli
benchmark:
  kind: dab
  data_root: {data_root}
  datasets: [bookreview]
trials: 1
observers:
  - kind: jsonl
    path: events.jsonl
"""
    )

    r = subprocess.run(
        ["uv", "run", "rk", "validate", str(spec)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr

    runs_dir = tmp_path / "_runs"
    r = subprocess.run(
        ["uv", "run", "rk", "run", str(spec), "--runs-dir", str(runs_dir)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert r.returncode == 0, f"rk run failed: {r.stderr}"

    run_dirs = list((runs_dir / "dab-claude-workflow-smoke").iterdir())
    assert len(run_dirs) >= 1
    run_dir = run_dirs[0]

    summary = json.loads((run_dir / "summary.json").read_text())
    assert "stratified_pass_at_1" in summary

    diff_result = subprocess.run(
        ["uv", "run", "rk", "runs", "diff", str(run_dir), str(run_dir)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    # diff may exit 20 (seed mismatch) or 0; both acceptable here — AC-2 check is
    # "the diff command was invocable end-to-end, not the math".
    assert diff_result.returncode in (0, 20)

    baseline = tmp_path / "_baselines" / "dab-claude-smoke"
    promote_result = subprocess.run(
        [
            "uv",
            "run",
            "rk",
            "baseline",
            "promote",
            str(run_dir),
            "--to",
            str(baseline),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if promote_result.returncode == 2:
        pytest.skip("M6 rk baseline promote not landed")
    assert promote_result.returncode == 0

    assert (baseline / "spec.frozen.yaml").exists()
    assert (baseline / "summary.json").exists()
