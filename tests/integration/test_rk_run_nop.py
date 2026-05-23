# ABOUTME: End-to-end test for `rk run examples/specs/nop.yaml`.
# ABOUTME: Asserts AC-1 through AC-8 against a single live run-dir.

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "examples" / "specs" / "nop.yaml"


@pytest.fixture
def runs_root(colima_safe_tmp_path):
    return colima_safe_tmp_path / "_runs"


def test_rk_run_nop_end_to_end(runs_root):
    env = {**os.environ}
    result = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(SPEC), "--runs-dir", str(runs_root)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    # AC-1: exit 0.
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"

    # AC-1: a single run-dir under _runs/m1-nop/<job_name>/.
    experiment_dir = runs_root / "m1-nop"
    run_dirs = list(experiment_dir.iterdir())
    assert len(run_dirs) == 1, run_dirs
    run_dir = run_dirs[0]

    # AC-2: §6.3 layout at the top level.
    for name in ("spec.frozen.yaml", "manifest.json", "events.jsonl", "summary.json", "lock.json"):
        assert (run_dir / name).is_file(), f"missing {name} in {run_dir}"

    # AC-2: per-trial layout (harbor 0.6.6 places trials directly under run_dir).
    candidates = [p for p in run_dir.iterdir() if p.is_dir()]
    trial_dir = next(p for p in candidates if (p / "config.json").exists())
    for name in ("config.json", "result.json", "agent", "verifier", "artifacts"):
        assert (trial_dir / name).exists(), f"missing {name} in {trial_dir}"

    # AC-3: spec.frozen.yaml is a faithful echo (input bytes appear in frozen text).
    frozen_text = (run_dir / "spec.frozen.yaml").read_text()
    assert "experiment: m1-nop" in frozen_text
    assert "kind: nop" in frozen_text
    assert "kind: local" in frozen_text

    # AC-4: manifest.json carries run_dir_version: 1 and ISO 8601 created_at.
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["run_dir_version"] == 1
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", manifest["created_at"])
    datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00"))

    # AC-5: v2 preserves the events.jsonl artifact. Harbor may leave it empty
    # for local nop runs; when rows exist, they must be valid JSON.
    lines = (run_dir / "events.jsonl").read_text().splitlines()
    parsed = [json.loads(l) for l in lines]
    assert all(isinstance(p, dict) for p in parsed)

    # AC-6: job_name == sha256(frozen)[:16].
    expected_jn = hashlib.sha256(frozen_text.encode("utf-8")).hexdigest()[:16]
    assert run_dir.name == expected_jn

    # AC-1 (verifier): summary records n_errored_trials == 0.
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary.get("n_trials_errored", summary.get("n_errored_trials")) == 0
    assert summary.get("n_trials_completed", summary.get("n_completed_trials")) >= 1


def test_rk_run_unknown_top_level_key_exits_10(colima_safe_tmp_path):
    bad = colima_safe_tmp_path / "bad.yaml"
    bad.write_text(
        "version: 1\nexperiment: x\nagent:\n  kind: nop\nbenchmark:\n  kind: local\nunknown_key: foo\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(bad)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 10, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "SpecError" in result.stderr
