# ABOUTME: AC-4 — batch-mode aggregator fans one trial's per-query verdicts into N outcomes.
# ABOUTME: Reads reward_per_query.json sidecar from the trial verifier dir.

from __future__ import annotations

import json
from pathlib import Path

from razorback._legacy.benchmarks.dab.aggregate import aggregate_job_result


class _StubVerifier:
    def __init__(self, reward: float) -> None:
        self.rewards = {"reward": reward}


class _StubTrial:
    def __init__(
        self, trial_name: str, reward: float, trial_dir: Path | None = None,
    ) -> None:
        self.trial_name = trial_name
        self.verifier_result = _StubVerifier(reward)
        self.trial_uri = trial_dir.resolve().as_uri() if trial_dir is not None else ""


def _write_per_query_sidecar(trial_dir: Path, payload: dict) -> None:
    """Place reward_per_query.json under the multi-step trial verifier dir."""
    verifier_dir = trial_dir / "steps" / "main" / "verifier"
    verifier_dir.mkdir(parents=True, exist_ok=True)
    (verifier_dir / "reward_per_query.json").write_text(
        json.dumps(payload) + "\n"
    )


def test_aggregate_batch_trial_emits_per_query_outcomes(tmp_path: Path) -> None:
    trial_dir = tmp_path / "trial-bookreview"
    _write_per_query_sidecar(trial_dir, {
        "q1": {"reward": 1.0, "reason": "ok"},
        "q2": {"reward": 0.0, "reason": "wrong"},
        "q3": {"reward": 1.0, "reason": "ok"},
    })
    trials = [_StubTrial("bookreview__zzzz001", reward=2.0 / 3.0, trial_dir=trial_dir)]
    trial_name_map = {"bookreview": ("bookreview", [1, 2, 3])}

    out = tmp_path / "summary.json"
    aggregate_job_result(trials, trial_name_map, out)

    sidecar = json.loads((tmp_path / "per_trial_outcomes.json").read_text())
    rows = sidecar["trials"]
    assert len(rows) == 3
    by_qid = {row["query_id"]: row for row in rows}
    assert by_qid[1]["reward"] == 1.0
    assert by_qid[2]["reward"] == 0.0
    assert by_qid[3]["reward"] == 1.0
    assert all(row["dataset"] == "bookreview" for row in rows)

    summary = json.loads(out.read_text())
    book = summary["datasets"]["bookreview"]
    assert book["n_queries"] == 3
    assert abs(book["dataset_pass_at_1"] - (2.0 / 3.0)) < 1e-9


def test_aggregate_per_query_trial_unchanged(tmp_path: Path) -> None:
    """Per-query map entries (tuple[str, int]) keep the single-outcome shape."""
    trials = [
        _StubTrial("bookreview-q1__zzz", reward=1.0),
        _StubTrial("bookreview-q2__zzz", reward=0.0),
        _StubTrial("bookreview-q3__zzz", reward=1.0),
    ]
    trial_name_map = {
        "bookreview-q1": ("bookreview", 1),
        "bookreview-q2": ("bookreview", 2),
        "bookreview-q3": ("bookreview", 3),
    }
    out = tmp_path / "summary.json"
    aggregate_job_result(trials, trial_name_map, out)

    sidecar = json.loads((tmp_path / "per_trial_outcomes.json").read_text())
    assert len(sidecar["trials"]) == 3
    by_qid = {row["query_id"]: row for row in sidecar["trials"]}
    assert by_qid[1]["reward"] == 1.0
    assert by_qid[2]["reward"] == 0.0
    assert by_qid[3]["reward"] == 1.0


def test_aggregate_batch_missing_sidecar_yields_zero_per_query(tmp_path: Path) -> None:
    """When the sidecar file is absent (verifier crashed), per-query rewards are 0.0
    and one outcome per declared query_id is still emitted — silent-empty would be
    a regression class.
    """
    trial_dir = tmp_path / "trial-bookreview-empty"
    (trial_dir / "steps" / "main" / "verifier").mkdir(parents=True)
    trials = [_StubTrial("bookreview__zzzz", reward=0.0, trial_dir=trial_dir)]
    trial_name_map = {"bookreview": ("bookreview", [1, 2, 3])}

    out = tmp_path / "summary.json"
    aggregate_job_result(trials, trial_name_map, out)

    sidecar = json.loads((tmp_path / "per_trial_outcomes.json").read_text())
    rows = sidecar["trials"]
    assert len(rows) == 3
    assert sorted(row["query_id"] for row in rows) == [1, 2, 3]
    assert all(row["reward"] == 0.0 for row in rows)
