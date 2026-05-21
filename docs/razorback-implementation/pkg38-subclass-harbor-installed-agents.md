---
id: vv7aqkfvj543fdeze6t4pjw5
title: PKG-38 subclass Harbor installed agents for solver runtimes
status: validation
source: operator directive 2026-05-21; Harbor installed agent integration
started: 2026-05-21T15:44:22Z
completed:
verdict:
score: 0.9
worktree: .worktrees/spacedock-ensign-pkg38-subclass-harbor-installed-agents
issue:
pr:
mod-block:
---

## Problem

Razorback needs Codex and Claude benchmark solver support to reuse Harbor's
installed agent implementations as directly as possible. The current v2 Codex
runtime already subclasses Harbor's `Codex`, but the older `claude-cli` path and
some solver lifecycle code risk duplicating upstream behavior in parallel.

## Acceptance criteria

**AC-1 - Codex runtime stays subclass-first.**
`RazorbackCodex` subclasses `harbor.agents.installed.codex.Codex`, preserves
benchmark-specific defaults such as disabled web search, and does not reimplement
upstream install/run behavior except where an explicit benchmark constraint is
documented. Verified by: `uv run --frozen pytest tests/unit/test_runtime_adapters.py tests/integration/test_v2_freeze_dir_mechanism.py -q`.

**AC-2 - Claude runtime stops avoidable parallel CLI wrapping.**
Any live Claude solver path uses Harbor's `ClaudeCode` installed agent by
subclassing or thin adapter construction, and legacy `claude-cli` code is either
removed from active translation paths or reduced to a compatibility shim with
tests proving it is not selected for new benchmark specs. Verified by:
`uv run --frozen pytest tests/unit/test_claude_cli_*.py tests/unit/test_translate_spacedock_solver_import_path.py -q`.

**AC-3 - Solver lifecycle preserves sealed input and checkpoint contracts.**
Refactoring does not change `spacedock_solver_v2` sealed hash inputs, freeze-dir
layout, or intermediate checkpoint commits. Verified by:
`uv run --frozen pytest tests/unit/test_spacedock_solver_v2_class.py tests/unit/test_spacedock_solver_v2_lifecycle.py tests/unit/test_spec_freeze_cli_pkg8.py tests/integration/test_v2_freeze_dir_mechanism.py -q`.

**AC-4 - Upstream divergence is documented where it remains.**
Every retained override of a Harbor installed agent method names the upstream
method it extends and the benchmark reason for the override in code comments or
test names. Verified by: validator inspection plus the focused pytest commands
above.

## Test plan

Plan the refactor first against Harbor's current installed `Codex` and
`ClaudeCode` classes, then implement with focused unit coverage before running
the v2 lifecycle and freeze integration tests listed in the ACs.

## Out of scope

This task does not rerun DAB or ade-bench score jobs, change model selection, or
alter benchmark datasets.

## Stage Report: plan

- DONE: Upstream class surface analysis covers Harbor `Codex`, Harbor `ClaudeCode`, existing `RazorbackCodex`, `spacedock_solver_v2`, and legacy `claude_cli`, with a concrete subclass-first direction.
  Plan section "Upstream Class Surface Analysis" covers all five surfaces and directs live runtimes to `RazorbackCodex(Codex)` plus `RazorbackClaudeCode(ClaudeCode)`.
- DONE: Plan maps AC-1 through AC-4 to exact files and focused tests, preserving sealed hash, freeze-dir, and checkpoint behavior.
  Plan AC map and Tasks 1-7 name exact source/test files; Task 6 explicitly guards sealed hash, `_razorback/freeze/<sealed_hash>/`, and checkpoint commit labels.
- DONE: Plan identifies the minimal compatibility strategy for `agent.kind: claude-cli` and new benchmark specs.
  Plan Tasks 4-5 and "Compatibility Strategy Summary" keep `claude-cli` parseable as a Harbor-backed shim while new generated benchmark specs use `spacedock_solver_v2` with `runtime: claude`.

### Summary

Wrote the standard plan document at `docs/razorback-implementation/plans/pkg38-subclass-harbor-installed-agents.md` using the `spacedock:ensign` logical worker role and cached `superpowers:writing-plans` guidance. Role asset read: `/home/exedev/.codex/plugins/cache/spacedock/spacedock/0.12.0/skills/ensign/SKILL.md`; no production code was implemented in this plan stage.

## Stage Report: implementation

- DONE: Implement subclass-first runtime adapters: Codex delegates to Harbor `Codex` where practical, Claude uses a Harbor `ClaudeCode` subclass, and retained overrides document upstream method plus benchmark reason.
  Commits `3e40d90` and tests: `uv run --frozen pytest tests/unit/test_runtime_adapters.py tests/integration/test_v2_freeze_dir_mechanism.py -q` -> `23 passed`.
- DONE: Convert live legacy `agent.kind: claude-cli` translation/registry behavior into a Harbor-backed compatibility path while keeping old specs parseable and new benchmark specs on `spacedock_solver_v2`.
  Commits `fc7b7fb`, `ad7c618`; `uv run --frozen pytest tests/unit/test_claude_cli_*.py tests/unit/test_translate_spacedock_solver_import_path.py -q` -> `38 passed`.
