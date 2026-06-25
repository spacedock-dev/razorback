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


def test_link_mode_symlinks_files_but_never_mutates_source_task_toml(tmp_path):
    """`view_mode="link"` must symlink the bulk task tree (the whole point of
    bind mode: no eager duplication of large trees) yet keep `task.toml`
    view-owned. Patching env/docker into a symlinked task.toml would otherwise
    follow the link and corrupt the SHARED source fixture, leaking the
    injected benchmark env back into the source on disk.
    """
    source = _write_source_task(tmp_path)
    source_toml_before = (source / "task.toml").read_text()

    view = materialize_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        benchmark_kind="fixture-bench",
        benchmark_task_id="task-001",
        transform_name="fixture-transform",
        environment_env={"RAZORBACK_BENCHMARK_TASK_ID": "task-001"},
        view_mode="link",
    )

    # bulk files are symlinks (no copy) — that is the bind/link contract
    assert (view / "instruction.md").is_symlink()
    assert (view / "data" / "input.csv").is_symlink()
    # but the patched task.toml is a real, view-owned file (not a symlink)
    assert (view / "task.toml").is_file()
    assert not (view / "task.toml").is_symlink()
    # the view carries the injected env
    task_toml = tomllib.loads((view / "task.toml").read_text())
    assert task_toml["environment"]["env"]["RAZORBACK_BENCHMARK_TASK_ID"] == "task-001"
    # and the SOURCE task.toml is byte-for-byte unchanged
    assert (source / "task.toml").read_text() == source_toml_before
    assert "RAZORBACK_BENCHMARK_TASK_ID" not in (source / "task.toml").read_text()


def test_link_mode_copies_environment_build_context_as_real_files(tmp_path):
    """`view_mode="link"` must keep the `environment/` Docker build context as
    REAL files, not symlinks. `docker compose build` runs with the view's
    `environment/` dir as the build context; BuildKit cannot read a Dockerfile
    that symlinks outside the context (`failed to read dockerfile: no such file
    or directory`), so a symlinked build context breaks every build-from-source
    benchmark (e.g. swe-bench-pro) under the default bind/link mode. Bulk task
    files still symlink — only the build context is forced real.
    """
    source = _write_source_task(tmp_path)
    dockerfile_text = (source / "environment" / "Dockerfile").read_text()

    view = materialize_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        benchmark_kind="fixture-bench",
        benchmark_task_id="task-001",
        transform_name="fixture-transform",
        view_mode="link",
    )

    # the Docker build context is a real, view-owned file (readable by BuildKit)
    assert (view / "environment" / "Dockerfile").is_file()
    assert not (view / "environment" / "Dockerfile").is_symlink()
    assert (view / "environment" / "Dockerfile").read_text() == dockerfile_text
    # bulk files outside environment/ still symlink — the bind/link contract holds
    assert (view / "instruction.md").is_symlink()
    assert (view / "data" / "input.csv").is_symlink()


def test_environment_symlink_to_denied_target_is_not_smuggled(tmp_path):
    """A symlink under `environment/` with an innocuous name must not smuggle a
    DENIED target's bytes into the view. Copying the build context follows
    symlinks (shutil.copy2), and the name-based deny filter only sees the link's
    own path — so `environment/leak.patch -> ../gold_patch.diff` would otherwise
    embed gold-patch content under an allowed view path. The materializer must
    resolve the target and re-apply the deny check, dropping it.
    """
    source = _write_source_task(tmp_path)
    (source / "gold_patch.diff").write_text("--- GOLD ANSWER PATCH ---\n")
    (source / "environment" / "leak.patch").symlink_to(source / "gold_patch.diff")

    view = materialize_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        benchmark_kind="fixture-bench",
        benchmark_task_id="task-001",
        transform_name="fixture-transform",
        exclude_globs=("gold_patch*", "gold.patch"),
        view_mode="link",
    )

    # the legit build context is still materialized as a real file …
    assert (view / "environment" / "Dockerfile").is_file()
    assert not (view / "environment" / "Dockerfile").is_symlink()
    # … but the disguised symlink to a denied target is dropped, not embedded
    assert not (view / "environment" / "leak.patch").exists()


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
