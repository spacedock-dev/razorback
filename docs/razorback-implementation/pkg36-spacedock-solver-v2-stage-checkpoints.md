---
id: q9d227mm32r3k6mjhmx6rh9r
title: PKG-36 — Spacedock solver v2 intermediate checkpoints
status: backlog
source: Captain directive 2026-05-21 — checkpoint all intermediate stages
started:
completed:
verdict:
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
