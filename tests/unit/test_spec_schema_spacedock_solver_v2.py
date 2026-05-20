# ABOUTME: AC-7, spec.agent.kind: spacedock_solver_v2 routes to the v2 schema block.
# ABOUTME: v1's kind: spacedock-solver still routes to v1 block (per AC-8).

import pytest
from pydantic import ValidationError

from razorback.spec.schema import SpacedockSolverV2AgentBlock


def test_spacedock_solver_v2_block_parses(tmp_path):
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")
    block = SpacedockSolverV2AgentBlock(
        kind="spacedock_solver_v2",
        runtime="claude",
        model="claude-opus-4-5",
        solver_workflow=workflow,
        max_turns=200,
        max_budget_usd=10,
        tools_allowed=[],
        tools_denied=[],
    )
    assert block.runtime == "claude"
    assert block.kind == "spacedock_solver_v2"


def test_spacedock_solver_v2_runtime_enum_enforced():
    with pytest.raises(ValidationError):
        SpacedockSolverV2AgentBlock(
            kind="spacedock_solver_v2",
            runtime="unsupported",
            model="x",
            solver_workflow=".",
        )


def test_v1_spacedock_solver_block_still_parses():
    """AC-8: v1's kind: spacedock-solver routes to the v1 block; no breakage."""
    from razorback.spec.schema import SpacedockSolverAgentBlock
    block = SpacedockSolverAgentBlock(
        kind="spacedock-solver",
        prompts={"model": "p1.md", "analyze": "p2.md", "verify": "p3.md"},
    )
    assert block.kind == "spacedock-solver"


def test_v2_discriminator_routes_full_spec(tmp_path):
    """End-to-end: a full Spec with agent.kind: spacedock_solver_v2 parses to v2 block."""
    import yaml
    from razorback.spec.schema import Spec

    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    spec_yaml = f"""
version: 1
experiment: phase3-schema-test
agent:
  kind: spacedock_solver_v2
  runtime: claude
  model: claude-opus-4-5
  solver_workflow: {workflow}
  solver_workflow_content_hash: "sha256:{'a' * 64}"
  spacedock_skill_version: "1.0.0"
  sealed_hash: "0123456789abcdef0123456789abcdef"
  max_turns: 200
benchmark:
  kind: local
  task_paths: []
trials: 1
"""
    spec = Spec.model_validate(yaml.safe_load(spec_yaml))
    assert spec.agent.kind == "spacedock_solver_v2"
    assert isinstance(spec.agent, SpacedockSolverV2AgentBlock)
