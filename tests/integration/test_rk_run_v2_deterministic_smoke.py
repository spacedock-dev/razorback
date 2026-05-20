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

    # AC-1: summary.json parses (harbor writes it; razorback does not).
    summary_paths = list(run_dir.glob("**/summary.json"))
    assert summary_paths, f"no summary.json found under {run_dir}"
    summary = json.loads(summary_paths[0].read_text())
    if "n_completed_trials" in summary:
        assert summary["n_completed_trials"] >= 1
        assert summary.get("n_errored_trials", 0) == 0
