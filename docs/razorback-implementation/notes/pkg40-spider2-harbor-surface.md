# PKG-40 Spider2 Harbor Surface Spike

Date: 2026-05-21

## Commands Run

### Local Harbor model surfaces

Command:

```bash
uv run python - <<'PY'
import inspect
from harbor.models.job.config import JobConfig
from harbor.models.trial.config import TaskConfig, TrialConfig
print(inspect.getsource(TaskConfig))
print(inspect.getsource(JobConfig))
print(inspect.getsource(TrialConfig.generate_trial_name))
PY
```

Summary:

- Harbor version: `0.6.6`.
- `TaskConfig` accepts local `path`, package `name`/`ref`, git fields, and `source`.
- `TaskConfig.get_local_path()` delegates to `get_task_id().get_local_path()`, so Razorback can hand Harbor ordinary `TaskConfig(path=view_dir)` entries.
- `JobConfig.n_concurrent_trials` defaults to `4`; Razorback should set it explicitly from spec concurrency.
- `TrialConfig.generate_trial_name()` derives the prefix from `self.task.get_task_id().get_name().split("/")[-1]`, then appends a short random suffix. For local task views, the materialized directory name is therefore part of the visible Harbor trial name.

### Installed Spider2 adapter source

Command:

```bash
rg -n "spider2|spider2-dbt|SpiderAgentDBT" .venv/lib/python3.12/site-packages/harbor .venv/lib/python3.12/site-packages -g '*.py' -g '*.yaml' -g '*.md'
```

Summary: exit code `1`, no matches. This VM's installed Harbor package does not include Spider2 adapter source files to inspect.

### Public Harbor Spider2 package export

Command:

```bash
uv run harbor download spider2-dbt@1.0 --output-dir runs/pkg40-spider2-download --export --overwrite
find runs/pkg40-spider2-download -maxdepth 3 -name task.toml | head -5
```

Summary: the registry located `spider2-dbt@1.0` and reported `0/64 Downloading tasks...`, then failed during git checkout:

```text
CalledProcessError: Command '['git', 'checkout', '82d1fb0c144d28b1fd9852006cee0a39e74bd4a8']' returned non-zero exit status 128.
find: 'runs/pkg40-spider2-download': No such file or directory
```

Spider2 live source access is blocked in this VM by the package git checkout failure. T5/T8 should proceed with a minimal local fixture while preserving this blocker evidence.

### Public parity artifacts

Commands:

```bash
curl -L --fail --silent https://huggingface.co/datasets/harborframework/parity-experiments/raw/refs%2Fpr%2F201/adapters/spider2-dbt/config.yaml
curl -L --fail --silent https://huggingface.co/datasets/harborframework/parity-experiments/raw/refs%2Fpr%2F201/adapters/spider2-dbt/README.md
```

Summary:

- `config.yaml` uses `datasets: [{path: datasets/spider2-dbt}]`, `orchestrator.n_concurrent_trials: 4`, Docker environment with `force_build: true`/`delete: true`, and `agents[0].import_path: adapters.spider2-dbt.spider_agent_dbt:SpiderAgentDBT`.
- `README.md` cites Harbor parity commands from `adapters/spider2-dbt`, including `uv run python run_adapter.py` and `uv run harbor jobs start -p datasets/spider2-dbt --agent-import-path "adapters.spider2-dbt.spider_agent_dbt:SpiderAgentDBT" -m "gpt-5-mini-2025-08-07"`.
- Public README task ids include `airport001`, `quickbooks003`, `workday001`, `workday002`, `lever001`, `divvy001`, `retail001`, `mrr002`, `hubspot001`, `mrr001`, `tickit001`, `playbook001`, `salesforce001`, `shopify002`, `maturity001`, `hive001`, `marketo001`, and `f1003`.

## Spider2 Source Status

Live Harbor download did not produce task directories in this VM. The generic materializer and Spider2 consumer should use a fixture-backed source for implementation and tests, and live Spider2 smoke should be marked blocked until the Harbor package git checkout succeeds or a pre-hydrated `datasets/spider2-dbt` tree is provided.

## Leakage and Verifier Paths

No live Spider2 task tree was available to inspect. The fixture and shared denylist should fail closed by excluding:

- `solution/**`
- `solutions/**`
- `**/solution.*`
- `**/answer*`
- `**/*answers*`
- `tests/expected/**`
- verifier-only expected-output or answer files if present in future live Spider2 task trees

## Minimum Fixture Shape for T5

Use one local Harbor-shaped Spider2 fixture task:

```text
tests/fixtures/spider2_dbt/tasks/spider2-fixture-001/
  task.toml
  instruction.md
  environment/Dockerfile
  tests/test.sh
  dbt_project/models/example.sql
  data/input.csv
  solution/answer.sql
  tests/expected/answer.txt
```

The consumer should materialize only the agent-visible Harbor task view, patch the shared Docker image when requested, add `RAZORBACK_BENCHMARK_TASK_ID`, and omit the denied solution/expected-answer paths before Harbor sees `TaskConfig(path=view_dir)`.
