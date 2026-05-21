---
id: dy0w211g9dp8w80jyje1rgz9
title: PKG-40 Harbor task view materializer for ADE-Bench and Spider2-DBT
status: validation
source: captain request 2026-05-21 - Harbor-shaped ADE plus Spider2-DBT shared-image, batching, freeze/resume path
started: 2026-05-21T22:35:16Z
completed:
verdict:
score: 0.95
worktree: .worktrees/spacedock-ensign-pkg40-harbor-task-view-materializer
issue:
pr:
mod-block:
---

## Problem

Razorback should run Harbor-native benchmark task sets without benchmark-specific
one-off adapters in the execution path. ADE-Bench and Spider2-DBT should both
consume Harbor-shaped task directories through a generic view-materialization
layer that can patch task definitions, use shared images, run Spacedock/Codex
solvers, batch same-dataset tasks when requested, and preserve freeze/resume
semantics under parallel execution.

## Acceptance criteria

**AC-1 - Local upstream ADE adapter path is retired or made unreachable for new score specs.**
Verified by: schema/generator tests reject or stop emitting `ade_bench_root` plus
`{slug: ...}` local-task specs, and existing examples/docs point score runs at
Harbor-shaped task roots instead.

**AC-2 - Generic Harbor task view materializer exists and is benchmark-neutral.**
Verified by: focused unit tests create a source Harbor task directory and assert
the view layer can copy or link task files, patch `task.toml`, inject
`[environment].docker_image`, add env/resource overrides, record source
checksums plus transform metadata, and leave Harbor execution to `TaskConfig(path=...)`.

**AC-3 - ADE-Bench uses the generic materializer, not an ADE-only adapter.**
Verified by: an ADE Harbor-shaped task under
`runs/goal4-ade-bench-codex-clean/harbor-data/ade-bench` is transformed through
the generic view layer, runs with a shared dbt/DuckDB image, and completes a
smoke `rk run` with `agent.kind: spacedock_solver_v2`, `runtime: codex`, and a
valid `summary.json`.

**AC-4 - Spider2-DBT uses the same generic materializer.**
Verified by: a Spider2-DBT Harbor-shaped task source is discovered or hydrated,
transformed through the same view layer, and smoke-run with the same
Spacedock/Codex solver path. If upstream data access blocks live execution, the
task records the exact blocker and includes a minimal local fixture proving the
same transform contract.

**AC-5 - Batched same-dataset specs are supported without losing task identity.**
Verified by: generated/frozen specs can include multiple ADE tasks and multiple
Spider2-DBT tasks in one Harbor job, with `n_concurrent_trials` configurable and
summary/per-trial artifacts retaining the original benchmark task id as the
scoring stratum.

**AC-6 - Freeze/resume is safe for batched and parallel jobs.**
Verified by: `spacedock_solver_v2` freeze state is keyed so simultaneous trials
do not collide, and a kill/resume smoke rerun of the same frozen spec skips or
reuses completed trials while incomplete trials can resume from their correct
task-scoped context.

**AC-7 - Shared-context batch mode is explicit and separate from per-task batch mode.**
Verified by: specs or generator options distinguish normal Harbor multi-task
batching from an experimental "same-dataset tasks inside one task/workspace"
mode, and tests prove the two modes produce different, auditable task layouts.

**AC-8 - No solution leakage or verifier-data exposure regressions.**
Verified by: materialized agent-visible views exclude known solution files and
tests inspect both ADE and Spider2-DBT transformed views for solution/test answer
paths before any live agent run.

## Test plan

Use TDD for the generic materializer first, then add ADE and Spider2-DBT
consumer tests. Acceptance commands should include focused unit tests, one ADE
smoke, one Spider2-DBT smoke or fixture-backed blocker report, one generated
multi-task frozen spec, and one kill/resume exercise against the smallest
batched job that can demonstrate non-colliding freeze state.

## Out of scope

This task does not require full-score ADE-Bench or Spider2-DBT runs. It creates
the reusable execution substrate and smoke-proves the benchmark sets are runnable
through it. Full matrix scoring remains in the score-run goal entities after
this substrate lands.

## Stage Report: plan

- DONE: The plan clearly separates the generic Harbor task view materializer from ADE-Bench and Spider2-DBT consumer transforms, with concrete files/modules and tests for each.
  Evidence: `docs/razorback-implementation/plans/pkg40-harbor-task-view-materializer.md` defines `src/razorback/harbor_tasks/*` for generic materialization and separate `ade_bench/harbor_view.py` plus `spider2_dbt/harbor_view.py` consumer tasks/tests.
