# ABOUTME: spacedock_solver freeze-repo git executes on host, not via environment.exec.
# ABOUTME: Reproduces rc=128 host/container mount mismatch surfaced by PKG-26 T4 live `rk run`.

import subprocess
from unittest.mock import AsyncMock, MagicMock

import pytest

from razorback.agents.spacedock_solver import SpacedockSolverAgent


def _kw(tmp_path, **overrides):
    workflow = tmp_path / "solver"
    workflow.mkdir(exist_ok=True)
    (workflow / "README.md").write_text("## Stages\n- model\n")
    logs_dir = tmp_path / "run" / "trials" / "task-0001__abc1234" / "logs" / "agent"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "run" / "spec.frozen.yaml").write_text("placeholder")
    base = dict(
        logs_dir=logs_dir,
        runtime="claude",
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": None},
        solver_workflow=workflow,
        solver_workflow_content_hash="sha256:" + "a" * 64,
        prompt_content_hashes={"readme": "sha256:" + "b" * 64},
        spacedock_skill_version="1.0.0",
        harbor_agent_kwargs={"max_turns": 200},
        extra_env={"ANTHROPIC_API_KEY": "x"},
    )
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_first_stage_git_runs_on_host_not_via_environment_exec(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """Freeze-repo git init/config/add/commit must execute on host.

    PKG-26 T4 surfaced rc=128 because environment.exec runs inside the agent
    container, where the host freeze path is not bind-mounted. Fix routes git
    to host subprocess; environment.exec sees zero git invocations.
    """
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()

    await agent.setup(fake_env)

    git_exec_calls = [
        call for call in fake_env.exec.call_args_list
        if call.args and "git" in str(call.args[0])
    ]
    assert git_exec_calls == [], (
        f"git executed via environment.exec (container) instead of host: "
        f"{[c.args[0] for c in git_exec_calls]}"
    )


@pytest.mark.asyncio
async def test_first_stage_creates_real_git_repo_on_host(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """After setup(), freeze_dir contains a real .git/ and sealed_hash.txt."""
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()

    await agent.setup(fake_env)

    freeze_dir = agent.resolve_freeze_dir()
    assert (freeze_dir / "sealed_hash.txt").exists()
    assert (freeze_dir / "sealed_hash.txt").read_text().strip() == agent.sealed_hash
    assert (freeze_dir / ".git").is_dir()
    rev = subprocess.run(
        ["git", "-C", str(freeze_dir), "rev-parse", "--git-dir"],
        capture_output=True, text=True,
    )
    assert rev.returncode == 0, rev.stderr


@pytest.mark.asyncio
async def test_commit_stage_appends_real_commit_on_host(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """_commit_stage writes a real git commit to the host freeze repo."""
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()

    await agent.setup(fake_env)
    await agent._commit_stage(fake_env, "model")

    freeze_dir = agent.resolve_freeze_dir()
    log = subprocess.run(
        ["git", "-C", str(freeze_dir), "log", "--format=%s"],
        capture_output=True, text=True,
    )
    assert log.returncode == 0, log.stderr
    subjects = [s for s in log.stdout.strip().split("\n") if s]
    assert any("stage: model" in s for s in subjects), (
        f"_commit_stage did not produce a real commit on host; log: {subjects}"
    )
    git_exec_calls = [
        call for call in fake_env.exec.call_args_list
        if call.args and "git" in str(call.args[0])
    ]
    assert git_exec_calls == [], (
        f"_commit_stage executed git via environment.exec: "
        f"{[c.args[0] for c in git_exec_calls]}"
    )


@pytest.mark.asyncio
async def test_resume_path_runs_git_checkout_on_host(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """Resume path runs `git checkout -- .` on host, not via environment.exec."""
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    freeze = agent.resolve_freeze_dir()
    freeze.mkdir(parents=True)
    (freeze / "sealed_hash.txt").write_text(agent.sealed_hash)
    subprocess.run(["git", "-C", str(freeze), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(freeze), "config", "user.email", "razorback@local"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(freeze), "config", "user.name", "razorback"], check=True,
    )
    subprocess.run(
        ["git", "-C", str(freeze), "add", "-A"], check=True,
    )
    subprocess.run(
        ["git", "-C", str(freeze), "commit", "-q", "-m", "seed"],
        check=True,
    )

    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()

    await agent.setup(fake_env)

    git_exec_calls = [
        call for call in fake_env.exec.call_args_list
        if call.args and "git" in str(call.args[0])
    ]
    assert git_exec_calls == [], (
        f"resume path executed git via environment.exec: "
        f"{[c.args[0] for c in git_exec_calls]}"
    )


@pytest.mark.asyncio
async def test_freeze_dir_outside_active_worktree(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """AC-1: resolved freeze_dir is NOT under any directory containing .git."""
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    freeze_dir = agent.resolve_freeze_dir()
    # Walk up from freeze_dir and confirm no .git ancestor inside tmp_path.
    for parent in [freeze_dir, *freeze_dir.parents]:
        if not str(parent).startswith(str(tmp_path)):
            break
        assert not (parent / ".git").exists(), (
            f"freeze_dir {freeze_dir} is inside a git worktree at {parent}"
        )
