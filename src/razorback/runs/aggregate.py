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


SUMMARY_VERSION = 1

_NON_TRIAL_TOP_LEVEL = {
    "manifest.json",
    "summary.json",
    "per_trial_outcomes.json",
    "events.jsonl",
    "result.json",
    "lock.json",
    "config.json",
    "job.log",
    "spec.frozen.yaml",
    "spec.frozen.prior.yaml",
    "provenance.yaml",
    "_job_config.yaml",
    "tasks",
    ".harbor-home",
    "crash.json",
}


def _iter_trial_dirs(run_dir: Path) -> list[Path]:
    """Trial dirs are sibling subdirs of run_dir, excluding scaffolding."""
    out: list[Path] = []
    for child in sorted(run_dir.iterdir()):
        if not child.is_dir() or child.name in _NON_TRIAL_TOP_LEVEL:
            continue
        if not (child / "result.json").exists():
            continue
        out.append(child)
    return out


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _resolve_stratum(trial_dir: Path) -> dict | None:
    """Reuse the same precedence rk score/load.py:110-146 walks."""
    candidates = [
        trial_dir / "agent" / "stratum.json",
        trial_dir / "logs" / "verifier" / "stratum.json",
    ]
    steps_root = trial_dir / "steps"
    if steps_root.is_dir():
        for step_dir in sorted(steps_root.iterdir()):
            candidates.append(step_dir / "verifier" / "stratum.json")
    for candidate in candidates:
        payload = _read_json(candidate)
        if payload is not None:
            return payload.get("stratum")
    return None


def _trial_cost(trial_dir: Path) -> float | None:
    """Sum per-step agent_result.cost_usd; mirror runs/cost.py:58-78."""
    result = _read_json(trial_dir / "result.json") or {}
    steps = result.get("step_results")
    if not isinstance(steps, list):
        return None
    costs: list[float] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        agent = step.get("agent_result")
        if not isinstance(agent, dict):
            continue
        value = agent.get("cost_usd")
        if value is not None:
            costs.append(float(value))
    return sum(costs) if costs else None


def _read_trial(trial_dir: Path) -> dict:
    """Extract one trial's row for summary.json + per_trial_outcomes.json."""
    result = _read_json(trial_dir / "result.json") or {}
    exception_info = result.get("exception_info")
    verifier = result.get("verifier_result")
    stratum = _resolve_stratum(trial_dir) or {}

    if exception_info is not None:
        return {
            "trial_id": trial_dir.name,
            "reward": None,
            "cost_usd": None,
            "wall_seconds": None,
            "error_reason": exception_info.get("exception_type"),
            "stratum": stratum,
        }

    reward = None
    if verifier is not None:
        rewards = verifier.get("rewards") or {}
        if "reward" in rewards:
            reward = float(rewards["reward"])
        elif rewards:
            reward = float(next(iter(rewards.values())))

    return {
        "trial_id": trial_dir.name,
        "reward": reward,
        "cost_usd": _trial_cost(trial_dir),
        "wall_seconds": None,
        "error_reason": None,
        "stratum": stratum,
    }


def _stratified_pass_at_1(trials: list[dict]) -> tuple[dict, float | None]:
    """Group completed trials by stratum.dataset; pass@1 = mean over datasets of dataset mean.

    Mirrors benchmarks/dab/aggregate.py:_build_summary. Returns
    (datasets_block, stratified_pass_at_1_or_None).
    """
    completed = [t for t in trials if t["error_reason"] is None and t["reward"] is not None]
    if not completed:
        return ({}, None)

    by_ds_q: dict[tuple[str, int | None], list[float]] = {}
    for t in completed:
        ds = (t["stratum"] or {}).get("dataset", "default")
        qid = (t["stratum"] or {}).get("query_id")
        by_ds_q.setdefault((str(ds), qid), []).append(float(t["reward"]))

    datasets: dict[str, dict] = {}
    for (ds, qid), rewards in by_ds_q.items():
        n = len(rewards)
        c = sum(1 for r in rewards if r >= 1.0)
        entry = datasets.setdefault(ds, {"dataset_pass_at_1": 0.0, "n_queries": 0, "queries": []})
        entry["queries"].append(
            {"query_id": qid, "n_trials": n, "n_correct": c, "pass_at_1": (c / n) if n else 0.0}
        )
    for ds, entry in datasets.items():
        entry["queries"].sort(key=lambda q: (q["query_id"] is None, q["query_id"]))
        entry["n_queries"] = len(entry["queries"])
        entry["dataset_pass_at_1"] = sum(q["pass_at_1"] for q in entry["queries"]) / entry["n_queries"]

    stratified = sum(d["dataset_pass_at_1"] for d in datasets.values()) / len(datasets)
    return (dict(sorted(datasets.items())), stratified)


def _job_cost_usd(run_dir: Path) -> float | None:
    """Harbor's job-level cost; falls back to per-trial sum."""
    result = _read_json(run_dir / "result.json") or {}
    stats = result.get("stats") or {}
    value = stats.get("cost_usd")
    if value is not None:
        return float(value)
    totals: list[float] = []
    for child in _iter_trial_dirs(run_dir):
        c = _trial_cost(child)
        if c is not None:
            totals.append(c)
    return sum(totals) if totals else None


def aggregate_summary(run_dir: Path) -> None:
    """AC-2: write <run_dir>/summary.json with per-trial rows + stratified pass@1."""
    trials = [_read_trial(td) for td in _iter_trial_dirs(run_dir)]
    n_total = len(trials)
    n_errored = sum(1 for t in trials if t["error_reason"] is not None)
    n_completed = n_total - n_errored

    datasets, stratified = _stratified_pass_at_1(trials)

    summary = {
        "summary_version": SUMMARY_VERSION,
        "n_trials_total": n_total,
        "n_trials_completed": n_completed,
        "n_trials_errored": n_errored,
        "stratified_pass_at_1": stratified,
        "datasets": datasets,
        "trials": [
            {
                "trial_id": t["trial_id"],
                "reward": t["reward"],
                "cost_usd": t["cost_usd"],
                "wall_seconds": t["wall_seconds"],
                "error_reason": t["error_reason"],
            }
            for t in trials
        ],
        "cost_usd": _job_cost_usd(run_dir),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
