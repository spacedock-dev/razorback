# ABOUTME: Run orchestrator — spec → freeze → harbor Job → drainer → run-dir.
# ABOUTME: The acceptance path: matches the §6.3 layout end-to-end.

import asyncio
import json
from pathlib import Path

from harbor.job import Job
from harbor.trial.hooks import TrialEvent, TrialHookEvent

from razorback.compat import spec_to_job_config
from razorback.errors import RazorbackError, ExitCode
from razorback.manifest import write_manifest
from razorback.observers import EventChannel, JsonlObserver, StdoutObserver
from razorback.provenance.drift import check_alias_drift, check_harbor_drift
from razorback.provenance.provenance_yaml import write_provenance_yaml
from razorback.spec.freeze import derive_job_name, freeze_spec
from razorback.spec.schema import Spec


class HarborRuntimeError(RazorbackError):
    exit_code: int = ExitCode.HARBOR_RUNTIME


def execute_run(
    *, spec: Spec, runs_dir: Path, allow_alias_drift: bool = False
) -> None:
    """Synchronous entry point invoked by the CLI."""
    asyncio.run(
        _execute_run_async(
            spec=spec, runs_dir=runs_dir, allow_alias_drift=allow_alias_drift
        )
    )


async def _execute_run_async(
    *, spec: Spec, runs_dir: Path, allow_alias_drift: bool = False
) -> None:
    from razorback.spec.parse import parse_spec_text

    frozen_text = freeze_spec(spec)
    job_name = derive_job_name(frozen_text)
    # Re-parse the frozen text so downstream gets a Spec that reflects the freeze
    # (e.g. spacedock-solver `sealed_hash` and `prompt_contents` populated).
    spec = parse_spec_text(frozen_text)

    run_dir = Path(runs_dir).resolve() / spec.experiment / job_name
    run_dir.mkdir(parents=True, exist_ok=True)

    # M4: capture the prior seed's frozen spec (for halt-resume sealed-hash check)
    # BEFORE we write the resume's frozen_text and clobber it.
    prior_frozen_spec_path: Path | None = None
    spec_frozen_path = run_dir / "spec.frozen.yaml"
    if spec_frozen_path.exists():
        prior_frozen_spec_path = run_dir / "spec.frozen.prior.yaml"
        prior_frozen_spec_path.write_bytes(spec_frozen_path.read_bytes())

    # M5: provenance drift checks (harbor version, model alias) and provenance.yaml
    # write happen against the about-to-be-written frozen spec.
    frozen_provenance = spec.model_dump(mode="json").get("provenance") or {}
    frozen_model_version = frozen_provenance.get("model_resolved_version")
    frozen_harbor = frozen_provenance.get("harbor_version")
    drift_record: dict | None = None

    if frozen_harbor is not None:
        check_harbor_drift(frozen=frozen_harbor, installed=None)

    if frozen_model_version is not None:
        model_alias = getattr(spec.agent, "model", None) or "claude-opus-4-5"
        import anthropic

        client = anthropic.Anthropic()
        resolved_id, resolved_at = check_alias_drift(
            model_alias=model_alias,
            frozen_resolved_version=frozen_model_version,
            client=client,
            allow=allow_alias_drift,
        )
        if resolved_id != frozen_model_version:
            drift_record = {
                "model_alias": model_alias,
                "frozen": frozen_model_version,
                "resolved": resolved_id,
                "resolved_at": resolved_at,
            }

    if frozen_provenance:
        write_provenance_yaml(
            run_dir / "provenance.yaml", frozen_provenance, drift_record=drift_record
        )

    spec_frozen_path.write_text(frozen_text)
    write_manifest(
        run_dir / "manifest.json",
        experiment=spec.experiment,
        job_name=job_name,
        benchmark_kind=spec.benchmark.kind,
    )

    channel = EventChannel()
    for obs_block in spec.observers:
        if obs_block.kind == "jsonl":
            channel.add_observer(JsonlObserver(run_dir / (obs_block.path or "events.jsonl")))
        elif obs_block.kind == "stdout":
            channel.add_observer(StdoutObserver())

    # Harbor's jobs_dir + job_name produces jobs_dir/<job_name>/, which is our run_dir.
    tasks_root = run_dir / "tasks"
    # rk run is invoked from the project root; .env (AC-3 source) lives here.
    project_root = Path.cwd()
    job_config, trial_name_map = spec_to_job_config(
        spec,
        job_name=job_name,
        jobs_dir=run_dir.parent,
        tasks_root=tasks_root,
        project_root=project_root,
        prior_frozen_spec_path=prior_frozen_spec_path,
    )

    # AC-1: instantiate the spacedock-solver agent BEFORE harbor.Job.create so
    # SeedMismatchError surfaces (and the CLI exits with code 20) without spinning
    # up docker. The construction is cheap and validates the sealed_hash.
    _refuse_resume_if_spacedock_mismatch(job_config, run_dir.parent / job_name / "agent_freeze")

    drain_task = asyncio.create_task(channel.drain())

    try:
        job = await Job.create(job_config)
        for event in TrialEvent:
            job.add_hook(event, _hook_publisher(channel, event))
        try:
            result = await job.run()
        except Exception as exc:
            (run_dir / "crash.json").write_text(json.dumps({"error": str(exc)}, indent=2))
            raise HarborRuntimeError(f"harbor run failed: {exc}") from exc
    finally:
        await channel.aclose()
        await drain_task

    from razorback.spec.schema import AdeBenchBenchmarkBlock, DabBenchmarkBlock
    if isinstance(spec.benchmark, DabBenchmarkBlock):
        from razorback.benchmarks.dab.aggregate import aggregate_job_result
        aggregate_job_result(
            trial_results=result.trial_results,
            trial_name_map=trial_name_map,
            out_path=run_dir / "summary.json",
        )
    elif isinstance(spec.benchmark, AdeBenchBenchmarkBlock):
        from razorback.benchmarks.ade_bench.aggregate import aggregate_job_result as ade_aggregate
        ade_aggregate(
            trial_results=result.trial_results,
            out_path=run_dir / "summary.json",
        )
    else:
        summary = {
            "experiment": spec.experiment,
            "job_name": job_name,
            "n_total_trials": result.n_total_trials,
            "n_completed_trials": result.stats.n_completed_trials,
            "n_errored_trials": result.stats.n_errored_trials,
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def _refuse_resume_if_spacedock_mismatch(job_config, agent_logs_dir: Path) -> None:
    """AC-1: pre-construct a SpacedockSolverAgent so its sealed_hash check fires
    BEFORE harbor.Job.create. Other agent kinds are no-ops here."""
    for agent_cfg in job_config.agents:
        if agent_cfg.import_path != "razorback.agents.spacedock_solver:SpacedockSolverAgent":
            continue
        from razorback.agents.spacedock_solver import SpacedockSolverAgent
        SpacedockSolverAgent(
            logs_dir=agent_logs_dir,
            model_name=agent_cfg.model_name,
            **agent_cfg.kwargs,
        )


def _hook_publisher(channel: EventChannel, event: TrialEvent):
    async def _publish(hook_event: TrialHookEvent) -> None:
        await channel.publish({
            "event": event.value,
            "trial_id": hook_event.trial_id,
            "task_name": hook_event.task_name,
            "timestamp": hook_event.timestamp.isoformat(),
        })
    return _publish
