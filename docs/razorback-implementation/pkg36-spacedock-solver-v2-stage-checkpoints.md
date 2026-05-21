---
id: q9d227mm32r3k6mjhmx6rh9r
title: PKG-36 — Spacedock solver v2 intermediate checkpoints
status: done
source: Captain directive 2026-05-21 — checkpoint all intermediate stages
started: 2026-05-21T15:10:33Z
completed: 2026-05-21T15:18:05Z
verdict: PASSED
score: 0.84
worktree: 
issue:
pr:
mod-block:
---

## Problem

The v2 Spacedock solver initializes a freeze git repo and has a `_commit_stage`
helper, but `run()` only commits the seed state. Full benchmark runs need named
intermediate checkpoints so interrupted Codex/Spacedock attempts can be inspected
and resumed with useful provenance.

## Acceptance criteria

**AC-1 — v2 solver writes named intermediate freeze commits.**
Verified by: a focused test runs the v2 solver with a stub inner agent and observes
git commits for setup, pre-agent, and post-agent stage checkpoints in the freeze repo.

**AC-2 — Checkpointing is no-op safe when freeze setup is unavailable.**
Verified by: an existing or new test covers a run path without an initialized freeze
repo and confirms solver execution still completes.

**AC-3 — Checkpoint stage names are stable and documented in code/tests.**
Verified by: tests assert exact stage labels and the implementation centralizes the
labels rather than scattering string literals.

## Test plan

Run the new v2 checkpoint tests plus the existing `spacedock_solver_v2` and freeze
mechanism integration tests.

## Out of scope

Splitting one Codex invocation into multiple independent solver prompts is deferred;
this task records checkpoints around the current v2 execution boundaries.

## Stage Report: implementation

- DONE: A focused v2 lifecycle test observes exact checkpoint commit messages for setup/ready, run/before-agent, and run/after-agent.
  Evidence: `test_setup_and_run_write_named_checkpoint_commits` asserts `stage: setup/ready`, `stage: run/before-agent`, and `stage: run/after-agent`.
- DONE: A no-freeze or uninitialized path remains executable without turning a test-only stub into a hard failure.
  Evidence: `test_run_sends_solver_workflow_readme_before_task_instruction` asserts direct `run()` delegation does not call `environment.exec`.
- DONE: Existing v2 lifecycle/freeze tests still pass with the new checkpoint calls.
  Evidence: `uv run pytest tests/unit/test_spacedock_solver_v2_lifecycle.py tests/unit/test_spacedock_solver_v2_class.py` -> 18 passed; `uv run pytest tests/integration/test_spacedock_git_freeze.py tests/integration/test_v2_freeze_dir_mechanism.py` -> 10 passed.

### Summary

Implemented centralized checkpoint labels in `src/razorback/agents/spacedock_solver_v2.py` and added setup/run checkpoint commits around the existing freeze repo lifecycle and inner-agent delegation. Touched the Harbor-facing `setup()` and `run()` lifecycle surfaces only; no schema, translate, freeze, or generator files were edited. The only deviation from always checkpointing is the documented test/non-freeze direct `run()` path, where checkpointing remains a no-op until `setup()` has initialized or restored freeze git.
