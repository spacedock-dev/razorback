# PKG-40 Harbor Task View Materializer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ADE-Bench and Spider2-DBT run through one generic Harbor task view materializer that supports shared images, normal multi-task batching, experimental shared-context batching, freeze/resume safety, task identity, and leakage controls.

**Architecture:** Add a benchmark-neutral materializer under `src/razorback/harbor_tasks/` that takes Harbor-shaped task directories and emits Razorback-owned views plus manifests. Keep ADE-Bench and Spider2-DBT as consumer transforms that select sources, options, and smoke fixtures; Harbor still receives ordinary `TaskConfig(path=...)` entries. Validate the riskiest mechanism first: a materialized task view must round-trip through Harbor `TaskConfig(path=...)`, retain benchmark task identity in scoring, and produce a freeze key that cannot collide when multiple tasks share the same model and solver workflow.

**Tech Stack:** Python 3.12, `uv`, pytest, Pydantic, TOML via `tomllib`/Harbor `TaskConfig.model_validate_toml`, Harbor `JobConfig`/`TaskConfig(path=...)`, Razorback v2 specs, `spacedock_solver_v2`, Codex runtime.

---

## AC to Task Map

| AC | Governing spec cites | Tasks | Focused verification |
| --- | --- | --- | --- |
| AC-1 - Local upstream ADE adapter path is retired or made unreachable for new score specs | v2 spec §6.1 benchmark-block translation; §6.3 validation; §8.2 freeze provenance | T4, T10 | Schema/generator tests reject new `{slug: ...}` plus `ade_bench_root` specs; examples target Harbor-shaped task roots. |
| AC-2 - Generic Harbor task view materializer exists and is benchmark-neutral | v2 spec §6.1 offline adapter contract; Harbor adapter guide task-dir contract; Harbor `TaskConfig(path=...)` | T2, T3 | Unit tests copy/link source task files, patch `[environment].docker_image`, apply env/resource overrides, write manifest checksums/metadata, and feed `TaskConfig(path=view)`. |
| AC-3 - ADE-Bench uses the generic materializer, not an ADE-only adapter | v2 spec §4.3 runtime selection; §6.1 task translation; §7.1 run-dir contract | T4, T8 | ADE Harbor-shaped fixture and `runs/goal4-ade-bench-codex-clean/harbor-data/ade-bench` smoke use generic materializer and `spacedock_solver_v2` Codex. |
| AC-4 - Spider2-DBT uses the same generic materializer | v2 spec §6.1 task translation; Harbor public `spider2-dbt@1.0` registry surface | T1, T5, T8 | Spike records source shape; fixture or live task transforms through the same materializer and smoke-runs or records a concrete access blocker. |
| AC-5 - Batched same-dataset specs are supported without losing task identity | v2 spec §6.3 `trials` translation; §8.3 score stratum grouping; Harbor `JobConfig.n_concurrent_trials` | T6, T7 | Frozen specs include multiple ADE and Spider2 tasks in one Harbor job, configurable `n_concurrent_trials`, and summaries retain `benchmark_task_id`. |
| AC-6 - Freeze/resume is safe for batched and parallel jobs | v2 spec §4.3 freeze-dir contract; §4.4 Harbor-resume interaction; §7.1 `_razorback/freeze` layout; §8.4 sealed hash | T7, T9 | Unit and integration tests prove freeze keys include task identity, concurrent trials do not share one freeze repo, and kill/resume reuses completed trials safely. |
| AC-7 - Shared-context batch mode is explicit and separate from per-task batch mode | v2 spec §4.3 solver workflow bootstrap; §6.1 benchmark translation; §7.1 run-dir artifacts | T6, T8 | Normal multi-task mode emits one Harbor task per benchmark task; shared-context mode emits one auditable Harbor task/workspace with child task identities in metadata. |
| AC-8 - No solution leakage or verifier-data exposure regressions | v2 spec §6.2 `tools_denied`; Harbor adapter guide says `instruction.md` must not include answers; Harbor verifier path contract | T2, T3, T5, T8 | Materializer denylist tests inspect ADE and Spider2 views; known solution/verifier-answer paths are absent from agent-visible files before any live run. |

## Current Evidence and Spike Inputs

Local evidence already checked:

- `src/razorback/benchmarks/ade_bench/tasks.py` currently mixes ADE-specific local upstream materialization, git-task fetching, Docker image rewrite, and solution-file exclusion. PKG-40 extracts the generic Harbor-shaped part and leaves upstream `task.yaml` synthesis behind.
- `src/razorback/translate.py` currently hardcodes `n_concurrent_trials=1` in all benchmark branches and returns `{}` for ADE task identity. PKG-40 must add a real concurrency surface and a benchmark task identity manifest.
- Harbor 0.6.6's `harbor.models.trial.config.TaskConfig` accepts local `path`, git task fields, package `name`, and `source`; `TrialConfig.generate_trial_name()` derives the visible trial prefix from `TaskConfig.get_task_id().get_name()`, which for local tasks is the materialized directory name.
- Harbor `Job._init_trial_configs()` builds trials with nested loops over `range(config.n_attempts)`, task configs, and agents. Razorback must not use `n_attempts` as the only benchmark-trial abstraction when it needs task-scoped freeze keys and scoring strata.
- `src/razorback/runs/aggregate.py` currently resolves strata from `agent/stratum.json`, verifier `stratum.json`, step verifier sidecars, or DAB-like trial-name parsing. PKG-40 should add a stable Razorback sidecar source keyed by task identity instead of relying on trial-name heuristics.

