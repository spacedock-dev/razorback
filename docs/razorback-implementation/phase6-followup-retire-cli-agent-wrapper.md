---
id: yhb5ej5g3gnr71sbgr2cv5jz
title: Phase 6 follow-up — retire standalone CLI agent wrapper
status: done
source: phase6-promote-v2-canonical validation — deferred AC-4 standalone CLI sideline
started: 2026-05-23T05:27:15Z
completed: 2026-05-23T14:30:53Z
verdict: PASSED
score: 0.78
worktree: 
issue:
pr:
mod-block: 
---

## Problem

Phase 6 core solver retirement left `src/razorback/agents/claude_cli.py`
active because `src/razorback/agents/_runtime/claude.py` still imports
`ClaudeCliAgent` for telemetry and tool-policy behavior. Retiring the
standalone wrapper needs a predecessor extraction, not a crude file move.

## Acceptance criteria

**AC-1 — Runtime adapter no longer imports the standalone wrapper.**
`src/razorback/agents/_runtime/claude.py` uses Harbor's installed
Claude agent or a v2-named local helper that is not the legacy
`ClaudeCliAgent`.
Verified by: `rg -n "ClaudeCliAgent|agents.claude_cli" src/razorback/agents/_runtime src/razorback/translate.py` returns no active hits.

**AC-2 — Standalone wrapper is legacy-only.**
`src/razorback/agents/claude_cli.py` is moved to `_legacy/agents/`
or deleted after active behavior is preserved elsewhere.
Verified by: `test -e src/razorback/agents/claude_cli.py` exits non-zero and focused runtime adapter tests pass.

**AC-3 — Tool policy and cost/audit behavior survive.**
The Claude runtime adapter still enforces proxy/tool restrictions and
emits the data required by score/audit surfaces.
Verified by: `uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_tools_denied_claude_hook.py -q`.

## Notes

Filed by first officer after auto-approved Phase 6 local merge. This
was a validation-approved follow-up, not human-gated.

## Inline Implementation Plan

# Retire Standalone Claude CLI Wrapper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` for this tiny follow-up. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the active `src/razorback/agents/claude_cli.py` wrapper while preserving the Claude runtime adapter's tool policy, auth/proxy handling, and cost/audit telemetry.

**Architecture:** Promote the wrapper behavior that is still needed by `runtime: claude` into a v2-named helper on `src/razorback/agents/_runtime/claude.py`, most likely `RazorbackClaudeCode(ClaudeCode)`, and have `build_inner_agent()` construct that helper directly. Then move the historical standalone wrapper to `src/razorback/_legacy/agents/claude_cli.py` or delete it after all active imports and tests are retargeted.

**Tech Stack:** Python, Harbor installed `ClaudeCode`, pydantic spec/translation, pytest, `rg` verification.

---

Spec cites: v2 spec §1.3 and §4.1 (Razorback ships one custom Harbor agent, `SpacedockSolverAgent`), §4.3 and §8.4 (per-runtime adapters construct Harbor installed agents), §4.5 and §8.1 (import-path dispatch through translated `JobConfig`), §6.2 and §9.4 (tools-denied runtime leak layer), §7 and §8.3a (run-dir score/cost/audit surfaces).

### Behavior to Preserve

Current `ClaudeCliAgent` supplies these active behaviors that must survive without an active `_runtime/claude.py` import from `razorback.agents.claude_cli`:

