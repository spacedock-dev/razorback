# ABOUTME: AC-2 + AC-6, halt-resume lifecycle wiring; freeze-dir resolution per b5 contract.
# ABOUTME: Tests resolve_freeze_dir, first-stage init, sealed_hash.txt write, resume-restore.

import subprocess
from unittest.mock import AsyncMock, MagicMock

import pytest

from razorback.agents.spacedock_solver_v2 import (
    CHECKPOINT_RUN_AFTER_AGENT,
    CHECKPOINT_RUN_BEFORE_AGENT,
    CHECKPOINT_SETUP_READY,
    SpacedockSolverAgent,
)
from razorback.errors import SeedMismatchError


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


def _git_commit_subjects(path):
    out = subprocess.check_output(
        ["git", "-C", str(path), "log", "--format=%s"], text=True
    )
    return out.splitlines()


def test_freeze_dir_resolves_to_sealed_hash_keyed_external_path(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """AC-1: <cas-root>/<sealed_hash>/ (env-override CAS, outside any worktree)."""
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    expected = (tmp_path / "freeze-cas").resolve() / agent.sealed_hash
    assert agent.resolve_freeze_dir() == expected
    # The path lives OUTSIDE harbor's run-dir / trials/ subtree entirely.
    assert "trials" not in str(expected)
    assert (tmp_path / "run") not in expected.parents


@pytest.mark.asyncio
async def test_first_stage_writes_sealed_hash_txt(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """b5 contract point 4 + AC-5: sealed_hash.txt lands at the keyed path on first stage."""
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()
    await agent.setup(fake_env)
    sealed_file = agent.resolve_freeze_dir() / "sealed_hash.txt"
    assert sealed_file.exists()
    assert sealed_file.read_text().strip() == agent.sealed_hash


@pytest.mark.asyncio
async def test_resume_restores_workspace_from_freeze_git(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """b5 contract point 5: on resume, restore from <freeze_dir>/.git/ on host."""
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
    subprocess.run(["git", "-C", str(freeze), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(freeze), "commit", "-q", "-m", "seed"], check=True,
    )
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()
    await agent.setup(fake_env)
    # Resume path runs `git checkout -- .` on host (no environment.exec for git).
    env_git_calls = [
        c.args[0] for c in fake_env.exec.call_args_list
        if c.args and "git" in str(c.args[0])
    ]
    assert env_git_calls == [], (
        f"resume path executed git via environment.exec: {env_git_calls}"
    )


@pytest.mark.asyncio
async def test_resume_with_mismatched_sealed_hash_in_freeze_dir_refuses(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """b5 contract point 4: sealed_hash.txt mismatch raises SeedMismatchError at setup."""
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    freeze = agent.resolve_freeze_dir()
    freeze.mkdir(parents=True)
    (freeze / "sealed_hash.txt").write_text("deadbeef" * 4)
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()
    with pytest.raises(SeedMismatchError):
        await agent.setup(fake_env)


@pytest.mark.asyncio
async def test_first_stage_runs_git_init(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """b5 contract point 3: create freeze dir + git init on first stage (on host)."""
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()
    await agent.setup(fake_env)
    # Host-side git: a real .git dir lands at the freeze path.
    assert (agent.resolve_freeze_dir() / ".git").is_dir()
    env_git_calls = [
        c.args[0] for c in fake_env.exec.call_args_list
        if c.args and "git" in str(c.args[0])
    ]
    assert env_git_calls == [], (
        f"setup executed git via environment.exec: {env_git_calls}"
    )


@pytest.mark.asyncio
async def test_setup_and_run_write_named_checkpoint_commits(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """PKG-36: exact v2 checkpoint labels are stable git commit messages."""
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    context = MagicMock()
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()
    agent._inner.run = AsyncMock()

    await agent.setup(fake_env)
    await agent.run("solve this", fake_env, context)

    assert _git_commit_subjects(agent.resolve_freeze_dir())[:3] == [
        f"stage: {CHECKPOINT_RUN_AFTER_AGENT}",
        f"stage: {CHECKPOINT_RUN_BEFORE_AGENT}",
        f"stage: {CHECKPOINT_SETUP_READY}",
    ]