External/current evidence checked on 2026-05-21:

- Harbor adapter guide: generated tasks are standard directories containing `task.toml`, `instruction.md`, `environment/`, `solution/`, and `tests/`, with Harbor consuming the generated directories at run time. Source: <https://www.harborframework.com/docs/datasets/adapters>.
- Harbor public registry lists `spider2-dbt@1.0` with 64 tasks and describes it as DBT/SQL-environment work. Source: <https://harborframework.com/registry> redirects to Harbor Hub.
- Harbor Spider2 parity artifacts exist at `harborframework/parity-experiments` under `refs/pr/201/adapters/spider2-dbt`; `config.yaml` uses `datasets: [{path: datasets/spider2-dbt}]`, `n_concurrent_trials: 4`, and an adapter-local `SpiderAgentDBT`. Source: <https://huggingface.co/datasets/harborframework/parity-experiments/tree/refs%2Fpr%2F201/adapters/spider2-dbt>.
- Direct local source for Harbor's `spider2-dbt` adapter is not installed in this repo's `.venv` package, so T1 is a bounded discovery spike rather than assumed implementation detail.

## Planned Files

| File | Responsibility | Planned action |
| --- | --- | --- |
| `src/razorback/harbor_tasks/materialize.py` | Benchmark-neutral Harbor task view materializer | Create. Copy/link task views, patch TOML with structured parser, apply env/resource overrides, enforce exclude globs, emit manifest. |
| `src/razorback/harbor_tasks/manifest.py` | Manifest dataclasses and checksum helpers | Create. Stable `view_manifest.json` schema with source checksums, transform metadata, `benchmark_kind`, `benchmark_task_id`, `view_mode`. |
| `src/razorback/harbor_tasks/leakage.py` | Solution/verifier-data denylist checks | Create. Shared predicates for source relative paths and post-materialization assertions. |
| `src/razorback/benchmarks/ade_bench/harbor_view.py` | ADE consumer transform | Create. Resolve Harbor-shaped ADE source tasks and call generic materializer with ADE-specific identity and exclude globs. |
| `src/razorback/benchmarks/spider2_dbt/harbor_view.py` | Spider2 consumer transform | Create. Resolve Spider2 task sources or fixture and call generic materializer with Spider2-specific identity and exclude globs. |
| `src/razorback/spec/schema.py` | Benchmark, concurrency, batching schema | Modify. Add `ConcurrencyBlock`, Harbor-shaped ADE/Spider2 benchmark blocks/options, deprecate or reject upstream ADE local entries for new score specs. |
| `src/razorback/spec/freeze.py` and `src/razorback/provenance/freeze_cmd.py` | Freeze validation and sealed inputs | Modify. Include materialization/batching/task identity metadata in frozen specs and sealed hashes where required. |
| `src/razorback/agents/seal.py` and `src/razorback/agents/spacedock_solver_v2.py` | Freeze-key and resume mechanics | Modify. Include task-scoped identity in the runtime freeze key while preserving cross-job `resume_from_freeze` checks. |
| `src/razorback/translate.py` | Spec to Harbor `JobConfig` | Modify. Build materialized task views, set `n_concurrent_trials`, pass `TaskConfig(path=...)`, and write a task identity sidecar for aggregation. |
| `src/razorback/runs/aggregate.py` and score loader tests | Scoring identity | Modify. Resolve `benchmark_task_id` from Razorback's task identity sidecar or view manifest before trial-name fallbacks. |
| `examples/drivers/generate-codex-benchmark-specs.py` | ADE/Spider2 spec generation | Modify. Generate Harbor-shaped ADE and Spider2 specs, normal batching specs, and explicit shared-context specs. |
| `examples/specs/` | Smoke specs | Modify/create. Replace upstream ADE local-path examples with Harbor-shaped roots; add Spider2 smoke/fixture spec if live data is blocked. |
| `tests/unit/test_harbor_task_view_materializer.py` | Generic materializer unit tests | Create. |
| `tests/unit/test_harbor_task_view_leakage.py` | Leakage denylist tests | Create. |
| `tests/unit/test_ade_bench_harbor_view.py` | ADE consumer tests | Create/modify existing ADE tests. |
| `tests/unit/test_spider2_dbt_harbor_view.py` | Spider2 consumer tests | Create. |
| `tests/unit/test_translate_harbor_task_batches.py` | Batching and concurrency translator tests | Create. |
| `tests/integration/test_pkg40_harbor_task_views_smoke.py` | Smallest end-to-end smoke tests | Create. Live sections skip with explicit blocker when data/auth unavailable. |

