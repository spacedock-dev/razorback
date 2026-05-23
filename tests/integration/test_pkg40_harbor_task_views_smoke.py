import json
from pathlib import Path

import pytest

from razorback.errors import SpecError
from razorback.spec.freeze import freeze_spec
from razorback.spec.schema import NopAgentBlock, Spec
from razorback.translate import spec_to_job_config


ADE_TASKS = Path(__file__).parent.parent / "fixtures" / "ade_bench" / "tasks"
SPIDER2_TASKS = (
    Path(__file__).parent.parent
    / "fixtures"
    / "spider2_dbt"
    / "harbor_task_minimal"
)


def test_ade_fixture_materializes_task_view_for_harbor(tmp_path):
    spec = Spec(
        version=1,
        experiment="pkg40-ade-smoke",
        agent=NopAgentBlock(kind="nop"),
        benchmark={
            "kind": "ade-bench",
            "tasks_root": ADE_TASKS,
            "tasks": ["adebench-fixture-001"],
            "docker_image_override": "shared-dbt-duckdb:latest",
        },
    )

    job_config, _ = spec_to_job_config(spec, job_name="ade-smoke", jobs_dir=tmp_path)

    view = job_config.tasks[0].path
    assert view.name == "ade-bench-adebench-fixture-001"
    manifest = json.loads((view / "view_manifest.json").read_text())
    assert manifest["benchmark_kind"] == "ade-bench"
    assert manifest["benchmark_task_id"] == "adebench-fixture-001"
    assert job_config.tasks[0].get_local_path() == view.resolve()


def test_spider2_fixture_materializes_task_view_for_harbor(tmp_path):
    spec = Spec(
        version=1,
        experiment="pkg40-spider2-smoke",
        agent=NopAgentBlock(kind="nop"),
        benchmark={
            "kind": "spider2-dbt",
            "tasks_root": SPIDER2_TASKS,
            "tasks": ["spider2-fixture-001"],
            "docker_image_override": "shared-dbt-duckdb:latest",
        },
        concurrency={"trials": 2},
    )

    job_config, _ = spec_to_job_config(
        spec, job_name="spider2-smoke", jobs_dir=tmp_path
    )

    view = job_config.tasks[0].path
    assert view.name == "spider2-dbt-spider2-fixture-001"
    assert job_config.n_concurrent_trials == 2
    assert not (view / "solution" / "solve.sh").exists()
    assert not (view / "tests" / "expected" / "answer.txt").exists()
    manifest = json.loads((view / "view_manifest.json").read_text())
    assert manifest["benchmark_kind"] == "spider2-dbt"
    assert manifest["benchmark_task_id"] == "spider2-fixture-001"


def test_shared_context_layout_fails_closed_before_harbor(tmp_path):
    spec = Spec(
        version=1,
        experiment="pkg40-shared-context-smoke",
        agent=NopAgentBlock(kind="nop"),
        benchmark={
            "kind": "spider2-dbt",
            "tasks_root": SPIDER2_TASKS,
            "tasks": ["spider2-fixture-001"],
            "batch_mode": "shared-context",
        },
    )

    with pytest.raises(SpecError, match="shared-context"):
        spec_to_job_config(spec, job_name="shared-context", jobs_dir=tmp_path)


def test_freeze_preserves_concurrency_and_batch_metadata():
    spec = Spec(
        version=1,
        experiment="pkg40-freeze-smoke",
        agent=NopAgentBlock(kind="nop"),
        benchmark={
            "kind": "spider2-dbt",
            "tasks_root": SPIDER2_TASKS,
            "tasks": ["spider2-fixture-001"],
            "batch_mode": "per-task",
        },
        concurrency={"trials": 2},
    )

    frozen = freeze_spec(spec)

    assert "concurrency:" in frozen
    assert "trials: 2" in frozen
    assert "batch_mode: per-task" in frozen
