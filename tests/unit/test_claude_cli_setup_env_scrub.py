# ABOUTME: AC-2 — setup() scrubs env, injects ONLY the chosen auth, never co-mingles.

from unittest.mock import AsyncMock, MagicMock

import pytest

from razorback.agents.claude_cli import ClaudeCliAgent


def _make_environment(version_rc=0):
    env = MagicMock()
    env.exec = AsyncMock(
        return_value=MagicMock(
            return_code=version_rc, stdout="0.6.3 (Claude Code)\n", stderr=""
        )
    )
    return env


async def test_setup_with_only_api_key_carries_only_api_key(tmp_path):
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
        resolved_auth_env={"ANTHROPIC_API_KEY": "sk-1"},
    )
    await agent.setup(_make_environment())
    assert "ANTHROPIC_API_KEY" in agent._exec_env
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in agent._exec_env
    assert agent._exec_env["ANTHROPIC_API_KEY"] == "sk-1"


async def test_setup_with_only_oauth_carries_only_oauth(tmp_path):
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
        resolved_auth_env={"CLAUDE_CODE_OAUTH_TOKEN": "oauth-1"},
    )
    await agent.setup(_make_environment())
    assert "CLAUDE_CODE_OAUTH_TOKEN" in agent._exec_env
    assert "ANTHROPIC_API_KEY" not in agent._exec_env


async def test_setup_refuses_to_co_mingle(tmp_path):
    with pytest.raises(Exception):
        ClaudeCliAgent(
            logs_dir=tmp_path,
            model_name="claude-opus-4-5",
            resolved_auth_env={
                "ANTHROPIC_API_KEY": "sk-1",
                "CLAUDE_CODE_OAUTH_TOKEN": "oauth-1",
            },
        )


async def test_setup_carries_proxy_block_into_exec_env(tmp_path):
    """The proxy block from run_experiment.py:1515-1525 must ride alongside the auth."""
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
        resolved_auth_env={"ANTHROPIC_API_KEY": "sk-1"},
    )
    await agent.setup(_make_environment())
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
              "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        assert k in agent._exec_env
    assert agent._exec_env["HTTP_PROXY"] == "http://127.0.0.1:1"
    assert ".anthropic.com" in agent._exec_env["NO_PROXY"]


async def test_setup_validates_claude_binary_inside_container(tmp_path):
    """setup() runs `claude --version` inside the container; non-zero exit → raise."""
    env = _make_environment(version_rc=127)
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
        resolved_auth_env={"ANTHROPIC_API_KEY": "sk-1"},
    )
    with pytest.raises(Exception):
        await agent.setup(env)
