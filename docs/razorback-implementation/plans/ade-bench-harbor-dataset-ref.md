# ADE-Bench Harbor Dataset Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Razorback ADE-Bench specs name a published Harbor dataset (e.g. `ade-bench@1.0`) and have Razorback resolve+materialize the task package through Harbor's public dataset client, then layer the resolved tasks under PKG-40's existing task-view materializer (image override, leakage exclusion, runtime env) before handing `TaskConfig(path=...)` to Harbor. Local Harbor-shaped `tasks_root` stays as a dev/fixture escape hatch.

**Architecture:** Add a thin source-resolver layer in `src/razorback/benchmarks/ade_bench/dataset_ref.py` that turns `dataset: ade-bench@1.0` + `tasks: [...]` into a list of resolved local task directories using `harbor.tasks.client.TaskClient.download_tasks([PackageTaskId(...)])`. Each resolved directory then flows through the existing `materialize_ade_harbor_task_view` from PKG-40 — the new boundary is purely "where did the source task dir come from?" The translator's `_build_ade_bench` branch grows one new source path (`dataset_ref` → resolved cache → materializer); the materializer, image-override, leakage-deny, and runtime-tooling layers downstream are unchanged. Record the resolved `content_hash` from `TaskDownloadResult` in `view_manifest.json` and freeze provenance so the dataset version is pinned. Riskiest contract: confirming `TaskClient.download_tasks(PackageTaskId(org="harbor", name="ade-bench", ref="1.0"), output_dir=..., export=True)` yields a directory layout that `materialize_ade_harbor_task_view` already accepts (Harbor-shaped `task.toml` per task). T0 validates that contract before any schema work.

**Tech Stack:** Python 3.12, `uv`, pytest, Pydantic v2, Harbor 0.6.6+ (`harbor.tasks.client.TaskClient`, `harbor.models.task.id.PackageTaskId`), existing Razorback PKG-40 materializer (`src/razorback/harbor_tasks/`, `src/razorback/benchmarks/ade_bench/harbor_view.py`).

---

## AC to Task Map

| AC | Governing cites | Tasks | Focused verification |
| --- | --- | --- | --- |
| AC-1 ADE specs accept a Harbor dataset reference | v2 spec §6.1 benchmark-block translation; §6.3 schema validation; entity Notes (source selection boundary) | T1, T2, T6 | Schema tests cover `dataset` + `tasks` subset, `dataset` alone, and the existing `tasks_root` shape; conflict between `dataset` and `tasks_root` raises a `SpecError` naming both keys. |
| AC-2 Dataset resolution uses Harbor's public resolver | v2 spec §6.1 task translation; Harbor `harbor.tasks.client.TaskClient.download_tasks` + `PackageTaskId(org,name,ref)`; pkg40 plan §"Current Evidence" (Harbor TaskConfig surface) | T0, T3, T4 | Unit test patches `TaskClient.download_tasks` and asserts the translator constructs `PackageTaskId(org="harbor", name="ade-bench", ref="1.0")` and passes the resolved paths to `materialize_ade_harbor_task_view`; manifest records `dataset_ref` + `dataset_content_hash`. |
| AC-3 ADE task views still provide Razorback controls | v2 spec §6.1 (task translation); §6.2 leakage; PKG-40 plan §"Architecture" (consumer transforms route through generic materializer); `src/razorback/benchmarks/ade_bench/harbor_view.py` (image override, dbt-deps layer, deny globs) | T3, T4, T7 | Translator test asserts dataset-ref-resolved tasks flow through `materialize_ade_harbor_task_view` (NOT a bypass), and the resulting view has `[environment].docker_image == docker_image_override`, `RAZORBACK_BENCHMARK_KIND=ade-bench`, dbt-deps Dockerfile layer applied when `packages.yml` is present, and `solution/**` excluded. |
| AC-4 Examples stop teaching local ADE roots as canonical | v2 spec §6.3 example governance; PKG-40 plan T10 docs cleanup | T6 | `rg "tasks_root: .*ade" examples/specs examples/drivers` returns only paths marked `fixture-` / `probe-` / `dev-`; new smoke spec `examples/specs/ade-bench-harbor-dataset-codex.yaml` names `dataset: ade-bench@1.0`; generator emits dataset-ref specs by default. |
| AC-5 No submodule requirement; clear setup errors | entity AC-5; v2 spec §6.1 (offline-shape errors); Harbor `TaskClient` exception surface | T0, T5, T7 | `git submodule status` shows no new entries after the implementation lands; resolver-failure unit test asserts that a `TaskClient.download_tasks` exception surfaces as a `SpecError` naming the dataset ref and the underlying cause; integration smoke runs `rk freeze` on the dataset-ref spec in a clean checkout. |

## Current Evidence and Probe Inputs

External evidence already checked on 2026-05-22:

