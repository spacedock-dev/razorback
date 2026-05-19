# ABOUTME: One-off pre-M1 smoke for the harbor 0.6.6 library API.
# ABOUTME: Builds a minimal hello-world task and runs harbor's nop agent end-to-end.

"""Run the harbor nop agent against a minimal hello-world task.

Purpose: confirm `Job.create(JobConfig)` and `Job.run()` work standalone
against harbor 0.6.6, and that the per-trial output directory layout
matches §6.3 of the design doc.
"""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path

from harbor.job import Job
from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig
from harbor.models.trial.config import AgentConfig, TaskConfig, VerifierConfig
from harbor.trial.hooks import TrialEvent


TASK_TOML = """\
schema_version = "1.2"

[task]
name = "razorback/hello-world"
description = "Trivial smoke task for the nop agent."
"""

INSTRUCTION = "Do nothing; the verifier reports success unconditionally."

DOCKERFILE = """\
FROM alpine:3.20
WORKDIR /work
CMD ["sleep", "infinity"]
"""

TEST_SH = """\
#!/bin/sh
# Always emit a passing reward via harbor's verifier contract.
set -eu
echo "smoke-test running, writing reward" 1>&2
printf '1.0' > /logs/verifier/reward.txt
ls -la /logs/verifier 1>&2
"""


def write_task(root: Path) -> Path:
    task_dir = root / "hello-world"
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "tests").mkdir()
    (task_dir / "task.toml").write_text(TASK_TOML)
    (task_dir / "instruction.md").write_text(INSTRUCTION)
    (task_dir / "environment" / "Dockerfile").write_text(DOCKERFILE)
    test_path = task_dir / "tests" / "test.sh"
    test_path.write_text(TEST_SH)
    test_path.chmod(0o755)
    return task_dir


async def main() -> None:
    # Colima only mounts /Users/clkao into its VM; macOS's /var/folders
    # TMPDIR is invisible to containers. Use a repo-local tempdir so
    # harbor's bind mounts work end-to-end.
    repo_tmp = Path(__file__).resolve().parent.parent / ".smoke-tmp"
    repo_tmp.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="rk-smoke-", dir=repo_tmp))
    try:
        task_dir = write_task(work)
        jobs_dir = work / "jobs"

        config = JobConfig(
            job_name="smoke-nop",
            jobs_dir=jobs_dir,
            n_concurrent_trials=1,
            n_attempts=1,
            agents=[AgentConfig(name=AgentName.NOP.value)],
            tasks=[TaskConfig(path=task_dir)],
            verifier=VerifierConfig(disable=True),
        )

        events: list[str] = []

        async def record(event: TrialEvent, payload):
            events.append(event.value)

        job = await Job.create(config)
        for event in TrialEvent:
            job.add_hook(event, lambda payload, e=event: record(e, payload))

        result = await job.run()

        run_dir = jobs_dir / "smoke-nop"
        print("---SMOKE RESULT---")
        print(f"events fired: {sorted(set(events))}")
        print(f"jobs_dir contents: {sorted(p.name for p in run_dir.iterdir())}")
        for trial_dir in sorted(run_dir.iterdir()):
            if not trial_dir.is_dir():
                continue
            print(f"trial {trial_dir.name}: {sorted(p.name for p in trial_dir.iterdir())}")
        stats = result.stats
        print(f"stats: {json.dumps(stats.model_dump(mode='json'), indent=2)[:400]}")
        # Dump exception detail and verifier listing for debugging.
        for trial_dir in sorted(run_dir.iterdir()):
            if not trial_dir.is_dir():
                continue
            exc = trial_dir / "exception.txt"
            if exc.exists():
                print(f"\n--- {exc} ---")
                print(exc.read_text())
            ver = trial_dir / "verifier"
            if ver.exists():
                print(f"--- {ver} contents ---")
                for f in sorted(ver.rglob("*")):
                    if f.is_file():
                        print(f"  {f.relative_to(ver)} ({f.stat().st_size}B)")
                        if f.stat().st_size < 4000:
                            print(f"    {f.read_text()!r}")
            tlog = trial_dir / "trial.log"
            if tlog.exists():
                print(f"--- trial.log (tail) ---")
                print(tlog.read_text()[-2000:])
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
