# ABOUTME: AC-1, AC-7 — Wilson CI, exact-McNemar p, power-at-fixed-N MDE.

import math

import pytest

from razorback.diff.stats import (
    exact_mcnemar_p,
    power_mde_at_fixed_n,
    wilson_ci,
)

# --- Wilson 95% CI ---


def test_wilson_ci_zero_successes_at_n_five() -> None:
    """k=0, n=5, alpha=0.05: lower bound clipped to 0; upper bound is the closed-form."""
    lo, hi = wilson_ci(k=0, n=5, alpha=0.05)
    # Hand-computed with z=1.959963984540054:
    #   denom = 1 + z^2/5 = 1.7679...
    #   center = (0 + z^2/10) / denom = 0.21712...
    #   half = (z / denom) * sqrt(0 + z^2/100) = 0.21712...
    # ci = (0.0 [clipped], 0.43424).
    assert lo == pytest.approx(0.0, abs=1e-9)
    assert hi == pytest.approx(0.43434, abs=1e-3)


def test_wilson_ci_three_of_five() -> None:
    """k=3, n=5, alpha=0.05: known-good Wilson bounds approximately (0.23, 0.88)."""
    lo, hi = wilson_ci(k=3, n=5, alpha=0.05)
    assert 0.0 < lo < hi < 1.0
    assert lo == pytest.approx(0.23, abs=0.05)
    assert hi == pytest.approx(0.88, abs=0.05)


def test_wilson_ci_perfect_pass_at_n_five() -> None:
    """k=n=5: lower bound is strictly less than 1.0; upper bound clipped at 1.0."""
    lo, hi = wilson_ci(k=5, n=5, alpha=0.05)
    assert lo > 0.0
    assert lo < 1.0
    assert hi == pytest.approx(1.0, abs=1e-9)


def test_wilson_ci_alpha_widens_interval() -> None:
    lo_01, hi_01 = wilson_ci(k=3, n=10, alpha=0.01)
    lo_05, hi_05 = wilson_ci(k=3, n=10, alpha=0.05)
    assert (hi_01 - lo_01) > (hi_05 - lo_05)


def test_wilson_ci_zero_n_returns_full_unit_interval() -> None:
    lo, hi = wilson_ci(k=0, n=0, alpha=0.05)
    assert lo == 0.0
    assert hi == 1.0


# --- Exact-McNemar p ---


def test_mcnemar_perfect_agreement_returns_one() -> None:
    """b=c=0: no discordant pairs; p = 1.0 by convention."""
    assert exact_mcnemar_p(b=0, c=0) == 1.0


def test_mcnemar_one_vs_zero_discordant() -> None:
    """b=1, c=0 on n_discordant=1: exact-binomial two-sided p at k=0, n=1, p=0.5 is 1.0."""
    assert exact_mcnemar_p(b=1, c=0) == pytest.approx(1.0)


def test_mcnemar_two_vs_zero_discordant() -> None:
    """b=2, c=0: exact-binomial two-sided p = 0.5."""
    assert exact_mcnemar_p(b=2, c=0) == pytest.approx(0.5)


def test_mcnemar_five_vs_zero_discordant() -> None:
    """b=5, c=0: p = 2 * 0.5^5 = 0.0625."""
    assert exact_mcnemar_p(b=5, c=0) == pytest.approx(0.0625, abs=1e-9)


def test_mcnemar_symmetric_in_b_and_c() -> None:
    assert exact_mcnemar_p(b=2, c=5) == pytest.approx(exact_mcnemar_p(b=5, c=2))


# --- Power-at-fixed-N MDE ---


def test_power_mde_at_alpha_05_power_80_baseline_05_n_60() -> None:
    """Closed-form normal-approx MDE: (1.95996 + 0.84162) * sqrt(0.25/60) = 0.18019."""
    mde = power_mde_at_fixed_n(alpha=0.05, power=0.80, baseline_p=0.5, n=60)
    assert mde == pytest.approx(0.18019, abs=1e-3)


def test_power_mde_smaller_at_larger_n() -> None:
    mde_60 = power_mde_at_fixed_n(alpha=0.05, power=0.80, baseline_p=0.5, n=60)
    mde_600 = power_mde_at_fixed_n(alpha=0.05, power=0.80, baseline_p=0.5, n=600)
    assert mde_600 < mde_60


def test_power_mde_smaller_at_lower_power() -> None:
    mde_80 = power_mde_at_fixed_n(alpha=0.05, power=0.80, baseline_p=0.5, n=60)
    mde_50 = power_mde_at_fixed_n(alpha=0.05, power=0.50, baseline_p=0.5, n=60)
    assert mde_50 < mde_80


def test_power_mde_is_finite_at_baseline_0() -> None:
    """baseline_p=0 -> se=0 -> mde=0; the line is a no-op but must not divide by zero."""
    mde = power_mde_at_fixed_n(alpha=0.05, power=0.80, baseline_p=0.0, n=60)
    assert math.isfinite(mde)
    assert mde == 0.0
