# ABOUTME: AC-6 — adapter-agnostic stratum tagging.
# ABOUTME: DAB fixture (stratum.dataset) + ade-bench fixture (stratum.split) both work.

from __future__ import annotations

from pathlib import Path

import pytest

from razorback.score.load import ScoreInputError, load_run_dir

FIXTURE_ROOT = Path(__file__).parent.parent / "fixtures" / "score"


def test_dab_fixture_uses_dataset_as_stratum_label() -> None:
    records = load_run_dir(FIXTURE_ROOT / "mixed_trial_run_dir")
    assert {r.stratum for r in records} == {"bookreview"}


def test_ade_bench_fixture_uses_first_scalar_key_as_stratum() -> None:
    """ade-bench's stratum lacks `dataset`; loader picks first scalar (`split`)."""
    records = load_run_dir(FIXTURE_ROOT / "ade_bench_run_dir")
    assert len(records) == 3
    assert {r.stratum for r in records} == {"test"}


def test_no_scalar_stratum_raises_score_input_error() -> None:
    """A stratum that has only list-valued fields cannot be labeled."""
    with pytest.raises(ScoreInputError) as exc_info:
        load_run_dir(FIXTURE_ROOT / "no_scalar_stratum_run_dir")
    assert "trial-1" in str(exc_info.value)
