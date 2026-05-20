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


# Task 2 — Reducer counting + null-result rule.


def test_mixed_stratum_uses_n_completed_denominator() -> None:
    """1 pass + 1 fail + 1 errored → pass@1 = 1/2 (NOT 1/3). spec §9.2."""
    records = [
        _completed("p", "A", True),
        _completed("f", "A", False),
        _errored("e", "A"),
    ]
    report = reduce_trials(records, alpha=0.05)
    s = report["strata"]["A"]
    assert s["n_total"] == 3
    assert s["n_completed"] == 2
    assert s["n_errored"] == 1
    assert s["n_pass"] == 1
    assert s["pass_at_1"] == pytest.approx(0.5)
    assert s["error_reason"] is None


def test_all_completed_stratum_has_clean_denominator() -> None:
    """3 passes / 0 errors → pass@1 = 1.0, n_errored = 0, wilson_ci not null, error_reason None."""
    records = [_completed(f"p{i}", "A", True) for i in range(3)]
    report = reduce_trials(records, alpha=0.05)
    s = report["strata"]["A"]
    assert s["n_total"] == 3
    assert s["n_completed"] == 3
    assert s["n_errored"] == 0
    assert s["n_pass"] == 3
    assert s["pass_at_1"] == pytest.approx(1.0)
    assert s["wilson_ci"] is not None
    assert s["error_reason"] is None


def test_all_errored_stratum_null_passes_and_wilson() -> None:
    """3 errored / 0 completed → pass@1 = None, wilson_ci = None, n_pass = 0."""
    records = [_errored(f"e{i}", "A", "SubprocessError") for i in range(3)]
    report = reduce_trials(records, alpha=0.05)
    s = report["strata"]["A"]
    assert s["n_total"] == 3
    assert s["n_completed"] == 0
    assert s["n_errored"] == 3
    assert s["n_pass"] == 0
    assert s["pass_at_1"] is None
    assert s["wilson_ci"] is None


def test_all_errored_run_level_rollup_is_null() -> None:
    """Two strata, both all-errored → stratified_pass_at_1 None, stratified_n_completed 0."""
    records = [
        _errored("a1", "A", "SubprocessError"),
        _errored("a2", "A", "SubprocessError"),
        _errored("b1", "B", "TimeoutError"),
        _errored("b2", "B", "TimeoutError"),
    ]
    report = reduce_trials(records, alpha=0.05)
    assert report["stratified_pass_at_1"] is None
    assert report["stratified_n_completed"] == 0
    assert report["stratified_n_errored"] == 4
    assert report["error_reason"] is not None


def test_macro_average_drops_null_strata() -> None:
    """A (all-pass) + B (all-fail) + C (all-errored) → stratified = mean(1.0, 0.0) = 0.5, NOT 0.333."""
    records = [
        _completed("a1", "A", True),
        _completed("a2", "A", True),
        _completed("b1", "B", False),
        _completed("b2", "B", False),
        _errored("c1", "C", "SubprocessError"),
        _errored("c2", "C", "SubprocessError"),
    ]
    report = reduce_trials(records, alpha=0.05)
    assert report["strata"]["A"]["pass_at_1"] == pytest.approx(1.0)
    assert report["strata"]["B"]["pass_at_1"] == pytest.approx(0.0)
    assert report["strata"]["C"]["pass_at_1"] is None
    assert report["stratified_pass_at_1"] == pytest.approx(0.5)
