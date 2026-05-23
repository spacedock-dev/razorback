---
id: sf587hvtrjs0mm448new17ty
title: Keep active workflow examples aligned with current rk commands
status: backlog
source: 2026-05-23 staff audit - active workflow examples reference removed CLI and import surfaces
started:
completed:
verdict:
score: 0.78
worktree:
issue:
pr:
mod-block:
---

## Problem

Some active workflow examples still point agents at removed surfaces such as
`rk spec freeze`, `rk validate`, and `razorback.runtime.reconcile`. These are
not harmless docs when agents use examples as operational prompts; stale
commands waste benchmark runs and can produce misleading smoke failures.

## Acceptance criteria

**AC-1 - Active examples use current CLI commands.**
Examples under `examples/workflows/` reference the current `rk freeze`,
`rk run`, `rk score`, and `rk audit` surfaces, or are clearly marked legacy and
excluded from operational examples.
Verified by: grep checks find no active references to `rk spec`, `rk validate`,
or `razorback.runtime.reconcile`.

**AC-2 - The DAB workflow example is runnable or retired.**
`examples/workflows/dab-claude/` is either updated to the current architecture
or moved to a legacy location with a note explaining its status.
Verified by: the chosen active example path has a smoke command that exits 0.

**AC-3 - Example rot is tested cheaply.**
A lightweight test or lint check catches removed CLI subcommands and import
surfaces in active workflow examples.
Verified by: adding one stale command to a fixture fails the check.
