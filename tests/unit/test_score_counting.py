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


# Task 3 — Error-reason rule.


def test_single_class_all_errored_names_the_class() -> None:
    """All three errored as SubprocessError → error_reason == 'SubprocessError'."""
    records = [_errored(f"e{i}", "A", "SubprocessError") for i in range(3)]
    report = reduce_trials(records, alpha=0.05)
    assert report["strata"]["A"]["error_reason"] == "SubprocessError"


def test_mixed_class_all_errored_picks_dominant() -> None:
    """2 SubprocessError + 1 TimeoutError → SubprocessError dominates (count 2 > 1)."""
    records = [
        _errored("e1", "A", "SubprocessError"),
        _errored("e2", "A", "SubprocessError"),
        _errored("e3", "A", "TimeoutError"),
    ]
    report = reduce_trials(records, alpha=0.05)
    assert report["strata"]["A"]["error_reason"] == "SubprocessError"


def test_error_reason_tie_broken_alphabetically() -> None:
    """1 SubprocessError + 1 TimeoutError (tied at 1) → 'SubprocessError' wins by alphabetical order."""
    records = [
        _errored("e1", "A", "SubprocessError"),
        _errored("e2", "A", "TimeoutError"),
    ]
    report = reduce_trials(records, alpha=0.05)
    assert report["strata"]["A"]["error_reason"] == "SubprocessError"


def test_error_reason_tie_alphabetical_when_first_letter_decides() -> None:
    """'AError' tied 1:1 with 'ZError' → 'AError' wins. Confirms sort order is alphabetical, not insertion."""
    records = [
        _errored("e1", "A", "ZError"),
        _errored("e2", "A", "AError"),
    ]
    report = reduce_trials(records, alpha=0.05)
    assert report["strata"]["A"]["error_reason"] == "AError"


def test_top_level_error_reason_aggregates_across_strata() -> None:
    """A: 3 Subprocess; B: 1 Subprocess + 2 Timeout. Total: 4 Subprocess + 2 Timeout → 'SubprocessError'."""
    records = [
        _errored("a1", "A", "SubprocessError"),
        _errored("a2", "A", "SubprocessError"),
        _errored("a3", "A", "SubprocessError"),
        _errored("b1", "B", "SubprocessError"),
        _errored("b2", "B", "TimeoutError"),
        _errored("b3", "B", "TimeoutError"),
    ]
    report = reduce_trials(records, alpha=0.05)
    assert report["error_reason"] == "SubprocessError"


def test_mixed_stratum_has_no_per_stratum_error_reason() -> None:
    """n_completed > 0 ⇒ error_reason absent (None) on the stratum, even when one trial errored."""
    records = [
        _completed("p", "A", True),
        _errored("e", "A", "SubprocessError"),
    ]
    report = reduce_trials(records, alpha=0.05)
    assert report["strata"]["A"]["n_completed"] == 1
    assert report["strata"]["A"]["n_errored"] == 1
    assert report["strata"]["A"]["error_reason"] is None


def test_top_level_error_reason_absent_when_any_stratum_has_completions() -> None:
    """If at least one stratum has a pass@1, top-level error_reason is None (signal lives in pass@1)."""
    records = [
        _completed("p", "A", True),
        _errored("e1", "B", "SubprocessError"),
        _errored("e2", "B", "SubprocessError"),
    ]
    report = reduce_trials(records, alpha=0.05)
    assert report["stratified_pass_at_1"] is not None
    assert report["error_reason"] is None


def test_missing_verifier_result_surfaces_as_error_class() -> None:
    """Loader maps verifier_result=null + exception_info=null to error_class='MissingVerifierResult'.

    Plan named the fallback 'UnknownError'; the implementation chose the more specific
    'MissingVerifierResult' to identify the cause (missing verifier output) rather than
    a generic catch-all. The reducer is agnostic to the literal: whatever the loader
    emits as error_class propagates verbatim into error_reason. Documented as
    plan-vs-implementation drift in the entity stage report.
    """
    records = [_errored(f"e{i}", "A", "MissingVerifierResult") for i in range(3)]
    report = reduce_trials(records, alpha=0.05)
    assert report["strata"]["A"]["error_reason"] == "MissingVerifierResult"


# Wire-shape invariants — error_reason key present-with-null on no-error and mixed paths (spec §3.3 stability).


def test_error_reason_key_present_with_null_on_clean_stratum() -> None:
    """error_reason MUST be a key (value None) on no-error stratum so schema snapshot is stable."""
    records = [_completed("p", "A", True)]
    report = reduce_trials(records, alpha=0.05)
    assert "error_reason" in report["strata"]["A"]
    assert report["strata"]["A"]["error_reason"] is None


def test_top_level_error_reason_key_present_with_null_on_clean_run() -> None:
    """Top-level error_reason MUST be a key (value None) on a run that has any pass@1."""
    records = [_completed("p", "A", True)]
    report = reduce_trials(records, alpha=0.05)
    assert "error_reason" in report
    assert report["error_reason"] is None
