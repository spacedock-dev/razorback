---
id: f1g6189n5zq8pdg0j4ebvzpv
title: freeze tree content-addressable store for halt/resume independence
status: validation
source: spacedock_solver_v2's freeze design + goal1-resume-spacedock-first 2026-05-22 — sealed-hash freeze trees lived under the gitignored worktree-relative runs/ path and were destroyed by worktree teardown. The halt/resume design CANNOT actually halt/resume in this regime.
started: 2026-05-22T23:55:01Z
completed:
verdict:
score: 0.95
worktree: .worktrees/spacedock-ensign-freeze-tree-content-addressable-store
issue:
pr:
mod-block: merge:pr-merge
---

## Problem

`spacedock_solver_v2` materializes freeze trees at
`<run-dir>/_razorback/freeze/<sealed_hash>/` (see
`src/razorback/agents/spacedock_solver_v2.py` lines 166-170).
The `<sealed_hash>` is computed from the spec — it is content-
addressable by design. Any future razorback invocation could
discover and reuse an existing freeze tree by sealed-hash
lookup, enabling:

- Skip the expensive agent invocations (~$5/cell) on re-run
- Re-score against the saved answers using updated validators
  or new metrics (e.g., paper's per-query pass@1 vs razorback's
  binary)
- Audit the trajectories
- Reproduce cost numbers exactly

**But the freeze trees ARE worktree-relative.** The `<run-dir>`
defaults to a worktree-local path (the same issue
`razorback-runs-outside-worktree` is fixing for run artifacts).
When the worktree is removed at entity terminal cleanup, the
freeze trees go with it. The universal sealed_hash key becomes
useless because the data behind the key is gone.

The halt/resume design is the project's flagship "we don't have
to redo everything" feature. As wired today it fails the basic
scenario of "FO shipped the entity; we want to re-score under a
new metric without re-running the agent."

The fix is to move freeze trees to a content-addressable store
(CAS) at a location independent of any single worktree:

- `~/.local/share/razorback/freeze/<sealed_hash>/` (XDG-style)
- or `$RAZORBACK_FREEZE_DIR/<sealed_hash>/` (env-overridable)

With CAS, both razorback and harbor get the same lookup. Any
worktree can discover any prior freeze.

## Acceptance criteria

**AC-1 — Freeze trees materialize at the CAS path.**
`spacedock_solver_v2._freeze_dir` returns
`$XDG_DATA_HOME/razorback/freeze/<sealed_hash>/` (default
`~/.local/share/razorback/freeze/`) when
`$RAZORBACK_FREEZE_DIR` is unset, OR the env-overridden path
when set.
Verified by: a unit test asserts the resolved freeze_dir is
not a sub-path of the active worktree.

**AC-2 — Discovery by sealed_hash works cross-worktree.**
A freeze tree written in worktree A is discoverable from
worktree B (or after worktree A is removed) by computing the
sealed_hash from the spec.
Verified by: integration test creates worktree A, runs a
spacedock cell to produce a freeze, removes worktree A,
creates worktree B, runs the same spec, and asserts the agent
DOESN'T re-invoke claude (it resumes from the freeze).

**AC-3 — Halt/resume tests stay green.**
`tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py`
plus the in-tree spacedock_solver_v2 lifecycle tests stay
GREEN under the new path.
Verified by: explicit test run documented in validation
report.

**AC-4 — Migration helper.**
A `razorback freeze migrate` CLI subcommand walks the old
worktree-relative paths (if any survive) and moves them into
the CAS. Idempotent.
Verified by: a unit test runs the migration against a
fixture freeze tree at the old path.

**AC-5 — Goal 1 re-score from CAS without re-running.**
After this entity + `razorback-runs-outside-worktree` +
`commit-small-artifacts-by-default` ship: running goal1-resume
a SECOND time picks up the freeze trees from the first run
and re-scores under paper's `per_query_pass_at_1` metric
without invoking claude. The dollar cost of the second run
is ~$0 (only verifier + score, no agent inference).
Verified by: live re-score test produces a per-query pass@1
report without any agent invocation, with cost_usd reported
as the cached cost from the first run.

## Test plan

- **Unit:** path resolution + sealed_hash key derivation.
- **Integration:** cross-worktree discovery (AC-2) + halt/resume
  regression (AC-3) + migration helper (AC-4).
