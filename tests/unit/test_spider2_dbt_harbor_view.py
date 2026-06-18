from __future__ import annotations

from pathlib import Path

from razorback.benchmarks.spider2_dbt.harbor_view import (
    _DBT_PROJECT_DIRNAME,
    SPIDER2_DBT_DENY_GLOBS,
    materialize_spider2_harbor_task_view,
)
from razorback.harbor_tasks.leakage import DEFAULT_SOLUTION_DENY_GLOBS


_TASK_TOML = "\n".join(
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


def _write_source(
    source: Path,
    *,
    with_packages: bool,
    with_duckdb: bool,
    dockerfile_lines: list[str] | None = None,
) -> Path:
    (source / "environment").mkdir(parents=True)
    (source / "dbt_project" / "models").mkdir(parents=True)
    (source / "task.toml").write_text(_TASK_TOML)
    (source / "instruction.md").write_text("Fix the dbt project.\n")
    (source / "dbt_project" / "dbt_project.yml").write_text(
        "name: example\nprofile: example\n"
    )
    (source / "dbt_project" / "models" / "example.sql").write_text("select 1\n")
    if with_packages:
        (source / "dbt_project" / "packages.yml").write_text(
            "packages:\n  - package: dbt-labs/dbt_utils\n    version: 1.3.2\n"
        )
    if with_duckdb:
        import duckdb

        db = source / "dbt_project" / "spider2-fixture-001.duckdb"
        conn = duckdb.connect(str(db))
        try:
            conn.execute("CREATE TABLE orders (id INTEGER)")
        finally:
            conn.close()
    lines = dockerfile_lines or [
        "FROM python:3.12",
        "WORKDIR /app",
        'CMD ["bash"]',
        "",
    ]
    (source / "environment" / "Dockerfile").write_text("\n".join(lines))
    return source


# --- AC-1: dbt-deps image layer -------------------------------------------


def test_spider2_view_installs_dbt_packages_when_packages_yml_present(tmp_path):
    source = _write_source(
        tmp_path / "source", with_packages=True, with_duckdb=True
    )

    view = materialize_spider2_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        task_slug="spider2-fixture-001",
    )

    dockerfile = (view / "environment" / "Dockerfile").read_text()
    assert (
        "Razorback: install declared dbt packages before agent runtime."
        in dockerfile
    )
    assert (
        "RUN if [ -f /app/packages.yml ]; then cd /app && dbt deps; fi"
        in dockerfile
    )
    assert dockerfile.index("dbt deps") < dockerfile.index('CMD ["bash"]')


def test_spider2_view_omits_dbt_deps_layer_when_no_packages_yml(tmp_path):
    source = _write_source(
        tmp_path / "source", with_packages=False, with_duckdb=True
    )

    view = materialize_spider2_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        task_slug="spider2-fixture-001",
    )

    dockerfile = (view / "environment" / "Dockerfile").read_text()
    assert "install declared dbt packages" not in dockerfile
    assert "dbt deps" not in dockerfile


# --- AC-2 (image side): preflight build layer ------------------------------


def test_spider2_view_injects_workspace_preflight_before_cmd(tmp_path):
    source = _write_source(
        tmp_path / "source", with_packages=True, with_duckdb=True
    )

    view = materialize_spider2_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        task_slug="spider2-fixture-001",
    )

    preflight_script = view / "environment" / "razorback_spider2_preflight.py"
    assert preflight_script.is_file()
    assert "def preflight_spider2_workspace" in preflight_script.read_text()

    dockerfile = (view / "environment" / "Dockerfile").read_text()
    assert (
        "Razorback: validate spider2-dbt source DuckDB before agent runtime."
        in dockerfile
    )
    assert (
        "COPY razorback_spider2_preflight.py /tmp/razorback_spider2_preflight.py"
        in dockerfile
    )
    assert "--task-id spider2-fixture-001" in dockerfile
    assert "--workspace /app" in dockerfile
    assert dockerfile.index("razorback_spider2_preflight.py") < dockerfile.index(
        'CMD ["bash"]'
    )


# --- RIDER (Codex finding 2, mandatory) ------------------------------------
# The preflight RUN must NOT be able to fail on a missing dbt project: this
# entity owns landing dbt_project/ + the source .duckdb at /app BEFORE the
# preflight RUN, proven at BUILD-CONTEXT level (the files the COPY references
# are actually present in the environment/ build context), not by text
# inspection alone.


