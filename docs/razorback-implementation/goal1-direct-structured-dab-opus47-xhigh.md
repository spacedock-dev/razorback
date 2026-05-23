---
id: 7qwenbebdvmqj3gd7xxdpytd
title: Goal 1 sibling — DAB direct-structured matrix, opus-4.7, reasoning_effort=xhigh, batch, parallel=1
status: plan
source: Captain directive 2026-05-23 — "run an equivalent of this (same workflow readme) but without spacedock" — paper-comparable direct-baseline run alongside the just-archived `d8 goal1-rerun-headline-per-query-recompute` (spacedock pooled per-query=0.722, verdict=above paper-spacedock=0.577)
started: 2026-05-23T19:48:50Z
completed:
verdict:
score: 0.92
worktree:
issue:
pr:
mod-block:
---

## Problem

The just-archived `an goal1-rerun-dab-spacedock-opus47-xhigh` +
`d8 goal1-rerun-headline-per-query-recompute` sequence shipped a clean
goal-1 spacedock headline: pooled per-query pass@1 = `0.722 [0.591, 0.824]`
across 12 DAB datasets, verdict `above` paper's `spacedock=0.577` (CI
lower 0.591 > paper). Captain has asked for the equivalent run "without
spacedock" so the spacedock crew loop's contribution can be measured
against a paper-comparable direct baseline at the same model + effort
point (opus-4.7 + reasoning_effort=xhigh + batch + N=1).

