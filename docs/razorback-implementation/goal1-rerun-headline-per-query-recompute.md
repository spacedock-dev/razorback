---
id: d883spjk4ypycse716tfy3pt
title: Goal 1 re-run — recompute captain-facing headline against canonical per-query reducer (post-1s)
status: validation
source: Captain directive 2026-05-23 — "stop reporting binary for dab" — follow-up #4 from archived `an goal1-rerun-dab-spacedock-opus47-xhigh`, unblocked by `1s runs-aggregate-single-score-reducer` shipping (commit on main)
started: 2026-05-23T18:57:57Z
completed:
verdict:
score: 0.9
worktree: .worktrees/spacedock-ensign-goal1-rerun-headline-per-query-recompute
issue:
pr:
mod-block: merge:pr-merge
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

## Stage Report: plan

- DONE: Apply plan-output flex rule; justify inline vs separate plan doc.
  Inline. 4 ACs nominally, but operationally collapses to one driver re-wire
  + one report rewrite (no production code, no spec re-derivation, no
  multi-subsystem touch). Separate `plans/{slug}.md` doc would be overhead.
- DONE: Mechanism validation — verify `examples/drivers/aggregate-goal1-scores.py`
  consumes `runs/aggregate.py:reduce_per_query_stratified` post-`1s`.
  BLOCKER FOUND. The aggregator still reads each cell's top-level
  `result.json` (`stats.evals.<x>.reward_stats.reward`) and binarizes with
  `r >= 1.0` at `aggregate-goal1-scores.py:64-65`. It never imports from
  `razorback.runs.aggregate`. Yelp's `0.8571` reward maps to `0/1` (the old
  under-count). Task 0 (driver re-wire) must land before recompute. The
  canonical reducer exists at `src/razorback/runs/aggregate.py:372`
  (`reduce_per_query_stratified`) with `read_trial_outcomes`/`count_trials`
  helpers; `rk score` (`src/razorback/cli/score.py:52-55`) is the reference
  caller pattern. The `reward_per_query.json` sidecars exist for DAB cells
  (verified at `_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/yelp/.../yelp__Cc94VEd/steps/main/verifier/reward_per_query.json` — 7 q's, 6 with reward=1.0).
- DONE: Name recompute command sequence + report-edit diff scope.
  See Task list below.

### Plan (inline)

#### AC↔task map
- Task 0 (driver re-wire) → enables AC-1, AC-3
- Task 1 (recompute) → AC-1, AC-3 data
- Task 2 (report rewrite) → AC-2, AC-3, AC-4

#### Task 0 — Re-wire `examples/drivers/aggregate-goal1-scores.py` to canonical reducer

- **Why first:** Riskiest contract. The driver's reward-extraction path
  (binary `r >= 1.0` over the cell-level `result.json`) is the bug. No
  recompute can produce a per-query number until this is fixed.
- **TDD checkpoint:** Mechanism smoke test against the yelp cell.
  Before any code change, run `uv run python -c "from razorback.runs.aggregate import read_trial_outcomes, reduce_per_query_stratified, count_trials; from pathlib import Path; run_dir = Path('_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/yelp/goal1-spacedock-yelp/484d0b940af2aa7b'); out = read_trial_outcomes(run_dir); r = reduce_per_query_stratified(out, trial_counts=count_trials(run_dir)); print(r['stratified_pass_at_1'], r['strata'])"`. Expected: `0.857...` with one `yelp` stratum, 7 query cells, 6 with `pass_at_1=1.0`. This proves the canonical reducer reads the sidecar correctly against a real cell before we touch the driver.
- **Code change (smallest reasonable):** Replace `extract_cell_stats(result_json)`'s reward-walking loop (lines 48-72) with a delegation to `reduce_per_query_stratified` on the cell's run-dir (the hash directory, i.e., the parent of the trial dirs). `find_result_json(cell_dir)` returns `cell_dir/*/*/result.json` — its `.parent` is the run-dir (`{cell_dir}/{task-folder}/{hash}/`). Pass that run-dir to `read_trial_outcomes` and `reduce_per_query_stratified`. The per-cell return dict gains `per_query_pass_at_1` (the reducer's `stratified_pass_at_1` on a single-dataset stratum) alongside the existing binary `pass_at_1`; keep `n_total`/`n_pass`/`n_errored` from `count_trials` so the pooled Wilson CI math at lines 107-109 keeps a consistent denominator. Spec §3.2 (per-query stratified pass@1) governs the contract.
- **Aggregate-level wiring:** `aggregate_variant` (lines 75-143) keeps the same shape but the per-stratum `pass_at_1` becomes the per-query number. The pooled headline still wants a Wilson CI over a binomial denominator; the cleanest reading of §3.2 is to pool `(sum of n_correct, sum of n_trials)` across all `(dataset, query_id)` cells (i.e., 7 yelp queries contribute 7 trials, 6 correct), and the cycle-1 binary denominator (1 cell = 1 trial) for non-batch strata stays unchanged. Add a `per_query_pass_at_1` field on the per-cell dict and a `pooled_per_query_pass_at_1` field on the aggregate dict to keep the binary numbers visible for audit (do not overwrite them).
- **Failing-test-first equivalent:** No formal pytest covers this driver (one-off script). Use the yelp-cell mechanism smoke above as the failing test; capture before/after numbers in the recompute step's stdout for evidence.

#### Task 1 — Recompute the 12-cell matrix

- **Command:** `uv run python examples/drivers/aggregate-goal1-scores.py --matrix-root _runs/goal1-rerun-spacedock-opus47-xhigh --out-dir _runs/goal1-rerun-spacedock-opus47-xhigh`
- **Expected output:** `_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/aggregate-score.json` carries the new `pooled_per_query_pass_at_1` + per-cell `per_query_pass_at_1`. Yelp's per-cell entry should show `per_query_pass_at_1: 0.857` (6/7); strata where the binary cell-level reward is already in `{0.0, 1.0}` (e.g., `bookreview` at 1.0, `agnews` at 0.5 binary→0/2 if it has 2 queries) should preserve their fan-out. The pooled headline drifts from `0.333` upward, capturing the partial-credit cells (`crmarenapro 0.692`, `googlelocal 0.750`, `PANCANCER_ATLAS 0.667`, `yelp 0.857`, etc.).
- **Mechanism-validation gate:** Before believing the full pooled number, eyeball the per-cell sub-table for any stratum whose new `per_query_pass_at_1` is structurally implausible (e.g., a cell whose continuous reward column says `0.857` but per-query reports `0.0` — that would indicate the sidecar didn't load and we silently fell back to the cell-level reward). Failing that check forces a Task 0 fix-cycle, not a Task 2 report rewrite.
- **Wallclock budget:** Driver runs in seconds (no re-execution). The full recompute should finish under 30s; if it exceeds 2 minutes, investigate.

#### Task 2 — Rewrite `docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md`

Diff scope (read-mostly edits — keep cycle 1/2 detail, dispatch ledger, freeze CAS, wallclock ledger, cost ledger, AC-5 provenance enumeration sections verbatim):

1. **Remove the cycle-2 banner box** (lines 7-23). The under-count is fixed by `1s`. Replace with a single line at the same position: `> **Headline scoring:** canonical per-query reducer (`runs/aggregate.py:reduce_per_query_stratified`, post-`1s` merge at commit `f76443b` on main).`
2. **Replace the Headline section** (lines 25-34, "## Headline (cycle 2 — clean 12/12)"). New title: `## Headline (post-1s recompute — per-query)`. New top line: `**Spacedock pooled per-query pass@1 = {N} (95% Wilson CI [{lo}, {hi}]) across {n_query_cells} query cells over 12 dataset strata.**` Followed by the `--against-constant paper=0.577` verdict. Then 1-2 sentences narrating the gain over binary (e.g., "Up from binary 0.333; yelp now contributes 6/7 instead of 0; <ds> still binary because <reason>"). Numbers filled in from Task 1 output.
3. **Preserve cycle-1 and cycle-2 binary headlines** in a new `## Audit history — prior headlines` subsection (immediately after the new Headline). Move the existing `## Cycle-1 headline (preserved for trail)` block (lines 42-52) under it AS-IS, and add: `### Cycle-2 binary headline (pre-1s, archived)` with the old `0.333 [0.138, 0.609]` number and the original verdict line. Do NOT delete these; they are the audit trail per AC-2's verified-by clause.
4. **Per-dataset table (lines 54-68)** — add one new column `per_query_pass@1` between the existing `pass@1` (binary) and `wilson_ci_95` columns. Update the column header. Each row's value comes from Task 1's `_runs/.../spacedock/aggregate-score.json`'s strata block. The pooled row's `per_query_pass@1` cell is the new headline number; the binary `pass@1` cell stays `0.333` for audit. Flag any row where `per_query_pass@1` and continuous `reward` diverge by > 0.05 with a footnote.
5. **Provenance block (new section at end, immediately after `## Wallclock ledger`):**
   ```
   ## Provenance — post-1s recompute

   - **Reducer source:** `src/razorback/runs/aggregate.py:reduce_per_query_stratified` (introduced by entity `1s runs-aggregate-single-score-reducer`, merged into `main` at commit `f76443b` on 2026-05-23).
   - **Fixture source:** 12 cell run-dirs at `_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/<dataset>/` (8 cycle-1 preserved + 4 cycle-2 re-executed; `reward_per_query.json` sidecars under each trial's `steps/main/verifier/`).
   - **Matrix-execution source:** entity `an goal1-rerun-dab-spacedock-opus47-xhigh` (archived; produced the run-dir artifacts above).
   - **Recompute date:** {YYYY-MM-DD filled at implementation time}.
   ```

#### Verified-by spot-checks (post-rewrite)

- `grep -F 'stratified_pass_at_1 = 0.333' docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md` returns ≥1 match inside the `Audit history` subsection (preserved) and 0 matches inside the new `Headline (post-1s recompute — per-query)` block. (AC-2 verified-by clause.)
- New `per_query_pass@1` column header is grep-able; yelp's row shows `0.857`. (AC-3 verified-by clause.)
- Provenance section is 4 lines; `git log --oneline main -- docs/razorback-implementation/runs-aggregate-single-score-reducer.md` confirms commit `c1fa7ad` (archive) lineage; `git log --oneline --merges main -- src/razorback/runs/aggregate.py` confirms `f76443b` as the merge. (AC-4 verified-by clause.)
- `uv run pytest` stays green (no production code changes; driver is not under pytest). (Test plan line 4.)

### Summary

Plan committed inline; 4 ACs collapse to 3 tasks (driver re-wire, recompute,
report rewrite). Task 0 (driver re-wire) is a hard prerequisite that the entity
body's AC-1 verified-by clause did not call out — the goal1 aggregator script
still binarizes via `r >= 1.0` and does not consume the canonical
`reduce_per_query_stratified`. The reducer + the per-cell `reward_per_query.json`
sidecars are confirmed present; only the driver wiring is missing. The riskiest
contract (canonical-reducer-against-real-cell yelp smoke) is named as the
first mechanism check before any driver code change, per the workflow's
mechanism-validation rule.
