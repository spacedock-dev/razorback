# ABOUTME: PKG-17 post-harbor aggregator. Writes manifest/summary/events/per_trial_outcomes.
# ABOUTME: Reads run-dir filesystem state; no JobResult dependency (harbor runs as subprocess).

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_SCHEMA_VERSION = 1


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_manifest(
    run_dir: Path,
    *,
    spec_path: Path,
    frozen_spec_hash: str,
    provenance_hash: str,
    harbor_job_name: str,
    n_trials_total: int,
    n_trials_completed: int,
    n_trials_errored: int,
    per_trial_paths: list[str],
    benchmark_kind: str | None,
) -> None:
    """AC-1: write <run_dir>/manifest.json.

    Carries enough to reconstruct provenance + per-trial discovery. The
    experiment / job_name fields are derived from the run-dir path so
    consumers don't need to re-parse the frozen spec to enumerate runs.
    """
    payload = {
        "run_dir_version": MANIFEST_SCHEMA_VERSION,
        "experiment": run_dir.parent.name,
        "job_name": run_dir.name,
        "created_at": _utcnow_iso(),
        "spec_path": str(spec_path),
        "frozen_spec_hash": frozen_spec_hash,
        "provenance_hash": provenance_hash,
        "harbor_job_name": harbor_job_name,
        "n_trials_total": n_trials_total,
        "n_trials_completed": n_trials_completed,
        "n_trials_errored": n_trials_errored,
        "per_trial_paths": per_trial_paths,
        "benchmark_kind": benchmark_kind,
    }
    (run_dir / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n")
