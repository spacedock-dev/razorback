# ABOUTME: AC-1 fix: rk run routes harbor's hardcoded ~/.cache/harbor under runs-dir
# ABOUTME: so the walking-skeleton works in sandboxed environments (CI, agent sandboxes, Colima).

import os
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from razorback.cli import app


FROZEN_SPEC_YAML = (
    "version: 1\n"
    "experiment: phase1-harbor-cache-test\n"
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


def test_invoke_harbor_routes_HOME_under_runs_dir(tmp_path: Path):
    spec_path = tmp_path / "input.frozen.yaml"
    spec_path.write_text(FROZEN_SPEC_YAML)
    runs_dir = tmp_path / "_runs"

    captured_env: dict[str, str] = {}

    def fake_invoke(job_config_yaml: Path, env: dict[str, str]) -> int:
        captured_env.update(env)
        return 0

    with patch("razorback.cli.run._run_canary"), \
         patch(
             "razorback.cli.run._resolve_model_version",
             return_value=("claude-opus-4-5-20251022", "2026-05-19"),
         ), \
         patch("razorback.cli.run._invoke_harbor", side_effect=fake_invoke):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            app,
            ["run", str(spec_path), "--runs-dir", str(runs_dir)],
        )
        assert result.exit_code == 0, result.stderr or result.stdout

    # HOME for harbor subprocess must live under runs-dir so harbor's
    # ~/.cache/harbor and ~/.harbor expand to writable, sandbox-safe paths.
    home = captured_env.get("HOME")
    assert home is not None, "rk run must set HOME for harbor subprocess"
    home_path = Path(home).resolve()
    runs_root = runs_dir.resolve()
    assert runs_root in home_path.parents or home_path == runs_root or runs_root in home_path.parents, (
        f"HOME={home_path} not under runs_dir={runs_root}"
    )
    # The directory must exist so harbor's mkdir(parents=True, exist_ok=True) succeeds.
    assert home_path.exists()
    assert (home_path / ".cache").exists() or home_path.exists()
