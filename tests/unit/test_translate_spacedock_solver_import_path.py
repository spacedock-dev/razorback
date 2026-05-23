# ABOUTME: Phase 6: spec.agent.kind: spacedock_solver translates to v2 AgentConfig.import_path.
# ABOUTME: Verifies the import_path literal per harbor entry-point probe (AC-0.2).

from pathlib import Path

import pytest

from razorback.spec.parse import parse_spec_text
from razorback.translate import spec_to_job_config


SPACEDOCK_SPEC_YAML = """\
version: 1
experiment: phase6-translate-canonical-test
agent:
  kind: spacedock_solver
  runtime: codex
  model: gpt-5.1-codex
  solver_workflow: {solver_workflow}
  solver_workflow_content_hash: "sha256:{workflow_hash}"
  spacedock_skill_version: "1.0.0"
  sealed_hash: "{sealed_hash}"
  max_turns: 200
  tools_allowed: []
  tools_denied: []
benchmark:
  kind: local
  task_paths: []
trials: 1
"""


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test-fixture\n")
    fixture_dir = tmp_path / "tests" / "fixtures" / "translate"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "model.md").write_text("model stage prompt body\n")
    (fixture_dir / "analyze.md").write_text("analyze stage prompt body\n")
    (fixture_dir / "verify.md").write_text("verify stage prompt body\n")
    return tmp_path


def test_spacedock_solver_emits_import_path(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(project_root)
    (project_root / ".env").write_text("OPENAI_API_KEY=sk-test-fixture\n")
    workflow = project_root / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")
    spec = parse_spec_text(
        SPACEDOCK_SPEC_YAML.format(
            solver_workflow=workflow,
            workflow_hash="a" * 64,
            sealed_hash="0123456789abcdef0123456789abcdef",
        )
    )

    jc, _ = spec_to_job_config(
        spec,
        job_name="job-test",
        jobs_dir=project_root / "_runs" / "phase6-translate-canonical-test",
        project_root=project_root,
    )

    assert len(jc.agents) == 1
    agent_cfg = jc.agents[0]
    assert agent_cfg.import_path == "razorback.agents.spacedock_solver:SpacedockSolverAgent"
    assert agent_cfg.model_name == "gpt-5.1-codex"
    # AC-6 cross-cut: per harbor source probe (AC-0.4), auth lands on AgentConfig.env,
    # NOT kwargs. The FU-1 AC-1 invariant survives in v2.
    assert "OPENAI_API_KEY" in agent_cfg.env
    assert "OPENAI_API_KEY" not in agent_cfg.kwargs
    assert agent_cfg.kwargs["runtime"] == "codex"
    assert agent_cfg.kwargs["solver_workflow"] == str(workflow)
    assert agent_cfg.kwargs["solver_workflow_content_hash"] == "sha256:" + "a" * 64
    assert agent_cfg.kwargs["harbor_agent_kwargs"] == {
        "max_turns": 200,
        "tools_allowed": [],
        "tools_denied": [],
    }
    assert agent_cfg.kwargs["tools_denied"] == []


def test_spacedock_solver_uses_proxy_separated_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-test-fixture\n")
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")
    spec = parse_spec_text(
        SPACEDOCK_SPEC_YAML.format(
            solver_workflow=workflow,
            workflow_hash="a" * 64,
            sealed_hash="0123456789abcdef0123456789abcdef",
        )
    )

    jc, _ = spec_to_job_config(
        spec,
        job_name="job-test",
        jobs_dir=tmp_path / "_runs" / "pkg37-translate-v2-test",
        project_root=tmp_path,
    )

    assert (
        jc.environment.import_path
        == "razorback.environments.docker:ProxySeparatedDockerEnvironment"
    )
    assert jc.environment.delete is False
    assert jc.environment.env["HTTP_PROXY"] == "http://127.0.0.1:1"
    assert "api.openai.com" in jc.environment.env["NO_PROXY"]
    assert jc.environment.mounts_json == [
        {
            "type": "bind",
            "source": str(
                (
                    tmp_path
                    / "_runs"
                    / "pkg37-translate-v2-test"
                    / "job-test"
                    / "_razorback"
                    / "freeze"
                ).resolve()
            ),
            "target": "/razorback-freeze",
        }
    ]