- **Acceptance:** goal1-resume re-score from CAS (AC-5).

## Out of scope

- Freeze tree garbage collection / retention. Future entity.
- Multi-machine CAS (e.g., shared NFS mount, S3-backed). Future
  if collaboration emerges.
- Generalizing CAS to non-freeze artifacts (e.g., result.json,
  cost ledgers). Stays separate.

## Depends on

- `razorback-runs-outside-worktree` — provides the precedent
  user-data path structure; this entity adopts the same
  XDG-default + env-override pattern
- spacedock_solver_v2 (shipped) — the freeze surface this entity
  relocates

## Resume hook

After this entity merges, halt/resume becomes worktree-
independent. Goal 1's matrix re-run can reuse freeze trees
from this session's failed attempts, dropping the cost from
$95 to ~$0 (only verifier + score on saved answers).

## Stage Report: plan

- DONE: Separate plan doc at docs/razorback-implementation/plans/freeze-tree-content-addressable-store.md with AC↔task map. Re-baseline assumptions: jp (commit-small-artifacts) was SUPERSEDED (see _archive/), so AC-5's 'after this entity + razorback-runs-outside-worktree + commit-small-artifacts-by-default ship' clause becomes 'after this entity + x9 ship' — note this in the plan.
  Plan at `docs/razorback-implementation/plans/freeze-tree-content-addressable-store.md` with an AC↔Task map covering AC-1..AC-5; "Baseline assumptions" section explicitly re-baselines AC-5 to drop the jp dependency (jp archived 2026-05-22T23:14:13Z per `_archive/commit-small-artifacts-by-default.md`) and notes x9 is shipped.
- DONE: Reuse x9's resolver pattern: new helper module (e.g., `src/razorback/freeze_dir_default.py` or extension of `runs_dir_default.py`) with `$RAZORBACK_FREEZE_DIR` → `$XDG_DATA_HOME/razorback/freeze` → `~/.local/share/razorback/freeze`. Specify where `spacedock_solver_v2._freeze_dir` is called and how the wiring changes.
  Plan creates `src/razorback/freeze_dir_default.py` as a direct mirror of `runs_dir_default.py` (T0 RED + T1 GREEN, 6 unit tests). T2 re-wires `SpacedockSolverAgent.resolve_freeze_dir` (current impl at `src/razorback/agents/spacedock_solver_v2.py:162-182`) from `<run-dir>/_razorback/freeze/<sealed_hash>/` to `resolve_default_freeze_dir() / self.sealed_hash`; deletes the dead `_resolve_run_dir_from_logs_dir` static method; updates the four existing host-git unit tests + two existing mechanism integration tests to set `$RAZORBACK_FREEZE_DIR` per-test. Note: the entity body says `_freeze_dir` but the actual symbol is `resolve_freeze_dir` — plan calls out the actual symbol verbatim.
- DONE: AC-4 migration helper: goal1-resume's old worktree-relative freeze trees were destroyed by prior FO --force cleanup, so there is nothing to migrate today. Recommend either deferring AC-4 (mark out-of-scope) OR scoping it to a simple `--source-dir`-driven helper for future use. Name the recommendation.
  **Recommendation: DEFER AC-4** — mark out of scope; rationale in plan under "AC-4 re-baseline". No migration target exists today and YAGNI applies; the breakglass sketch (a ~30-min `razorback freeze migrate --source-dir` Typer subcommand) is retained as Task 4 sketch in case captain rejects the deferral.

### Summary

Plan decomposes the entity into 6 TDD tasks (T0..T6, skipping T4) ordered riskiest-contract-first: resolver RED+GREEN (T0+T1) → agent re-wiring with existing-test updates (T2) → cross-worktree discovery mechanism (T3, AC-2 gate) → CAS-resume mechanism (T5, AC-5 gate) → full regression capture (T6, AC-3 gate). AC-4 (migration helper) is SKIPPED with rationale; the entity's other four ACs each get a dedicated task. The plan reuses x9's `runs_dir_default` resolver shape verbatim and removes the worktree-relative freeze path outright (no dual-path backwards compat) per the entity's AC-2 statement that freeze trees must be reachable "after worktree A is removed."