- DONE: The plan includes a bounded spike section for uncertain Harbor/Spider2 surfaces and names the commands or local/web sources used or still required.
  Evidence: plan Task 1 names exact `uv run harbor`, `rg`, and `curl` commands, plus public Harbor docs/registry/Hugging Face Spider2 sources and fixture fallback criteria.
- DONE: The plan directly covers freeze/resume collision safety, parallelism, normal batching, shared-context batching, task identity in scoring, and solution/verifier-data leakage controls.
  Evidence: AC map and Tasks 6-10 cover `n_concurrent_trials`, per-task versus shared-context layouts, task-scoped freeze keys, kill/resume tests, scoring strata, and leakage scans.

### Summary

Wrote the standard separate plan doc at `docs/razorback-implementation/plans/pkg40-harbor-task-view-materializer.md`. The plan starts with Spider2/Harbor discovery, then proves the generic materializer before routing ADE and Spider2 through thin consumer transforms; batching, task identity, freeze/resume, and leakage controls are tested before live smokes.

### Follow-up Addendum

- DONE: Added operational hardening coverage requested before gate review.
  Evidence: `docs/razorback-implementation/plans/pkg40-harbor-task-view-materializer.md` now includes a dedicated addendum for shared image lifecycle, disk/storage cleanup, and Docker concurrency/resource guardrails.

## Gate Decision: plan

- AUTO-APPROVED: Move PKG-40 from plan to implementation under delegated
  first-officer gate authority; this was not a human-gated approval.
  Decision time: 2026-05-21T22:59:40Z.
- Conditions for implementation:
  - Start with the bounded Spider2-DBT and Harbor surface spike before editing the materializer.
  - Keep the generic Harbor task view materializer separate from ADE-Bench and Spider2-DBT consumer transforms.
  - Preserve task identity through batching, scoring, and freeze/resume.
  - Treat shared-context batching as an explicit experimental mode separate from normal Harbor multi-task batching.
  - Fail closed on solution/test-answer leakage and on unsupported Harbor prebuilt/shared-image semantics.
  - Record image tag/digest, Harbor version, cache/freeze storage impact, and infra-vs-model failure classification in acceptance evidence.

## Stage Report: implementation

- DONE: Generic Harbor task view materializer and ADE/Spider2 consumer transforms are implemented from the approved plan, after the required bounded spike.
  Evidence: commits `dbb58d7`, `fc0a8aa`, and `e5bb089`; generic code is under `src/razorback/harbor_tasks/`, with thin consumers in `src/razorback/benchmarks/ade_bench/harbor_view.py` and `src/razorback/benchmarks/spider2_dbt/harbor_view.py`.
- DONE: Tests and smokes cover batching/concurrency, task identity, leakage controls, and freeze/resume collision safety without relying on the retired local ADE adapter path.
  Evidence: `uv run --frozen pytest ...` reported `21 passed`, identity/freeze smokes reported `15 passed`, and generator tests reported `17 passed`; Harbor-shaped ADE/Spider2 fixtures use `TaskConfig(path=...)` task views.
- DONE: The implementation stage report records exact commands, commits, blockers, Harbor/image/cache evidence, and the ADE smoke/result artifact path or the concrete blocker preventing it.
  Evidence: this report names commands/commits; Spider2 live export is blocked by git checkout of `82d1fb0c144d28b1fd9852006cee0a39e74bd4a8`; fixture smoke specs are `examples/specs/pkg40-ade-harbor-task-view-codex.yaml` and `examples/specs/pkg40-spider2-dbt-harbor-task-view-codex.yaml`.

### Summary

Implemented a benchmark-neutral Harbor task view materializer that copies/link-ready task directories, patches Harbor TOML through Harbor's parser, records `view_manifest.json`, and fails closed on solution/answer paths. ADE-Bench and Spider2-DBT now route Harbor-shaped per-task specs through this generic layer; `concurrency.trials` maps to `JobConfig.n_concurrent_trials`, shared-context mode is explicit and currently fails closed before Harbor dispatch, scoring reads benchmark task identity from view manifests, and `spacedock_solver_v2` can key freeze dirs by task identity.

