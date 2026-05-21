---
id: 0ammh1a5fgj9wncpe79w7syw
title: PKG-26 — Codex runtime adapter for spacedock_solver_v2
status: backlog
source: Captain directive 2026-05-21 — "get 1x score for full dataset of DAB and ade-bench, using codex"
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

Razorback's v2 agent schema already accepts
`agent.kind: spacedock_solver_v2` with `runtime: codex`, but the
runtime adapter is still a deliberate `NotImplementedError` stub in
`src/razorback/agents/_runtime/codex.py`. DAB and ade-bench Codex
score runs cannot start until `SpacedockSolverAgent` can construct
and run Harbor's Codex installed agent.

This task implements the Codex runtime adapter while preserving the
existing Claude runtime behavior and the sealed-input contract.

## Acceptance criteria

**AC-1 — `runtime: codex` constructs a Harbor Codex inner agent.**
`SpacedockSolverAgent._build_inner_agent()` dispatches
`runtime="codex"` to a functional adapter that instantiates Harbor's
Codex installed agent with the configured model and supported runtime
kwargs. It no longer raises `NotImplementedError`.
Verified by: `uv run pytest tests/unit/test_runtime_adapters.py
tests/integration/test_v2_freeze_dir_mechanism.py -q` includes a
Codex-positive assertion.

**AC-2 — Codex kwargs map defensibly.**
`max_turns`, `tools_allowed`, `tools_denied`, and
`append_system_prompt` are either mapped to Harbor Codex constructor
kwargs when supported, or rejected with an explicit
`SpacedockSolverAgentError` that names the unsupported kwarg. The
adapter must not silently drop tool restrictions.
Verified by: unit tests cover one accepted Codex config and one
unsupported-kwarg rejection path.

**AC-3 — Codex smoke run exits through `rk run`.**
A small frozen spec using `spacedock_solver_v2`, `runtime: codex`,
and `examples/solver_workflows/_smoke/` runs against the in-tree
hello-world task and writes the normal run-dir artifacts.
Verified by: `uv run rk freeze <codex-smoke-spec>` followed by
`uv run rk run <codex-smoke-spec.frozen.yaml> --runs-dir
runs/pkg26-codex-smoke/ --allow-plugin-drift --allow-alias-drift`
exits 0 and the resulting run-dir contains `result.json`,
`manifest.json`, `summary.json`, and a Codex trace sentinel
(`codex-output.jsonl` or Harbor's Codex-equivalent trace file).

**AC-4 — Claude runtime remains green.**
The existing Claude adapter tests continue to pass unchanged.
Verified by: `uv run pytest tests/unit/test_runtime_adapters.py
tests/unit/test_spacedock_solver_v2_class.py -q` passes.

## Plan

Standard implementation task. Inspect Harbor's installed Codex agent
class and tests first, then implement the smallest adapter that
constructs that class without weakening the sealed-input or
tool-denial contracts. If Harbor's Codex installed agent lacks a
feature required by AC-2, fail closed with a clear error and file a
follow-up instead of pretending the restriction landed.

## Depends on

- `phase3-spacedock-solver-v2` — shipped; provides the v2 class and
  runtime dispatch seam.

