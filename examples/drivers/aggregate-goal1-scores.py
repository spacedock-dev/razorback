#!/usr/bin/env python3
# ABOUTME: Goal 1 per-variant aggregator — stratified pass@1 + Wilson CI + against-constant verdict.
# ABOUTME: Reads runs/goal1/matrix/<variant>/<dataset>/.../result.json across the 12 strata.

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from razorback.runs.aggregate import (
    count_trials,
    read_trial_outcomes,
    reduce_per_query_stratified,
)
from razorback_plugin_dab.dataset_def import load_default_definition
from razorback_plugin_dab.generate.workspace_readme import WORKSPACE_VARIANTS

_DEFINITION = load_default_definition()


VARIANT_TARGETS = {
    "spacedock": ("spacedock", 0.577),
    "direct-minimal": ("direct_baseline", 0.4376),
    "direct-structured": ("direct_baseline", 0.4376),
}


def wilson_ci(n_pass: int, n_total: int, alpha: float = 0.05) -> tuple[float, float]:
    if n_total <= 0:
        return (0.0, 1.0)
    p = n_pass / n_total
    z = 1.959963984540054 if abs(alpha - 0.05) < 1e-9 else _z_for_alpha(alpha)
    denom = 1.0 + (z * z) / n_total
    center = (p + (z * z) / (2.0 * n_total)) / denom
    margin = (z / denom) * math.sqrt((p * (1 - p) / n_total) + (z * z) / (4.0 * n_total * n_total))
    return (max(0.0, center - margin), min(1.0, center + margin))


def _z_for_alpha(alpha: float) -> float:
    from statistics import NormalDist
    return NormalDist().inv_cdf(1.0 - alpha / 2.0)


def find_result_json(cell_dir: Path) -> Path | None:
    for rj in sorted(cell_dir.glob("*/*/result.json")):
        return rj
    return None


def extract_cell_stats(result_json: Path) -> dict[str, Any]:
    """Per-cell stats for the goal1 matrix aggregator.

    Binary `n_total`/`n_pass` (cell-level reward >= 1.0) is preserved for audit
    against the cycle-1/cycle-2 archived headlines. `per_query_pass_at_1`,
    `n_query_trials`, `n_query_correct` are the canonical per-query numbers
    from `runs/aggregate.py:reduce_per_query_stratified` — these are what the
    post-1s captain-facing headline reads. Trial counts come from
    `count_trials` so DAB-batch fan-out doesn't double-count the denominator.
    """
    body = json.loads(result_json.read_text())
    stats = body.get("stats") or {}
    evals = stats.get("evals") or {}
    if evals:
        eval_block = next(iter(evals.values()))
        rewards = eval_block.get("reward_stats", {}).get("reward", {})
    else:
        rewards = {}
    n_pass_binary = 0
    n_total_binary = 0
    for reward_value, trial_ids in rewards.items():
        try:
            r = float(reward_value)
        except (TypeError, ValueError):
            continue
        n_total_binary += len(trial_ids)
        if r >= 1.0:
            n_pass_binary += len(trial_ids)

    run_dir = result_json.parent
    outcomes = read_trial_outcomes(run_dir)
    trial_counts = count_trials(run_dir)
    report = reduce_per_query_stratified(outcomes, trial_counts=trial_counts)

    per_query_pass = report["stratified_pass_at_1"]
    n_query_trials = 0
    n_query_correct = 0
    for ds_entry in report["strata"].values():
        for q in ds_entry["queries"]:
            n_query_trials += q["n_trials"]
            n_query_correct += q["n_correct"]

    return {
        "n_total": n_total_binary,
        "n_pass": n_pass_binary,
        "n_errored": stats.get("n_errored_trials", 0),
        "rewards": rewards,
        "result_json": str(result_json),
        "per_query_pass_at_1": per_query_pass,
        "n_query_trials": n_query_trials,
        "n_query_correct": n_query_correct,
        "per_query_strata": report["strata"],
    }


