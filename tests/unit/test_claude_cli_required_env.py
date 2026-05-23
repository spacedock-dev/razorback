# ABOUTME: AC-1 — RazorbackClaudeCode declares required-env names; the declaration is an
# ABOUTME: alternation (ANTHROPIC_API_KEY OR CLAUDE_CODE_OAUTH_TOKEN — not both required).

from razorback.agents._runtime.claude import RazorbackClaudeCode


def test_required_env_lists_exactly_the_two_auth_alternates():
    declared = RazorbackClaudeCode.required_env()
    assert isinstance(declared, dict)
    assert declared["mode"] == "alternation"
    assert sorted(declared["names"]) == ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"]


def test_required_env_is_a_class_method_callable_without_instance():
    declared = RazorbackClaudeCode.required_env()
    assert declared is not None
