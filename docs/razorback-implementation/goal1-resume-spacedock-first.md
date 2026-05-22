---
id: djrw746ny83bf47t4cj4h5vz
title: Goal 1 RESUME — DAB paper reproduction (spacedock-first matrix order)
status: validation
source: Goal 1 PARTIAL ship 2026-05-20 (archived at _archive/goal1-dab-paper-reproduction.md) — matrix order put spacedock variant last; ENOSPC at cell 20/36 left spacedock 0/12. Captain directive 2026-05-20: redispatch with spacedock-first ordering since AC-5 names spacedock as the primary reproduction claim.
started: 2026-05-21T06:11:54Z
completed:
verdict:
score: 0.65
worktree: .worktrees/spacedock-ensign-goal1-resume-spacedock-first
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

## Plan (inline)

Scope is small: re-use the archived dispatch's matrix driver +
spec generator with a single-axis reordering (spacedock first),
then re-burn the 36-cell matrix on the paid API tier and update
the result doc. No new code surfaces; no new ACs beyond the
ordering and budget changes.

### Architecture

**Reordering change point — ONE source of truth.**
`WORKSPACE_VARIANTS` at
`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py:7`
is the canonical tuple. Both `examples/drivers/generate-dab-paper-matrix-specs.py:88`
and `examples/drivers/aggregate-goal1-scores.py:163` iterate it
verbatim. The bash driver hard-codes its own
`DEFAULT_VARIANTS="direct-minimal,direct-structured,spacedock"` at
`examples/drivers/dab-paper-matrix.sh:29`.

Reorder option A (chosen): change the canonical
`WORKSPACE_VARIANTS` tuple to `("spacedock", "direct-structured",
"direct-minimal")`. The spec generator and aggregator pick this
up automatically. The bash driver's `DEFAULT_VARIANTS` constant
is updated in lockstep to the same order. One existing unit test
at
`packages/razorback-plugin-dab/tests/unit/test_workspace_readme_variants.py:13`
asserts the tuple order — that test is updated to the new
spacedock-first order (test-first: the failing assertion is the
TDD step proving the reorder landed).

Option B (rejected): pass `--variants spacedock,...` everywhere.
Rejected because the implicit default would still be wrong, and a
future re-dispatcher would silently re-stack `direct-minimal`
first. The canonical tuple is the right single point of truth.

**Dataset ordering within a variant.** Current order is
DAB_DATASETS' natural enum order. That's deterministic and
captain doesn't require alphabetical, so we leave it. AC-1's
"alphabetical or score-priority" allows either.

