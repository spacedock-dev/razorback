# ABOUTME: M6 — DAB aggregator writes per_trial_outcomes.json sidecar alongside summary.json.
# ABOUTME: Schema is the diff command's pairing input.

import json
from pathlib import Path

from razorback.benchmarks.dab.aggregate import aggregate_synthetic


def test_aggregate_synthetic_writes_per_trial_outcomes_sidecar(tmp_path: Path) -> None:
    rows = [
        {"dataset": "bookreview", "query_id": 1, "trial_index": 0, "rewards": {"reward": 1.0}},
        {"dataset": "bookreview", "query_id": 1, "trial_index": 1, "rewards": {"reward": 0.0}},
        {"dataset": "bookreview", "query_id": 2, "trial_index": 0, "rewards": {"reward": 1.0}},
        {"dataset": "agnews", "query_id": 1, "trial_index": 0, "rewards": {"reward": 0.0}},
    ]
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    sidecar = tmp_path / "per_trial_outcomes.json"
    assert sidecar.exists(), "per_trial_outcomes.json sidecar must be written next to summary.json"
    payload = json.loads(sidecar.read_text())
    assert payload["outcomes_version"] == 1
    assert len(payload["trials"]) == 4
    sample = next(
        t for t in payload["trials"]
        if t["dataset"] == "bookreview" and t["query_id"] == 1 and t["trial_index"] == 0
    )
    assert sample["reward"] == 1.0


def test_aggregate_synthetic_summary_shape_unchanged(tmp_path: Path) -> None:
    """The M5 summary.json contract is unchanged — additive sidecar only."""
    rows = [
        {"dataset": "ds", "query_id": 1, "trial_index": 0, "rewards": {"reward": 1.0}},
    ]
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    payload = json.loads(out.read_text())
    assert payload["summary_version"] == 1
    assert "stratified_pass_at_1" in payload
    assert "datasets" in payload


def test_aggregate_synthetic_back_compat_trial_index_defaults(tmp_path: Path) -> None:
    """M2 fixtures without explicit trial_index still aggregate and emit a sidecar.

    Per (dataset, query_id) running counter starting at 0 — preserves the order rows arrive.
    """
    rows = [
        {"dataset": "ds", "query_id": 1, "rewards": {"reward": 1.0}},
        {"dataset": "ds", "query_id": 1, "rewards": {"reward": 0.0}},
        {"dataset": "ds", "query_id": 2, "rewards": {"reward": 1.0}},
    ]
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    payload = json.loads((tmp_path / "per_trial_outcomes.json").read_text())
    trials_q1 = sorted(
        (t for t in payload["trials"] if t["query_id"] == 1),
        key=lambda t: t["trial_index"],
    )
    assert [t["trial_index"] for t in trials_q1] == [0, 1]
    assert [t["reward"] for t in trials_q1] == [1.0, 0.0]