- Harbor 0.6.6 source at `.venv/lib/python3.12/site-packages/harbor/tasks/client.py:457` exposes `TaskClient.download_tasks(task_ids, overwrite, output_dir, export)`. `PackageTaskId` lives at `harbor/models/task/id.py:35` with `(org, name, ref)`. `BatchDownloadResult.results[i]` includes `.path`, `.content_hash`, `.cached` per task — that is the resolved dataset version handle AC-2 should pin.
- `TaskConfig` (`harbor/models/trial/config.py:128`) accepts a `name`/`ref` package shape natively. The naive option ("just pass `TaskConfig(name='harbor/ade-bench', ref='1.0')` and let Harbor resolve at job time") would bypass our materializer entirely — that breaks AC-3. We must resolve to a local directory ourselves so PKG-40's overrides apply.
- `_download_package_tasks` (`harbor/tasks/client.py:262`) targets `output_dir/<name>/` when `export=True`. Each downloaded task ends up at `<output_dir>/ade-bench/<task-id>/task.toml` (subject to T0 confirmation). The cache layout is `<PACKAGE_CACHE_DIR>/<org>/<name>/<content_hash>/...` when `export=False`.
- PKG-40 already shipped `src/razorback/harbor_tasks/materialize.py` + `src/razorback/benchmarks/ade_bench/harbor_view.py`. `_build_ade_bench` in `src/razorback/translate.py:264` currently resolves sources via `resolve_task_dirs(tasks_root=...)` then calls `materialize_ade_harbor_task_view`. New code grows a sibling source path; the materializer call shape is unchanged.
- `view_manifest.json` schema (`src/razorback/harbor_tasks/manifest.py:43`) has `environment_overrides: dict[str, Any]` already — we add `dataset_ref` and `dataset_content_hash` as new top-level optional fields with `schema_version` bumped to 2.

## Planned Files

| File | Responsibility | Planned action |
| --- | --- | --- |
| `src/razorback/benchmarks/ade_bench/dataset_ref.py` | Parse `ade-bench@1.0` and resolve to local dirs via Harbor | Create. `parse_dataset_ref(s) -> (org, name, ref)`, `resolve_dataset_tasks(dataset_ref, tasks, cache_root) -> list[ResolvedDatasetTask]` calling `TaskClient.download_tasks([PackageTaskId(...)])`. |
| `src/razorback/spec/schema.py` | `AdeBenchBenchmarkBlock` accepts dataset ref | Modify. Add `dataset: str | None`, keep `tasks_root` optional, validator: exactly one of `dataset`/`tasks_root`; `tasks` becomes optional when `dataset` is present (resolve all dataset tasks). |
| `src/razorback/translate.py` | ADE translator dataset-ref branch | Modify `_build_ade_bench`: when `dataset` is set, call `resolve_dataset_tasks` instead of `resolve_task_dirs`, then funnel resolved dirs through the existing `materialize_ade_harbor_task_view` call. Pass `dataset_ref` and `dataset_content_hash` into the materializer. |
| `src/razorback/benchmarks/ade_bench/harbor_view.py` | Materializer accepts dataset provenance kwargs | Modify. Add `dataset_ref: str | None`, `dataset_content_hash: str | None` parameters; thread them through to `materialize_harbor_task_view`. |
| `src/razorback/harbor_tasks/materialize.py` | Generic materializer records dataset provenance | Modify. Add `dataset_ref`, `dataset_content_hash` kwargs; write into manifest. |
| `src/razorback/harbor_tasks/manifest.py` | Manifest schema | Modify. Bump `TASK_VIEW_MANIFEST_SCHEMA_VERSION` to `2`; add `dataset_ref: str | None`, `dataset_content_hash: str | None`. |
| `examples/specs/ade-bench-harbor-dataset-codex.yaml` | Smoke spec | Create. Names `benchmark.kind: ade-bench`, `dataset: ade-bench@1.0`, optional subset. |
| `examples/drivers/generate-codex-benchmark-specs.py` | Generator default | Modify. New ADE score specs emit `dataset:` instead of `tasks_root:`; fixture-only examples keep `tasks_root`. |
| `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml` | Existing local-root probe | Modify. Rename/annotate as `fixture-` to mark it dev-only (AC-4). |
| `tests/fixtures/ade_bench/fake_dataset/` | Fake downloaded-package layout | Create. One or two Harbor-shaped tasks mimicking what `TaskClient.download_tasks(...PackageTaskId, export=True)` produces. |
| `tests/unit/test_ade_bench_dataset_ref_schema.py` | Schema tests for `dataset:` field | Create. |
| `tests/unit/test_ade_bench_dataset_ref_resolver.py` | Resolver tests with patched `TaskClient` | Create. |
| `tests/unit/test_ade_bench_dataset_ref_translator.py` | Translator dataset-ref branch tests | Create. |
| `tests/integration/test_ade_bench_dataset_ref_freeze_smoke.py` | `rk freeze` over dataset-ref spec, no live network | Create. Uses monkeypatched `TaskClient` and asserts `view_manifest.json` + `provenance.yaml` carry `dataset_ref` and `dataset_content_hash`. |
| `docs/razorback-implementation/notes/ade-bench-harbor-dataset-ref-probe.md` | T0 probe evidence note | Create. Records exact `TaskClient.download_tasks` invocation, resolved directory layout, content_hash shape. |

