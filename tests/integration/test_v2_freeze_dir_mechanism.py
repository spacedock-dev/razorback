# ABOUTME: AC-5, sealed_hash-keyed external freeze write contract (b5 load-bearing path).
# ABOUTME: Mechanism check: smallest end-to-end exercise of the riskiest b5 contract.

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from razorback.agents.auth import AuthDiscoveryError
from razorback.agents.spacedock_solver_v2 import SpacedockSolverAgent
from razorback.spec.schema import Spec
from razorback.translate import spec_to_job_config


def _make_harbor_run_dir(tmp_path: Path, trial_name: str) -> Path:
    """Mimic harbor 0.6.6 layout: <run-dir>/trials/<trial_name>/logs/agent/."""
    run_dir = tmp_path / "run"
    logs_dir = run_dir / "trials" / trial_name / "logs" / "agent"
    logs_dir.mkdir(parents=True, exist_ok=True)
    spec_path = run_dir / "spec.frozen.yaml"
    if not spec_path.exists():
        spec_path.write_text("placeholder")
    return logs_dir


def _common_kwargs(workflow: Path) -> dict:
    return dict(
        runtime="claude",
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": None},
        solver_workflow=workflow,
        solver_workflow_content_hash="sha256:" + "a" * 64,
        prompt_content_hashes={"readme": "sha256:" + "b" * 64},
        spacedock_skill_version="1.0.0",
        harbor_agent_kwargs={"max_turns": 200},
        extra_env={"ANTHROPIC_API_KEY": "x"},
    )


def test_codex_runtime_dispatch_constructs_inner_agent(tmp_path):
    """PKG-26: runtime=codex dispatches through the v2 adapter to Harbor Codex."""
    logs_dir = _make_harbor_run_dir(tmp_path, "codex-smoke__abc1234")
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    kw = _common_kwargs(workflow)
    kw.update(
        runtime="codex",
        model="gpt-5.1-codex",
        harbor_agent_kwargs={
            "max_turns": 200,
            "tools_allowed": [],
            "tools_denied": [],
            "reasoning_effort": "high",
        },
        extra_env={"OPENAI_API_KEY": "sk-fake"},
    )
    agent = SpacedockSolverAgent(logs_dir=logs_dir, **kw)

    inner = agent._build_inner_agent()

    assert inner.__class__.__name__ == "Codex"
    assert inner.model_name == "gpt-5.1-codex"
    assert getattr(inner, "_flag_kwargs", {})["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_sealed_hash_txt_lands_at_keyed_external_path(tmp_path):
    """AC-5 mechanism: sealed_hash.txt at <run-dir>/_razorback/freeze/<sealed_hash>/."""
    logs_dir = _make_harbor_run_dir(tmp_path, "bookreview-0001__abc1234")
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    agent = SpacedockSolverAgent(logs_dir=logs_dir, **_common_kwargs(workflow))

    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()

    await agent.setup(fake_env)

    expected = tmp_path / "run" / "_razorback" / "freeze" / agent.sealed_hash
    assert (expected / "sealed_hash.txt").exists()
    assert (expected / "sealed_hash.txt").read_text().strip() == agent.sealed_hash
    # AC-5 mandate: NOT inside trials/.
    rel = str(expected.relative_to(tmp_path / "run"))
    assert "trials" not in rel


@pytest.mark.asyncio
async def test_harbor_jobs_resume_round_trip_with_new_trial_name(tmp_path):
    """AC-6 mechanism: re-executed trial with a NEW trial_name reads the SAME freeze tree."""
    logs_a = _make_harbor_run_dir(tmp_path, "bookreview-0001__abc1234")
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")
    kw = _common_kwargs(workflow)
    agent_a = SpacedockSolverAgent(logs_dir=logs_a, **kw)
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent_a._inner = MagicMock()
    agent_a._inner.setup = AsyncMock()
    await agent_a.setup(fake_env)

    freeze_dir = agent_a.resolve_freeze_dir()
    assert (freeze_dir / "sealed_hash.txt").exists()

    # Simulate harbor jobs resume: rmtree trials/<old_name>/, new trial_name.
    import shutil
    shutil.rmtree(tmp_path / "run" / "trials" / "bookreview-0001__abc1234")
    logs_b = _make_harbor_run_dir(tmp_path, "bookreview-0001__wMGYfz7")

    agent_b = SpacedockSolverAgent(logs_dir=logs_b, **kw)
    assert agent_b.sealed_hash == agent_a.sealed_hash
    assert agent_b.resolve_freeze_dir() == freeze_dir  # SAME tree, different trial.

    await agent_b.setup(fake_env)
    assert freeze_dir.exists()
    assert not (tmp_path / "run" / "trials" / "bookreview-0001__abc1234").exists()


def test_translator_emits_spacedock_solver_v2_import_path(tmp_path):
    """AC-7: spec.agent.kind: spacedock_solver_v2 -> import_path of v2 class."""
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    spec_yaml = f"""
version: 1
experiment: phase3-translate-test
agent:
  kind: spacedock_solver_v2
  runtime: claude
  model: claude-opus-4-5
  solver_workflow: {workflow}
  solver_workflow_content_hash: "sha256:{'a' * 64}"
  spacedock_skill_version: "1.0.0"
  sealed_hash: "0123456789abcdef0123456789abcdef"
  max_turns: 200
benchmark:
  kind: local
  task_paths: []
trials: 1
"""
    spec = Spec.model_validate(yaml.safe_load(spec_yaml))
    # Create a fake .env in the project_root so resolve_claude_auth succeeds.
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".env").write_text("ANTHROPIC_API_KEY=sk-fake\n")
    home = tmp_path / "home"
    home.mkdir()
    cfg, _ = spec_to_job_config(
        spec=spec,
        job_name="phase3-test",
        jobs_dir=tmp_path / "_runs",
        project_root=project_root,
        home=home,
    )
    agent_cfg = cfg.agents[0]
    assert agent_cfg.import_path == (
        "razorback.agents.spacedock_solver_v2:SpacedockSolverAgent"
    )
    assert agent_cfg.kwargs["runtime"] == "claude"
    assert agent_cfg.kwargs["solver_workflow_content_hash"] == "sha256:" + "a" * 64
    # Auth flows via env (FU-1 AC-1), never via kwargs.
    assert "ANTHROPIC_API_KEY" not in (agent_cfg.kwargs or {})
    assert "ANTHROPIC_API_KEY" in (agent_cfg.env or {})


