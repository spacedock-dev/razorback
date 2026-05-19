# ABOUTME: Pair two run-dirs' per_trial_outcomes by (dataset, query_id, trial_index).
# ABOUTME: §6.5 stable-pairing surface; the diff command's structural pre-stat step.

import json
from pathlib import Path


def load_run_outcomes(run_dir: Path) -> list[dict]:
    """Read `<run_dir>/per_trial_outcomes.json` and return the trials list."""
    path = Path(run_dir) / "per_trial_outcomes.json"
    payload = json.loads(path.read_text())
    if payload.get("outcomes_version") != 1:
        raise ValueError(
            f"unsupported outcomes_version: {payload.get('outcomes_version')}"
        )
    return list(payload["trials"])


def pair_outcomes(a: list[dict], b: list[dict]) -> list[dict]:
    """Pair by (dataset, query_id, trial_index); raise if key sets differ across arms."""
    a_map = {
        (r["dataset"], int(r["query_id"]), int(r["trial_index"])): r for r in a
    }
    b_map = {
        (r["dataset"], int(r["query_id"]), int(r["trial_index"])): r for r in b
    }
    if set(a_map) != set(b_map):
        diff_a = sorted(set(a_map) - set(b_map))[:3]
        diff_b = sorted(set(b_map) - set(a_map))[:3]
        raise ValueError(
            f"paired diff requires identical keys; A-only: {diff_a}; B-only: {diff_b}"
        )
    out: list[dict] = []
    for k in sorted(a_map):
        ds, qid, ti = k
        out.append(
            {
                "dataset": ds,
                "query_id": qid,
                "trial_index": ti,
                "a_reward": float(a_map[k]["reward"]),
                "b_reward": float(b_map[k]["reward"]),
            }
        )
    return out