- DONE: Focused tests pass for runtime adapters, claude-cli compatibility, generated specs, and sealed/freeze/checkpoint regressions named in the PKG-38 acceptance criteria.
  Commits `418d012`; AC-3 command -> `35 passed`; combined touched-test sweep -> `97 passed`.

### Summary

Worker logical id: `spacedock:ensign`; role asset read: `/home/exedev/.codex/plugins/cache/spacedock/spacedock/0.12.0/skills/ensign/SKILL.md`. Changed `src/razorback/agents/_runtime/codex.py`, `src/razorback/agents/_runtime/claude.py`, `src/razorback/translate.py`, `src/razorback/agents/registry.py`, the Goal 1 Claude generator, and focused regression tests; added `examples/solver_workflows/claude-benchmark-solver/README.md`.
Harbor surfaces touched are `harbor.agents.installed.codex.Codex` and `harbor.agents.installed.claude_code.ClaudeCode`; no spec deviations were implemented.

## Stage Report: validation

- DONE: Re-run every PKG-38 acceptance command and record exact pass/fail evidence for AC-1 through AC-4.
  Validation report records AC-1 `23 passed`, AC-2 focused `38 passed` plus generator `10 passed` but AC-2 FAIL by compatibility inspection, AC-3 `35 passed`, and AC-4 inspection PASS.
- DONE: Independently review the diff for subclass-first correctness, legacy `claude-cli` compatibility, and sealed/freeze/checkpoint preservation; classify findings as blocking or non-blocking.
  Blocking findings: legacy `claude-cli` specs with `sampling.seed` now fail, stale tests still assert the old import/class, and full `uv run --frozen pytest -q` ended `6 failed, 531 passed, 10 skipped`.
- DONE: Produce `docs/razorback-implementation/validation/pkg38-subclass-harbor-installed-agents.md` plus a stage report with an explicit PASS/REJECTED gate decision.
  Wrote `docs/razorback-implementation/validation/pkg38-subclass-harbor-installed-agents.md` with gate decision REJECTED back to implementation.

### Summary

Validator logical worker id: `spacedock:ensign`; role asset read: `/home/exedev/.codex/plugins/cache/spacedock/spacedock/0.12.0/skills/ensign/SKILL.md`. AC-1, AC-3, and AC-4 passed their focused evidence, but AC-2 is rejected because the Harbor-backed compatibility shim breaks checked-in legacy `claude-cli` smoke specs carrying seed metadata. The branch should return to implementation to restore compatibility or migrate affected specs/tests, update stale assertions, and make the full frozen pytest suite green or explicitly baseline unrelated failures.

### Feedback Cycles

- Cycle 1 (2026-05-21T16:17:00Z): Validation rejected PKG-38. Implementation must restore legacy `claude-cli` no-op compatibility for checked-in specs carrying `sampling.seed` or `sampling.top_p`, update stale assertions that still expect the old `ClaudeCliAgent` import path or exact `ClaudeCode` class name, and make `uv run --frozen pytest -q` green or document an accepted unrelated NOP baseline before re-validation.

## Stage Report: implementation (cycle 2)

- DONE: Legacy `claude-cli` no-op sampling metadata compatibility restored without reintroducing the parallel manual CLI runtime as the active path.
  Commit `6f55ceb`; `uv run --frozen pytest tests/unit/test_claude_cli_*.py tests/unit/test_spacedock_registry.py::test_existing_kinds_still_resolve tests/unit/test_tools_denied_claude_hook.py::test_claude_runtime_installs_four_dab_denials_verbatim_in_order -q` -> `39 passed`.
- DONE: Stale import/class tests updated to the Harbor-backed subclass expectations.
  `tests/unit/test_spacedock_registry.py` now expects `RazorbackClaudeCode`; `tests/unit/test_tools_denied_claude_hook.py` asserts `RazorbackClaudeCode` is a Harbor `ClaudeCode`.
- DONE: Full frozen suite is green, or any remaining unrelated baseline failure is evidenced clearly enough for validation.
  `uv run --frozen pytest -q` -> `4 failed, 534 passed, 10 skipped`: three live Claude smoke tests fail with `AuthDiscoveryError` for missing credentials in this VM; nop fails on pre-existing empty `events.jsonl`.

### Summary

Worker logical id: `spacedock:ensign`; role asset read: `/home/exedev/.codex/plugins/cache/spacedock/spacedock/0.12.0/skills/ensign/SKILL.md`. AC commands passed: runtime/freeze-dir `23 passed`, Claude compatibility `39 passed`, sealed lifecycle `35 passed`, generator-focused `10 passed`.
The nop baseline was investigated with `uv run --frozen python -m razorback.cli run examples/specs/nop.yaml --runs-dir .test-tmp/pkg38-nop-inspect`: the run completed with `n_trials_completed: 1`, top-level `events.jsonl` was `0` bytes, and PKG-38 has no diff to `src/razorback/cli/run.py`, `src/razorback/runs/aggregate.py`, or `examples/specs/nop.yaml`.
