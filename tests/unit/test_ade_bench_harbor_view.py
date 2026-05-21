import json
import tomllib
from pathlib import Path

from razorback.benchmarks.ade_bench.harbor_view import materialize_ade_harbor_task_view


FIXTURE_TASKS = Path(__file__).parent.parent / "fixtures" / "ade_bench" / "tasks"


def test_ade_harbor_view_uses_generic_manifest_shape(tmp_path):
    view = materialize_ade_harbor_task_view(
        source_task_dir=FIXTURE_TASKS / "adebench-fixture-001",
        view_root=tmp_path / "views",
        task_slug="adebench-fixture-001",
        docker_image="shared-dbt-duckdb:latest",
    )

    manifest = json.loads((view / "view_manifest.json").read_text())
    assert manifest["benchmark_kind"] == "ade-bench"
    assert manifest["benchmark_task_id"] == "adebench-fixture-001"
    assert manifest["transform_name"] == "ade-bench-harbor-task-view"

    task_toml = tomllib.loads((view / "task.toml").read_text())
    assert task_toml["environment"]["docker_image"] == "shared-dbt-duckdb:latest"
    assert task_toml["environment"]["env"]["RAZORBACK_BENCHMARK_KIND"] == "ade-bench"
    assert (
        task_toml["environment"]["env"]["RAZORBACK_BENCHMARK_TASK_ID"]
        == "adebench-fixture-001"
    )
