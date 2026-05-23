# ABOUTME: AC-2 mechanism gate — freeze tree written from worktree A is
# ABOUTME: discoverable from worktree B sharing the same $RAZORBACK_FREEZE_DIR.

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from razorback.agents.spacedock_solver import SpacedockSolverAgent

REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_worktree(repo_root: Path, base: Path, name: str) -> Path:
    wt = base / name
    subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "add",
         "--detach", str(wt), "HEAD"],
        check=True, capture_output=True,
    )
    return wt


def _force_remove(repo_root: Path, wt: Path) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "remove", "--force", str(wt)],
        check=True, capture_output=True,
    )


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


def _make_logs_dir(worktree_root: Path, trial_name: str) -> Path:
    logs = worktree_root / "runs" / "exp" / "job" / "trials" / trial_name / "logs" / "agent"
    logs.mkdir(parents=True, exist_ok=True)
    (worktree_root / "runs" / "exp" / "job" / "spec.frozen.yaml").write_text(
        "placeholder"
    )
    return logs


@pytest.mark.asyncio
async def test_freeze_survives_worktree_a_teardown_and_is_visible_from_worktree_b(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cas_root = tmp_path / "freeze-cas"
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(cas_root))

    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    wt_a = _make_worktree(REPO_ROOT, tmp_path, "wt-a")
    wt_b = _make_worktree(REPO_ROOT, tmp_path, "wt-b")
    try:
        # Construct + setup agent from inside worktree A's surface.
        logs_a = _make_logs_dir(wt_a, "task-0001__abc1234")
        agent_a = SpacedockSolverAgent(
            logs_dir=logs_a, **_common_kwargs(workflow)
        )
        fake_env = MagicMock()
        fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
        agent_a._inner = MagicMock()
        agent_a._inner.setup = AsyncMock()
        await agent_a.setup(fake_env)

        freeze_a = agent_a.resolve_freeze_dir()
        assert freeze_a.is_relative_to(cas_root), (
            f"freeze_a {freeze_a} is not under CAS root {cas_root}"
        )
        assert (freeze_a / "sealed_hash.txt").read_text().strip() == agent_a.sealed_hash
    finally:
        _force_remove(REPO_ROOT, wt_a)

    # Worktree A is gone. Build agent B from inside worktree B with the
    # SAME inputs (same sealed_hash) and confirm discovery.
    try:
        logs_b = _make_logs_dir(wt_b, "task-0001__deadbeef")
        agent_b = SpacedockSolverAgent(
            logs_dir=logs_b, **_common_kwargs(workflow)
        )
        assert agent_b.sealed_hash == agent_a.sealed_hash, (
            "sealed_hash must be input-derived, not worktree-derived"
        )
        freeze_b = agent_b.resolve_freeze_dir()
        assert freeze_b == freeze_a, (
            f"AC-2 violated: agent B resolved {freeze_b}, not the shared {freeze_a}"
        )
        # The pre-existing freeze tree is intact (worktree A teardown did not destroy it).
        assert (freeze_b / "sealed_hash.txt").exists()
        assert (freeze_b / ".git").is_dir()
    finally:
        _force_remove(REPO_ROOT, wt_b)