---

## Task 0: Bounded Harbor Dataset-Ref Probe (riskiest-contract first)

This task validates the smallest end-to-end exercise of the riskiest contract: Harbor's `TaskClient.download_tasks([PackageTaskId(org='harbor', name='ade-bench', ref='1.0')], output_dir=..., export=True)` must produce a directory layout that the existing PKG-40 materializer accepts unchanged. If the contract differs from expectations (e.g. tasks are nested under an extra subdir, or Harbor's export layout puts `task.toml` at an unexpected depth), the rest of the plan reshapes the resolver — not the materializer.

**Spec cites:** v2 spec §6.1 task translation; Harbor `TaskClient.download_tasks` (`harbor/tasks/client.py:457`); `PackageTaskId` (`harbor/models/task/id.py:35`).

**Files:**
- Create: `docs/razorback-implementation/notes/ade-bench-harbor-dataset-ref-probe.md`
- Test: no code test; this is bounded discovery for T1–T5.

- [ ] **Step 1: Record Harbor's PackageTaskId surface.**
  Run:
  ```bash
  cd /Users/clkao/git/razorback
  uv run python - <<'PY'
  import inspect
  from harbor.models.task.id import PackageTaskId
  from harbor.tasks.client import TaskClient, BatchDownloadResult, TaskDownloadResult
  print(inspect.getsource(PackageTaskId))
  print(inspect.signature(TaskClient.download_tasks))
  print(inspect.getsource(TaskDownloadResult))
  PY
  ```
  Expected: `PackageTaskId(org, name, ref)`; `download_tasks` returns `BatchDownloadResult` with `.results: list[TaskDownloadResult]` and each result has `.path`, `.content_hash`, `.cached`.

- [ ] **Step 2: Try the actual download (network-permitting).**
  Run:
  ```bash
  uv run python - <<'PY'
  import asyncio
  from pathlib import Path
  from harbor.models.task.id import PackageTaskId
  from harbor.tasks.client import TaskClient
  out = Path("runs/ade-bench-dataset-ref-probe").resolve()
  out.mkdir(parents=True, exist_ok=True)
  result = asyncio.run(TaskClient().download_tasks(
      task_ids=[PackageTaskId(org="harbor", name="ade-bench", ref="1.0")],
      output_dir=out,
      export=True,
      overwrite=True,
  ))
  for r in result.results:
      print(r.path, r.content_hash, r.cached)
  PY
  find runs/ade-bench-dataset-ref-probe -maxdepth 4 -name task.toml | head -5
  ```
  Expected paths: `runs/ade-bench-dataset-ref-probe/ade-bench/<task-slug>/task.toml`. If a `task.toml` exists exactly one or two levels under the export root, the contract matches; otherwise record the actual depth and adjust T1's `resolve_dataset_tasks` accordingly.

- [ ] **Step 3: Identify the per-task slug naming used by Harbor's export.**
  Run:
  ```bash
  ls runs/ade-bench-dataset-ref-probe/ade-bench/ | head -20
  ```
  Expected: per-task subdirectories whose names align with ADE task ids (e.g. `airbnb001`, `airbnb002`). Record any naming surprises (UUID-based, hash-based, etc.) — T2's `tasks: [airbnb001]` subset semantics depend on this.

- [ ] **Step 4: Record content_hash shape.**
  From Step 2 output, note whether `content_hash` is a `sha256:...` string and whether all tasks in one dataset share the dataset-level hash or carry per-task hashes. If shared, AC-2's `dataset_content_hash` is one value; if per-task, the manifest stores a per-task hash plus a dataset-level digest derived from the package archive.

- [ ] **Step 5: If the public download fails (auth, network, registry).**
  Record stdout/stderr verbatim. T0 still passes — the failure becomes the documented blocker for T7's live integration smoke, and T1–T5 proceed against a fake_dataset fixture (no behavior shifts in source code, only test fixtures).

- [ ] **Step 6: Write the probe note.**
  Create `docs/razorback-implementation/notes/ade-bench-harbor-dataset-ref-probe.md` with sections:
  - command outputs (truncated to first/last lines per command);
  - confirmed `PackageTaskId(...)` arg shape;
  - confirmed export directory layout (or actual layout if different);
  - confirmed `content_hash` per-task vs dataset-level;
  - clean-checkout commands (`rm -rf runs/ade-bench-dataset-ref-probe`, Harbor package cache cleanup) and approximate size of downloaded dataset;
  - if download blocked: blocker text suitable to embed in T7's skip reason.

