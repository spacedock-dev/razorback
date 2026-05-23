# ABOUTME: AC-3: rk run writes spec.frozen.yaml + provenance.yaml into the harbor run-dir.
# ABOUTME: spec.frozen.yaml matches the input bytes (no re-freezing inside rk run).

from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from razorback.cli import app


FROZEN_SPEC_YAML = (
    "version: 1\n"
    "experiment: phase1-ac3-test\n"
    "agent:\n"
    "  kind: nop\n"
    "benchmark:\n"
    "  kind: local\n"
    "  task_paths: []\n"
    "trials: 1\n"
    "provenance:\n"
    "  model_resolved_version: claude-opus-4-5-20251022\n"
    "  harbor_version: 0.6.6\n"
)


def test_rk_run_writes_spec_frozen_yaml_byte_for_byte(tmp_path: Path):
    spec_path = tmp_path / "input.frozen.yaml"
    spec_path.write_text(FROZEN_SPEC_YAML)
    runs_dir = tmp_path / "_runs"

    with patch("razorback.cli.run._run_canary"), \
         patch(
             "razorback.cli.run._resolve_model_version",
             return_value=("claude-opus-4-5-20251022", "2026-05-19"),
         ), \
         patch("razorback.cli.run._invoke_harbor", return_value=0):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            app,
            ["run", str(spec_path), "--runs-dir", str(runs_dir)],
        )
        assert result.exit_code == 0, result.stderr or result.stdout

    experiment_dir = runs_dir / "phase1-ac3-test"
    run_dirs = [p for p in experiment_dir.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1, run_dirs
    run_dir = run_dirs[0]

    # AC-3: byte-for-byte echo of input frozen spec.
    written = (run_dir / "spec.frozen.yaml").read_text()
    assert written == FROZEN_SPEC_YAML

    # AC-3: provenance.yaml is also present and parses.
    assert (run_dir / "provenance.yaml").is_file()
    pv = yaml.safe_load((run_dir / "provenance.yaml").read_text())
    assert pv["model_resolved_version"] == "claude-opus-4-5-20251022"
    assert pv["harbor_version"] == "0.6.6"
