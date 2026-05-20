# ABOUTME: PKG-19 AC-1/AC-2/AC-4 — materialize_local_task builds a view-dir from ade_bench_root
# ABOUTME: with synthesized task.toml + symlinked artifacts, excluding seeds/solution__*.csv.

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def test_materialize_local_task_emits_task_toml(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    task_toml = (materialized / "task.toml").read_text()
    assert 'docker_image = "ade-bench-agent:latest"' in task_toml
    assert "[environment]" in task_toml
    # The instruction text comes from prompts[0].prompt in the upstream yaml.
    instruction_md = (materialized / "instruction.md").read_text()
    assert "Do the example task." in instruction_md


def test_materialize_local_task_does_not_clone(tmp_path: Path, monkeypatch) -> None:
    """AC-1: no git operations during local materialization."""
    from razorback.benchmarks.ade_bench import tasks as ade_tasks

    def _fail(*a, **kw):
        raise AssertionError(
            "AC-1: materialize_local_task must NOT invoke harbor's git fetch"
        )

    # Defend against accidental wiring back into TaskClient.
    monkeypatch.setattr(ade_tasks, "_run_async", _fail, raising=False)

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = ade_tasks.materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    assert (materialized / "task.toml").exists()


def test_view_dir_disk_footprint_under_10mb(tmp_path: Path) -> None:
    """AC-2: per-task view-dir is ≤ 10 MB excluding symlink targets."""
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )

    total_bytes = 0
    for p in materialized.rglob("*"):
        if p.is_symlink():
            continue
        if p.is_file():
            total_bytes += p.stat().st_size
    assert total_bytes < 10 * 1024 * 1024, (
        f"AC-2: per-task view-dir must be ≤ 10 MB (excluding symlinks); "
        f"got {total_bytes} bytes"
    )


def test_view_dir_excludes_solution_csv_files(tmp_path: Path) -> None:
    """AC-4: solution__*.csv files must NOT be reachable from the view-dir."""
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    seeds_dir = materialized / "seeds"
    assert seeds_dir.exists(), "seeds/ must be reflected (for non-solution files)"
    solution_files = list(seeds_dir.glob("solution__*.csv"))
    assert solution_files == [], (
        f"AC-4: view-dir must not expose solution files; got {solution_files}"
    )
    # Other seed files (e.g., _no-op.txt) remain accessible.
    assert (seeds_dir / "_no-op.txt").exists()


def test_view_dir_solution_files_not_reachable_via_symlink_chain(tmp_path: Path) -> None:
    """AC-4 invariant: even if seeds/ is a symlink, following it must not
    yield solution files (i.e., seeds/ is NOT a whole-dir symlink to
    ade_bench_root when the dir contains excluded files)."""
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    seeds_dir = materialized / "seeds"
    assert not seeds_dir.is_symlink(), (
        "AC-4: seeds/ must be a real directory (with selective symlinks), "
        "NOT a symlink to ade_bench_root's seeds/"
    )


def test_view_dir_whole_dir_symlink_when_no_excluded_files(tmp_path: Path) -> None:
    """When a subdirectory has no excluded files, the materializer may
    whole-dir symlink for performance (or copy; behavior is implementation-
    defined). This test confirms `tests/` is reflected either way."""
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    tests_dir = materialized / "tests"
    assert tests_dir.exists()
    assert tests_dir.is_dir() or tests_dir.is_symlink()


def test_ade_bench_root_seeds_remain_unfiltered(tmp_path: Path) -> None:
    """AC-4 invariant: solution__*.csv files are EXCLUDED from the agent
    view-dir, but REMAIN on the host filesystem under ade_bench_root for
    the verifier's separate mount."""
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    upstream_seeds = ade_bench_root / "tasks" / "example001" / "seeds"
    assert (upstream_seeds / "solution__x.csv").exists()
