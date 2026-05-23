# ABOUTME: T2/T4 — RazorbackClaudeCode renders --plugin-dir + --agent flags when
# ABOUTME: plugin_dirs + sub_agent kwargs are supplied; build_inner_agent threads both.

from pathlib import Path

import pytest

from razorback.agents._runtime.claude import (
    RazorbackClaudeCode,
    build_inner_agent,
)
from razorback.agents.spacedock_solver import SpacedockSolverAgentError


def test_plugin_dirs_render_repeatable_plugin_dir_flags(tmp_path):
    agent = RazorbackClaudeCode(
        logs_dir=tmp_path,
        model_name="claude-opus-4-7",
        plugin_dirs=["/path/to/spacedock", "/other/plug"],
    )
    flags = agent.build_cli_flags()
    assert "--plugin-dir /path/to/spacedock" in flags
    assert "--plugin-dir /other/plug" in flags


def test_sub_agent_renders_agent_flag(tmp_path):
    agent = RazorbackClaudeCode(
        logs_dir=tmp_path,
        model_name="claude-opus-4-7",
        sub_agent="spacedock:first-officer",
    )
    flags = agent.build_cli_flags()
    assert "--agent spacedock:first-officer" in flags


def test_default_flags_unchanged_when_no_plugin_or_agent(tmp_path):
    agent = RazorbackClaudeCode(logs_dir=tmp_path, model_name="claude-opus-4-7")
    flags = agent.build_cli_flags()
    assert "--plugin-dir" not in flags
    assert "--agent " not in flags


def test_build_inner_agent_threads_plugin_dirs_and_sub_agent(tmp_path):
    inner = build_inner_agent(
        logs_dir=tmp_path,
        model="claude-opus-4-7",
        harbor_agent_kwargs={"max_turns": 50},
        extra_env={"CLAUDE_CODE_OAUTH_TOKEN": "x"},
        plugin_dirs=[Path("/p1"), "/p2"],
        sub_agent="spacedock:first-officer",
    )
    flags = inner.build_cli_flags()
    assert "--plugin-dir /p1" in flags
    assert "--plugin-dir /p2" in flags
    assert "--agent spacedock:first-officer" in flags
    assert "--max-turns 50" in flags


def test_build_inner_agent_without_plugin_or_subagent_preserves_existing_shape(tmp_path):
    inner = build_inner_agent(
        logs_dir=tmp_path,
        model="claude-opus-4-7",
        harbor_agent_kwargs={"max_turns": 50},
        extra_env={"CLAUDE_CODE_OAUTH_TOKEN": "x"},
    )
    flags = inner.build_cli_flags()
    assert "--plugin-dir" not in flags
    assert "--agent " not in flags
    assert "--max-turns 50" in flags


def test_unsupported_harbor_agent_kwargs_still_raises(tmp_path):
    with pytest.raises(SpacedockSolverAgentError):
        build_inner_agent(
            logs_dir=tmp_path,
            model="claude-opus-4-7",
            harbor_agent_kwargs={"definitely_unsupported": 1},
            extra_env={"CLAUDE_CODE_OAUTH_TOKEN": "x"},
        )