## Task 1: Bounded Spider2 and Harbor Surface Spike

**Spec cites:** §6.1 benchmark-block translation; §6.3 validation; Harbor adapter guide task-dir contract.

**Files:**
- Create: `docs/razorback-implementation/notes/pkg40-spider2-harbor-surface.md`
- Test: no code test; this is the bounded discovery input for T5 and T8.

- [ ] **Step 1: Record local Harbor model surfaces.**
  Run:
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
  Expected: output shows `TaskConfig(path=...)`, `JobConfig.n_concurrent_trials`, and trial-name derivation from task id.

- [ ] **Step 2: Record installed adapter absence/presence.**
  Run:
  ```bash
  rg -n "spider2|spider2-dbt|SpiderAgentDBT" .venv/lib/python3.12/site-packages/harbor .venv/lib/python3.12/site-packages -g '*.py' -g '*.yaml' -g '*.md'
  ```
  Expected in this VM: no installed Spider2 adapter source. If a future Harbor version includes it, cite the adapter file paths and inspect its task-template path names.

- [ ] **Step 3: Record public Spider2 task source commands.**
  Run:
  ```bash
  uv run harbor download spider2-dbt@1.0 --output-dir runs/pkg40-spider2-download --export --overwrite
  find runs/pkg40-spider2-download -maxdepth 3 -name task.toml | head -5
  ```
  Expected: if public registry download succeeds, at least one `task.toml` is available for T5. If it fails because of registry auth, package size, or network, capture stdout/stderr and use a minimal fixture in T5.

- [ ] **Step 4: Record web/public parity artifacts used.**
  Run:
  ```bash
  curl -L --fail --silent https://huggingface.co/datasets/harborframework/parity-experiments/raw/refs%2Fpr%2F201/adapters/spider2-dbt/config.yaml
  curl -L --fail --silent https://huggingface.co/datasets/harborframework/parity-experiments/raw/refs%2Fpr%2F201/adapters/spider2-dbt/README.md
  ```
  Expected: `config.yaml` names `datasets/spider2-dbt`, `n_concurrent_trials`, and the adapter-local `SpiderAgentDBT`; README names the parity command and task ids.

- [ ] **Step 5: Write the note.**
  Create `docs/razorback-implementation/notes/pkg40-spider2-harbor-surface.md` with sections:
  - commands run and outputs summarized;
  - Spider2 source status: live Harbor download path or fixture blocker;
  - observed solution/verifier directories to exclude;
  - minimum local fixture shape for T5 if live data is blocked.

- [ ] **Step 6: Commit.**
  ```bash
  git add docs/razorback-implementation/notes/pkg40-spider2-harbor-surface.md
  git commit -m "docs(pkg40): record spider2 harbor surface spike"
  ```

## Task 2: Generic Materializer RED Tests

**Spec cites:** §6.1 offline task-generator contract; §7.1 run-dir layout; Harbor adapter guide generated task-dir contract.

**Files:**
- Create: `tests/unit/test_harbor_task_view_materializer.py`
- Create: `tests/unit/test_harbor_task_view_leakage.py`

- [ ] **Step 1: Add a source Harbor task fixture builder in the test file.**
  The fixture should create:
  ```text
  source/task.toml
  source/instruction.md
  source/environment/Dockerfile
  source/tests/test.sh
  source/solution/solve.sh
  source/data/input.csv
  source/data/answers.csv
  ```
  `task.toml` must contain `[task] name = "fixture/source-task"` and `[environment] docker_image = "source-image:latest"` plus `cpus = 1`.

- [ ] **Step 2: Add red test `test_materializer_patches_task_toml_and_manifest`.**
  Assert a future `materialize_harbor_task_view(...)`:
  - emits `task.toml`, `instruction.md`, `environment/`, `tests/`, and `data/input.csv`;
  - patches `[environment].docker_image` to `"shared-dbt-duckdb:latest"`;
  - adds `[environment.env] RAZORBACK_BENCHMARK_TASK_ID = "task-001"`;
  - overrides `cpus` and `memory_mb`;
  - writes `view_manifest.json` with source path, source checksums, benchmark kind, benchmark task id, transform name, and view mode.

- [ ] **Step 3: Add red test `test_materializer_excludes_solution_and_answer_paths`.**
  Assert `solution/solve.sh` and `data/answers.csv` are absent from the view and the leakage checker raises if either path appears after materialization.

- [ ] **Step 4: Add red test `test_materialized_view_is_harbor_taskconfig_path_ready`.**
  Instantiate `harbor.models.trial.config.TaskConfig(path=view_dir)` and assert `get_local_path() == view_dir.resolve()` and `get_task_id().get_name()` equals the materialized directory name.

- [ ] **Step 5: Run the red tests.**
  ```bash
  uv run --frozen pytest tests/unit/test_harbor_task_view_materializer.py tests/unit/test_harbor_task_view_leakage.py -q
  ```
  Expected before implementation: import failure for `razorback.harbor_tasks`.

