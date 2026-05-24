# ABOUTME: AC-4 verifier — `rk score` surfaces taint_status from audit.json and
# ABOUTME: auto-pulls paper_baseline from the spec frontmatter.

from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app

FIXTURE_ROOT = Path(__file__).parent.parent / "fixtures" / "score"
SOURCE_FIXTURE = FIXTURE_ROOT / "mixed_trial_run_dir"


def _copy_fixture(dst: Path) -> Path:
    """Copy the mixed_trial fixture into a fresh tmp run-dir."""
    shutil.copytree(SOURCE_FIXTURE, dst)
    return dst


def _write_audit_json(run_dir: Path, *, clean: int = 2, tainted: int = 1) -> None:
    audit = {
        "policy": "strict",
        "schema_version": "rk-audit-v1",
        "summary": {
            "clean": clean,
            "tainted": tainted,
            "coverage_missing": 0,
        },
        "trials": [],
    }
    (run_dir / "audit.json").write_text(json.dumps(audit))


def _write_frozen_spec_with_paper_baseline(
    run_dir: Path, *, name: str, value: float
) -> None:
    spec = (
        "version: 1\n"
        "experiment: test-paper-baseline-auto-pull\n"
        "agent:\n"
        "  kind: nop\n"
        "benchmark:\n"
        "  kind: harbor\n"
        "  dataset: adyen/dabstep@latest\n"
        "trials: 1\n"
        "experiment_meta:\n"
        f"  paper_baseline:\n    name: {name}\n    value: {value}\n"
    )
    (run_dir / "spec.frozen.yaml").write_text(spec)


def test_score_surfaces_taint_status_from_audit_json(tmp_path: Path) -> None:
    """AC-4: rk score's JSON output has a top-level `taint_status` field equal
    to the audit.json summary verdict (clean/tainted counts)."""
    run_dir = _copy_fixture(tmp_path / "rd")
    _write_audit_json(run_dir, clean=2, tainted=1)

    runner = CliRunner()
    result = runner.invoke(app, ["score", str(run_dir), "--format", "json"])
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert "taint_status" in payload
    assert payload["taint_status"]["clean"] == 2
    assert payload["taint_status"]["tainted"] == 1


def test_score_soft_fails_when_audit_json_missing(tmp_path: Path) -> None:
    """When audit.json is absent, rk score warns but proceeds (soft-fail)."""
    run_dir = _copy_fixture(tmp_path / "rd")

    runner = CliRunner()
    result = runner.invoke(app, ["score", str(run_dir), "--format", "json"])
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    # Either omitted entirely or marked None/missing — the contract is
    # "soft-fail keeps score working without audit"
    assert payload.get("taint_status") in (None, {"clean": 0, "tainted": 0, "coverage_missing": 0}, {"status": "missing"})


def test_score_auto_pulls_paper_baseline_from_frozen_spec(tmp_path: Path) -> None:
    """AC-4: when spec.frozen.yaml declares experiment_meta.paper_baseline,
    rk score auto-applies it as the --against-constant target."""
    run_dir = _copy_fixture(tmp_path / "rd")
    _write_audit_json(run_dir)
    _write_frozen_spec_with_paper_baseline(run_dir, name="paper", value=0.476)

    runner = CliRunner()
    result = runner.invoke(app, ["score", str(run_dir), "--format", "json"])
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert "against_constant" in payload, payload
    cmp_block = payload["against_constant"]
    assert cmp_block["name"] == "paper"
    assert cmp_block["value"] == 0.476
    assert cmp_block.get("source") == "spec.frontmatter"


def test_score_explicit_against_constant_overrides_paper_baseline(tmp_path: Path) -> None:
    """Explicit --against-constant CLI flag wins over the spec frontmatter
    auto-pull; the source field flips back to 'cli' for transparency."""
    run_dir = _copy_fixture(tmp_path / "rd")
    _write_audit_json(run_dir)
    _write_frozen_spec_with_paper_baseline(run_dir, name="paper", value=0.476)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["score", str(run_dir), "--format", "json", "--against-constant", "custom=0.5"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    cmp_block = payload["against_constant"]
    assert cmp_block["name"] == "custom"
    assert cmp_block["value"] == 0.5
    assert cmp_block.get("source") == "cli"
