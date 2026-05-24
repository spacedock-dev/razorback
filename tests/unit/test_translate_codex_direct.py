# ABOUTME: Translation coverage for direct agent.kind: codex minimal runs.
# ABOUTME: Locks direct Codex to RazorbackCodex without spacedock solver fields.

from pathlib import Path

from razorback.agents.proxy import PROXY_BLOCK_ENV
from razorback.spec.parse import parse_spec_text
from razorback.translate import spec_to_job_config


DIRECT_CODEX_SPEC_YAML = """\
version: 1
experiment: direct-codex-translate-test
agent:
  kind: codex
  model: gpt-5.5
  sampling:
    temperature: 0.0
  reasoning_effort: xhigh
  reasoning_summary: auto
  override_timeout_sec: 1200
  max_timeout_sec: 1200
benchmark:
  kind: local
  task_paths: []
trials: 1
"""


def test_direct_codex_emits_razorback_codex_without_solver_fields(tmp_path: Path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-test-fixture\n")
    spec = parse_spec_text(DIRECT_CODEX_SPEC_YAML)

    jc, _ = spec_to_job_config(
        spec,
        job_name="job-test",
        jobs_dir=tmp_path / "_runs" / "direct-codex-translate-test",
        project_root=tmp_path,
    )

    assert len(jc.agents) == 1
    agent_cfg = jc.agents[0]
    assert agent_cfg.import_path == "razorback.agents._runtime.codex:RazorbackCodex"
    assert agent_cfg.model_name == "gpt-5.5"
    assert agent_cfg.override_timeout_sec == 1200
    assert agent_cfg.max_timeout_sec == 1200
    assert agent_cfg.kwargs == {
        "reasoning_effort": "xhigh",
        "reasoning_summary": "auto",
    }
    assert agent_cfg.env == {"OPENAI_API_KEY": "sk-test-fixture"}
    assert "solver_workflow" not in agent_cfg.kwargs
    assert "sealed_hash" not in agent_cfg.kwargs
    assert "OPENAI_API_KEY" not in agent_cfg.kwargs


def test_direct_codex_uses_proxy_block_environment_without_freeze_mount(
    tmp_path: Path,
):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-test-fixture\n")
    spec = parse_spec_text(DIRECT_CODEX_SPEC_YAML)

    jc, _ = spec_to_job_config(
        spec,
        job_name="job-test",
        jobs_dir=tmp_path / "_runs" / "direct-codex-translate-test",
        project_root=tmp_path,
    )

    assert (
        jc.environment.import_path
        == "razorback.environments.docker:ProxySeparatedDockerEnvironment"
    )
    assert jc.environment.env == PROXY_BLOCK_ENV
    assert jc.environment.mounts_json is None
