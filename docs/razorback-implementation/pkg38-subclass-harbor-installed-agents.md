---
id: vv7aqkfvj543fdeze6t4pjw5
title: PKG-38 subclass Harbor installed agents for solver runtimes
status: backlog
source: operator directive 2026-05-21; Harbor installed agent integration
started:
completed:
verdict:
score: 0.9
worktree:
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
