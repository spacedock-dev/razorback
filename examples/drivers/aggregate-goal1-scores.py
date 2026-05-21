#!/usr/bin/env python3
# ABOUTME: Goal 1 per-variant aggregator — stratified pass@1 + Wilson CI + against-constant verdict.
# ABOUTME: Reads runs/goal1/matrix/<variant>/<dataset>/.../result.json across the 12 strata.

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from razorback_plugin_dab.datasets import DAB_DATASETS
from razorback_plugin_dab.generate.workspace_readme import WORKSPACE_VARIANTS


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
    body = json.loads(result_json.read_text())
    stats = body.get("stats") or {}
    evals = stats.get("evals") or {}
    if not evals:
        return {"n_total": 0, "n_pass": 0, "n_errored": 0, "rewards": {}}
    eval_block = next(iter(evals.values()))
    rewards = eval_block.get("reward_stats", {}).get("reward", {})
    n_pass = 0
    n_total = 0
    for reward_value, trial_ids in rewards.items():
        try:
            r = float(reward_value)
        except (TypeError, ValueError):
            continue
        n_total += len(trial_ids)
        if r >= 1.0:
            n_pass += len(trial_ids)
    return {
        "n_total": n_total,
        "n_pass": n_pass,
        "n_errored": stats.get("n_errored_trials", 0),
        "rewards": rewards,
        "result_json": str(result_json),
    }


def aggregate_variant(matrix_root: Path, variant: str) -> dict[str, Any]:
    strata: dict[str, dict[str, Any]] = {}
    for ds in DAB_DATASETS:
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

    target_name, target_value = VARIANT_TARGETS[variant]
    if stratified_mean is None:
        verdict = "no_data"
    else:
        lo, hi = stratified_ci
        if lo <= target_value <= hi:
            verdict = "matches"
        elif target_value > hi:
            verdict = "below"
        else:
            verdict = "above"

    return {
        "variant": variant,
        "n_strata_scored": len(scored_strata),
        "n_strata_total": len(DAB_DATASETS),
        "stratified_pass_at_1_mean_over_strata": stratified_mean,
        "pooled_pass_at_1": (total_pass / total_n) if total_n > 0 else None,
        "pooled_n_pass": total_pass,
        "pooled_n_total": total_n,
        "pooled_wilson_95ci": list(stratified_ci) if stratified_ci else None,
        "against_constant": {
            "name": target_name,
            "value": target_value,
            "verdict": verdict,
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
        variant_out.write_text(json.dumps(agg, indent=2, sort_keys=True))
        summary["variants"][variant] = {
            "n_strata_scored": agg["n_strata_scored"],
            "n_strata_total": agg["n_strata_total"],
            "stratified_mean_over_strata": agg["stratified_pass_at_1_mean_over_strata"],
            "pooled_pass_at_1": agg["pooled_pass_at_1"],
            "pooled_n_pass": agg["pooled_n_pass"],
            "pooled_n_total": agg["pooled_n_total"],
            "pooled_wilson_95ci": agg["pooled_wilson_95ci"],
            "against_constant": agg["against_constant"],
            "aggregate_json_path": str(variant_out),
        }
        print(f"{variant}: scored {agg['n_strata_scored']}/{agg['n_strata_total']} strata; "
              f"pooled_pass@1={agg['pooled_pass_at_1']}; verdict={agg['against_constant']['verdict']}")
    (out_dir / "matrix-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(f"wrote {out_dir / 'matrix-summary.json'}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
