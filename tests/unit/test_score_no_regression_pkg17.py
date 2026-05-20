# ABOUTME: PKG-17 AC-8 — rk score's output is unchanged after PKG-17 lands.
# ABOUTME: Walks per-trial result.json (score/load.py:44-60) — independent of new summary.json.

import shutil
from pathlib import Path

from razorback.score.load import load_run_dir

FIXTURE_RUN = Path(__file__).resolve().parents[1] / "fixtures" / "runs" / "post_harbor_skeleton"


def test_rk_score_loader_unaffected_by_summary_json_presence(tmp_path: Path):
    """`load_run_dir` walks per-trial result.json, not summary.json. Adding
    summary.json (and friends) at run-dir top level must not change which
    trial records `load_run_dir` returns."""
    work = tmp_path / "exp" / "job"
    work.mkdir(parents=True)
    for child in FIXTURE_RUN.iterdir():
        if child.is_dir():
            shutil.copytree(child, work / child.name)
        else:
            shutil.copy(child, work / child.name)

    before = load_run_dir(work)
    before_state = {(r.trial_name, r.state, r.reward) for r in before}

    from razorback.runs.aggregate import aggregate_run_dir

    (work / "spec.frozen.yaml").write_text("version: 1\n")
    (work / "provenance.yaml").write_text("harbor_version: 0.6.6\n")
    aggregate_run_dir(
        work,
        spec_path=Path("/x"),
        frozen_spec_hash="a" * 64,
        provenance_hash="b" * 64,
        harbor_job_name="job",
        benchmark_kind="dab",
    )

    after = load_run_dir(work)
    after_state = {(r.trial_name, r.state, r.reward) for r in after}

    assert before_state == after_state, (
        f"rk score loader regression: {before_state ^ after_state}"
    )
