---
id: 08ghk1yvkq9vzs71gzecx5bf
title: goal1 matrix aggregator computes paper-comparison verdict from stratified-mean (not pooled CI)
status: backlog
source: 2026-05-25 captain audit during 7q + d8 + an three-way crew-loop study. `examples/drivers/aggregate-goal1-scores.py:189` reads `per_query_verdict = _verdict(pooled_per_query_ci)` — the aggregator computes the against-paper-baseline verdict from the POOLED-per-query Wilson CI lower bound, NOT from the stratified-per-query mean. The DAB paper's `direct_baseline=0.4376` and `spacedock_baseline=0.577` are stratified-per-query values (each dataset weighted equally regardless of query count); comparing them against pooled-per-query CI is apples-to-oranges. Today the verdict happens to come out "above" for both 7q (0.7407 pooled vs 0.4376) and d8 (0.7222 pooled vs 0.577) but the magnitude and statistical reasoning are wrong, and the lens-mismatch could produce a different verdict on a borderline matrix. Discovered when captain asked "what's the stratified score" and FO surfaced that the captain-facing report's headline and verdict were both pooled-per-query, not stratified.
score: 0.85
auto-approve: false
worktree:
issue:
pr:
mod-block:
started:
completed:
verdict:
---

## Problem

`examples/drivers/aggregate-goal1-scores.py` rolls up 12 per-cell
`score.json` files into a single matrix-level `aggregate-score.json`
with three aggregation lenses computed:

- `pooled_per_query_pass_at_1` (lump all queries across all cells)
- `per_query_pass_at_1_mean_over_strata` (mean of per-cell pass@1 —
  paper-canonical for DAB)
- `pooled_pass_at_1` (each cell as one binary)

But the `against_constant` block emits a `per_query_verdict` field
computed from `pooled_per_query_ci` (lines 189-211). That's the wrong
lens for paper comparison: the DAB paper's `direct_baseline=0.4376`
and `spacedock_baseline=0.577` are stratified-per-query values, not
pooled.

Concrete impact discovered 2026-05-25: 7q + d8 captain-facing
reports led with `pooled_per_query` headline (0.7407 / 0.7222) and
cited the `per_query_verdict` (from pooled CI) as the paper-
comparison verdict. Captain corrected: "the benchmark compares
stratified. why do you keep talking about binary and pooled."
The verdict against paper happened to come out "above" either way
in this case, but on a borderline matrix the lens mismatch could
flip the verdict.

The fix is structural: the aggregator must emit a
`stratified_verdict` field computed against the stratified-mean
value, with appropriate CI methodology (mean-of-proportions is
not binomial — needs bootstrap or per-stratum CI aggregation).

## Acceptance criteria

**AC-1 — Aggregator emits stratified-mean verdict against paper_baseline.**
`examples/drivers/aggregate-goal1-scores.py` adds an
`against_constant.stratified_verdict` field (or equivalent) computed
from `per_query_pass_at_1_mean_over_strata` against the
auto-pulled or CLI-passed `paper_baseline.value`. The existing
`per_query_verdict` (pooled) and `verdict` (binary) fields remain
as supplementary views for backward compatibility, but the
canonical paper-comparison verdict is `stratified_verdict`.
Verified by:
- `grep -n "stratified_verdict\|per_query_pass_at_1_mean_over_strata" examples/drivers/aggregate-goal1-scores.py` shows the new field building logic.
- Running the aggregator against the 7q matrix root produces an `aggregate-score.json` with `against_constant.stratified_verdict` block containing `{value: 0.4376, stratified_mean: 0.6719, verdict: "above"}` (or equivalent).
- The verdict is computed against the stratified mean (`per_query_pass_at_1_mean_over_strata`), NOT against `pooled_per_query_pass_at_1`.

**AC-2 — CI methodology for stratified mean documented + implemented.**
The aggregator picks ONE of: (a) bootstrap resampling over per-cell
pass@1 values to compute an empirical CI on the stratified mean, OR
(b) emit `stratified_verdict.ci: null` with an explicit note that
mean-of-proportions isn't binomial. Verdict logic (above / inside /
below) uses the mean directly when CI is null (point comparison) or
the CI bounds when CI is available.
Verified by:
- The aggregator's source has a documented CI methodology choice (a) or (b) in a comment block above the `stratified_verdict` building.
- If choice (a): `stratified_verdict.ci` is a 2-tuple from bootstrap; verdict logic compares CI bounds.
- If choice (b): `stratified_verdict.ci` is null; verdict is a point comparison; downstream consumers don't claim statistical significance from a null CI.

