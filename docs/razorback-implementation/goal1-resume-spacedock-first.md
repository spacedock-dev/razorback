---
id: djrw746ny83bf47t4cj4h5vz
title: Goal 1 RESUME — DAB paper reproduction (spacedock-first matrix order)
status: backlog
source: Goal 1 PARTIAL ship 2026-05-20 (archived at _archive/goal1-dab-paper-reproduction.md) — matrix order put spacedock variant last; ENOSPC at cell 20/36 left spacedock 0/12. Captain directive 2026-05-20: redispatch with spacedock-first ordering since AC-5 names spacedock as the primary reproduction claim.
started:
completed:
verdict:
score: 0.65
worktree:
issue:
pr:
mod-block:
---

## Problem

The archived goal1-dab-paper-reproduction shipped with verdict
PARTIAL because the matrix interrupted at cell 20/36 with ENOSPC
(root cause closed by PKG-21 SQLite/DuckDB bind-mount). The
matrix dispatch order — direct-minimal → direct-structured →
spacedock — meant the spacedock variant was last in the queue
and never ran (0/12 cells).

But the archived entity's AC-5 said:
> "The verdict for the `spacedock` variant is the **primary
> reproduction claim**."

The matrix-order miss buried the load-bearing variant. This
resume entity re-dispatches the 36-cell matrix with **spacedock
first**, so that any future partial-completion scenario leaves
the headline reproduction number intact.

This resume entity also picks up the upstream fixes that have
landed since the archived dispatch:
- PKG-21 (SQLite/DuckDB clonefile materialization) — closes the
  ENOSPC root cause
- PKG-25 (Linux reflink fallback) — safety hot-fix, no runtime
  effect on darwin but the docstring is now honest
- PKG-15-mongo-init-followup (filed concurrently) — extends the
  mongo healthcheck timeout so agnews + yelp cells produce real
  verifier output instead of mongo-not-ready short-circuit

## Acceptance criteria

**AC-1 — Matrix dispatch order is spacedock-first.**
`examples/drivers/dab-paper-matrix.sh` (or the
generate-dab-paper-matrix-specs.py output) walks variants in
order: spacedock → direct-structured → direct-minimal. Within
each variant, datasets are walked in a deterministic order
(alphabetical or score-priority).
Verified by: `dab-paper-matrix.sh --dry-run` prints cell 1/36 as
`spacedock/agnews` (or whatever the first spacedock dataset is),
and cell 12/36 as the last spacedock cell.

**AC-2 — Resume picks up partial results from the archived run.**
The matrix driver is idempotent — cells with valid result.json
from the archived dispatch are skipped on re-dispatch. (The
archived run's run-dirs are at
`.worktrees/spacedock-ensign-goal1-dab-paper-reproduction/runs/goal1/`
which got cleaned post-merge; new dispatch starts fresh under a
NEW runs/ path.)
Verified by: dry-run output shows 36 cells dispatched in
spacedock-first order; a partial completion + re-dispatch
reproduces the final state.

**AC-3 — Per-variant `rk score --against-constant` produces 3 per-
variant stratified pass@1 numbers with Wilson 95% CIs.** Same as
the archived entity's AC-5. The spacedock variant compares
against 0.577 (paper headline); direct-minimal and
direct-structured compare against 0.4376 (paper direct
baseline).
Verified by: per-variant `rk score` output committed alongside
the matrix's run-dir set.

**AC-4 — Audit is clean across all 36 cells.**
`rk audit --policy strict` reports `n_tainted: 0` over the
aggregate run-dir set. PKG-16's workdir-no-dump policy stays
enforced.
Verified by: aggregate audit report's `n_tainted` is 0.

**AC-5 — Cost stays within budget.**
The dispatcher's final budget.json total is at or below the
declared `experiment.max_budget_usd` (suggested $100 with paid
API tier; .env auth means cost_usd is non-null).
Verified by: cost ledger committed; total ≤ budget.

**AC-6 — Result summary committed.**
`docs/superpowers/plans/2026-05-19-goal1-paper-reproduction.md`
(the same path the archived dispatch wrote to — overwrite OR
append a "Resume" section) carries the 3 per-variant numbers,
audit pass, cost ledger, and a "matrix-order lesson" caveat
explicitly naming why spacedock-first is the correct ordering
for AC-5-style entity-typed reproductions.
Verified by: result doc references the new run-dir set and
explicitly contrasts the partial PARTIAL ship (spacedock 0/12)
with the corrected resume (spacedock 12/12 expected).

## Test plan

- **Dry-run test:** dispatcher's `--dry-run` mode prints the 36-
  cell plan in spacedock-first order.
- **Acceptance command:** `bash
  examples/drivers/dab-paper-matrix.sh --budget 100 --output-dir
  runs/goal1-resume/` exits 0 after dispatching all 36 cells.

## Out of scope

- N>1 trials per cell (still N=1 per captain's "1× is fine"
  directive).
- Goal 2 (separate entity, separate matrix shape).
- Failure-mode analysis (PKG-11 future work).

## Depends on

- PKG-21 (shipped) — SQLite/DuckDB clonefile materialization
- PKG-25 (shipped) — Linux reflink fallback (no runtime effect on
  darwin; included for completeness)
- PKG-15-mongo-init-healthcheck-timeout (concurrent — agnews +
  yelp cells need this to produce real verifier output)
- Archived goal1-dab-paper-reproduction (lessons + matrix
  artifacts; this entity supersedes its verdict)

## Resume hook

After this entity merges with verdict=PASSED, the 3 per-variant
stratified pass@1 numbers + Wilson CIs are the canonical Goal 1
result. The archived PARTIAL ship is superseded but kept for
audit history.
