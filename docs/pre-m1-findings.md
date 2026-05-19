# Pre-M1 findings: harbor 0.6.6 library API

Verified against `harbor==0.6.6` (PyPI) on macOS 14 / Colima docker.

## What the spike confirmed

| Spike question | Answer | Evidence |
|---|---|---|
| `Job.create(JobConfig)` runs standalone | yes | `scripts/smoke_nop.py` constructs `JobConfig`, awaits `Job.create(cfg)`, awaits `job.run()` |
| All six `TrialEvent` hooks fire | partial | live run with verifier disabled fired START, ENVIRONMENT_START, AGENT_START, END. VERIFICATION_START fires when verifier is enabled (observed in the failing-verifier run). CANCEL only fires on explicit cancel (source-confirmed); we did not exercise that path |
| Custom `BaseAgent` registers via `AgentConfig(import_path=...)` | source-confirmed | `harbor.agents.factory` uses `importlib`; verified by reading factory.py (`AgentName.NOP.value` resolves to bundled class; `import_path="module:Class"` is the dotted-path slot) |
| Per-trial output layout stable | yes | the trial dir contains `agent/`, `verifier/`, `artifacts/`, `config.json`, `result.json`, `trial.log` — matches §6.3 of the design |
| Harbor resumes on matching `(jobs_dir, job_name)` | source-confirmed | `Job._maybe_init_existing_job` reads existing `JobConfig` and refuses on mismatch (job.py:204-212) |

## Harbor API map (versions razorback depends on)

- Package name on PyPI is **`harbor`** (the design draft says "harbor-framework"; the actual PyPI name is shorter). pyproject pins `harbor==0.6.6`.
- `harbor.__version__ == "0.6.6"`.
- Imports razorback uses for M1:
  - `from harbor.job import Job`
  - `from harbor.models.job.config import JobConfig`
  - `from harbor.models.trial.config import AgentConfig, TaskConfig, VerifierConfig`
  - `from harbor.models.agent.name import AgentName` (enum carries `NOP = "nop"`)
  - `from harbor.trial.hooks import TrialEvent, TrialHookEvent`
- `JobConfig` fields razorback writes: `job_name`, `jobs_dir`, `n_concurrent_trials`, `n_attempts`, `agents: list[AgentConfig]`, `tasks: list[TaskConfig]`, `verifier: VerifierConfig`, `retry: RetryConfig`.
- A `TaskConfig(path=...)` against a local task dir works without registry I/O.

## Per-trial reward contract (relevant for M1 hello-world task)

Harbor's verifier executes `tests/test.sh` inside the container with stdout/stderr redirected to `/logs/verifier/test-stdout.txt`. The script must leave a reward at either `/logs/verifier/reward.txt` (single value) or `/logs/verifier/reward.json` (key/value map). After the script returns, harbor checks the host-side bind-mounted path and raises `RewardFileNotFoundError` if neither exists.

In this smoke we ran with `VerifierConfig(disable=True)` to validate the full lifecycle without the reward contract. **M1 owes**: a hello-world task whose `tests/test.sh` actually drops a reward file. The current smoke script's `test.sh` writes `printf '1.0' > /logs/verifier/reward.txt` but the file never appears on the host — investigating that is M1 work.

## Host gotchas

- **macOS + Colima:** `tempfile.mkdtemp()` defaults to `$TMPDIR` (`/var/folders/...`), which Colima does **not** mount into the VM. Bind mounts from that path silently land in the VM and never reach the host. Anything razorback writes that needs to round-trip through a container must live under `/Users/<user>/` (Colima's default mount). M1's run-dir layout (`_runs/...`) sits under the repo root, so this is fine; tests that use `tempfile` for run-dirs must explicitly target a `/Users`-rooted dir.
- **`fatal: bad revision 'HEAD'`:** harmless log line emitted by harbor when it probes a git SHA in a fresh repo without commits. Disappears after the first commit.
- **`Skipping image OS validation: docker inspect returned 1`:** harmless warning the first time harbor builds the task image; the image gets built and the trial proceeds.

## Six TrialEvent values, for reference

`harbor.trial.hooks.TrialEvent` enumerates:

```
START
ENVIRONMENT_START
AGENT_START
VERIFICATION_START
END
CANCEL
```

The `events.jsonl` observer (M1) registers a callback for each.
