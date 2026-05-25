---
id: 08ghk1yvkq9vzs71gzecx5bf
title: goal1 matrix aggregator computes paper-comparison verdict from stratified-mean (not pooled CI)
status: implementation
source: 2026-05-25 captain audit during 7q + d8 + an three-way crew-loop study. `examples/drivers/aggregate-goal1-scores.py:189` reads `per_query_verdict = _verdict(pooled_per_query_ci)` — the aggregator computes the against-paper-baseline verdict from the POOLED-per-query Wilson CI lower bound, NOT from the stratified-per-query mean. The DAB paper's `direct_baseline=0.4376` and `spacedock_baseline=0.577` are stratified-per-query values (each dataset weighted equally regardless of query count); comparing them against pooled-per-query CI is apples-to-oranges. Today the verdict happens to come out "above" for both 7q (0.7407 pooled vs 0.4376) and d8 (0.7222 pooled vs 0.577) but the magnitude and statistical reasoning are wrong, and the lens-mismatch could produce a different verdict on a borderline matrix. Discovered when captain asked "what's the stratified score" and FO surfaced that the captain-facing report's headline and verdict were both pooled-per-query, not stratified.
score: 0.85
auto-approve: false
worktree: .worktrees/spacedock-ensign-goal1-matrix-aggregator-stratified-verdict-fix
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

## Stage Report: plan

- DONE: Plan-output flex: 4 ACs, single-file change to examples/drivers/aggregate-goal1-scores.py + a fixture-based regression test + amendment blocks to 2 archived reports. Recommend INLINE plan per README threshold (single primary file + amendments).
  INLINE confirmed: README §plan flex rule says ≤3 ACs / single-file → inline; 4+ ACs / multi-subsystem → separate doc. This entity has 4 ACs but the change surface is a single Python file (~30 lines added) plus a single new test file plus two markdown amendments — all single-file edits, no subsystem touched, no harbor surfaces, no CLI shape change. The 4th AC is a backward-compat assertion, not a new subsystem. Single-file-change criterion dominates; inline plan is correct.
- DONE: Mechanism validation: read aggregate-goal1-scores.py:140-220 to confirm where `against_constant.per_query_verdict` is built; identify the right insertion point for `stratified_verdict`. Read 7q's `aggregate-score.json` to confirm `per_query_pass_at_1_mean_over_strata` is the right field name. Read AC-2's bootstrap-vs-null-CI methodology choice; recommend which option (a or b) per plan-stage analysis.
  Confirmed: `examples/drivers/aggregate-goal1-scores.py:189` builds `per_query_verdict = _verdict(pooled_per_query_ci)` from the pooled Wilson CI — the bug. `per_query_pass_at_1_mean_over_strata` is computed at L152-156 and is the canonical paper-comparable lens. Right insertion point: a new `stratified_verdict = _verdict_point(per_query_mean_over_strata, target_value)` between L188 and L189, with the new field emitted into the `against_constant` dict at L207-212. Verified against the 7q archived fixture at `_evidence/goal1-direct-structured-v2/matrix-aggregate/aggregate-score.json`: `per_query_pass_at_1_mean_over_strata = 0.6719017094017095`, target `direct_baseline = 0.4376`, expected new `stratified_verdict = "above"`.
- DONE: Task sequence: T0 RED unit test (fixture matrix root with paper_baseline=0.4376, known stratified mean 0.6719) → T1 GREEN add stratified_verdict computation → T2 CI methodology (bootstrap implementation OR null-CI documentation) → T3 amend 7q + d8 evidence reports → T4 full pytest stays green. Captain-decision-required at the CI methodology choice (T2) per AC-2.
  Task sequence below; AC-2 choice surfaced as captain-decision gate before T2.

### Summary

Inline plan for the goal1 matrix aggregator stratified-verdict fix. Single-file change at `examples/drivers/aggregate-goal1-scores.py` adds an `against_constant.stratified_verdict` field computed from `per_query_pass_at_1_mean_over_strata` against `paper_baseline.value`. AC-2's CI-methodology choice is surfaced as a captain-decision gate; plan-stage recommendation is **choice (b) null-CI + point comparison** on three grounds (bootstrap over 12 cells gives unhelpfully wide bounds at N=1 per query trial; mean-of-proportions across non-identical-N strata has multiple legitimate methods, picking one is a separate methodology entity per "Out of scope"; entity's research-integrity framing argues for conservative point comparison rather than premature statistical claims). Two archived captain-facing reports get amendment blocks at their top citing this entity and replacing pooled-headline verdict with stratified verdict. Pre-existing aggregator tests at `tests/unit/test_aggregate_goal1_from_definition.py` are shape-only and stay green per AC-4.

