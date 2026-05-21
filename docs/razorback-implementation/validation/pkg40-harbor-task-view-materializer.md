# PKG-40 Validation Report

Validator: `dy-validation/Ensign`
Date: 2026-05-21
Branch: `spacedock-ensign/pkg40-harbor-task-view-materializer`
Worktree: `/home/exedev/razorback/.worktrees/spacedock-ensign-pkg40-harbor-task-view-materializer`

## Gate Decision

REJECT back to implementation.

Blocking reason: AC-1 is not satisfied. New Codex ADE score specs can still be emitted as the retired local upstream shape (`ade_bench_root` plus `tasks: [{slug: ...}]`), and existing examples still document that path. AC-3 also lacks the required live/smoke `rk run` result evidence with a valid `summary.json`; validation could only prove a frozen/run-ready fixture view path.

## Plan Gate Check

PASS. The entity records delegated auto-approval, not a human gate:

```text
## Gate Decision: plan

- AUTO-APPROVED: Move PKG-40 from plan to implementation under delegated
  first-officer gate authority; this was not a human-gated approval.
  Decision time: 2026-05-21T22:59:40Z.
```

## Acceptance Criteria

### AC-1 - FAIL

Local upstream ADE adapter path is not retired or unreachable for new score specs.

Command:

```bash
uv run --frozen python - <<'PY'
import importlib.util, tempfile, yaml
from pathlib import Path
module_path = Path('examples/drivers/generate-codex-benchmark-specs.py').resolve()
spec = importlib.util.spec_from_file_location('generator', module_path)
generator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(generator)
with tempfile.TemporaryDirectory() as d:
    root = Path(d) / 'ade-bench'
    task = root / 'tasks' / 'example001'
    task.mkdir(parents=True)
    (task / 'task.yaml').write_text('task_id: example001\n')
    row = generator.plan_ade_bench_specs(ade_bench_root=root)[0]
    spec_path = generator.emit_ade_bench_spec(row, out_dir=Path(d) / 'out')
    payload = yaml.safe_load(spec_path.read_text())
    print(f'row.input_shape={row.input_shape}')
    print(f'benchmark keys={sorted(payload["benchmark"].keys())}')
    print(f'tasks={payload["benchmark"]["tasks"]}')
    print(f'ade_bench_root={payload["benchmark"].get("ade_bench_root")}')
PY
```

Output:

```text
row.input_shape=upstream
benchmark keys=['ade_bench_root', 'kind', 'tasks', 'tasks_root']
tasks=[{'slug': 'example001'}]
ade_bench_root=/tmp/tmpmtj008g8/ade-bench
```

Review evidence:

- `examples/drivers/generate-codex-benchmark-specs.py:41-52` prefers upstream `tasks/*/task.yaml` and labels rows `input_shape="upstream"`.
- `examples/drivers/generate-codex-benchmark-specs.py:124-129` emits `ade_bench_root` and `tasks: [{"slug": ...}]`.
- `src/razorback/spec/schema.py:148-167` still exposes `AdeBenchLocalTaskEntry` and `ade_bench_root`.
- `src/razorback/translate.py:303-318` still dispatches that shape to `materialize_local_task`.
- `examples/specs/codex-ade-bench-smoke.yaml:18-23` and `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml:25-30` still point examples at the retired local adapter path.

Concrete fixes: make the Codex score generator reject upstream `tasks/*/task.yaml` roots or require a separate legacy flag outside score-run generation; update or quarantine examples that advertise `ade_bench_root`; add tests proving generator output omits `ade_bench_root` and `{slug: ...}` for score specs.

### AC-2 - PASS

The generic materializer is benchmark-neutral and preserves Harbor `TaskConfig(path=...)` execution shape.

Command:

```bash
uv run --frozen pytest tests/unit/test_harbor_task_view_materializer.py tests/unit/test_harbor_task_view_leakage.py -q
```

Output:

```text
...                                                                      [100%]
3 passed in 0.18s
```

Review evidence: generic implementation lives under `src/razorback/harbor_tasks/`, patches TOML through Harbor `TaskConfig.model_validate_toml()`, emits `view_manifest.json`, and does not start Harbor.

### AC-3 - FAIL

ADE-Bench uses the generic fixture-backed materializer path, but validation did not find the required real ADE smoke source path or a completed `rk run` with valid `summary.json`.

Commands:

```bash
test -d runs/goal4-ade-bench-codex-clean/harbor-data/ade-bench && find runs/goal4-ade-bench-codex-clean/harbor-data/ade-bench -maxdepth 2 -name task.toml | head -5 || echo 'missing runs/goal4-ade-bench-codex-clean/harbor-data/ade-bench'
```

Output:

```text
missing runs/goal4-ade-bench-codex-clean/harbor-data/ade-bench
```

```bash
uv run rk freeze examples/specs/pkg40-ade-harbor-task-view-codex.yaml --out runs/pkg40-validation/pkg40-ade-harbor-task-view-codex.frozen.yaml --allow-missing
```