- It subclasses Harbor's `ClaudeCode`, so Harbor's stream-json execution, CLI flag descriptors, token/cost parsing, and `populate_context_post_run()` behavior remain the base contract.
- It rejects co-mingled `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN`, declares those names as auth alternates, and temporarily stamps `extra_env` into `os.environ` while delegating `run()` because Harbor reads Claude auth from process env.
- It maps Razorback `tools_allowed` to Harbor `allowed_tools`, applies `DEFAULT_ALLOWED_TOOLS` when empty, and always applies the Razorback/DAB `DISALLOWED_TOOLS` list unless the caller passes a wider `tools_denied` list.
- It compensates for Harbor's unquoted CLI flag rendering by shell-quoting the disallowed-tools CSV, which matters for patterns like `Bash(curl *)` and `Bash(pip install datasets*)`.
- It validates `claude --version` inside the trial environment, materializes `_exec_env` as `PROXY_BLOCK_ENV + extra_env` for the legacy test surface, preserves `supported_sampling() == {"temperature"}`, and keeps `_sampling_temperature` as metadata.
- It delegates post-run context population to Harbor and then publishes the `claude-output.jsonl` audit sentinel from Harbor's `claude-code.txt` log, which keeps `rk score`, `rk runs cost`, and `rk audit` surfaces populated.

### Task 1: Lock the Runtime Helper Contract First (AC-1, AC-3)

**Files:**
- Modify: `tests/unit/test_runtime_adapters.py`
- Modify: `tests/unit/test_tools_denied_claude_hook.py`
- Modify: `tests/unit/test_claude_cli_kwarg_mapping.py`
- Modify: `tests/unit/test_claude_cli_setup_env_scrub.py`
- Modify: `tests/unit/test_claude_cli_version.py`
- Modify: `tests/unit/test_claude_cli_required_env.py`
- Modify: `tests/unit/test_claude_cli_supported_sampling.py`
- Modify: `tests/unit/test_ade_bench_missing_tool_graceful_error.py`

- [ ] Replace direct test imports of `razorback.agents.claude_cli.ClaudeCliAgent` with `razorback.agents._runtime.claude.RazorbackClaudeCode` and, if needed, `RazorbackClaudeCodeError`.
- [ ] In `tests/unit/test_runtime_adapters.py`, change `test_claude_constructs_inner_agent_as_claude_cli_subclass` to assert `isinstance(inner, claude_adapter.RazorbackClaudeCode)` and `isinstance(inner, ClaudeCode)`, with no import from `razorback.agents.claude_cli`.
- [ ] Add a focused import-path test for the already-translated legacy route: `importlib.import_module("razorback.agents._runtime.claude")` and `getattr(module, "RazorbackClaudeCode")`, because `translate.py` already emits `razorback.agents._runtime.claude:RazorbackClaudeCode`.
- [ ] Add or retarget a post-run telemetry test: create `tmp_path / "claude-code.txt"`, monkeypatch `ClaudeCode.populate_context_post_run` to a no-op/spy, call `RazorbackClaudeCode(...).populate_context_post_run(context)`, and assert `claude-output.jsonl` exists as a symlink or copied file. This locks the audit sentinel before moving the old wrapper.
- [ ] Run the focused tests before implementation and confirm failure for missing `RazorbackClaudeCode` or stale `ClaudeCliAgent` imports:
  `uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_tools_denied_claude_hook.py tests/unit/test_claude_cli_kwarg_mapping.py tests/unit/test_claude_cli_setup_env_scrub.py tests/unit/test_claude_cli_version.py tests/unit/test_claude_cli_required_env.py tests/unit/test_claude_cli_supported_sampling.py tests/unit/test_ade_bench_missing_tool_graceful_error.py -q`

Expected red state: tests fail because `_runtime/claude.py` has no active `RazorbackClaudeCode` class and still constructs `ClaudeCliAgent`.

### Task 2: Move Needed Behavior Into `_runtime/claude.py` (AC-1, AC-3)

**Files:**
- Modify: `src/razorback/agents/_runtime/claude.py`
- Read-only dependencies: `src/razorback/agents/claude_invoke.py`, `src/razorback/agents/proxy.py`, `src/razorback/agents/auth.py`

