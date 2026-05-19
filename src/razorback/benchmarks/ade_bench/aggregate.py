# ABOUTME: ade-bench summary aggregator — mean reward across trials → summary.json (§M7 AC-3).
# ABOUTME: Shape is strictly minimal: score, n_trials, n_correct, benchmark_kind, summary_version.

import json
from pathlib import Path
from typing import Iterable

SUMMARY_VERSION = 1


def aggregate_synthetic(rows: list[dict], out_path: Path) -> None:
    """Aggregate hand-written fixture rows. Each row: {task_name, reward: float | None}."""
    rewards = [
        float(r["reward"]) if r.get("reward") is not None else 0.0 for r in rows
    ]
    _write_summary(rewards, out_path)


def aggregate_job_result(
    trial_results: Iterable,
    out_path: Path,
) -> None:
    """Aggregate a real harbor JobResult.trial_results sequence into ade-bench summary.json.

    Each trial_result must expose `.verifier_result.rewards: dict | None`. Missing
    verifier_result yields reward=0.0 (parity with DAB §6.5 retry=0 behavior).
    """
    rewards: list[float] = []
    for tr in trial_results:
        reward = 0.0
        verifier = getattr(tr, "verifier_result", None)
        if verifier is not None:
            rewards_dict = getattr(verifier, "rewards", None) or {}
            reward = float(rewards_dict.get("reward", 0.0))
        rewards.append(reward)
    _write_summary(rewards, out_path)


def _write_summary(rewards: list[float], out_path: Path) -> None:
    n_trials = len(rewards)
    n_correct = sum(1 for r in rewards if r >= 1.0)
    score = (sum(rewards) / n_trials) if n_trials > 0 else 0.0
    summary = {
        "summary_version": SUMMARY_VERSION,
        "benchmark_kind": "ade-bench",
        "score": score,
        "n_trials": n_trials,
        "n_correct": n_correct,
    }
    Path(out_path).write_text(json.dumps(summary, indent=2) + "\n")