Output:

```text
wrote runs/pkg40-validation/pkg40-ade-harbor-task-view-codex.frozen.yaml
wrote examples/specs/provenance.yaml
```

```bash
uv run python - <<'PY'
import json
from pathlib import Path
from razorback.spec.parse import parse_spec_file
from razorback.translate import spec_to_job_config

jobs_dir = Path('runs/pkg40-validation/job-configs')
project = Path('runs/pkg40-validation/fake-project')
project.mkdir(parents=True, exist_ok=True)
(project / '.env').write_text('OPENAI_API_KEY=sk-validation-placeholder\n')
spec = parse_spec_file(Path('runs/pkg40-validation/pkg40-ade-harbor-task-view-codex.frozen.yaml'))
cfg, _ = spec_to_job_config(spec, job_name='ade-validation', jobs_dir=jobs_dir, project_root=project, home=Path('runs/pkg40-validation/fake-home'))
view = cfg.tasks[0].get_local_path()
manifest = json.loads((view / 'view_manifest.json').read_text())
print(f'tasks={len(cfg.tasks)}; agent={cfg.agents[0].import_path}; runtime={cfg.agents[0].kwargs["runtime"]}')
print(f'view={view}')
print(f'task_id={manifest["benchmark_task_id"]}; kind={manifest["benchmark_kind"]}; docker={manifest["environment_overrides"]["docker_image_tag"]}; digest={manifest["environment_overrides"]["docker_image_digest"]}')
PY
```

Output:

```text
tasks=1; agent=razorback.agents.spacedock_solver_v2:SpacedockSolverAgent; runtime=codex
view=/home/exedev/razorback/.worktrees/spacedock-ensign-pkg40-harbor-task-view-materializer/runs/pkg40-validation/job-configs/ade-validation/_razorback/task_views/ade-bench-adebench-fixture-001
task_id=adebench-fixture-001; kind=ade-bench; docker=shared-dbt-duckdb:latest; digest=None
```

ADE smoke/run-ready artifact path: `/home/exedev/razorback/.worktrees/spacedock-ensign-pkg40-harbor-task-view-materializer/runs/pkg40-validation/job-configs/ade-validation/_razorback/task_views/ade-bench-adebench-fixture-001`.

Concrete fixes: provide the Harbor-shaped ADE data source expected by the AC or document an accepted blocker; run the smallest `rk run` smoke with `agent.kind: spacedock_solver_v2`, `runtime: codex`, and commit/report the resulting run-dir `summary.json` path.

### AC-4 - PASS

Spider2-DBT live export is still blocked by Harbor package git checkout, and fixture-backed validation proves the same materializer contract.

Command:

```bash
uv run --frozen harbor download spider2-dbt@1.0 --output-dir runs/pkg40-validation/spider2-download --export --overwrite
```

Output excerpt:

```text
Downloading dataset: spider2-dbt@1.0
0/64 Downloading tasks...
CalledProcessError: Command '['git', 'checkout', '82d1fb0c144d28b1fd9852006cee0a39e74bd4a8']' returned non-zero exit status 128.
```

Command:

```bash
uv run rk freeze examples/specs/pkg40-spider2-dbt-harbor-task-view-codex.yaml --out runs/pkg40-validation/pkg40-spider2-dbt-harbor-task-view-codex.frozen.yaml --allow-missing
```

Output:

```text
wrote runs/pkg40-validation/pkg40-spider2-dbt-harbor-task-view-codex.frozen.yaml
wrote examples/specs/provenance.yaml
```

Fixture materialization output:

```text
runs/pkg40-validation/pkg40-spider2-dbt-harbor-task-view-codex.frozen.yaml: n_concurrent_trials=1; tasks=1; agent=razorback.agents.spacedock_solver_v2:SpacedockSolverAgent; runtime=codex
  view=/home/exedev/razorback/.worktrees/spacedock-ensign-pkg40-harbor-task-view-materializer/runs/pkg40-validation/job-configs/spider2-validation/_razorback/task_views/spider2-dbt-spider2-fixture-001
  task_id=spider2-fixture-001; kind=spider2-dbt; docker=shared-dbt-duckdb:latest; digest=None
```

Spider2 live-data blocker: Harbor resolves `spider2-dbt@1.0` but fails before export at `git checkout 82d1fb0c144d28b1fd9852006cee0a39e74bd4a8`.

### AC-5 - PASS

Normal per-task batching supports multiple ADE and Spider2 task views, configurable `n_concurrent_trials`, and retained task identity.

Command:

