# ABOUTME: Filesystem-only primitives that enumerate and read razorback run-dirs.
# ABOUTME: Wire shapes here are semver-stable per spec §3.3.

import json
from pathlib import Path


def list_run_dirs(root: Path, *, experiment: str | None = None) -> list[dict]:
    """Enumerate razorback run-dirs under <root>/<experiment>/<job>/.

    A run-dir is recognized by the presence of manifest.json. summary.json
    is tolerated as missing (the headline score becomes None). Output is
    sorted by (experiment, job_name).
    """
    if not root.exists():
        return []

    entries: list[dict] = []
    for experiment_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if experiment is not None and experiment_dir.name != experiment:
            continue
        for run_dir in sorted(p for p in experiment_dir.iterdir() if p.is_dir()):
            manifest_path = run_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text())
            except (OSError, json.JSONDecodeError):
                continue

            summary_path = run_dir / "summary.json"
            stratified_pass_at_1: float | None = None
            if summary_path.exists():
                try:
                    summary = json.loads(summary_path.read_text())
                    stratified_pass_at_1 = summary.get("stratified_pass_at_1")
                except (OSError, json.JSONDecodeError):
                    stratified_pass_at_1 = None

            entries.append(
                {
                    "path": str(run_dir.resolve()),
                    "experiment": manifest.get("experiment", experiment_dir.name),
                    "job_name": manifest.get("job_name", run_dir.name),
                    "created_at": manifest.get("created_at"),
                    "run_dir_version": manifest.get("run_dir_version"),
                    "stratified_pass_at_1": stratified_pass_at_1,
                }
            )
    return entries


def read_run_dir(run_dir: Path) -> dict:
    """Read one run-dir's manifest + summary.

    Raises FileNotFoundError if the run-dir is missing or if either
    manifest.json or summary.json is absent.
    """
    if not run_dir.exists():
        raise FileNotFoundError(f"run-dir does not exist: {run_dir}")

    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found in {run_dir}")
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"summary.json not found in {run_dir}")

    return {
        "manifest": json.loads(manifest_path.read_text()),
        "summary": json.loads(summary_path.read_text()),
        "path": str(run_dir.resolve()),
    }
