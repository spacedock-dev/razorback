# ABOUTME: `rk run --explain` dry-runs solver/runtime/prompt preparation.
# ABOUTME: Guards against spending Harbor/model work just to inspect a run plan.

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from razorback.cli import app


def test_run_explain_spacedock_codex_prints_prompt_without_harbor(
    tmp_path: Path,
) -> None:
    workflow = tmp_path / "workflow"
    workflow.mkdir()
    (workflow / "README.md").write_text("# Workflow\n\nDo the repair carefully.\n")

    task = tmp_path / "task"
    task.mkdir()
    (task / "instruction.md").write_text("Fix the dbt model.\n")

    spec = tmp_path / "spec.frozen.yaml"
    spec.write_text(
        "version: 1\n"
        "experiment: explain-spacedock\n"
        "agent:\n"
        "  kind: spacedock_solver\n"
        "  runtime: codex\n"
        "  model: gpt-5.4-mini\n"
        "  solver_workflow: " + str(workflow) + "\n"
        "  solver_workflow_content_hash: sha256:test\n"
        "  sealed_hash: abc123\n"
        "  spacedock_skill_version: 1.0.0\n"
        "  prompt_content_hashes: {}\n"
        "  reasoning_effort: xhigh\n"
        "benchmark:\n"
        "  kind: local\n"
        "  task_paths:\n"
        "    - " + str(task) + "\n"
        "trials: 1\n"
    )

    runs_dir = tmp_path / "_runs"
    with patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._invoke_harbor") as harbor, \
         patch(
             "razorback.translate.resolve_codex_auth",
             return_value=SimpleNamespace(env={"CODEX_AUTH_JSON_PATH": "/tmp/auth.json"}),
         ):
        result = CliRunner(mix_stderr=False).invoke(
            app,
            ["run", str(spec), "--runs-dir", str(runs_dir), "--explain"],
        )

    assert result.exit_code == 0, result.stderr or result.stdout
    harbor.assert_not_called()
    assert "Explain-only: Harbor will not be invoked" in result.stdout
    assert "spacedock-codex-first-officer" in result.stdout
    assert "Resolve the packaged entrypoint `spacedock:first-officer`" in result.stdout
    assert "# Solver workflow instructions" in result.stdout
    assert "Do the repair carefully." in result.stdout
    assert "# Task instruction" in result.stdout
    assert "Fix the dbt model." in result.stdout
    assert not list(runs_dir.rglob("_job_config.yaml"))


def test_run_explain_json_reports_direct_codex_agent(tmp_path: Path) -> None:
    task = tmp_path / "task"
    task.mkdir()
    (task / "instruction.md").write_text("Answer directly.\n")

    spec = tmp_path / "spec.frozen.yaml"
    spec.write_text(
        "version: 1\n"
        "experiment: explain-direct\n"
        "agent:\n"
        "  kind: codex\n"
        "  model: gpt-5.4-mini\n"
        "  reasoning_effort: low\n"
        "benchmark:\n"
        "  kind: local\n"
        "  task_paths:\n"
        "    - " + str(task) + "\n"
        "trials: 1\n"
    )

    with patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._invoke_harbor") as harbor, \
         patch(
             "razorback.translate.resolve_codex_auth",
             return_value=SimpleNamespace(env={"CODEX_AUTH_JSON_PATH": "/tmp/auth.json"}),
         ):
        result = CliRunner(mix_stderr=False).invoke(
            app,
            [
                "run",
                str(spec),
                "--runs-dir",
                str(tmp_path / "_runs"),
                "--explain",
                "--explain-format",
                "json",
            ],
        )

    assert result.exit_code == 0, result.stderr or result.stdout
    harbor.assert_not_called()
    assert '"schema_version": "rk-run-explain-v1"' in result.stdout
    assert '"spec_kind": "codex"' in result.stdout
    assert '"mode": "direct-task-instruction"' in result.stdout
    assert "Answer directly." in result.stdout
