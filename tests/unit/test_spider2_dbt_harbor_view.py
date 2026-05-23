import json
import tomllib
from pathlib import Path

from razorback.benchmarks.spider2_dbt.harbor_view import (
    materialize_spider2_harbor_task_view,
)
from razorback.spec.schema import Spider2DbtBenchmarkBlock


FIXTURE_TASKS = (
    Path(__file__).parent.parent
    / "fixtures"
    / "spider2_dbt"
    / "harbor_task_minimal"
)


def test_spider2_schema_defaults_to_per_task():
    block = Spider2DbtBenchmarkBlock(
        kind="spider2-dbt",
        tasks_root=FIXTURE_TASKS,
        tasks=["spider2-fixture-001"],
    )
    assert block.batch_mode == "per-task"


def test_spider2_harbor_view_uses_generic_manifest_shape(tmp_path):
    view = materialize_spider2_harbor_task_view(
        source_task_dir=FIXTURE_TASKS / "spider2-fixture-001",
        view_root=tmp_path / "views",
        task_slug="spider2-fixture-001",
        docker_image="shared-dbt-duckdb:latest",
    )

    assert (view / "dbt_project" / "models" / "example.sql").is_file()
    assert not (view / "solution" / "solve.sh").exists()
    assert not (view / "tests" / "expected" / "answer.txt").exists()

    manifest = json.loads((view / "view_manifest.json").read_text())
    assert manifest["benchmark_kind"] == "spider2-dbt"
    assert manifest["benchmark_task_id"] == "spider2-fixture-001"
    assert manifest["transform_name"] == "spider2-dbt-harbor-task-view"

    task_toml = tomllib.loads((view / "task.toml").read_text())
    assert task_toml["environment"]["docker_image"] == "shared-dbt-duckdb:latest"
    assert (
        task_toml["environment"]["env"]["RAZORBACK_BENCHMARK_KIND"]
        == "spider2-dbt"
    )