- [ ] Add `RazorbackClaudeCodeError(RazorbackError)` in `_runtime/claude.py`.
- [ ] Add `class RazorbackClaudeCode(ClaudeCode)` in `_runtime/claude.py` with the preserved constructor surface: `logs_dir`, `model_name`, `logger`, `mcp_servers`, `skills_dir`, `tools_allowed`, `sampling_temperature`, `extra_env`, and `**kwargs`.
- [ ] Import `DEFAULT_ALLOWED_TOOLS`, `DISALLOWED_TOOLS`, and `PROXY_BLOCK_ENV` directly in `_runtime/claude.py`; do not import `razorback.agents.claude_cli`.
- [ ] In the constructor, reject both Claude auth env names together, set `_tools_allowed`, `_sampling_temperature`, default `allowed_tools`, default quoted `disallowed_tools`, call `super().__init__(..., extra_env=env, **kwargs)`, and mirror `_razorback_extra_env` plus `_exec_env`.
- [ ] Preserve `name() -> "claude-cli"`, `required_env()` alternation, and `supported_sampling() -> {"temperature"}` for legacy translation/tests while keeping the helper v2-owned by path and class name.
- [ ] Preserve `run()` env stamping around `super().run(...)`.
- [ ] Preserve `setup()`'s container-side `claude --version` validation and `_exec_env = {**PROXY_BLOCK_ENV, **extra_env}` behavior unless the implementation deliberately delegates to Harbor's `ClaudeCode.setup()`; if it delegates, update tests to prove proxy/auth behavior still survives.
- [ ] Preserve `populate_context_post_run()` by calling `super()` then publishing `claude-output.jsonl` from `claude-code.txt`, falling back from symlink to copy.
- [ ] Update `build_inner_agent()` to return `RazorbackClaudeCode` and update docstrings/comments to describe a v2 runtime helper rather than the legacy standalone wrapper.
- [ ] Run:
  `uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_tools_denied_claude_hook.py -q`

Commit: `phase6: preserve claude runtime behavior in runtime adapter`

### Task 3: Retarget Legacy Tests and Remove Active Wrapper Imports (AC-1, AC-2)

**Files:**
- Modify: tests listed in Task 1
- Modify only if a stale comment/import remains: `src/razorback/agents/spacedock_solver.py`

- [ ] Retarget all unit tests that still import `ClaudeCliAgent` to `RazorbackClaudeCode`; keep filenames if that avoids unnecessary churn, but update test names/comments away from the active standalone wrapper.
- [ ] Update `tests/unit/test_tools_denied_claude_hook.py` comments to say the inner agent is `RazorbackClaudeCode`, a Harbor `ClaudeCode` subclass, and still installs the default `DISALLOWED_TOOLS`.
- [ ] Update `tests/unit/test_runtime_adapters.py` so it imports no symbol from `razorback.agents.claude_cli` and still checks Harbor descriptor shapes, `tools_allowed`, `tools_denied`, unsupported kwargs, and `extra_env`.
- [ ] Run the broader wrapper-behavior suite:
  `uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_tools_denied_claude_hook.py tests/unit/test_claude_cli_kwarg_mapping.py tests/unit/test_claude_cli_setup_env_scrub.py tests/unit/test_claude_cli_version.py tests/unit/test_claude_cli_required_env.py tests/unit/test_claude_cli_supported_sampling.py tests/unit/test_ade_bench_missing_tool_graceful_error.py tests/unit/test_claude_cli_compat_shim.py tests/unit/test_claude_cli_translator_proxy.py -q`
- [ ] Run:
  `rg -n "ClaudeCliAgent|agents\\.claude_cli" src/razorback/agents/_runtime src/razorback/translate.py`
  Expected: no output, exit 1.

Commit: `phase6: retarget claude wrapper tests to runtime helper`

### Task 4: Sideline or Delete `src/razorback/agents/claude_cli.py` (AC-2)

**Files:**
- Move or delete: `src/razorback/agents/claude_cli.py`
- If moving: create/use `src/razorback/_legacy/agents/claude_cli.py`

