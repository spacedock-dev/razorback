# ABOUTME: T3/T5 — _compose_run_instruction prepends a first-officer ROLE prefix
# ABOUTME: that names the workspace dir and tells claude to dispatch via subagents.

from razorback.agents.spacedock_solver import SpacedockSolverAgent


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


def test_compose_run_instruction_starts_with_role_prefix(tmp_path):
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    out = agent._compose_run_instruction("solve this task")
    assert out.startswith("ROLE: You are the first-officer")
    # README content still present after the ROLE block
    assert "## Stages" in out
    assert "solve this task" in out


def test_compose_run_instruction_mentions_subagent_dispatch(tmp_path):
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    out = agent._compose_run_instruction("solve this task")
    # The ROLE block tells the model to use the Task tool with spacedock:ensign.
    assert "subagent_type" in out
    assert "spacedock:ensign" in out


def test_codex_compose_run_instruction_uses_codex_fo_dispatch_surface(tmp_path):
    agent = SpacedockSolverAgent(
        **_kw(
            tmp_path,
            runtime="codex",
            model="gpt-5.5",
            harbor_agent_kwargs={"reasoning_effort": "xhigh"},
            extra_env={"OPENAI_API_KEY": "x"},
        )
    )
    out = agent._compose_run_instruction("solve this task")
    assert out.startswith("ROLE: You are the first-officer")
    assert "current working directory IS the workspace (/app)" in out
    assert "Use the inline \"# Solver workflow instructions\" section" in out
    assert "do not search for Spacedock entity files" in out
    assert "spawn_agent(..., fork_context=false)" in out
    assert "wait_agent(...)" in out
    assert "/tmp/razorback-agents/skills/spacedock/skills/first-officer/SKILL.md" in out
    assert "role_asset_name: ensign" in out
    assert "## Stages" in out
