# ABOUTME: AC-2 — setup() scrubs env, injects ONLY the chosen auth, never co-mingles.
# ABOUTME: Post FU-1 AC-2: auth is read from os.environ inside the container (not constructor).

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


@pytest.fixture(autouse=True)
def _clear_claude_auth_env(monkeypatch):
    """Tests own their own env; clear any inherited claude credentials."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)


async def test_setup_with_only_api_key_carries_only_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-1")
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
    )
    await agent.setup(_make_environment())
    assert "ANTHROPIC_API_KEY" in agent._exec_env
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in agent._exec_env
    assert agent._exec_env["ANTHROPIC_API_KEY"] == "sk-1"


async def test_setup_with_only_oauth_carries_only_oauth(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-1")
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
    )
    await agent.setup(_make_environment())
    assert "CLAUDE_CODE_OAUTH_TOKEN" in agent._exec_env
    assert "ANTHROPIC_API_KEY" not in agent._exec_env


async def test_setup_refuses_to_co_mingle(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-1")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-1")
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
    )
    with pytest.raises(Exception) as exc:
        await agent.setup(_make_environment())
    assert "cannot both be set" in str(exc.value)


async def test_setup_refuses_when_no_auth_present(tmp_path):
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
    )
    with pytest.raises(Exception):
        await agent.setup(_make_environment())


async def test_setup_carries_proxy_block_into_exec_env(tmp_path, monkeypatch):
    """The proxy block from run_experiment.py:1515-1525 must ride alongside the auth."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-1")
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
    )
    await agent.setup(_make_environment())
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
              "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        assert k in agent._exec_env
    assert agent._exec_env["HTTP_PROXY"] == "http://127.0.0.1:1"
    assert ".anthropic.com" in agent._exec_env["NO_PROXY"]


async def test_setup_validates_claude_binary_inside_container(tmp_path, monkeypatch):
    """setup() runs `claude --version` inside the container; non-zero exit → raise."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-1")
    env = _make_environment(version_rc=127)
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
    )
    with pytest.raises(Exception):
        await agent.setup(env)