This entity runs the existing 12 frozen direct-structured specs
(`examples/specs/goal1/direct-structured/*.yaml`) through the same
matrix dispatcher (`examples/drivers/dab-paper-matrix.sh`) and
captures a paper-comparable headline against the direct baseline
constant (`paper direct_baseline = 0.4376`, per
`dab-paper-matrix.sh:196`). No spacedock_solver wrapper; plain
`agent.kind: claude-cli` against DAB's `workspace_variant:
direct-structured` workspace README.

## Acceptance criteria

**AC-1 — Specs are post-sprint canonical and aligned with spacedock cell.**
The 12 direct-structured specs at
`examples/specs/goal1/direct-structured/*.yaml` carry `agent.kind:
claude-cli`, `agent.model: claude-opus-4-7`, `agent.reasoning_effort:
xhigh`, `benchmark.kind: harbor_dab`, `benchmark.dataset: dab@1.0`,
`benchmark.workspace_variant: direct-structured`,
`benchmark.query_mode: batch`, `trials: 1`. Already on disk from the
`an` cycle-1 regeneration (commit `a6ab344 regen: 36 dab paper matrix
specs with reasoning_effort: xhigh`).
Verified by: `grep -l 'workspace_variant: direct-structured'
examples/specs/goal1/direct-structured/*.yaml` returns all 12;
`grep -l 'reasoning_effort: xhigh' examples/specs/goal1/direct-structured/*.yaml`
returns all 12.

**AC-2 — Each spec freezes cleanly.**
`rk freeze` runs against each of the 12 spec files and produces
`spec.frozen.yaml` + `provenance.yaml` adjacent. No `SpecError` or
`AliasDriftError` raised.
Verified by: a shell loop runs `rk freeze` per spec and captures exit
codes; all 12 = 0; 12 frozen.yaml files appear on disk under
`examples/specs/goal1/direct-structured/*.frozen.yaml`.

**AC-3 — Full 12-cell run completes.**
`examples/drivers/dab-paper-matrix.sh --variants direct-structured
--max-cell-budget-usd 10.0 --continue-on-fail` executes against the
existing matrix root at
`/Users/clkao/git/razorback/_runs/goal1-direct-structured-opus47-xhigh/`
(or sibling); each cell produces a run-dir with `summary.json`,
`provenance.yaml`, per-trial `result.json` + `reward_per_query.json`,
and `score.json`. Failure of an individual cell does not block
subsequent cells. The verifier-fix from `d6fbfdd` is already in main,
so no `common_scaffold` ImportError gap.
Verified by: 12 run-dirs exist; their `summary.json` files are
parseable JSON; freeze CAS root contains the corresponding
`sealed_hash` subdirs; `dispatch-ledger.tsv` records `status: ok` for
all 12.

**AC-4 — Per-query headline emitted against paper direct baseline.**
The goal1 aggregator (post-`d8` re-wire, now consuming
`reduce_per_query_stratified`) runs against the matrix root and
prints a per-query pooled pass@1 + per-cell sub-table + Wilson CI +
verdict against `paper direct_baseline = 0.4376`. The captain-facing
report at
`docs/razorback-implementation/_evidence/goal1-direct-structured-dab-opus47-xhigh-report.md`
carries the headline + per-cell table + provenance block, mirroring
the shape of the spacedock report at
`docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md`.
Verified by: report exists at the cited path with the four sections;
verdict line names `direct_baseline=0.4376` and the
above/inside/below classification.

**AC-5 — Provenance artifacts pin the run.**
Every cell's `provenance.yaml` records `solver_workflow_content_hash`
(may be null/missing for `claude-cli` agent kind — that's
expected and the report's deviations section names it),
`harbor_agent_kwargs_hash`, the `reasoning_effort: xhigh` setting,
and the resolved opus-4.7 model version (`pin_model_version: true`).
A future re-run from the same spec reproduces the same `sealed_hash`
and discovers the existing freeze tree.
Verified by: per-cell `provenance.yaml` enumerated in the final
report; the four claude-cli-relevant fields present per cell;
sealed_hash stability noted.

## Test plan

- **Smoke (mechanism gate):** one cell (`bookreview`) cycles through
  `rk freeze` then `rk run` end-to-end against the existing
  `dab-agent:latest` image; confirm `claude-cli` agent kind exercises
  the direct-structured workspace README correctly and produces a
  non-empty `result.json`. If the agent fails to engage the DBs at
  all (e.g., the direct-structured README assumes a different DB
  access path than the dispatcher provides), surface to captain at
  impl-stage gate.
- **End-to-end smoke:** one cell (bookreview, N=1) completes with
  non-zero reward; record wallclock.
- **Full matrix:** all 12 cells sequentially per
  `concurrency.trials: 1`; collect `summary.json` each. Estimated
  wallclock 2-3 hours (paper-direct baseline runs are typically
  shorter than spacedock since no crew loop), cost ~$25-40 at the
  per-cell budget cap.
- **Aggregate:** captain-facing report against
  `direct_baseline=0.4376`. Per-query headline; per-cell
  binary+per-query columns; flagged divergences.

## Out of scope

- **N=5 paper-grade reproduction.** Sibling entity if/when captain
  wants paper-grade reproducibility; this entity stays at N=1.
- **direct-minimal variant.** Captain selected direct-structured; the
  minimal variant remains as a future sibling.
- **Same-workflow-README-but-no-crew-loop variant.** Interpretation #3
  from the captain question (use `dab_paper_matrix/README.md` against
  a plain `claude-cli` agent) was deferred. File if the
  direct-structured number motivates that A/B test.
- **Three-way comparison report.** Could be filed as a sibling
  entity if both `d8` (spacedock=0.722) and this entity's number
  warrant a single side-by-side narrative.
- **Cost telemetry fix.** Still a known follow-up; not in scope here.

## Depends on

- **`d8 goal1-rerun-headline-per-query-recompute`**: DONE / archived.
  The aggregator script `examples/drivers/aggregate-goal1-scores.py`
  is re-wired to consume the canonical reducer; this entity's
  recompute step inherits that fix.
- **`1s runs-aggregate-single-score-reducer`**: DONE / archived. The
  canonical reducer at `src/razorback/runs/aggregate.py` is what the
  aggregator consumes.
- **`an goal1-rerun-dab-spacedock-opus47-xhigh`**: DONE / archived.
  Established the matrix dispatcher pattern, the per-cell evidence
  mirroring pattern, the captain-facing report shape.

## Resume hook

When this lands, the captain has a head-to-head paper-comparable
spacedock-vs-direct-structured number at the same model + effort
point. If `spacedock=0.722` vs `direct-structured=X` shows a
meaningful gap, the spacedock crew loop earns its keep; if the gap
is small, the loop's overhead is questioned. Either result motivates
a sibling: deeper variant comparison (direct-minimal, same-README-
no-loop), or N=5 of whichever wins.