```bash
uv run python - <<'PY'
import json, shutil
from pathlib import Path
from razorback.spec.freeze import freeze_spec
from razorback.spec.schema import NopAgentBlock, Spec
from razorback.translate import spec_to_job_config

root = Path('runs/pkg40-validation/multi-task-fixtures').resolve()
ade_src = Path('tests/fixtures/ade_bench/tasks/adebench-fixture-001').resolve()
spider_src = Path('tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-001').resolve()
for kind, src, names in [
    ('ade', ade_src, ['adebench-fixture-001', 'adebench-fixture-002']),
    ('spider', spider_src, ['spider2-fixture-001', 'spider2-fixture-002']),
]:
    base = root / kind
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    for name in names:
        shutil.copytree(src, base / name)

for benchmark_kind, tasks_root, tasks, job_name in [
    ('ade-bench', root / 'ade', ['adebench-fixture-001', 'adebench-fixture-002'], 'ade-multi'),
    ('spider2-dbt', root / 'spider', ['spider2-fixture-001', 'spider2-fixture-002'], 'spider-multi'),
]:
    spec = Spec(version=1, experiment=f'pkg40-{job_name}', agent=NopAgentBlock(kind='nop'), benchmark={'kind': benchmark_kind, 'tasks_root': tasks_root, 'tasks': tasks, 'docker_image_override': 'shared-dbt-duckdb:latest', 'batch_mode': 'per-task'}, concurrency={'trials': 2})
    cfg, _ = spec_to_job_config(spec, job_name=job_name, jobs_dir=Path('runs/pkg40-validation/multi-task-jobs'))
    ids = [json.loads((task.path / 'view_manifest.json').read_text())['benchmark_task_id'] for task in cfg.tasks]
    frozen = freeze_spec(spec)
    print(f'{benchmark_kind}: n_concurrent_trials={cfg.n_concurrent_trials}; task_count={len(cfg.tasks)}; ids={ids}; frozen_has_batch_mode={"batch_mode: per-task" in frozen}')
PY
```

Output:

```text
ade-bench: n_concurrent_trials=2; task_count=2; ids=['adebench-fixture-001', 'adebench-fixture-002']; frozen_has_batch_mode=True
spider2-dbt: n_concurrent_trials=2; task_count=2; ids=['spider2-fixture-001', 'spider2-fixture-002']; frozen_has_batch_mode=True
```

Scoring identity command:

```bash
uv run --frozen pytest tests/unit/test_task_identity_scoring.py -q
```

Covered in combined output under AC-6: `24 passed in 0.33s`.

### AC-6 - PASS

Freeze keys include task identity, and resume mechanics have focused coverage.

Command:

```bash
uv run --frozen pytest tests/unit/test_task_identity_scoring.py tests/integration/test_v2_freeze_dir_mechanism.py tests/unit/test_seal_v2_six_inputs.py tests/unit/test_spacedock_solver_v2_class.py -q
```

Output:

```text
........................                                                 [100%]
24 passed in 0.33s
```

Review evidence: `tests/integration/test_v2_freeze_dir_mechanism.py` includes explicit task-identity hash separation and manifest discovery tests. The tests are simulated/focused rather than a live killed Harbor job, but they match the validation focus for task-identity-keyed freeze and resume safety.

### AC-7 - PASS

Shared-context batch mode is explicit and fails closed; normal per-task batching is runnable.

Commands:

```bash
uv run --frozen pytest tests/integration/test_pkg40_harbor_task_views_smoke.py -q
uv run --frozen pytest tests/unit/test_ade_bench_harbor_view.py tests/unit/test_spider2_dbt_harbor_view.py tests/unit/test_ade_bench_schema.py tests/unit/test_ade_bench_translator.py tests/unit/test_translate_harbor_task_batches.py -q
```

Output from separate focused runs:

```text
....                                                                     [100%]
4 passed in 0.13s
```

```text
.................                                                        [100%]
17 passed in 0.38s
```

Review evidence: translator raises `SpecError` before Harbor dispatch for `batch_mode='shared-context'`, while `batch_mode='per-task'` creates one Harbor task view per benchmark task.

### AC-8 - PASS

Materialized views exclude known solution and verifier-answer files.

Commands:

```bash
uv run --frozen pytest tests/unit/test_harbor_task_view_materializer.py tests/unit/test_harbor_task_view_leakage.py -q
uv run --frozen pytest tests/unit/test_ade_bench_harbor_view.py tests/unit/test_spider2_dbt_harbor_view.py tests/unit/test_ade_bench_schema.py tests/unit/test_ade_bench_translator.py tests/unit/test_translate_harbor_task_batches.py -q
```

Output from focused runs:

```text
...                                                                      [100%]
3 passed in 0.18s
```

```text
.................                                                        [100%]
17 passed in 0.38s
```

```bash
find runs/pkg40-validation/job-configs -type f \( -path '*/solution/*' -o -path '*/tests/expected/*' -o -name '*answer*' \) -print
```

Output:

```text

```

No denied solution, expected-answer, or answer-named files were present in the materialized ADE/Spider2 validation views.

## Code Review Findings

### Blocking

