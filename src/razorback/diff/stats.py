# ABOUTME: Paired statistics for `rk runs diff` (§6.5).
# ABOUTME: wilson_ci, exact_mcnemar_p, paired_bootstrap_ci, power_mde_at_fixed_n.

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

import numpy as np


def paired_bootstrap_ci(
    outcomes_a: Sequence[dict],
    outcomes_b: Sequence[dict],
    *,
    alpha: float,
    B: int,
    seed: int,
) -> tuple[float, float]:
    """Percentile-method paired bootstrap CI on the stratified pass@1 delta (§6.5).

    Each outcome row is `{"dataset": str, "query_id": int, "trial_index": int, "reward": float}`.
    Arms A and B must share (dataset, query_id, trial_index) keys; pairing is by that triple.
    A reward >= 1.0 counts as a success.

    The bootstrap resamples paired (dataset, query_id, trial_index) keys with replacement
    B times. For each resample, recompute stratified pass@1 for A and B (cross-dataset
    macro-average of per-dataset means of per-query pass@1), take Delta = B - A, and record.
    The CI is (alpha/2, 1 - alpha/2) percentiles of the B-length Delta distribution.

    Cite: §6.5 verbatim "a paired bootstrap CI on the stratified delta
    (B=`--bootstrap-iters`, default 10000, percentile method)".
    """
    pair_index = _build_pair_index(outcomes_a, outcomes_b)
    keys = sorted(pair_index.keys())
    n = len(keys)
    if n == 0:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    deltas = np.empty(B, dtype=np.float64)
    keys_arr = np.array(keys, dtype=object)
    for i in range(B):
        idx = rng.integers(0, n, size=n)
        resampled = [keys_arr[j] for j in idx]
        deltas[i] = _stratified_delta(resampled, pair_index)
    lo = float(np.quantile(deltas, alpha / 2))
    hi = float(np.quantile(deltas, 1 - alpha / 2))
    return lo, hi


def _build_pair_index(
    outcomes_a: Sequence[dict],
    outcomes_b: Sequence[dict],
) -> dict[tuple[str, int, int], tuple[float, float]]:
    a_map = {
        (r["dataset"], int(r["query_id"]), int(r["trial_index"])): float(r["reward"])
        for r in outcomes_a
    }
    b_map = {
        (r["dataset"], int(r["query_id"]), int(r["trial_index"])): float(r["reward"])
        for r in outcomes_b
    }
    if set(a_map.keys()) != set(b_map.keys()):
        a_only = sorted(set(a_map) - set(b_map))[:3]
        b_only = sorted(set(b_map) - set(a_map))[:3]
        raise ValueError(
            "paired bootstrap requires identical (dataset, query_id, trial_index) keys "
            f"across arms; A-only: {a_only}; B-only: {b_only}"
        )
    return {k: (a_map[k], b_map[k]) for k in a_map}


def _stratified_delta(
    keys: list,
    pair_index: dict[tuple[str, int, int], tuple[float, float]],
) -> float:
    """Compute stratified pass@1 for both arms over the given (resampled) keys; return B - A."""
    by_ds_q_a: dict[tuple[str, int], list[float]] = defaultdict(list)
    by_ds_q_b: dict[tuple[str, int], list[float]] = defaultdict(list)
    for k in keys:
        # numpy object arrays return numpy scalars; coerce to a hashable native triple.
        key = (str(k[0]), int(k[1]), int(k[2]))
        a_r, b_r = pair_index[key]
        ds = key[0]
        qid = key[1]
        by_ds_q_a[(ds, qid)].append(1.0 if a_r >= 1.0 else 0.0)
        by_ds_q_b[(ds, qid)].append(1.0 if b_r >= 1.0 else 0.0)

    def stratified(by_ds_q: dict[tuple[str, int], list[float]]) -> float:
        per_ds: dict[str, list[float]] = defaultdict(list)
        for (ds, _qid), rewards in by_ds_q.items():
            per_ds[ds].append(sum(rewards) / len(rewards))
        per_ds_means = [sum(rs) / len(rs) for rs in per_ds.values()]
        return sum(per_ds_means) / len(per_ds_means) if per_ds_means else 0.0

    return stratified(by_ds_q_b) - stratified(by_ds_q_a)
