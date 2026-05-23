---
id: d883spjk4ypycse716tfy3pt
title: Goal 1 re-run — recompute captain-facing headline against canonical per-query reducer (post-1s)
status: plan
source: Captain directive 2026-05-23 — "stop reporting binary for dab" — follow-up #4 from archived `an goal1-rerun-dab-spacedock-opus47-xhigh`, unblocked by `1s runs-aggregate-single-score-reducer` shipping (commit on main)
started: 2026-05-23T18:57:57Z
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
mod-block:
---

## Problem

The archived `an goal1-rerun-dab-spacedock-opus47-xhigh` entity shipped
with a banner-box notice on its captain-facing report at
`docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md`
declaring its `pooled stratified_pass_at_1 = 0.333 [0.138, 0.609]`
headline a known under-count for DAB batch-mode (because the old
`runs/aggregate.py:_stratified_pass_at_1` binarized each cell's
composite reward via `>= 1.0`). The fix entity `1s
runs-aggregate-single-score-reducer` has now shipped a canonical
reducer that consumes `reward_per_query.json` directly — the yelp 0.857
composite reward now contributes 6/7 to the headline, not 0.

This entity re-issues the captain-facing report's headline against the
new reducer using the 12 cycle-1 + cycle-2 run-dir artifacts that were
preserved verbatim. No re-execution of the matrix is needed; the
recompute is a deterministic transformation of the existing artifacts.

## Acceptance criteria

**AC-1 — Recomputed headline reads `reward_per_query.json`.**
A fresh `rk score` or aggregator pass over the 12 cycle-1+cycle-2
run-dirs under `_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/`
(or equivalently the mirrored fixtures at
`docs/razorback-implementation/_evidence/an-goal1-rerun-cells/<dataset>/`)
emits a per-query / per-cell pass@1 number that is strictly different
from the binary `0.333` of the archived report (under-count) for at
least the cells whose `reward_per_query.json` records sub-binary
aggregates (yelp at 0.857 = 6/7 is the canonical example).
Verified by: run `examples/drivers/aggregate-goal1-scores.py`
(or equivalent) against the existing matrix root; capture the new
pooled `stratified_pass_at_1` number + the per-cell sub-table; assert
yelp's contribution is now 6/7, not 0.

**AC-2 — Captain-facing report headline replaced.**
The report at
`docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md`
is updated so the top-of-document Headline section carries the
per-query / continuous headline number with the Wilson CI and the
refreshed `--against-constant paper=0.577` verdict. The cycle-1 and
cycle-2 binary numbers are preserved in an "Audit history" or "Prior
headlines" subsection (do NOT delete them — they are the audit trail).
The cycle-1 banner-box notice is removed (the under-count is now
fixed); replace with a one-line "Headline scoring: canonical
per-query reducer (`runs/aggregate.py` post-`1s`)".
Verified by: the report's first non-frontmatter line is the new
headline; `grep -F 'stratified_pass_at_1 = 0.333' report.md` returns
0 matches in the Headline section but DOES return matches in the
"Prior headlines" subsection (audit trail preserved).

**AC-3 — Per-cell table surfaces per-query pass@1 alongside continuous reward.**
The per-dataset table in the report now shows each cell's per-query
pass@1 (the post-`1s` value) alongside the existing continuous
`reward` column. For DAB batch-mode cells the two should track each
other closely (per-query pass@1 ≈ rounded continuous reward); for any
cell where they diverge, the row is flagged for investigation.
Verified by: the table column header includes `per_query_pass@1`;
yelp's row shows `per_query_pass@1: 0.857` (= 6/7) + `reward: 0.857`.

**AC-4 — Provenance retained.**
The report cites the merged `1s` commit (or the merge commit on `main`)
as the reducer source, the run-dir paths as the fixture source, and
the date of recompute. The original `an` entity is referenced as the
matrix-execution source.
Verified by: bottom of report carries a 4-line provenance block with
the four citations above; `git log --oneline main -- docs/razorback-implementation/runs-aggregate-single-score-reducer.md`
confirms the cited commit.

## Test plan

- **Mechanism smoke:** one-cell recompute against `yelp` only.
  Confirm `rk score` reads `reward_per_query.json` and emits `6/7`
  (and that this matches the unit-test fixture from `1s`'s
  `tests/fixtures/score/dab_batch_run_dir/yelp__Cc94VEd/`).
- **Full recompute:** run the aggregator against the 12-cell matrix
  root. Capture the pooled number + per-cell sub-table.
- **Report rewrite:** edit
  `docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md`
  per AC-2 and AC-3. Diff is read-mostly: new Headline, new per-cell
  column, removed banner, preserved audit-history subsection.
- **Pytest:** `uv run pytest` stays green (no production code changes
  in this entity).

## Out of scope

- **N=5 paper-grade reproduction.** Filed as a sibling entity if/when
  captain wants paper-grade reproducibility; this entity stays at
  N=1.
- **Re-executing the matrix.** Artifacts are stable; recompute is
  deterministic.
- **Backporting the recompute pattern to other goals' reports.**
  Goals 2/3/4 (if any reports exist) are sibling work; this entity
  is scoped to goal1-rerun's report.
- **Cost telemetry fix.** The cycle-1/cycle-2 cells' `cost_usd: null`
  problem remains a known follow-up; not in scope here.

## Depends on

- **`1s runs-aggregate-single-score-reducer`**: DONE / archived
  (merged into main at commit `0a5e3a3` — actual merge commit on
  main; verify with `git log --oneline --merges -5 | grep 1s`).
  The canonical reducer in `runs/aggregate.py` is what this entity
  consumes.
- **`an goal1-rerun-dab-spacedock-opus47-xhigh`**: DONE / archived.
  Its run-dir artifacts + mirrored evidence are this entity's input
  fixtures.

## Resume hook

When this lands, the goal1-rerun captain-facing report stops carrying
a banner about a known under-count, and Goal 1 has a paper-faithful
headline. If captain wants the same recompute pattern applied to
other reports (or wants a sibling N=5 entity filed), the precedent is
set.
