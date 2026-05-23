# ABOUTME: AC-3 RISKIEST CONTRACT — ade-bench spec → JobConfig translator (§6.1).
# ABOUTME: Translates a benchmark.kind=ade-bench spec into one TaskConfig per task slug.

from pathlib import Path

import json

import pytest

from razorback.spec.schema import (
    AdeBenchBenchmarkBlock,
    NopAgentBlock,
    Spec,
)
from razorback.translate import spec_to_job_config

FIXTURE_TASKS = Path(__file__).parent.parent / "fixtures" / "ade_bench" / "tasks"


def _make_spec(slug: str) -> Spec:
    return Spec(
        version=1,
        experiment="ade-bench-translator-smoke",
        agent=NopAgentBlock(kind="nop"),
        benchmark=AdeBenchBenchmarkBlock(
            kind="ade-bench",
            tasks_root=FIXTURE_TASKS,
            tasks=[slug],
        ),
        trials=1,
        observers=[],
    )


def test_translator_emits_one_taskconfig_per_slug(tmp_path):
    spec = _make_spec("adebench-fixture-001")
    job_config, trial_name_map = spec_to_job_config(
        spec, job_name="testjob", jobs_dir=tmp_path
    )
    assert len(job_config.tasks) == 1
    assert job_config.tasks[0].path == (
        tmp_path
        / "testjob"
        / "_razorback"
        / "task_views"
        / "ade-bench-adebench-fixture-001"
    )
    manifest = json.loads((job_config.tasks[0].path / "view_manifest.json").read_text())
    assert manifest["benchmark_kind"] == "ade-bench"
    assert manifest["benchmark_task_id"] == "adebench-fixture-001"
    assert job_config.n_attempts == 1
    assert job_config.n_concurrent_trials == 1
    assert job_config.retry.max_retries == 0  # §6.5 parity with DAB
    assert trial_name_map == {}  # ade-bench has no (dataset, query_id) pairing


def test_translator_uses_spec_concurrency_for_ade(tmp_path):
    spec = _make_spec("adebench-fixture-001")
    spec.concurrency.trials = 3
    job_config, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    assert job_config.n_concurrent_trials == 3


def test_translator_rejects_unknown_slug(tmp_path):
    spec = _make_spec("does-not-exist")
    with pytest.raises(Exception) as exc_info:
        spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    msg = str(exc_info.value).lower()
    assert "does-not-exist" in msg or "not found" in msg
