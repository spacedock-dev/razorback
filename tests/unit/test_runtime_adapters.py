# ABOUTME: AC-3, per-runtime adapter sub-modules exist; codex + pi raise NotImplementedError.
# ABOUTME: claude.py constructs a harbor ClaudeCode instance with the expected kwargs.

import pytest

from razorback.agents._runtime import claude as claude_adapter
from razorback.agents._runtime import codex as codex_adapter
from razorback.agents._runtime import pi as pi_adapter


def test_codex_raises_not_implemented(tmp_path):
    with pytest.raises(NotImplementedError, match="codex"):
        codex_adapter.build_inner_agent(
            logs_dir=tmp_path,
            model="any",
            harbor_agent_kwargs={},
            extra_env={},
        )


def test_pi_raises_not_implemented(tmp_path):
    with pytest.raises(NotImplementedError, match="pi"):
        pi_adapter.build_inner_agent(
            logs_dir=tmp_path,
            model="any",
            harbor_agent_kwargs={},
            extra_env={},
        )


def test_claude_constructs_inner_agent(tmp_path):
    inner = claude_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        harbor_agent_kwargs={
            "max_turns": 200,
            "tools_allowed": ["Read", "Write"],
            "tools_denied": ["Bash(rm*)"],
            "append_system_prompt": "You are the first officer.",
        },
        extra_env={"ANTHROPIC_API_KEY": "sk-fake"},
    )
    assert inner.__class__.__name__ == "ClaudeCode"


def test_claude_passes_tools_denied_through_to_harbor_kwargs(tmp_path):
    """v4-pkg9-v2 owns the PreToolUse hook plumbing; Phase 3 just passes the kwarg through.

    Harbor's ClaudeCode stashes CLI flag kwargs in `_flag_kwargs`. The adapter
    must map razorback's `tools_denied` field to harbor's `disallowed_tools`.
    """
    inner = claude_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        harbor_agent_kwargs={
            "max_turns": 200,
            "tools_denied": ["Bash(pip install datasets*)"],
        },
        extra_env={"ANTHROPIC_API_KEY": "x"},
    )
    flag_kwargs = getattr(inner, "_flag_kwargs", {})
    assert "disallowed_tools" in flag_kwargs, (
        f"adapter did not forward tools_denied → disallowed_tools; flag_kwargs={flag_kwargs}"
    )
    assert "Bash(pip install datasets*)" in flag_kwargs["disallowed_tools"]


def test_claude_passes_tools_allowed_through(tmp_path):
    inner = claude_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        harbor_agent_kwargs={"max_turns": 200, "tools_allowed": ["Read", "Edit"]},
        extra_env={"ANTHROPIC_API_KEY": "x"},
    )
    flag_kwargs = getattr(inner, "_flag_kwargs", {})
    assert "allowed_tools" in flag_kwargs
    assert "Read" in flag_kwargs["allowed_tools"]
    assert "Edit" in flag_kwargs["allowed_tools"]