Commands run: `uv run python` Harbor model probe; `rg` installed Spider2 probe; `uv run harbor download spider2-dbt@1.0 --output-dir runs/pkg40-spider2-download --export --overwrite` (failed at git checkout); two Hugging Face `curl` probes; `uv run --frozen pytest tests/unit/test_harbor_task_view_materializer.py tests/unit/test_harbor_task_view_leakage.py -q`; `uv run --frozen pytest tests/unit/test_ade_bench_harbor_view.py tests/unit/test_spider2_dbt_harbor_view.py tests/unit/test_ade_bench_schema.py tests/unit/test_ade_bench_translator.py tests/unit/test_translate_harbor_task_batches.py -q`; `uv run --frozen pytest tests/unit/test_task_identity_scoring.py tests/integration/test_v2_freeze_dir_mechanism.py tests/unit/test_seal_v2_six_inputs.py tests/unit/test_spacedock_solver_v2_class.py -q`; `uv run --frozen pytest tests/integration/test_pkg40_harbor_task_views_smoke.py -q`; `uv run rk freeze examples/specs/pkg40-ade-harbor-task-view-codex.yaml --allow-missing`; `uv run rk freeze examples/specs/pkg40-spider2-dbt-harbor-task-view-codex.yaml --allow-missing`; final sweeps `21 passed`, `15 passed`, and `17 passed`.

Harbor/image/cache evidence: Harbor version `0.6.6`; manifests record authored `docker_image_tag` and `docker_image_digest: null` when no Docker digest is resolved; no Docker image was pulled or built by fixture smokes; task views are bounded under `<run-dir>/_razorback/task_views`; freeze roots are under `<run-dir>/_razorback/freeze/<sealed_hash>`. Infrastructure blockers are classified separately from model correctness: live Spider2 access failed before model execution due Harbor package git checkout; shared-context dispatch is an explicit pre-Harbor `SpecError` until a safe shared workspace layout is implemented.

## Stage Report: validation

- DONE: Validation report covers AC-1 through AC-8 with exact commands/output and classifies each PASS/FAIL/SKIPPED with evidence.
  Evidence: `docs/razorback-implementation/validation/pkg40-harbor-task-view-materializer.md` records AC-1 FAIL, AC-2 PASS, AC-3 FAIL, AC-4 PASS, AC-5 PASS, AC-6 PASS, AC-7 PASS, and AC-8 PASS with commands and outputs.
- DONE: Independent code review identifies no blocking material issue, or lists concrete implementation fixes for rejection.
  Evidence: validation found blocking AC-1 generator/schema/translator reachability for `ade_bench_root` plus `{slug: ...}` and missing AC-3 `rk run`/`summary.json` evidence, with concrete implementation fixes in the report.
- DONE: Stage report gives a gate recommendation and explicitly names the ADE smoke/result artifact path plus any Spider2 live-data blocker.
  Evidence: gate recommendation is REJECT; ADE run-ready artifact path is `runs/pkg40-validation/job-configs/ade-validation/_razorback/task_views/ade-bench-adebench-fixture-001`; Spider2 live export is blocked at `git checkout 82d1fb0c144d28b1fd9852006cee0a39e74bd4a8`.

### Summary

Validation reran the focused PKG-40 pytest suites, freeze commands, fixture materialization probes, multi-task batching probe, leakage scan, and Spider2 live export probe. The generic materializer, Spider2 fixture fallback, batching identity, freeze identity, shared-context fail-closed behavior, and leakage checks passed, but the gate is rejected because new ADE score-spec generation can still emit the retired local `ade_bench_root`/`slug` path and the required ADE `rk run` summary evidence is missing.

### Feedback Cycles

#### Cycle 1 - validation to implementation

Validation rejected PKG-40 back to implementation. Concrete fixes requested:

- AC-1: stop new Codex ADE score-spec generation from emitting `ade_bench_root`
  plus `tasks: [{slug: ...}]`; update or quarantine examples advertising that
  retired path.
- AC-1: make `AdeBenchLocalTaskEntry` / `ade_bench_root` unreachable for new
  score specs, or guard it as legacy-only so PKG-40 cannot silently use the
  local upstream adapter path.
- AC-3: produce the required ADE smoke evidence through the new generic Harbor
  task-view abstraction: a smallest `rk run` with `agent.kind:
  spacedock_solver_v2`, `runtime: codex`, and a valid `summary.json`, or a
  concrete accepted blocker for the missing Harbor-shaped ADE source.

## Stage Report: implementation (cycle 2)

