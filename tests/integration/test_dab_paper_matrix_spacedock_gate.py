# ABOUTME: T10/T11 integration — matrix dispatcher's spacedock smoke hook
# ABOUTME: REJECTs runs whose dispatch manifests report captured == 0.

import json
import re
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER = REPO_ROOT / "examples" / "drivers" / "dab-paper-matrix.sh"


def test_dispatcher_hook_invokes_smoke_validator_via_subprocess(tmp_path):
    """The matrix dispatcher embeds 'razorback.agents.subagent_smoke' as the
    smoke gate command for the spacedock variant. The validator accepts run
    dirs and resolves per-trial manifests internally. Catch accidental hook
    removal during refactors."""
    body = DRIVER.read_text()
    assert "razorback.agents.subagent_smoke" in body
    assert "subagent-dispatch-missing" in body
    assert re.search(r'if \[\[ "\$v" == "spacedock" \]\]', body), (
        "spacedock smoke gate must be wrapped in a variant guard"
    )


def test_smoke_validator_rejects_zero_captured_cell(tmp_path):
    """Build a synthetic cell with captured=0 and confirm the validator emits
    the expected exit code + stderr. (Direct invocation, no rk-run dependency.)"""
    cell = tmp_path / "cell"
    cell.mkdir()
    manifest = {
        "schema_version": "razorback-subagent-traces-v1",
        "expected": None,
        "captured": 0,
        "dispatches": [],
        "parent_agent": {"model": "claude-opus-4-7"},
        "capture_source": "razorback-claude-cli-trace",
    }
    (cell / "subagent-trace-manifest.json").write_text(json.dumps(manifest))
    result = subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "--project",
            str(REPO_ROOT),
            "python",
            "-m",
            "razorback.agents.subagent_smoke",
            str(cell),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "subagent-dispatch-missing" in result.stderr


def test_smoke_validator_passes_one_captured_cell(tmp_path):
    cell = tmp_path / "cell"
    cell.mkdir()
    manifest = {
        "schema_version": "razorback-subagent-traces-v1",
        "expected": None,
        "captured": 1,
        "dispatches": [
            {
                "tool_use_id": "toolu_x",
                "subagent_type": "spacedock:ensign",
                "prompt_sha256": "a" * 64,
                "spawn_index": 0,
            }
        ],
        "parent_agent": {"model": "claude-opus-4-7"},
        "capture_source": "razorback-claude-cli-trace",
    }
    (cell / "subagent-trace-manifest.json").write_text(json.dumps(manifest))
    result = subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "--project",
            str(REPO_ROOT),
            "python",
            "-m",
            "razorback.agents.subagent_smoke",
            str(cell),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
