# ABOUTME: AC-4 — rk validate emits warning when adapter declares compose_services=False (§6.5).
# ABOUTME: Verbatim §6.5 example: "ade-bench with compose_services: False warns because postgres state leaks".

import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app

runner = CliRunner()


def _write_ade_bench_spec(tmp_path: Path) -> Path:
    tasks_root = tmp_path / "ade-bench-tasks"
    task_dir = tasks_root / "fixture"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        'schema_version = "1.2"\n[task]\nname = "x/fixture"\n'
    )
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        f"""
version: 1
experiment: ade-bench-validate-warn
agent:
  kind: nop
benchmark:
  kind: ade-bench
  tasks_root: {tasks_root}
  tasks: [fixture]
"""
    )
    return spec


def test_validate_warns_when_compose_services_false_on_ade_bench(tmp_path):
    spec = _write_ade_bench_spec(tmp_path)
    result = runner.invoke(app, ["validate", str(spec)])
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    codes = [w["code"] for w in payload.get("warnings", [])]
    assert "ADE_BENCH_COMPOSE_NOT_RESET" in codes
    msg = next(
        w["message"]
        for w in payload["warnings"]
        if w["code"] == "ADE_BENCH_COMPOSE_NOT_RESET"
    )
    # AC-4: "The warning text is asserted in a unit test."
    assert "compose_services: False" in msg
    assert "§6.5" in msg


def test_validate_does_not_warn_on_dab(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        f"""
version: 1
experiment: dab-validate-no-warn
agent:
  kind: nop
benchmark:
  kind: dab
  data_root: {data_root}
  datasets: [bookreview]
"""
    )
    result = runner.invoke(app, ["validate", str(spec)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    codes = [w["code"] for w in payload.get("warnings", [])]
    assert "ADE_BENCH_COMPOSE_NOT_RESET" not in codes


def test_validate_returns_exit_10_on_schema_failure(tmp_path):
    spec = tmp_path / "bad.yaml"
    spec.write_text(
        "version: 1\nexperiment: x\nagent: {kind: nop}\nbenchmark: {kind: nonsense}\n"
    )
    result = runner.invoke(app, ["validate", str(spec)])
    assert result.exit_code == 10  # ExitCode.SPEC_ERROR