### Plan

#### AC ↔ task map

| Task | Covers | Surface |
|---|---|---|
| T0 | AC-1, AC-2 | tests/unit/test_aggregate_goal1_stratified_verdict.py (new) |
| T1 | AC-1 | examples/drivers/aggregate-goal1-scores.py |
| T2 | AC-2 | examples/drivers/aggregate-goal1-scores.py (CI methodology + docstring comment block) |
| T3 | AC-3 | docs/razorback-implementation/_evidence/goal1-direct-structured-v2/report.md AND docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md |
| T4 | AC-4 | full `uv run pytest tests/` |

#### Captain-decision gate (BLOCKING — required before T2)

**AC-2 CI methodology — captain choose (a) or (b).** Plan-stage recommendation: **(b) null-CI + point comparison** for the reasons in the Summary above. If captain prefers (a) bootstrap, T2 implements `numpy.random.choice` resampling of per-cell `per_query_pass_at_1` values with N=1000 resamples + 2.5/97.5 percentile bounds, and the verdict logic compares the bounds (matching the existing `_verdict(ci)` shape). The first officer surfaces this gate to the captain before dispatching the implementation stage; the FO does not auto-resolve regardless of sprint-wide auto-approval state per `auto-approve: false` in the entity frontmatter.

#### T0 — RED unit test (mechanism check first)

Add `tests/unit/test_aggregate_goal1_stratified_verdict.py` (new file, sibling of the existing `test_aggregate_goal1_from_definition.py`). The test plants the 7q archived `aggregate-score.json` strata into a stub matrix root: for each of the 12 datasets, write a minimal `result.json` shape that drives `extract_cell_stats` to return the per-cell `per_query_pass_at_1` value recorded in the 7q archived fixture (12 cells, stratified mean = 0.6719). Then run `module.aggregate_variant(matrix_root, "direct-structured")` and assert:

- `agg["per_query_pass_at_1_mean_over_strata"] == pytest.approx(0.6719, abs=1e-3)`
- `agg["against_constant"]["name"] == "direct_baseline"` and `agg["against_constant"]["value"] == 0.4376`
- **`agg["against_constant"]["stratified_verdict"]["verdict"] == "above"`** ← this is the RED assertion; field does not exist on baseline `main`.
- `agg["against_constant"]["stratified_verdict"]["stratified_mean"] == pytest.approx(0.6719, abs=1e-3)`
- `agg["against_constant"]["stratified_verdict"]["value"] == 0.4376`
- backward-compat assertions: `agg["against_constant"]["per_query_verdict"]` and `agg["against_constant"]["verdict"]` still emit (AC-4 backstop).

Run the test on baseline `main` to confirm RED (the `stratified_verdict` key access raises KeyError). Commit the failing test before T1.

Spec cite: AC-1 ("Running the aggregator against the 7q matrix root produces an `aggregate-score.json` with `against_constant.stratified_verdict` block containing `{value: 0.4376, stratified_mean: 0.6719, verdict: 'above'}`").

#### T1 — GREEN implementation

In `examples/drivers/aggregate-goal1-scores.py`:

1. Add a `_verdict_point(mean: float | None, target: float) -> str` helper near `_verdict` (L178-186). Returns "above" / "below" / "matches" by direct numeric comparison; "no_data" when mean is None. "matches" is reserved for the null-CI choice when `mean == target` exactly (rare in floating point; in practice this branch produces above/below only).
2. Between L188 (`verdict = _verdict(stratified_ci)`) and L189, add: `stratified_verdict_value = _verdict_point(per_query_mean_over_strata, target_value)`.
3. In the `against_constant` dict at L207-212, add a new key (place it first to signal canonical lens):
   ```
   "stratified_verdict": {
       "value": target_value,
       "stratified_mean": per_query_mean_over_strata,
       "ci": None,                  # ← AC-2 choice (b); see T2 if choice (a)
       "verdict": stratified_verdict_value,
   },
   ```
4. Leave `verdict` (binary, L210) and `per_query_verdict` (pooled, L211) unchanged — backward compat per AC-4.
5. Add a 3-line comment block above the new field building noting: "Canonical paper-comparison lens. The DAB paper's `paper_baseline` is stratified-per-query (each dataset weighted equally regardless of query count); `per_query_verdict` (pooled) and `verdict` (binary) are supplementary views."

