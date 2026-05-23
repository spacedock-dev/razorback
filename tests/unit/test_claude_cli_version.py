# ABOUTME: AC-4 — version() returns the string captured by setup()'s container-side
# ABOUTME: `claude --version` exec. Harbor's BaseInstalledAgent.version() returns self._version.

from unittest.mock import AsyncMock, MagicMock

from razorback.agents._runtime.claude import RazorbackClaudeCode


def _make_environment(version_rc=0, stdout="0.6.3 (Claude Code)\n"):
    env = MagicMock()
    env.exec = AsyncMock(
        return_value=MagicMock(return_code=version_rc, stdout=stdout, stderr="")
    )
    return env


async def test_version_is_captured_from_container_setup(tmp_path):
    """setup() captures `claude --version` stdout into self._version."""
    agent = RazorbackClaudeCode(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
        extra_env={"ANTHROPIC_API_KEY": "sk-1"},
    )
    await agent.setup(_make_environment(stdout="0.6.3 (Claude Code)\n"))
    assert agent.version() == "0.6.3 (Claude Code)"


async def test_version_is_none_before_setup(tmp_path):
    """Before setup() runs, _version is unset (harbor default None)."""
    agent = RazorbackClaudeCode(logs_dir=tmp_path, model_name="claude-opus-4-5")
    assert agent.version() is None
