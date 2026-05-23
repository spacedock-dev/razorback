# ABOUTME: AC-5 — supported_sampling() returns exactly {"temperature"}.

from razorback.agents._runtime.claude import RazorbackClaudeCode


def test_supported_sampling_is_exactly_temperature():
    assert RazorbackClaudeCode.supported_sampling() == {"temperature"}


def test_supported_sampling_omits_top_p_and_seed():
    s = RazorbackClaudeCode.supported_sampling()
    assert "top_p" not in s
    assert "seed" not in s
