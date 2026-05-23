# ABOUTME: PKG-17 post-harbor aggregator. Writes manifest/summary/events/per_trial_outcomes.
# ABOUTME: Reads run-dir filesystem state; no JobResult dependency (harbor runs as subprocess).

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from razorback.diff.stats import wilson_ci

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
    """Reuse the same precedence rk score/load.py:110-146 walks.

    Falls back to parsing the trial dir name (e.g. `bookreview-q1__a` →
    {dataset: bookreview, query_id: 1}) so DAB trials without per-trial
    stratum.json sidecars (e.g. nop agent runs) still aggregate cleanly.
    """
    manifest_stratum = _resolve_stratum_from_task_view_manifest(trial_dir)
    if manifest_stratum is not None:
        return manifest_stratum

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
    return _parse_stratum_from_trial_name(trial_dir.name)


def _resolve_stratum_from_task_view_manifest(trial_dir: Path) -> dict | None:
    run_dir = trial_dir.parent
    views_root = run_dir / "_razorback" / "task_views"
    if not views_root.is_dir():
        return None

    trial_prefix = trial_dir.name.split("__", 1)[0]
    for manifest_path in sorted(views_root.glob("*/view_manifest.json")):
        payload = _read_json(manifest_path)
        if payload is None:
            continue
        view_name = manifest_path.parent.name[:32].rstrip("_-")
        if trial_prefix != view_name:
            continue
        benchmark_kind = payload.get("benchmark_kind")
        benchmark_task_id = payload.get("benchmark_task_id")
        if not benchmark_kind or not benchmark_task_id:
            return None
        return {
            "dataset": str(benchmark_kind),
            "query_id": str(benchmark_task_id),
            "benchmark_kind": str(benchmark_kind),
            "benchmark_task_id": str(benchmark_task_id),
        }
    return None


def _parse_stratum_from_trial_name(trial_name: str) -> dict | None:
    """Recover (dataset, query_id) from `<dataset>-q<n>__<suffix>` naming."""
    head = trial_name.split("__", 1)[0]
    if "-q" not in head:
        return None
    dataset, _, qpart = head.rpartition("-q")
    if not dataset or not qpart:
        return None
    try:
        return {"dataset": dataset, "query_id": int(qpart)}
    except ValueError:
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


class QueryCell(TypedDict):
    query_id: str | int | float | bool | None
    n_trials: int
    n_correct: int
    pass_at_1: float
    wilson_ci: tuple[float, float] | None


class DatasetStratum(TypedDict):
    dataset: str
    n_queries: int
    dataset_pass_at_1: float
    queries: list[QueryCell]
    wilson_ci: None


class StratifiedReport(TypedDict):
    score_version: int
    alpha: float
    strata: dict[str, DatasetStratum]
    stratified_pass_at_1: float | None
    n_trials_total: int
    n_trials_completed: int
    n_trials_errored: int
    error_reason: str | None


class TrialOutcome(TypedDict):
    trial_id: str
    reward: float | None
    cost_usd: float | None
    wall_seconds: float | None
    error_reason: str | None
    stratum: dict[str, Any]


def read_trial_outcomes(run_dir: Path) -> list[TrialOutcome]:
    """Walk run_dir's trial subdirs and return one outcome row per trial.

    Filesystem-state-driven mirror of the per-trial information aggregate_summary
    consumes. Used by `rk score` to delegate scoring to the same reducer the
    post-harbor aggregator writes into summary.json.
    """
    return [_read_trial(td) for td in _iter_trial_dirs(run_dir)]


SCORE_REPORT_VERSION = 1


