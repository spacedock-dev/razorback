# ABOUTME: PKG-19 AC-1 — translator dispatches to materialize_local_task when
# ABOUTME: ade_bench_root is set on AdeBenchBenchmarkBlock.

from pathlib import Path

import pytest

from razorback.spec.schema import (
    AdeBenchBenchmarkBlock,
    AdeBenchLocalTaskEntry,
    NopAgentBlock,
    Spec,
)
from razorback.translate import spec_to_job_config

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def _spec(ade_bench_root: Path) -> Spec:
    return Spec(
        version=1,
        experiment="pkg19-translator-test",
        agent=NopAgentBlock(kind="nop"),
        benchmark=AdeBenchBenchmarkBlock(
            kind="ade-bench",
            tasks_root=Path("."),
            ade_bench_root=ade_bench_root,
            tasks=[AdeBenchLocalTaskEntry(slug="example001")],
            docker_image_override="ade-bench-agent:latest",
        ),
        trials=1,
        observers=[],
    )


def test_translator_uses_ade_bench_root_when_set(tmp_path: Path) -> None:
    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    spec = _spec(ade_bench_root)
    cfg, _ = spec_to_job_config(
        spec=spec,
        job_name="pkg19-test",
        jobs_dir=tmp_path,
        home=tmp_path / "home",
    )
    assert len(cfg.tasks) == 1
    task_path = cfg.tasks[0].path
    assert (task_path / "task.toml").exists()
    assert "ade-bench" in str(task_path)
    # AC-4 invariant cross-check: the view-dir does NOT expose solution files.
    assert not (task_path / "seeds" / "solution__x.csv").exists()


def test_translator_rejects_local_entry_without_ade_bench_root(tmp_path: Path) -> None:
    spec = Spec(
        version=1,
        experiment="pkg19-translator-noroot",
        agent=NopAgentBlock(kind="nop"),
        benchmark=AdeBenchBenchmarkBlock(
            kind="ade-bench",
            tasks_root=Path("."),
            tasks=[AdeBenchLocalTaskEntry(slug="example001")],
        ),
        trials=1,
        observers=[],
    )
    with pytest.raises(Exception) as exc_info:
        spec_to_job_config(
            spec=spec,
            job_name="pkg19-noroot",
            jobs_dir=tmp_path,
            home=tmp_path / "home",
        )
    msg = str(exc_info.value).lower()
    assert "ade_bench_root" in msg
