# ABOUTME: AC-7 — the spec → JobConfig translator stamps the proxy block from
# ABOUTME: run_experiment.py:1497-1525 into the materialized task.toml's [environment.env].

import tomllib
from pathlib import Path

import pytest

from razorback.translate import spec_to_job_config
from razorback.spec.parse import parse_spec_text


def _make_fixture_dataset(root: Path) -> Path:
    ds = root / "query_bookreview"
    (ds / "query_dataset").mkdir(parents=True)
    (ds / "db_config.yaml").write_text("db_clients: {}\n")
    (ds / "db_description.txt").write_text("desc")
    for qid in (1,):
        q = ds / f"query{qid}"
        q.mkdir()
        (q / "query.json").write_text(f'"Q{qid}?"')
        (q / "validate.py").write_text(f"def validate(s): return ('{qid}' in s, 'ok')\n")
    return root


CLAUDE_SPEC = """\
version: 1
experiment: m3-bookreview-claude
agent:
  kind: claude-cli
  model: claude-opus-4-5
  sampling:
    temperature: 0.0
  tools_allowed: [Bash, Read, Write, Edit, Glob, Grep]
benchmark:
  kind: dab
  data_root: {data_root}
  datasets:
    - bookreview
trials: 1
"""


def _read_task_env(task) -> dict[str, str]:
    """Pull the [environment.env] block out of the materialized task.toml on disk."""
    task_toml = task.path / "task.toml"
    data = tomllib.loads(task_toml.read_text())
    return data.get("environment", {}).get("env", {})


def test_translator_stamps_proxy_block_into_task_toml_environment_env(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test\n")
    spec = parse_spec_text(CLAUDE_SPEC.format(data_root=data_root))

    cfg, _trial_map = spec_to_job_config(
        spec,
        job_name="claude" + "0" * 11,
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
        project_root=tmp_path,
    )

    [task] = cfg.tasks
    env_block = _read_task_env(task)
    # AC-7: literal proxy lock-down values land in the task.toml's [environment.env].
    assert env_block["HTTP_PROXY"] == "http://127.0.0.1:1"
    assert env_block["HTTPS_PROXY"] == "http://127.0.0.1:1"
    assert "anthropic" in env_block["NO_PROXY"]
    assert "statsig" in env_block["NO_PROXY"]
    assert "pypi" in env_block["NO_PROXY"]
    assert env_block["HF_HUB_OFFLINE"] == "1"
    assert env_block["TRANSFORMERS_OFFLINE"] == "1"
    assert env_block["HF_DATASETS_OFFLINE"] == "1"


def test_translator_passes_resolved_auth_into_agent_env_not_kwargs(tmp_path):
    """FU-1 AC-1: auth rides via AgentConfig.env (harbor redacts on disk), NOT kwargs."""
    data_root = _make_fixture_dataset(tmp_path / "data")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test-2\n")
    spec = parse_spec_text(CLAUDE_SPEC.format(data_root=data_root))

    cfg, _ = spec_to_job_config(
        spec,
        job_name="claude" + "0" * 11,
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
        project_root=tmp_path,
    )
    agent_cfg = cfg.agents[0]
    assert (
        agent_cfg.import_path
        == "razorback.agents._runtime.claude:RazorbackClaudeCode"
    )
    # AC-1: kwargs must not carry any auth surface.
    assert "resolved_auth_env" not in agent_cfg.kwargs
    assert agent_cfg.kwargs["allowed_tools"] == "Bash,Read,Write,Edit,Glob,Grep"
    assert "sampling_temperature" not in agent_cfg.kwargs
    # AC-1: env carries the resolved value in-memory (harbor's templatize_sensitive_env
    # redacts on serialization, not on the Python object).
    assert agent_cfg.env == {"ANTHROPIC_API_KEY": "sk-test-2"}


def test_translator_never_emits_both_auth_names(tmp_path):
    """AC-2 at the translator layer: even when both sources resolve, only one rides."""
    data_root = _make_fixture_dataset(tmp_path / "data")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-1\n")
    home = tmp_path / "fake-home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "benchmark-token").write_text("oauth-2")
    spec = parse_spec_text(CLAUDE_SPEC.format(data_root=data_root))

    cfg, _ = spec_to_job_config(
        spec,
        job_name="claude" + "0" * 11,
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
        project_root=tmp_path,
        home=home,
    )
    auth_env = cfg.agents[0].env
    assert "ANTHROPIC_API_KEY" in auth_env
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in auth_env
    assert "resolved_auth_env" not in cfg.agents[0].kwargs


def test_translator_raises_when_no_credentials(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    (tmp_path / ".env").write_text("# empty\n")
    home = tmp_path / "fake-home-no-token"
    (home / ".claude").mkdir(parents=True)
    spec = parse_spec_text(CLAUDE_SPEC.format(data_root=data_root))

    with pytest.raises(Exception):
        spec_to_job_config(
            spec,
            job_name="claude" + "0" * 11,
            jobs_dir=tmp_path / "jobs",
            tasks_root=tmp_path / "tasks",
            project_root=tmp_path,
            home=home,
        )


def test_translator_keeps_nop_agent_path_working(tmp_path):
    """Regression — the M2 nop+DAB path must keep parsing through the M3-extended translator."""
    data_root = _make_fixture_dataset(tmp_path / "data")
    nop_spec = """\
version: 1
experiment: m2-nop-regression
agent:
  kind: nop
benchmark:
  kind: dab
  data_root: {data_root}
  datasets:
    - bookreview
trials: 1
"""
    spec = parse_spec_text(nop_spec.format(data_root=data_root))
    cfg, _ = spec_to_job_config(
        spec,
        job_name="nop" + "0" * 13,
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
        project_root=tmp_path,
    )
    # nop agents resolve to AgentName.NOP — no import_path, no kwargs.
    assert cfg.agents[0].import_path is None
    assert cfg.agents[0].kwargs == {}
