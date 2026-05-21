# ABOUTME: AC-2 + AC-6, halt-resume lifecycle wiring; freeze-dir resolution per b5 contract.
# ABOUTME: Tests resolve_freeze_dir, first-stage init, sealed_hash.txt write, resume-restore.

from unittest.mock import AsyncMock, MagicMock

import pytest

from razorback.agents.spacedock_solver_v2 import (
    SpacedockSolverAgent,
    SpacedockSolverAgentError,
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


def _exec_result(return_code=0):
    return MagicMock(return_code=return_code)


def test_freeze_dir_resolves_to_sealed_hash_keyed_external_path(tmp_path):
    """b5 contract point 2: <run-dir>/_razorback/freeze/<sealed_hash>/."""
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    expected = tmp_path / "run" / "_razorback" / "freeze" / agent.sealed_hash
    assert agent.resolve_freeze_dir() == expected
    # The path lives OUTSIDE harbor's trials/ subtree.
    parts_after_razorback = str(agent.resolve_freeze_dir()).split("_razorback", 1)[1]
    assert "trials" not in parts_after_razorback


@pytest.mark.asyncio
async def test_first_stage_writes_sealed_hash_txt(tmp_path):
    """b5 contract point 4 + AC-5: sealed_hash.txt lands at the keyed path on first stage."""
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
async def test_resume_restores_workspace_from_freeze_git(tmp_path):
    """b5 contract point 5: on resume, restore from <freeze_dir>/.git/."""
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    freeze = agent.resolve_freeze_dir()
    freeze.mkdir(parents=True)
    (freeze / "sealed_hash.txt").write_text(agent.sealed_hash)
    (freeze / ".git").mkdir()
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()
    await agent.setup(fake_env)
    git_calls = [c.args[0] for c in fake_env.exec.call_args_list if "git" in c.args[0]]
    assert any("checkout" in c for c in git_calls), (
        f"setup did not call git checkout on resume; calls: {git_calls}"
    )


@pytest.mark.asyncio
async def test_resume_with_mismatched_sealed_hash_in_freeze_dir_refuses(tmp_path):
    """b5 contract point 4: sealed_hash.txt mismatch raises SeedMismatchError at setup."""
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
async def test_first_stage_runs_git_init(tmp_path):
    """b5 contract point 3: create freeze dir + git init on first stage."""
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()
    await agent.setup(fake_env)
    git_calls = [c.args[0] for c in fake_env.exec.call_args_list if "git" in c.args[0]]
    assert any("init" in c for c in git_calls), f"git init missing; calls: {git_calls}"


@pytest.mark.asyncio
async def test_first_stage_installs_git_before_git_init_when_missing(tmp_path):
    """PKG-29 AC-1: missing git is installed before sealed freeze repo init."""
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    fake_env = MagicMock()

    async def fake_exec(cmd):
        if cmd == "command -v git >/dev/null 2>&1":
            prior_calls = [c.args[0] for c in fake_env.exec.call_args_list[:-1]]
            installed = any("apt-get install" in c for c in prior_calls)
            return _exec_result(0 if installed else 1)
        if cmd == "command -v apk >/dev/null 2>&1":
            return _exec_result(1)
        return _exec_result(0)

    fake_env.exec = AsyncMock(side_effect=fake_exec)
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()

    await agent.setup(fake_env)

    calls = [c.args[0] for c in fake_env.exec.call_args_list]
    install_index = calls.index(
        "DEBIAN_FRONTEND=noninteractive apt-get update -qq && "
        "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git"
    )
    init_index = next(
        i for i, cmd in enumerate(calls) if "git -C" in cmd and "init" in cmd
    )
    assert install_index < init_index


@pytest.mark.asyncio
async def test_setup_reports_clear_error_when_git_has_no_package_manager(tmp_path):
    """PKG-29 AC-2: unsupported install path names sealed freeze repo git requirement."""
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    fake_env = MagicMock()

    async def fake_exec(cmd):
        if cmd.startswith("command -v "):
            return _exec_result(1)
        return _exec_result(0)

    fake_env.exec = AsyncMock(side_effect=fake_exec)
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()

    with pytest.raises(
        SpacedockSolverAgentError,
        match="git is required for the sealed freeze repo",
    ):
        await agent.setup(fake_env)


@pytest.mark.asyncio
async def test_setup_reports_clear_error_when_git_install_fails(tmp_path):
    """PKG-29 AC-2: install failure names sealed freeze repo git requirement."""
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    fake_env = MagicMock()

    async def fake_exec(cmd):
        if cmd == "command -v git >/dev/null 2>&1":
            return _exec_result(1)
        if cmd == "command -v apk >/dev/null 2>&1":
            return _exec_result(0)
        if cmd == "apk add --no-cache git":
            return _exec_result(42)
        return _exec_result(0)

    fake_env.exec = AsyncMock(side_effect=fake_exec)
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()

    with pytest.raises(
        SpacedockSolverAgentError,
        match="git is required for the sealed freeze repo.*apk.*rc=42",
    ):
        await agent.setup(fake_env)
