# ABOUTME: AC-3 — per-query Wilson CIs at the cell level; null at the stratum level.
# ABOUTME: The dataset stratum is mean-of-proportions, not binomial, so its CI is null.

from __future__ import annotations

from razorback.diff.stats import wilson_ci
from razorback.runs.aggregate import reduce_per_query_stratified


def _outcome(
    trial_id: str,
    *,
    reward: float | None,
    dataset: str = "bookreview",
    query_id: int | str | None = 1,
    error_reason: str | None = None,
) -> dict:
    return {
        "trial_id": trial_id,
        "reward": reward,
        "cost_usd": None,
        "wall_seconds": None,
        "error_reason": error_reason,
        "stratum": {"dataset": dataset, "query_id": query_id},
    }


def test_per_query_wilson_matches_diff_stats_wilson() -> None:
    """A query with k=3, n=5 yields the same Wilson CI as diff/stats.wilson_ci."""
    outcomes = [_outcome(f"t{i}", reward=r) for i, r in enumerate([1.0, 1.0, 1.0, 0.0, 0.0])]
    report = reduce_per_query_stratified(outcomes, alpha=0.05)

    [cell] = report["strata"]["bookreview"]["queries"]
    assert cell["n_trials"] == 5
    assert cell["n_correct"] == 3
    assert cell["wilson_ci"] == wilson_ci(k=3, n=5, alpha=0.05)


def test_dataset_stratum_wilson_ci_is_always_null() -> None:
    """Mean-of-proportions across queries is not binomial; emit explicit null."""
    outcomes = [
        _outcome("t1", reward=1.0, query_id=1),
        _outcome("t2", reward=0.0, query_id=2),
    ]
    report = reduce_per_query_stratified(outcomes, alpha=0.05)
    assert report["strata"]["bookreview"]["wilson_ci"] is None


def test_all_pass_query_upper_bound_one() -> None:
    outcomes = [_outcome(f"t{i}", reward=1.0) for i in range(5)]
    report = reduce_per_query_stratified(outcomes, alpha=0.05)
    [cell] = report["strata"]["bookreview"]["queries"]
    assert cell["wilson_ci"][1] == 1.0


def test_alpha_flag_propagates_to_cell_wilson() -> None:
    outcomes = [_outcome(f"t{i}", reward=r) for i, r in enumerate([1.0, 0.0])]
    narrow = reduce_per_query_stratified(outcomes, alpha=0.50)
    wide = reduce_per_query_stratified(outcomes, alpha=0.05)
    narrow_cell = narrow["strata"]["bookreview"]["queries"][0]
    wide_cell = wide["strata"]["bookreview"]["queries"][0]
    narrow_width = narrow_cell["wilson_ci"][1] - narrow_cell["wilson_ci"][0]
    wide_width = wide_cell["wilson_ci"][1] - wide_cell["wilson_ci"][0]
    assert narrow_width < wide_width


def test_unequal_trials_per_query_uses_mean_of_proportions() -> None:
    """q1: 1/2 = 0.5; q2: 0/1 = 0.0; dataset mean = 0.25 (NOT the binary 1/3)."""
    outcomes = [
        _outcome("t1", reward=1.0, query_id=1),
        _outcome("t2", reward=0.0, query_id=1),
        _outcome("t3", reward=0.0, query_id=2),
    ]
    report = reduce_per_query_stratified(outcomes, alpha=0.05)
    assert report["strata"]["bookreview"]["dataset_pass_at_1"] == 0.25
    assert report["stratified_pass_at_1"] == 0.25


def test_all_errored_emits_null_stratified_with_dominant_error_reason() -> None:
    outcomes = [
        _outcome("t1", reward=None, error_reason="SubprocessError"),
        _outcome("t2", reward=None, error_reason="SubprocessError"),
        _outcome("t3", reward=None, error_reason="OtherError"),
    ]
    report = reduce_per_query_stratified(outcomes, alpha=0.05)
    assert report["stratified_pass_at_1"] is None
    assert report["error_reason"] == "SubprocessError"
    assert report["n_trials_errored"] == 3
    assert report["n_trials_completed"] == 0
