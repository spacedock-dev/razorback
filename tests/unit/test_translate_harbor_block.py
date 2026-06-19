# ABOUTME: Translator tests for the generic kind: harbor benchmark block.
# ABOUTME: Unit coverage for harbor-local dispatch wiring; live dataset path is integration-marked.

from pathlib import Path

import pytest

from razorback.spec.schema import (
    HarborBenchmarkBlock,
    HarborLocalBenchmarkBlock,
    NopAgentBlock,
    Spec,
)
from razorback.translate import spec_to_job_config


FIXTURE_ADE_TASKS = (
    Path(__file__).parent.parent / "fixtures" / "ade_bench" / "tasks"
)


def _make_spec(*, benchmark) -> Spec:
    return Spec(
        version=1,
        experiment="harbor-translator-smoke",
        agent=NopAgentBlock(kind="nop"),
        benchmark=benchmark,
        trials=1,
        observers=[],
    )


def test_translator_emits_one_taskconfig_per_local_task(tmp_path):
    """kind: harbor-local: spec entries map 1:1 to TaskConfig(path=...)."""
    spec = _make_spec(
        benchmark=HarborLocalBenchmarkBlock(
            kind="harbor-local",
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
        benchmark=HarborLocalBenchmarkBlock(
            kind="harbor-local",
            tasks_root=FIXTURE_ADE_TASKS,
            tasks=["adebench-fixture-001"],
        ),
    )
    spec.concurrency.trials = 4
    job_config, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    assert job_config.n_concurrent_trials == 4


def test_translator_uses_correct_environment_config(tmp_path):
    spec = _make_spec(
        benchmark=HarborLocalBenchmarkBlock(
            kind="harbor-local",
            tasks_root=FIXTURE_ADE_TASKS,
            tasks=["adebench-fixture-001"],
        ),
    )
    job_config, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    assert job_config.environment is not None


def test_translator_rejects_missing_local_task(tmp_path):
    """harbor-local: missing task dir surfaces as a SpecError so `rk run`
    returns SPEC_ERROR exit code instead of a cryptic FileNotFoundError later."""
    spec = _make_spec(
        benchmark=HarborLocalBenchmarkBlock(
            kind="harbor-local",
            tasks_root=FIXTURE_ADE_TASKS,
            tasks=["does-not-exist"],
        ),
    )
    with pytest.raises(Exception) as exc:
        spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    msg = str(exc.value).lower()
    assert "does-not-exist" in msg or "not found" in msg


# ---- `kind: harbor` (registry) selector coverage --------------------------

def test_harbor_block_respects_n_tasks_cap_after_resolution(tmp_path, monkeypatch):
    """n_tasks slices the resolved task list after registry resolution."""
    fake_dir_a = tmp_path / "task-a"
    fake_dir_b = tmp_path / "task-b"
    for d in (fake_dir_a, fake_dir_b):
        d.mkdir(parents=True)

    def fake_resolver(*, dataset_ref, tasks, cache_root):
        return [fake_dir_a, fake_dir_b]

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks", fake_resolver
    )
    spec = _make_spec(
        benchmark=HarborBenchmarkBlock(
            kind="harbor",
            dataset="adyen/dabstep@latest",
            n_tasks=1,
        ),
    )
    job_config, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    assert len(job_config.tasks) == 1


def test_harbor_block_respects_exclude_tasks_after_resolution(tmp_path, monkeypatch):
    fake_a = tmp_path / "wanted"
    fake_b = tmp_path / "excluded"
    for d in (fake_a, fake_b):
        d.mkdir(parents=True)

    def fake_resolver(*, dataset_ref, tasks, cache_root):
        return [fake_a, fake_b]

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks", fake_resolver
    )
    spec = _make_spec(
        benchmark=HarborBenchmarkBlock(
            kind="harbor",
            dataset="adyen/dabstep@latest",
            exclude_tasks=["excluded"],
        ),
    )
    job_config, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    assert len(job_config.tasks) == 1
    assert job_config.tasks[0].path == fake_a


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


def test_harbor_local_path_writes_no_view_manifest(tmp_path):
    """AC-3: the harbor-local path emits TaskConfig(path=source) and materializes NO view_manifest under tasks_root. Identity on this path must
    keep coming from stratum.json / trial-name parsing, not manifest discovery,
    so the tasks_root reconciliation (direction b) leaves it untouched.
    """
    spec = _make_spec(
        benchmark=HarborLocalBenchmarkBlock(
            kind="harbor-local",
            tasks_root=FIXTURE_ADE_TASKS,
            tasks=["adebench-fixture-001"],
        ),
    )
    job_config, trial_name_map = spec_to_job_config(
        spec, job_name="testjob", jobs_dir=tmp_path
    )
    run_dir = tmp_path / "testjob"
    # Task path points at the source dir, not a materialized view under run_dir/tasks.
    assert job_config.tasks[0].path == FIXTURE_ADE_TASKS / "adebench-fixture-001"
    # No manifests materialized under the shared task-views root (run_dir/tasks).
    tasks_root = run_dir / "tasks"
    manifests = list(tasks_root.glob("*/view_manifest.json")) if tasks_root.is_dir() else []
    assert manifests == []
    # Generic path leaves the per-query rewiring map empty (no spider2 wiring).
    assert trial_name_map == {}
