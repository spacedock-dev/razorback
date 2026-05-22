#!/usr/bin/env python3
# ABOUTME: Post-hoc cost reconstruction for goal1-resume — sums opus-4.7 token usage from
# ABOUTME: per-trial session jsonl since populate_context_post_run path-mismatch leaves cost_usd null.

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


OPUS_4_7_PRICES_PER_M_TOKENS = {
    "input": 15.0,
    "cache_creation": 18.75,
    "cache_read": 1.5,
    "output": 75.0,
}


def reconstruct_trial_cost(trial_dir: Path) -> dict:
    """Walk session jsonl under <trial_dir> and sum usage tokens × opus-4.7 prices."""
    ti = tcr = tcw = to = 0
    n = 0
    for sp in trial_dir.rglob("*.jsonl"):
        for ln in sp.read_text().splitlines():
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            msg = d.get("message") if isinstance(d, dict) else None
            if not isinstance(msg, dict):
                continue
            u = msg.get("usage")
            if not isinstance(u, dict):
                continue
            ti += u.get("input_tokens") or 0
            tcr += u.get("cache_read_input_tokens") or 0
            tcw += u.get("cache_creation_input_tokens") or 0
            to += u.get("output_tokens") or 0
            n += 1
    cost = (
        ti * OPUS_4_7_PRICES_PER_M_TOKENS["input"]
        + tcw * OPUS_4_7_PRICES_PER_M_TOKENS["cache_creation"]
        + tcr * OPUS_4_7_PRICES_PER_M_TOKENS["cache_read"]
        + to * OPUS_4_7_PRICES_PER_M_TOKENS["output"]
    ) / 1_000_000
    return {
        "messages": n,
        "input_tokens": ti,
        "cache_creation_tokens": tcw,
        "cache_read_tokens": tcr,
        "output_tokens": to,
        "cost_usd": round(cost, 4),
    }


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (center - half, center + half)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-root", required=True, help="runs/goal1-resume root path")
    ap.add_argument("--variant", default="spacedock")
    ap.add_argument("--paper-target", type=float, default=0.577)
    args = ap.parse_args()

    root = Path(args.runs_root).expanduser().resolve()
    variant_root = root / args.variant
    if not variant_root.exists():
        print(f"variant root not found: {variant_root}", file=sys.stderr)
        return 1

    per_dataset = {}
    total_cost = 0.0
    total_correct = 0
    total_trials = 0

    for ds_dir in sorted(variant_root.iterdir()):
        if not ds_dir.is_dir():
            continue
        ds = ds_dir.name
        # Find result.json + trial dir
        results = list(ds_dir.glob("*/*/result.json"))
        if not results:
            per_dataset[ds] = {
                "n_trials": 0,
                "n_correct": 0,
                "reward": None,
                "cost_usd": None,
                "note": "no result.json",
            }
            continue
        rj = results[0]
        body = json.loads(rj.read_text())
        stats = body.get("stats") or {}
        evals = stats.get("evals") or {}
        # PKG-26 era: reward via per_trial_outcomes.json
        outcomes_path = rj.parent / "per_trial_outcomes.json"
        rewards = []
        if outcomes_path.exists():
            outcomes = json.loads(outcomes_path.read_text())
            for t in outcomes.get("trials") or []:
                r = t.get("reward")
                if r is not None:
                    rewards.append(float(r))
        # Find trial dir (sibling of result.json with <trial_name> as dir)
        trials_root = rj.parent
        trial_cost = {"cost_usd": None, "messages": 0}
        for sub in trials_root.iterdir():
            if sub.is_dir() and sub.name.startswith(f"{ds}__"):
                trial_cost = reconstruct_trial_cost(sub)
                break
        n_correct = sum(1 for r in rewards if r and r >= 1.0)
        n_trials = len(rewards) if rewards else 0
        reward = n_correct / n_trials if n_trials else None
        per_dataset[ds] = {
            "n_trials": n_trials,
            "n_correct": n_correct,
            "reward": reward,
            **trial_cost,
        }
        if trial_cost.get("cost_usd"):
            total_cost += trial_cost["cost_usd"]
        if n_trials:
            total_correct += n_correct
            total_trials += n_trials

    stratified = total_correct / total_trials if total_trials else None
    wilson_lo, wilson_hi = wilson_ci(total_correct, total_trials)
    verdict = None
    if stratified is not None:
        if wilson_lo <= args.paper_target <= wilson_hi:
            verdict = "PAPER_INSIDE_CI"
        elif stratified > wilson_hi:
            verdict = "ABOVE_CI (better than paper)"
        elif stratified < wilson_lo:
            verdict = "BELOW_CI (worse than paper)"

    report = {
        "variant": args.variant,
        "n_datasets": len(per_dataset),
        "n_trials_total": total_trials,
        "n_correct_total": total_correct,
        "stratified_pass_at_1": round(stratified, 4) if stratified is not None else None,
        "wilson_95_ci": [round(wilson_lo, 4), round(wilson_hi, 4)],
        "paper_target": args.paper_target,
        "verdict_vs_paper": verdict,
        "total_cost_usd_reconstructed": round(total_cost, 4),
        "per_dataset": per_dataset,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
