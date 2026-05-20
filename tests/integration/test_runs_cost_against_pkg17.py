# ABOUTME: PKG-17 AC-6 — rk runs cost walks PKG-17-produced run-dirs.

import json
import shutil
import subprocess
import sys
from pathlib import Path

from razorback.runs.aggregate import aggregate_run_dir

REPO = Path(__file__).resolve().parents[2]
FIXTURE_RUN = REPO / "tests" / "fixtures" / "runs" / "post_harbor_skeleton"


def _populate(run_dir: Path, *, cost_in_summary: float | None) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for child in FIXTURE_RUN.iterdir():
        target = run_dir / child.name
        if target.exists():
            continue
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy(child, target)
    (run_dir / "spec.frozen.yaml").write_text("version: 1\nexperiment: smoke\n")
    (run_dir / "provenance.yaml").write_text("harbor_version: 0.6.6\n")
    aggregate_run_dir(
        run_dir,
        spec_path=Path("/x"),
        frozen_spec_hash="a" * 64,
        provenance_hash="b" * 64,
        harbor_job_name=run_dir.name,
        benchmark_kind="dab",
    )
    if cost_in_summary is not None:
        summary = json.loads((run_dir / "summary.json").read_text())
        summary["cost_usd"] = cost_in_summary
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def test_rk_runs_cost_sums_pkg17_run_dirs(tmp_path: Path):
    matrix = tmp_path / "matrix"
    _populate(matrix / "bookreview" / "j1", cost_in_summary=1.23)
    _populate(matrix / "bookreview" / "j2", cost_in_summary=4.56)
    _populate(matrix / "crmarenapro" / "j3", cost_in_summary=7.89)

    result = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "runs", "cost", "--root", str(matrix)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    doc = json.loads(result.stdout)
    assert doc["n_known"] == 3
    assert doc["n_unknown"] == 0
    assert abs(doc["total_usd"] - (1.23 + 4.56 + 7.89)) < 1e-9
    assert not doc["warnings"]