- [ ] Prefer `git mv src/razorback/agents/claude_cli.py src/razorback/_legacy/agents/claude_cli.py` as a pure sideline commit so historical references remain inspectable. Delete instead only if the implementation finds no value in legacy retention and all behavior has already been copied to `_runtime/claude.py`.
- [ ] Do not leave any active `_runtime/claude.py` or `translate.py` import from `_legacy`; `_legacy` is for archaeology only.
- [ ] Run:
  `test ! -e src/razorback/agents/claude_cli.py`
- [ ] Run:
  `rg -n "from razorback\\.agents\\.claude_cli|import razorback\\.agents\\.claude_cli|agents\\.claude_cli" src/razorback tests`
  Expected: only allowed historical fixture/archive hits, with no active runtime/translate/test imports. If active tests still hit, retarget them before committing the move.
- [ ] Run the required AC-3 command:
  `uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_tools_denied_claude_hook.py -q`

Commit: `sideline: standalone claude cli agent wrapper`

### Task 5: Final Validation and Coordination Check (AC-1, AC-2, AC-3)

**Files:** no production changes unless validation exposes a bug.

- [ ] Exact AC-1 grep:
  `rg -n "ClaudeCliAgent|agents\\.claude_cli" src/razorback/agents/_runtime src/razorback/translate.py`
  Expected: no output, exit 1.
- [ ] Exact AC-2 file check:
  `test ! -e src/razorback/agents/claude_cli.py`
- [ ] Exact AC-3 focused tests:
  `uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_tools_denied_claude_hook.py -q`
- [ ] Compatibility/proxy/auth regression tests:
  `uv run pytest tests/unit/test_claude_cli_compat_shim.py tests/unit/test_claude_cli_translator_proxy.py tests/unit/test_claude_cli_setup_env_scrub.py tests/unit/test_claude_cli_kwarg_mapping.py tests/unit/test_claude_cli_version.py tests/unit/test_claude_cli_required_env.py tests/unit/test_claude_cli_supported_sampling.py tests/unit/test_ade_bench_missing_tool_graceful_error.py -q`
- [ ] Runtime import-path smoke:
  `uv run python - <<'PY'
import importlib
module = importlib.import_module("razorback.agents._runtime.claude")
cls = getattr(module, "RazorbackClaudeCode")
print(cls.__name__)
PY`
  Expected output: `RazorbackClaudeCode`.
- [ ] Optional comprehensive confidence run if the worktree is otherwise clean:
  `uv run pytest`

Coordination risks:

- Harbor's installed `ClaudeCode` constructor, `CLI_FLAGS`, `ENV_VARS`, `build_cli_flags()`, `setup()`, and `populate_context_post_run()` are upstream-owned and can change. Keep the current descriptor-shape test in `tests/unit/test_runtime_adapters.py`; do not copy Harbor install command literals into Razorback.
- The old wrapper shell-quotes `disallowed_tools` because Harbor renders CLI flag values unquoted. Re-check generated flags when changing the helper, especially patterns with parentheses or `*`.
- If Harbor starts publishing `claude-output.jsonl` directly or changes `claude-code.txt`, update the sentinel logic and audit tests together; `rk audit` currently discovers `claude-output.jsonl`.
- Direct legacy `agent.kind: claude-cli` specs currently translate to `razorback.agents._runtime.claude:RazorbackClaudeCode`. This follow-up should keep that import path loadable or explicitly remove the legacy route in a separate, captain-approved task; do not silently break existing compatibility tests while retiring the standalone file.

## Stage Report: plan

- DONE: if the plan identifies the behavior currently supplied by `ClaudeCliAgent` and how to preserve it without active `_runtime/claude.py` imports from `agents.claude_cli`.
  The "Behavior to Preserve" section inventories auth alternation, env stamping, tool policy, proxy setup, sampling metadata, version capture, and telemetry/audit sentinel behavior; Tasks 2-3 move it to `_runtime/claude.RazorbackClaudeCode`.
