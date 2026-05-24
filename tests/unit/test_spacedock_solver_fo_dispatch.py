# ABOUTME: T3/T6 — SpacedockSolverAgent._build_inner_agent (runtime=claude) wires
# ABOUTME: sub_agent="spacedock:first-officer" + plugin_dirs from env-var resolution.

import pytest

from razorback.agents.spacedock_solver import SpacedockSolverAgent


def _plugin_dir(tmp_path):
    plugin = tmp_path / "spacedock-plugin"
    for rel in (
        ".codex-plugin/plugin.json",
        "skills/first-officer/SKILL.md",
        "skills/ensign/SKILL.md",
        "agents/first-officer.md",
        "agents/ensign.md",
    ):
        path = plugin / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder\n")
    return plugin


def _kw(tmp_path, **overrides):
    workflow = tmp_path / "solver"
    workflow.mkdir(exist_ok=True)
    (workflow / "README.md").write_text("## Stages\n- model\n")
    logs_dir = tmp_path / "run" / "trials" / "task-0001__abc1234" / "logs" / "agent"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "run" / "spec.frozen.yaml").write_text("placeholder")
    base = dict(
        logs_dir=logs_dir,
        runtime="claude",
        model="claude-opus-4-7",
        sampling={"temperature": 0.0, "top_p": None, "seed": None},
        solver_workflow=workflow,
        solver_workflow_content_hash="sha256:" + "a" * 64,
        prompt_content_hashes={"readme": "sha256:" + "b" * 64},
        spacedock_skill_version="1.0.0",
        harbor_agent_kwargs={"max_turns": 200},
        extra_env={"ANTHROPIC_API_KEY": "x"},
    )
    base.update(overrides)
    return base


def test_claude_runtime_builds_inner_with_fo_subagent_and_plugin_dir(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    plugin = _plugin_dir(tmp_path)
    monkeypatch.setenv("RAZORBACK_SPACEDOCK_PLUGIN_DIR", str(plugin))
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    inner = agent._build_inner_agent()
    flags = inner.build_cli_flags()
    assert "--agent spacedock:first-officer" in flags
    assert f"--plugin-dir {plugin}" in flags


def test_codex_runtime_builds_inner_with_multi_agent_and_plugin_dir(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    plugin = _plugin_dir(tmp_path)
    monkeypatch.setenv("RAZORBACK_SPACEDOCK_PLUGIN_DIR", str(plugin))
    agent = SpacedockSolverAgent(
        **_kw(
            tmp_path,
            runtime="codex",
            model="gpt-5.5",
            harbor_agent_kwargs={"reasoning_effort": "xhigh"},
            extra_env={"OPENAI_API_KEY": "x"},
        )
    )
    inner = agent._build_inner_agent()
    flags = inner.build_cli_flags()
    assert "--enable multi_agent" in flags
    assert inner._spacedock_plugin_dirs == [plugin]


def test_claude_runtime_refuses_when_plugin_dir_env_unset(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("RAZORBACK_SPACEDOCK_PLUGIN_DIR", raising=False)
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    from razorback.agents.spacedock_solver import SpacedockSolverAgentError

    with pytest.raises(SpacedockSolverAgentError):
        agent._build_inner_agent()
