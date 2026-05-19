# ABOUTME: AC-6 — setup() filters MCP servers against tools_allowed and stamps the
# ABOUTME: DISALLOWED_TOOLS list. env carries proxy block + auth + HOME only.

from unittest.mock import AsyncMock, MagicMock

import pytest

from harbor.models.task.config import MCPServerConfig

from razorback.agents.claude_invoke import DISALLOWED_TOOLS
from razorback.agents.spacedock_solver import (
    SpacedockSolverAgent,
    SpacedockSolverAgentError,
)
from razorback.agents.seal import compute_sealed_hash, prompt_sha256


def _make_environment(version_rc=0, git_rc=0):
    env = MagicMock()

    async def fake_exec(cmd, **kw):
        if cmd.startswith("claude --version"):
            rc = version_rc
        elif cmd.startswith("git --version"):
            rc = git_rc
        else:
            rc = 0
        result = MagicMock()
        result.return_code = rc
        result.stdout = "ok"
        result.stderr = ""
        return result

    env.exec = AsyncMock(side_effect=fake_exec)
    return env


def _agent_kwargs(tmp_path, **overrides):
    # Build a valid frozen-style agent: sealed_hash matches prompts.
    body_m = b"M\n"
    body_a = b"A\n"
    body_v = b"V\n"
    prompts = {
        "model": prompt_sha256(body_m),
        "analyze": prompt_sha256(body_a),
        "verify": prompt_sha256(body_v),
    }
    sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes=prompts,
    )
    base = dict(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        tools_allowed=["Bash", "Read"],
        prompts=prompts,
        sealed_hash=sealed,
        extra_env={"ANTHROPIC_API_KEY": "sk-test"},
        prompt_contents={
            "model": body_m.decode(),
            "analyze": body_a.decode(),
            "verify": body_v.decode(),
        },
        prior_frozen_spec_path=None,
    )
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_setup_filters_mcp_servers_against_tools_allowed(tmp_path):
    mcp_bash = MCPServerConfig(name="Bash", transport="stdio", command="echo bash")
    mcp_webfetch = MCPServerConfig(name="WebFetch", transport="stdio", command="echo webfetch")
    agent = SpacedockSolverAgent(
        mcp_servers=[mcp_bash, mcp_webfetch],
        **_agent_kwargs(tmp_path, tools_allowed=["Bash", "Read"]),
    )
    await agent.setup(_make_environment())
    remaining = [s.name for s in agent.mcp_servers]
    assert remaining == ["Bash"]
    assert "WebFetch" not in remaining


@pytest.mark.asyncio
async def test_setup_does_not_filter_when_tools_allowed_is_empty(tmp_path):
    mcp_bash = MCPServerConfig(name="Bash", transport="stdio", command="echo bash")
    mcp_webfetch = MCPServerConfig(name="WebFetch", transport="stdio", command="echo webfetch")
    agent = SpacedockSolverAgent(
        mcp_servers=[mcp_bash, mcp_webfetch],
        **_agent_kwargs(tmp_path, tools_allowed=[]),
    )
    await agent.setup(_make_environment())
    assert {s.name for s in agent.mcp_servers} == {"Bash", "WebFetch"}


@pytest.mark.asyncio
async def test_setup_env_carries_only_proxy_auth_and_home(tmp_path):
    agent = SpacedockSolverAgent(**_agent_kwargs(tmp_path))
    await agent.setup(_make_environment())
    keys = set(agent._exec_env.keys())
    assert "ANTHROPIC_API_KEY" in keys
    assert "HTTP_PROXY" in keys
    assert "NO_PROXY" in keys
    assert "HF_HUB_OFFLINE" in keys
    assert "HOME" in keys
    assert "PATH" not in keys
    assert "USER" not in keys


@pytest.mark.asyncio
async def test_setup_refuses_without_git_binary(tmp_path):
    agent = SpacedockSolverAgent(**_agent_kwargs(tmp_path))
    with pytest.raises(SpacedockSolverAgentError):
        await agent.setup(_make_environment(git_rc=127))


@pytest.mark.asyncio
async def test_setup_refuses_without_claude_binary(tmp_path):
    agent = SpacedockSolverAgent(**_agent_kwargs(tmp_path))
    with pytest.raises(SpacedockSolverAgentError):
        await agent.setup(_make_environment(version_rc=127))


def test_disallowed_tools_list_matches_run_experiment():
    assert "WebFetch" in DISALLOWED_TOOLS
    assert "Bash(curl *)" in DISALLOWED_TOOLS
    assert "Bash(pip install datasets*)" in DISALLOWED_TOOLS
    assert "Bash(pip3 install evaluate*)" in DISALLOWED_TOOLS
