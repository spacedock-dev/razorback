# ABOUTME: M3 Task 1 — RISK-FIRST smoke for the claude-CLI-in-harbor-docker path.
# ABOUTME: Bypasses razorback's registry/schema layer; runs an ad-hoc BaseAgent subclass
# ABOUTME: against one bookreview query inside harbor's docker env (dab-agent:latest image).
# ABOUTME: Asserts the verifier emits a numeric reward (the path works); pass OR fail is OK.

import asyncio
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest
from dotenv import dotenv_values

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.job import Job
from harbor.models.agent.context import AgentContext
from harbor.models.job.config import JobConfig, RetryConfig
from harbor.models.trial.config import (
    AgentConfig,
    EnvironmentConfig,
    TaskConfig,
    VerifierConfig,
)

from razorback.benchmarks.dab.prepare import prepare_dataset_tasks


DAB_DATA = Path("/Users/clkao/git/dataagentbench/data")
REPO = Path(__file__).resolve().parents[2]
HOST_CLAUDE = shutil.which("claude")
DOTENV_API_KEY = dotenv_values(REPO / ".env").get("ANTHROPIC_API_KEY") if (REPO / ".env").exists() else None
_TOKEN_PATH = Path.home() / ".claude" / "benchmark-token"
OAUTH_TOKEN = _TOKEN_PATH.read_text().strip() if _TOKEN_PATH.exists() else None


