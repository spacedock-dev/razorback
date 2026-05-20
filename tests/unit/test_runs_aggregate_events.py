# ABOUTME: PKG-17 AC-3 — top-level events.jsonl is the per-trial concatenation
# ABOUTME: with each line carrying {trial_id, line_offset} for cross-trial correlation.

import json
import shutil
from pathlib import Path

from razorback.runs.aggregate import concatenate_events

FIXTURE_RUN = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "runs"
    / "post_harbor_skeleton"
)


def _copy_fixture(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dst / child.name
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy(child, target)


def test_concatenate_events_writes_top_level_with_trial_prefix(tmp_path):
    work = tmp_path / "exp" / "job"
    _copy_fixture(FIXTURE_RUN, work)

    concatenate_events(work)

    top = (work / "events.jsonl").read_text().splitlines()
    # Q1 has 3 events; Q2 has 2; Q3 has none.
    assert len(top) == 5

    parsed = [json.loads(line) for line in top]
    for row in parsed:
        assert "trial_id" in row
        assert "line_offset" in row

    q1_rows = [r for r in parsed if r["trial_id"] == "bookreview-q1__a"]
    assert q1_rows[0]["event"] == "start"
    assert q1_rows[0]["line_offset"] == 0
    assert q1_rows[2]["event"] == "end"
    assert q1_rows[2]["line_offset"] == 2


def test_concatenate_events_tolerates_missing_per_trial_file(tmp_path):
    work = tmp_path / "exp" / "job"
    _copy_fixture(FIXTURE_RUN, work)

    concatenate_events(work)
    parsed = [json.loads(line) for line in (work / "events.jsonl").read_text().splitlines()]
    assert not any(r["trial_id"] == "bookreview-q3__c" for r in parsed)
