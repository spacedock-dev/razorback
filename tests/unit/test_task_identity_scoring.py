import json
from pathlib import Path

from razorback.runs.aggregate import aggregate_summary, write_per_trial_outcomes


def _write_trial(run_dir: Path, trial_name: str, reward: float) -> None:
    trial = run_dir / trial_name
    trial.mkdir(parents=True)
    (trial / "result.json").write_text(
        json.dumps({"verifier_result": {"rewards": {"reward": reward}}})
    )


def _write_manifest(run_dir: Path, view_name: str, kind: str, task_id: str) -> None:
    view = run_dir / "_razorback" / "task_views" / view_name
    view.mkdir(parents=True)
    (view / "view_manifest.json").write_text(
        json.dumps(
            {
                "benchmark_kind": kind,
                "benchmark_task_id": task_id,
                "view_mode": "copy",
            }
        )
    )


def test_aggregator_resolves_task_identity_from_view_manifest(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_manifest(
        run_dir,
        "ade-bench-adebench-fixture-001",
        "ade-bench",
        "adebench-fixture-001",
    )
    _write_manifest(
        run_dir,
        "spider2-dbt-spider2-fixture-001",
        "spider2-dbt",
        "spider2-fixture-001",
    )
    _write_trial(run_dir, "ade-bench-adebench-fixture-001__abc1234", 1.0)
    _write_trial(run_dir, "spider2-dbt-spider2-fixture-001__def5678", 0.0)

    aggregate_summary(run_dir)
    write_per_trial_outcomes(run_dir)

    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["trials"][0]["stratum"]["benchmark_task_id"] == (
        "adebench-fixture-001"
    )
    assert summary["trials"][1]["stratum"]["benchmark_task_id"] == (
        "spider2-fixture-001"
    )

    outcomes = json.loads((run_dir / "per_trial_outcomes.json").read_text())
    task_ids = {row["benchmark_task_id"] for row in outcomes["trials"]}
    assert task_ids == {"adebench-fixture-001", "spider2-fixture-001"}
