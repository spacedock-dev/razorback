# ABOUTME: AC-5 mechanism gate — second agent invocation with the same
# ABOUTME: sealed_hash resumes from the CAS freeze tree without re-init.

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from razorback.agents.spacedock_solver import SpacedockSolverAgent


def _kw(tmp_path: Path) -> dict:
    workflow = tmp_path / "solver"
    workflow.mkdir(exist_ok=True)
    (workflow / "README.md").write_text("## Stages\n- model\n")
    logs_dir = (
        tmp_path / "run" / "trials" / "task-0001__abc1234" / "logs" / "agent"
    )
    logs_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "run" / "spec.frozen.yaml").write_text("placeholder")
    return dict(
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


@pytest.mark.asyncio
async def test_second_setup_takes_resume_branch_without_reinit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))

    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))

    # First setup: init branch — real git init on host so the .git exists.
    agent_a = SpacedockSolverAgent(**_kw(tmp_path))
    agent_a._inner = MagicMock()
    agent_a._inner.setup = AsyncMock()
    await agent_a.setup(fake_env)

    freeze_dir = agent_a.resolve_freeze_dir()
    assert (freeze_dir / "sealed_hash.txt").exists()
    assert (freeze_dir / ".git").is_dir()

    # Second setup with the SAME inputs — must take the resume branch.
    # We track host-git argv shapes by patching _host_git.
    agent_b = SpacedockSolverAgent(**_kw(tmp_path))
    agent_b._inner = MagicMock()
    agent_b._inner.setup = AsyncMock()
    assert agent_b.resolve_freeze_dir() == freeze_dir  # CAS hit.

    host_git_calls: list[tuple[str, ...]] = []
    original_host_git = agent_b._host_git

    async def recording_host_git(*args: str) -> None:
        host_git_calls.append(tuple(args))
        await original_host_git(*args)

    agent_b._host_git = recording_host_git  # type: ignore[assignment]
    await agent_b.setup(fake_env)

    # Resume branch starts with `checkout -- .` and does NOT re-init or re-seed
    # (pkg40 adds an orthogonal CHECKPOINT_SETUP_READY commit after the
    # init/resume fork; that's allowed — what's banned is `init` / `seed`).
    assert host_git_calls[0] == ("checkout", "--", "."), (
        f"AC-5 violated: second setup did not take the resume branch. "
        f"host_git argv list: {host_git_calls}"
    )
    forbidden = [c for c in host_git_calls if c[0] == "init" or (
        len(c) >= 5 and c[0] == "commit" and c[-1] == "seed"
    )]
    assert forbidden == [], (
        f"AC-5 violated: resume branch re-initialized or re-seeded the freeze tree: {forbidden}"
    )
    # Inner setup was called once on the resumed agent: the freeze tree could
    # be re-replayed (the inner agent is wired) but no re-init / re-seed git
    # work happened on the host.
    assert agent_b._inner.setup.await_count == 1
