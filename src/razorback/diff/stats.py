# ABOUTME: Paired statistics for `rk runs diff` (§6.5).
# ABOUTME: wilson_ci, exact_mcnemar_p, paired_bootstrap_ci, power_mde_at_fixed_n.

from __future__ import annotations

import math
from collections import defaultdict
from typing import Sequence

import numpy as np
from scipy.stats import binomtest, norm


def wilson_ci(*, k: int, n: int, alpha: float) -> tuple[float, float]:
    """Wilson 1927 score interval for a binomial proportion at level 1 - alpha.

      z = phi^{-1}(1 - alpha/2)
      p_hat = k / n
      center = (p_hat + z^2/(2n)) / (1 + z^2/n)
      half = (z / (1 + z^2/n)) * sqrt(p_hat(1-p_hat)/n + z^2/(4n^2))
      ci = (max(0, center - half), min(1, center + half))

    Cite: Wilson, E. B. (1927). "Probable inference, the law of succession, and
    statistical inference." JASA.
    """
    if n == 0:
        return (0.0, 1.0)
    z = float(norm.ppf(1 - alpha / 2))
    p_hat = k / n
    denom = 1 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def exact_mcnemar_p(*, b: int, c: int) -> float:
    """Exact-binomial McNemar p-value (two-sided).

    Under H0 (no treatment effect) each discordant pair is equally likely to favor
    either arm. We use scipy.stats.binomtest at p=0.5; this is the same computation
    as scipy.stats.contingency.mcnemar(exact=True) with a stable API across scipy 1.x.

    For b = c = 0 (perfect agreement) we return 1.0 by convention.

    Cite: McNemar (1947); design §6.5 ("using exact binomial when the discordant count
    is small (the common case at the DAB N=5 local default)").
    """
    if b + c == 0:
        return 1.0
    return float(
        binomtest(k=min(b, c), n=b + c, p=0.5, alternative="two-sided").pvalue
    )


def power_mde_at_fixed_n(
    *,
    alpha: float,
    power: float,
    baseline_p: float,
    n: int,
) -> float:
    """Closed-form normal-approximation minimum detectable effect for a one-sample proportion.

      z_{alpha/2} = phi^{-1}(1 - alpha/2)
      z_{beta}    = phi^{-1}(power)
      se          = sqrt(p_0(1-p_0)/n)
      MDE         = (z_{alpha/2} + z_{beta}) * se

    Cite: §6.5 "a power-at-fixed-N line that names the minimum detectable effect
    at alpha and 80% power for the given `$trials * $queries`." We use the
    closed-form normal-approximation MDE treating N as trials * queries (the total
    paired trials). This is a CONSERVATIVE bound — pairing increases effective
    sample size when correlation > 0, so the bootstrap CI captures the tighter
    paired-test signal. The closed-form MDE here is the upper bound the operator
    quotes alongside the bootstrap CI.

    Cohen, J. (1988). "Statistical Power Analysis for the Behavioral Sciences."
    """
    if n <= 0:
        return 0.0
    z_alpha = float(norm.ppf(1 - alpha / 2))
    z_beta = float(norm.ppf(power))
    se = math.sqrt(baseline_p * (1 - baseline_p) / n)
    return (z_alpha + z_beta) * se


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
