# ABOUTME: PKG-19 AC-5 — materialize_mode={bind,copy} selects view-dir vs full copy.
# ABOUTME: Both modes enforce AC-4 (no solution__*.csv leaks into the agent view-dir).

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def test_materialize_copy_mode_full_copy(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
        materialize_mode="copy",
    )
    for p in materialized.rglob("*"):
        if p.is_symlink():
            pytest.fail(f"copy mode must not produce symlinks; found {p}")
    # AC-4 still holds in copy mode.
    assert not (materialized / "seeds" / "solution__x.csv").exists()
    # Real seed file is copied.
    assert (materialized / "seeds" / "_no-op.txt").exists()


def test_materialize_bind_mode_uses_symlinks(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
        materialize_mode="bind",
    )
    setup = materialized / "setup.sh"
    assert setup.is_symlink(), "bind mode must produce symlinks for upstream files"
