# ABOUTME: PKG-19 AC-6 — missing or empty ade_bench_root fails fast with clear error.

from pathlib import Path

import pytest


def test_missing_ade_bench_root_raises(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    missing_root = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError) as exc_info:
        materialize_local_task(
            ade_bench_root=missing_root,
            task_slug="example001",
            docker_image="ade-bench-agent:latest",
            cache_root=tmp_path / "cache",
        )
    assert "does_not_exist" in str(exc_info.value) or "example001" in str(exc_info.value)


def test_empty_ade_bench_root_raises(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    empty_root = tmp_path / "empty_root"
    empty_root.mkdir()
    with pytest.raises(FileNotFoundError) as exc_info:
        materialize_local_task(
            ade_bench_root=empty_root,
            task_slug="example001",
            docker_image="ade-bench-agent:latest",
            cache_root=tmp_path / "cache",
        )
    assert "example001" in str(exc_info.value)
