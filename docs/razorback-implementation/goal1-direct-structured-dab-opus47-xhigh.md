---
id: 7qwenbebdvmqj3gd7xxdpytd
title: Goal 1 sibling — DAB direct-structured matrix, opus-4.7, reasoning_effort=xhigh, batch, parallel=1
status: validation
source: Captain directive 2026-05-23 — "run an equivalent of this (same workflow readme) but without spacedock" — paper-comparable direct-baseline run alongside the just-archived `d8 goal1-rerun-headline-per-query-recompute` (spacedock pooled per-query=0.722, verdict=above paper-spacedock=0.577)
started: 2026-05-23T19:48:50Z
completed:
verdict:
score: 0.92
worktree: .worktrees/spacedock-ensign-goal1-direct-structured-dab-opus47-xhigh
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

## Stage Report: plan

- DONE: Apply plan-output flex rule. 5 ACs but operationally simple — freeze + matrix dispatch + aggregate + report. Recommend separate plan doc at `docs/razorback-implementation/plans/goal1-direct-structured-dab-opus47-xhigh.md` mirroring the shape of the archived `an` plan, since AC count is at the threshold and the per-cell wallclock budget warrants explicit task sequencing + risk register.
  Wrote separate plan doc at `docs/razorback-implementation/plans/goal1-direct-structured-dab-opus47-xhigh.md` mirroring `plans/goal1-rerun-dab-spacedock-opus47-xhigh.md` (AC↔task map, surface map, tasks T1–T8, risk register, definition of done). AC count = 5 + 2–3h wallclock + matrix dispatch shape met the "standard — separate doc" threshold per README §`plan` "Plan output scope".
- DONE: Mechanism validation — confirm the direct-structured workspace README actually exists at the path harbor_dab expects and that the agent's `kind: claude-cli` (no spacedock_solver wrapper) is wired to the right docker invocation path. Read `src/razorback/benchmarks/dab/` (or equivalent) for the `workspace_variant: direct-structured` handler; trace it to the actual workspace README that gets dropped into the agent container. Compare to spacedock's wiring (which we know works from `d8`'s 12/12). If the direct-structured path is unfamiliar or untested in current razorback, surface as a Task 0 mechanism-smoke gate (bookreview cell only, validate end-to-end before the full matrix). If it's a well-trodden path, plain Task 1 freeze + Task 2 matrix is enough.
  Static-source trace performed (5 source-file checkpoints, captured in the plan's "Mechanism check — DONE in plan stage" section): `WORKSPACE_VARIANTS` declares `direct-structured` (`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py:7`); green template test (`tests/unit/test_workspace_readme_variants.py:test_direct_structured_has_layout_block`); dispatcher threads variant directly (`src/razorback/translate.py:381`); spec shape on disk matches AC-1 at commit `a6ab344`; matrix driver supports `--variants direct-structured` natively (`dab-paper-matrix.sh:14, 29, 196`). Path is well-trodden BUT the entity's caution (first goal1 paper-comparable matrix at opus-4.7+xhigh for this combo) is honored by adding T4 (bookreview smoke) as a runtime mechanism-gate before T5 burns 2–3 hours.
- DONE: Sequence the riskiest contract first per CLAUDE.md mechanism-validation rule. Whichever path the answer to item 2 takes, name it explicitly in the plan. Then enumerate the matrix-dispatch shape (out-dir, freeze-dir, dispatcher invocation), the aggregator command, and the report-rewrite diff scope. The captain-facing report at `_evidence/goal1-direct-structured-dab-opus47-xhigh-report.md` mirrors the spacedock one's shape; the aggregator already emits both binary + per-query numbers post-d8.
  Riskiest-contract sequencing named explicitly: T4 (bookreview smoke, 5–10 min, end-to-end) precedes T5 (full 12-cell, 2–3h). Matrix-dispatch shape enumerated in T5 with full env, flags, per-cell + matrix-wide artifact paths. Aggregator flags verified by reading `aggregate-goal1-scores.py:218-228` — uses `--matrix-root` + `--out-dir` (not `--runs-root` + `--variants`), corrected in plan T7. Captain-facing report shape enumerated in T8 as 11 sections mirroring `_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md` (frontmatter, headline, per-dataset table with binary+per-query columns, AC-5 provenance enumeration, freeze CAS check, cost ledger, wallclock ledger, failure analysis, deviations, provenance, artifact retention, follow-ups).

### Summary

Wrote `plans/goal1-direct-structured-dab-opus47-xhigh.md` as a standard separate-doc plan mirroring the archived `an` plan's shape (AC↔task map, surface map, tasks T1–T8, risk register, definition of done). Mechanism-validation done at the source level (5 trace points) — `direct-structured` workspace_variant is a first-class, tested path; the matrix dispatcher routes it without special-casing; specs at commit `a6ab344` already satisfy AC-1 at `reasoning_effort: xhigh` so no regen is needed. Implementation stage starts at freeze (T2). T4 (bookreview-cell smoke) is the runtime mechanism gate that catches any direct-structured-vs-claude-cli DB-access or workspace-README mismatch BEFORE the full 12-cell dispatch burns 2–3 hours; the plan explicitly names the hard-blocker conditions that escalate to captain at impl-stage gate rather than silently widening scope. Plan inherits the spacedock report's captain-approved deviations (`_runs/` runs-dir, `DATAAGENTBENCH_DATA_ROOT` env, null `cost_usd`, null `solver_workflow_hash` for `claude-cli` kind) and pre-flags them in T8's deviations section.