def test_preflight_build_context_holds_duckdb_before_preflight_run(tmp_path):
    source = _write_source(
        tmp_path / "source", with_packages=True, with_duckdb=True
    )

    view = materialize_spider2_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        task_slug="spider2-fixture-001",
    )

    environment = view / "environment"
    dockerfile_text = (environment / "Dockerfile").read_text()
    lines = dockerfile_text.splitlines()

    # Find the COPY that lands the dbt project (incl. the .duckdb) at /app and
    # the preflight RUN. The COPY must precede the preflight RUN.
    copy_app_idx = next(
        i
        for i, ln in enumerate(lines)
        if ln.strip().startswith("COPY ") and ln.strip().rstrip().endswith("/app/")
    )
    preflight_run_idx = next(
        i
        for i, ln in enumerate(lines)
        if "razorback_spider2_preflight.py" in ln and ln.strip().startswith("RUN ")
    )
    assert copy_app_idx < preflight_run_idx

    # BUILD-CONTEXT proof: the path the /app COPY references must exist as a
    # real entry inside the environment/ build context, and it must contain
    # the source .duckdb. Parse the COPY source path from the Dockerfile and
    # resolve it against the build context root (environment/).
    copy_line = lines[copy_app_idx].strip()
    # form: COPY <src> /app/
    parts = copy_line.split()
    assert parts[0] == "COPY"
    assert parts[-1] == "/app/"
    copy_src = parts[1]
    staged = environment / copy_src
    assert staged.exists(), f"build context missing COPY source: {copy_src}"
    duckdbs = list(staged.rglob("*.duckdb"))
    assert duckdbs, (
        "no .duckdb staged into the build context under "
        f"{copy_src}; preflight RUN --workspace /app could fail on a "
        "missing DuckDB"
    )


def test_preflight_layer_absent_when_not_a_dbt_project(tmp_path):
    # A non-dbt source (no dbt_project/) gets no preflight layer at all, so the
    # preflight RUN can never run against an empty /app.
    source = tmp_path / "source"
    (source / "environment").mkdir(parents=True)
    (source / "task.toml").write_text(_TASK_TOML)
    (source / "environment" / "Dockerfile").write_text(
        "FROM python:3.12\nCMD [\"bash\"]\n"
    )

    view = materialize_spider2_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        task_slug="plain-001",
    )

    dockerfile = (view / "environment" / "Dockerfile").read_text()
    assert "razorback_spider2_preflight.py" not in dockerfile
    assert not (view / "environment" / "razorback_spider2_preflight.py").exists()


# --- AC-3: deny-glob lock --------------------------------------------------


def test_spider2_view_excludes_gold_solution_expected_paths(tmp_path):
    source = _write_source(
        tmp_path / "source", with_packages=False, with_duckdb=False
    )
    (source / "gold").mkdir()
    (source / "gold" / "answer.sql").write_text("select 'gold';\n")
    (source / "golden").mkdir()
    (source / "golden" / "result.txt").write_text("golden output\n")
    (source / "tests" / "expected").mkdir(parents=True)
    (source / "tests" / "expected" / "expected.csv").write_text("id\n1\n")
    (source / "expected").mkdir()
    (source / "expected" / "answer.txt").write_text("answer\n")
    (source / "solution").mkdir()
    (source / "solution" / "solve.sh").write_text("#!/bin/bash\n")

    view = materialize_spider2_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        task_slug="spider2-fixture-001",
    )

    assert not (view / "gold" / "answer.sql").exists()
    assert not (view / "golden" / "result.txt").exists()
    assert not (view / "tests" / "expected" / "expected.csv").exists()
    assert not (view / "expected" / "answer.txt").exists()
    assert not (view / "solution" / "solve.sh").exists()


def test_spider2_deny_globs_cover_required_families():
    assert {"gold/**", "expected/**", "golden/**"} <= set(SPIDER2_DBT_DENY_GLOBS)
    assert set(DEFAULT_SOLUTION_DENY_GLOBS) <= set(SPIDER2_DBT_DENY_GLOBS)


# --- REGRESSION: link mode must never mutate the source Dockerfile ---------
# Mirrors test_link_mode_symlinks_files_but_never_mutates_source_task_toml.
# Under `view_mode="link"` the reflected environment/Dockerfile is a symlink
# back into the shared source tree; the three image-layer helpers each call
# `dockerfile.write_text(...)`, which would FOLLOW the symlink and corrupt the
# version-controlled source (and leak idempotency markers, suppressing layer
# injection on later runs). Each helper must unlink the symlink before writing
# so the view owns a real file.


def test_link_mode_injects_layers_but_never_mutates_source_dockerfile(tmp_path):
    source = _write_source(
        tmp_path / "source", with_packages=True, with_duckdb=True
    )
    source_dockerfile = source / "environment" / "Dockerfile"
    source_dockerfile_before = source_dockerfile.read_text()

    view = materialize_spider2_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        task_slug="spider2-fixture-001",
        view_mode="link",
    )

    # The view's Dockerfile is a real, view-owned file (not a symlink) and
    # carries all three injected layers.
    view_dockerfile = view / "environment" / "Dockerfile"
    assert view_dockerfile.is_file()
    assert not view_dockerfile.is_symlink()
    view_text = view_dockerfile.read_text()
    assert "Razorback: install declared dbt packages before agent runtime." in view_text
    assert "Razorback: validate spider2-dbt source DuckDB before agent runtime." in view_text
    assert f"COPY {_DBT_PROJECT_DIRNAME}/ /app/" in view_text

    # The SOURCE Dockerfile is byte-for-byte unchanged — no write followed the
    # symlink, and no idempotency marker leaked back into the source.
    assert source_dockerfile.read_text() == source_dockerfile_before
    assert "Razorback:" not in source_dockerfile.read_text()
