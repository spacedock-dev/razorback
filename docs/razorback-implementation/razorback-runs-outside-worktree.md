---
id: x9wz0wb8x4gm2wfqdn5c7de6
title: razorback runs_dir default outside the worktree
status: backlog
source: goal1-resume-spacedock-first 2026-05-22 — FO `git worktree remove --force` destroyed `runs/goal1-resume/` with per-cell validation.json, reward_per_query.json, session jsonl traces, audit-aggregate. Per-query rescore against paper's metric now impossible without re-running.
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

Razorback's experiment outputs (the project's actual deliverable)
live under worktree-relative gitignored paths: `runs/`, `_runs/`,
`.runs/`. When the FO runs `git worktree remove --force` at entity
terminal cleanup, those paths get deleted along with the worktree
filesystem.

goal1-resume-spacedock-first shipped on 2026-05-22 with verdict
PASSED; the merge + force-remove sequence destroyed:

- `runs/goal1-resume/{spacedock}/{12 datasets}/.../validation.json`
  (per-query pass/fail map — would have let us rescore using
  paper's `per_query_pass_at_1` metric instead of razorback's
  binary `rk score`)
- `runs/goal1-resume/.../reward_per_query.json` (verify_batch.py's
  own per-query map)
- Session jsonl traces (the basis for the $94.77 reconstructed
  cost — now unverifiable)
- `runs/goal1-resume/audit-aggregate.json`
- All freeze trees at `<run-dir>/_razorback/freeze/<sealed_hash>/`
  that spacedock_solver_v2 wrote for halt/resume

The root cause is razorback's default — `runs_dir` defaults to a
worktree-relative path. The same FO + razorback combination
destroys outputs every time an entity ships.

## Acceptance criteria

**AC-1 — Default `runs_dir` is OUTSIDE the worktree.**
When no `--output-dir` is supplied, razorback writes to
`$XDG_DATA_HOME/razorback/runs/` (default
`~/.local/share/razorback/runs/`) or honors `$RAZORBACK_RUNS_DIR`
when set. The path is absolute, NOT worktree-relative.
Verified by: a unit test asserts the resolved default path is
not a sub-path of `Path.cwd()` or the active git worktree.

**AC-2 — Backward compat for `--output-dir`.**
Explicit `--output-dir runs/foo/` still works as today (relative
to cwd). Existing experiment specs that hardcode
worktree-relative paths still run.
Verified by: existing integration tests stay green.

**AC-3 — Migration documented.**
The repo README + razorback CLI help mention the new default
location. The harbor-DAB plugin's docs reference the same.
Verified by: README has a short "Where do runs go?" section.

**AC-4 — Worktree teardown can no longer destroy runs.**
A smoke test creates a worktree, runs a cell, removes the
worktree, then asserts the run artifacts are still readable
from the user-data location.
Verified by: an integration test exercises this sequence.

## Test plan

- **Unit:** path-resolution helper test (AC-1).
- **Integration:** worktree-create → cell-run → worktree-remove
  → artifacts-still-readable smoke (AC-4).
- **Acceptance:** running the existing goal1-resume specs against
  the new default produces a runs tree at the user-data location.

## Out of scope

- Migrating existing experiment specs to the new default. They
  can opt in over time.
- Run-dir cleanup / retention policies — that's a future entity.
- Cross-worktree run discovery / indexing — see
  `freeze-tree-content-addressable-store` for the freeze case.

## Depends on

- None. Independent infra change.

## Resume hook

After this entity merges, the next razorback experiment dispatch
writes artifacts to a path that survives worktree teardown.
Goal 1's matrix re-run becomes safe.
