# ABOUTME: M1 mechanism smoke — runs the nop agent + verifier round-trip end-to-end.
# ABOUTME: Riskiest contract first: does tests/test.sh's reward.txt land on the host?

import asyncio
import json
from pathlib import Path

from harbor.job import Job
from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig
from harbor.models.trial.config import AgentConfig, TaskConfig, VerifierConfig
from harbor.trial.hooks import TrialEvent

REPO = Path(__file__).resolve().parent.parent
TASK_DIR = REPO / "examples" / "tasks" / "hello-world"


async def main() -> None:
    # Anchor under /Users/<user>/ so Colima's bind mounts work. The plan
    # suggested ~/.cache but the runtime sandbox blocks writes there;
    # the repo-local .smoke-tmp/ is equally Colima-mountable.
    work = REPO / ".smoke-tmp" / "razorback-smoke"
    work.mkdir(parents=True, exist_ok=True)
    jobs_dir = work / "jobs"

    config = JobConfig(
        job_name="smoke-nop-verified",
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=1,
        agents=[AgentConfig(name=AgentName.NOP.value)],
        tasks=[TaskConfig(path=TASK_DIR)],
        verifier=VerifierConfig(disable=False),
    )

    fired: list[str] = []

    async def record(event: TrialEvent, payload):
        fired.append(event.value)

    job = await Job.create(config)
    for event in TrialEvent:
        job.add_hook(event, lambda payload, e=event: record(e, payload))

    result = await job.run()

    run_dir = jobs_dir / "smoke-nop-verified"
    print(f"events fired: {fired}")
    print(f"n_completed: {result.stats.n_completed_trials}")
    print(f"n_errored:   {result.stats.n_errored_trials}")
    for trial_dir in sorted(run_dir.iterdir()):
        if not trial_dir.is_dir():
            continue
        ver = trial_dir / "verifier"
        if ver.exists():
            print(f"--- {ver} ---")
            for f in sorted(ver.rglob("*")):
                if f.is_file():
                    print(f"  {f.relative_to(ver)} ({f.stat().st_size}B): {f.read_text()!r}")


if __name__ == "__main__":
    asyncio.run(main())
