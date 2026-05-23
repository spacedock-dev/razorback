# ABOUTME: M4 end-to-end — seed run materializes agent_freeze/.git + phase_stats.json,
# ABOUTME: resume re-uses the same (jobs_dir, job_name) lock and passes the sealed_hash check.

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values


REPO = Path(__file__).resolve().parents[2]
SEED_SPEC = REPO / "examples" / "specs" / "bookreview-spacedock-seed.yaml"
DAB_DATA = Path(
    os.environ.get("DATAAGENTBENCH_DATA_ROOT", "~/dataagentbench/data")
).expanduser() / "query_bookreview"
HAS_AUTH = bool(
    dotenv_values(REPO / ".env").get("ANTHROPIC_API_KEY")
    or dotenv_values(REPO / ".env").get("CLAUDE_CODE_OAUTH_TOKEN")
    or (Path.home() / ".claude" / "benchmark-token").exists()
)


@pytest.mark.skipif(
    not DAB_DATA.exists() or shutil.which("claude") is None or not HAS_AUTH,
    reason="end-to-end needs bookreview dataset, host `claude` CLI, and an auth token",
)
@pytest.mark.timeout(1800)
def test_seed_run_then_resume_run_against_matching_sealed_hash(colima_safe_tmp_path):
    tmp_path = colima_safe_tmp_path
    runs_root = tmp_path / "_runs"

    seed_run = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(SEED_SPEC),
         "--runs-dir", str(runs_root)],
        cwd=REPO, env={**os.environ}, capture_output=True, text=True, timeout=1500,
    )
    assert seed_run.returncode == 0, seed_run.stderr

    experiment_dir = runs_root / "m4-bookreview-spacedock"
    assert experiment_dir.exists()

    agent_freeze_dirs = list(experiment_dir.rglob("agent_freeze"))
    assert agent_freeze_dirs, "no agent_freeze/ subtree found under the seed run-dir"
    for d in agent_freeze_dirs:
        assert (d / ".git").exists(), f"{d}/.git missing"
        from razorback.agents.spacedock_solver import assert_phase_stats_schema
        assert_phase_stats_schema(d / "phase_stats.json")

    resume_run = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(SEED_SPEC),
         "--runs-dir", str(runs_root)],
        cwd=REPO, env={**os.environ}, capture_output=True, text=True, timeout=1500,
    )
    assert resume_run.returncode != 20, (
        f"resume against matching sealed_hash raised SeedMismatchError; should not.\n"
        f"stderr={resume_run.stderr}"
    )
