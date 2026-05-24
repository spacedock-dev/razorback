# ABOUTME: T10/T11 — subagent_smoke __main__ exits 0/2/3 based on manifest captured.

import json
import subprocess
import sys
from pathlib import Path


def _run_validator(cell_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "razorback.agents.subagent_smoke", str(cell_dir)],
        capture_output=True,
        text=True,
    )


def _write_manifest(cell_dir: Path, captured: int) -> None:
    cell_dir.mkdir(parents=True, exist_ok=True)
    (cell_dir / "subagent-trace-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "razorback-subagent-traces-v1",
                "expected": None,
                "captured": captured,
                "dispatches": [],
                "parent_agent": {"model": "claude-opus-4-7"},
                "capture_source": "razorback-claude-cli-trace",
            }
        )
    )


def _write_run_inventory(run_dir: Path, trial_names: list[str]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_dir_version": 1,
                "per_trial_paths": trial_names,
                "benchmark_kind": "dab",
            }
        )
    )
    (run_dir / "spec.frozen.yaml").write_text(
        "agent:\n  kind: spacedock_solver\n",
        encoding="utf-8",
    )


def test_validator_exits_zero_when_captured_ge_one(tmp_path):
    cell = tmp_path / "cell"
    _write_manifest(cell, captured=1)
    result = _run_validator(cell)
    assert result.returncode == 0, result.stderr


def test_validator_exits_two_when_captured_zero(tmp_path):
    cell = tmp_path / "cell"
    _write_manifest(cell, captured=0)
    result = _run_validator(cell)
    assert result.returncode == 2
    assert "subagent-dispatch-missing" in result.stderr


def test_validator_exits_three_when_manifest_missing(tmp_path):
    cell = tmp_path / "missing"
    cell.mkdir()
    result = _run_validator(cell)
    assert result.returncode == 3
    assert "manifest-missing" in result.stderr


def test_validator_exits_zero_for_run_dir_with_per_trial_manifests(tmp_path):
    run_dir = tmp_path / "run"
    _write_run_inventory(run_dir, ["trial-a__aaaa", "trial-b__bbbb"])
    _write_manifest(run_dir / "trial-a__aaaa", captured=1)
    _write_manifest(run_dir / "trial-b__bbbb", captured=1)

    result = _run_validator(run_dir)

    assert result.returncode == 0, result.stderr


def test_validator_exits_three_when_listed_trial_manifest_missing(tmp_path):
    run_dir = tmp_path / "run"
    _write_run_inventory(run_dir, ["trial-a__aaaa", "trial-b__bbbb"])
    _write_manifest(run_dir / "trial-a__aaaa", captured=1)
    (run_dir / "trial-b__bbbb").mkdir()

    result = _run_validator(run_dir)

    assert result.returncode == 3
    assert "manifest-missing" in result.stderr
    assert "trial-b__bbbb/subagent-trace-manifest.json" in result.stderr


def test_validator_accepts_legacy_single_trial_root_manifest(tmp_path):
    run_dir = tmp_path / "run"
    _write_run_inventory(run_dir, ["trial-a__aaaa"])
    (run_dir / "trial-a__aaaa").mkdir()
    _write_manifest(run_dir, captured=1)

    result = _run_validator(run_dir)

    assert result.returncode == 0, result.stderr
