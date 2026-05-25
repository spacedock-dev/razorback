---
id: js6maenxqbn2c2wf78wad3r4
title: Execution lock contract for runtime, image, and plugin provenance
status: backlog
source: 2026-05-25 full ADE gpt-5.4-mini audit - frozen provenance recorded dab-agent while run used ADE task images and mutable Codex install; captain directive for a unified contract covering Claude Code, Codex, Spacedock, images, and harness realization
started:
completed:
verdict:
score: 0.97
auto-approve: false
worktree:
issue:
pr:
mod-block:
---

## Problem

Razorback's current freeze/run provenance contract is fragmented. The full
ADE-Bench `gpt-5.4-mini` run surfaced the concrete failure: the frozen spec
recorded `image_digest` for local `dab-agent:latest`, while Harbor actually
built and ran generated ADE task images from `python:3.11-slim`. Codex was not
baked into those task images; Harbor installed `@openai/codex@latest` at trial
setup time. Spacedock provenance recorded a placeholder skill version rather
than the actual staged plugin identity.

That means the score can be reproduced from local run artifacts, but the
provenance does not truthfully describe the execution substrate. Future scored
runs need a single execution-lock contract that distinguishes:

- frozen intent: what razorback intended to run;
- observed realization: what Harbor actually built, installed, staged, and
  executed;
- enforcement: whether `rk run`, `rk score`, and `rk audit` refuse or mark
  non-canonical when observed realization differs from the lock.

This must cover benchmark task images, DAB compose images, Claude Code, Codex,
Spacedock plugin/skills, solver workflow content, Harbor/Razorback versions,
and benchmark task-view identity without inventing separate ad hoc contracts
per runtime.

## Acceptance criteria

**AC-1 - Unified execution-lock schema exists.**
Frozen specs and run artifacts expose one documented `execution_lock` shape
covering `benchmark_image`, `agent_runtime`, `orchestration`, `harness`, and
`policy` sections. The schema explicitly models both frozen intent and observed
realization without overloading legacy `provenance.image_digest` or
`agent_cli_hash`.
Verified by: schema/model tests parse a frozen spec containing the full lock
and reject unknown lock fields.

**AC-2 - Benchmark image locking matches the actual run path.**
ADE/Spider task-view runs lock Dockerfile/build-context identity and record the
actual built task-image digest per task. DAB/generic Harbor compose runs lock
the compose image refs actually used by services such as `main`, postgres, and
mongo. No benchmark may fall back to an unrelated default image for provenance.
Verified by: a fixture ADE run no longer records `dab-agent` when task views
are built from `python:3.11-slim`; a DAB fixture records the digest-pinned
`main` service image.

**AC-3 - Agent CLI/runtime locking is explicit and enforceable.**
Claude Code and Codex runtimes record install mode (`prebaked`, `npm`, or
`binary`), package/ref, resolved version, binary hash, and install-plan hash.
Runtime installs may not use mutable `latest` unless the run is explicitly
marked non-canonical or allowed by a named development policy.
Verified by: tests fail a frozen scored run that would install
`@openai/codex@latest` or `@anthropic-ai/claude-code@latest`, and pass a run
with a pinned package version or prebaked binary hash.

**AC-4 - Spacedock and solver workflow identity are locked as first-class inputs.**
The lock records the staged Spacedock plugin manifest version, plugin content
hash, first-officer skill hash, ensign skill hash, agent asset hashes, and
solver workflow hash. Placeholder values such as `spacedock_skill_version:
1.0.0` are not sufficient for canonical scored runs.
Verified by: changing a staged Spacedock skill or solver workflow causes
`rk run` to detect lock drift before agent execution unless an explicit
`--allow-...-drift` option is used.

**AC-5 - `rk run` enforces lock/observed consistency and writes realization artifacts.**
`rk run` writes an `observed_execution.yaml` (or equivalently named artifact)
after image build, agent install/setup, plugin staging, and Harbor dispatch. It
compares observed values to the frozen lock and refuses canonical runs on
mismatch. Existing drift flags remain narrow and explicit.
Verified by: integration fixtures cover both a matching run and a deliberate
image/runtime/plugin mismatch; the mismatch exits with a documented
provenance/drift error before scoring.

**AC-6 - `rk score` and `rk audit` surface canonicality.**
Score and audit outputs include a canonicality status derived from the
execution lock. A run with reproducible local artifacts but mismatched or
missing execution-lock evidence is reported as non-canonical instead of cleanly
publishable.
Verified by: a fixture modeled after the ADE `gpt-5.4-mini` run reports the
numeric score but also reports non-canonical provenance because the frozen
image/agent/plugin lock does not match observed execution.

## Test plan

- Start with a failing fixture that mirrors the discovered ADE run shape:
  frozen `image_digest` points at `dab-agent`, task views are generated from
  `python:3.11-slim`, Codex is runtime-installed with `@latest`, and Spacedock
  identity is placeholder-only.
- Add schema/model tests for the unified lock shape before changing run logic.
- Add lock builders per benchmark/runtime, then wire `rk freeze` to emit only
  values it can honestly enforce or observe at run time.
- Add `rk run` observed-realization fixtures for ADE task images, DAB compose,
  Codex, Claude Code, and Spacedock plugin staging.
- Add `rk score` / `rk audit` fixture coverage for canonical and
  non-canonical outputs.

## Out of scope

- Re-scoring the existing ADE `gpt-5.4-mini` run. This task defines future
  provenance and canonicality behavior; historical runs can be reclassified but
  not made canonical retroactively.
- Choosing whether Claude/Codex should be prebaked or installed at setup time.
  This contract supports both, as long as the choice is pinned and enforced.
- Renaming or rebuilding the DAB agent image. Existing image-specific backlog
  items own that work.
- Retiring legacy provenance fields immediately. Compatibility shims may remain
  as long as the new lock is the canonical source for new scored runs.

## Depends on

- Coordinate with `hm` generic Harbor surface work before implementation so the
  lock schema lands on the post-HM benchmark abstraction rather than the
  soon-to-be-reworked ADE/DAB-specific paths.
- Related but not blocked by:
  - `canonical-sealed-hash-runtime-freeze-key`
  - `pkg24-vendor-dab-agent-dockerfile`
  - `ade-bench-task-image-claude-cli-layer`
  - `dab-agent-image-duckdb-extension-preinstall`

## Resume hook

When this lands, future scored runs can answer "what exact image, agent CLI,
Spacedock plugin, solver workflow, and harness did this score use?" from a
single lock/observed-realization pair, and `rk score` / `rk audit` can separate
"locally reproducible" from "canonical publishable."
