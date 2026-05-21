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

    Each row is a dict with keys: `dataset`, `query_id`, `rewards: {"reward": float}`,
    and optionally `trial_index` (defaults to a per-(dataset, query_id) running counter).
    Writes `summary.json` AND `per_trial_outcomes.json` (the M6 diff command's input).
    """
    per_query: dict[tuple[str, int], list[float]] = {}
    outcomes: list[dict] = []
    counter: dict[tuple[str, int], int] = {}
    for row in rows:
        ds = row["dataset"]
        qid = int(row["query_id"])
        reward = float(row["rewards"]["reward"])
        per_query.setdefault((ds, qid), []).append(reward)
        ti = int(row["trial_index"]) if "trial_index" in row else counter.get((ds, qid), 0)
        counter[(ds, qid)] = ti + 1
        outcomes.append(
            {"dataset": ds, "query_id": qid, "trial_index": ti, "reward": reward}
        )

    summary = _build_summary(per_query)
    Path(out_path).write_text(json.dumps(summary, indent=2) + "\n")
    sidecar = Path(out_path).parent / "per_trial_outcomes.json"
    sidecar.write_text(
        json.dumps({"outcomes_version": 1, "trials": outcomes}, indent=2) + "\n"
    )


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
    trial_name_map: dict[str, tuple[str, int] | tuple[str, list[int]]],
    out_path: Path,
) -> None:
    """Aggregate a real harbor JobResult.trial_results sequence.

    `trial_name_map` is built by the spec → JobConfig translator. Each trial_result
    must expose `.trial_name: str` and `.verifier_result.rewards: dict | None`.

    Per §6.5 the aggregator never reads `JobResult.stats` (AC-5). The mapping pairs
    each trial back to its (dataset, query_ids) by exact `trial_name → key` lookup.

    Two key shapes are supported:
      - per-query — value is ``(dataset, query_id: int)``. One outcome per trial.
      - batch    — value is ``(dataset, query_ids: list[int])``. One outcome per
        query_id, drawn from the trial's ``reward_per_query.json`` sidecar at
        ``<trial_dir>/steps/main/verifier/reward_per_query.json`` (or
        ``<trial_dir>/verifier/reward_per_query.json`` for single-step trials).
    """
    per_query: dict[tuple[str, int], list[float]] = {}
    outcomes: list[dict] = []
    counter: dict[tuple[str, int], int] = {}
    for tr in trial_results:
        key = _resolve_key(tr.trial_name, trial_name_map)
        if key is None:
            continue
        dataset, qid_or_list = key
        if isinstance(qid_or_list, list):
            per_query_rewards = _load_per_query_rewards(
                tr, query_ids=qid_or_list,
            )
            for qid in qid_or_list:
                reward = per_query_rewards.get(qid, 0.0)
                sub_key = (dataset, qid)
                per_query.setdefault(sub_key, []).append(reward)
                ti = counter.get(sub_key, 0)
                counter[sub_key] = ti + 1
                outcomes.append(
                    {
                        "dataset": dataset,
                        "query_id": qid,
                        "trial_index": ti,
                        "trial_name": tr.trial_name,
                        "reward": reward,
                    }
                )
            continue
        reward = 0.0
        if tr.verifier_result is not None and tr.verifier_result.rewards:
            reward = float(tr.verifier_result.rewards.get("reward", 0.0))
        sub_key = (dataset, qid_or_list)
        per_query.setdefault(sub_key, []).append(reward)
        ti = counter.get(sub_key, 0)
        counter[sub_key] = ti + 1
        outcomes.append(
            {
                "dataset": dataset,
                "query_id": qid_or_list,
                "trial_index": ti,
                "trial_name": tr.trial_name,
                "reward": reward,
            }
        )

    summary = _build_summary(per_query)
    Path(out_path).write_text(json.dumps(summary, indent=2) + "\n")
    sidecar = Path(out_path).parent / "per_trial_outcomes.json"
    sidecar.write_text(
        json.dumps({"outcomes_version": 1, "trials": outcomes}, indent=2) + "\n"
    )


def _resolve_key(
    trial_name: str,
    trial_name_map: dict[str, tuple[str, int] | tuple[str, list[int]]],
) -> tuple[str, int] | tuple[str, list[int]] | None:
    prefix = trial_name.split("__", 1)[0]
    return trial_name_map.get(prefix)


def _load_per_query_rewards(trial, *, query_ids: list[int]) -> dict[int, float]:
    """Read a batch trial's `reward_per_query.json` sidecar.

    Returns a {query_id: reward} dict. Missing file / unparseable file yields
    an empty dict so the caller defaults to 0.0 per declared query_id. The
    sidecar is written by verify_batch.py under the verifier dir; multi-step
    trials emit it under steps/main/verifier/, single-step trials under
    verifier/.
    """
    trial_uri = getattr(trial, "trial_uri", None) or ""
    if not trial_uri.startswith("file://"):
        return {}
    trial_dir = Path(trial_uri[len("file://"):])
    candidates = [
        trial_dir / "steps" / "main" / "verifier" / "reward_per_query.json",
        trial_dir / "verifier" / "reward_per_query.json",
    ]
    payload: dict | None = None
    for candidate in candidates:
        if candidate.exists():
            try:
                payload = json.loads(candidate.read_text())
            except json.JSONDecodeError:
                payload = None
            break
    if not isinstance(payload, dict):
        return {}
    out: dict[int, float] = {}
    for qid in query_ids:
        entry = payload.get(f"q{qid}")
        if isinstance(entry, dict) and "reward" in entry:
            try:
                out[qid] = float(entry["reward"])
            except (TypeError, ValueError):
                continue
    return out
