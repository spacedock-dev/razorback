# ABOUTME: Unit-test fixtures for pkg1: make_run_dir synthesizes razorback run-dirs.
# ABOUTME: Mirrors the harbor run-dir layout (<root>/<experiment>/<job>/manifest+summary).

import json
from pathlib import Path


DEFAULT_MANIFEST = {
    "run_dir_version": 1,
    "experiment": "exp",
    "job_name": "job",
    "created_at": "2026-05-20T00:00:00Z",
    "benchmark_kind": "dab",
}

DEFAULT_SUMMARY = {
    "summary_version": 1,
    "stratified_pass_at_1": 1.0,
    "datasets": {
        "bookreview": {
            "dataset_pass_at_1": 1.0,
            "n_queries": 1,
            "queries": [
                {"query_id": 1, "n_trials": 1, "n_correct": 1, "pass_at_1": 1.0}
            ],
        },
    },
}


def make_run_dir(
    tmp_path: Path,
    *,
    root: str,
    experiment: str,
    job_name: str,
    manifest_overrides: dict | None = None,
    summary_overrides: dict | None = None,
    omit: tuple[str, ...] = (),
    cost_in_summary: float | None = None,
    cost_in_result_stats: float | None = None,
    write_result_stats: bool = False,
) -> Path:
    """Create a synthetic run-dir at <tmp_path>/<root>/<experiment>/<job_name>/.

    Writes manifest.json and summary.json unless their names appear in `omit`.
    Returns the run-dir path.

    Cost-bearing kwargs (Phase 4a):
    - cost_in_summary: writes `cost_usd: <value>` into summary.json.
    - cost_in_result_stats: writes `result.json` with `stats.cost_usd: <value>`.
      Pass write_result_stats=True with cost_in_result_stats=None to emit
      the present-but-null case (the subscription-auth shape).
    """
    run_dir = tmp_path / root / experiment / job_name
    run_dir.mkdir(parents=True, exist_ok=True)

    if "manifest.json" not in omit:
        manifest = {**DEFAULT_MANIFEST, "experiment": experiment, "job_name": job_name}
        if manifest_overrides:
            manifest.update(manifest_overrides)
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    if "summary.json" not in omit:
        summary = dict(DEFAULT_SUMMARY)
        if summary_overrides:
            summary.update(summary_overrides)
        if cost_in_summary is not None:
            summary["cost_usd"] = cost_in_summary
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    if cost_in_result_stats is not None or write_result_stats:
        result = {"stats": {"cost_usd": cost_in_result_stats}}
        (run_dir / "result.json").write_text(json.dumps(result, indent=2))

    return run_dir


def make_trial_dir(run_dir: Path, *, trial_name: str, agent_cost_usd: float | None) -> Path:
    """Create a per-trial subdir under run_dir carrying step_results[].agent_result.cost_usd.

    Mirrors the harbor per-trial result.json shape observed at
    .runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/<job>/<trial>/result.json.
    """
    trial = run_dir / trial_name
    trial.mkdir(parents=True, exist_ok=True)
    body = {"step_results": [{"agent_result": {"cost_usd": agent_cost_usd}}]}
    (trial / "result.json").write_text(json.dumps(body, indent=2))
    return trial
