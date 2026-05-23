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
