# ABOUTME: Compose paired stats into the JSON shape `rk runs diff` emits (§6.5).
# ABOUTME: Wilson CI per (query, arm); exact-McNemar per query; bootstrap on stratified delta; power MDE.

from collections import defaultdict
from typing import Sequence

from razorback.diff.pairing import pair_outcomes
from razorback.diff.stats import (
    exact_mcnemar_p,
    paired_bootstrap_ci,
    power_mde_at_fixed_n,
    wilson_ci,
)

DIFF_VERSION = 1


def compute_diff(
    outcomes_a: Sequence[dict],
    outcomes_b: Sequence[dict],
    *,
    alpha: float,
    bootstrap_iters: int,
    seed: int = 0,
) -> dict:
    """Compose Wilson CI per (query, arm), exact-McNemar per query, paired bootstrap CI on
    stratified delta, and power-at-fixed-N MDE into one JSON dict.

    Cite: §6.5 verbatim — "The JSON output carries: per-arm per-query Wilson 95% CI on pass@1
    (level set by `--alpha`); per-query exact-McNemar p, using exact binomial when the
    discordant count is small ... a paired bootstrap CI on the stratified delta ... and a
    power-at-fixed-N line."
    """
    paired = pair_outcomes(list(outcomes_a), list(outcomes_b))
    by_q: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in paired:
        by_q[(r["dataset"], r["query_id"])].append(r)

    wilson_rows: list[dict] = []
    mcnemar_rows: list[dict] = []
    for (ds, qid), rows in sorted(by_q.items()):
        n = len(rows)
        a_k = sum(1 for r in rows if r["a_reward"] >= 1.0)
        b_k = sum(1 for r in rows if r["b_reward"] >= 1.0)
        a_lo, a_hi = wilson_ci(k=a_k, n=n, alpha=alpha)
        b_lo, b_hi = wilson_ci(k=b_k, n=n, alpha=alpha)
        wilson_rows.append(
            {
                "dataset": ds,
                "query_id": qid,
                "a": {
                    "k": a_k,
                    "n": n,
                    "pass_at_1": a_k / n,
                    "wilson_lo": a_lo,
                    "wilson_hi": a_hi,
                },
                "b": {
                    "k": b_k,
                    "n": n,
                    "pass_at_1": b_k / n,
                    "wilson_lo": b_lo,
                    "wilson_hi": b_hi,
                },
            }
        )
        # b_only = A fails, B passes; c_only = A passes, B fails.
        b_only = sum(
            1 for r in rows if r["a_reward"] < 1.0 and r["b_reward"] >= 1.0
        )
        c_only = sum(
            1 for r in rows if r["a_reward"] >= 1.0 and r["b_reward"] < 1.0
        )
        mcnemar_rows.append(
            {
                "dataset": ds,
                "query_id": qid,
                "b_only": b_only,
                "c_only": c_only,
                "p": exact_mcnemar_p(b=b_only, c=c_only),
            }
        )

    a_strat = _stratified_from_outcomes(outcomes_a)
    b_strat = _stratified_from_outcomes(outcomes_b)
    delta = b_strat - a_strat
    boot_lo, boot_hi = paired_bootstrap_ci(
        outcomes_a, outcomes_b, alpha=alpha, B=bootstrap_iters, seed=seed,
    )

    n_total = len(paired)
    mde = power_mde_at_fixed_n(alpha=alpha, power=0.80, baseline_p=a_strat, n=n_total)

    return {
        "diff_version": DIFF_VERSION,
        "alpha": alpha,
        "bootstrap_iters": bootstrap_iters,
        "per_arm_stratified_pass_at_1": {"a": a_strat, "b": b_strat},
        "stratified_delta": delta,
        "stratified_delta_ci": {"lo": boot_lo, "hi": boot_hi},
        "per_arm_wilson_ci_by_query": wilson_rows,
        "exact_mcnemar_p_by_query": mcnemar_rows,
        "power_mde": {
            "alpha": alpha,
            "power": 0.80,
            "baseline_p": a_strat,
            "n": n_total,
            "mde": mde,
        },
    }


def _stratified_from_outcomes(outcomes: Sequence[dict]) -> float:
    by_ds_q: dict[tuple[str, int], list[float]] = defaultdict(list)
    for r in outcomes:
        by_ds_q[(r["dataset"], int(r["query_id"]))].append(float(r["reward"]))
    per_ds: dict[str, list[float]] = defaultdict(list)
    for (ds, _qid), rewards in by_ds_q.items():
        passes = sum(1 for x in rewards if x >= 1.0) / len(rewards)
        per_ds[ds].append(passes)
    per_ds_means = [sum(v) / len(v) for v in per_ds.values()]
    return sum(per_ds_means) / len(per_ds_means) if per_ds_means else 0.0
