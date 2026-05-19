# ABOUTME: Tests for razorback.agents.registry — agent.kind → kwargs schema mapping.
# ABOUTME: Asserts claude-cli kind validates a minimal config and rejects unknown fields.

import pytest

from razorback.agents.registry import AgentKindError, resolve_agent_kind


def test_claude_cli_kind_resolves_to_a_schema_and_import_path():
    entry = resolve_agent_kind("claude-cli")
    assert entry.import_path == "razorback.agents.claude_cli:ClaudeCliAgent"
    cfg = entry.config_schema(model="claude-opus-4-5", tools_allowed=[], prompt_file=None)
    assert cfg.model == "claude-opus-4-5"
    assert cfg.tools_allowed == []


def test_claude_cli_kind_rejects_unknown_kwargs():
    entry = resolve_agent_kind("claude-cli")
    with pytest.raises(Exception):
        entry.config_schema(model="x", tools_allowed=[], prompt_file=None, frobnicator=True)


def test_unknown_kind_raises_agent_kind_error():
    with pytest.raises(AgentKindError):
        resolve_agent_kind("definitely-not-a-real-kind")


def test_nop_kind_still_resolves_for_back_compat_with_m1_m2():
    entry = resolve_agent_kind("nop")
    assert entry.import_path is None
    cfg = entry.config_schema()
    assert cfg.model_dump() == {}
