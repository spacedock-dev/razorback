# ABOUTME: AC-3, per-runtime adapter sub-modules exist; codex + pi raise NotImplementedError.
# ABOUTME: claude.py constructs razorback's ClaudeCliAgent (a ClaudeCode subclass) so
# ABOUTME: the spacedock v2 inner emits cost_usd + claude-output.jsonl (PKG-26 surface).

import pytest

from harbor.agents.installed.claude_code import ClaudeCode

from razorback.agents._runtime import claude as claude_adapter
from razorback.agents._runtime import codex as codex_adapter
from razorback.agents._runtime import pi as pi_adapter
from razorback.agents.claude_cli import ClaudeCliAgent


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


def test_claude_constructs_inner_agent_as_claude_cli_subclass(tmp_path):
    """Inner must be razorback's ClaudeCliAgent, not harbor's ClaudeCode directly.

    Routing through ClaudeCliAgent inherits PKG-26's cost-emit + claude-output.jsonl
    audit sentinel. Returning harbor.ClaudeCode directly (the earlier shape) silently
    dropped cost_usd telemetry even under paid-API auth — surfaced live during
    Goal 1 RESUME cell 1 (spacedock/agnews) where cost was null on disk despite
    a 3m54s opus-4.7 run, with raw tokens reconstructible only from session jsonl.
    """
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
    assert isinstance(inner, ClaudeCliAgent)
    # Defense-in-depth: ClaudeCliAgent IS a ClaudeCode subclass; the harbor base
    # contract still holds.
    assert isinstance(inner, ClaudeCode)


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
