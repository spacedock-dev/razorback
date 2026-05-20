# ABOUTME: AC-1 walking skeleton: rk run examples/specs/_deterministic-smoke.frozen.yaml.
# ABOUTME: Asserts exit 0 + summary.json parses against the harbor schema (3/3 pass baseline).

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
SPEC_TEMPLATE = REPO / "examples" / "specs" / "_deterministic-smoke.yaml"


@pytest.mark.integration
def test_deterministic_smoke_runs_end_to_end(colima_safe_tmp_path: Path):
    runs_root = colima_safe_tmp_path / "_runs"
    runs_root.mkdir()

    from razorback.spec.freeze import freeze_spec
    from razorback.spec.parse import parse_spec_file

    spec = parse_spec_file(SPEC_TEMPLATE)
    frozen_text = freeze_spec(spec)
    frozen_path = colima_safe_tmp_path / "_deterministic-smoke.frozen.yaml"
    frozen_path.write_text(frozen_text)

    env = {**os.environ}
    result = subprocess.run(
        [
            sys.executable, "-m", "razorback.cli", "run",
            str(frozen_path), "--runs-dir", str(runs_root),
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=1200,
    )

    assert result.returncode == 0, (
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )

    experiment_dir = runs_root / "_deterministic-smoke"
    run_dirs = [p for p in experiment_dir.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1, run_dirs
    run_dir = run_dirs[0]

    # AC-3: spec.frozen.yaml present and byte-faithful.
    assert (run_dir / "spec.frozen.yaml").read_text() == frozen_text
    # AC-3: provenance.yaml present.
    assert (run_dir / "provenance.yaml").is_file()

    # AC-1: harbor writes result.json at the job root; mechanism check is that
    # it parses and that all trials completed without harbor-runtime exceptions.
    result_path = run_dir / "result.json"
    assert result_path.is_file(), f"no result.json found under {run_dir}"
    harbor_result = json.loads(result_path.read_text())
    stats = harbor_result.get("stats", {})
    assert stats.get("n_completed_trials", 0) >= 1
    assert stats.get("n_errored_trials", 0) == 0, (
        f"harbor reported {stats.get('n_errored_trials')} errored trials; "
        f"deterministic-smoke baseline expects 0"
    )
