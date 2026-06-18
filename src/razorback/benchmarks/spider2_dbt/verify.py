# ABOUTME: spider2-dbt verifier — compares predicted vs gold .duckdb via
# ABOUTME: duckdb_match semantics and writes harbor's {"reward": <float>} file.
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from razorback.benchmarks.spider2_dbt.duckdb_match import compare_duckdb
    from razorback.benchmarks.spider2_dbt.eval_spec import load_eval_spec
except ModuleNotFoundError:  # running flat from /tests in the verifier container
    from duckdb_match import compare_duckdb  # type: ignore[no-redef]
    from eval_spec import load_eval_spec  # type: ignore[no-redef]


def emit_reward(
    *,
    predicted_db: Path,
    gold_db: Path,
    eval_spec: Path,
    reward_out: Path,
) -> None:
    """Compute the binary duckdb_match reward and write harbor's reward.json."""
    err: str | None = None
    if not Path(predicted_db).exists():
        is_match = False
        err = f"predicted DB not found ({predicted_db})"
    else:
        # Fail closed: an empty / malformed / schema-drifted gold spec must
        # surface as reward 0, never crash-into-pass and never silently 1.0.
        try:
            spec = load_eval_spec(Path(eval_spec))
            is_match = compare_duckdb(
                predicted_db=Path(predicted_db),
                gold_db=Path(gold_db),
                spec=spec,
            )
        except Exception as exc:  # noqa: BLE001 — any spec/compare failure = non-match
            is_match = False
            err = f"eval-spec/compare error: {exc}"
    payload = {"reward": 1.0 if is_match else 0.0}
    Path(reward_out).parent.mkdir(parents=True, exist_ok=True)
    Path(reward_out).write_text(json.dumps(payload) + "\n")
    if not is_match:
        detail = f": {err}" if err else ""
        sys.stderr.write(
            f"spider2-dbt verify: mismatch (predicted={predicted_db}){detail}\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predicted-db", type=Path, required=True)
    parser.add_argument("--gold-db", type=Path, required=True)
    parser.add_argument("--eval-spec", type=Path, required=True)
    parser.add_argument("--reward-out", type=Path, required=True)
    args = parser.parse_args()
    emit_reward(
        predicted_db=args.predicted_db,
        gold_db=args.gold_db,
        eval_spec=args.eval_spec,
        reward_out=args.reward_out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
