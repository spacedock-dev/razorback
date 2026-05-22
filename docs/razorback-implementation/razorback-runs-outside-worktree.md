---
id: x9wz0wb8x4gm2wfqdn5c7de6
title: razorback runs_dir default outside the worktree
status: validation
source: goal1-resume-spacedock-first 2026-05-22 — FO `git worktree remove --force` destroyed `runs/goal1-resume/` with per-cell validation.json, reward_per_query.json, session jsonl traces, audit-aggregate. Per-query rescore against paper's metric now impossible without re-running.
started: 2026-05-22T23:11:16Z
completed:
verdict:
score: 0.95
worktree: .worktrees/spacedock-ensign-razorback-runs-outside-worktree
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

## Stage Report: plan

- DONE: Separate plan doc at docs/razorback-implementation/plans/razorback-runs-outside-worktree.md per the README's 4+-AC rule. Include an AC↔task map and spec §-cites where relevant.
  Plan written at `docs/razorback-implementation/plans/razorback-runs-outside-worktree.md` with an "AC ↔ Task map" table covering AC-1..AC-4 and per-task file/line cites into `src/razorback/cli/run.py:141`, `runs_dir_canary.py`, and `examples/drivers/dab-paper-matrix.sh:36`.
- DONE: Name the exact module/function for runs_dir default resolution (currently worktree-relative). Specify env-var ($RAZORBACK_RUNS_DIR) + XDG fallback ordering, and how --output-dir backward compat (AC-2) is preserved.
  New module `src/razorback/runs_dir_default.py` exposing `resolve_default_runs_dir() -> Path` with precedence `$RAZORBACK_RUNS_DIR` → `$XDG_DATA_HOME/razorback/runs` → `~/.local/share/razorback/runs`. T2 changes `cli/run.py:141` to `Optional[Path] = None` and resolves at entry; existing `--runs-dir` callers unaffected. AC-2 ambiguity flagged: razorback's `rk run` uses `--runs-dir`, the only `--output-dir` is the matrix-driver shell flag (`examples/drivers/dab-paper-matrix.sh:36`); plan interprets AC-2 as keeping both surfaces verbatim (T3 locks the driver shape).
- DONE: Spec the AC-1 unit test (path-resolution helper) and AC-4 worktree-teardown smoke test — name test file paths and the smallest end-to-end exercise that proves AC-4.
  AC-1 unit tests at `tests/unit/test_runs_dir_default.py` (6 cases incl. `test_default_not_under_cwd`). AC-4 integration smoke at `tests/integration/test_worktree_teardown_preserves_runs.py`: create throwaway worktree under `tmp_path`, run `rk run` from inside with `_invoke_harbor` mocked, `git worktree remove --force`, assert `spec.frozen.yaml` still readable at the `$RAZORBACK_RUNS_DIR`-rooted run-dir.

### Summary

Plan decomposes the entity into 6 TDD tasks (T0..T5) ordered riskiest-contract-first: resolver RED+GREEN before CLI wiring before mechanism-validation worktree smoke. The one substantive ambiguity in the spec (AC-2's "`--output-dir` backward compat" when `rk run` actually uses `--runs-dir`) is flagged at the top of the plan so the executing agent stops and asks if the interpretation is wrong before touching code. Each task lists exact file paths, complete test/code bodies, and the commit message; no placeholders.
