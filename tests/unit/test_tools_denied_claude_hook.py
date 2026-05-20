# ABOUTME: PKG-9 v2 AC-2: claude runtime adapter installs tools_denied as inner-agent denials.
# ABOUTME: Spec §6.2: tools_denied is a denylist installed as PreToolUse hooks in the inner runtime.

from pathlib import Path

from razorback.agents.spacedock_solver_v2 import SpacedockSolverAgent


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
    as the inner ClaudeCode agent's disallowed_tools (harbor's PreToolUse surface)
    verbatim and in order. Cite spec §6.2.
    """
    agent = SpacedockSolverAgent(**_base_kwargs(tmp_path, tools_denied=DAB_DENIALS))
    inner = agent._build_inner_agent()
    assert inner.__class__.__name__ == "ClaudeCode"
    flag_kwargs = getattr(inner, "_flag_kwargs", {})
    assert "disallowed_tools" in flag_kwargs, (
        "claude adapter did not install tools_denied as inner-agent disallowed_tools; "
        f"flag_kwargs={flag_kwargs}"
    )
    entries = flag_kwargs["disallowed_tools"].split(",")
    assert entries == DAB_DENIALS, (
        f"tools_denied entries lost ordering or contents: got {entries!r}, "
        f"expected {DAB_DENIALS!r}"
    )


def test_claude_runtime_empty_tools_denied_emits_no_disallowed_tools(tmp_path):
    """Plan risk: an empty tools_denied list must not emit an empty disallowed_tools
    flag (harbor versions reject empty permission blocks).
    """
    agent = SpacedockSolverAgent(**_base_kwargs(tmp_path, tools_denied=[]))
    inner = agent._build_inner_agent()
    flag_kwargs = getattr(inner, "_flag_kwargs", {})
    assert "disallowed_tools" not in flag_kwargs, (
        "claude adapter emitted disallowed_tools for empty tools_denied; "
        f"flag_kwargs={flag_kwargs}"
    )
