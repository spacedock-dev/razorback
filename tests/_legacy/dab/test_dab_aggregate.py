# ABOUTME: Unit tests for the DAB aggregator (§6.5).
# ABOUTME: Frozen synthetic input → byte-exact golden summary.json (AC-1).

import json
from pathlib import Path

from razorback._legacy.benchmarks.dab.aggregate import aggregate_synthetic

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "dab"


def test_aggregator_matches_golden_summary(tmp_path):
    rows = json.loads((FIXTURES / "synthetic_trial_results.json").read_text())
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    got = json.loads(out.read_text())
    expected = json.loads((FIXTURES / "golden_summary.json").read_text())
    assert got == expected


def test_pass_at_1_uses_pass_k_formula_at_k_equals_1():
    """pass@1 at k=1 reduces to c/n. Anchored to harbor's golden math."""
    from razorback._legacy.benchmarks.dab.aggregate import pass_at_k

    # pass_at_k uses the verbatim DAB formula `1 - comb(n-c, k)/comb(n, k)`.
    # For k=1 this equals c/n algebraically, but float division leaves a residue
    # at c=1, n=5 (0.19999…). The assertions below match the function as it
    # ships (verbatim upstream); approximate comparison is intentional.
    from math import isclose

    assert pass_at_k(n=5, c=0, k=1) == 0.0
    assert pass_at_k(n=5, c=5, k=1) == 1.0
    assert isclose(pass_at_k(n=5, c=3, k=1), 0.6)
    assert isclose(pass_at_k(n=5, c=1, k=1), 0.2)


class _StubVerifier:
    def __init__(self, reward: float) -> None:
        self.rewards = {"reward": reward}


class _StubTrial:
    def __init__(self, trial_name: str, reward: float) -> None:
        self.trial_name = trial_name
        self.verifier_result = _StubVerifier(reward)


def test_aggregate_job_result_uses_trial_name_map_to_pair(tmp_path):
    from razorback._legacy.benchmarks.dab.aggregate import aggregate_job_result

    trial_name_map = {
        "bookreview-q1": ("bookreview", 1),
        "bookreview-q2": ("bookreview", 2),
        "bookreview-q3": ("bookreview", 3),
    }
    rows = json.loads((FIXTURES / "synthetic_trial_results.json").read_text())
    trials = [_StubTrial(row["trial_name"], row["rewards"]["reward"]) for row in rows]

    out = tmp_path / "summary.json"
    aggregate_job_result(trial_results=trials, trial_name_map=trial_name_map, out_path=out)
    got = json.loads(out.read_text())
    expected = json.loads((FIXTURES / "golden_summary.json").read_text())
    assert got == expected


def test_aggregate_job_result_handles_missing_verifier_result(tmp_path):
    """A trial that errored before verifier emission counts as 0 reward."""
    from razorback._legacy.benchmarks.dab.aggregate import aggregate_job_result

    class _ErroredTrial:
        trial_name = "bookreview-q1__zzzz001"
        verifier_result = None

    out = tmp_path / "summary.json"
    aggregate_job_result(
        trial_results=[_ErroredTrial()],
        trial_name_map={"bookreview-q1": ("bookreview", 1)},
        out_path=out,
    )
    got = json.loads(out.read_text())
    assert got["datasets"]["bookreview"]["queries"][0]["n_correct"] == 0
