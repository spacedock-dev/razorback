# ABOUTME: Phase 6, agent.kind: spacedock_solver routes to the canonical schema block.
# ABOUTME: Transitional and v1 solver spellings reject.

import pytest
from pydantic import ValidationError

from razorback.spec.schema import SpacedockSolverAgentBlock


def test_spacedock_solver_block_parses(tmp_path):
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")
    block = SpacedockSolverAgentBlock(
        kind="spacedock_solver",
        runtime="claude",
        model="claude-opus-4-5",
        solver_workflow=workflow,
        max_turns=200,
        max_budget_usd=10,
        override_timeout_sec=1200,
        override_setup_timeout_sec=300,
        max_timeout_sec=1200,
        tools_allowed=[],
        tools_denied=[],
    )
    assert block.runtime == "claude"
    assert block.kind == "spacedock_solver"
    assert block.override_timeout_sec == 1200
    assert block.override_setup_timeout_sec == 300
    assert block.max_timeout_sec == 1200


def test_spacedock_solver_runtime_enum_enforced():
    with pytest.raises(ValidationError):
        SpacedockSolverAgentBlock(
            kind="spacedock_solver",
            runtime="unsupported",
            model="x",
            solver_workflow=".",
        )


@pytest.mark.parametrize(
    "field",
    ["override_timeout_sec", "override_setup_timeout_sec", "max_timeout_sec"],
)
def test_spacedock_solver_timeout_fields_must_be_positive(field):
    with pytest.raises(ValidationError):
        SpacedockSolverAgentBlock(
            kind="spacedock_solver",
            runtime="codex",
            model="gpt-5.5",
            solver_workflow=".",
            **{field: 0},
        )


def test_spacedock_solver_max_timeout_cannot_be_less_than_override():
    with pytest.raises(ValidationError, match="max_timeout_sec"):
        SpacedockSolverAgentBlock(
            kind="spacedock_solver",
            runtime="codex",
            model="gpt-5.5",
            solver_workflow=".",
            override_timeout_sec=1200,
            max_timeout_sec=600,
        )


def test_transitional_solver_kind_rejects(tmp_path):
    import yaml
    from razorback.spec.schema import Spec

    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    stale_kind = "spacedock_" + "solver_v2"  # intentional historical rejection assertion
    spec_yaml = f"""
version: 1
experiment: phase6-stale-transitional-route-test
agent:
  kind: {stale_kind}
  runtime: claude
  model: claude-opus-4-5
  solver_workflow: {workflow}
benchmark:
  kind: local
  task_paths: []
trials: 1
"""
    with pytest.raises(ValidationError):
        Spec.model_validate(yaml.safe_load(spec_yaml))


def test_v1_hyphenated_spacedock_solver_rejects():
    import yaml
    from razorback.spec.schema import Spec

    stale_kind = "spacedock" + "-solver"
    spec_yaml = f"""
version: 1
experiment: phase6-stale-v1-route-test
agent:
  kind: {stale_kind}
  prompts:
    model: p1.md
    analyze: p2.md
    verify: p3.md
benchmark:
  kind: local
  task_paths: []
trials: 1
"""
    with pytest.raises(ValidationError):
        Spec.model_validate(yaml.safe_load(spec_yaml))


def test_canonical_discriminator_routes_full_spec(tmp_path):
    """End-to-end: a full Spec with agent.kind: spacedock_solver parses."""
    import yaml
    from razorback.spec.schema import Spec

    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    spec_yaml = f"""
version: 1
experiment: phase3-schema-test
agent:
  kind: spacedock_solver
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
    assert spec.agent.kind == "spacedock_solver"
    assert isinstance(spec.agent, SpacedockSolverAgentBlock)
