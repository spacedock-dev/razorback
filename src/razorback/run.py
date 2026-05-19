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
from razorback.spec.freeze import derive_job_name, freeze_spec
from razorback.spec.schema import Spec


class HarborRuntimeError(RazorbackError):
    exit_code: int = ExitCode.HARBOR_RUNTIME


def execute_run(*, spec: Spec, runs_dir: Path) -> None:
    """Synchronous entry point invoked by the CLI."""
    asyncio.run(_execute_run_async(spec=spec, runs_dir=runs_dir))


async def _execute_run_async(*, spec: Spec, runs_dir: Path) -> None:
    frozen_text = freeze_spec(spec)
    job_name = derive_job_name(frozen_text)

    run_dir = Path(runs_dir).resolve() / spec.experiment / job_name
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "spec.frozen.yaml").write_text(frozen_text)
    write_manifest(run_dir / "manifest.json", experiment=spec.experiment, job_name=job_name)

    channel = EventChannel()
    for obs_block in spec.observers:
        if obs_block.kind == "jsonl":
            channel.add_observer(JsonlObserver(run_dir / (obs_block.path or "events.jsonl")))
        elif obs_block.kind == "stdout":
            channel.add_observer(StdoutObserver())

    # Harbor's jobs_dir + job_name produces jobs_dir/<job_name>/, which is our run_dir.
    tasks_root = run_dir / "tasks"
    job_config, trial_name_map = spec_to_job_config(
        spec, job_name=job_name, jobs_dir=run_dir.parent, tasks_root=tasks_root
    )

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

    summary = {
        "experiment": spec.experiment,
        "job_name": job_name,
        "n_total_trials": result.n_total_trials,
        "n_completed_trials": result.stats.n_completed_trials,
        "n_errored_trials": result.stats.n_errored_trials,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def _hook_publisher(channel: EventChannel, event: TrialEvent):
    async def _publish(hook_event: TrialHookEvent) -> None:
        await channel.publish({
            "event": event.value,
            "trial_id": hook_event.trial_id,
            "task_name": hook_event.task_name,
            "timestamp": hook_event.timestamp.isoformat(),
        })
    return _publish
