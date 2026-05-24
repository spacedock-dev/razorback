from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from razorback.agents.spacedock_solver import (
    SpacedockSolverAgent,
    SpacedockSolverAgentError,
)


def _kw(tmp_path: Path, **overrides):
    workflow = tmp_path / "solver"
    workflow.mkdir(exist_ok=True)
    (workflow / "README.md").write_text("## Stages\n- model\n")
    logs_dir = tmp_path / "run" / "trials" / "f1001__abc1234" / "logs" / "agent"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "run" / "spec.frozen.yaml").write_text("placeholder")
    base = dict(
        logs_dir=logs_dir,
        runtime="codex",
        model="gpt-5.5",
        sampling={"temperature": 0.0, "top_p": None, "seed": None},
        solver_workflow=workflow,
        solver_workflow_content_hash="sha256:" + "a" * 64,
        prompt_content_hashes={"readme": "sha256:" + "b" * 64},
        spacedock_skill_version="1.0.0",
        harbor_agent_kwargs={"max_turns": 200},
        benchmark_kind="harbor",
        benchmark_task_id="f1001",
        extra_env={"OPENAI_API_KEY": "x"},
    )
    base.update(overrides)
    return base


def _git_commit_subjects(path: Path) -> list[str]:
    out = subprocess.check_output(
        ["git", "-C", str(path), "log", "--format=%s"], text=True
    )
    return out.splitlines()


@pytest.mark.asyncio
async def test_workspace_preflight_runs_before_inner_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Generic preflight: solver execs `/workspace/preflight.sh` once if present.

    No benchmark-kind gate — filesystem convention only.
    """
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(
        return_value=MagicMock(return_code=0, stdout="", stderr="")
    )
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()

    await agent.setup(fake_env)

    preflight_command = fake_env.exec.call_args_list[0].args[0]
    assert "/workspace/preflight.sh" in preflight_command
    agent._inner.setup.assert_awaited_once_with(fake_env)
    assert _git_commit_subjects(agent.resolve_freeze_dir())[0] == "stage: setup/ready"


@pytest.mark.asyncio
async def test_workspace_preflight_failure_blocks_inner_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(
        return_value=MagicMock(
            return_code=2,
            stdout="",
            stderr="preflight script said no",
        )
    )
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()

    with pytest.raises(SpacedockSolverAgentError) as exc_info:
        await agent.setup(fake_env)

    message = str(exc_info.value)
    assert "workspace preflight (/workspace/preflight.sh)" in message
    agent._inner.setup.assert_not_awaited()
