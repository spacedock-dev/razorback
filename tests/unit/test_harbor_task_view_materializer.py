import json
import tomllib
from pathlib import Path

from harbor.models.trial.config import TaskConfig

from razorback.harbor_tasks.materialize import materialize_harbor_task_view


def _write_source_task(root: Path) -> Path:
    source = root / "source"
    (source / "environment").mkdir(parents=True)
    (source / "tests").mkdir()
    (source / "solution").mkdir()
    (source / "data").mkdir()
    (source / "task.toml").write_text(
        "\n".join(
            [
                'schema_version = "1.2"',
                "",
                "[task]",
                'name = "fixture/source-task"',
                "",
                "[environment]",
                'docker_image = "source-image:latest"',
                "cpus = 1",
                "memory_mb = 2048",
                "",
            ]
        )
    )
    (source / "instruction.md").write_text("Repair the dbt model.\n")
    (source / "environment" / "Dockerfile").write_text("FROM python:3.12\n")
    (source / "tests" / "test.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (source / "solution" / "solve.sh").write_text("echo secret\n")
    (source / "data" / "input.csv").write_text("id,value\n1,a\n")
    (source / "data" / "answers.csv").write_text("id,answer\n1,secret\n")
    return source


def test_materializer_patches_task_toml_and_manifest(tmp_path):
    source = _write_source_task(tmp_path)

    view = materialize_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        benchmark_kind="fixture-bench",
        benchmark_task_id="task-001",
        transform_name="fixture-transform",
        docker_image="shared-dbt-duckdb:latest",
        environment_env={"RAZORBACK_BENCHMARK_TASK_ID": "task-001"},
        resource_overrides={"cpus": 2, "memory_mb": 4096},
    )

    assert (view / "task.toml").is_file()
    assert (view / "instruction.md").is_file()
    assert (view / "environment" / "Dockerfile").is_file()
    assert (view / "tests" / "test.sh").is_file()
    assert (view / "data" / "input.csv").is_file()

    task_toml = tomllib.loads((view / "task.toml").read_text())
    assert task_toml["environment"]["docker_image"] == "shared-dbt-duckdb:latest"
    assert task_toml["environment"]["env"]["RAZORBACK_BENCHMARK_TASK_ID"] == "task-001"
    assert task_toml["environment"]["cpus"] == 2
    assert task_toml["environment"]["memory_mb"] == 4096

    manifest = json.loads((view / "view_manifest.json").read_text())
    assert manifest["source_task_dir"] == str(source.resolve())
    assert manifest["source_checksums"]["task.toml"].startswith("sha256:")
    assert manifest["benchmark_kind"] == "fixture-bench"
    assert manifest["benchmark_task_id"] == "task-001"
    assert manifest["transform_name"] == "fixture-transform"
    assert manifest["view_mode"] == "copy"
    assert manifest["environment_overrides"]["docker_image_tag"] == "shared-dbt-duckdb:latest"
    assert manifest["environment_overrides"]["resources"]["cpus"] == 2


def test_materialized_view_is_harbor_taskconfig_path_ready(tmp_path):
    source = _write_source_task(tmp_path)

    view = materialize_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        benchmark_kind="fixture-bench",
        benchmark_task_id="task-001",
        transform_name="fixture-transform",
    )

    task_config = TaskConfig(path=view)
    assert task_config.get_local_path() == view.resolve()
    assert task_config.get_task_id().get_name() == view.name