def _has_dab_agent_image() -> bool:
    """Check whether dab-agent:latest is present locally (required for the smoke)."""
    try:
        r = subprocess.run(
            ["docker", "image", "inspect", "dab-agent:latest"],
            capture_output=True,
            timeout=10,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(
    not (DAB_DATA / "query_bookreview").exists()
    or HOST_CLAUDE is None
    or not (DOTENV_API_KEY or OAUTH_TOKEN)
    or not _has_dab_agent_image(),
    reason=(
        "Smoke needs bookreview dataset, host `claude` CLI, one auth token "
        "(in .env or ~/.claude/benchmark-token), and dab-agent:latest image."
    ),
)


# Verbatim copy of run_experiment.py:1509-1525 — do NOT paraphrase the host list.
PROXY_EXEMPT = (
    ".anthropic.com,api.anthropic.com,statsig.anthropic.com,"
    "featuregates.org,.statsig.com,"
    ".openai.com,api.openai.com,auth.openai.com,chatgpt.com,"
    "pypi.org,files.pythonhosted.org,pypi.python.org"
)
PROXY_BLOCK_ENV = {
    "HTTP_PROXY": "http://127.0.0.1:1",
    "HTTPS_PROXY": "http://127.0.0.1:1",
    "http_proxy": "http://127.0.0.1:1",
    "https_proxy": "http://127.0.0.1:1",
    "NO_PROXY": PROXY_EXEMPT,
    "no_proxy": PROXY_EXEMPT,
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
}


class _SmokeClaudeAgent(BaseAgent):
    """Minimal claude-CLI agent for the smoke. The full agent ships in Task 4."""

    @staticmethod
    def name() -> str:
        return "claude-cli-smoke"

    def version(self) -> str:
        return "0.0.0-smoke"

    async def setup(self, environment: BaseEnvironment) -> None:
        # Sanity: the `claude` binary must be on PATH inside the container.
        result = await environment.exec("claude --version")
        assert result.return_code == 0, (
            "claude CLI missing inside container — Task 1 STOP: "
            f"exit={result.return_code} stdout={getattr(result, 'stdout', '')!r} "
            f"stderr={getattr(result, 'stderr', '')!r}"
        )

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        env = dict(PROXY_BLOCK_ENV)
        if DOTENV_API_KEY:
            env["ANTHROPIC_API_KEY"] = DOTENV_API_KEY
        else:
            assert OAUTH_TOKEN is not None
            env["CLAUDE_CODE_OAUTH_TOKEN"] = OAUTH_TOKEN

        cmd = (
            "claude -p " + shlex.quote(instruction)
            + " --allowedTools Bash,Read,Write,Edit,Glob,Grep"
            + " --disallowedTools WebFetch --disallowedTools WebSearch"
            + " --permission-mode bypassPermissions"
        )
        # Let harbor use the container's configured workdir (set in task.toml).
        result = await environment.exec(cmd, env=env, timeout_sec=600)
        # Capture for the smoke's debug surface — written into the agent's logs dir
        # so the test can read it back even though tmp dirs get cleaned up.
        trace = self.logs_dir / "claude_smoke_trace.txt"
        trace.parent.mkdir(parents=True, exist_ok=True)
        trace.write_text(
            f"return_code={result.return_code}\n"
            f"--- stdout ---\n{getattr(result, 'stdout', '')!s}\n"
            f"--- stderr ---\n{getattr(result, 'stderr', '')!s}\n"
        )


WORKDIR_IN_IMAGE = "/workspace"


def _patch_task_for_dab_agent(task_dir: Path) -> None:
    """Repoint the task at the dab-agent:latest prebuilt image.

    Three changes layered over what M2's prepare.py emits:
      1. [environment] docker_image = "dab-agent:latest" + workdir = "/workspace".
         dab-agent ships claude + /workspace WORKDIR; M2's python:3.12-slim image
         has neither.
      2. [[steps]] name = "main" with workdir relocated to steps/main/workdir/.
         Harbor's single-step trial path does NOT auto-upload task_dir/workdir,
         only steps/<name>/workdir gets uploaded (trial.py:482-496). Without this,
         bookreview's db_config.yaml / query_dataset / db_description.txt never
         reach the container.
      3. instruction.md + tests/test.sh: rewrite the hardcoded /work/answers.json
         path to /workspace/answers.json so the agent writes and the verifier
         reads the same file.
    Task 5 folds these into prepare.py; here we patch in-place to keep the
    smoke independent of M3's schema/registry scaffolding.
    """
    toml_path = task_dir / "task.toml"
    body = toml_path.read_text()
    if "[environment]" not in body:
        body += (
            "\n[environment]\n"
            f'docker_image = "dab-agent:latest"\n'
            f'workdir = "{WORKDIR_IN_IMAGE}"\n'
            "\n[[steps]]\n"
            'name = "main"\n'
        )
        toml_path.write_text(body)

    instr_path = task_dir / "instruction.md"
    instr_path.write_text(
        instr_path.read_text().replace("/work/answers.json", f"{WORKDIR_IN_IMAGE}/answers.json")
    )

    test_sh = task_dir / "tests" / "test.sh"
    test_sh.write_text(
        test_sh.read_text().replace(
            "/work/answers.json", f"{WORKDIR_IN_IMAGE}/answers.json"
        )
    )

    # Relocate the workdir/ contents under steps/main/workdir/ so the trial's
    # _upload_step_workdir picks them up. Also copy instruction.md into the step
    # dir — harbor multi-step trials read step_instruction_path, not the top-
    # level instruction.md.
    old_workdir = task_dir / "workdir"
    step_dir = task_dir / "steps" / "main"
    step_dir.mkdir(parents=True, exist_ok=True)
    old_workdir.rename(step_dir / "workdir")
    (step_dir / "instruction.md").write_text(instr_path.read_text())


@pytest.mark.timeout(900)
def test_claude_cli_smoke_writes_numeric_reward(colima_safe_tmp_path):
    tasks_root = colima_safe_tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=DAB_DATA, dataset="bookreview", tasks_root=tasks_root
    )
    q1 = next(e for e in manifest if e["query_id"] == 1)
    _patch_task_for_dab_agent(q1["task_dir"])

    jobs_dir = colima_safe_tmp_path / "_jobs"
    job_name = "smoke" + "0" * 11

    config = JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=1,
        agents=[AgentConfig(import_path=_import_path_of(_SmokeClaudeAgent))],
        tasks=[TaskConfig(path=q1["task_dir"])],
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        # Keep the dab-agent:latest image after the trial. Default delete=True
        # tears it down via `docker compose down --rmi all`, which would force
        # a rebuild before every subsequent run.
        environment=EnvironmentConfig(delete=False),
    )

    result = asyncio.run(_run_job(config))

    assert result.stats.n_completed_trials == 1, (
        f"smoke failed: completed={result.stats.n_completed_trials} "
        f"errored={result.stats.n_errored_trials}"
    )
    [trial] = result.trial_results
    assert trial.verifier_result is not None, "verifier did not run — smoke STOP"
    assert trial.verifier_result.rewards is not None, (
        "verifier produced no rewards dict — smoke STOP"
    )
    assert "reward" in trial.verifier_result.rewards, (
        f"missing 'reward' key — got {trial.verifier_result.rewards!r}"
    )
    reward = trial.verifier_result.rewards["reward"]
    assert isinstance(reward, (int, float)), f"reward not numeric: {reward!r}"
    print(f"\n[smoke] reward={reward!r} rewards={trial.verifier_result.rewards!r}")
    # Surface the claude exec trace so a 0.0 reward can be diagnosed (auth/proxy/etc.)
    for trace in jobs_dir.rglob("claude_smoke_trace.txt"):
        print(f"[smoke] trace at {trace}:\n{trace.read_text()}")


async def _run_job(config: JobConfig):
    job = await Job.create(config)
    return await job.run()


def _import_path_of(cls) -> str:
    return f"{cls.__module__}:{cls.__name__}"
