---
id: njy7knzwtg7bwjrhcfxchxat
title: Direct Codex minimal agent kind
status: implementation
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