- [ ] **Step 6: Commit RED tests.**
  ```bash
  git add tests/unit/test_harbor_task_view_materializer.py tests/unit/test_harbor_task_view_leakage.py
  git commit -m "test(pkg40): red tests for generic harbor task materializer"
  ```

## Task 3: Generic Materializer Implementation

**Spec cites:** §6.1 benchmark-block translation; §8.1 `rk run` pass-through; Harbor task TOML schema.

**Files:**
- Create: `src/razorback/harbor_tasks/__init__.py`
- Create: `src/razorback/harbor_tasks/materialize.py`
- Create: `src/razorback/harbor_tasks/manifest.py`
- Create: `src/razorback/harbor_tasks/leakage.py`
- Test: `tests/unit/test_harbor_task_view_materializer.py`
- Test: `tests/unit/test_harbor_task_view_leakage.py`

- [ ] **Step 1: Implement manifest dataclasses.**
  Add `TaskViewManifest` with fields:
  `schema_version`, `source_task_dir`, `source_checksums`, `benchmark_kind`, `benchmark_task_id`, `transform_name`, `view_mode`, `excluded_globs`, `environment_overrides`, `created_at`.

- [ ] **Step 2: Implement leakage path matching.**
  Add `DEFAULT_SOLUTION_DENY_GLOBS = ("solution/**", "solutions/**", "**/solution.*", "**/answer*", "**/*answers*", "tests/expected/**")` and `assert_no_denied_paths(view_dir, deny_globs=...)`.

- [ ] **Step 3: Implement `materialize_harbor_task_view`.**
  Signature:
  ```python
  def materialize_harbor_task_view(
      *,
      source_task_dir: Path,
      view_root: Path,
      benchmark_kind: str,
      benchmark_task_id: str,
      transform_name: str,
      docker_image: str | None = None,
      environment_env: dict[str, str] | None = None,
      resource_overrides: dict[str, int] | None = None,
      exclude_globs: tuple[str, ...] = DEFAULT_SOLUTION_DENY_GLOBS,
      view_mode: Literal["copy", "link"] = "copy",
  ) -> Path:
  ```
  Use `tomllib` plus `harbor.models.task.config.TaskConfig.model_validate_toml` and `model_dump_toml()` for TOML mutation. Do not string-patch TOML.

- [ ] **Step 4: Preserve Harbor execution shape.**
  The function returns a local directory path only. It must not import `JobConfig`, start Harbor, or construct benchmark-specific objects. Callers will wrap it as `TaskConfig(path=view_dir)`.

- [ ] **Step 5: Run focused tests.**
  ```bash
  uv run --frozen pytest tests/unit/test_harbor_task_view_materializer.py tests/unit/test_harbor_task_view_leakage.py -q
  ```
  Expected: all generic materializer tests pass.

- [ ] **Step 6: Commit.**
  ```bash
  git add src/razorback/harbor_tasks tests/unit/test_harbor_task_view_materializer.py tests/unit/test_harbor_task_view_leakage.py
  git commit -m "feat(pkg40): add generic harbor task view materializer"
  ```

## Task 4: ADE Consumer Transform and Local Upstream Retirement

**Spec cites:** §6.1 benchmark-block translation; §6.3 validation; §8.2 freeze provenance.

**Files:**
- Create: `src/razorback/benchmarks/ade_bench/harbor_view.py`
- Modify: `src/razorback/benchmarks/ade_bench/tasks.py`
- Modify: `src/razorback/spec/schema.py`
- Modify: `src/razorback/translate.py`
- Modify: `examples/drivers/generate-codex-benchmark-specs.py`
- Modify: `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml`
- Test: `tests/unit/test_ade_bench_harbor_view.py`
- Test: existing ADE schema/translator/generator tests

- [ ] **Step 1: Add red tests for ADE using generic materializer.**
  In `tests/unit/test_ade_bench_harbor_view.py`, build a Harbor-shaped ADE source task with `task.toml`, `instruction.md`, `environment/`, `tests/`, and a fake solution file. Assert `materialize_ade_harbor_task_view(...)` calls `materialize_harbor_task_view` and writes a manifest with `benchmark_kind="ade-bench"` and `benchmark_task_id` equal to the ADE task slug.

- [ ] **Step 2: Add red schema/generator tests rejecting new upstream ADE local entries.**
  Assert specs generated for score runs no longer emit:
  ```yaml
  benchmark:
    kind: ade-bench
    ade_bench_root: ...
    tasks:
      - slug: ...
  ```
  and that parsing this shape for new `ade-bench` specs raises a `SpecError` or Pydantic validation error naming Harbor-shaped task roots.

- [ ] **Step 3: Implement ADE consumer transform.**
  Move Harbor-shaped path handling to `harbor_view.py`. Keep any legacy upstream `task.yaml` support either unreachable from generator output or behind an explicitly named legacy compatibility path that new score specs cannot select.