- [ ] **Step 7: Commit.**
  ```bash
  git add docs/razorback-implementation/notes/ade-bench-harbor-dataset-ref-probe.md
  git commit -m "docs(ade-bench-dataset-ref): record harbor TaskClient probe evidence"
  ```

## Task 1: Resolver — RED tests

**Spec cites:** v2 spec §6.1 task translation; Harbor `TaskClient.download_tasks` async surface.

**Files:**
- Create: `tests/unit/test_ade_bench_dataset_ref_resolver.py`
- Create: `tests/fixtures/ade_bench/fake_dataset/airbnb001/task.toml` (+ `instruction.md`, `environment/Dockerfile`, `tests/test.sh`)
- Create: `tests/fixtures/ade_bench/fake_dataset/airbnb002/task.toml` (+ minimal sibling shape)

- [ ] **Step 1: Build the fake-dataset fixture.**
  Mirror Harbor's export layout from T0 evidence: `tests/fixtures/ade_bench/fake_dataset/<slug>/task.toml`. Each `task.toml` carries `schema_version = "1.0"`, `[environment]` with `os = "linux"`, `cpus = 1`, `memory_mb = 1024`, `storage_mb = 1024`, and `docker_image = "ade-source-image:latest"`.

- [ ] **Step 2: Add red test `test_parse_dataset_ref_basic`.**
  Assert `parse_dataset_ref("ade-bench@1.0") == ("harbor", "ade-bench", "1.0")` and `parse_dataset_ref("harbor/ade-bench@1.0") == ("harbor", "ade-bench", "1.0")`. Invalid forms (`"ade-bench"` without `@`, `"@1.0"` without name) raise `SpecError`.

- [ ] **Step 3: Add red test `test_resolve_dataset_tasks_invokes_taskclient`.**
  Monkeypatch `harbor.tasks.client.TaskClient.download_tasks` to a stub that records the `task_ids` argument and returns a `BatchDownloadResult` pointing at the fake-dataset fixture paths. Assert `resolve_dataset_tasks(dataset_ref="ade-bench@1.0", tasks=["airbnb001"], cache_root=tmp_path)` calls `download_tasks` once with `task_ids=[PackageTaskId(org="harbor", name="ade-bench", ref="1.0")]` and `export=True`.

- [ ] **Step 4: Add red test `test_resolve_dataset_tasks_subset_selection`.**
  After the stubbed download writes both `airbnb001` and `airbnb002` into the export dir, assert that `resolve_dataset_tasks(..., tasks=["airbnb001"])` returns exactly one `ResolvedDatasetTask` for `airbnb001` and ignores `airbnb002`. Assert each `ResolvedDatasetTask` carries `path`, `task_slug`, and `content_hash`.

- [ ] **Step 5: Add red test `test_resolve_dataset_tasks_missing_subset_raises`.**
  When `tasks=["airbnb_nope"]` is requested but the resolved dataset only contains `airbnb001`, raise `SpecError` naming both the dataset ref and the missing task id.

- [ ] **Step 6: Add red test `test_resolve_dataset_tasks_taskclient_failure_wraps`.**
  Monkeypatch `download_tasks` to raise `RuntimeError("network unreachable")`. Assert `resolve_dataset_tasks` raises `SpecError` whose message names the dataset ref AND the underlying exception text.

- [ ] **Step 7: Run the red tests.**
  ```bash
  uv run --frozen pytest tests/unit/test_ade_bench_dataset_ref_resolver.py -q
  ```
  Expected: ImportError on `razorback.benchmarks.ade_bench.dataset_ref`.

- [ ] **Step 8: Commit RED tests + fixture.**
  ```bash
  git add tests/unit/test_ade_bench_dataset_ref_resolver.py tests/fixtures/ade_bench/fake_dataset
  git commit -m "test(ade-bench-dataset-ref): red tests for harbor TaskClient resolver"
  ```

## Task 2: Schema — RED tests

**Spec cites:** v2 spec §6.1 benchmark-block schema; §6.3 validation; entity AC-1.

**Files:**
- Create: `tests/unit/test_ade_bench_dataset_ref_schema.py`

- [ ] **Step 1: Add red test `test_schema_accepts_dataset_only`.**
  Parse a spec body with `benchmark: {kind: ade-bench, dataset: "ade-bench@1.0"}` (no `tasks_root`, no `tasks`). Assert `spec.benchmark.dataset == "ade-bench@1.0"` and `spec.benchmark.tasks is None or == []` and `spec.benchmark.tasks_root is None`.

