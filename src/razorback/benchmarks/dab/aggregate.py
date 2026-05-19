# ABOUTME: DAB stratified pass@1 aggregator (§6.5).
# ABOUTME: Reads typed per-trial records; writes per-query / per-dataset / stratified summary.json.

import json
from math import comb
from pathlib import Path
from typing import Iterable

SUMMARY_VERSION = 1


def pass_at_k(*, n: int, c: int, k: int) -> float:
    """Verbatim DAB pass@k.

    Mirrors /Users/clkao/git/dataagentbench/data/common_scaffold/validate/pass_k.py.
    For k=1 this reduces to c/n; the general formula is kept so M5 can add pass@k>1
    without changing the code path.
    """
    if c == 0:
        return 0.0
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def aggregate_synthetic(rows: list[dict], out_path: Path) -> None:
    """Aggregate hand-written fixture rows.

    Each row is a dict with keys: `dataset`, `query_id`, `rewards: {"reward": float}`.
    Used by the AC-1 unit test before the harbor translator landing in Task 7.
    """
    per_query: dict[tuple[str, int], list[float]] = {}
    for row in rows:
        ds = row["dataset"]
        qid = int(row["query_id"])
        reward = float(row["rewards"]["reward"])
        per_query.setdefault((ds, qid), []).append(reward)

    summary = _build_summary(per_query)
    Path(out_path).write_text(json.dumps(summary, indent=2) + "\n")


def _build_summary(per_query: dict[tuple[str, int], list[float]]) -> dict:
    datasets: dict[str, dict] = {}
    for (ds, qid), rewards in per_query.items():
        n = len(rewards)
        c = sum(1 for r in rewards if r >= 1.0)
        entry = datasets.setdefault(ds, {"dataset_pass_at_1": 0.0, "n_queries": 0, "queries": []})
        entry["queries"].append({
            "query_id": qid,
            "n_trials": n,
            "n_correct": c,
            "pass_at_1": pass_at_k(n=n, c=c, k=1),
        })
    for ds, entry in datasets.items():
        entry["queries"].sort(key=lambda q: q["query_id"])
        entry["n_queries"] = len(entry["queries"])
        entry["dataset_pass_at_1"] = sum(q["pass_at_1"] for q in entry["queries"]) / entry["n_queries"]
    stratified = (
        sum(ds["dataset_pass_at_1"] for ds in datasets.values()) / len(datasets)
        if datasets
        else 0.0
    )
    return {
        "summary_version": SUMMARY_VERSION,
        "stratified_pass_at_1": stratified,
        "datasets": dict(sorted(datasets.items())),
    }


def aggregate_job_result(
    trial_results: Iterable,
    trial_name_map: dict[str, tuple[str, int]],
    out_path: Path,
) -> None:
    """Aggregate a real harbor JobResult.trial_results sequence.

    `trial_name_map` is built by the spec → JobConfig translator. Each trial_result
    must expose `.trial_name: str` and `.verifier_result.rewards: dict | None`.

    Per §6.5 the aggregator never reads `JobResult.stats` (AC-5). The mapping pairs
    each trial back to its (dataset, query_id) by exact `trial_name → key` lookup.
    """
    per_query: dict[tuple[str, int], list[float]] = {}
    for tr in trial_results:
        key = _resolve_key(tr.trial_name, trial_name_map)
        if key is None:
            continue
        reward = 0.0
        if tr.verifier_result is not None and tr.verifier_result.rewards:
            reward = float(tr.verifier_result.rewards.get("reward", 0.0))
        per_query.setdefault(key, []).append(reward)

    summary = _build_summary(per_query)
    Path(out_path).write_text(json.dumps(summary, indent=2) + "\n")


def _resolve_key(
    trial_name: str,
    trial_name_map: dict[str, tuple[str, int]],
) -> tuple[str, int] | None:
    prefix = trial_name.split("__", 1)[0]
    return trial_name_map.get(prefix)