def aggregate_variant(matrix_root: Path, variant: str) -> dict[str, Any]:
    strata: dict[str, dict[str, Any]] = {}
    for ds in _DEFINITION.datasets:
        cell_dir = matrix_root / variant / ds.name
        rj = find_result_json(cell_dir)
        if rj is None:
            strata[ds.name] = {
                "n_total": 0,
                "n_pass": 0,
                "n_errored": 0,
                "pass_at_1": None,
                "wilson_ci": None,
                "error_reason": "no_result_json",
                "result_json": None,
            }
            continue
        s = extract_cell_stats(rj)
        if s["n_total"] == 0:
            strata[ds.name] = {
                **s,
                "pass_at_1": None,
                "wilson_ci": None,
                "error_reason": "no_completed_trials_with_reward",
            }
        else:
            p = s["n_pass"] / s["n_total"]
            ci = wilson_ci(s["n_pass"], s["n_total"])
            strata[ds.name] = {**s, "pass_at_1": p, "wilson_ci": list(ci), "error_reason": None}

    scored_strata = [v for v in strata.values() if v.get("pass_at_1") is not None]
    if scored_strata:
        stratified_mean = sum(v["pass_at_1"] for v in scored_strata) / len(scored_strata)
        total_pass = sum(v["n_pass"] for v in scored_strata)
        total_n = sum(v["n_total"] for v in scored_strata)
        stratified_ci = wilson_ci(total_pass, total_n)
    else:
        stratified_mean = None
        total_pass = 0
        total_n = 0
        stratified_ci = None

    per_query_scored = [
        v for v in scored_strata if v.get("per_query_pass_at_1") is not None
    ]
    if per_query_scored:
        per_query_mean_over_strata = (
            sum(v["per_query_pass_at_1"] for v in per_query_scored)
            / len(per_query_scored)
        )
        pooled_query_correct = sum(v["n_query_correct"] for v in per_query_scored)
        pooled_query_trials = sum(v["n_query_trials"] for v in per_query_scored)
        pooled_per_query_pass_at_1 = (
            pooled_query_correct / pooled_query_trials
            if pooled_query_trials > 0
            else None
        )
        pooled_per_query_ci = (
            wilson_ci(pooled_query_correct, pooled_query_trials)
            if pooled_query_trials > 0
            else None
        )
    else:
        per_query_mean_over_strata = None
        pooled_query_correct = 0
        pooled_query_trials = 0
        pooled_per_query_pass_at_1 = None
        pooled_per_query_ci = None

    target_name, target_value = VARIANT_TARGETS[variant]

    def _verdict(ci: tuple[float, float] | None) -> str:
        if ci is None:
            return "no_data"
        lo, hi = ci
        if lo <= target_value <= hi:
            return "matches"
        if target_value > hi:
            return "below"
        return "above"

    def _verdict_point(mean: float | None, target: float) -> str:
        if mean is None:
            return "no_data"
        if mean == target:
            return "matches"
        return "above" if mean > target else "below"

    verdict = _verdict(stratified_ci)
    per_query_verdict = _verdict(pooled_per_query_ci)
    # Canonical paper-comparison lens. The DAB paper's `paper_baseline` is
    # stratified-per-query (each dataset weighted equally regardless of
    # query count); `per_query_verdict` (pooled) and `verdict` (binary) are
    # supplementary views retained for backward-compat audit against the
    # archived headlines.
    #
    # CI methodology: null. Mean-of-proportions across non-identical-N
    # strata is not binomial; pick a stratified-CI methodology in a later
    # entity if statistical-significance machinery is needed. Bootstrap
    # over 12 cells at N=1 query trial per query is uninformative.
    # Downstream consumers MUST NOT claim statistical significance from
    # `stratified_verdict.ci == null` — verdict is a point comparison.
    stratified_verdict_value = _verdict_point(per_query_mean_over_strata, target_value)

    return {
        "variant": variant,
        "n_strata_scored": len(scored_strata),
        "n_strata_total": len(_DEFINITION.datasets),
        "stratified_pass_at_1_mean_over_strata": stratified_mean,
        "pooled_pass_at_1": (total_pass / total_n) if total_n > 0 else None,
        "pooled_n_pass": total_pass,
        "pooled_n_total": total_n,
        "pooled_wilson_95ci": list(stratified_ci) if stratified_ci else None,
        "per_query_pass_at_1_mean_over_strata": per_query_mean_over_strata,
        "pooled_per_query_pass_at_1": pooled_per_query_pass_at_1,
        "pooled_n_query_correct": pooled_query_correct,
        "pooled_n_query_trials": pooled_query_trials,
        "pooled_per_query_wilson_95ci": (
            list(pooled_per_query_ci) if pooled_per_query_ci else None
        ),
        "against_constant": {
            "stratified_verdict": {
                "value": target_value,
                "stratified_mean": per_query_mean_over_strata,
                "ci": None,
                "verdict": stratified_verdict_value,
            },
            "name": target_name,
            "value": target_value,
            "verdict": verdict,
            "per_query_verdict": per_query_verdict,
        },
        "strata": strata,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--matrix-root",
        default="runs/goal1/matrix",
        help="Root containing <variant>/<dataset>/<experiment>/<hash>/result.json.",
    )
    parser.add_argument(
        "--out-dir",
        default="runs/goal1/matrix",
        help="Where to write per-variant aggregate-score.json and matrix-summary.json.",
    )
    args = parser.parse_args()

    matrix_root = Path(args.matrix_root).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {"variants": {}}
    for variant in WORKSPACE_VARIANTS:
        agg = aggregate_variant(matrix_root, variant)
        variant_out = out_dir / variant / "aggregate-score.json"
        variant_out.parent.mkdir(parents=True, exist_ok=True)
        variant_out.write_text(json.dumps(agg, indent=2, sort_keys=True, default=list))
        summary["variants"][variant] = {
            "n_strata_scored": agg["n_strata_scored"],
            "n_strata_total": agg["n_strata_total"],
            "stratified_mean_over_strata": agg["stratified_pass_at_1_mean_over_strata"],
            "pooled_pass_at_1": agg["pooled_pass_at_1"],
            "pooled_n_pass": agg["pooled_n_pass"],
            "pooled_n_total": agg["pooled_n_total"],
            "pooled_wilson_95ci": agg["pooled_wilson_95ci"],
            "per_query_mean_over_strata": agg["per_query_pass_at_1_mean_over_strata"],
            "pooled_per_query_pass_at_1": agg["pooled_per_query_pass_at_1"],
            "pooled_n_query_correct": agg["pooled_n_query_correct"],
            "pooled_n_query_trials": agg["pooled_n_query_trials"],
            "pooled_per_query_wilson_95ci": agg["pooled_per_query_wilson_95ci"],
            "against_constant": agg["against_constant"],
            "aggregate_json_path": str(variant_out),
        }
        print(
            f"{variant}: scored {agg['n_strata_scored']}/{agg['n_strata_total']} strata; "
            f"pooled_pass@1={agg['pooled_pass_at_1']}; "
            f"pooled_per_query_pass@1={agg['pooled_per_query_pass_at_1']} "
            f"({agg['pooled_n_query_correct']}/{agg['pooled_n_query_trials']}); "
            f"verdict={agg['against_constant']['verdict']}"
        )
    (out_dir / "matrix-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(f"wrote {out_dir / 'matrix-summary.json'}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