- [ ] **Step 2: Add red test `test_schema_accepts_dataset_with_subset`.**
  Parse `benchmark: {kind: ade-bench, dataset: "ade-bench@1.0", tasks: [airbnb001, airbnb002]}`. Assert both keys round-trip.

- [ ] **Step 3: Add red test `test_schema_keeps_local_tasks_root_compat`.**
  Parse the existing `tasks_root + tasks` shape (current schema). Assert it still validates — this is the dev/fixture escape hatch.

- [ ] **Step 4: Add red test `test_schema_rejects_dataset_plus_tasks_root`.**
  Parse `benchmark: {kind: ade-bench, dataset: "ade-bench@1.0", tasks_root: ./fixtures/ade}`. Assert a `pydantic.ValidationError` (or `SpecError`) names both `dataset` and `tasks_root`.

- [ ] **Step 5: Run the red tests.**
  ```bash
  uv run --frozen pytest tests/unit/test_ade_bench_dataset_ref_schema.py -q
  ```
  Expected: `AdeBenchBenchmarkBlock` has no `dataset` field → tests fail.

- [ ] **Step 6: Commit RED tests.**
  ```bash
  git add tests/unit/test_ade_bench_dataset_ref_schema.py
  git commit -m "test(ade-bench-dataset-ref): red schema tests for dataset field"
  ```

## Task 3: Translator — RED tests

**Spec cites:** v2 spec §6.1 task translation; PKG-40 architecture (consumer transforms route through generic materializer); entity AC-2, AC-3.

**Files:**
- Create: `tests/unit/test_ade_bench_dataset_ref_translator.py`

- [ ] **Step 1: Add red test `test_translator_dataset_ref_calls_resolver_then_materializer`.**
  Monkeypatch both `razorback.benchmarks.ade_bench.dataset_ref.resolve_dataset_tasks` and `razorback.benchmarks.ade_bench.harbor_view.materialize_ade_harbor_task_view`. Assert the translator calls the resolver exactly once with the parsed dataset ref, and calls the materializer once per resolved task, passing `source_task_dir=<resolved.path>`, `task_slug=<resolved.task_slug>`, `dataset_ref="ade-bench@1.0"`, and `dataset_content_hash=<resolved.content_hash>`.

- [ ] **Step 2: Add red test `test_translator_dataset_ref_does_not_call_resolve_task_dirs`.**
  Monkeypatch `razorback.benchmarks.ade_bench.tasks.resolve_task_dirs` to raise if called. Assert dataset-ref specs translate without invoking it (the local `tasks_root` path is not exercised).

- [ ] **Step 3: Add red test `test_translator_emits_taskconfig_path_per_resolved_task`.**
  Assert the resulting `JobConfig.tasks` is a list of `TaskConfig(path=<view_dir>)` entries, one per resolved task; `n_concurrent_trials` reflects `spec.concurrency.trials`; `verifier.disable is False`.

- [ ] **Step 4: Add red test `test_translator_preserves_docker_image_override_through_dataset_path`.**
  With `benchmark.docker_image_override == "shared-dbt-duckdb:latest"`, assert the materializer call receives `docker_image="shared-dbt-duckdb:latest"`. This is the AC-3 guardrail: dataset-ref source selection must NOT bypass the existing image override layer.

- [ ] **Step 5: Run the red tests.**
  ```bash
  uv run --frozen pytest tests/unit/test_ade_bench_dataset_ref_translator.py -q
  ```
  Expected: schema has no `dataset` field yet (also fails) or translator has no dataset-ref branch → tests fail.

- [ ] **Step 6: Commit RED tests.**
  ```bash
  git add tests/unit/test_ade_bench_dataset_ref_translator.py
  git commit -m "test(ade-bench-dataset-ref): red translator tests for dataset-ref path"
  ```

## Task 4: Resolver + Schema + Translator + Manifest — GREEN implementation

**Spec cites:** Harbor `TaskClient.download_tasks` (`harbor/tasks/client.py:457`); `PackageTaskId` (`harbor/models/task/id.py:35`); PKG-40 materializer (`src/razorback/harbor_tasks/materialize.py`, `src/razorback/benchmarks/ade_bench/harbor_view.py`).

**Files:**
- Create: `src/razorback/benchmarks/ade_bench/dataset_ref.py`
- Modify: `src/razorback/spec/schema.py`
- Modify: `src/razorback/translate.py` (only the ADE branch)
- Modify: `src/razorback/benchmarks/ade_bench/harbor_view.py`
- Modify: `src/razorback/harbor_tasks/materialize.py`
- Modify: `src/razorback/harbor_tasks/manifest.py`