def test_translator_uses_codex_auth_for_codex_runtime(tmp_path):
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    spec_yaml = f"""
version: 1
experiment: phase3-translate-codex-test
agent:
  kind: spacedock_solver_v2
  runtime: codex
  model: gpt-5.1-codex
  solver_workflow: {workflow}
  solver_workflow_content_hash: "sha256:{'a' * 64}"
  spacedock_skill_version: "1.0.0"
  sealed_hash: "0123456789abcdef0123456789abcdef"
  max_turns: 200
benchmark:
  kind: local
  task_paths: []
trials: 1
"""
    spec = Spec.model_validate(yaml.safe_load(spec_yaml))
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".env").write_text("OPENAI_API_KEY=sk-openai\n")
    cfg, _ = spec_to_job_config(
        spec=spec,
        job_name="phase3-codex-test",
        jobs_dir=tmp_path / "_runs",
        project_root=project_root,
    )

    agent_cfg = cfg.agents[0]
    assert agent_cfg.kwargs["runtime"] == "codex"
    assert agent_cfg.env == {"OPENAI_API_KEY": "sk-openai"}
    assert "ANTHROPIC_API_KEY" not in agent_cfg.env


def test_translator_uses_codex_auth_json_for_codex_runtime(tmp_path):
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    spec_yaml = f"""
version: 1
experiment: phase3-translate-codex-auth-json-test
agent:
  kind: spacedock_solver_v2
  runtime: codex
  model: gpt-5.1-codex
  solver_workflow: {workflow}
  solver_workflow_content_hash: "sha256:{'a' * 64}"
  spacedock_skill_version: "1.0.0"
  sealed_hash: "0123456789abcdef0123456789abcdef"
  max_turns: 200
benchmark:
  kind: local
  task_paths: []
trials: 1
"""
    spec = Spec.model_validate(yaml.safe_load(spec_yaml))
    project_root = tmp_path / "project"
    project_root.mkdir()
    home = tmp_path / "home"
    auth_path = home / ".codex" / "auth.json"
    auth_path.parent.mkdir(parents=True)
    auth_path.write_text('{"tokens": "fake"}\n')

    cfg, _ = spec_to_job_config(
        spec=spec,
        job_name="phase3-codex-auth-json-test",
        jobs_dir=tmp_path / "_runs",
        project_root=project_root,
        home=home,
    )

    agent_cfg = cfg.agents[0]
    assert agent_cfg.kwargs["runtime"] == "codex"
    assert agent_cfg.env == {"CODEX_AUTH_JSON_PATH": str(auth_path)}
    assert "OPENAI_API_KEY" not in agent_cfg.env


def test_translator_codex_runtime_fails_without_credentials(tmp_path):
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    spec_yaml = f"""
version: 1
experiment: phase3-translate-codex-missing-auth-test
agent:
  kind: spacedock_solver_v2
  runtime: codex
  model: gpt-5.1-codex
  solver_workflow: {workflow}
  solver_workflow_content_hash: "sha256:{'a' * 64}"
  spacedock_skill_version: "1.0.0"
  sealed_hash: "0123456789abcdef0123456789abcdef"
  max_turns: 200
benchmark:
  kind: local
  task_paths: []
trials: 1
"""
    spec = Spec.model_validate(yaml.safe_load(spec_yaml))
    project_root = tmp_path / "project"
    project_root.mkdir()

    with pytest.raises(AuthDiscoveryError) as exc_info:
        spec_to_job_config(
            spec=spec,
            job_name="phase3-codex-missing-auth-test",
            jobs_dir=tmp_path / "_runs",
            project_root=project_root,
            home=tmp_path / "home",
        )

    message = str(exc_info.value)
    assert "OPENAI_API_KEY" in message
    assert "CODEX_AUTH_JSON_PATH" in message
    assert ".codex/auth.json" in message
