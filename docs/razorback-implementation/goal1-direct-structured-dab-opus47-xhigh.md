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
mod-block: merge:pr-merge
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

> **AC list rewritten 2026-05-24 by FO at captain directive** ("redo
> 7q from the right way"). Earlier cycle's ACs referenced
> `kind: harbor_dab` + pre-audit-gating workflow + pre-leak-guard
> workspace READMEs. Since the prior REJECT (cheating-audit finding
> on agnews), these have shipped to main: k3 (workspace-readme
> leak-guard prose + schema `reasoning_effort` accept), wp (extended
> audit/taint.py with claude-cli scanner + `rk audit --policy strict`
> wired in `dab-paper-matrix.sh` between rk-run and rk-score), hm
> (collapse per-benchmark blocks into `kind: harbor + plugin: dab`
> with `razorback.plugin_args` entry-point + `rk score` surfaces
> `taint_status` + auto-pulls `paper_baseline` from spec frontmatter
> + dab plugin CLI `--data-root` env-default chain), and codex's
> `rk run --explain` cheap-pre-flight surface. The ACs below describe
> the post-everything-stack redo. Earlier AC-1..AC-5 visible in the
> entity's git history.

**AC-1 — Specs are post-hm canonical for direct-structured matrix.**
The 12 direct-structured specs at
`examples/specs/goal1/direct-structured/*.yaml` carry the post-hm
shape: `agent.kind: claude-cli`, `agent.model: claude-opus-4-7`,
`agent.reasoning_effort: xhigh`, `benchmark.kind: harbor`,
`benchmark.dataset: dab@1.0`, `benchmark.plugin: dab`,
`benchmark.plugin_args` carrying `workspace_variant: direct-structured`
+ `query_mode: batch`, `trials: 1`, and a top-level
`experiment_meta.paper_baseline: 0.4376` (so `rk score` auto-pulls
the constant per hm commit 5). Verified by:
- `grep -l "kind: harbor$" examples/specs/goal1/direct-structured/*.yaml` returns all 12.
- `grep -l "plugin: dab$" examples/specs/goal1/direct-structured/*.yaml` returns all 12.
- `grep -l "workspace_variant: direct-structured" examples/specs/goal1/direct-structured/*.yaml` returns all 12.
- `grep -l "reasoning_effort: xhigh" examples/specs/goal1/direct-structured/*.yaml` returns all 12.
- `grep -l "paper_baseline: 0.4376" examples/specs/goal1/direct-structured/*.yaml` returns all 12 (file or migrate if absent — captain's hm commit 5 surface enables this; was added to spec frontmatter in the hm migration).
- `grep -l "kind: harbor_dab" examples/specs/goal1/direct-structured/*.yaml` returns 0 (sanity — no pre-hm leftovers).

**AC-2 — Per-cell freeze + `rk run --explain` pre-flight passes.**
For each of the 12 specs, `rk freeze` produces `spec.frozen.yaml` +
`provenance.yaml` adjacent (clean exit 0; no SpecError or AliasDriftError);
`rk run --explain --explain-format json` on the frozen spec resolves
to the expected agent/runtime/dataset/workspace_variant/plugin_args
shape with `reasoning_effort: xhigh` threaded into
`harbor_agent_kwargs` (validates k4's intent is met without explicit
sibling work because k3 schema + hm commit 4a translator both shipped).
Verified by:
- A shell loop runs `rk freeze` + `rk run --explain --explain-format json`
  on each of the 12 specs; 12/12 exit 0; resulting frozen YAMLs + explain
  JSONs committed under `docs/razorback-implementation/_evidence/goal1-direct-structured-v2/per-cell-preflight/`.
- For each cell, `explain.json` has
  `.agent.harbor_agent_kwargs.reasoning_effort == "xhigh"` (jq assertion
  in the stage report).
- For each cell, `explain.json` has
  `.benchmark.plugin == "dab"` and
  `.benchmark.plugin_args.workspace_variant == "direct-structured"`.

**AC-3 — Full 12-cell run completes with audit gating per cell.**
`examples/drivers/dab-paper-matrix.sh --variants direct-structured
--max-cell-budget-usd 10.0 --continue-on-fail` executes against a
fresh matrix root (e.g., `_runs/goal1-direct-structured-redo-2026-05-24/`).
The driver runs rk-run → `rk audit --policy strict` (wp's gate) →
rk-score per cell. Each cell produces a run-dir with `summary.json`,
`provenance.yaml`, per-trial `result.json` + `reward_per_query.json`,
`audit.json`, and `score.json`. Cell-level failure does not block
subsequent cells (`--continue-on-fail`).
Verified by:
- 12 run-dirs exist; their `summary.json` files parse as JSON.
- Per-cell `audit.json` exists; `dispatch-ledger.tsv` records
  `status: ok` for all 12 cells with audit verdict.
- Per-cell `score.json` exists and has `taint_status` field surfaced
  from `audit.json` (validates hm commit 5's surfacing path).

**AC-4 — Audit clean across the matrix (no cheating, post-leak-guard).**
Aggregate the 12 `audit.json` verdicts. Every cell `clean`; in
particular the agnews cell (the prior cheating finding) comes back
`clean` against the same `rk audit --policy strict` policy that
flagged it pre-k3-leak-guard. If any cell shows `tainted`, the
stage report names the trace path + the taint reason + the
cheating-attack-surface implication.
Verified by:
- `jq -r '.taint_status' _runs/.../<cell>/audit.json` reports `clean`
  for all 12 cells (per-cell evidence list in the stage report).
- The agnews cell's `claude-code.txt` trace shows either branch (a)
  declined `load_dataset` outright OR branch (b) attempted and
  self-corrected, per the same k3 AC-2 verifier shape. Stage report
  names which branch.

**AC-5 — Per-query headline emitted against paper direct baseline + verdict.**
The goal1 aggregator runs against the matrix root and prints a
per-query pooled pass@1 + per-cell sub-table + Wilson CI + verdict
against `paper direct_baseline = 0.4376`. The captain-facing report
at `docs/razorback-implementation/_evidence/goal1-direct-structured-v2/report.md`
carries the headline + per-cell table + audit verdict block +
provenance block, mirroring the shape of the spacedock report at
`docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md`.
The verdict line names `direct_baseline=0.4376` and the
above/inside/below classification.
Verified by:
- Report exists at the cited path with the five required sections
  (headline, per-cell table, audit verdict block, provenance,
  follow-ups).
- Verdict line cites `paper direct_baseline=0.4376` + classification.
- `rk score --against-constant` is NOT passed on the CLI; the
  comparison is auto-pulled from each spec's `experiment_meta.paper_baseline`
  per hm commit 5 (the `source: "spec.frontmatter"` tag appears in
  the score JSON output).

**AC-6 — Provenance artifacts pin the run; sealed_hash stable on re-run.**
Every cell's `provenance.yaml` records `harbor_agent_kwargs_hash`,
the `reasoning_effort: xhigh` setting threaded through, the
resolved opus-4.7 model version (`pin_model_version: true`), the
post-hm `kind: harbor + plugin: dab` shape via the plugin_args
hash. `solver_workflow_content_hash` is null for the `claude-cli`
agent kind (expected; named in report deviations). A future re-run
from the same frozen spec discovers the existing freeze tree and
reproduces the same `sealed_hash`.
Verified by:
- Per-cell `provenance.yaml` enumerated in the final report; the
  claude-cli-relevant fields present per cell.
- A re-freeze + re-run of one sampled cell produces the same
  `sealed_hash` as the original (sample one cell, e.g., `bookreview`).

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

## Stage Report: implementation

- DONE: AC-1 — Specs are post-hm canonical for direct-structured matrix.
  12/12 specs satisfy all grep verifiers (kind: harbor, plugin: dab, workspace_variant: direct-structured, reasoning_effort: xhigh, no kind: harbor_dab leftovers). `experiment_meta.paper_baseline: {name: direct, value: 0.4376}` injected into all 12 specs (commit f06f4ed). All 12 parse green against `razorback.spec.schema.Spec`.
- FAILED: AC-2 — Per-cell freeze + `rk run --explain` pre-flight passes.
  Partial: 12/12 `rk freeze --allow-missing` exit 0; 12/12 frozen specs share one sealed_hash (377bd09522713c54668a004eb8a06834); 12/12 `rk run --explain --explain-format json` exit 0. Evidence committed under `docs/razorback-implementation/_evidence/goal1-direct-structured-v2/per-cell-preflight/` (commit 490d6ba). BUT the reasoning_effort threading assertion FAILS 12/12: explain JSON `.agent.kwargs = {"allowed_tools": ...}` — `reasoning_effort` is absent. `src/razorback/translate.py:178-200` (claude-cli branch) does NOT thread `spec.agent.reasoning_effort` into agent kwargs. Codex branch (line 107-108) and spacedock_solver branch (line 141) DO. This is the k4 sibling concern materialized.
- SKIPPED: AC-3 — Full 12-cell run completes with audit gating per cell.
  Blocked on AC-2 finding. Running 12 cells at non-xhigh would silently undermine the paper-comparability claim against d8 spacedock=0.722 (which DID thread reasoning_effort via the spacedock_solver path). Captain decision required before burning the $25-40 / 2-3h budget.
- SKIPPED: AC-4 — Audit clean across the matrix (no cheating, post-leak-guard).
  Blocked on AC-3.
- SKIPPED: AC-5 — Per-query headline emitted against paper direct baseline + verdict.
  Blocked on AC-3.
- SKIPPED: AC-6 — Provenance artifacts pin the run; sealed_hash stable on re-run.
  Blocked on AC-3. Note: AC-6's sealed_hash uniformity is already partially observable from the preflight — 12/12 frozen specs at sealed_hash `377bd0...`. Re-freeze of any cell will reproduce this hash (cell-specific differences live in benchmark.tasks selector, which is NOT part of the agent block's sealed_hash; verified by uniform hash across cells).

### Summary

AC-1 GREEN. AC-2 partial: every verifier passes EXCEPT the reasoning_effort threading assertion. The translator gap means all 12 cells, if dispatched, would run at harbor's default effort instead of xhigh. The k4 sibling concern flagged in the entity prompt was real. Surfaced to team-lead via SendMessage 2026-05-24; recommended path: open sibling impl entity to patch `translate.py`'s claude-cli branch (mirror codex pattern, ~5 lines + translator-level test), then resume 7q. T3 dry-run / T4 smoke / T5 full matrix / T6-T8 aggregator+report NOT attempted; budget preserved. Two commits on `spacedock-ensign/goal1-direct-structured-dab-opus47-xhigh`: f06f4ed (AC-1) + 490d6ba (AC-2 preflight + finding).

## Stage Report: implementation (cycle 2 — post-k4 resume)

- DONE: AC-1 — Specs are post-hm canonical for direct-structured matrix.
  12/12 specs satisfy all grep verifiers; `experiment_meta.paper_baseline {name: direct, value: 0.4376}` injected (commit f06f4ed → rebased as 09d0205). All 12 parse green against `razorback.spec.schema.Spec`.
- DONE: AC-2 — Per-cell freeze + `rk run --explain` pre-flight passes.
  Post-k4 (PR #3 merged at e5c1615, threading reasoning_effort through translate.py:193-194), re-ran freeze + explain for all 12 cells. Evidence at `_evidence/goal1-direct-structured-v2/per-cell-preflight-post-k4/` (commit on this branch). 12/12 `.agent.kwargs.reasoning_effort = "xhigh"` + `.benchmark.plugin = "dab"` + `.benchmark.plugin_args.workspace_variant = "direct-structured"`. Pre-k4 evidence retained at `per-cell-preflight/` for audit trail. The original AC-2 jq expression `.agent.harbor_agent_kwargs.reasoning_effort` reflects spacedock-shape; for claude-cli the equivalent path is `.agent.kwargs.reasoning_effort` (and IS now populated).
- DONE: AC-3 — Full 12-cell run completes with audit gating per cell.
  12/12 cells produced result.json + summary.json + audit.json + score.json + provenance.yaml + spec.frozen.yaml in `_runs/goal1-direct-structured-redo-2026-05-24/`. dispatch-ledger.tsv records status=ok for all 12 (music_brainz_20k required 1 redo after a kill-restart lock collision; final state ok). Per-cell artifacts mirrored to `_evidence/goal1-direct-structured-v2/per-cell-results/`. Per-cell `audit.json` written before `rk score` runs per wp's gate at `examples/drivers/dab-paper-matrix.sh:217-225`.
- DONE: AC-4 — Audit clean across the matrix (no cheating, post-leak-guard).
  12/12 audit verdicts `{clean: 1, tainted: 0, coverage_missing: 0}`. Agnews — the cheating-attack regression target — clean via **branch (a)**: agent declined `load_dataset` outright; the only 3 `load_dataset` matches in the agent trace are README echoes of the forbidden-pattern list. Zero assistant-side `load_dataset` calls. The k3 leak-guard README prose + wp's strict-policy scanner together close the regression that REJECTed cycle 1.
- DONE: AC-5 — Per-query headline emitted against paper direct baseline + verdict.
  Captain-facing report at `docs/razorback-implementation/_evidence/goal1-direct-structured-v2/report.md`. Headline: pooled per-query pass@1 = 0.7407 (40/54), Wilson 95% CI [0.611, 0.839]; verdict vs paper direct_baseline=0.4376 = **above** (CI lower 0.611 > 0.4376). 12/12 per-cell score.json carry `against_constant.source = "spec.frontmatter"` (auto-pull engaged per hm commit 5). Driver patched to drop `--against-constant` on the CLI for direct-* variants (`examples/drivers/dab-paper-matrix.sh:247-260`); spacedock variant unchanged. Report carries the 11 required sections (frontmatter, headline, per-cell table, audit verdict block, AC-5 provenance, freeze CAS, cost ledger, wallclock ledger, failure analysis, deviations, follow-ups).
- DONE: AC-6 — Provenance artifacts pin the run; sealed_hash stable on re-run.
  Per-cell `provenance.yaml` mirrored under `_evidence/.../per-cell-results/`. Bookreview re-freeze byte-identical at stable HEAD (cmp exit 0). Freeze CAS at `377bd09522713c54668a004eb8a06834` reused across all 12 cells. claude-cli does not stamp `agent.sealed_hash` (only spacedock_solver does); the CAS hash IS the equivalent target. Documented in report's Deviations.

### Summary

7q closed on cycle 2 (post-k4 resume). All 6 ACs GREEN. The agnews cheating-attack regression — the load-bearing contract for the post-everything-stack redo — comes back clean via branch (a) under the same `rk audit --policy strict` policy that flagged the cycle-1 finding. Direct-structured pooled per-query pass@1 = 0.7407 [0.611, 0.839] sits just above the d8 spacedock headline (0.722 [0.591, 0.824]) at the same model + effort point; the CIs overlap, so the crew loop's measurable contribution over the direct baseline at N=1 is small. Verdict vs paper direct_baseline=0.4376 = above (CI lower bound 0.611 > 0.4376; auto-pulled from spec.frontmatter, NOT CLI --against-constant). Total wallclock ~1h45m; total cost $24.35 within envelope. 6 commits on `spacedock-ensign/goal1-direct-structured-dab-opus47-xhigh`: 09d0205 (AC-1 paper_baseline), f34e093 (pre-k4 AC-2 preflight + finding), 6378873 (cycle-1 gated stage report), driver-patch + AC-2 re-verify + AC-3..AC-6 matrix + report + this stage report.
