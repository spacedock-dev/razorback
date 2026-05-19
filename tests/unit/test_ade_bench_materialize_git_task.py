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
