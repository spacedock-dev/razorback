# ABOUTME: FU-2 AC-1 — materialize_git_task rewrites docker_image in fetched task.toml.
# ABOUTME: Covers REPLACE (existing line) and INSERT (no line) paths; source untouched.

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def test_rewrite_replaces_existing_docker_image(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_git_task

    source = (FIXTURES / "fixture_git_task_with_image").resolve()
    target_root = tmp_path / "fu2-cache"
    materialized = materialize_git_task(
        git_url="file://" + str(source),
        git_commit_id="deadbeef" * 5,
        source_path=Path("fixture_git_task_with_image"),
        docker_image="dab-agent:latest",
        cache_root=target_root,
        _fake_git_source=source,
    )
    task_toml = (materialized / "task.toml").read_text()
    assert 'docker_image = "dab-agent:latest"' in task_toml
    assert 'docker_image = "some-other-image:tag"' not in task_toml
    # Original source file UNTOUCHED (full bytewise assert in Task 4).
    original = (source / "task.toml").read_text()
    assert 'docker_image = "some-other-image:tag"' in original


def test_rewrite_inserts_docker_image_when_missing(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_git_task

    source = (FIXTURES / "fixture_git_task_no_image").resolve()
    target_root = tmp_path / "fu2-cache"
    materialized = materialize_git_task(
        git_url="file://" + str(source),
        git_commit_id="cafebabe" * 5,
        source_path=Path("fixture_git_task_no_image"),
        docker_image="dab-agent:latest",
        cache_root=target_root,
        _fake_git_source=source,
    )
    task_toml = (materialized / "task.toml").read_text()
    assert 'docker_image = "dab-agent:latest"' in task_toml
    # Other [environment] fields preserved verbatim.
    assert "build_timeout_sec = 900.0" in task_toml
    assert "cpus = 1" in task_toml
    assert "memory_mb = 4096" in task_toml
    # Other tables preserved verbatim.
    assert "[verifier.env]" in task_toml
    assert 'DB_TYPE = "duckdb"' in task_toml
    # Insertion lands inside [environment], NOT inside [verifier.env] or
    # [solution.env]. Assert ordering: [environment] precedes docker_image
    # precedes [verifier.env].
    env_idx = task_toml.index("[environment]")
    img_idx = task_toml.index('docker_image = "dab-agent:latest"')
    ver_env_idx = task_toml.index("[verifier.env]")
    assert env_idx < img_idx < ver_env_idx


def test_materialized_dir_matches_harbor_shortuuid_layout(tmp_path: Path) -> None:
    """Sanity: target_dir = cache_root / shortuuid(str(GitTaskId)) / path.name.

    Catches future harbor changes to the cache-path formula.
    """
    import shortuuid
    from harbor.models.task.id import GitTaskId

    from razorback.benchmarks.ade_bench.tasks import materialize_git_task

    source = (FIXTURES / "fixture_git_task_with_image").resolve()
    cache_root = tmp_path / "fu2-cache"
    materialized = materialize_git_task(
        git_url="file://" + str(source),
        git_commit_id="deadbeef" * 5,
        source_path=Path("fixture_git_task_with_image"),
        docker_image="dab-agent:latest",
        cache_root=cache_root,
        _fake_git_source=source,
    )
    task_id = GitTaskId(
        git_url="file://" + str(source),
        git_commit_id="deadbeef" * 5,
        path=Path("fixture_git_task_with_image"),
    )
    expected = cache_root / shortuuid.uuid(str(task_id)) / "fixture_git_task_with_image"
    assert materialized == expected


def test_source_task_toml_unchanged_after_materialization(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_git_task

    source = (FIXTURES / "fixture_git_task_with_image").resolve()
    original_bytes = (source / "task.toml").read_bytes()
    original_dockerfile = (source / "environment" / "Dockerfile").read_bytes()
    materialize_git_task(
        git_url="file://" + str(source),
        git_commit_id="deadbeef" * 5,
        source_path=Path("fixture_git_task_with_image"),
        docker_image="dab-agent:latest",
        cache_root=tmp_path / "fu2-cache",
        _fake_git_source=source,
    )
    assert (source / "task.toml").read_bytes() == original_bytes
    assert (
        (source / "environment" / "Dockerfile").read_bytes() == original_dockerfile
    )


def test_two_materializations_with_different_overrides_dont_drift_source(
    tmp_path: Path,
) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_git_task

    source = (FIXTURES / "fixture_git_task_no_image").resolve()
    original_bytes = (source / "task.toml").read_bytes()
    for image in ("dab-agent:latest", "custom-agent:v2"):
        materialize_git_task(
            git_url="file://" + str(source),
            git_commit_id="cafebabe" * 5,
            source_path=Path("fixture_git_task_no_image"),
            docker_image=image,
            cache_root=tmp_path / f"cache-{image.split(':')[0]}",
            _fake_git_source=source,
        )
    assert (source / "task.toml").read_bytes() == original_bytes