- DONE: if the plan gives TDD checkpoints for moving/deleting `src/razorback/agents/claude_cli.py` while preserving tool policy, proxy/auth handling, telemetry/cost behavior, and runtime adapter tests.
  Tasks 1-4 write/retarget failing tests first, preserve the helper behavior, retarget tests, then sideline/delete `src/razorback/agents/claude_cli.py` only after the AC greps and focused tests pass.
- DONE: if the plan states exact validation commands and any coordination risk with Harbor installed agents.
  Task 5 lists the exact `rg`, `test ! -e`, focused pytest, compatibility pytest, import-path smoke, and optional full-suite commands, plus Harbor `ClaudeCode` churn risks.

### Summary

Inline plan written on the entity per the first-officer tiny/small scope call; no separate `plans/phase6-followup-retire-cli-agent-wrapper.md` document was created. I read the packaged `spacedock:ensign` role and the cached `superpowers:writing-plans` skill guidance, inspected the Phase 6 validation report, current runtime adapter, wrapper, translation path, and focused tests, and did not edit production code.

## Stage Report: implementation

- DONE: Claude runtime adapter preserves auth, proxy/tool policy, sampling, setup, and telemetry behavior without importing `razorback.agents.claude_cli`.
  `c9343b6` adds `_runtime/claude.RazorbackClaudeCode` with auth alternation/env stamping, proxy setup, tool flags, sampling metadata, version validation, and `claude-output.jsonl` sentinel publication.
- DONE: `src/razorback/agents/claude_cli.py` is sidelined to `_legacy` or removed, with active tests retargeted to the runtime helper.
  `34251d2` moves the wrapper to `src/razorback/_legacy/agents/claude_cli.py`, retargets active tests/comments, and leaves no active `_runtime` or translator import from the old path.
- DONE: Required runtime adapter and tool-denial validation commands pass, or any remaining blocker is isolated with exact command output and next fix.
  `uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_tools_denied_claude_hook.py -q` passed `18 passed`; compatibility/auth/proxy suite passed `26 passed`; import smoke printed `RazorbackClaudeCode`.

### Summary

Implemented the v2-owned Claude runtime helper in `src/razorback/agents/_runtime/claude.py` and kept Harbor `ClaudeCode` surfaces for CLI flags, env descriptors, setup/version behavior, and post-run cost/audit population. The standalone wrapper is retained only under `_legacy`; `translate.py` continues to route legacy `agent.kind: claude-cli` specs to `razorback.agents._runtime.claude:RazorbackClaudeCode`. No deviations from the approved inline plan.

## Stage Report: validation

- DONE: AC-1 and AC-2 are independently verified with exact command results and rationale for any remaining allowed wrapper hits.
  AC-1 `rg -n "ClaudeCliAgent|agents\\.claude_cli" src/razorback/agents/_runtime src/razorback/translate.py` exited 1 with no output; AC-2 `test -e src/razorback/agents/claude_cli.py` exited 1 and `test ! -e src/razorback/agents/claude_cli.py` exited 0; remaining broad hits are schema/fixture/_legacy archive references, not active wrapper imports.
- DONE: AC-3 focused runtime adapter/tool-denial command is rerun and its actual result is recorded.
  `uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_tools_denied_claude_hook.py -q` passed `18 passed in 0.23s`; compatibility/proxy/auth suite passed `26 passed in 0.53s`; full `uv run pytest` passed `576 passed, 12 skipped`.
- DONE: Code review findings are classified as blocking or non-blocking, with a clear PASS/REJECTED gate recommendation.
  Applied the cached `superpowers:requesting-code-review` checklist manually to `8611e34..0123bea`; blocking findings: none; non-blocking findings: none; gate recommendation: PASSED.

### Summary

Validation independently reproduced AC-1, AC-2, AC-3, the inline-plan compatibility/proxy/auth regression bundle, runtime import-path smoke, and the full pytest suite from the assigned worktree branch. The standalone wrapper is absent from the active path and retained only under `_legacy`; approve this entity to `done` with gate recommendation PASSED.
