# ABOUTME: razorback.runs package — read-side helpers + PKG-17 post-harbor aggregator.
# ABOUTME: Backs the rk runs list/show/cost/diff CLI subcommands.

from razorback.runs.aggregate import aggregate_run_dir

__all__ = ["aggregate_run_dir"]
