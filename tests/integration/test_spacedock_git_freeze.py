# ABOUTME: AC-4 — agent_freeze/.git is a real git repo with one commit per stage boundary.
# ABOUTME: Integration-scoped: uses a fake BaseEnvironment that pipes exec through subprocess.

import asyncio
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from razorback.agents.seal import compute_sealed_hash, prompt_sha256
from razorback.agents.spacedock_solver import SpacedockSolverAgent


class _LocalShellEnvironment:
    """Minimal BaseEnvironment-shaped fake — pipes exec through subprocess on the host."""

    def __init__(self, workdir: Path):
        self.workdir = workdir
        self.default_user = None

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        actual_cwd = cwd or str(self.workdir)
        proc = subprocess.run(
            command, shell=True, cwd=actual_cwd,
            env={**os.environ, **(env or {})},
            capture_output=True, text=True, timeout=timeout_sec or 60,
        )
        result = MagicMock()
        result.return_code = proc.returncode
        result.stdout = proc.stdout
        result.stderr = proc.stderr
        return result


def _stub_claude_on_path(tmp_path: Path) -> Path:
    """Write a fake `claude` script that succeeds on --version and writes a stage log on -p."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "claude"
    stub.write_text(
        "#!/bin/bash\n"
        'if [ "$1" = "--version" ]; then echo "0.0.0-stub"; exit 0; fi\n'
        'echo "stub claude ran with args: $@" >> stage.log\n'
        "exit 0\n"
    )
    stub.chmod(0o755)
    return bin_dir


def _build_agent(tmp_path, logs_dir):
    body_m = b"MODEL PROMPT\n"
    body_a = b"ANALYZE PROMPT\n"
    body_v = b"VERIFY PROMPT\n"
    prompts = {
        "model": prompt_sha256(body_m),
        "analyze": prompt_sha256(body_a),
        "verify": prompt_sha256(body_v),
    }
    sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes=prompts,
    )
    return SpacedockSolverAgent(
        logs_dir=logs_dir,
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        tools_allowed=["Bash"],
        prompts=prompts,
        sealed_hash=sealed,
        extra_env={"ANTHROPIC_API_KEY": "sk-test"},
        prompt_contents={
            "model": body_m.decode(),
            "analyze": body_a.decode(),
            "verify": body_v.decode(),
        },
        prior_frozen_spec_path=None,
    )


@pytest.mark.timeout(60)
def test_run_creates_agent_freeze_git_repo_with_stage_commits(tmp_path, monkeypatch):
    """AC-4: agent_freeze/.git is a valid repo with per-stage commits."""
    bin_dir = _stub_claude_on_path(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    agent = _build_agent(tmp_path, logs_dir)

    env = _LocalShellEnvironment(work_dir)
    context = MagicMock()
    asyncio.run(agent.setup(env))
    asyncio.run(agent.run("solve the bookreview query", env, context))

    freeze_dir = logs_dir / "agent_freeze"
    git_dir = freeze_dir / ".git"
    assert git_dir.exists()
    rev = subprocess.run(
        ["git", "-C", str(freeze_dir), "rev-parse", "--git-dir"],
        capture_output=True, text=True,
    )
    assert rev.returncode == 0, rev.stderr
    assert rev.stdout.strip().endswith(".git")

    log = subprocess.run(
        ["git", "-C", str(freeze_dir), "log", "--format=%s"],
        capture_output=True, text=True,
    )
    assert log.returncode == 0
    subjects = [s for s in log.stdout.strip().split("\n") if s]
    assert any("stage: model" in s for s in subjects)
    assert any("stage: analyze" in s for s in subjects)
    assert any("stage: verify" in s for s in subjects)


@pytest.mark.timeout(60)
def test_run_never_writes_inside_harbor_agent_dir(tmp_path, monkeypatch):
    """AC-7 (positive): every razorback write lands under logs_dir/agent_freeze/."""
    bin_dir = _stub_claude_on_path(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    trial_root = tmp_path / "trial"
    (trial_root / "agent").mkdir(parents=True)
    (trial_root / "logs_dir").mkdir()
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    agent = _build_agent(tmp_path, trial_root / "logs_dir")
    env = _LocalShellEnvironment(work_dir)
    context = MagicMock()
    asyncio.run(agent.setup(env))
    asyncio.run(agent.run("solve", env, context))

    assert list((trial_root / "agent").iterdir()) == []
    assert (trial_root / "logs_dir" / "agent_freeze" / ".git").exists()
