---
id: axtvw69xx1a3x41cw7npv4wa
title: PKG-35 — Codex reasoning effort config for benchmark specs
status: done
source: Captain directive 2026-05-21 — run gpt-5.5/xhigh/batch/spacedock
started: 2026-05-21T15:10:33Z
completed: 2026-05-21T15:18:05Z
verdict: PASSED
score: 0.86
worktree: 
issue:
pr:
mod-block:
archived: 2026-05-21T15:18:16Z
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

## Stage Report: implementation

- DONE: A schema/translator test proves `runtime: codex`, `model: gpt-5.5`, and `reasoning_effort: xhigh` produce `harbor_agent_kwargs["reasoning_effort"] == "xhigh"`.
  `uv run pytest tests/integration/test_v2_freeze_dir_mechanism.py::test_translator_includes_codex_reasoning_kwargs_for_v2_agent ...` passed; the test also covers optional `reasoning_summary`.
- DONE: The spec freezer and runtime translation use the same optional Codex kwargs when computing/passing the v2 sealed hash.
  Added shared `build_v2_harbor_agent_kwargs`; `uv run pytest tests/unit/test_spec_freeze_cli_pkg8.py::test_freeze_includes_codex_reasoning_kwargs_in_v2_sealed_hash ...` passed.
- DONE: The Codex benchmark spec generator can emit `reasoning_effort: xhigh` via CLI while preserving old default behavior.
  Generator tests passed for default omission, direct emission, and `--reasoning-effort xhigh` CLI output.

### Summary

Added optional v2 agent schema fields `reasoning_effort` and `reasoning_summary`, and routed them through the shared Harbor `harbor_agent_kwargs` builder used by both translation and freeze sealed-hash stamping. Updated `examples/drivers/generate-codex-benchmark-specs.py` with `--reasoning-effort` while keeping default output backward compatible. No deviations from the approved plan; Harbor surface touched is only the v2 `harbor_agent_kwargs` contract passed to `SpacedockSolverAgent`.

Focused tests:

`uv run pytest tests/integration/test_v2_freeze_dir_mechanism.py::test_translator_includes_codex_reasoning_kwargs_for_v2_agent tests/unit/test_spec_freeze_cli_pkg8.py::test_freeze_includes_codex_reasoning_kwargs_in_v2_sealed_hash tests/unit/test_codex_benchmark_spec_generator.py::test_emit_dab_codex_spec_uses_solver_v2_codex_and_harbor_dab tests/unit/test_codex_benchmark_spec_generator.py::test_emit_dab_codex_spec_allows_reasoning_effort tests/unit/test_codex_benchmark_spec_generator.py::test_cli_can_emit_reasoning_effort_when_requested` -> 5 passed.

`uv run pytest tests/unit/test_codex_benchmark_spec_generator.py tests/unit/test_spec_freeze_cli_pkg8.py tests/unit/test_spec_schema_spacedock_solver_v2.py tests/integration/test_v2_freeze_dir_mechanism.py` -> 29 passed.