**Idempotence.** The bash driver at
`examples/drivers/dab-paper-matrix.sh:115-138` already checks
each cell's `<runs_dir>/*/*/result.json` for
`n_completed_trials >= 1 and n_errored_trials == 0`. We dispatch
into a NEW path `runs/goal1-resume/` (per AC-2's "starts fresh
under a NEW runs/ path"), so the resume run does not see archived
partial state — that's the captain-intended fresh re-burn. The
idempotence shape is preserved for *intra-resume* partial
recovery: if the resume itself interrupts, re-running the driver
skips completed cells under `runs/goal1-resume/`.

**Paid-API auth.** The archived run used Claude Code subscription
auth (`CLAUDE_CODE_OAUTH_TOKEN` from `~/.claude/benchmark-token`);
`cost_usd` was `null` for every trial. The resume runs on paid
API tier — `.env` carries `ANTHROPIC_API_KEY`, the agent reports
real `cost_usd`, and the per-cell `budget.json` actually
enforces a ceiling. The driver does not need changes for this:
`uv run rk run --max-budget-usd-running ...` already enforces
when `cost_usd` is non-null.

**Scoring contract (unchanged).** Spacedock → `spacedock=0.577`;
direct-minimal + direct-structured → `direct_baseline=0.4376`.
Per-variant aggregate at `aggregate-goal1-scores.py` already
walks `WORKSPACE_VARIANTS` and emits stratified-mean pass@1 +
Wilson 95% CI per variant. AC-3 falls out of running it over
`runs/goal1-resume/matrix/`.

**Mongo healthcheck dependency.** PKG-15-mongo-init-healthcheck-timeout
gates agnews + yelp cells producing real verifier output. If
PKG-15 has not landed by the time T2 dispatches, those two cells
short-circuit the same way the archived run did — they aggregate
as "no completed trial with reward", which is a known failure
mode the result doc must surface. T2 must NOT dispatch the full
matrix until PKG-15 ships; if PKG-15 slips, captain decides
whether to dispatch the other 34 cells and re-do agnews + yelp
later, or wait.

### Tasks

**T0 — Paid-API cost-shape verification (riskiest-contract-first).**
- 1 trial opus-4.7 against `bookreview` with `.env`
  `ANTHROPIC_API_KEY` auth (NOT
  `CLAUDE_CODE_OAUTH_TOKEN`); record measured per-trial
  `cost_usd`.
- Project matrix total: `per_trial_cost × 36`. The 36-cell
  matrix has highly variable cost per cell (some DAB tasks are
  10-question, some 100+); the bookreview probe is a lower bound.
  Better projection: probe 3 cells of differing question-count
  (bookreview ~3 questions, crmarenapro ~13, PANCANCER_ATLAS
  ~100+) and scale by question-count median.
- **Captain gate:** if projected total > $100 (the declared
  `experiment.max_budget_usd`), STOP and surface to captain
  before T2 dispatches. Per captain standing order, $100 is the
  budget ceiling; over that needs explicit approval.
- Output: `runs/goal1-resume/t0/` with 1-3 probe trials and a
  `cost-projection.md` summarizing per-trial cost + matrix
  projection.

**T1 — Reorder `WORKSPACE_VARIANTS` (TDD) + regenerate specs.**
- Update
  `packages/razorback-plugin-dab/tests/unit/test_workspace_readme_variants.py:13`
  to assert `("spacedock", "direct-structured", "direct-minimal")`.
  Run test → it fails (TDD step 1-2).
- Update `WORKSPACE_VARIANTS` at
  `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py:7`
  to the new order. Run test → it passes (TDD step 3-4).
- Update `DEFAULT_VARIANTS` in
  `examples/drivers/dab-paper-matrix.sh:29` to
  `"spacedock,direct-structured,direct-minimal"` to match.
- Regenerate the 36 spec set:
  `uv run examples/drivers/generate-dab-paper-matrix-specs.py --freeze`.
  The script walks `WORKSPACE_VARIANTS` so the regenerated specs
  carry the new order on disk too (though spec files are
  per-variant directories, so the on-disk ordering is just a
  cosmetic re-emit).
- Verify dry-run: `bash examples/drivers/dab-paper-matrix.sh
  --dry-run` prints cell 1/36 as `spacedock/agnews` (or whichever
  DAB dataset is first in DAB_DATASETS) and cell 12/36 as the
  last spacedock dataset. This satisfies AC-1 verification.

**T2 — Dispatch the matrix into `runs/goal1-resume/`.**
- **Hard pre-condition:** PKG-15-mongo-init-healthcheck-timeout
  is shipped (status=done, verdict=PASSED). Otherwise the agnews
  + yelp cells short-circuit and the resume reproduces the
  archived run's mongo failure mode. The entity's "Depends on"
  list names this explicitly.
- Set `.env` `ANTHROPIC_API_KEY` for paid-API auth (NOT the
  subscription `CLAUDE_CODE_OAUTH_TOKEN`).
- Run `bash examples/drivers/dab-paper-matrix.sh --budget 100
  --output-dir runs/goal1-resume/`. Driver dispatches all 36
  cells in spacedock-first order, runs per-cell `rk run + rk
  audit + rk score`, writes per-cell `result.json` + `audit.json`
  + `score.json`, threads `budget.json` for in-flight cost gate.
- Driver's `--continue-on-fail` is OFF by default — first failure
  halts the matrix so we can surface to captain. If the failure
  is a known-recoverable one (e.g., transient API hiccup), driver
  is re-runnable and skips completed cells.
- If $100 ceiling is hit mid-dispatch, driver's per-cell
  `rk run --max-budget-usd-running` refuses with exit 22 and
  the matrix pauses; surface to captain.

**T3 — Per-variant `rk score` aggregate + `rk audit` aggregate.**
- Run `uv run python examples/drivers/aggregate-goal1-scores.py
  --runs-root runs/goal1-resume/` (or whatever its flag shape
  is) to produce per-variant stratified pass@1 + Wilson CI +
  per-stratum verdicts. Output: `runs/goal1-resume/matrix/
  <variant>/aggregate-score.json` + matrix summary.
- Run `uv run rk audit runs/goal1-resume/ --policy strict
  --format json` over the aggregate run-dir set; assert
  `n_tainted == 0`. This satisfies AC-4.
- Commit cost ledger: the driver's `dispatch-ledger.tsv` already
  records per-cell `cost_usd`. Sum them; assert total ≤ $100
  (AC-5).

**T4 — Update result doc.**
- APPEND a `## Resume — spacedock-first re-dispatch
  (2026-05-21)` section to
  `docs/superpowers/plans/2026-05-19-goal1-paper-reproduction.md`
  (NOT overwrite — the archived PARTIAL ship's reporting stays
  visible for audit history per the entity's "archived ... but
  kept" framing). The Resume section carries:
  - 3 per-variant stratified pass@1 numbers + Wilson 95% CIs,
    spacedock LISTED FIRST as the headline reproduction claim
  - audit pass/fail (`n_tainted == 0` over 36 cells)
  - cost ledger total + per-cell breakdown
  - **matrix-order lesson** subsection explicitly naming:
    "AC-5-style entity-typed reproductions where one variant is
    the load-bearing claim MUST dispatch that variant first.
    The archived ship buried spacedock at position 25-36 of the
    36-cell queue; ENOSPC at cell 20/36 left 0/12 spacedock
    cells. The corrected ordering dispatches spacedock at 1-12
    so any future partial-completion scenario preserves the
    headline number."
  - run-dir set references: `runs/goal1-resume/matrix/`,
    `runs/goal1-resume/<variant>/<dataset>/`, the
    dispatch-ledger TSV.
- Commit alongside the matrix artifacts.

### TDD-order rationale (riskiest-contract-first)

T0 first: paid-API cost is the unknown that could invalidate
everything downstream. If projected matrix > $100, captain
decides before any code or spec changes burn time.

T1 second: the reorder is the entity's load-bearing change.
TDD ensures the canonical tuple change actually propagates;
the dry-run check at T1 end is mechanism-validation kin
(per CLAUDE.md "validate the smallest end-to-end exercise of
the riskiest path FIRST") — cheap to verify, expensive to miss.

T2 third (dependent on PKG-15): the actual burn. Will not start
until PKG-15 ships and T0/T1 are green. T2's idempotence shape
lets a partial resume recover without re-burning completed cells.

T3 + T4 last: aggregation and reporting. These are mechanical
once T2 lands.

### Out-of-scope reaffirmation

- N>1 trials per cell (entity body §Out of scope).
- New ACs or surface changes — this is a re-burn with a single-
  axis reorder.
- Failure-mode analysis of failed trials (PKG-11 future work).
- Cross-model comparison (opus-4.7 only; same as archived).
- Aggregator refactoring beyond running it.

### Dependencies (operational)

- **PKG-15-mongo-init-healthcheck-timeout** — HARD blocker on T2
  (agnews + yelp cells). If PKG-15 slips, captain decides
  partial-dispatch vs. wait.
- PKG-21 (shipped) — SQLite/DuckDB clonefile materialization;
  closes the archived run's ENOSPC root cause.
- PKG-25 (shipped) — Linux reflink fallback; no darwin runtime
  effect.
- Archived `goal1-dab-paper-reproduction` — supersedes its
  verdict; preserves its result-doc section for audit history.

## Stage Report: plan

- DONE: Plan is INLINE (small scope: re-use existing matrix driver + spec generator with spacedock-first reordering). Stage report on entity body.
  Plan added inline above as `## Plan (inline)`; no separate plan doc; scope is single-axis reorder + re-burn.
- DONE: Plan names the exact code change point: most likely examples/drivers/generate-dab-paper-matrix-specs.py — change variant iteration order. ALSO note that the matrix driver should pick up partial result.json from prior runs/ paths if any exist (idempotency); fresh dispatch path is new runs/goal1-resume/.
  Change point is the canonical tuple at `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py:7` (both the spec generator and aggregator iterate it), plus the bash driver's `DEFAULT_VARIANTS` at `examples/drivers/dab-paper-matrix.sh:29`. Idempotence preserved: T2 dispatches into NEW `runs/goal1-resume/`; intra-resume partial recovery uses the driver's existing `n_completed_trials >= 1 and n_errored_trials == 0` skip logic.
- DONE: Plan TDD-orders: T0 cost-shape verification (1 trial opus-4.7 with .env paid auth) FIRST since we're now on paid API and need to confirm per-trial cost projection; T1 spec regen with spacedock-first; T2 matrix driver dispatch; T3 score + audit aggregate; T4 result-doc UPDATE (append Resume section to docs/superpowers/plans/2026-05-19-goal1-paper-reproduction.md with matrix-order lesson explicit). Plan acknowledges this entity is dependent on PKG-15-mongo-init-healthcheck-timeout shipping before T2 dispatches the agnews/yelp cells.
  T0→T1→T2→T3→T4 ordered per riskiest-contract-first; T0 paid-API probe (3-cell question-count-scaled projection, $100 captain gate); T1 TDD reorder of canonical `WORKSPACE_VARIANTS` (failing unit test first); T2 dispatch into `runs/goal1-resume/` with HARD pre-condition that PKG-15 has shipped (named in §Tasks T2); T3 aggregator + `rk audit --policy strict`; T4 APPENDS a "Resume" section to the existing result doc (not overwrites) with explicit matrix-order lesson subsection.

### Summary

Wrote an inline plan with T0-T4 covering all 6 ACs. The
load-bearing change is a single canonical `WORKSPACE_VARIANTS`
tuple reorder at
`packages/razorback-plugin-dab/.../workspace_readme.py:7` plus
the bash driver's mirroring `DEFAULT_VARIANTS` constant — both
updated in lockstep, gated by a failing unit test (TDD). T0
verifies paid-API cost shape against the $100 ceiling before
any matrix burn. T2 hard-blocks on PKG-15 (mongo healthcheck)
shipping; the resume dispatches into a fresh `runs/goal1-resume/`
path so the archived partial-result history at
`runs/goal1/` and the archived result-doc section stay
visible for audit.
