---
id: axtvw69xx1a3x41cw7npv4wa
title: PKG-35 — Codex reasoning effort config for benchmark specs
status: backlog
source: Captain directive 2026-05-21 — run gpt-5.5/xhigh/batch/spacedock
started:
completed:
verdict:
score: 0.86
worktree:
issue:
pr:
mod-block:
---

## Problem

Codex benchmark specs need to request `gpt-5.5` with `model_reasoning_effort=xhigh`
through the `spacedock_solver_v2` path. Harbor's Codex adapter already accepts the
kwarg, but Razorback's v2 agent schema and translator do not expose it from frozen
specs.

## Acceptance criteria

**AC-1 — `spacedock_solver_v2` specs can declare Codex reasoning effort.**
Verified by: a schema/translator test with `runtime: codex`, `model: gpt-5.5`, and
`reasoning_effort: xhigh` proves the generated Harbor agent kwargs include
`reasoning_effort: xhigh`.

**AC-2 — Generator output can request xhigh without hand-editing specs.**
Verified by: `examples/drivers/generate-codex-benchmark-specs.py` has a CLI flag for
reasoning effort and emits `reasoning_effort: xhigh` under the agent block when
requested.

**AC-3 — Existing Codex defaults remain compatible.**
Verified by: the existing v2 freeze/dispatch and generator tests still pass without
requiring a reasoning effort field.

## Test plan

Run focused unit/integration tests covering schema translation and generator output,
then run the existing Codex runtime dispatch test.

## Out of scope

OpenAI API Batch integration is not implemented here; this task only unblocks
Codex CLI/Harbor spec configuration.
