# ABOUTME: PKG-23 AC-1 + AC-2 — translator-level wiring + gating check that
# ABOUTME: only ade-bench tasks pick up the six T_BENCH_* env keys.

import tomllib
from pathlib import Path

from razorback.spec.schema import (
    AdeBenchBenchmarkBlock,
    AdeBenchLocalTaskEntry,
    NopAgentBlock,
    Spec,
)
from razorback.translate import spec_to_job_config

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def _ade_bench_spec(ade_bench_root: Path) -> Spec:
    return Spec(
        version=1,
        experiment="pkg23-translator-test",
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


def test_translator_materializes_task_toml_with_t_bench_env(tmp_path: Path) -> None:
    """AC-1 translator-level: spec_to_job_config produces a TaskConfig whose
    path's task.toml carries the six T_BENCH_* env keys."""
    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    spec = _ade_bench_spec(ade_bench_root)
    cfg, _ = spec_to_job_config(
        spec=spec,
        job_name="pkg23-test",
        jobs_dir=tmp_path,
        home=tmp_path / "home",
    )
    assert len(cfg.tasks) == 1
    task_toml = tomllib.loads(
        (cfg.tasks[0].path / "task.toml").read_text()
    )
    env = task_toml["environment"]["env"]
    assert "T_BENCH_REPO_ROOT" in env
    assert env["T_BENCH_REPO_ROOT"] == str(ade_bench_root)


def test_harbor_dab_translator_does_not_invoke_ade_bench_materializer() -> None:
    """AC-2 gating: harbor-DAB translator path never reaches
    materialize_local_task / _compute_t_bench_env / mentions T_BENCH_* in its
    body. Structural assertion via source inspection."""
    import razorback.translate as translate_module

    src = Path(translate_module.__file__).read_text()
    dab_body_start = src.index("def _build_harbor_dab")
    rest = src[dab_body_start + 1:]
    next_def = rest.find("\ndef ")
    dab_body_end = (
        dab_body_start + 1 + next_def if next_def != -1 else len(src)
    )
    dab_body = src[dab_body_start:dab_body_end]
    assert "materialize_local_task" not in dab_body
    assert "_compute_t_bench_env" not in dab_body
    assert "T_BENCH_" not in dab_body
