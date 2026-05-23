# ABOUTME: PKG-26 AC-1/AC-5 — RazorbackClaudeCode is a ClaudeCode subclass; identity and
# ABOUTME: razorback-specific surface (name, supported_sampling, co-mingled auth) preserved.

from harbor.agents.installed.claude_code import ClaudeCode

from razorback.agents._runtime.claude import RazorbackClaudeCode


def test_razorback_claude_code_subclasses_harbor_claude_code(tmp_path):
    """AC-1: instance is-a ClaudeCode (inherits stream-json + cost parsing)."""
    agent = RazorbackClaudeCode(logs_dir=tmp_path, model_name="claude-opus-4-7")
    assert isinstance(agent, ClaudeCode)


def test_razorback_claude_code_class_is_subclass_of_claude_code():
    assert issubclass(RazorbackClaudeCode, ClaudeCode)


def test_name_is_claude_cli():
    """AC-5: razorback's spec discriminator stays stable."""
    assert RazorbackClaudeCode.name() == "claude-cli"


def test_supported_sampling_is_temperature_only():
    """AC-5: razorback contract — temperature only, no top_p/seed."""
    assert RazorbackClaudeCode.supported_sampling() == {"temperature"}
