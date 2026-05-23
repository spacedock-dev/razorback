# ABOUTME: Direct agent.kind: codex schema path for minimal Codex runs.
# ABOUTME: Ensures solver-workflow and sealed-hash fields stay out of the direct agent.

import pytest
import yaml
from pydantic import ValidationError

from razorback.spec.schema import CodexAgentBlock, Spec


def test_codex_agent_block_parses_minimal_runtime_options():
    block = CodexAgentBlock(
        kind="codex",
        model="gpt-5.5",
        sampling={"temperature": 0.0, "top_p": None, "seed": None},
        reasoning_effort="xhigh",
        reasoning_summary="auto",
        override_timeout_sec=1200,
        max_timeout_sec=1200,
    )

    assert block.kind == "codex"
    assert block.model == "gpt-5.5"
    assert block.reasoning_effort == "xhigh"
    assert block.reasoning_summary == "auto"


@pytest.mark.parametrize(
    "field,value",
    [
        ("solver_workflow", "."),
        ("solver_workflow_content_hash", "sha256:" + "a" * 64),
        ("sealed_hash", "deadbeef" * 4),
        ("tools_allowed", []),
        ("tools_denied", []),
    ],
)
def test_codex_agent_rejects_solver_only_and_tool_policy_fields(field, value):
    with pytest.raises(ValidationError):
        CodexAgentBlock(kind="codex", model="gpt-5.5", **{field: value})


@pytest.mark.parametrize(
    "sampling",
    [
        {"temperature": 0.2, "top_p": None, "seed": None},
        {"temperature": 0.0, "top_p": 0.95, "seed": None},
        {"temperature": 0.0, "top_p": None, "seed": 1},
    ],
)
def test_codex_agent_rejects_unsupported_sampling_controls(sampling):
    with pytest.raises(ValidationError, match="sampling controls"):
        CodexAgentBlock(kind="codex", model="gpt-5.5", sampling=sampling)


def test_codex_discriminator_routes_full_spec():
    spec_yaml = """
version: 1
experiment: direct-codex-schema-test
agent:
  kind: codex
  model: gpt-5.5
  sampling: {temperature: 0.0}
  reasoning_effort: xhigh
benchmark:
  kind: local
  task_paths: []
trials: 1
"""
    spec = Spec.model_validate(yaml.safe_load(spec_yaml))

    assert isinstance(spec.agent, CodexAgentBlock)
    assert spec.agent.kind == "codex"