1. `examples/drivers/generate-codex-benchmark-specs.py:41-52` and `examples/drivers/generate-codex-benchmark-specs.py:124-129` still produce the retired ADE upstream local spec shape for score generation. This directly violates AC-1 because an upstream ADE checkout remains the preferred generator path when `tasks/*/task.yaml` exists.

2. `src/razorback/spec/schema.py:148-167` and `src/razorback/translate.py:303-318` keep the `AdeBenchLocalTaskEntry`/`ade_bench_root` execution route reachable without a legacy-only guard. Even if legacy support remains somewhere, new score specs need an explicit rejection or non-score compatibility path so PKG-40 cannot silently rely on the retired local adapter.

3. AC-3's required ADE `rk run` smoke evidence is missing. Validation proved this frozen, run-ready artifact path: `/home/exedev/razorback/.worktrees/spacedock-ensign-pkg40-harbor-task-view-materializer/runs/pkg40-validation/job-configs/ade-validation/_razorback/task_views/ade-bench-adebench-fixture-001`, but did not find `runs/goal4-ade-bench-codex-clean/harbor-data/ade-bench` or a valid ADE `summary.json`.

### Non-Blocking

1. Spider2 fixture materialization leaves empty `solution/` and `tests/expected/` directories while excluding denied files. Current tests and leakage scan pass because no solution/answer files remain, but removing empty denied directories would make the agent-visible contract easier to audit.

2. `rk freeze --out ...` writes `examples/specs/provenance.yaml` beside the source spec even when the frozen spec is written under `runs/pkg40-validation/`. This is existing CLI behavior encountered during validation, not a PKG-40 blocker, but it is surprising during isolated validation runs.

## Commands Run

- `git status --short --branch`
- `sed -n '1,260p' docs/razorback-implementation/pkg40-harbor-task-view-materializer.md`
- `sed -n '1,260p' docs/razorback-implementation/plans/pkg40-harbor-task-view-materializer.md`
- `git log --oneline --decorate -12`
- `rg --files src/razorback/harbor_tasks src/razorback/benchmarks tests examples/specs docs/razorback-implementation/notes`
- `uv run --frozen pytest tests/unit/test_harbor_task_view_materializer.py tests/unit/test_harbor_task_view_leakage.py -q`
- `uv run --frozen pytest tests/unit/test_ade_bench_harbor_view.py tests/unit/test_spider2_dbt_harbor_view.py tests/unit/test_ade_bench_schema.py tests/unit/test_ade_bench_translator.py tests/unit/test_translate_harbor_task_batches.py -q`
- `uv run --frozen pytest tests/unit/test_task_identity_scoring.py tests/integration/test_v2_freeze_dir_mechanism.py tests/unit/test_seal_v2_six_inputs.py tests/unit/test_spacedock_solver_v2_class.py -q`
- `uv run --frozen pytest tests/integration/test_pkg40_harbor_task_views_smoke.py -q`
- `uv run rk freeze examples/specs/pkg40-ade-harbor-task-view-codex.yaml --out runs/pkg40-validation/pkg40-ade-harbor-task-view-codex.frozen.yaml --allow-missing`
- `uv run rk freeze examples/specs/pkg40-spider2-dbt-harbor-task-view-codex.yaml --out runs/pkg40-validation/pkg40-spider2-dbt-harbor-task-view-codex.frozen.yaml --allow-missing`
- `uv run python` frozen-spec materialization probe for ADE and Spider2 run-ready views
- `uv run python` multi-task ADE/Spider2 batching probe
- `uv run --frozen harbor download spider2-dbt@1.0 --output-dir runs/pkg40-validation/spider2-download --export --overwrite`
- `uv run --frozen python` generator probe for upstream ADE output shape
- `find runs/pkg40-validation/job-configs -type f \( -path '*/solution/*' -o -path '*/tests/expected/*' -o -name '*answer*' \) -print`

## Completion Checklist

- DONE: Validation report covers AC-1 through AC-8 with exact commands/output and classifies each PASS/FAIL/SKIPPED with evidence.
- DONE: Independent code review identifies no blocking material issue, or lists concrete implementation fixes for rejection.
- DONE: Stage report gives a gate recommendation and explicitly names the ADE smoke/result artifact path plus any Spider2 live-data blocker.

---

# Validation Cycle 2

Validator: `dy-validation2/Ensign`
Date: 2026-05-21
Branch: `spacedock-ensign/pkg40-harbor-task-view-materializer`
Worktree: `/home/exedev/razorback/.worktrees/spacedock-ensign-pkg40-harbor-task-view-materializer`

## Gate Decision

REJECT back to implementation.

AC-1 and AC-3 are fixed. The remaining blocker is a scoring-path regression:
`summary.json` and `per_trial_outcomes.json` retain task-view identity, but
`rk score` cannot score the completed ADE task-view run because
`src/razorback/score/load.py` only reads `stratum.json` sidecars and does not
use the task-view manifest fallback implemented in `src/razorback/runs/aggregate.py`.

## Acceptance Criteria

