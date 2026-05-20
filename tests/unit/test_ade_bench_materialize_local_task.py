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
