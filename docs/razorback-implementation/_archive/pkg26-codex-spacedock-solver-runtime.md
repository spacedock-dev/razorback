---
id: 0ammh1a5fgj9wncpe79w7syw
title: PKG-26 — Codex runtime adapter for spacedock_solver_v2
status: done
source: Captain directive 2026-05-21 — "get 1x score for full dataset of DAB and ade-bench, using codex"
started: 2026-05-21T07:35:11Z
completed: 2026-05-21T07:55:50Z
verdict: PASSED
score: 0.95
worktree: 
issue:
pr:
mod-block:
archived: 2026-05-21T07:55:59Z
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

## Stage Report: implementation

- DONE: Codex adapter constructs Harbor's Codex installed agent for `spacedock_solver_v2` without silently dropping model or tool-restriction kwargs.
  Commit `baf4b17` adds `src/razorback/agents/_runtime/codex.py` construction of Harbor `Codex(model_name=..., extra_env=...)`, forwards supported Codex descriptor kwargs, and raises `SpacedockSolverAgentError` for active unsupported controls.
- DONE: Unit/integration tests cover the Codex-positive path, unsupported-kwarg fail-closed behavior, and Claude no-regression behavior.
  `uv run pytest tests/unit/test_runtime_adapters.py tests/integration/test_v2_freeze_dir_mechanism.py -q` passed `14 passed`; `uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_spacedock_solver_v2_class.py -q` passed `14 passed`.
- DONE: Stage report records exact verification commands, including a Codex smoke run if available or a concrete environment blocker if live Codex execution cannot run in this worktree.
  Smoke commands: `uv run rk freeze examples/specs/_codex-smoke-v2.yaml` exited 11 on unresolved `model_resolved_version`; `uv run rk freeze examples/specs/_codex-smoke-v2.yaml --allow-missing` exited 0; `uv run rk run examples/specs/_codex-smoke-v2.frozen.yaml --runs-dir runs/pkg26-codex-smoke --allow-plugin-drift --allow-alias-drift` stopped with `AuthDiscoveryError` because this worktree has no `.env` `OPENAI_API_KEY`.

### Summary

Implemented the Codex runtime adapter, Codex `.env` auth resolution, v2 Codex translation, and v2 freeze stamping needed for the checked-in `examples/specs/_codex-smoke-v2.yaml` smoke path. Harbor surfaces touched were the installed `Codex` constructor/descriptor kwargs, `AgentConfig.env` credential wiring, and freeze-time provenance/sealed-hash materialization. Verification also passed `uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_claude_cli_auth_dotenv_only.py tests/unit/test_spec_freeze_cli_pkg8.py tests/integration/test_v2_freeze_dir_mechanism.py -q` (`29 passed`) and `uv run --frozen ruff check ...` (`All checks passed`); the only live-smoke deviation is the environment blocker above.

### Additional verification

After completion, `uv run pytest` was run across the full suite. Result: `492 passed, 10 skipped, 4 failed`; three failures were live Claude smoke/budget paths blocked by missing `ANTHROPIC_API_KEY`/`CLAUDE_CODE_OAUTH_TOKEN` in this worktree, and one pre-existing nop integration assertion observed an empty `events.jsonl`. The Codex-focused tests still passed in that run.

## Stage Report: validation

- DONE: Validation report independently verifies AC-1, AC-2, and AC-4 with exact test commands and reviews the code for silent Codex kwarg drops.
  Report: `docs/razorback-implementation/validation/pkg26-codex-spacedock-solver-runtime.md`; AC-1 `14 passed`, AC-4 `14 passed`, broader verifier `29 passed`; no silent active kwarg drops found.
- DONE: Validation report independently attempts AC-3 Codex smoke or records the exact auth/environment blocker after confirming freeze succeeds.
  `uv run rk freeze examples/specs/_codex-smoke-v2.yaml --allow-missing` wrote frozen/provenance files; `uv run rk run ...` failed with `AuthDiscoveryError: no codex credentials found. Add OPENAI_API_KEY to .../.env.`
- DONE: Validation report gives a clear PASS/REJECT gate decision with blocking findings separated from non-blocking findings.
  Gate decision: APPROVE to `done`; blocking findings: none; non-blocking findings: dirty pre-existing `uv.lock`, normal freeze requires `--allow-missing` due unresolved model version.

### Summary

Fresh validation reran `uv run pytest`, the task's targeted AC commands, and the Codex smoke freeze/run path from the assigned worktree. AC-1, AC-2, and AC-4 pass; AC-3 is blocked only by missing local Codex credentials after `--allow-missing` freeze succeeds, so the recommended gate is APPROVE to `done`.
