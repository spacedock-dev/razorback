# ABOUTME: T3 — dab-paper-matrix.sh wires the external-oracle audit as a
# ABOUTME: post-run / pre-audit per-cell hook with the right ledger contract.

import json
import subprocess
import sys
from pathlib import Path


DRIVER = Path("examples/drivers/dab-paper-matrix.sh")
AGGREGATOR = Path("examples/drivers/aggregate-goal1-scores.py")


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


def test_driver_invokes_external_oracle_audit_between_rk_run_and_rk_audit() -> None:
    """AC-4 shape: the matrix driver must invoke the audit module per-cell."""
    body = DRIVER.read_text()
    assert "razorback.agents.external_oracle_audit" in body, (
        "dab-paper-matrix.sh must invoke the external-oracle audit per-cell"
    )
    # Hook fires for EVERY variant (NOT gated like the smoke gate).
    # If a variant-only conditional shows up wrapping the audit, this catches it.
    # Find the rk run / rk audit invocation sites (skip the file-header
    # comments that mention the commands as documentation).
    rk_run_idx = body.index('uv run --project "$REPO_ROOT" rk run')
    audit_idx = body.index("razorback.agents.external_oracle_audit")
    rk_audit_idx = body.index('uv run --project "$REPO_ROOT" rk audit')
    assert rk_run_idx < audit_idx < rk_audit_idx, (
        "external-oracle audit must run after rk run and before rk audit"
    )


def test_driver_sets_external_oracle_cheating_status_on_audit_rc_2() -> None:
    body = DRIVER.read_text()
    assert "external-oracle-cheating" in body, (
        "driver must surface external-oracle-cheating as a distinct ledger status"
    )
    assert "external-oracle-audit-error" in body, (
        "driver must surface external-oracle-audit-error (rc==3) distinctly"
    )


def test_driver_writes_audit_sidecar_path_to_failures_log() -> None:
    """AC-4: cheating-cell rows must be appended to FAILURES_LOG so the
    captain-facing review can locate the offending cells from a single file."""
    body = DRIVER.read_text()
    # Same pattern as the run_failed branch: append to FAILURES_LOG on rc==2.
    assert "FAILURES_LOG" in body
    # External-oracle-cheating rows must increment failed_cells (so the matrix
    # exit code surfaces them) rather than ok_cells.
    audit_section = body[body.index("razorback.agents.external_oracle_audit"):]
    assert "failed_cells=$((failed_cells+1))" in audit_section, (
        "external-oracle-cheating cells must increment failed_cells"
    )


def test_audit_module_rejects_synthetic_cheating_cell(tmp_path: Path) -> None:
    """End-to-end: synthetic cell with a load_dataset event → exit 2 + sidecar
    findings non-empty. The dispatcher relies on this contract."""
    cell = tmp_path / "cheating"
    _write_trace(
        cell,
        [
            {"type": "system", "subtype": "init", "tools": ["Bash"]},
            _bash_event(
                "python3 -c \"from datasets import load_dataset; "
                "load_dataset('fancyzhx/ag_news')\""
            ),
        ],
    )
    rc = subprocess.run(
        [sys.executable, "-m", "razorback.agents.external_oracle_audit", str(cell)],
        capture_output=True,
        text=True,
    )
    assert rc.returncode == 2, rc.stderr
    sidecar = json.loads((cell / "external-oracle-audit.json").read_text())
    assert sidecar["confirmed_count"] >= 1
    assert sidecar["findings"], "sidecar findings must be non-empty for cheating cells"


def test_audit_module_passes_synthetic_clean_cell(tmp_path: Path) -> None:
    cell = tmp_path / "clean"
    _write_trace(
        cell,
        [
            {"type": "system", "subtype": "init", "tools": ["Bash"]},
            _bash_event("psql -c 'SELECT 1'"),
        ],
    )
    rc = subprocess.run(
        [sys.executable, "-m", "razorback.agents.external_oracle_audit", str(cell)],
        capture_output=True,
        text=True,
    )
    assert rc.returncode == 0, rc.stderr
    sidecar = json.loads((cell / "external-oracle-audit.json").read_text())
    assert sidecar["findings"] == []
    assert sidecar["confirmed_count"] == 0
