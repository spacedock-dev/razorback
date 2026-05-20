# ABOUTME: PKG-17 AC-5 — lock.json drift surface for rk runs show.

import json
from pathlib import Path

from razorback.runs.lock_drift import compute_drift


def _write_lock(run_dir: Path, harbor_version: str) -> None:
    (run_dir / "lock.json").write_text(json.dumps({
        "schema_version": 1,
        "created_at": "2026-05-20T10:00:00Z",
        "harbor": {"version": harbor_version, "is_editable": False},
    }))


def _write_provenance(run_dir: Path, harbor_version: str) -> None:
    (run_dir / "provenance.yaml").write_text(
        f"harbor_version: {harbor_version}\nmodel_resolved_version: claude-opus-4-5-20250101\n"
    )


def test_compute_drift_returns_none_when_fingerprints_match(tmp_path: Path):
    run_dir = tmp_path / "exp" / "job"
    run_dir.mkdir(parents=True)
    _write_lock(run_dir, "0.6.6")
    _write_provenance(run_dir, "0.6.6")
    assert compute_drift(run_dir) is None


def test_compute_drift_returns_record_when_harbor_version_disagrees(tmp_path: Path):
    run_dir = tmp_path / "exp" / "job"
    run_dir.mkdir(parents=True)
    _write_lock(run_dir, "0.6.7")
    _write_provenance(run_dir, "0.6.6")
    drift = compute_drift(run_dir)
    assert drift is not None
    assert drift["field"] == "harbor_version"
    assert drift["provenance"] == "0.6.6"
    assert drift["lock"] == "0.6.7"


def test_compute_drift_tolerates_missing_lock_json(tmp_path: Path):
    """harbor>=0.7 may relocate lock.json; absent file → drift=None, not crash."""
    run_dir = tmp_path / "exp" / "job"
    run_dir.mkdir(parents=True)
    _write_provenance(run_dir, "0.6.6")
    assert compute_drift(run_dir) is None


def test_rk_runs_show_renders_drift_record(tmp_path: Path):
    """End-to-end: rk runs show <run-dir> emits lock_drift in JSON output."""
    from typer.testing import CliRunner
    from razorback.cli.runs import runs_app

    run_dir = tmp_path / "exp" / "job"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(json.dumps({
        "run_dir_version": 1,
        "experiment": "exp",
        "job_name": "job",
        "created_at": "2026-05-20T10:00:00Z",
    }))
    (run_dir / "summary.json").write_text(json.dumps({"summary_version": 1}))
    _write_lock(run_dir, "0.6.7")
    _write_provenance(run_dir, "0.6.6")

    result = CliRunner().invoke(runs_app, ["show", str(run_dir)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["lock_drift"]["field"] == "harbor_version"
