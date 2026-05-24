# ABOUTME: T3 cycle-2 — dab-paper-matrix.sh wires rk audit --policy strict as
# ABOUTME: the per-cell external-oracle gate (no separate gate-only module).

import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app


DRIVER = Path("examples/drivers/dab-paper-matrix.sh")
AGGREGATOR = Path("examples/drivers/aggregate-goal1-scores.py")

runner = CliRunner()


def _write_trace(cell_dir: Path, events: list[dict]) -> Path:
    agent_dir = cell_dir / "steps" / "main" / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    path = agent_dir / "claude-code.txt"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return path


def _bash_event(cmd: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-7",
            "id": "msg_x",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_x",
                    "name": "Bash",
                    "input": {"command": cmd},
                }
            ],
        },
    }


def test_driver_invokes_rk_audit_strict_after_rk_run() -> None:
    """AC-4 shape: the matrix driver must invoke rk audit --policy strict
    as the per-cell external-oracle gate, between rk run and rk score."""
    body = DRIVER.read_text()
    assert "rk audit" in body, "dab-paper-matrix.sh must invoke rk audit per-cell"
    assert "--policy strict" in body, "rk audit must run under --policy strict"
    rk_run_idx = body.index('uv run --project "$REPO_ROOT" rk run')
    audit_idx = body.index('uv run --project "$REPO_ROOT" rk audit')
    rk_score_idx = body.index('uv run --project "$REPO_ROOT" rk score')
    assert rk_run_idx < audit_idx < rk_score_idx, (
        "rk audit --policy strict must run after rk run and before rk score"
    )


def test_driver_maps_audit_exit_23_to_external_oracle_cheating() -> None:
    body = DRIVER.read_text()
    assert "external-oracle-cheating" in body, (
        "driver must surface external-oracle-cheating as a distinct ledger status"
    )
    assert "external-oracle-audit-error" in body, (
        "driver must surface external-oracle-audit-error as a distinct ledger status"
    )
    # The exit-23 → cheating mapping must be explicit in the script.
    assert "audit_rc == 23" in body, (
        "driver must explicitly check for rk audit's strict-policy exit 23"
    )


def test_driver_failing_audit_appends_to_failures_log() -> None:
    """A failing audit must roll the cell from ok_cells to failed_cells and
    append to FAILURES_LOG so the captain-facing review can locate the
    offending cells from one file."""
    body = DRIVER.read_text()
    assert "FAILURES_LOG" in body
    audit_section = body[body.index("rk audit"):]
    assert "failed_cells=$((failed_cells+1))" in audit_section
    assert "ok_cells=$((ok_cells-1))" in audit_section


def test_rk_audit_strict_rejects_synthetic_cheating_cell(tmp_path: Path) -> None:
    """End-to-end: synthetic claude-code.txt with load_dataset event makes
    rk audit --policy strict exit 23 — the dispatcher relies on this contract."""
    cell = tmp_path / "task-a" / "query-1" / "trial-0"
    _write_trace(cell, [
        {"type": "system", "subtype": "init", "tools": ["Bash"]},
        _bash_event(
            "python3 -c \"from datasets import load_dataset; "
            "load_dataset('fancyzhx/ag_news')\""
        ),
    ])
    result = runner.invoke(app, ["audit", str(tmp_path), "--policy", "strict"])
    assert result.exit_code == 23, result.stdout
    assert "TaintFindingsError" in result.output


def test_rk_audit_strict_passes_synthetic_clean_cell(tmp_path: Path) -> None:
    cell = tmp_path / "task-a" / "query-1" / "trial-0"
    _write_trace(cell, [
        {"type": "system", "subtype": "init", "tools": ["Bash"]},
        _bash_event("psql -c 'SELECT 1'"),
        _bash_event("pip install rapidfuzz"),
    ])
    result = runner.invoke(app, ["audit", str(tmp_path), "--policy", "strict"])
    assert result.exit_code == 0, result.stdout
    payload, _ = json.JSONDecoder().raw_decode(result.stdout)
    assert payload["summary"]["tainted"] == 0
    assert payload["summary"]["clean"] >= 1