- DONE: AC-1 generator/schema/translator/examples no longer expose the retired local ADE score-spec path for new score specs, with tests.
  Evidence: commit `13294c1` rejects upstream `tasks/*/task.yaml` roots in `examples/drivers/generate-codex-benchmark-specs.py`, removes `ade_bench_root` from `AdeBenchBenchmarkBlock`, guards direct legacy local entries in `src/razorback/translate.py`, and updates ADE examples to Harbor-shaped `tasks_root` plus string task ids.
- DONE: AC-3 has a real ADE `rk run` summary artifact through the generic task-view abstraction, or a precise blocker and fixture-backed evidence accepted by the entity AC.
  Evidence: `uv run rk run runs/pkg40-cycle2/pkg40-ade-harbor-task-view-codex-python.frozen.yaml --runs-dir runs/pkg40-cycle2/runs-python` completed with `1/1` trial, `0` exceptions, reward `1.0`; summary path: `runs/pkg40-cycle2/runs-python/pkg40-ade-harbor-task-view-codex/72b3dd571f3c865f/summary.json`.
- DONE: Entity implementation follow-up report records commits, commands, summary path/blocker, and regression status.
  Evidence: this cycle 2 report records fix commit `13294c1`, the ADE run command and summary path, and regression commands below; no new Spider2 blocker beyond the previously recorded Harbor checkout failure.

### Summary

Cycle 2 fixed only the validation blockers. New Codex ADE score generation now accepts only Harbor-shaped task roots with `*/task.toml`, emits `batch_mode: per-task`, and no longer emits `ade_bench_root` or `{slug: ...}` task entries; the schema rejects that retired shape for new score specs, while a translator guard prevents direct constructed legacy entries from silently routing through `materialize_local_task`.

The ADE smoke was rerun through the generic Harbor task-view abstraction with `spacedock_solver_v2`, `runtime: codex`, and a runnable `python:3.12` smoke image after the first attempt exposed a missing fixture `environment/Dockerfile` and placeholder-image pull failure. Commands run: AC-1 focused tests and validator-style generator probe; `uv run rk freeze examples/specs/pkg40-ade-harbor-task-view-codex.yaml --out runs/pkg40-cycle2/pkg40-ade-harbor-task-view-codex-python.frozen.yaml --allow-missing`; `uv run rk run runs/pkg40-cycle2/pkg40-ade-harbor-task-view-codex-python.frozen.yaml --runs-dir runs/pkg40-cycle2/runs-python`; regression sweeps `97 passed`, `15 passed`, and ADE glob `71 passed`; `git diff --check`.

## Stage Report: validation (cycle 2)

- DONE: Validation cycle 2 report re-checks AC-1 and AC-3 fixes with exact commands/output and confirms all AC-1..AC-8 statuses.
  Evidence: `docs/razorback-implementation/validation/pkg40-harbor-task-view-materializer.md` records AC-1 PASS, AC-2 PASS, AC-3 PASS, AC-4 PASS, AC-5 FAIL, AC-6 PASS, AC-7 PASS, and AC-8 PASS.
- DONE: Independent code review finds no blocking issue, or rejects with concrete implementation fixes.
  Evidence: validation rejects on `rk score` failing the completed ADE task-view run because `src/razorback/score/load.py` does not resolve strata from `_razorback/task_views/*/view_manifest.json`; the report names the concrete loader/sidecar fixes.
- DONE: Stage report gives a gate recommendation and names the ADE summary artifact and Spider2 blocker status.
  Evidence: gate recommendation is REJECT; ADE summary artifact is `runs/pkg40-cycle2/runs-python/pkg40-ade-harbor-task-view-codex/72b3dd571f3c865f/summary.json`; Spider2 live export remains blocked at Harbor `git checkout 82d1fb0c144d28b1fd9852006cee0a39e74bd4a8`.

### Summary

Cycle 2 validation confirms the prior AC-1 and AC-3 blockers are fixed: new ADE score specs reject the retired local upstream shape, and the ADE Codex smoke summary reports one completed trial with dataset `ade-bench`, query `adebench-fixture-001`, and reward `1.0` through the generic task-view manifest. The gate remains rejected because `uv run --frozen rk score runs/pkg40-cycle2/runs-python/pkg40-ade-harbor-task-view-codex/72b3dd571f3c865f --format json` exits with `score input error: trial ade-bench-adebench-fixture-001__NyS5nr6 has no stratum tag`, leaving PKG-40 task identity unavailable to the public scoring path.