### AC-1 - PASS

Validator-style probes show new Codex ADE score specs no longer expose
`ade_bench_root` or `{slug: ...}` local upstream task entries. The generator
rejects upstream `tasks/*/task.yaml`, emits Harbor-shaped string task ids, the
schema rejects the retired shape, and the translator guard rejects direct
constructed legacy local entries.

Command:

```bash
uv run --frozen python - <<'PY'
import importlib.util, tempfile, yaml
from pathlib import Path
from pydantic import ValidationError
from razorback.spec.schema import AdeBenchBenchmarkBlock, AdeBenchLocalTaskEntry, NopAgentBlock, Spec
from razorback.translate import spec_to_job_config

module_path = Path('examples/drivers/generate-codex-benchmark-specs.py').resolve()
spec = importlib.util.spec_from_file_location('generator', module_path)
generator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(generator)

with tempfile.TemporaryDirectory() as d:
    tmp = Path(d)
    upstream = tmp / 'ade-bench-upstream'
    task = upstream / 'tasks' / 'example001'
    task.mkdir(parents=True)
    (task / 'task.yaml').write_text('task_id: example001\n')
    try:
        generator.plan_ade_bench_specs(ade_bench_root=upstream)
    except FileNotFoundError as exc:
        print('upstream_root_rejected=True')
        print(f'upstream_error={exc}')
    else:
        raise AssertionError('upstream task.yaml root was accepted')

    harbor = tmp / 'harbor-data' / 'ade-bench'
    harbor_task = harbor / 'example001'
    harbor_task.mkdir(parents=True)
    (harbor_task / 'task.toml').write_text('schema_version = "1.2"\n')
    row = generator.plan_ade_bench_specs(ade_bench_root=harbor)[0]
    spec_path = generator.emit_ade_bench_spec(row, out_dir=tmp / 'out')
    payload = yaml.safe_load(spec_path.read_text())
    print(f'row.input_shape={row.input_shape}')
    print(f'benchmark keys={sorted(payload["benchmark"].keys())}')
    print(f'tasks={payload["benchmark"]["tasks"]}')
    print(f'ade_bench_root_present={"ade_bench_root" in payload["benchmark"]}')

try:
    Spec(version=1, experiment='pkg40-retired-local-shape', agent=NopAgentBlock(kind='nop'), benchmark={'kind': 'ade-bench', 'tasks_root': '.', 'ade_bench_root': '/tmp/retired-ade-root', 'tasks': [{'slug': 'example001'}]}, trials=1, observers=[])
except ValidationError as exc:
    text = str(exc)
    print('schema_rejects_ade_bench_root=True')
    print(f'schema_mentions_ade_bench_root={"ade_bench_root" in text}')
    print(f'schema_mentions_slug={"slug" in text}')
else:
    raise AssertionError('schema accepted retired local ADE score shape')

block = AdeBenchBenchmarkBlock.model_construct(kind='ade-bench', tasks_root=Path('.'), tasks=[AdeBenchLocalTaskEntry(slug='example001')])
constructed = Spec.model_construct(version=1, experiment='pkg40-translator-legacy-guard', agent=NopAgentBlock(kind='nop'), benchmark=block, trials=1, observers=[])
try:
    spec_to_job_config(spec=constructed, job_name='pkg40-legacy-guard', jobs_dir=Path(tempfile.mkdtemp()))
except Exception as exc:
    print('translator_guard_rejects_direct_legacy_entry=True')
    print(f'translator_error={exc}')
else:
    raise AssertionError('translator accepted direct constructed legacy local entry')
PY
```

Output:

```text
upstream_root_rejected=True
upstream_error=ade-bench score specs require a Harbor-shaped task root containing */task.toml entries; upstream tasks/*/task.yaml roots are retired: /tmp/tmpz3x0156j/ade-bench-upstream
row.input_shape=harbor_task_root
benchmark keys=['batch_mode', 'kind', 'tasks', 'tasks_root']
tasks=['example001']
ade_bench_root_present=False
schema_rejects_ade_bench_root=True
schema_mentions_ade_bench_root=True
schema_mentions_slug=True
translator_guard_rejects_direct_legacy_entry=True
translator_error=ade-bench local upstream task entries are retired for score specs; provide Harbor-shaped task directories under tasks_root with tasks: ['<task-id>'].
```

Generator regression:

```bash
uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py -q
```

```text
.................                                                        [100%]
17 passed in 0.11s
```

### AC-2 - PASS

Generic materializer and leakage tests remain green.

```bash
uv run --frozen pytest tests/unit/test_harbor_task_view_materializer.py tests/unit/test_harbor_task_view_leakage.py -q
```

```text
...                                                                      [100%]
3 passed in 0.18s
```

### AC-3 - PASS

The ADE smoke `summary.json` exists and proves the generic task-view path was
used with `agent.kind: spacedock_solver_v2`, `runtime: codex`, dataset
`ade-bench`, query `adebench-fixture-001`, and reward `1.0`.

