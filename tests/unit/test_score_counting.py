# ABOUTME: PKG-2 v2 counting-honesty rules — fragment of Phase 4a rk score.
# ABOUTME: Pins denominator (n_completed), null-result, and error_reason rules per spec §3.2 + §8.3a + §9.2.

from __future__ import annotations

from pathlib import Path

import pytest

from razorback.score.load import TrialRecord, load_run_dir
from razorback.score.reduce import reduce_trials

FIXTURE_ROOT = Path(__file__).parent.parent / "fixtures" / "score"
ERROR_TAXONOMY = FIXTURE_ROOT / "error_taxonomy"


def _completed(name: str, stratum: str, passed: bool) -> TrialRecord:
    return TrialRecord(
        trial_name=name,
        stratum=stratum,
        state="completed",
        passed=passed,
        reward=1.0 if passed else 0.0,
        error_class=None,
    )


def _errored(name: str, stratum: str, error_class: str | None = "SubprocessError") -> TrialRecord:
    return TrialRecord(
        trial_name=name,
        stratum=stratum,
        state="errored",
        passed=None,
        reward=None,
        error_class=error_class,
    )


# Task 1 — Error-state taxonomy fixtures + loader assertion (AC-2 prerequisite).


def test_loader_resolves_four_state_cells() -> None:
    """PASS / FAIL / ERROR-subprocess / ERROR-other cells must map to canonical TrialRecord shapes."""
    records = load_run_dir(ERROR_TAXONOMY)
    by_name = {r.trial_name: r for r in records}

    assert by_name["trial-pass"].state == "completed"
    assert by_name["trial-pass"].passed is True
    assert by_name["trial-pass"].reward == 1.0
    assert by_name["trial-pass"].error_class is None

    assert by_name["trial-fail"].state == "completed"
    assert by_name["trial-fail"].passed is False
    assert by_name["trial-fail"].reward == 0.0
    assert by_name["trial-fail"].error_class is None

    assert by_name["trial-error-subprocess"].state == "errored"
    assert by_name["trial-error-subprocess"].passed is None
    assert by_name["trial-error-subprocess"].reward is None
    assert by_name["trial-error-subprocess"].error_class == "SubprocessError"

    assert by_name["trial-error-other"].state == "errored"
    assert by_name["trial-error-other"].passed is None
    assert by_name["trial-error-other"].reward is None
    assert by_name["trial-error-other"].error_class == "TimeoutError"


def test_loader_stratum_tag_passthrough_from_dab_shape() -> None:
    """agent/stratum.json with DAB shape resolves to dataset slug as stratum label."""
    records = load_run_dir(ERROR_TAXONOMY)
    assert all(r.stratum == "bookreview" for r in records)
