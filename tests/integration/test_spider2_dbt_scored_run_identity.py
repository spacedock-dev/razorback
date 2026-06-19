# ABOUTME: AC-1 end-to-end — spider2-dbt scored run preserves benchmark identity
# ABOUTME: through summary.json / per_trial_outcomes.json via the tasks_root manifest.
#
# Hermetic: the dataset source resolver is monkeypatched to a committed fixture,
# so no network fetch or docker is required. NOT marked `integration` (that
# marker is reserved for live docker/auth tests per pyproject.toml).
import json
from pathlib import Path

from razorback.runs.aggregate import aggregate_summary, write_per_trial_outcomes
from razorback.spec.schema import HarborBenchmarkBlock, NopAgentBlock, Spec
from razorback.translate import spec_to_job_config

# The same committed fixture the spider2-dbt translator unit tests use.
FIXTURE_ROOT = (
    Path(__file__).parent.parent
    / "fixtures" / "spider2_dbt" / "harbor_task_minimal"
)


def _spider2_spec() -> Spec:
    return Spec(
        version=1,
        experiment="spider2-scored-run-identity",
        agent=NopAgentBlock(kind="nop"),
        benchmark=HarborBenchmarkBlock(
            kind="harbor", dataset="spider2-dbt/spider2-dbt@1.0"
        ),
        trials=1,
        observers=[],
    )


def test_spider2_dbt_scored_run_carries_benchmark_identity(tmp_path, monkeypatch):
    """The run-orchestrator tasks_root <-> scoring discovery-root agreement:
    the producer materializes a spider2-dbt view manifest under run_dir/tasks,
    and scoring reads that same root, so benchmark identity reaches
    summary.json / per_trial_outcomes.json (AC-1)."""
    run_dir = tmp_path / "spider2job"
    tasks_root = run_dir / "tasks"
    source = FIXTURE_ROOT / "spider2-fixture-001"

    # 1. Producer: materialize spider2-dbt views under tasks_root. Stub the
    #    dataset source resolver so no network fetch occurs (hermetic).
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: [source],
    )
    job_config, _ = spec_to_job_config(
        spec=_spider2_spec(),
        job_name="spider2job",
        jobs_dir=tmp_path,
        tasks_root=tasks_root,
    )

    # Precondition: the producer wrote a manifest under tasks_root.
    manifests = list(tasks_root.glob("*/view_manifest.json"))
    assert manifests, "producer must materialize a view manifest under tasks_root"
    manifest = json.loads(manifests[0].read_text())
    view_name = manifests[0].parent.name
    assert manifest["benchmark_kind"] == "spider2-dbt"
    task_id = manifest["benchmark_task_id"]

    # 2. Fabricate a completed trial dir keyed to the view prefix. The
    #    aggregator matches trial_dir.name.split("__",1)[0] against
    #    manifest_dir.name[:32].rstrip("_-").
    trial_prefix = view_name[:32].rstrip("_-")
    trial_dir = run_dir / f"{trial_prefix}__a"
    trial_dir.mkdir(parents=True)
    (trial_dir / "result.json").write_text(
        json.dumps({"verifier_result": {"rewards": {"reward": 1.0}}})
    )

    # 3. Run scoring. Both writers take run_dir and write the artifact as a
    #    side effect (return None).
    aggregate_summary(run_dir)
    write_per_trial_outcomes(run_dir)

    # 4. Assert identity propagated end-to-end (AC-1).
    summary = json.loads((run_dir / "summary.json").read_text())
    trial_row = summary["trials"][0]
    assert trial_row["stratum"]["benchmark_kind"] == "spider2-dbt"
    assert trial_row["stratum"]["benchmark_task_id"] == task_id

    outcomes = json.loads((run_dir / "per_trial_outcomes.json").read_text())
    row = outcomes["trials"][0]
    assert row["benchmark_kind"] == "spider2-dbt"
    assert row["benchmark_task_id"] == task_id
