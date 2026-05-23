# ABOUTME: AC-1 — canonical reducer consumes reward_per_query.json for DAB batch trials.
# ABOUTME: Run-dir-driven; exercises read_trial_outcomes + reduce_per_query_stratified end-to-end.

from __future__ import annotations

from pathlib import Path

from razorback.runs.aggregate import read_trial_outcomes, reduce_per_query_stratified

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "score"
DAB_BATCH_FIXTURE = FIXTURE_ROOT / "dab_batch_run_dir"


def test_batch_mode_reads_reward_per_query_sidecar() -> None:
    """A DAB batch trial with composite reward 0.857 and a sidecar of six 1.0s
    and one 0.0 must reduce to pass_at_1 == 6/7, not 0.0."""
    outcomes = read_trial_outcomes(DAB_BATCH_FIXTURE)
    report = reduce_per_query_stratified(outcomes, alpha=0.05)

    cells = report["strata"]["yelp"]["queries"]
    by_qid = {c["query_id"]: c["n_correct"] for c in cells}
    assert by_qid == {1: 1, 2: 1, 3: 1, 4: 0, 5: 1, 6: 1, 7: 1}
    assert report["strata"]["yelp"]["dataset_pass_at_1"] == 6 / 7
    assert report["stratified_pass_at_1"] == 6 / 7
