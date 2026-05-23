---
id: njy7knzwtg7bwjrhcfxchxat
title: Direct Codex minimal agent kind
status: validation
source: Captain directive 2026-05-23 — solver variant separation
started: 2026-05-23T21:43:32Z
completed:
verdict:
score: 0.93
worktree: .worktrees/spacedock-ensign-direct-codex-minimal-agent-kind
issue:
pr:
mod-block: 
---

## Problem

Codex "minimum / no Spacedock" runs currently have no first-class spec path.
The practical path uses `agent.kind: spacedock_solver` with `runtime: codex`,
which adds solver-workflow prompting and freeze/checkpoint behavior. That makes
minimum Codex results ambiguous and blocks clean comparisons across minimal,
structured, and Spacedock-workflow variants.

## Acceptance criteria

**AC-1 — Specs can request direct Codex without `solver_workflow`.**
Verified by: schema/parse tests accept `agent.kind: codex` with model and Codex
runtime options, and reject any `solver_workflow`-only fields on that direct
agent block.

**AC-2 — Translation routes direct Codex to the Razorback Codex adapter.**
Verified by: translator tests show `agent.kind: codex` emits
`AgentConfig.import_path == "razorback.agents._runtime.codex:RazorbackCodex"`,
resolves Codex auth, applies the proxy-block task env, and does not require
`agent.sealed_hash`.

**AC-3 — Direct Codex preserves supported Codex controls and fails closed.**
Verified by: tests cover `reasoning_effort`/`reasoning_summary` pass-through
when supported by Harbor Codex, unsupported direct-agent kwargs are rejected by
schema or adapter construction, and existing `spacedock_solver` Codex tests
continue to pass.

**AC-4 — Minimal Codex examples and docs are unambiguous.**
Verified by: at least one Codex smoke/example or generator path can emit
`agent.kind: codex` for a minimum run, and `docs/agent-run-architecture.md`
describes the desired-state variant split plus the current remaining gaps.

## Notes

This task owns `docs/agent-run-architecture.md` updates for the variant split.
Do not implement first-officer dispatch here; that belongs to
`spacedock-workflow-invokes-first-officer`.

## Stage Report: implementation

- DONE: `agent.kind: codex` parses and translates directly to `RazorbackCodex` without `solver_workflow` or `sealed_hash`, with focused schema/translator tests.
  Evidence: commit 874e96e adds `CodexAgentBlock`, direct registry/translator routing, `tests/unit/test_spec_schema_codex.py`, and `tests/unit/test_translate_codex_direct.py`; focused suite passed 76/76.
- DONE: supported Codex controls such as reasoning effort are preserved or fail closed in the direct path, without regressing existing `spacedock_solver` Codex behavior.
  Evidence: `reasoning_effort`/`reasoning_summary` pass through direct `AgentConfig.kwargs`; unsupported solver/tool/sampling fields reject; existing runtime adapter and spacedock translator tests passed in the 76-test focused suite.
- DONE: minimal Codex examples/docs are unambiguous, including an update to `docs/agent-run-architecture.md` for desired state and remaining gaps.
  Evidence: commit 874e96e updates Codex smoke specs and `generate-codex-benchmark-specs.py` to emit direct `agent.kind: codex`, and updates `docs/agent-run-architecture.md` variant guidance.

### Summary

Implemented a first-class direct Codex schema/registry/translator path that routes to `razorback.agents._runtime.codex:RazorbackCodex` with Codex auth and proxy-block environment handling, without solver workflow or sealed-hash requirements. Updated Codex examples, generator tests, and architecture docs; true first-officer dispatch remains intentionally out of scope for the parallel workflow task.

## Stage Report: implementation (cycle 2)

- DONE: Merge current `main` into the direct Codex worktree branch and preserve direct Codex ownership.
  Evidence: merged `main` after root update `049cb34`/`ab5b5d8`; resolved the only content conflict in `examples/drivers/generate-dab-paper-matrix-specs.py` by keeping both optional `dataset_ref` and main's `reasoning_effort` support.
- DONE: Preserve architecture desired-state/gaps while not taking over Claude-side real FO dispatch.
  Evidence: `docs/agent-run-architecture.md` still documents direct `agent.kind: codex`, structured+freeze, and true first-officer dispatch as a remaining gap; Goal 1 generated examples remain Claude/spacedock cells from main.
- DONE: Re-run focused validation after the main merge.
  Evidence: `uv run --frozen pytest ... test_dab_paper_matrix_spec_generator.py -q` passed 79/79.

### Summary

Post-merge resolution kept the direct Codex minimal implementation intact and incorporated main's Goal 1 reasoning-effort generator changes without converting Claude-side Goal 1 specs to Codex. No true first-officer dispatch implementation was added.

## Stage Report: validation

- DONE: AC-1 and AC-2 are independently verified: `agent.kind: codex` parses/translates directly to `RazorbackCodex`, requires no `solver_workflow` or `sealed_hash`, resolves Codex auth, and applies proxy-block environment behavior as intended.
  Evidence: `uv run --frozen pytest tests/unit/test_spec_schema_codex.py tests/unit/test_translate_codex_direct.py tests/unit/test_spacedock_registry.py tests/unit/test_spec_freeze_cli_pkg8.py tests/unit/test_codex_benchmark_spec_generator.py tests/unit/test_runtime_adapters.py tests/unit/test_translate_spacedock_solver_import_path.py tests/unit/test_dab_paper_matrix_spec_generator.py -q` -> `98 passed in 1.66s`; `uv run --frozen rk freeze examples/specs/codex-dab-smoke.yaml --allow-missing --out .validation-tmp/codex-dab-smoke.frozen.yaml` -> wrote frozen spec whose `agent.kind` is `codex` and lacks `solver_workflow`, `solver_workflow_content_hash`, and `sealed_hash`.
- DONE: AC-3 is independently verified: Codex controls pass through or fail closed, and existing `spacedock_solver` Codex/structured+freeze behavior is not regressed.
  Evidence: the same 98-test suite covers `reasoning_effort`/`reasoning_summary` pass-through, schema rejection of unsupported direct-agent fields/sampling, runtime adapter kwargs, spacedock translator import path, and freeze sealed-hash regression; `uv run --frozen pytest tests/unit/test_docker_environment_proxy_separation.py tests/unit/test_translate_codex_direct.py -q` -> `5 passed, 6 warnings in 0.24s`.
- DONE: AC-4 is independently verified: examples/generator/docs make minimal Codex unambiguous and do not conflict with the Claude-side real FO dispatch plan now on main.
  Evidence: examples/specs use `agent.kind: codex`, generator tests in the 98-test suite pass, `docs/agent-run-architecture.md` says true first-officer dispatch is not implemented here, `git diff --check main...HEAD -- ':!uv.lock'` -> no output/exit 0, and `git diff --name-only HEAD...main -- ':!uv.lock'` -> only `docs/razorback-implementation/direct-codex-minimal-agent-kind.md`.

### Summary

PASS. Blocking findings: none. Non-blocking finding: `uv run --frozen pytest tests/unit/test_claude_cli_translator_proxy.py tests/unit/test_translate_codex_direct.py -q` failed `5 failed, 2 passed` because the unchanged Claude proxy test fixture still uses retired `benchmark.kind: dab`; this is outside the direct Codex diff and was not counted against the gate. Gate decision: approve-to-done.
