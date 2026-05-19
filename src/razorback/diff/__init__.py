# ABOUTME: Razorback diff package — paired statistics for `rk runs diff` (§6.5).
# ABOUTME: Re-exports the public surface as tasks land.

from razorback.diff.stats import (
    exact_mcnemar_p,
    paired_bootstrap_ci,
    power_mde_at_fixed_n,
    wilson_ci,
)

__all__ = [
    "exact_mcnemar_p",
    "paired_bootstrap_ci",
    "power_mde_at_fixed_n",
    "wilson_ci",
]