Run T0; expect GREEN. Commit.

Spec cite: AC-1 (Verified by: aggregator's source has `stratified_verdict` building logic + 7q-shape produces expected dict).

#### T2 — CI methodology (gated on captain choice)

**If choice (b) — recommended:** Add a comment block above the `stratified_verdict` building (3-6 lines) documenting: "CI methodology: null. Mean-of-proportions across non-identical-N strata is not binomial; bootstrap over 12 cells at N=1 query trial per query is uninformative. Verdict is a point comparison. Downstream consumers MUST NOT claim statistical significance from `stratified_verdict.ci == null`. Stratified-Wilson / Cochran-Mantel-Haenszel aggregation is a separate methodology entity if captain wants significance claims." T2 ships as part of T1's commit.

**If choice (a) — bootstrap:** Add a `_bootstrap_stratified_mean_ci(values: list[float], n_resamples: int = 1000, alpha: float = 0.05) -> tuple[float, float]` helper near `wilson_ci` (L31-39). Uses `random.Random(seed=0)` for determinism (matches `wilson_ci`'s deterministic-z conventions; do not introduce numpy/scipy dep unless captain ack). Resamples 12 per-cell `per_query_pass_at_1` values with replacement, computes the mean each time, returns 2.5/97.5 percentiles. Wire into `stratified_verdict["ci"]`; verdict logic compares CI bounds via `_verdict(ci)` rather than `_verdict_point(mean, target)`. Add a T0 supplementary assertion: `stratified_verdict["ci"]` is a 2-tuple, both bounds in [0, 1], lo ≤ stratified_mean ≤ hi. Commit.

Spec cite: AC-2 (Verified by: documented methodology choice; if (a), CI 2-tuple; if (b), ci is null + downstream note).

#### T3 — amend 7q + d8 archived reports

Add an `## Amendment 2026-MM-DD post-aggregator-fix` section at the **top of the body** (immediately after the closing `---` of the YAML frontmatter, before the existing `## Headline` section) of both:

1. `docs/razorback-implementation/_evidence/goal1-direct-structured-v2/report.md`
2. `docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md`

Each amendment block (≤15 lines) contains:
- Forward-pointer: "Aggregator emitted pooled-per-query as the paper-comparison verdict at the time this report was archived. Per `docs/razorback-implementation/goal1-matrix-aggregator-stratified-verdict-fix.md` (commit SHA recorded in this entity's archived stage report), the canonical lens is stratified-per-query."
- Corrected headline: stratified-mean value (7q: 0.6719; d8: TBD — implementation-stage worker reads `_evidence/goal1-rerun-.../matrix-aggregate/aggregate-score.json` for the d8 number, or re-runs the aggregator on the d8 matrix root if the archived file predates the field).
- Corrected verdict: stratified-verdict against paper_baseline (7q: above 0.4376; d8: above 0.577).
- Note that archived run-dirs are immutable; the amendment is a forward-pointing correction, not a re-run.

Implementation-stage worker records both commit SHAs in the archive stage report per AC-3 "Verified by".

Spec cite: AC-3 (Verified by: both reports carry `## Amendment 2026-MM-DD post-aggregator-fix` at top; entity's archived stage report cites the commit SHAs).

#### T4 — pytest green + backward compat

Run `uv run pytest tests/` from repo root. Required to pass (modulo pre-existing failures documented elsewhere):
- `tests/unit/test_aggregate_goal1_from_definition.py` (existing, shape-only) — stays green.
- `tests/unit/test_aggregate_goal1_stratified_verdict.py` (new from T0) — green post-T1.
- Integration test `tests/integration/test_dab_paper_matrix_external_oracle_gate.py` — does not exercise per_query_verdict semantics; stays green.

If pre-existing failures surface, document them in the implementation-stage stage report; do not fix them in this entity per YAGNI.

Spec cite: AC-4 (Verified by: `uv run pytest tests/` exits 0 modulo pre-existing failures; aggregator's regression tests pass).

#### Validation entry criteria

- T0's RED→GREEN transition demonstrated in implementation-stage stage report (commit SHAs for RED commit and GREEN commit).
- T1 + T2 implementation lands on the worktree branch with the AC-2 choice the captain selected at the gate.
- T3 amendment commits cited by SHA in the implementation-stage stage report.
- T4 pytest output captured (pass count, not full log).
- Validation-stage agent re-runs T0's test and `uv run pytest tests/` independently.
