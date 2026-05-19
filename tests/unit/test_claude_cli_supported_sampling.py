# ABOUTME: AC-5 — supported_sampling() returns exactly {"temperature"}.

from razorback.agents.claude_cli import ClaudeCliAgent


def test_supported_sampling_is_exactly_temperature():
    assert ClaudeCliAgent.supported_sampling() == {"temperature"}


def test_supported_sampling_omits_top_p_and_seed():
    s = ClaudeCliAgent.supported_sampling()
    assert "top_p" not in s
    assert "seed" not in s
