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
    assert "Razorback: validate ADE task-specific DuckDB before agent runtime." in dockerfile
    assert "COPY razorback_ade_preflight.py /tmp/razorback_ade_preflight.py" in dockerfile
    assert "--task-id f1001" in dockerfile
    assert "--db-name f1" in dockerfile
    assert dockerfile.index("razorback_ade_preflight.py") < dockerfile.index('CMD ["bash"]')
