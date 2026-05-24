# ABOUTME: Translation coverage for direct agent.kind: claude-cli kwargs threading.
# ABOUTME: Locks claude-cli branch to thread reasoning_effort into AgentConfig.kwargs.

from pathlib import Path

from razorback.spec.parse import parse_spec_text
from razorback.translate import spec_to_job_config


CLAUDE_CLI_SPEC_YAML = """\
version: 1
experiment: claude-cli-translate-test
agent:
  kind: claude-cli
  model: claude-opus-4-5
  sampling:
    temperature: 0.0
  tools_allowed: [Bash, Read, Write]
  reasoning_effort: xhigh
benchmark:
  kind: local
  task_paths: []
trials: 1
"""


def test_claude_cli_threads_reasoning_effort_into_kwargs(tmp_path: Path):
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test-fixture\n")
    spec = parse_spec_text(CLAUDE_CLI_SPEC_YAML)

    jc, _ = spec_to_job_config(
        spec,
        job_name="job-test",
        jobs_dir=tmp_path / "_runs" / "claude-cli-translate-test",
        project_root=tmp_path,
    )

    assert len(jc.agents) == 1
    agent_cfg = jc.agents[0]
    assert agent_cfg.import_path == "razorback.agents._runtime.claude:RazorbackClaudeCode"
    assert agent_cfg.model_name == "claude-opus-4-5"
    assert agent_cfg.kwargs == {
        "allowed_tools": "Bash,Read,Write",
        "reasoning_effort": "xhigh",
    }
