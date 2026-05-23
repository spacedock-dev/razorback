# ABOUTME: M6 — run-dir aggregator writes per_trial_outcomes.json sidecar.
# ABOUTME: Schema is the diff command's pairing input.

import json
from pathlib import Path

from razorback.runs.aggregate import aggregate_summary, write_per_trial_outcomes


def _write_trial(run_dir: Path, name: str, reward: float | None) -> None:
    trial_dir = run_dir / name
    trial_dir.mkdir(parents=True)
    if reward is None:
        result = {"exception_info": {"exception_type": "AgentTimeoutError"}}
    else:
        result = {"verifier_result": {"rewards": {"reward": reward}}}
    (trial_dir / "result.json").write_text(json.dumps(result) + "\n")


def test_run_dir_aggregator_writes_per_trial_outcomes_sidecar(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_trial(run_dir, "agnews-q1__a", 0.0)
    _write_trial(run_dir, "bookreview-q1__a", 1.0)
    _write_trial(run_dir, "bookreview-q1__b", 0.0)
    _write_trial(run_dir, "bookreview-q2__a", 1.0)

    write_per_trial_outcomes(run_dir)

    sidecar = run_dir / "per_trial_outcomes.json"
    assert sidecar.exists(), "per_trial_outcomes.json sidecar must be written next to summary.json"
    payload = json.loads(sidecar.read_text())
    assert payload["outcomes_version"] == 1
    assert len(payload["trials"]) == 4
    sample = next(
        t for t in payload["trials"]
        if t["dataset"] == "bookreview" and t["query_id"] == 1 and t["trial_index"] == 0
    )
    assert sample["reward"] == 1.0


def test_run_dir_summary_shape_unchanged(tmp_path: Path) -> None:
    """The M5 summary.json contract is unchanged — additive sidecar only."""
    run_dir = tmp_path / "run"
    _write_trial(run_dir, "ds-q1__a", 1.0)

    aggregate_summary(run_dir)

    payload = json.loads((run_dir / "summary.json").read_text())
    assert payload["summary_version"] == 1
    assert "stratified_pass_at_1" in payload
    assert "datasets" in payload


def test_run_dir_trial_index_defaults(tmp_path: Path) -> None:
    """Per (dataset, query_id) counter starts at 0 in trial-dir sort order."""
    run_dir = tmp_path / "run"
    _write_trial(run_dir, "ds-q1__a", 1.0)
    _write_trial(run_dir, "ds-q1__b", 0.0)
    _write_trial(run_dir, "ds-q2__a", 1.0)

    write_per_trial_outcomes(run_dir)

    payload = json.loads((run_dir / "per_trial_outcomes.json").read_text())
    trials_q1 = sorted(
        (t for t in payload["trials"] if t["query_id"] == 1),
        key=lambda t: t["trial_index"],
    )
    assert [t["trial_index"] for t in trials_q1] == [0, 1]
    assert [t["reward"] for t in trials_q1] == [1.0, 0.0]
