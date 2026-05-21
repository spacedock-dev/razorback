# ABOUTME: AC-2 + AC-4, SpacedockSolverAgent v2 class: sealed_hash, refusal, KEEP-VERBATIM extractions.
# ABOUTME: Per spec §4.3 + §8.4. Constructs with valid kwargs; refuses on resume mismatch (exit 20).

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from razorback.agents.seal import compute_sealed_hash
from razorback.agents.spacedock_solver_v2 import (
    SpacedockSolverAgent,
    SpacedockSolverAgentError,
)
from razorback.errors import SeedMismatchError


def _valid_kwargs(tmp_path: Path) -> dict:
    workflow = tmp_path / "solver"
    workflow.mkdir(exist_ok=True)
    (workflow / "README.md").write_text("## Stages\n- model\n- analyze\n")
    logs_dir = tmp_path / "trial-logs"
    logs_dir.mkdir(exist_ok=True)
    return dict(
        logs_dir=logs_dir,
        runtime="claude",
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": None},
        solver_workflow=workflow,
        solver_workflow_content_hash="sha256:" + "a" * 64,
        prompt_content_hashes={"readme": "sha256:" + "b" * 64},
        spacedock_skill_version="1.0.0",
        harbor_agent_kwargs={"max_turns": 200, "tools_allowed": [], "tools_denied": []},
        max_turns=200,
        tools_allowed=[],
        tools_denied=[],
        extra_env={"ANTHROPIC_API_KEY": "sk-fake"},
    )


def test_constructor_validates_and_computes_sealed_hash(tmp_path):
    kw = _valid_kwargs(tmp_path)
    agent = SpacedockSolverAgent(**kw)
    expected = compute_sealed_hash(
        model=kw["model"],
        sampling=kw["sampling"],
        solver_workflow_content_hash=kw["solver_workflow_content_hash"],
        prompt_content_hashes=kw["prompt_content_hashes"],
        spacedock_skill_version=kw["spacedock_skill_version"],
        harbor_agent_kwargs=kw["harbor_agent_kwargs"],
    )
    assert agent.sealed_hash == expected


@pytest.mark.asyncio
async def test_run_sends_solver_workflow_readme_before_task_instruction(tmp_path):
    kw = _valid_kwargs(tmp_path)
    readme = Path(kw["solver_workflow"]) / "README.md"
    readme.write_text("# Solver Workflow\n\nRead task-local instructions first.\n")
    agent = SpacedockSolverAgent(**kw)
    agent._inner = MagicMock()
    agent._inner.run = AsyncMock()
    environment = MagicMock()
    context = MagicMock()

    await agent.run("task instruction", environment, context)

    environment.exec.assert_not_called()
    agent._inner.run.assert_awaited_once()
    delegated_instruction = agent._inner.run.await_args.args[0]
    assert "# Solver Workflow" in delegated_instruction
    assert "task instruction" in delegated_instruction
    assert delegated_instruction.index("# Solver Workflow") < delegated_instruction.index(
        "task instruction"
    )
    assert agent._inner.run.await_args.args[1:] == (environment, context)


def test_co_mingled_auth_refused(tmp_path):
    kw = _valid_kwargs(tmp_path)
    kw["extra_env"] = {"ANTHROPIC_API_KEY": "x", "CLAUDE_CODE_OAUTH_TOKEN": "y"}
    with pytest.raises(SpacedockSolverAgentError, match="cannot both be set"):
        SpacedockSolverAgent(**kw)


def test_resume_mismatch_refuses_with_exit_20(tmp_path):
    """Per b5 contract point 4: sealed_hash.txt mismatch raises SeedMismatchError."""
    kw = _valid_kwargs(tmp_path)
    freeze_dir = tmp_path / "_razorback_prior" / "freeze" / ("deadbeef" * 4)
    freeze_dir.mkdir(parents=True)
    (freeze_dir / "sealed_hash.txt").write_text("deadbeef" * 4)
    kw["resume_from_freeze"] = freeze_dir
    with pytest.raises(SeedMismatchError):
        SpacedockSolverAgent(**kw)
    from razorback.errors import SeedMismatchError as E
    assert E.exit_code == 20


def test_each_of_six_sealed_inputs_perturbs_hash(tmp_path):
    """AC-2: perturbing each of the six sealed inputs in isolation flips the hash."""
    base_kw = _valid_kwargs(tmp_path)
    base = SpacedockSolverAgent(**base_kw).sealed_hash
    perturbations = [
        ("model", "claude-sonnet-4-6"),
        ("sampling", {"temperature": 0.7, "top_p": None, "seed": None}),
        ("solver_workflow_content_hash", "sha256:" + "c" * 64),
        ("prompt_content_hashes", {"readme": "sha256:" + "d" * 64}),
        ("spacedock_skill_version", "1.0.1"),
        (
            "harbor_agent_kwargs",
            {"max_turns": 201, "tools_allowed": [], "tools_denied": []},
        ),
    ]
    for field, perturbed in perturbations:
        kw = {**base_kw, field: perturbed}
        h = SpacedockSolverAgent(**kw).sealed_hash
        assert h != base, f"perturbing {field} did not flip sealed_hash"


def test_extra_env_redaction_invariant(tmp_path):
    """AC-4: FU-1, extra_env carries secrets; they must not appear in repr or str."""
    kw = _valid_kwargs(tmp_path)
    kw["extra_env"] = {"ANTHROPIC_API_KEY": "sk-SECRET-VALUE"}
    agent = SpacedockSolverAgent(**kw)
    assert "sk-SECRET-VALUE" not in repr(agent)
    assert "sk-SECRET-VALUE" not in str(agent)