- [ ] **Step 4: Update translator branch.**
  `_build_ade_bench` should call the ADE consumer transform for every ADE task and append `TaskConfig(path=materialized_view)`. It should no longer call ADE-only materialization for Harbor-shaped score specs.

- [ ] **Step 5: Update examples/generator.**
  Point ADE examples at Harbor-shaped task roots such as `runs/goal4-ade-bench-codex-clean/harbor-data/ade-bench` or a checked-in minimal fixture. Do not embed `~/git/ade-bench` in new score specs.

- [ ] **Step 6: Run focused tests.**
  ```bash
  uv run --frozen pytest tests/unit/test_ade_bench_harbor_view.py tests/unit/test_ade_bench_schema.py tests/unit/test_ade_bench_translator.py tests/unit/test_codex_benchmark_spec_generator.py -q
  ```
  Expected: all pass; any legacy tests that intentionally cover upstream `task.yaml` are renamed with `legacy` in the test name.

- [ ] **Step 7: Commit.**
  ```bash
  git add src/razorback/benchmarks/ade_bench src/razorback/spec/schema.py src/razorback/translate.py examples/drivers/generate-codex-benchmark-specs.py examples/specs tests/unit
  git commit -m "feat(pkg40): route ade bench through generic harbor task views"
  ```

## Task 5: Spider2 Consumer Transform

**Spec cites:** §6.1 benchmark-block translation; §6.3 validation; Harbor public `spider2-dbt@1.0` task surface.

**Files:**
- Create: `src/razorback/benchmarks/spider2_dbt/__init__.py`
- Create: `src/razorback/benchmarks/spider2_dbt/harbor_view.py`
- Create: `tests/unit/test_spider2_dbt_harbor_view.py`
- Create: `tests/fixtures/spider2_dbt/harbor_task_minimal/<task>/...`
- Modify: `src/razorback/spec/schema.py`
- Modify: `src/razorback/translate.py`

- [ ] **Step 1: Add a minimal Spider2 fixture from T1 evidence.**
  If T1 downloaded a real task, reduce it to the smallest Harbor-shaped fixture preserving directory names relevant to leakage checks. If live download was blocked, create a synthetic fixture with `task.toml`, `instruction.md`, `environment/Dockerfile`, `tests/test.sh`, `solution/solve.sh`, and a dbt project directory.

- [ ] **Step 2: Add red schema tests.**
  Add `Spider2DbtBenchmarkBlock` tests for:
  - `kind: spider2-dbt`;
  - `tasks_root: Path`;
  - `tasks: list[str]`;
  - `docker_image_override: str | None`;
  - `batch_mode: "per-task" | "shared-context"` defaulting to `"per-task"`.

- [ ] **Step 3: Add red transform tests.**
  Assert `materialize_spider2_harbor_task_view(...)` uses the generic materializer and writes `benchmark_kind="spider2-dbt"`, `benchmark_task_id=<slug>`, and Spider2-specific deny globs.

- [ ] **Step 4: Implement Spider2 consumer transform.**
  The module should resolve `<tasks_root>/<slug>/task.toml`, call `materialize_harbor_task_view`, inject `RAZORBACK_BENCHMARK_KIND`, `RAZORBACK_BENCHMARK_TASK_ID`, and optional shared image overrides.

- [ ] **Step 5: Wire translator.**
  Add a `Spider2DbtBenchmarkBlock` branch to `spec_to_job_config`, returning `TaskConfig(path=view)` entries and a task identity map.

- [ ] **Step 6: Run focused tests.**
  ```bash
  uv run --frozen pytest tests/unit/test_spider2_dbt_harbor_view.py tests/unit/test_compat_translator.py -q
  ```
  Expected: pass.

- [ ] **Step 7: Commit.**
  ```bash
  git add src/razorback/benchmarks/spider2_dbt src/razorback/spec/schema.py src/razorback/translate.py tests/fixtures/spider2_dbt tests/unit/test_spider2_dbt_harbor_view.py
  git commit -m "feat(pkg40): add spider2 dbt harbor task view consumer"
  ```

## Task 6: Normal Batching, Concurrency, and Shared-Context Schema

**Spec cites:** §6.1 benchmark translation; §6.3 `trials` translation; §8.3 scoring strata.

**Files:**
- Modify: `src/razorback/spec/schema.py`
- Modify: `src/razorback/translate.py`
- Modify: `examples/drivers/generate-codex-benchmark-specs.py`
- Create: `tests/unit/test_translate_harbor_task_batches.py`
- Modify: generator tests

- [ ] **Step 1: Add red concurrency tests.**
  Create tests that parse:
  ```yaml
  concurrency:
    trials: 3
  ```
  and assert translated `JobConfig.n_concurrent_trials == 3` for ADE and Spider2 specs.

- [ ] **Step 2: Add red normal batching tests.**
  Assert a spec with `tasks: [task-a, task-b]` produces two materialized `TaskConfig(path=...)` entries, one view manifest per task, and `batch_mode="per-task"` in frozen/spec JSON.

