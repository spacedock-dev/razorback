# ABOUTME: FU-1 AC-1 — resolved claude auth must NEVER appear plaintext in any run-dir file.
# ABOUTME: Drives `rk run` against the ade-bench fixture w/ a sentinel .env; greps the run-dir.

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FIXTURE_TASK = REPO / "tests" / "fixtures" / "ade_bench" / "tasks" / "adebench-fixture-001"
GREP_SENTINEL = "sk-ant-TEST-SENTINEL-FU1-DO-NOT-USE-XYZ123"


SPEC_TEMPLATE = """\
version: 1
experiment: fu1-auth-leak-smoke
agent:
  kind: claude-cli
  tools_allowed: []
benchmark:
  kind: ade-bench
  tasks_root: {tasks_root}
  tasks:
    - adebench-fixture-001
trials: 1
observers:
  - kind: jsonl
    path: events.jsonl
"""


def test_no_auth_token_plaintext_in_run_dir(colima_safe_tmp_path):
    """FU-1 AC-1 — drive `rk run` against the alpine fixture; assert sentinel never appears.

    The translator's pre-fix forwarding path writes the resolved token into
    `AgentConfig.kwargs.resolved_auth_env`, which harbor serializes verbatim to
    `<run-dir>/<job>/config.json`. After Task 2's fix, the token only rides via
    `AgentConfig.env`, which harbor's `templatize_sensitive_env` redacts.
    """
    project = colima_safe_tmp_path / "project"
    project.mkdir(parents=True)
    (project / ".env").write_text(f"ANTHROPIC_API_KEY={GREP_SENTINEL}\n")

    # Use the in-repo fixture tasks_root directly — claude setup fails on alpine,
    # but config.json/lock.json get written before the failure.
    spec_path = project / "spec.yaml"
    spec_path.write_text(SPEC_TEMPLATE.format(tasks_root=FIXTURE_TASK.parent))

    runs_root = colima_safe_tmp_path / "_runs"

    env = {**os.environ}
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    # rk run reads .env from cwd (Path.cwd() in run.py); cwd into the project dir.
    result = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(spec_path), "--runs-dir", str(runs_root)],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    # rk run is expected to fail (alpine has no `claude`); we only need the run-dir
    # files to have been written before that failure.
    assert runs_root.exists(), (
        f"runs_root not created — rk run did not reach harbor.Job.create:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )

    experiment_dir = runs_root / "fu1-auth-leak-smoke"
    run_dirs = [p for p in experiment_dir.iterdir() if p.is_dir()]
    assert run_dirs, f"no run-dir under {experiment_dir} (stderr={result.stderr})"
    run_dir = run_dirs[0]

    # Verify config.json was indeed written (mechanism precondition).
    config_path = run_dir / "config.json"
    assert config_path.exists(), (
        f"config.json missing under {run_dir}; "
        f"harbor did not reach the persist step. stderr={result.stderr}"
    )

    # AC-1 grep: literal sentinel must not appear in any run-dir file.
    grep = subprocess.run(
        ["grep", "-r", "-F", "--", GREP_SENTINEL, str(run_dir)],
        capture_output=True,
        text=True,
    )
    assert grep.returncode != 0, (
        f"AC-1 VIOLATION: literal auth sentinel found in run-dir:\n{grep.stdout}"
    )


def test_grep_run_dir_for_secrets_script_detects_known_leak(tmp_path):
    """The host-runnable grep gate exits 1 when a leak is present, 0 when clean."""
    script = REPO / "scripts" / "grep-run-dir-for-secrets.sh"
    assert script.exists() and os.access(script, os.X_OK), (
        f"grep gate script missing or not executable: {script}"
    )

    # Synthetic leaked run-dir: drop the sentinel in a config.json file.
    leak_dir = tmp_path / "leaked-run"
    leak_dir.mkdir()
    (leak_dir / "config.json").write_text(
        '{"agents": [{"kwargs": {"resolved_auth_env": '
        f'{{"ANTHROPIC_API_KEY": "{GREP_SENTINEL}"}}}}]}}\n'
    )

    leaked = subprocess.run(
        [str(script), str(leak_dir), GREP_SENTINEL],
        capture_output=True,
        text=True,
    )
    assert leaked.returncode == 1, (
        f"grep gate failed to detect known leak (rc={leaked.returncode}); "
        f"stdout={leaked.stdout}\nstderr={leaked.stderr}"
    )
    assert "AC-1 VIOLATION" in leaked.stderr

    # Clean run-dir: gate exits 0.
    clean_dir = tmp_path / "clean-run"
    clean_dir.mkdir()
    (clean_dir / "config.json").write_text(
        '{"agents": [{"env": {"ANTHROPIC_API_KEY": "sk-a****Z123"}}]}\n'
    )
    clean = subprocess.run(
        [str(script), str(clean_dir), GREP_SENTINEL],
        capture_output=True,
        text=True,
    )
    assert clean.returncode == 0, (
        f"grep gate flagged a clean run-dir (rc={clean.returncode}); "
        f"stdout={clean.stdout}\nstderr={clean.stderr}"
    )
    assert "AC-1 OK" in clean.stderr


def test_grep_run_dir_for_secrets_script_usage(tmp_path):
    """Missing the literal-token argument should exit 2 (usage)."""
    script = REPO / "scripts" / "grep-run-dir-for-secrets.sh"
    result = subprocess.run(
        [str(script), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, (
        f"grep gate usage path wrong (rc={result.returncode}); stderr={result.stderr}"
    )
