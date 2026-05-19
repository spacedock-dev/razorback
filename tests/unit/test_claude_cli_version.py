# ABOUTME: AC-4 — version() returns the string parsed from `claude --version`.

import subprocess
from unittest.mock import patch

from razorback.agents.claude_cli import ClaudeCliAgent


def _agent(tmp_path):
    return ClaudeCliAgent(logs_dir=tmp_path, model_name="claude-opus-4-5")


def test_version_parses_claude_cli_output(tmp_path):
    fake = subprocess.CompletedProcess(
        args=["claude", "--version"], returncode=0,
        stdout="0.6.3 (Claude Code)\n", stderr="",
    )
    with patch("razorback.agents.claude_cli.subprocess.run", return_value=fake) as run:
        agent = _agent(tmp_path)
        assert agent.version() == "0.6.3 (Claude Code)"
        run.assert_called_once()
        called_argv = run.call_args.args[0]
        assert called_argv == ["claude", "--version"]


def test_version_returns_none_on_cli_missing(tmp_path):
    with patch(
        "razorback.agents.claude_cli.subprocess.run",
        side_effect=FileNotFoundError("claude"),
    ):
        agent = _agent(tmp_path)
        assert agent.version() is None


def test_version_returns_none_on_nonzero_exit(tmp_path):
    fake = subprocess.CompletedProcess(
        args=["claude", "--version"], returncode=1, stdout="", stderr="boom",
    )
    with patch("razorback.agents.claude_cli.subprocess.run", return_value=fake):
        agent = _agent(tmp_path)
        assert agent.version() is None