- [ ] **Step 1: Implement `parse_dataset_ref` and `resolve_dataset_tasks`.**
  In `src/razorback/benchmarks/ade_bench/dataset_ref.py`:
  ```python
  @dataclass(frozen=True)
  class ResolvedDatasetTask:
      path: Path           # absolute path to the materialized task source dir
      task_slug: str       # the per-task subdir name from Harbor's export
      content_hash: str | None

  def parse_dataset_ref(ref: str) -> tuple[str, str, str]: ...
  def resolve_dataset_tasks(
      *,
      dataset_ref: str,
      tasks: list[str] | None,
      cache_root: Path,
  ) -> list[ResolvedDatasetTask]: ...
  ```
  Default org is `"harbor"` if not prefixed. The function calls `TaskClient().download_tasks(task_ids=[PackageTaskId(...)], output_dir=cache_root, export=True, overwrite=False)` via `_run_async` (mirroring the existing helper in `ade_bench/tasks.py`). Wrap `TaskClient.download_tasks` exceptions in `SpecError(f"failed to resolve dataset '{dataset_ref}': {exc}")`.

- [ ] **Step 2: Update `AdeBenchBenchmarkBlock` schema.**
  In `src/razorback/spec/schema.py`, add `dataset: str | None = None`, make `tasks_root: Path | None = None`, make `tasks: list[str | AdeBenchTaskEntry] | None = None`. Add a `@model_validator(mode="after")` enforcing: exactly one of `dataset` or `tasks_root` is set; `dataset + tasks_root` raises with a message naming both keys; `tasks_root` without `tasks` keeps the existing `min_length=1` requirement; `dataset` without `tasks` means "resolve all tasks in the package".

- [ ] **Step 3: Add dataset-ref branch in `_build_ade_bench`.**
  In `src/razorback/translate.py:264`, when `spec.benchmark.dataset is not None`:
  - Call `resolve_dataset_tasks(dataset_ref=spec.benchmark.dataset, tasks=spec.benchmark.tasks, cache_root=cache_root)`.
  - For each `ResolvedDatasetTask`, call `materialize_ade_harbor_task_view(source_task_dir=r.path, view_root=view_root, task_slug=r.task_slug, docker_image=spec.benchmark.docker_image_override, dataset_ref=spec.benchmark.dataset, dataset_content_hash=r.content_hash)`.
  - Append `TaskConfig(path=materialized)` per task.
  Leave the existing `tasks_root` branch (and the git-task branch) untouched.

- [ ] **Step 4: Extend `materialize_ade_harbor_task_view`.**
  In `src/razorback/benchmarks/ade_bench/harbor_view.py`, accept new optional kwargs `dataset_ref: str | None = None` and `dataset_content_hash: str | None = None` and forward them to `materialize_harbor_task_view`.

- [ ] **Step 5: Extend `materialize_harbor_task_view`.**
  In `src/razorback/harbor_tasks/materialize.py`, accept new optional kwargs `dataset_ref: str | None = None`, `dataset_content_hash: str | None = None`, and write them into the `TaskViewManifest` instance.

- [ ] **Step 6: Bump manifest schema.**
  In `src/razorback/harbor_tasks/manifest.py`, bump `TASK_VIEW_MANIFEST_SCHEMA_VERSION` to `2`; add `dataset_ref: str | None = None`, `dataset_content_hash: str | None = None` fields with defaults so existing PKG-40 callers stay green.

- [ ] **Step 7: Run focused tests.**
  ```bash
  uv run --frozen pytest \
    tests/unit/test_ade_bench_dataset_ref_resolver.py \
    tests/unit/test_ade_bench_dataset_ref_schema.py \
    tests/unit/test_ade_bench_dataset_ref_translator.py \
    tests/unit/test_ade_bench_harbor_view.py \
    tests/unit/test_harbor_task_view_materializer.py \
    tests/unit/test_ade_bench_translator.py \
    tests/unit/test_ade_bench_schema.py -q
  ```
  Expected: all pass. PKG-40 regressions must stay green — if any existing test fails, the new manifest-schema-version bump is the most likely cause; ensure callers writing manifests don't hard-code `schema_version=1`.

- [ ] **Step 8: Commit.**
  ```bash
  git add src/razorback/benchmarks/ade_bench/dataset_ref.py src/razorback/spec/schema.py src/razorback/translate.py src/razorback/benchmarks/ade_bench/harbor_view.py src/razorback/harbor_tasks/materialize.py src/razorback/harbor_tasks/manifest.py
  git commit -m "feat(ade-bench-dataset-ref): resolve harbor dataset refs through TaskClient + materializer"
  ```

## Task 5: Resolver-failure error-path test

**Spec cites:** entity AC-5 ("clear setup errors"); `SpecError` surface.

**Files:**
- Modify: `tests/unit/test_ade_bench_dataset_ref_resolver.py` (add one more test); OR add to `tests/unit/test_ade_bench_dataset_ref_translator.py`

