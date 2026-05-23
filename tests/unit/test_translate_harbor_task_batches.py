import json
from pathlib import Path

import pytest

from razorback.errors import SpecError
from razorback.spec.schema import NopAgentBlock, Spec, Spider2DbtBenchmarkBlock
from razorback.translate import spec_to_job_config


ADE_TASKS = Path(__file__).parent.parent / "fixtures" / "ade_bench" / "tasks"
SPIDER2_TASKS = (
    Path(__file__).parent.parent
    / "fixtures"
    / "spider2_dbt"
    / "harbor_task_minimal"
)


def test_ade_batch_materializes_one_view_per_task(tmp_path):
    spec = Spec(
        version=1,
        experiment="pkg40-ade-batch",
        agent=NopAgentBlock(kind="nop"),
        benchmark={
            "kind": "ade-bench",
            "tasks_root": ADE_TASKS,
            "tasks": ["adebench-fixture-001"],
        },
        concurrency={"trials": 2},
    )

    job_config, _ = spec_to_job_config(spec, job_name="batch", jobs_dir=tmp_path)

    assert job_config.n_concurrent_trials == 2
    assert len(job_config.tasks) == 1
    manifest = json.loads((job_config.tasks[0].path / "view_manifest.json").read_text())
    assert manifest["benchmark_task_id"] == "adebench-fixture-001"


def test_spider2_batch_materializes_one_view_per_task(tmp_path):
    spec = Spec(
        version=1,
        experiment="pkg40-spider2-batch",
        agent=NopAgentBlock(kind="nop"),
        benchmark=Spider2DbtBenchmarkBlock(
            kind="spider2-dbt",
            tasks_root=SPIDER2_TASKS,
            tasks=["spider2-fixture-001"],
        ),
        concurrency={"trials": 3},
    )

    job_config, _ = spec_to_job_config(spec, job_name="batch", jobs_dir=tmp_path)

    assert job_config.n_concurrent_trials == 3
    assert len(job_config.tasks) == 1
    manifest = json.loads((job_config.tasks[0].path / "view_manifest.json").read_text())
    assert manifest["benchmark_kind"] == "spider2-dbt"
    assert manifest["benchmark_task_id"] == "spider2-fixture-001"


def test_shared_context_batch_mode_fails_closed(tmp_path):
    spec = Spec(
        version=1,
        experiment="pkg40-shared-context",
        agent=NopAgentBlock(kind="nop"),
        benchmark={
            "kind": "spider2-dbt",
            "tasks_root": SPIDER2_TASKS,
            "tasks": ["spider2-fixture-001"],
            "batch_mode": "shared-context",
        },
    )

    with pytest.raises(SpecError, match="shared-context"):
        spec_to_job_config(spec, job_name="shared", jobs_dir=tmp_path)
