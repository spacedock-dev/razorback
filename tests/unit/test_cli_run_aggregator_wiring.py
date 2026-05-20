# ABOUTME: PKG-17 — cli/run.py invokes the aggregator after harbor exit.
# ABOUTME: Patches _invoke_harbor + the aggregator to assert call ordering.

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from razorback.cli import app


def _fake_spec(tmp_path: Path) -> Path:
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "version: 1\n"
        "experiment: pkg17-wiring\n"
        "agent:\n  kind: nop\n"
        "benchmark:\n"
        "  kind: local\n"
        "  task_paths:\n"
        "    - examples/tasks/hello-world\n"
        "trials: 1\n"
    )
    return spec


def test_cli_run_invokes_aggregator_on_harbor_success(tmp_path: Path):
    spec = _fake_spec(tmp_path)
    runs_dir = tmp_path / "_runs"

    captured: dict = {}

    def fake_invoke_harbor(job_config_yaml, env):
        run_dir = Path(job_config_yaml).parent
        (run_dir / "result.json").write_text(json.dumps({
            "n_total_trials": 0,
            "stats": {"n_completed_trials": 0, "n_errored_trials": 0, "evals": {}, "cost_usd": None},
        }))
        return 0

    def fake_aggregate(run_dir, *, spec_path, frozen_spec_hash, provenance_hash,
                      harbor_job_name, benchmark_kind):
        captured["run_dir"] = run_dir
        captured["frozen_spec_hash"] = frozen_spec_hash
        captured["benchmark_kind"] = benchmark_kind
        (run_dir / "manifest.json").write_text("{}")
        (run_dir / "summary.json").write_text("{}")
        (run_dir / "events.jsonl").write_text("")
        (run_dir / "per_trial_outcomes.json").write_text("{}")

    with patch("razorback.cli.run._invoke_harbor", side_effect=fake_invoke_harbor), \
         patch("razorback.cli.run._run_canary"), \
         patch("razorback.runs.aggregate.aggregate_run_dir", side_effect=fake_aggregate):
        result = CliRunner().invoke(app, ["run", str(spec), "--runs-dir", str(runs_dir)])
    assert result.exit_code == 0, result.output
    assert captured["benchmark_kind"] == "local"
    assert captured["run_dir"].name


def test_cli_run_invokes_aggregator_on_harbor_failure(tmp_path: Path):
    """AC-1: after harbor exits success OR failure, aggregator still runs."""
    spec = _fake_spec(tmp_path)
    runs_dir = tmp_path / "_runs"

    called: list[Path] = []

    def fake_invoke_harbor(job_config_yaml, env):
        return 30

    def fake_aggregate(run_dir, **kwargs):
        called.append(run_dir)
        (run_dir / "manifest.json").write_text("{}")

    with patch("razorback.cli.run._invoke_harbor", side_effect=fake_invoke_harbor), \
         patch("razorback.cli.run._run_canary"), \
         patch("razorback.runs.aggregate.aggregate_run_dir", side_effect=fake_aggregate):
        result = CliRunner().invoke(app, ["run", str(spec), "--runs-dir", str(runs_dir)])
    assert result.exit_code == 30
    assert len(called) == 1


def test_cli_run_aggregator_failure_does_not_mask_harbor_exit(tmp_path: Path):
    """T8: when the aggregator raises, rk run still exits with harbor's code."""
    spec = _fake_spec(tmp_path)
    runs_dir = tmp_path / "_runs"

    with patch("razorback.cli.run._invoke_harbor", return_value=0), \
         patch("razorback.cli.run._run_canary"), \
         patch(
             "razorback.runs.aggregate.aggregate_run_dir",
             side_effect=RuntimeError("synthetic"),
         ):
        result = CliRunner().invoke(app, ["run", str(spec), "--runs-dir", str(runs_dir)])
    assert result.exit_code == 0
    combined = result.output or ""
    assert "aggregate" in combined.lower() or "synthetic" in combined.lower()