- [ ] **Step 3: Add red shared-context tests.**
  Assert `batch_mode: shared-context` produces exactly one Harbor task view directory with:
  - a manifest listing child task ids in order;
  - a single `instruction.md` that references the shared workspace but not solution files;
  - child identity metadata for scoring.

- [ ] **Step 4: Implement `ConcurrencyBlock`.**
  Add:
  ```python
  class ConcurrencyBlock(BaseModel):
      model_config = ConfigDict(extra="forbid")
      trials: int = Field(default=1, ge=1)
  ```
  and `concurrency: ConcurrencyBlock = Field(default_factory=ConcurrencyBlock)` on `Spec`.

- [ ] **Step 5: Implement batch layout selection.**
  Add per-benchmark fields for `batch_mode`. In `per-task`, each benchmark task becomes one Harbor task. In `shared-context`, a consumer-specific helper builds one synthetic Harbor task view containing child task descriptors and calls the generic materializer for shared environment/TOML handling.

- [ ] **Step 6: Run focused tests.**
  ```bash
  uv run --frozen pytest tests/unit/test_translate_harbor_task_batches.py tests/unit/test_codex_benchmark_spec_generator.py -q
  ```
  Expected: pass.

- [ ] **Step 7: Commit.**
  ```bash
  git add src/razorback/spec/schema.py src/razorback/translate.py examples/drivers/generate-codex-benchmark-specs.py tests/unit/test_translate_harbor_task_batches.py tests/unit/test_codex_benchmark_spec_generator.py
  git commit -m "feat(pkg40): add harbor task batching and concurrency schema"
  ```

## Task 7: Task Identity in Scoring and Freeze Keys

**Spec cites:** §4.3 sealed inputs; §4.4 Harbor-resume interaction; §7.1 freeze layout; §8.3 scoring.

**Files:**
- Modify: `src/razorback/agents/seal.py`
- Modify: `src/razorback/agents/spacedock_solver_v2.py`
- Modify: `src/razorback/spec/freeze.py`
- Modify: `src/razorback/runs/aggregate.py`
- Create: `tests/unit/test_task_identity_scoring.py`
- Create/modify: `tests/integration/test_v2_freeze_dir_mechanism.py`

- [ ] **Step 1: Add red scoring identity tests.**
  Build a fake run-dir with two completed trial dirs whose trial names are random but whose task view manifests map to `ade-bench-airbnb001` and `spider2-dbt-airport001`. Assert `summary.json` and `per_trial_outcomes.json` carry those task ids as strata.

- [ ] **Step 2: Add red freeze collision tests.**
  Instantiate two `SpacedockSolverAgent` objects with identical model, runtime, solver workflow hash, and harbor kwargs but different `benchmark_task_id`. Assert `resolve_freeze_dir()` differs.

- [ ] **Step 3: Extend sealed inputs.**
  Add task identity fields to freeze/runtime kwargs:
  - `benchmark_kind`;
  - `benchmark_task_id`;
  - `batch_mode`;
  - for shared-context, a stable hash of ordered child task ids.
  Keep `resume_from_freeze` refusal behavior: a resume only passes when the task identity metadata matches.

- [ ] **Step 4: Add a task identity sidecar for aggregation.**
  During translation/run setup, write a Razorback-owned map under the run-dir, for example `_razorback/task_views/{view_name}/view_manifest.json`. Aggregation should resolve each trial's local task path to the corresponding manifest before falling back to old trial-name parsing.

- [ ] **Step 5: Run focused tests.**
  ```bash
  uv run --frozen pytest tests/unit/test_task_identity_scoring.py tests/integration/test_v2_freeze_dir_mechanism.py -q
  ```
  Expected: pass.

- [ ] **Step 6: Commit.**
  ```bash
  git add src/razorback/agents src/razorback/spec/freeze.py src/razorback/runs/aggregate.py tests/unit/test_task_identity_scoring.py tests/integration/test_v2_freeze_dir_mechanism.py
  git commit -m "feat(pkg40): key freeze and scoring by benchmark task identity"
  ```

## Task 8: Smallest End-to-End Mechanism Smokes

**Spec cites:** §3.2 `rk freeze`; §4.3 runtime selection; §6.1 task translation; §7.1 run-dir contract.

**Files:**
- Create: `tests/integration/test_pkg40_harbor_task_views_smoke.py`
- Create/modify: `examples/specs/pkg40-ade-harbor-task-view-codex.yaml`
- Create/modify: `examples/specs/pkg40-spider2-dbt-harbor-task-view-codex.yaml`

- [ ] **Step 1: Add ADE fixture-backed smoke.**
  The smoke should freeze and run the smallest ADE Harbor-shaped fixture with `agent.kind: spacedock_solver_v2`, `runtime: codex`, and verifier enabled. Expected: `summary.json` exists, `benchmark_kind` is ADE, and the per-trial stratum contains the original ADE task id.

- [ ] **Step 2: Add Spider2 fixture/live smoke.**
  If T1 live download succeeded, select one small Spider2 task. If not, use the fixture and mark the live section skipped with the T1 blocker text. Expected fixture smoke: same generic transform path, same Codex solver path, and valid summary.

