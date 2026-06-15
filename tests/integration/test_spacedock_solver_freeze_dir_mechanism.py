# ABOUTME: AC-5, sealed_hash-keyed external freeze write contract (b5 load-bearing path).
# ABOUTME: Mechanism check: smallest end-to-end exercise of the riskiest b5 contract.

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from razorback.agents.auth import AuthDiscoveryError
from razorback.agents.proxy import PROXY_BLOCK_ENV
from razorback.agents.spacedock_solver import SpacedockSolverAgent
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
    """PKG-26: runtime=codex dispatches through the canonical adapter to Harbor Codex."""
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

    assert inner.__class__.__name__ == "RazorbackCodex"
    assert inner.model_name == "gpt-5.1-codex"
    assert getattr(inner, "_flag_kwargs", {})["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_sealed_hash_txt_lands_at_keyed_external_path(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """AC-1: sealed_hash.txt at <cas-root>/<sealed_hash>/ (env-override CAS)."""
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
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

    expected = tmp_path / "freeze-cas" / agent.sealed_hash / agent._cell_token()
    assert expected == agent.resolve_freeze_dir()
    assert (expected / "sealed_hash.txt").exists()
    assert (expected / "sealed_hash.txt").read_text().strip() == agent.sealed_hash
    # CAS root is outside the run-dir entirely.
    assert "trials" not in str(expected)
    assert (tmp_path / "run") not in expected.parents


@pytest.mark.asyncio
async def test_new_trial_name_gets_isolated_freeze_tree(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """A cell with a NEW trial_name gets its OWN freeze tree (per-cell isolation).

    This is what makes concurrent attempts safe: trials of one task share a
    sealed_hash but never share a git repo. The trade-off — intentional — is
    that a job restarted with a regenerated trial-name suffix starts a fresh
    freeze instead of reusing the prior one. Within-cell resume (same logs_dir)
    is covered by test_freeze_cas_resume_no_agent_invocation.
    """
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    monkeypatch.setenv("RAZORBACK_SPACEDOCK_PLUGIN_DIR", str(tmp_path))
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

    logs_b = _make_harbor_run_dir(tmp_path, "bookreview-0001__wMGYfz7")
    agent_b = SpacedockSolverAgent(logs_dir=logs_b, **kw)
    assert agent_b.sealed_hash == agent_a.sealed_hash  # same sealed inputs
    # ...but an isolated freeze tree under the shared sealed_hash dir.
    assert agent_b.resolve_freeze_dir() != freeze_dir
    assert agent_b.resolve_freeze_dir().parent == freeze_dir.parent

    agent_b._inner = MagicMock()
    agent_b._inner.setup = AsyncMock()
    await agent_b.setup(fake_env)
    assert agent_b.resolve_freeze_dir().exists()
    assert freeze_dir.exists()  # agent_a's tree is untouched.


def test_translator_emits_spacedock_solver_import_path(tmp_path):
    """AC-7: spec.agent.kind: spacedock_solver -> import_path of canonical class."""
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    spec_yaml = f"""
version: 1
experiment: phase3-translate-test
agent:
  kind: spacedock_solver
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
        "razorback.agents.spacedock_solver:SpacedockSolverAgent"
    )
    assert agent_cfg.kwargs["runtime"] == "claude"
    assert agent_cfg.kwargs["solver_workflow_content_hash"] == "sha256:" + "a" * 64
    # Auth flows via env (FU-1 AC-1), never via kwargs.
    assert "ANTHROPIC_API_KEY" not in (agent_cfg.kwargs or {})
    assert "ANTHROPIC_API_KEY" in (agent_cfg.env or {})


