# ABOUTME: PKG-9 carry-forward — DISALLOWED_TOOLS list matches upstream verbatim.
# ABOUTME: Source: dataagentbench/benchmark/lib/run_experiment.py:1531-1549.

from razorback_plugin_dab.generate.tools_denied import (
    DISALLOWED_TOOLS,
    generate_settings_json,
)


def test_denial_list_anchor_entries():
    assert "WebFetch" in DISALLOWED_TOOLS
    assert "WebSearch" in DISALLOWED_TOOLS
    assert "Bash(curl *)" in DISALLOWED_TOOLS
    assert "Bash(wget *)" in DISALLOWED_TOOLS
    assert "Bash(git clone *)" in DISALLOWED_TOOLS
    assert "Bash(huggingface-cli *)" in DISALLOWED_TOOLS
    assert "Bash(pip install datasets*)" in DISALLOWED_TOOLS
    assert "Bash(uv pip install transformers*)" in DISALLOWED_TOOLS


def test_denial_list_length_matches_upstream():
    # Upstream lines 1531-1549 declare exactly 29 entries
    # (2 Web* + 3 Bash-net + 2 Bash-hf + 4+4+4+4 install-variants + 3+3 module-form).
    assert len(DISALLOWED_TOOLS) == 29


def test_settings_json_carries_denials():
    settings = generate_settings_json("bookreview-q1")
    denials = settings["permissions"]["deny"]
    assert denials == list(DISALLOWED_TOOLS)
    assert settings["_provenance"]["task"] == "bookreview-q1"
    assert "run_experiment.py" in settings["_provenance"]["source"]