- [ ] **Step 1: Add red test `test_dataset_ref_resolver_failure_translates_to_spec_error`.**
  Patch `TaskClient.download_tasks` to raise `RuntimeError("registry 503")`. Translate a dataset-ref spec; assert `SpecError` is raised, the message contains `"ade-bench@1.0"`, and `"registry 503"` appears in the chained message.

- [ ] **Step 2: Verify the failure is the only effect.**
  Assert no `view_manifest.json` is written under `view_root` after the failure — the materializer must not run on partial resolver state.

- [ ] **Step 3: Run.**
  ```bash
  uv run --frozen pytest tests/unit/test_ade_bench_dataset_ref_translator.py::test_dataset_ref_resolver_failure_translates_to_spec_error -q
  ```
  Expected: green after Task 4's `SpecError` wrapping is in place.

- [ ] **Step 4: Commit.**
  ```bash
  git add tests/unit/test_ade_bench_dataset_ref_translator.py
  git commit -m "test(ade-bench-dataset-ref): assert resolver failure surfaces as SpecError"
  ```

## Task 6: Examples and generator — make dataset ref the canonical path

**Spec cites:** entity AC-4; v2 spec §6.3 example governance.

**Files:**
- Create: `examples/specs/ade-bench-harbor-dataset-codex.yaml`
- Modify: `examples/drivers/generate-codex-benchmark-specs.py`
- Modify (mark as fixture/dev): `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml`

- [ ] **Step 1: Add the canonical smoke spec.**
  Body:
  ```yaml
  experiment: ade-bench-harbor-dataset-codex
  agent:
    kind: spacedock_solver_v2
    model: <pinned-by-generator>
  runtime: codex
  benchmark:
    kind: ade-bench
    dataset: ade-bench@1.0
    tasks: [airbnb001]
    docker_image_override: shared-dbt-duckdb:latest
  trials: 1
  concurrency:
    trials: 1
  ```

- [ ] **Step 2: Update the generator.**
  In `examples/drivers/generate-codex-benchmark-specs.py`, change the ADE-Bench branch to emit `dataset: ade-bench@1.0` by default. Keep an opt-in `--legacy-tasks-root` switch for fixture/dev runs only.

- [ ] **Step 3: Mark the existing local-root probe as fixture-only.**
  Either rename `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml` to keep the `probe-` prefix and append a header comment `# Fixture-only: dev/debug escape hatch. Canonical path is examples/specs/ade-bench-harbor-dataset-codex.yaml.` or move it under `examples/specs/fixtures/`. Match the existing repo convention discovered when reading the directory.

- [ ] **Step 4: Validate AC-4 verification command.**
  ```bash
  rg "tasks_root: .*ade" examples/specs examples/drivers
  ```
  Expected: matches appear only inside files whose names start with `fixture-`, `probe-`, or are under `examples/specs/fixtures/`.

- [ ] **Step 5: Run generator tests.**
  ```bash
  uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py tests/unit/test_claude_benchmark_spec_generator.py -q
  ```
  Expected: generator tests updated to assert dataset-ref output; both pass.

- [ ] **Step 6: Commit.**
  ```bash
  git add examples/specs examples/drivers tests/unit/test_codex_benchmark_spec_generator.py tests/unit/test_claude_benchmark_spec_generator.py
  git commit -m "examples(ade-bench-dataset-ref): canonical dataset-ref specs; mark local-root probes as fixtures"
  ```

## Task 7: Freeze integration smoke (no live network)

**Spec cites:** v2 spec §6.1 task translation; §8.2 freeze provenance; entity AC-2 ("records the resolved dataset version/content hash"), AC-5 (clean checkout).

**Files:**
- Create: `tests/integration/test_ade_bench_dataset_ref_freeze_smoke.py`

- [ ] **Step 1: Build the smoke.**
  Monkeypatch `TaskClient.download_tasks` to point at the `tests/fixtures/ade_bench/fake_dataset` paths and return `BatchDownloadResult(results=[TaskDownloadResult(path=..., content_hash="sha256:abc", cached=False)])`. Invoke the translator end-to-end through `rk freeze` (or the in-process freeze entrypoint used by other integration tests — check `tests/integration/test_v2_freeze_dir_mechanism.py` for the canonical pattern) against `examples/specs/ade-bench-harbor-dataset-codex.yaml`.

- [ ] **Step 2: Assert manifest and provenance.**
  After freeze, assert each `view_manifest.json` contains `"dataset_ref": "ade-bench@1.0"` and `"dataset_content_hash": "sha256:abc"`. Assert `provenance.yaml` (or whichever sidecar `freeze_cmd.py` emits) carries the same dataset_ref + content_hash so frozen specs are pinned.

- [ ] **Step 3: Assert no submodule was added.**
  ```python
  result = subprocess.run(["git", "submodule", "status"], capture_output=True, text=True, cwd=repo_root)
  assert result.stdout.strip() == "" or "ade-bench" not in result.stdout
  ```
  This codifies AC-5's "no submodule requirement" — running this test in CI is the cleanest enforcement.