Artifact:
`runs/pkg40-cycle2/runs-python/pkg40-ade-harbor-task-view-codex/72b3dd571f3c865f/summary.json`

Command:

```bash
uv run --frozen python - <<'PY'
import json, yaml
from pathlib import Path
summary_path = Path('runs/pkg40-cycle2/runs-python/pkg40-ade-harbor-task-view-codex/72b3dd571f3c865f/summary.json')
summary = json.loads(summary_path.read_text())
query = summary['datasets']['ade-bench']['queries'][0]
trial = summary['trials'][0]
print(f'summary_path={summary_path}')
print(f'n_trials_total={summary["n_trials_total"]}')
print(f'n_trials_completed={summary["n_trials_completed"]}')
print(f'n_trials_errored={summary["n_trials_errored"]}')
print(f'stratified_pass_at_1={summary["stratified_pass_at_1"]}')
print(f'dataset_keys={list(summary["datasets"].keys())}')
print(f'query_id={query["query_id"]}')
print(f'query_pass_at_1={query["pass_at_1"]}')
print(f'trial_reward={trial["reward"]}')
print(f'trial_stratum={trial["stratum"]}')
run_dir = summary_path.parent
job_config = yaml.safe_load((run_dir / '_job_config.yaml').read_text())
manifest = json.loads((Path(job_config['tasks'][0]['path']) / 'view_manifest.json').read_text())
print(f'job_agent_import={job_config["agents"][0]["import_path"]}')
print(f'job_agent_runtime={job_config["agents"][0]["kwargs"].get("runtime")}')
print(f'manifest_transform={manifest["transform_name"]}')
print(f'manifest_docker={manifest["environment_overrides"]["docker_image_tag"]}')
PY
```

Output:

```text
summary_path=runs/pkg40-cycle2/runs-python/pkg40-ade-harbor-task-view-codex/72b3dd571f3c865f/summary.json
n_trials_total=1
n_trials_completed=1
n_trials_errored=0
stratified_pass_at_1=1.0
dataset_keys=['ade-bench']
query_id=adebench-fixture-001
query_pass_at_1=1.0
trial_reward=1.0
trial_stratum={'dataset': 'ade-bench', 'query_id': 'adebench-fixture-001', 'benchmark_kind': 'ade-bench', 'benchmark_task_id': 'adebench-fixture-001'}
job_agent_import=razorback.agents.spacedock_solver_v2:SpacedockSolverAgent
job_agent_runtime=codex
manifest_transform=ade-bench-harbor-task-view
manifest_docker=python:3.12
```

### AC-4 - PASS

Spider2 live export is still blocked by Harbor package checkout, and
fixture-backed evidence remains acceptable.

```bash
uv run --frozen harbor download spider2-dbt@1.0 --output-dir runs/pkg40-validation-cycle2/spider2-download --export --overwrite
```

Output excerpt:

```text
Downloading dataset: spider2-dbt@1.0
0/64 Downloading tasks...
CalledProcessError: Command '['git', 'checkout', '82d1fb0c144d28b1fd9852006cee0a39e74bd4a8']' returned non-zero exit status 128.
```

Fresh ADE/Spider2 fixture materialization:

```bash
uv run --frozen python - <<'PY'
import json
from pathlib import Path
from razorback.spec.parse import parse_spec_file
from razorback.translate import spec_to_job_config

jobs_dir = Path('runs/pkg40-validation-cycle2/job-configs')
project = Path('runs/pkg40-validation-cycle2/fake-project')
project.mkdir(parents=True, exist_ok=True)
(project / '.env').write_text('OPENAI_API_KEY=sk-validation-placeholder\n')
for name, spec_path in [
    ('ade-validation-cycle2', Path('runs/pkg40-validation-cycle2/pkg40-ade-harbor-task-view-codex.frozen.yaml')),
    ('spider2-validation-cycle2', Path('runs/pkg40-validation-cycle2/pkg40-spider2-dbt-harbor-task-view-codex.frozen.yaml')),
]:
    spec = parse_spec_file(spec_path)
    cfg, _ = spec_to_job_config(spec, job_name=name, jobs_dir=jobs_dir, project_root=project, home=Path('runs/pkg40-validation-cycle2/fake-home'))
    print(f'{spec_path}: n_concurrent_trials={cfg.n_concurrent_trials}; tasks={len(cfg.tasks)}; agent={cfg.agents[0].import_path}; runtime={cfg.agents[0].kwargs.get("runtime")}')
    for task in cfg.tasks:
        view = task.get_local_path()
        manifest = json.loads((view / 'view_manifest.json').read_text())
        print(f'  view={view}')
        print(f'  task_id={manifest["benchmark_task_id"]}; kind={manifest["benchmark_kind"]}; transform={manifest["transform_name"]}; docker={manifest["environment_overrides"]["docker_image_tag"]}; digest={manifest["environment_overrides"]["docker_image_digest"]}')
PY
```

