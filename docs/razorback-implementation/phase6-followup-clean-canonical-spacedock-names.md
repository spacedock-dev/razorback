---
id: nxaw93fjsj46tkrezjf4r7dx
title: Phase 6 follow-up — clean internal Spacedock v2 names
status: implementation
source: phase6-promote-v2-canonical validation — non-blocking canonical naming cleanup
started: 2026-05-23T05:32:13Z
completed:
verdict:
score: 0.58
worktree: .worktrees/spacedock-ensign-phase6-followup-clean-canonical-spacedock-names
issue:
pr:
mod-block:
---

## Problem

Phase 6 promoted the external solver surface to canonical
`spacedock_solver`, but validation still found internal `V2` symbol and
test-name remnants. They are not behavior blockers, but they make the
canonical surface harder for agents to understand.

## Acceptance criteria

**AC-1 — Active code uses canonical Spacedock solver names.**
Internal classes, constants, helper names, and active test filenames avoid
`V2` unless the code is explicitly testing historical rejection.
Verified by: `rg -n "V2|v2|spacedock_solver_v2" src/razorback tests examples --glob '!**/_legacy/**'` returns only intentional historical assertions.

**AC-2 — Behavior is unchanged.**
Canonical route, freeze, runtime adapter, and example-generator tests pass.
Verified by: `uv run pytest tests/unit/test_spec_schema_spacedock_solver.py tests/unit/test_translate_spacedock_solver_import_path.py tests/unit/test_spacedock_solver_class.py tests/unit/test_spacedock_solver_lifecycle.py tests/unit/test_runtime_adapters.py -q`.

**AC-3 — Docs distinguish history from active API.**
Any remaining historical references live in archive docs or validation notes,
not active examples or agent-readable README/AGENTS surfaces.
Verified by: validation report includes grep output and rationale for each remaining hit.

## Stage Report: plan

- DONE: Inventory active `V2` / `v2` / `spacedock_solver_v2` hits and classify cleanup targets versus intentional historical assertions.
  Evidence: plan inventory classifies schema/helper/test/example/README/backlog-doc cleanup targets and marks stale-discriminator tests plus archive/validation/debrief/evidence docs as historical.
- DONE: Plan canonical rename steps with TDD or focused validation that proves behavior is unchanged.
  Evidence: plan Tasks 1-6 map ACs to schema/helper/agent/example/doc rename steps, RED grep/import checkpoints, and focused pytest checkpoints.
- DONE: State exact validation commands and the rationale required for any remaining historical/documentation hits.
  Evidence: plan Task 6 gives exact AC grep, pytest, and docs grep commands; inventory section states the allowed historical-hit rationale.

### Summary

Wrote a separate implementation plan at `docs/razorback-implementation/plans/phase6-followup-clean-canonical-spacedock-names.md` because the inventory crosses multiple active subsystems despite only three ACs. The plan keeps this stage doc-only, reserves production edits for implementation, and requires validation to report every remaining historical hit explicitly.
