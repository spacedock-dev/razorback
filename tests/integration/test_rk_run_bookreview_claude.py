# ABOUTME: AC-6 — `uv run rk run examples/specs/bookreview-claude.yaml` writes
# ABOUTME: a summary.json whose bookreview pass@1 is strictly greater than 0.0.

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "examples" / "specs" / "bookreview-claude.yaml"
DAB_DATA = Path("/Users/clkao/git/dataagentbench/data/query_bookreview")
DOTENV_API_KEY = dotenv_values(REPO / ".env").get("ANTHROPIC_API_KEY") if (REPO / ".env").exists() else None
_TOKEN_PATH = Path.home() / ".claude" / "benchmark-token"
HAS_AUTH = bool(DOTENV_API_KEY or _TOKEN_PATH.exists())


def _has_dab_agent_image() -> bool:
    try:
        r = subprocess.run(
            ["docker", "image", "inspect", "dab-agent:latest"],
            capture_output=True,
            timeout=10,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.mark.skipif(
    not DAB_DATA.exists()
    or shutil.which("claude") is None
    or not HAS_AUTH
    or not _has_dab_agent_image(),
    reason=(
        "AC-6 needs bookreview dataset, host `claude` CLI, an auth token, "
        "and dab-agent:latest image."
    ),
)
@pytest.mark.timeout(1800)
def test_rk_run_bookreview_claude_produces_nonzero_score(colima_safe_tmp_path):
    runs_root = colima_safe_tmp_path / "_runs"
    env = {**os.environ}
    result = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(SPEC), "--runs-dir", str(runs_root)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert result.returncode == 0, f"rk run failed:\nstdout={result.stdout}\nstderr={result.stderr}"

    experiment_dir = runs_root / "m3-bookreview-claude"
    [run_dir] = list(experiment_dir.iterdir())
    summary = json.loads((run_dir / "summary.json").read_text())

    book = summary["datasets"]["bookreview"]
    assert book["dataset_pass_at_1"] > 0.0, (
        f"bookreview pass@1 not strictly > 0.0 — got {book['dataset_pass_at_1']}; "
        f"per-query: {[(q['query_id'], q['pass_at_1']) for q in book['queries']]}"
    )
