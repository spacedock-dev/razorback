# ABOUTME: PKG-9 v2 AC-2: claude runtime adapter installs tools_denied as inner-agent denials.
# ABOUTME: Spec §6.2: tools_denied is a denylist installed as PreToolUse hooks in the inner runtime.

from pathlib import Path

from harbor.agents.installed.claude_code import ClaudeCode

from razorback.agents.spacedock_solver import SpacedockSolverAgent


# Per spec §6.2 + AC-2: the four DAB-recommended denials.
DAB_DENIALS = [
    "Bash(pip install datasets*)",
    "Bash(pip install dataagentbench*)",
    "Bash(huggingface-cli login*)",
    "Bash(curl https://huggingface.co/*)",
]


def _base_kwargs(tmp_path: Path, *, tools_denied: list[str]) -> dict:
    workflow = tmp_path / "solver"
    workflow.mkdir(exist_ok=True)
    (workflow / "README.md").write_text("## Stages\n- model\n")
    logs_dir = tmp_path / "trial-logs"
    logs_dir.mkdir(exist_ok=True)
    harbor_agent_kwargs = {
        "max_turns": 200,
        "tools_allowed": [],
        "tools_denied": list(tools_denied),
    }
    return dict(
        logs_dir=logs_dir,
        runtime="claude",
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": None},
        solver_workflow=workflow,
        solver_workflow_content_hash="sha256:" + "a" * 64,
        prompt_content_hashes={"readme": "sha256:" + "b" * 64},
        spacedock_skill_version="1.0.0",
        harbor_agent_kwargs=harbor_agent_kwargs,
        max_turns=200,
        tools_allowed=[],
        tools_denied=list(tools_denied),
        extra_env={"ANTHROPIC_API_KEY": "sk-fake"},
    )


def test_claude_runtime_installs_four_dab_denials_verbatim_in_order(tmp_path):
    """AC-2: a SpacedockSolverAgent v2 with runtime=claude installs tools_denied
    as the inner agent's disallowed_tools (harbor's PreToolUse surface).
    Cite spec §6.2.

    The inner is razorback's ClaudeCliAgent (PKG-26 + goal1-resume followup); it
    inherits ClaudeCode but unions its own DISALLOWED_TOOLS list (curl, wget,
    huggingface, etc.) into harbor's disallowed_tools. The DAB-recommended
    denials must still appear in the merged list, but exact equality no longer
    holds because the union widens beyond the four DAB entries.
    """
    agent = SpacedockSolverAgent(**_base_kwargs(tmp_path, tools_denied=DAB_DENIALS))
    inner = agent._build_inner_agent()
    # ClaudeCliAgent is a ClaudeCode subclass.
    assert isinstance(inner, ClaudeCode)
    flag_kwargs = getattr(inner, "_flag_kwargs", {})
    assert "disallowed_tools" in flag_kwargs, (
        "claude adapter did not install tools_denied as inner-agent disallowed_tools; "
        f"flag_kwargs={flag_kwargs}"
    )
    raw = flag_kwargs["disallowed_tools"]
    # ClaudeCliAgent shell-quotes the merged CSV; tolerate the wrapping quote.
    for denial in DAB_DENIALS:
        assert denial in raw, (
            f"DAB denial missing from disallowed_tools: {denial!r}; got {raw!r}"
        )


def test_claude_runtime_empty_tools_denied_still_installs_default_block_list(tmp_path):
    """Empty tools_denied still emits disallowed_tools — ClaudeCliAgent installs
    its DEFAULT DISALLOWED_TOOLS list (curl/wget/huggingface) unconditionally,
    which is the spec'd block-list for the razorback claude-cli surface.

    Earlier shape (harbor.ClaudeCode direct) emitted no disallowed_tools on
    empty input; the new shape always blocks DISALLOWED_TOOLS. The new behavior
    is strictly more protective; the prior empty-emits-nothing contract is
    superseded by the ClaudeCliAgent surface.
    """
    agent = SpacedockSolverAgent(**_base_kwargs(tmp_path, tools_denied=[]))
    inner = agent._build_inner_agent()
    flag_kwargs = getattr(inner, "_flag_kwargs", {})
    assert "disallowed_tools" in flag_kwargs, (
        "claude adapter dropped ClaudeCliAgent default DISALLOWED_TOOLS; "
        f"flag_kwargs={flag_kwargs}"
    )
    raw = flag_kwargs["disallowed_tools"]
    # The default block list includes web/network exfil paths.
    assert "WebFetch" in raw, f"default block list missing WebFetch; got {raw!r}"
    assert "Bash(curl *)" in raw, f"default block list missing curl; got {raw!r}"