- [ ] **Step 3: Add normal multi-task batch smoke.**
  Build one frozen spec with two ADE tasks or one ADE plus one Spider2 fixture if mixed benchmark is supported only by an explicit test fixture. Assert Harbor receives multiple `TaskConfig(path=...)` entries and `n_concurrent_trials` matches `concurrency.trials`.

- [ ] **Step 4: Add shared-context layout smoke without a full expensive run.**
  Generate/freeze a shared-context spec and inspect the materialized task layout. The live Harbor run can be omitted if the single-task fixture verifier is not meaningful; the layout test must prove the child task identities are auditable.

- [ ] **Step 5: Run the smoke suite.**
  ```bash
  uv run --frozen pytest tests/integration/test_pkg40_harbor_task_views_smoke.py -q
  ```
  Expected: fixture-backed checks pass; live Spider2 check either passes or skips with the T1 blocker message.

- [ ] **Step 6: Commit.**
  ```bash
  git add tests/integration/test_pkg40_harbor_task_views_smoke.py examples/specs/pkg40-*.yaml
  git commit -m "test(pkg40): smoke harbor task views through codex solver"
  ```

## Task 9: Kill/Resume and Parallel Safety Exercise

**Spec cites:** §4.4 Harbor-resume interaction; §7.1 `_razorback/freeze` layout; §8.4 runtime adaptation.

**Files:**
- Create/modify: `tests/integration/test_pkg40_freeze_resume_batch.py`
- Possibly modify: `src/razorback/agents/spacedock_solver_v2.py`

- [ ] **Step 1: Add deterministic two-task resume test.**
  Use a nop or cheap fixture agent mode if available; otherwise monkeypatch the solver to write freeze state and exit before result. Simulate Harbor resume by removing incomplete trial dirs and re-running translation against the same frozen spec.

- [ ] **Step 2: Assert no collision under parallelism.**
  The test must assert two tasks with the same sealed model/workflow inputs have two distinct freeze dirs because their task identity differs.

- [ ] **Step 3: Assert completed trial reuse/skip behavior.**
  Complete one trial, interrupt another, rerun. Expected: the completed trial remains counted once; the incomplete trial restores from its task-scoped freeze dir.

- [ ] **Step 4: Run focused tests.**
  ```bash
  uv run --frozen pytest tests/integration/test_pkg40_freeze_resume_batch.py tests/integration/test_v2_freeze_dir_mechanism.py -q
  ```
  Expected: pass.

- [ ] **Step 5: Commit.**
  ```bash
  git add tests/integration/test_pkg40_freeze_resume_batch.py src/razorback/agents/spacedock_solver_v2.py
  git commit -m "test(pkg40): prove batched freeze resume task isolation"
  ```

## Task 10: Acceptance Sweep and Documentation Cleanup

**Spec cites:** §3.2 CLI surface; §6.1 benchmark translation; §6.2 leakage controls; §8.1 run wrapper.

**Files:**
- Modify: `README.md` or benchmark docs only if existing docs point at retired upstream ADE local shape.
- Modify: `docs/razorback-implementation/notes/pkg40-spider2-harbor-surface.md` only to add final live/fixture status.
- No workflow history edits.

- [ ] **Step 1: Run focused unit suites.**
  ```bash
  uv run --frozen pytest \
    tests/unit/test_harbor_task_view_materializer.py \
    tests/unit/test_harbor_task_view_leakage.py \
    tests/unit/test_ade_bench_harbor_view.py \
    tests/unit/test_spider2_dbt_harbor_view.py \
    tests/unit/test_translate_harbor_task_batches.py \
    tests/unit/test_task_identity_scoring.py -q
  ```
  Expected: all pass.

- [ ] **Step 2: Run integration mechanism suites.**
  ```bash
  uv run --frozen pytest \
    tests/integration/test_pkg40_harbor_task_views_smoke.py \
    tests/integration/test_pkg40_freeze_resume_batch.py \
    tests/integration/test_v2_freeze_dir_mechanism.py -q
  ```
  Expected: all fixture-backed tests pass; any live Spider2 skip names the T1 blocker.

- [ ] **Step 3: Freeze representative specs.**
  ```bash
  uv run rk freeze examples/specs/pkg40-ade-harbor-task-view-codex.yaml --allow-missing
  uv run rk freeze examples/specs/pkg40-spider2-dbt-harbor-task-view-codex.yaml --allow-missing
  ```
  Expected: frozen specs include solver workflow hashes, batching metadata, and task identity fields.

- [ ] **Step 4: Run leakage scan command.**
  ```bash
  rg -n "solution|answer|expected" runs/pkg40-* -g '!view_manifest.json' -g '!tests/**'
  ```
  Expected: no agent-visible solution or answer files appear in materialized views. If verifier files legitimately contain these words under `tests/`, they remain excluded from the scan or documented as verifier-only.

