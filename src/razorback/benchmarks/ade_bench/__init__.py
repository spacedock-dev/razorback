# ABOUTME: ade-bench benchmark adapter package (§9.2: second-supported harbor adapter after DAB).
# ABOUTME: Re-exports per_trial_state_reset for `rk validate` (§6.5 warning surface).

from razorback.benchmarks.ade_bench.reset import per_trial_state_reset

__all__ = ["per_trial_state_reset"]
