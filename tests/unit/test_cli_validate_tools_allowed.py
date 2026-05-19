# ABOUTME: AC-5 — rk validate warns when an ade-bench spec carries tools_allowed (§9.2).
# ABOUTME: Verbatim AC-5: "naming §9.2 in the warning text."

import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app

runner = CliRunner()


def _write_ade_bench_tasks_root(tmp_path: Path) -> Path:
    tasks_root = tmp_path / "ade-bench-tasks"
    task_dir = tasks_root / "fixture"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        'schema_version = "1.2"\n[task]\nname = "x/fixture"\n'
    )
    return tasks_root


def test_validate_warns_when_ade_bench_spec_has_tools_allowed(tmp_path):
    tasks_root = _write_ade_bench_tasks_root(tmp_path)
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        f"""
version: 1
experiment: ade-bench-tools-allowed-warn
agent:
  kind: claude-cli
  tools_allowed: [bash, edit]
benchmark:
  kind: ade-bench
  tasks_root: {tasks_root}
  tasks: [fixture]
"""
    )
    result = runner.invoke(app, ["validate", str(spec)])
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    codes = [w["code"] for w in payload["warnings"]]
    assert "ADE_BENCH_TOOLS_ALLOWED_NOT_ENFORCED" in codes
    msg = next(
        w["message"]
        for w in payload["warnings"]
        if w["code"] == "ADE_BENCH_TOOLS_ALLOWED_NOT_ENFORCED"
    )
    # AC-5 verbatim: "naming §9.2 in the warning text"
    assert "§9.2" in msg
    assert "bash" in msg  # tools_allowed list rendered into the message


def test_validate_does_not_warn_when_tools_allowed_is_empty(tmp_path):
    tasks_root = _write_ade_bench_tasks_root(tmp_path)
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        f"""
version: 1
experiment: ade-bench-no-tools-allowed
agent:
  kind: claude-cli
benchmark:
  kind: ade-bench
  tasks_root: {tasks_root}
  tasks: [fixture]
"""
    )
    result = runner.invoke(app, ["validate", str(spec)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    codes = [w["code"] for w in payload["warnings"]]
    assert "ADE_BENCH_TOOLS_ALLOWED_NOT_ENFORCED" not in codes


def test_validate_does_not_warn_when_tools_allowed_on_dab(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        f"""
version: 1
experiment: dab-tools-allowed
agent:
  kind: claude-cli
  tools_allowed: [bash]
benchmark:
  kind: dab
  data_root: {data_root}
  datasets: [bookreview]
"""
    )
    result = runner.invoke(app, ["validate", str(spec)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    codes = [w["code"] for w in payload["warnings"]]
    # DAB doesn't trigger the ade-bench tools_allowed warning
    assert "ADE_BENCH_TOOLS_ALLOWED_NOT_ENFORCED" not in codes
