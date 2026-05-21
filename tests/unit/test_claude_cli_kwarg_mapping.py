# ABOUTME: PKG-26 AC-2 — translator emits tools_allowed/sampling_temperature kwargs;
# ABOUTME: ClaudeCliAgent maps them to harbor's allowed_tools CLI flag and stashes temperature.

from razorback.agents.claude_cli import ClaudeCliAgent


def test_tools_allowed_lands_in_harbor_allowed_tools_flag(tmp_path):
    """AC-2: razorback's tools_allowed list → harbor's --allowedTools CSV."""
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-7",
        tools_allowed=["Bash", "Read"],
    )
    flags = agent.build_cli_flags()
    assert "--allowedTools Bash,Read" in flags


def test_disallowed_tools_includes_razorback_block_list(tmp_path):
    """Razorback's DISALLOWED_TOOLS block list (WebFetch/WebSearch/etc.) is enforced
    via harbor's --disallowedTools flag.
    """
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-7",
        tools_allowed=["Bash"],
    )
    flags = agent.build_cli_flags()
    assert "--disallowedTools" in flags
    assert "WebFetch" in flags
    assert "WebSearch" in flags


def test_sampling_temperature_is_preserved_on_instance(tmp_path):
    """Razorback honors sampling_temperature as a contract field; harbor's ClaudeCode
    has no temperature CLI flag, but the instance must record the requested value.
    """
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-7",
        sampling_temperature=0.0,
    )
    assert agent._sampling_temperature == 0.0


def test_default_tools_allowed_when_unset(tmp_path):
    """When tools_allowed is None/empty, default to DEFAULT_ALLOWED_TOOLS."""
    from razorback.agents.claude_invoke import DEFAULT_ALLOWED_TOOLS

    agent = ClaudeCliAgent(logs_dir=tmp_path, model_name="claude-opus-4-7")
    flags = agent.build_cli_flags()
    expected_csv = ",".join(DEFAULT_ALLOWED_TOOLS)
    assert f"--allowedTools {expected_csv}" in flags
