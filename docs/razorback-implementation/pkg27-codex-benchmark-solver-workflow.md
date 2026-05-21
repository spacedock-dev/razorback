---
id: 0h4p8jt0bj7yejbjxbhwtjbq
title: PKG-27 — reusable Codex benchmark solver workflow and specs
status: implementation
source: Captain directive 2026-05-21 — "get 1x score for full dataset of DAB and ade-bench, using codex"
started: 2026-05-21T07:56:58Z
completed:
verdict:
score: 0.9
worktree: .worktrees/spacedock-ensign-pkg27-codex-benchmark-solver-workflow
issue:
pr:
mod-block:
---

## Problem

PKG-26 makes `runtime: codex` executable, but the full benchmark
runs need a tracked solver workflow and repeatable Codex-shaped spec
templates. The existing examples are Claude-oriented (`claude-cli`)
or minimal smoke workflows; they are not enough to produce full DAB
and ade-bench Codex score numbers.

This task adds the reusable benchmark solver workflow and generator
surface that Goal 3 and Goal 4 consume.

## Acceptance criteria

**AC-1 — Codex solver workflow exists.**
A solver workflow directory under `examples/solver_workflows/`
contains a `README.md` suitable for one benchmark trial. It instructs
the agent to inspect task files, query only the provided local data
services/files, write the expected answer artifact, and avoid
external data acquisition.
Verified by: the workflow directory exists and
`uv run rk freeze` can content-hash it through
`solver_workflow_content_hash`.

**AC-2 — DAB Codex spec generation exists.**
A generator or static specs can emit all DAB full-dataset Codex
cells using `agent.kind: spacedock_solver_v2`, `runtime: codex`,
the Codex solver workflow, `benchmark.kind: harbor_dab`, and the
operator's local DAB data root.
Verified by: dry-run output lists all 12 DAB datasets with N=1 and
the configured data root.

**AC-3 — ade-bench Codex spec generation exists.**
A generator or static specs can emit all ade-bench Codex cells using
`agent.kind: spacedock_solver_v2`, `runtime: codex`, the Codex solver
workflow, `benchmark.kind: ade-bench`, local-task entries, and the
operator's local ade-bench checkout.
Verified by: dry-run output lists every discovered task under the
configured `ade_bench_root/tasks/` with N=1.

**AC-4 — Smoke specs freeze and run before matrix burn.**
One DAB smoke spec and one ade-bench smoke spec freeze successfully.
The DAB smoke runs end to end; the ade-bench smoke either runs end to
end or fails only on an already-filed ade-bench infrastructure
blocker, not on Codex spec construction.
Verified by: committed stage report names the exact commands and
run-dir paths.

## Depends on

- `pkg26-codex-spacedock-solver-runtime`
- `pkg23-harbor-shaped-compose-for-ade-bench` for full ade-bench
  runtime success; this task may still ship specs before the live
  ade-bench run unblocks.

## Stage Report: implementation

- DONE: Adds a reusable Codex benchmark solver workflow and DAB/ade-bench Codex spec generation surfaces with portable data-root arguments.
  Added `examples/solver_workflows/codex-benchmark-solver/README.md`, `examples/drivers/generate-codex-benchmark-specs.py`, and smoke specs `examples/specs/codex-{dab,ade-bench}-smoke.yaml`; roots are caller arguments or placeholder paths.
- DONE: Dry-run or tests prove DAB enumerates 12 datasets and ade-bench enumerates discovered local-task slugs at N=1.
  `uv run pytest tests/unit/test_codex_benchmark_spec_generator.py` passed 4/4; dry-runs listed 12 DAB datasets and 3 discovered fixture ade-bench tasks at N=1.
- DONE: Stage report records smoke/freeze attempts and exact blockers for live Codex or ade-bench execution, without running full score matrices.
  `uv run rk freeze examples/specs/codex-dab-smoke.yaml --allow-missing` and `uv run rk freeze examples/specs/codex-ade-bench-smoke.yaml --allow-missing` wrote frozen specs with solver workflow hash `sha256:803a512c01f0f9ce346933ea3860efd1cd7a70e73e4c4b6fe215a84c4a9f69ff`; `rk run` attempts to `/tmp/razorback-pkg27-{dab,ade}-smoke` failed before Harbor with `AuthDiscoveryError: no codex credentials found. Add OPENAI_API_KEY to <worktree>/.env.`

### Summary

Implemented the reusable Codex benchmark solver workflow and a portable generator for DAB `harbor_dab` and ade-bench local-task `spacedock_solver_v2` Codex specs. Harbor-facing surfaces touched are example specs and driver emission only; no translator, scorer, or Harbor runtime code changed. Full live score matrices were intentionally not run; smoke execution is blocked on missing Codex credentials in the worktree `.env`.
