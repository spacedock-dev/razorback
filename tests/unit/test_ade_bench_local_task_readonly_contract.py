# ABOUTME: PKG-19 AC-3 — synthesized task.toml introduces no agent-RW mounts.
# ABOUTME: Harbor handles `:ro` natively for task volumes; this asserts no escape hatch.

from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def test_synthesized_task_toml_introduces_no_rw_mounts(tmp_path: Path) -> None:
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
    # Negative assertion: shim does NOT inject any [environment.volumes] block
    # and never emits a `:rw` mount mode token.
    assert "[environment.volumes]" not in task_toml
    assert ":rw" not in task_toml
