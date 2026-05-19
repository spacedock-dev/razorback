# ABOUTME: AC-5 grep gate — aggregate.py never reads JobResult.stats.evals.
# ABOUTME: §6.5: harbor's JobStats.evals is a per-dataset micro-average, not what DAB needs.

import re
from pathlib import Path

import razorback.benchmarks.dab.aggregate as aggregate_module


def test_aggregate_does_not_reference_stats_evals():
    src = Path(aggregate_module.__file__).read_text()
    # No occurrence of `stats.evals` anywhere in the module source.
    assert not re.search(r"stats\.evals", src), "aggregate.py must not read JobStats.evals (AC-5)"
    # Defensive: the literal string `evals` should also not appear (no near-misses).
    assert "evals" not in src
