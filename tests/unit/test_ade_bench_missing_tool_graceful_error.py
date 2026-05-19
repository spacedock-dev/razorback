# ABOUTME: FU-2 AC-4 — setup() raises typed ClaudeCliAgentError naming the missing
# ABOUTME: binary when `claude --version` exits 127 inside the container.

from unittest.mock import AsyncMock, MagicMock

import pytest

from razorback.agents.claude_cli import ClaudeCliAgent, ClaudeCliAgentError


def _env_with_exit_127():
    """A harbor environment whose .exec returns exit 127 (binary not found)."""
    env = MagicMock()
    env.exec = AsyncMock(
        return_value=MagicMock(
            return_code=127,
            stdout="",
            stderr="claude: not found",
        )
    )
    return env


async def test_missing_claude_binary_emits_typed_error_naming_binary(tmp_path):
    """AC-4 contract: typed ClaudeCliAgentError + binary name in message."""
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
        extra_env={"ANTHROPIC_API_KEY": "sk-1"},
    )
    with pytest.raises(ClaudeCliAgentError) as exc_info:
        await agent.setup(_env_with_exit_127())
    msg = str(exc_info.value)
    assert "claude" in msg
    assert "127" in msg
    # The typed-error class — not a bare Exception.
    assert isinstance(exc_info.value, ClaudeCliAgentError)


async def test_missing_binary_error_carries_stderr_for_diagnosis(tmp_path):
    """AC-4 — stderr is forwarded so a triage reader sees the underlying message."""
    env = MagicMock()
    env.exec = AsyncMock(
        return_value=MagicMock(
            return_code=127,
            stdout="",
            stderr="exec: claude: not found",
        )
    )
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
        extra_env={"ANTHROPIC_API_KEY": "sk-1"},
    )
    with pytest.raises(ClaudeCliAgentError) as exc_info:
        await agent.setup(env)
    assert "claude: not found" in str(exc_info.value)
