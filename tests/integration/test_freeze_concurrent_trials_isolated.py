# ABOUTME: Regression for the freeze-repo HEAD-lock race that blocked concurrent attempts.
# ABOUTME: Concurrent trials of one task (same sealed_hash) must get isolated freeze repos.

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from razorback.agents.spacedock_solver import SpacedockSolverAgent


def _make_harbor_run_dir(tmp_path: Path, trial_name: str) -> Path:
    """Mimic harbor 0.6.6 layout: <run-dir>/trials/<trial_name>/logs/agent/."""
    run_dir = tmp_path / "run"
    logs_dir = run_dir / "trials" / trial_name / "logs" / "agent"
    logs_dir.mkdir(parents=True, exist_ok=True)
    spec_path = run_dir / "spec.frozen.yaml"
    if not spec_path.exists():
        spec_path.write_text("placeholder")
    return logs_dir


def _common_kwargs(workflow: Path) -> dict:
    return dict(
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


def _make_agent(logs_dir: Path, workflow: Path) -> SpacedockSolverAgent:
    agent = SpacedockSolverAgent(logs_dir=logs_dir, **_common_kwargs(workflow))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()
    return agent


@pytest.mark.asyncio
async def test_concurrent_trials_of_same_task_get_isolated_freeze_repos(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """Two attempts of one task (identical sealed_hash) must NOT share one git repo.

    They differ only by harbor's random trial-name suffix. Before the fix both
    resolved to <root>/<sealed_hash> and their concurrent commits raced on the
    HEAD ref lock (`cannot lock ref 'HEAD'`). After the fix each cell gets its
    own freeze subtree, so concurrent stage commits never contend.
    """
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    logs_a = _make_harbor_run_dir(tmp_path, "bookreview-0001__abc1234")
    logs_b = _make_harbor_run_dir(tmp_path, "bookreview-0001__wMGYfz7")

    agent_a = _make_agent(logs_a, workflow)
    agent_b = _make_agent(logs_b, workflow)

    # Same sealed inputs -> same sealed_hash, but isolated freeze trees.
    assert agent_a.sealed_hash == agent_b.sealed_hash
    assert agent_a.resolve_freeze_dir() != agent_b.resolve_freeze_dir()

    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    await asyncio.gather(agent_a.setup(fake_env), agent_b.setup(fake_env))

    # Each cell commits its stages sequentially (as setup()/run() do), but the
    # two cells run concurrently — the exact shape that raced on one shared
    # HEAD before the fix. With isolated repos this completes cleanly.
    async def commit_stages(agent: SpacedockSolverAgent, tag: str) -> None:
        for i in range(10):
            await agent._commit_stage(fake_env, f"{tag}-stage-{i}")

    await asyncio.gather(
        commit_stages(agent_a, "a"),
        commit_stages(agent_b, "b"),
    )

    # Each repo's history contains only its own stages.
    log_a = await _git_log_subjects(agent_a.resolve_freeze_dir())
    log_b = await _git_log_subjects(agent_b.resolve_freeze_dir())
    assert any("a-stage-" in line for line in log_a)
    assert not any("b-stage-" in line for line in log_a)
    assert any("b-stage-" in line for line in log_b)
    assert not any("a-stage-" in line for line in log_b)


async def _git_log_subjects(freeze_dir: Path) -> list[str]:
    proc = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(freeze_dir),
        "log",
        "--pretty=%s",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode().splitlines()