- [ ] **Step 5: Update docs/examples.**
  Remove or mark obsolete examples that teach new score runs to use `ade_bench_root` with `{slug: ...}`. Keep historical archived docs untouched.

- [ ] **Step 6: Commit.**
  ```bash
  git add docs README.md examples/specs docs/razorback-implementation/notes/pkg40-spider2-harbor-surface.md
  git commit -m "docs(pkg40): document harbor task view batching acceptance"
  ```

## Operational Hardening Addendum

This addendum is part of acceptance for PKG-40 implementation, not a follow-up project.

### Shared Image Lifecycle

- The implementation must treat shared ADE/Spider2 images as pinned run inputs. If a spec names a mutable tag such as `dab-agent:latest` or a shared dbt/DuckDB tag, freeze must record both the authored tag and the resolved image digest in `provenance.yaml` or the materialized `view_manifest.json`.
- Materialized `task.toml` rewrites must set `[environment].docker_image` and leave `EnvironmentConfig.force_build=False` unless the spec explicitly requests a rebuild. This avoids accidental Dockerfile rebuild drift when Harbor's prebuilt-image path is active.
- The T1/T10 spike/acceptance notes must record the Harbor version and any observed upstream WIP around prebuilt/shared-image behavior. If Harbor changes the prebuilt contract, PKG-40 should fail closed with a clear `SpecError` rather than silently rebuilding task images.
- Tests should assert the materializer records `docker_image_tag`, `docker_image_digest` when resolvable, `force_build=false`, and the Harbor version used for the smoke.

### Disk, Storage, and Cleanup

- All materialized views must live under a bounded Razorback-owned root inside the run directory or staged Harbor home, not an untracked global temp path. `view_manifest.json` should record view byte size, source byte size or checksum set, and whether the view uses copy or link mode.
- Spider2/ADE downloaded task data must be either under the run-scoped task cache or a documented Harbor cache path. The spike note should name the path and include cleanup commands such as `rm -rf runs/pkg40-*` plus Harbor cache/image cleanup commands that are safe for the operator to choose.
- Freeze dirs are intentionally durable under `<run-dir>/_razorback/freeze/`; acceptance docs must report their count and total size after the resume smoke so reviewers can tell whether shared-context and parallel tests create bounded state.
- Docker image/cache growth is not automatically pruned by implementation tests. Acceptance must document the images pulled/built, their tags/digests when available, and any manual `docker image ls` / `docker system df` evidence used to estimate local storage impact.

### Concurrency and Resource Guardrails

- `concurrency.trials` must default conservatively for Docker runs and reject obviously unsafe local values unless an explicit override is provided. The first implementation should cap local Docker `n_concurrent_trials` at a small tested value such as 4, with the cap named in schema validation errors and docs.
- Per-task resource overrides from `task.toml` (`cpus`, `memory_mb`, `storage_mb`, `gpus`) and any spec-level overrides must be surfaced in the view manifest. Shared-context mode must account for aggregate resource pressure rather than multiplying tasks silently.
- Infrastructure failures from Docker capacity, image pull/build errors, disk exhaustion, Harbor task download failures, or runs-dir mount visibility must be classified separately from model/verifier reward. `summary.json` / `per_trial_outcomes.json` should preserve a machine-readable infra error reason and avoid scoring those failures as model correctness unless the existing scoring contract explicitly requires it.
- Acceptance smokes should include one intentionally over-cap concurrency or resource fixture that fails before Harbor dispatch with a `SpecError`/config error, proving the guardrail is pre-run and not a late model-score artifact.

## Execution Order Rationale

T1 is first because Spider2's live source shape is the only materially uncertain surface. T2-T3 then prove the generic Harbor task view mechanism in isolation before any benchmark-specific code uses it. T4 and T5 are intentionally thin consumer transforms, so reviewer attention can stay on whether both benchmarks call the same generic materializer.

T6 introduces batching only after per-task materialization works. T7 follows immediately because batching without task-scoped scoring and freeze keys would create the highest-risk regression: multiple tasks with identical solver inputs colliding in `_razorback/freeze/<sealed_hash>/`. T8 and T9 are the smallest end-to-end exercises before the final acceptance sweep; full benchmark matrix runs remain out of scope.

## Self-Review

- AC coverage: AC-1 maps to T4/T10; AC-2 to T2/T3; AC-3 to T4/T8; AC-4 to T1/T5/T8; AC-5 to T6/T7; AC-6 to T7/T9; AC-7 to T6/T8; AC-8 to T2/T3/T5/T8/T10.
- Generic versus benchmark-specific split: the materializer lives only under `src/razorback/harbor_tasks/`; ADE and Spider2 modules only resolve sources, set identity, choose excludes, and pass options.
- Spike boundedness: T1 names exact local, Harbor CLI, and web commands and defines fixture fallback if live Spider2 data access is blocked.
- Collision safety: T7 and T9 require task identity in freeze keys and resume tests before acceptance runs.
- Leakage controls: generic denylist plus ADE/Spider2-specific view inspection tests run before live agent smokes.