**AC-3 — Captain-facing reports for 7q + d8 (archived) get an amendment commit on main.**
The shipped reports at `docs/razorback-implementation/_evidence/goal1-direct-structured-v2/report.md` (post-7q-fix already partial) and `docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md` get an amendment block at the top citing the aggregator-fix entity and replacing the pooled-headline verdict with the stratified verdict. Archived reports stay archived; the amendment is a forward-pointing note in the evidence directory.
Verified by:
- Both reports carry an `## Amendment 2026-MM-DD post-aggregator-fix` section at the top with the stratified-only headline + verdict.
- The aggregator-fix entity's archived stage report cites which evidence reports were amended + commit SHAs.

**AC-4 — Existing pytest stays green; backward compat preserved.**
The aggregator's existing `per_query_verdict` (pooled) and `verdict` (binary) fields remain available; tests covering the aggregator continue to pass; downstream consumers that read those fields don't break.
Verified by:
- `uv run pytest tests/` exits 0 modulo pre-existing failures.
- The aggregator's regression tests (if any exist) pass; if no aggregator tests exist, add at least one round-trip test against a fixture matrix root (using the 7q evidence as the fixture).

## Test plan

- **Mechanism check first:** read `aggregate-goal1-scores.py:140-220` to confirm the per-stratum / pooled / per-cell aggregation block; identify the right insertion point for `stratified_verdict`.
- **TDD:** RED test asserting `aggregate-score.json["against_constant"]["stratified_verdict"]["verdict"] == "above"` against a 7q-shape fixture matrix root with paper_baseline=0.4376 and known stratified mean 0.6719. RED on baseline `main`; GREEN after fix.
- **Bootstrap CI (if choice a):** add a small bootstrap-resampling helper or use scipy/numpy; resample over per-cell pass@1 with N=1000 or similar; emit 95% CI bounds.
- **Backward compat test:** existing `per_query_verdict` and `verdict` fields still emit per their original logic.
- **Reports amendment:** generate the amendment blocks for 7q + d8 evidence reports as part of the impl-stage stage report.

## Out of scope

- **Per-stratum Wilson CI aggregation methodology.** Mean-of-proportions across non-identical-N strata is a well-studied stats problem (Cochran-Mantel-Haenszel weighting, stratified Wilson, etc.); choosing a specific method is a separate methodology entity if captain wants statistical-significance claims beyond point comparison.
- **Bootstrap CI for N=1 per-stratum.** At N=1 trial per query per cell, the per-cell pass@1 IS the observed proportion; bootstrap over 12 cells gives an empirical CI but with wide bounds. Whether that's the right methodology is open.
- **Aggregator generalization to other benchmarks.** `aggregate-goal1-scores.py` is DAB-paper-shape specific (hard-codes the 12 datasets, variant names, etc.). Generalizing to other matrix shapes is a separate entity if/when other benchmarks need matrix-aggregation.
- **`rk score` single-cell verdict.** `rk score`'s `against_constant.stratified.verdict` is already correct (compares mean against constant, point comparison since CI is null per stratum). This entity's fix is only the matrix aggregator.

## Depends on

- **hm `generic-harbor-benchmark-surface-design`** (DONE / archived):
  ships `rk score` auto-pulling `paper_baseline` from spec frontmatter.
  Aggregator's stratified-verdict reads the same auto-pulled value.

## Resume hook

When this lands, the matrix aggregator's paper-comparison verdict is
on the same lens as the paper itself. Phase 5's analyze-stage prompt
can reference the aggregator path safely for DAB-shape multi-dataset
matrices. The 7q + d8 evidence reports carry corrected amendments.
Future DAB-shape matrix runs (e.g., an direct-minimal when it lands,
or any N≥3 follow-on study) get the right verdict by construction.

`auto-approve: false` because this is research-integrity surface —
a wrong-lens verdict on a published headline is misconduct in the
limit.
