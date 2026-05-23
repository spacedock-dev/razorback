# ABOUTME: Translator tests for the generic kind: harbor benchmark block.
# ABOUTME: Unit coverage for tasks_root local path + dispatch wiring; live dataset path is integration-marked.

from pathlib import Path

import pytest

from razorback.spec.schema import (
    HarborBenchmarkBlock,
    NopAgentBlock,
    Spec,
)
from razorback.translate import spec_to_job_config


FIXTURE_ADE_TASKS = (
    Path(__file__).parent.parent / "fixtures" / "ade_bench" / "tasks"
)


def _make_spec(*, benchmark: HarborBenchmarkBlock) -> Spec:
    return Spec(
        version=1,
        experiment="harbor-translator-smoke",
        agent=NopAgentBlock(kind="nop"),
        benchmark=benchmark,
        trials=1,
        observers=[],
    )


def test_translator_emits_one_taskconfig_per_local_task(tmp_path):
    """Local tasks_root path: spec entries map 1:1 to TaskConfig(path=...).

    Uses the existing ade-bench-shaped fixture as a Harbor-shaped task
    directory (same task.toml/instruction.md layout). The generic builder
    must NOT apply ADE-specific transforms (image overrides, leakage
    deny-globs) — those stay in `kind: ade-bench`.
    """
    spec = _make_spec(
        benchmark=HarborBenchmarkBlock(
            kind="harbor",
            tasks_root=FIXTURE_ADE_TASKS,
            tasks=["adebench-fixture-001"],
        ),
    )
    job_config, trial_name_map = spec_to_job_config(
        spec, job_name="testjob", jobs_dir=tmp_path
    )
    assert len(job_config.tasks) == 1
    assert job_config.tasks[0].path == FIXTURE_ADE_TASKS / "adebench-fixture-001"
    assert job_config.n_attempts == 1
    assert job_config.n_concurrent_trials == 1
    assert job_config.retry.max_retries == 0
    assert trial_name_map == {}


def test_translator_threads_spec_concurrency(tmp_path):
    spec = _make_spec(
        benchmark=HarborBenchmarkBlock(
            kind="harbor",
            tasks_root=FIXTURE_ADE_TASKS,
            tasks=["adebench-fixture-001"],
        ),
    )
    spec.concurrency.trials = 4
    job_config, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    assert job_config.n_concurrent_trials == 4


def test_translator_respects_n_tasks_cap(tmp_path):
    """n_tasks slices the resolved task list after selectors are applied."""
    spec = _make_spec(
        benchmark=HarborBenchmarkBlock(
            kind="harbor",
            tasks_root=FIXTURE_ADE_TASKS,
            tasks=["adebench-fixture-001", "adebench-fixture-001"],
            n_tasks=1,
        ),
    )
    job_config, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    assert len(job_config.tasks) == 1


def test_translator_respects_exclude_tasks(tmp_path):
    """exclude_tasks filters resolved task list by directory name."""
    spec = _make_spec(
        benchmark=HarborBenchmarkBlock(
            kind="harbor",
            tasks_root=FIXTURE_ADE_TASKS,
            tasks=["adebench-fixture-001"],
            exclude_tasks=["adebench-fixture-001"],
        ),
    )
    job_config, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    assert len(job_config.tasks) == 0


def test_translator_uses_correct_environment_config(tmp_path):
    """Generic builder must thread the spec's environment_config through, same
    as ade-bench / harbor_dab / local builders."""
    spec = _make_spec(
        benchmark=HarborBenchmarkBlock(
            kind="harbor",
            tasks_root=FIXTURE_ADE_TASKS,
            tasks=["adebench-fixture-001"],
        ),
    )
    job_config, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    # environment is populated (not None) — full env-config shape lives in
    # test_translate_spacedock_solver_import_path.py for the agent path.
    assert job_config.environment is not None


def test_translator_rejects_missing_local_task(tmp_path):
    """tasks_root path: missing task dir surfaces as a SpecError so `rk run`
    returns SPEC_ERROR exit code instead of a cryptic FileNotFoundError later."""
    spec = _make_spec(
        benchmark=HarborBenchmarkBlock(
            kind="harbor",
            tasks_root=FIXTURE_ADE_TASKS,
            tasks=["does-not-exist"],
        ),
    )
    with pytest.raises(Exception) as exc:
        spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    msg = str(exc.value).lower()
    assert "does-not-exist" in msg or "not found" in msg


@pytest.mark.integration
def test_translator_resolves_dabstep_via_package_dataset_client(tmp_path):
    """Live integration: resolves adyen/dabstep@latest via PackageDatasetClient,
    confirms one TaskConfig per requested task with downloaded local path.

    Network-dependent; gated behind `integration` marker. ~3s wallclock per
    plan-stage probe.
    """
    spec = _make_spec(
        benchmark=HarborBenchmarkBlock(
            kind="harbor",
            dataset="adyen/dabstep@latest",
            tasks=["35"],
        ),
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="testjob", jobs_dir=tmp_path, home=tmp_path
    )
    assert len(job_config.tasks) == 1
    resolved_path = job_config.tasks[0].path
    assert resolved_path.exists()
    assert (resolved_path / "task.toml").exists()
    assert (resolved_path / "instruction.md").exists()
