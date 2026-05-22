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


def test_ade_harbor_view_keeps_verifier_solution_seeds(tmp_path):
    source = tmp_path / "source"
    (source / "environment").mkdir(parents=True)
    (source / "seeds").mkdir()
    (source / "tests" / "seeds").mkdir(parents=True)
    (source / "task.toml").write_text(
        "\n".join(
            [
                'schema_version = "1.0"',
                "[environment]",
                'os = "linux"',
                "cpus = 1",
                "memory_mb = 1024",
                "storage_mb = 1024",
                "",
            ]
        )
    )
    (source / "environment" / "Dockerfile").write_text("FROM python:3.11-slim\n")
    (source / "seeds" / "solution__x.csv").write_text("secret\n")
    (source / "tests" / "seeds" / "solution__x.csv").write_text("expected\n")

    view = materialize_ade_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        task_slug="ade-bench-custom001",
    )

    assert not (view / "seeds" / "solution__x.csv").exists()
    assert (view / "tests" / "seeds" / "solution__x.csv").read_text() == "expected\n"