- [ ] **Step 4: Run the smoke.**
  ```bash
  uv run --frozen pytest tests/integration/test_ade_bench_dataset_ref_freeze_smoke.py -q
  ```
  Expected: pass. If the live download from T0 succeeded, also add an opt-in live smoke gated by an env var (e.g. `RAZORBACK_LIVE_HARBOR=1`); when unset, the test skips with the T0 blocker text from the probe note.

- [ ] **Step 5: Commit.**
  ```bash
  git add tests/integration/test_ade_bench_dataset_ref_freeze_smoke.py
  git commit -m "test(ade-bench-dataset-ref): freeze smoke pins dataset_ref + content_hash"
  ```

## Task 8: Acceptance sweep and docs cleanup

**Spec cites:** v2 spec §3.2 CLI surface; entity completion-checklist items.

- [ ] **Step 1: Run the full focused suite.**
  ```bash
  uv run --frozen pytest \
    tests/unit/test_ade_bench_dataset_ref_schema.py \
    tests/unit/test_ade_bench_dataset_ref_resolver.py \
    tests/unit/test_ade_bench_dataset_ref_translator.py \
    tests/unit/test_ade_bench_harbor_view.py \
    tests/unit/test_harbor_task_view_materializer.py \
    tests/unit/test_translate_harbor_task_batches.py \
    tests/integration/test_ade_bench_dataset_ref_freeze_smoke.py -q
  ```
  Expected: all pass.

- [ ] **Step 2: Confirm AC-4 example sweep.**
  Re-run `rg "tasks_root: .*ade" examples/specs examples/drivers` and paste the empty-or-fixture-only output into the stage report.

- [ ] **Step 3: Confirm AC-5 clean-checkout invariant.**
  ```bash
  git submodule status
  ```
  Expected: no ade-bench / harbor-datasets entry.

- [ ] **Step 4: Update the probe note with final live/fixture status.**
  Append a closing section to `docs/razorback-implementation/notes/ade-bench-harbor-dataset-ref-probe.md` recording the final state (live download confirmed working, or fixture-only path with named blocker).

- [ ] **Step 5: Commit.**
  ```bash
  git add docs/razorback-implementation/notes/ade-bench-harbor-dataset-ref-probe.md
  git commit -m "docs(ade-bench-dataset-ref): close probe note with acceptance evidence"
  ```

## Execution Order Rationale

T0 is first because Harbor's published-dataset resolver surface is the only materially uncertain contract: every downstream task assumes `TaskClient.download_tasks([PackageTaskId(...)], export=True)` produces directories that PKG-40's materializer accepts unchanged. A 10-minute probe protects multi-hour work. T1 (resolver tests) and T2 (schema tests) are independent but written in this order because the resolver's signature constrains the schema's optionality story. T3 (translator tests) follows because the translator binds resolver and schema together. T4 ships the implementation across all four layers in one commit per the "thin consumer transform" pattern PKG-40 established. T5 hardens the AC-5 failure path. T6 flips the canonical-path bit in examples; doing it before T7 lets the freeze smoke target a real example spec rather than an inline test string. T7 closes the AC-2 freeze-provenance loop with monkeypatched I/O, and T8 sweeps acceptance.

## Self-Review

- **AC coverage:** AC-1 → T2; AC-2 → T0, T3, T4 (+ T7 freeze pinning); AC-3 → T3, T4, T7 (manifest carries overrides); AC-4 → T6; AC-5 → T5, T7 (`git submodule status` assertion).
- **Layered under PKG-40, not replacing it:** the materializer call shape (`materialize_ade_harbor_task_view(source_task_dir=..., task_slug=..., docker_image=..., dataset_ref=..., dataset_content_hash=...)`) is the integration point. Image override, leakage deny globs, dbt-deps Dockerfile layer, and `RAZORBACK_BENCHMARK_*` env injection all live inside the existing materializer and are exercised by both `tasks_root` and `dataset` paths.
- **Mechanism validation first:** T0's bounded probe pays the small bill before T1–T7 commit to a `PackageTaskId`-shaped contract.
- **Riskiest contract:** Harbor's `TaskClient.download_tasks` export layout. T0 confirms or reshapes the resolver.
- **No new submodule:** AC-5 is enforced in test code (T7 Step 3), not just claimed in docs.
- **Backwards-compatibility:** the existing `tasks_root` shape stays valid (T2 step 3) as the dev/fixture escape hatch — captain's directive in the entity Notes section.
- **Freeze provenance:** `dataset_ref` and `dataset_content_hash` ride into `view_manifest.json` and `provenance.yaml` (T4 step 6, T7 step 2), so frozen specs reproduce against the same Harbor dataset version.
