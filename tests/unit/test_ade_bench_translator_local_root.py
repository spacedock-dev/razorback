# ABOUTME: PKG-40 AC-1 — retired ade_bench_root local upstream score specs are rejected.

from pathlib import Path

import pytest
from pydantic import ValidationError

from razorback.spec.schema import (
    NopAgentBlock,
    Spec,
)
from razorback.translate import spec_to_job_config

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def test_schema_rejects_ade_bench_root_score_shape() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Spec(
            version=1,
            experiment="pkg40-retired-local-shape",
            agent=NopAgentBlock(kind="nop"),
            benchmark={
                "kind": "ade-bench",
                "tasks_root": ".",
                "ade_bench_root": str(
                    (FIXTURES / "fixture_local_task_minimal").resolve()
                ),
                "tasks": [{"slug": "example001"}],
            },
            trials=1,
            observers=[],
        )
    msg = str(exc_info.value)
    assert "ade_bench_root" in msg
    assert "slug" in msg

def test_harbor_shaped_ade_spec_still_translates(tmp_path: Path) -> None:
    spec = Spec(
        version=1,
        experiment="pkg40-harbor-shaped",
        agent=NopAgentBlock(kind="nop"),
        benchmark={
            "kind": "ade-bench",
            "tasks_root": FIXTURES / "tasks",
            "tasks": ["adebench-fixture-001"],
        },
        trials=1,
        observers=[],
    )
    cfg, _ = spec_to_job_config(spec=spec, job_name="pkg40-ok", jobs_dir=tmp_path)
    assert len(cfg.tasks) == 1
    assert (cfg.tasks[0].path / "view_manifest.json").is_file()