Output:

```text
runs/pkg40-validation-cycle2/pkg40-ade-harbor-task-view-codex.frozen.yaml: n_concurrent_trials=1; tasks=1; agent=razorback.agents.spacedock_solver_v2:SpacedockSolverAgent; runtime=codex
  view=/home/exedev/razorback/.worktrees/spacedock-ensign-pkg40-harbor-task-view-materializer/runs/pkg40-validation-cycle2/job-configs/ade-validation-cycle2/_razorback/task_views/ade-bench-adebench-fixture-001
  task_id=adebench-fixture-001; kind=ade-bench; transform=ade-bench-harbor-task-view; docker=python:3.12; digest=None
runs/pkg40-validation-cycle2/pkg40-spider2-dbt-harbor-task-view-codex.frozen.yaml: n_concurrent_trials=1; tasks=1; agent=razorback.agents.spacedock_solver_v2:SpacedockSolverAgent; runtime=codex
  view=/home/exedev/razorback/.worktrees/spacedock-ensign-pkg40-harbor-task-view-materializer/runs/pkg40-validation-cycle2/job-configs/spider2-validation-cycle2/_razorback/task_views/spider2-dbt-spider2-fixture-001
  task_id=spider2-fixture-001; kind=spider2-dbt; transform=spider2-dbt-harbor-task-view; docker=shared-dbt-duckdb:latest; digest=None
```

### AC-5 - FAIL

Batched same-dataset specs translate with configurable concurrency and retained
task identity, but the public `rk score` path cannot score a completed
task-view run. This is blocking because task identity is not available to the
score loader.

Batching probe:

```bash
uv run --frozen python - <<'PY'
import json, shutil
from pathlib import Path
from razorback.spec.freeze import freeze_spec
from razorback.spec.schema import NopAgentBlock, Spec
from razorback.translate import spec_to_job_config

root = Path('runs/pkg40-validation-cycle2/multi-task-fixtures').resolve()
ade_src = Path('tests/fixtures/ade_bench/tasks/adebench-fixture-001').resolve()
spider_src = Path('tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-001').resolve()
for kind, src, names in [('ade', ade_src, ['adebench-fixture-001', 'adebench-fixture-002']), ('spider', spider_src, ['spider2-fixture-001', 'spider2-fixture-002'])]:
    base = root / kind
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    for name in names:
        shutil.copytree(src, base / name)

for benchmark_kind, tasks_root, tasks, job_name in [
    ('ade-bench', root / 'ade', ['adebench-fixture-001', 'adebench-fixture-002'], 'ade-multi-cycle2'),
    ('spider2-dbt', root / 'spider', ['spider2-fixture-001', 'spider2-fixture-002'], 'spider-multi-cycle2'),
]:
    spec = Spec(version=1, experiment=f'pkg40-{job_name}', agent=NopAgentBlock(kind='nop'), benchmark={'kind': benchmark_kind, 'tasks_root': tasks_root, 'tasks': tasks, 'docker_image_override': 'shared-dbt-duckdb:latest', 'batch_mode': 'per-task'}, concurrency={'trials': 2})
    cfg, _ = spec_to_job_config(spec, job_name=job_name, jobs_dir=Path('runs/pkg40-validation-cycle2/multi-task-jobs'))
    ids = [json.loads((task.path / 'view_manifest.json').read_text())['benchmark_task_id'] for task in cfg.tasks]
    frozen = freeze_spec(spec)
    print(f'{benchmark_kind}: n_concurrent_trials={cfg.n_concurrent_trials}; task_count={len(cfg.tasks)}; ids={ids}; frozen_has_batch_mode={"batch_mode: per-task" in frozen}')
PY
```

Output:

```text
ade-bench: n_concurrent_trials=2; task_count=2; ids=['adebench-fixture-001', 'adebench-fixture-002']; frozen_has_batch_mode=True
spider2-dbt: n_concurrent_trials=2; task_count=2; ids=['spider2-fixture-001', 'spider2-fixture-002']; frozen_has_batch_mode=True
```

Scoring probe:

```bash
uv run --frozen rk score runs/pkg40-cycle2/runs-python/pkg40-ade-harbor-task-view-codex/72b3dd571f3c865f --format json
```

Output:

```text
score input error: trial ade-bench-adebench-fixture-001__NyS5nr6 has no stratum tag (expected agent/stratum.json)
```

Concrete fix: make `src/razorback/score/load.py` resolve benchmark task
identity from `_razorback/task_views/*/view_manifest.json`, matching the
fallback already implemented in `src/razorback/runs/aggregate.py`, or write an
equivalent `agent/stratum.json` sidecar during task-view runs. Add a regression
test for `load_run_dir()` or `rk score` against a task-view run layout without
`stratum.json`.

### AC-6 - PASS

Freeze identity and resume coverage remains green.