def test_translator_mounts_canonical_freeze_root_into_container(tmp_path):
    """PKG-29: canonical external freeze root is mounted for in-container git commands."""
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    spec_yaml = f"""
version: 1
experiment: phase3-translate-test
agent:
  kind: spacedock_solver
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
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".env").write_text("ANTHROPIC_API_KEY=sk-fake\n")
    jobs_dir = tmp_path / "_runs"

    cfg, _ = spec_to_job_config(
        spec=spec,
        job_name="phase3-test",
        jobs_dir=jobs_dir,
        project_root=project_root,
    )

    host_freeze_root = jobs_dir / "phase3-test" / "_razorback" / "freeze"
    assert cfg.environment.mounts_json == [
        {
            "type": "bind",
            "source": str(host_freeze_root.resolve()),
            "target": "/razorback-freeze",
        }
    ]
    assert cfg.environment.env["HTTP_PROXY"] == PROXY_BLOCK_ENV["HTTP_PROXY"]
    assert cfg.environment.env["HF_DATASETS_OFFLINE"] == "1"
    assert host_freeze_root.is_dir()


def test_translator_uses_codex_auth_for_codex_runtime(tmp_path):
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    spec_yaml = f"""
version: 1
experiment: phase3-translate-codex-test
agent:
  kind: spacedock_solver
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


def test_freeze_dir_includes_explicit_benchmark_task_identity(tmp_path):
    logs_dir = _make_harbor_run_dir(tmp_path, "ade-bench-task-a__abc1234")
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")
    kw = _common_kwargs(workflow)

    agent_a = SpacedockSolverAgent(
        logs_dir=logs_dir,
        **kw,
        benchmark_kind="ade-bench",
        benchmark_task_id="task-a",
        batch_mode="per-task",
    )
    agent_b = SpacedockSolverAgent(
        logs_dir=logs_dir,
        **kw,
        benchmark_kind="ade-bench",
        benchmark_task_id="task-b",
        batch_mode="per-task",
    )

    assert agent_a.sealed_hash != agent_b.sealed_hash
    assert agent_a.resolve_freeze_dir() != agent_b.resolve_freeze_dir()


def test_freeze_dir_discovers_benchmark_task_identity_from_view_manifest(tmp_path):
    run_dir = tmp_path / "run"
    view = run_dir / "_razorback" / "task_views" / "ade-bench-task-a"
    view.mkdir(parents=True)
    (view / "view_manifest.json").write_text(
        '{"benchmark_kind":"ade-bench","benchmark_task_id":"task-a"}'
    )
    logs_a = _make_harbor_run_dir(tmp_path, "ade-bench-task-a__abc1234")
    logs_b = _make_harbor_run_dir(tmp_path, "bookreview-0001__abc1234")
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    with_identity = SpacedockSolverAgent(logs_dir=logs_a, **_common_kwargs(workflow))
    without_identity = SpacedockSolverAgent(logs_dir=logs_b, **_common_kwargs(workflow))

    assert with_identity.sealed_hash != without_identity.sealed_hash
    assert with_identity.resolve_freeze_dir() != without_identity.resolve_freeze_dir()


def test_translator_includes_codex_reasoning_kwargs_for_canonical_agent(tmp_path):
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    spec_yaml = f"""
version: 1
experiment: pkg35-translate-codex-reasoning-test
agent:
  kind: spacedock_solver
  runtime: codex
  model: gpt-5.5
  reasoning_effort: xhigh
  reasoning_summary: auto
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
        job_name="pkg35-codex-reasoning-test",
        jobs_dir=tmp_path / "_runs",
        project_root=project_root,
    )

    harbor_agent_kwargs = cfg.agents[0].kwargs["harbor_agent_kwargs"]
    assert cfg.agents[0].kwargs["runtime"] == "codex"
    assert cfg.agents[0].model_name == "gpt-5.5"
    assert harbor_agent_kwargs["reasoning_effort"] == "xhigh"
    assert harbor_agent_kwargs["reasoning_summary"] == "auto"


def test_translator_uses_codex_auth_json_for_codex_runtime(tmp_path):
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    spec_yaml = f"""
version: 1
experiment: phase3-translate-codex-auth-json-test
agent:
  kind: spacedock_solver
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
  kind: spacedock_solver
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
