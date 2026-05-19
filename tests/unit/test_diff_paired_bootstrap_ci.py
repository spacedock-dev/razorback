# ABOUTME: AC-1 RISKIEST CONTRACT — paired-bootstrap CI on stratified delta (§6.5).
# ABOUTME: Hand-authored 2x2x5 fixture; fixed seed; B=1000; tolerance 1e-9 on bounds.

import math

import pytest

from razorback.diff.stats import paired_bootstrap_ci


def _make_paired_outcomes() -> tuple[list[dict], list[dict]]:
    """Hand-author a 2-dataset x 2-query x 5-trial paired fixture.

    Hand-computed:
      Arm A:
        ds1 q1 trials = [1,1,1,0,0] -> pass@1 = 0.6
        ds1 q2 trials = [1,0,0,0,0] -> pass@1 = 0.2     -> ds1 mean = 0.4
        ds2 q1 trials = [1,1,1,1,0] -> pass@1 = 0.8
        ds2 q2 trials = [0,0,0,0,0] -> pass@1 = 0.0     -> ds2 mean = 0.4
        stratified_A = (0.4 + 0.4) / 2 = 0.4
      Arm B:
        ds1 q1 trials = [1,1,1,1,1] -> pass@1 = 1.0
        ds1 q2 trials = [1,1,0,0,0] -> pass@1 = 0.4     -> ds1 mean = 0.7
        ds2 q1 trials = [1,1,1,1,1] -> pass@1 = 1.0
        ds2 q2 trials = [1,0,0,0,0] -> pass@1 = 0.2     -> ds2 mean = 0.6
        stratified_B = (0.7 + 0.6) / 2 = 0.65
      Delta = stratified_B - stratified_A = 0.25
    """
    A = [
        {"dataset": "ds1", "query_id": 1, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 1, "reward": 1.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 2, "reward": 1.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 3, "reward": 0.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 4, "reward": 0.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 1, "reward": 0.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 2, "reward": 0.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 3, "reward": 0.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 4, "reward": 0.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 1, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 2, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 3, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 4, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 0, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 1, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 2, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 3, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 4, "reward": 0.0},
    ]
    B = [
        {"dataset": "ds1", "query_id": 1, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 1, "reward": 1.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 2, "reward": 1.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 3, "reward": 1.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 4, "reward": 1.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 1, "reward": 1.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 2, "reward": 0.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 3, "reward": 0.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 4, "reward": 0.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 1, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 2, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 3, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 4, "reward": 1.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 1, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 2, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 3, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 4, "reward": 0.0},
    ]
    return A, B


def test_paired_bootstrap_ci_returns_finite_interval_containing_true_delta():
    """The CI must be finite and contain the true delta = 0.25 on the hand-authored fixture."""
    A, B = _make_paired_outcomes()
    lo, hi = paired_bootstrap_ci(A, B, alpha=0.05, B=1000, seed=42)
    assert math.isfinite(lo) and math.isfinite(hi)
    assert lo <= hi
    assert lo <= 0.25 <= hi, f"true delta 0.25 outside CI [{lo}, {hi}]"


def test_paired_bootstrap_ci_deterministic_under_fixed_seed():
    """Calling twice with the same seed must produce identical bounds."""
    A, B = _make_paired_outcomes()
    lo1, hi1 = paired_bootstrap_ci(A, B, alpha=0.05, B=1000, seed=42)
    lo2, hi2 = paired_bootstrap_ci(A, B, alpha=0.05, B=1000, seed=42)
    assert lo1 == lo2
    assert hi1 == hi2


# Pinned after one canonical run: seed=42, B=1000, alpha=0.05 on the fixture above.
# Numpy 2.4.4 + scipy 1.17.1 on darwin-aarch64; if the bootstrap algorithm
# changes (e.g. percentile -> BCa) these MUST be re-derived.
EXPECTED_LO = 0.07137896825396822
EXPECTED_HI = 0.4854340277777777


def test_paired_bootstrap_ci_hand_computed_bounds():
    """At B=1000, seed=42, alpha=0.05, the bounds match pinned hand-computed values within 1e-9."""
    A, B = _make_paired_outcomes()
    lo, hi = paired_bootstrap_ci(A, B, alpha=0.05, B=1000, seed=42)
    assert abs(lo - EXPECTED_LO) < 1e-9, f"lo={lo} expected {EXPECTED_LO}"
    assert abs(hi - EXPECTED_HI) < 1e-9, f"hi={hi} expected {EXPECTED_HI}"


def test_paired_bootstrap_ci_alpha_widens_interval():
    """alpha=0.01 must produce a wider (or equal) interval than alpha=0.10."""
    A, B = _make_paired_outcomes()
    lo_01, hi_01 = paired_bootstrap_ci(A, B, alpha=0.01, B=1000, seed=42)
    lo_10, hi_10 = paired_bootstrap_ci(A, B, alpha=0.10, B=1000, seed=42)
    assert (hi_01 - lo_01) >= (hi_10 - lo_10)


def test_paired_bootstrap_ci_zero_delta_when_arms_identical():
    """When A == B (identical outcomes), the bootstrap CI must straddle 0."""
    A, _ = _make_paired_outcomes()
    lo, hi = paired_bootstrap_ci(A, A, alpha=0.05, B=1000, seed=42)
    assert lo <= 0.0 <= hi


def test_paired_bootstrap_ci_pairing_is_preserved():
    """Shuffling B's trial_index without shuffling A must change the bootstrap distribution.

    Pairing means trial_index=i in A is resampled together with trial_index=i in B. If we
    swap B's trial_index labels (breaking the pair-index correspondence), the resampled
    paired differences change.
    """
    A, B = _make_paired_outcomes()
    B_shuffled = [dict(row, trial_index=4 - row["trial_index"]) for row in B]
    lo_paired, hi_paired = paired_bootstrap_ci(A, B, alpha=0.05, B=1000, seed=42)
    lo_shuffled, hi_shuffled = paired_bootstrap_ci(A, B_shuffled, alpha=0.05, B=1000, seed=42)
    assert (lo_paired, hi_paired) != (lo_shuffled, hi_shuffled), (
        "shuffling pair indices in B did not change the CI — pairing is not being preserved"
    )