def reduce_per_query_stratified(
    outcomes: list[TrialOutcome], *, alpha: float = 0.05
) -> StratifiedReport:
    """Per-query stratified pass@1 with per-query Wilson CIs.

    Single source of truth for both summary.json's `stratified_pass_at_1`
    and `rk score`'s headline number. Each (dataset, query_id) cell is a
    binomial proportion (k=#trials with reward>=1.0, n=trials), and the
    Wilson CI attaches at the cell level only. The dataset stratum is the
    mean of per-query proportions — that is not a binomial, so its
    `wilson_ci` is always `null`.
    """
    n_trials_total = len(outcomes)
    completed = [t for t in outcomes if t["error_reason"] is None and t["reward"] is not None]
    n_trials_completed = len(completed)
    n_trials_errored = n_trials_total - n_trials_completed

    if not completed:
        return StratifiedReport(
            score_version=SCORE_REPORT_VERSION,
            alpha=alpha,
            strata={},
            stratified_pass_at_1=None,
            n_trials_total=n_trials_total,
            n_trials_completed=0,
            n_trials_errored=n_trials_errored,
            error_reason=_dominant_error_reason(outcomes) if outcomes else None,
        )

    by_ds_q: dict[tuple[str, Any], list[float]] = {}
    for t in completed:
        ds = (t["stratum"] or {}).get("dataset", "default")
        qid = (t["stratum"] or {}).get("query_id")
        by_ds_q.setdefault((str(ds), qid), []).append(float(t["reward"]))

    strata: dict[str, DatasetStratum] = {}
    for (ds, qid), rewards in by_ds_q.items():
        n = len(rewards)
        c = sum(1 for r in rewards if r >= 1.0)
        cell: QueryCell = {
            "query_id": qid,
            "n_trials": n,
            "n_correct": c,
            "pass_at_1": (c / n) if n else 0.0,
            "wilson_ci": wilson_ci(k=c, n=n, alpha=alpha) if n else None,
        }
        entry = strata.setdefault(
            ds,
            {"dataset": ds, "n_queries": 0, "dataset_pass_at_1": 0.0, "queries": [], "wilson_ci": None},
        )
        entry["queries"].append(cell)

    for entry in strata.values():
        entry["queries"].sort(key=lambda q: (q["query_id"] is None, q["query_id"]))
        entry["n_queries"] = len(entry["queries"])
        entry["dataset_pass_at_1"] = (
            sum(q["pass_at_1"] for q in entry["queries"]) / entry["n_queries"]
        )

    stratified = sum(d["dataset_pass_at_1"] for d in strata.values()) / len(strata)
    return StratifiedReport(
        score_version=SCORE_REPORT_VERSION,
        alpha=alpha,
        strata=dict(sorted(strata.items())),
        stratified_pass_at_1=stratified,
        n_trials_total=n_trials_total,
        n_trials_completed=n_trials_completed,
        n_trials_errored=n_trials_errored,
        error_reason=None,
    )


def _dominant_error_reason(outcomes: list[TrialOutcome]) -> str | None:
    """Most-frequent error_reason among errored trials; ties broken alphabetically."""
    classes = [t["error_reason"] for t in outcomes if t["error_reason"]]
    if not classes:
        return None
    counts = Counter(classes)
    max_count = max(counts.values())
    top = sorted(name for name, count in counts.items() if count == max_count)
    return top[0]


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
                "stratum": t["stratum"],
            }
            for t in trials
        ],
        "cost_usd": _job_cost_usd(run_dir),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def concatenate_events(run_dir: Path) -> None:
    """AC-3: write <run_dir>/events.jsonl, the per-trial concatenation.

    Each line carries `{trial_id, line_offset}` so `rk audit` can correlate a
    finding back to the per-trial events.jsonl. Trials with no per-trial
    events.jsonl contribute nothing (errored-before-publisher trials are valid).
    """
    out_lines: list[str] = []
    for trial_dir in _iter_trial_dirs(run_dir):
        per_trial = trial_dir / "events.jsonl"
        if not per_trial.exists():
            continue
        try:
            text = per_trial.read_text(encoding="utf-8")
        except OSError:
            continue
        for offset, raw in enumerate(text.splitlines()):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                payload = {"raw": stripped}
            payload = {"trial_id": trial_dir.name, "line_offset": offset, **payload}
            out_lines.append(json.dumps(payload))
    top_level = run_dir / "events.jsonl"
    if out_lines:
        top_level.write_text("\n".join(out_lines) + "\n")
    elif not top_level.exists():
        # No per-trial events to merge and no harbor-written top-level events.jsonl:
        # leave a zero-byte placeholder so consumers (rk audit) find the artifact.
        top_level.write_text("")


