import json
import os
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


def test_ade_harbor_view_installs_dbt_packages_during_image_build(tmp_path):
    source = tmp_path / "source"
    (source / "environment").mkdir(parents=True)
    (source / "project").mkdir()
    (source / "tests").mkdir()
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
    (source / "instruction.md").write_text("Fix the dbt project.\n")
    (source / "project" / "packages.yml").write_text(
        "packages:\n  - package: dbt-labs/dbt_utils\n    version: 1.3.2\n"
    )
    (source / "tests" / "test-setup.sh").write_text(
        "#!/bin/bash\n"
        "dbt deps\n"
        "dbt run --full-refresh\n"
    )
    (source / "environment" / "Dockerfile").write_text(
        "\n".join(
            [
                "FROM python:3.11-slim",
                "WORKDIR /app",
                "COPY project/ /app/",
                'CMD ["bash"]',
                "",
            ]
        )
    )

    view = materialize_ade_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        task_slug="ade-bench-dbt001",
    )

    dockerfile = (view / "environment" / "Dockerfile").read_text()
    assert "RUN if [ -f /app/packages.yml ]; then cd /app && dbt deps; fi" in dockerfile
    assert dockerfile.index("dbt deps") < dockerfile.index('CMD ["bash"]')

    test_setup = (view / "tests" / "test-setup.sh").read_text()
    assert "reuse image-installed dbt packages" in test_setup
    assert "Skipping dbt deps; dbt_packages already present." in test_setup
    assert "dbt run --full-refresh" in test_setup


def test_ade_harbor_view_injects_workspace_preflight_before_cmd(tmp_path):
    source = tmp_path / "source"
    (source / "environment").mkdir(parents=True)
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
    (source / "environment" / "db_name.txt").write_text("f1\n")
    (source / "environment" / "Dockerfile").write_text(
        "\n".join(
            [
                "FROM python:3.12",
                "WORKDIR /app",
                "RUN touch /app/f1.duckdb",
                'CMD ["bash"]',
                "",
            ]
        )
    )

    view = materialize_ade_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        task_slug="f1001",
    )

    preflight_script = view / "environment" / "razorback_ade_preflight.py"
    assert preflight_script.is_file()
    assert "def preflight_ade_workspace" in preflight_script.read_text()

    dockerfile = (view / "environment" / "Dockerfile").read_text()
    assert (
        "Razorback: validate ADE task-specific DuckDB before agent runtime."
        in dockerfile
    )
    assert (
        "COPY razorback_ade_preflight.py /tmp/razorback_ade_preflight.py"
        in dockerfile
    )
    assert "--task-id f1001" in dockerfile
    assert "--db-name f1" in dockerfile
    assert dockerfile.index("razorback_ade_preflight.py") < dockerfile.index('CMD ["bash"]')


def test_ade_harbor_view_materializes_db_metadata_as_dockerfile_literals(tmp_path):
    source = _write_ade_source_with_db_metadata(
        tmp_path / "source",
        task_db_name="f1",
        drive_file_id="161_e6FoV0rJb2Gp-KhbmbL7u3IMGnQz6",
    )

    view = materialize_ade_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        task_slug="f1001",
    )

    dockerfile = (view / "environment" / "Dockerfile").read_text()
    assert "COPY db_file_id.txt /tmp/db_file_id.txt" not in dockerfile
    assert "COPY db_name.txt /tmp/db_name.txt" not in dockerfile
    assert (
        "Razorback: materialize ADE task metadata from content-specific literals."
        in dockerfile
    )
    assert "161_e6FoV0rJb2Gp-KhbmbL7u3IMGnQz6" in dockerfile
    assert (
        "9679f47d8646ec88913003bb18ac2a94b6a054406d617e000b295023cf7a2450"
        in dockerfile
    )
    assert "gdown" in dockerfile
    assert dockerfile.index("db_file_id.txt;") < dockerfile.index("gdown")


def test_same_size_epoch_mtime_db_metadata_gets_content_specific_build_steps(
    tmp_path,
):
    airbnb_file_id = "1a26gCSe6XadPnd5ZuXpy3OsAv3eOeNSI"
    f1_file_id = "161_e6FoV0rJb2Gp-KhbmbL7u3IMGnQz6"
    assert len(airbnb_file_id) == len(f1_file_id)

    airbnb_source = _write_ade_source_with_db_metadata(
        tmp_path / "airbnb-source",
        task_db_name="airbnb",
        drive_file_id=airbnb_file_id,
    )
    f1_source = _write_ade_source_with_db_metadata(
        tmp_path / "f1-source",
        task_db_name="f1",
        drive_file_id=f1_file_id,
    )
    for path in (
        airbnb_source / "environment" / "db_file_id.txt",
        airbnb_source / "environment" / "db_name.txt",
        f1_source / "environment" / "db_file_id.txt",
        f1_source / "environment" / "db_name.txt",
    ):
        os.utime(path, (0, 0))

    airbnb_view = materialize_ade_harbor_task_view(
        source_task_dir=airbnb_source,
        view_root=tmp_path / "views",
        task_slug="airbnb001",
    )
    f1_view = materialize_ade_harbor_task_view(
        source_task_dir=f1_source,
        view_root=tmp_path / "views",
        task_slug="f1001",
    )

    airbnb_dockerfile = (airbnb_view / "environment" / "Dockerfile").read_text()
    f1_dockerfile = (f1_view / "environment" / "Dockerfile").read_text()
    assert airbnb_file_id in airbnb_dockerfile
    assert airbnb_file_id not in f1_dockerfile
    assert f1_file_id in f1_dockerfile
    assert f1_file_id not in airbnb_dockerfile
    assert "COPY db_file_id.txt /tmp/db_file_id.txt" not in f1_dockerfile


def _write_ade_source_with_db_metadata(
    source: Path, *, task_db_name: str, drive_file_id: str
) -> Path:
    (source / "environment").mkdir(parents=True)
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
    (source / "environment" / "db_file_id.txt").write_text(drive_file_id + "\n")
    (source / "environment" / "db_name.txt").write_text(task_db_name + "\n")
    (source / "environment" / "Dockerfile").write_text(
        "\n".join(
            [
                "FROM python:3.12",
                "WORKDIR /app",
                "COPY db_file_id.txt /tmp/db_file_id.txt",
                "COPY db_name.txt /tmp/db_name.txt",
                "RUN set -eux; \\",
                "    DB_NAME=\"$(tr -d '\\r\\n' < /tmp/db_name.txt)\"; \\",
                "    FILE_ID=\"$(tr -d '\\r\\n' < /tmp/db_file_id.txt)\"; \\",
                (
                    "    gdown \"https://drive.google.com/uc?id=${FILE_ID}\" "
                    "-O \"/app/${DB_NAME}.duckdb\""
                ),
                'CMD ["bash"]',
                "",
            ]
        )
    )
    return source
