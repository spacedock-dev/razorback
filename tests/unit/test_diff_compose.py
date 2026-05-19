# ABOUTME: M6 Task 5 — compute_diff composes the four stats into the JSON shape rk runs diff emits.

import pytest

from razorback.diff.diff import compute_diff

from tests.unit.test_diff_paired_bootstrap_ci import _make_paired_outcomes


def test_compute_diff_returns_full_json_shape() -> None:
    a, b = _make_paired_outcomes()
    out = compute_diff(a, b, alpha=0.05, bootstrap_iters=500, seed=42)
    assert out["diff_version"] == 1
    assert out["alpha"] == 0.05
    assert out["bootstrap_iters"] == 500
    assert out["per_arm_stratified_pass_at_1"]["a"] == pytest.approx(0.4)
    assert out["per_arm_stratified_pass_at_1"]["b"] == pytest.approx(0.65)
    assert out["stratified_delta"] == pytest.approx(0.25)
    assert "lo" in out["stratified_delta_ci"]
    assert "hi" in out["stratified_delta_ci"]
    # 2 datasets x 2 queries each = 4 rows
    assert len(out["per_arm_wilson_ci_by_query"]) == 4
    assert len(out["exact_mcnemar_p_by_query"]) == 4
    assert out["power_mde"]["mde"] > 0


def test_compute_diff_mcnemar_uses_exact_binomial_at_n5() -> None:
    """At N=5 the per-query McNemar p equals the exact-binomial p; confirm one row's value."""
    a, b = _make_paired_outcomes()
    out = compute_diff(a, b, alpha=0.05, bootstrap_iters=500, seed=42)
    # ds2/q1: A=[1,1,1,1,0], B=[1,1,1,1,1]. b_only=1 (A fails, B passes at trial_index=4); c_only=0.
    # exact-binomial p at b+c=1, k=0 is 1.0.
    row = next(
        r for r in out["exact_mcnemar_p_by_query"]
        if r["dataset"] == "ds2" and r["query_id"] == 1
    )
    assert row["b_only"] == 1
    assert row["c_only"] == 0
    assert row["p"] == 1.0


def test_compute_diff_wilson_per_query_per_arm_shape() -> None:
    a, b = _make_paired_outcomes()
    out = compute_diff(a, b, alpha=0.05, bootstrap_iters=200, seed=42)
    row = next(
        r for r in out["per_arm_wilson_ci_by_query"]
        if r["dataset"] == "ds1" and r["query_id"] == 1
    )
    assert row["a"]["k"] == 3
    assert row["a"]["n"] == 5
    assert row["a"]["pass_at_1"] == 0.6
    assert 0.0 < row["a"]["wilson_lo"] < 0.6 < row["a"]["wilson_hi"] < 1.0
    assert row["b"]["k"] == 5
    assert row["b"]["n"] == 5
    assert row["b"]["pass_at_1"] == 1.0
    assert row["b"]["wilson_hi"] == 1.0


def test_compute_diff_power_mde_uses_paired_n_total() -> None:
    a, b = _make_paired_outcomes()
    out = compute_diff(a, b, alpha=0.05, bootstrap_iters=200, seed=42)
    # Fixture has 2 ds * 2 q * 5 trials = 20 paired rows.
    assert out["power_mde"]["n"] == 20
    assert out["power_mde"]["baseline_p"] == pytest.approx(0.4)
    assert out["power_mde"]["power"] == 0.80
    assert out["power_mde"]["alpha"] == 0.05