```bash
uv run --frozen pytest tests/unit/test_task_identity_scoring.py tests/integration/test_v2_freeze_dir_mechanism.py tests/unit/test_seal_v2_six_inputs.py tests/unit/test_spacedock_solver_v2_class.py -q
```

```text
........................                                                 [100%]
24 passed in 0.32s
```

### AC-7 - PASS

Per-task batching and explicit shared-context behavior remain covered.

```bash
uv run --frozen pytest tests/unit/test_ade_bench_harbor_view.py tests/unit/test_spider2_dbt_harbor_view.py tests/unit/test_ade_bench_schema.py tests/unit/test_ade_bench_translator.py tests/unit/test_ade_bench_translator_local_root.py tests/unit/test_translate_harbor_task_batches.py -q
```

```text
.....................                                                    [100%]
21 passed in 0.41s
```

```bash
uv run --frozen pytest tests/integration/test_pkg40_harbor_task_views_smoke.py -q
```

```text
....                                                                     [100%]
4 passed in 0.13s
```

### AC-8 - PASS

No solution or verifier-answer leakage was found in the materialized validation
views.

```bash
find runs/pkg40-validation-cycle2/job-configs -type f \( -path '*/solution/*' -o -path '*/tests/expected/*' -o -name '*answer*' \) -print
```

```text
```

## Code Review Findings

### Blocking

1. `src/razorback/score/load.py:110-135` only resolves strata from
   `agent/stratum.json`, `logs/verifier/stratum.json`, and
   `steps/*/verifier/stratum.json`. PKG-40 task-view runs retain benchmark
   identity in `_razorback/task_views/*/view_manifest.json`; the aggregator
   uses that fallback, but `rk score` does not. The completed ADE smoke run
   therefore cannot be scored with `rk score`.

### Non-Blocking

1. `uv run rk freeze --out ...` failed when the parent output directory was
   absent. After `mkdir -p runs/pkg40-validation-cycle2`, both freeze commands
   succeeded. This is command setup behavior, not a PKG-40 acceptance blocker.
2. `uv run rk freeze ...` without `--frozen` modified `uv.lock`; that local
   side effect was restored before committing validation artifacts.

## Commands Run

- `git status --short --branch`
- `git log --oneline --decorate --max-count=12`
- `git diff --stat main...HEAD`
- `uv run --frozen python - <<'PY' ... AC-1 validator probe ... PY`
- `uv run --frozen python - <<'PY' ... ADE summary artifact probe ... PY`
- `uv run --frozen pytest tests/unit/test_harbor_task_view_materializer.py tests/unit/test_harbor_task_view_leakage.py -q`
- `uv run --frozen pytest tests/unit/test_ade_bench_harbor_view.py tests/unit/test_spider2_dbt_harbor_view.py tests/unit/test_ade_bench_schema.py tests/unit/test_ade_bench_translator.py tests/unit/test_ade_bench_translator_local_root.py tests/unit/test_translate_harbor_task_batches.py -q`
- `uv run --frozen pytest tests/unit/test_task_identity_scoring.py tests/integration/test_v2_freeze_dir_mechanism.py tests/unit/test_seal_v2_six_inputs.py tests/unit/test_spacedock_solver_v2_class.py -q`
- `uv run --frozen pytest tests/integration/test_pkg40_harbor_task_views_smoke.py -q`
- `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py -q`
- `mkdir -p runs/pkg40-validation-cycle2`
- `uv run rk freeze examples/specs/pkg40-ade-harbor-task-view-codex.yaml --out runs/pkg40-validation-cycle2/pkg40-ade-harbor-task-view-codex.frozen.yaml --allow-missing`
- `uv run rk freeze examples/specs/pkg40-spider2-dbt-harbor-task-view-codex.yaml --out runs/pkg40-validation-cycle2/pkg40-spider2-dbt-harbor-task-view-codex.frozen.yaml --allow-missing`
- `uv run --frozen python - <<'PY' ... ADE/Spider2 materialization probe ... PY`
- `find runs/pkg40-validation-cycle2/job-configs -type f \( -path '*/solution/*' -o -path '*/tests/expected/*' -o -name '*answer*' \) -print`
- `uv run --frozen python - <<'PY' ... multi-task batching probe ... PY`
- `uv run --frozen harbor download spider2-dbt@1.0 --output-dir runs/pkg40-validation-cycle2/spider2-download --export --overwrite`
- `git diff --check`
- `uv run --frozen rk score runs/pkg40-cycle2/runs-python/pkg40-ade-harbor-task-view-codex/72b3dd571f3c865f --format json`

## Completion Checklist

- DONE: Validation cycle 2 report re-checks AC-1 and AC-3 fixes with exact commands/output and confirms all AC-1..AC-8 statuses.
- DONE: Independent code review finds no blocking issue, or rejects with concrete implementation fixes.
- DONE: Stage report gives a gate recommendation and names the ADE summary artifact and Spider2 blocker status.
