# ABOUTME: PKG-38 compatibility checks for legacy agent.kind: claude-cli specs.
# ABOUTME: Active translation routes old specs to the RazorbackClaudeCode runtime helper.

from pathlib import Path

import pytest

from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text
from razorback.translate import spec_to_job_config


LEGACY_SPEC = """\
version: 1
experiment: legacy-claude-cli-compat
agent:
  kind: claude-cli
  model: claude-opus-4-5
  sampling:
    temperature: {temperature}
  tools_allowed: [Read, Write]
benchmark:
  kind: local
  task_paths: []
trials: 1
"""


def _translate(tmp_path: Path, *, temperature: float = 0.0):
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test\n")
    spec = parse_spec_text(LEGACY_SPEC.format(temperature=temperature))
    cfg, _ = spec_to_job_config(
        spec,
        job_name="legacy-compat",
        jobs_dir=tmp_path / "jobs",
        project_root=tmp_path,
    )
    return cfg.agents[0]


def test_legacy_claude_cli_translates_to_harbor_claude_code_subclass(tmp_path):
    agent_cfg = _translate(tmp_path)

    assert (
        agent_cfg.import_path
        == "razorback.agents._runtime.claude:RazorbackClaudeCode"
    )
    assert agent_cfg.model_name == "claude-opus-4-5"
    assert agent_cfg.kwargs == {
        "allowed_tools": "Read,Write",
    }
    assert agent_cfg.env == {"ANTHROPIC_API_KEY": "sk-test"}


def test_legacy_claude_cli_accepts_default_sampling_temperature(tmp_path):
    agent_cfg = _translate(tmp_path, temperature=0.0)

    assert "sampling_temperature" not in agent_cfg.kwargs


def test_legacy_claude_cli_rejects_non_default_temperature(tmp_path):
    with pytest.raises(SpecError, match="ClaudeCode.*temperature"):
        _translate(tmp_path, temperature=0.7)


def test_legacy_claude_cli_ignores_seed_and_top_p_metadata(tmp_path):
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test\n")
    spec = parse_spec_text(
        """\
version: 1
experiment: legacy-claude-cli-sampling-metadata
agent:
  kind: claude-cli
  model: claude-opus-4-5
  sampling:
    temperature: 0.0
    seed: 1
    top_p: 0.9
  tools_allowed: [Read]
benchmark:
  kind: local
  task_paths: []
trials: 1
"""
    )

    cfg, _ = spec_to_job_config(
        spec,
        job_name="legacy-sampling-metadata",
        jobs_dir=tmp_path / "jobs",
        project_root=tmp_path,
    )

    agent_cfg = cfg.agents[0]
    assert (
        agent_cfg.import_path
        == "razorback.agents._runtime.claude:RazorbackClaudeCode"
    )
    assert agent_cfg.kwargs == {"allowed_tools": "Read"}
