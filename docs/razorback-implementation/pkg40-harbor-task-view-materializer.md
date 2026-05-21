---
id: dy0w211g9dp8w80jyje1rgz9
title: PKG-40 Harbor task view materializer for ADE-Bench and Spider2-DBT
status: backlog
source: captain request 2026-05-21 - Harbor-shaped ADE plus Spider2-DBT shared-image, batching, freeze/resume path
started:
completed:
verdict:
score: 0.95
worktree:
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