OUTCOMES_VERSION = 1


def write_per_trial_outcomes(run_dir: Path) -> None:
    """AC-4: write <run_dir>/per_trial_outcomes.json for rk runs diff.

    Errored trials enter the outcomes table with reward=0.0 (parity with
    benchmarks/dab/aggregate.py:104 — `if verifier_result is None: reward = 0.0`).
    rk runs diff is a pairwise comparison and needs every key on both arms.
    """
    counter: dict[tuple[str, int | None], int] = {}
    rows: list[dict] = []
    for trial_dir in _iter_trial_dirs(run_dir):
        info = _read_trial(trial_dir)
        stratum = info.get("stratum") or {}
        dataset = str(stratum.get("dataset", "default"))
        query_id = stratum.get("query_id")
        key = (dataset, query_id)
        idx = counter.get(key, 0)
        counter[key] = idx + 1
        reward = info["reward"] if info["reward"] is not None else 0.0
        rows.append(
            {
                "dataset": dataset,
                "query_id": query_id,
                "benchmark_kind": stratum.get("benchmark_kind"),
                "benchmark_task_id": stratum.get("benchmark_task_id"),
                "trial_index": idx,
                "trial_name": trial_dir.name,
                "reward": float(reward),
            }
        )
    (run_dir / "per_trial_outcomes.json").write_text(
        json.dumps({"outcomes_version": OUTCOMES_VERSION, "trials": rows}, indent=2) + "\n"
    )


def aggregate_run_dir(
    run_dir: Path,
    *,
    spec_path: Path,
    frozen_spec_hash: str,
    provenance_hash: str,
    harbor_job_name: str,
    benchmark_kind: str | None,
) -> None:
    """Single post-harbor entrypoint. Writes the four canonical PKG-17 artifacts.

    Idempotent for summary / events / per_trial_outcomes (deterministic inputs);
    manifest.created_at re-stamps on each call by design.
    """
    trial_dirs = _iter_trial_dirs(run_dir)
    n_total = len(trial_dirs)
    n_errored = 0
    for td in trial_dirs:
        result = _read_json(td / "result.json") or {}
        if result.get("exception_info") is not None or result.get("verifier_result") is None:
            n_errored += 1
    n_completed = n_total - n_errored

    write_manifest(
        run_dir,
        spec_path=spec_path,
        frozen_spec_hash=frozen_spec_hash,
        provenance_hash=provenance_hash,
        harbor_job_name=harbor_job_name,
        n_trials_total=n_total,
        n_trials_completed=n_completed,
        n_trials_errored=n_errored,
        per_trial_paths=sorted(td.name for td in trial_dirs),
        benchmark_kind=benchmark_kind,
    )
    aggregate_summary(run_dir)
    concatenate_events(run_dir)
    write_per_trial_outcomes(run_dir)


def compute_provenance_hash(provenance_path: Path) -> str:
    """sha256 hex digest of provenance.yaml bytes."""
    return hashlib.sha256(provenance_path.read_bytes()).hexdigest()


def safe_aggregate_run_dir(
    run_dir: Path,
    *,
    spec_path: Path,
    frozen_spec_hash: str,
    provenance_hash: str,
    harbor_job_name: str,
    benchmark_kind: str | None,
) -> list[str]:
    """Run aggregate_run_dir; collect warnings instead of raising.

    Harbor's exit code is what the user gates on; the aggregator must not mask
    it with a Python traceback. Returns a list of human-readable warning strings;
    empty list = clean run.
    """
    warnings: list[str] = []
    try:
        aggregate_run_dir(
            run_dir,
            spec_path=spec_path,
            frozen_spec_hash=frozen_spec_hash,
            provenance_hash=provenance_hash,
            harbor_job_name=harbor_job_name,
            benchmark_kind=benchmark_kind,
        )
    except Exception as exc:
        warnings.append(f"aggregate_run_dir failed: {type(exc).__name__}: {exc}")
    return warnings
