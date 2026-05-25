---
id: an4czz3smccy5adazak2hr4y
title: Goal 1 — DAB direct-minimal matrix, opus-4.7, reasoning_effort=xhigh, batch, parallel=1 (SUPERSEDED)
status: implementation
source: SUPERSEDED 2026-05-25 — rolled into nested research project `_research/dab-goal1/` per captain decision; the direct-minimal-template-fix work continues as `_research/dab-goal1/hypotheses/direct-minimal-template-includes-db-access.md` (id `jvnr6hyx66wk99n72x7nszxn`). Original `an` matrix produced stratified=0.4279 vs paper direct_baseline=0.4376 (verdict `matches`), but captain identified the result as a workspace-setup failure (not paper-canonical): razorback's `_DIRECT_MINIMAL` template omits the `## Database access` section, so the agent could not connect to the DBs without trial-and-error discovery. The new hypothesis fixes the template + re-runs. Historical evidence preserved under `docs/razorback-implementation/_evidence/` and the still-mounted `.worktrees/spacedock-ensign-goal1-direct-minimal-dab-opus47-xhigh/_runs/` (until worktree teardown). This razorback-implementation entity becomes a stub pointer; no further work happens here.
score: 0.85
auto-approve: false
worktree: .worktrees/spacedock-ensign-goal1-direct-minimal-dab-opus47-xhigh
issue:
pr:
mod-block:
started:
completed:
verdict:
---

> **STUB — work continues at `_research/dab-goal1/hypotheses/direct-minimal-template-includes-db-access.md`.**
>
> This entity is being terminalized with `verdict: SUPERSEDED` once captain
> acks the move. The razorback-implementation workflow no longer drives
> direct-minimal-template-fix work; the nested research project at
> `_research/dab-goal1/` (instantiating phase5's experiment-workflow + research-project
> templates per captain decision 2026-05-25) is the canonical home.

## Problem

Goal 1's crew-loop study has two comparison points so far at
opus-4.7 + reasoning_effort=xhigh + batch + N=1:

- **spacedock**: stratified-per-query pass@1 = 0.7055 (d8 archive,
  pre-leak-guard but score genuine per captain audit probe 2026-05-25)
- **direct-structured**: stratified-per-query pass@1 = 0.6719 (7q
  post-redo on post-everything stack)

The direct-minimal variant is the third workspace_variant razorback
ships (per `packages/razorback-plugin-dab/src/razorback_plugin_dab/
generate/workspace_readme.py`'s `_DIRECT_MINIMAL` template — the
shortest variant, task statement + workspace layout only, no
procedure prompt). Filing it as a sibling closes the three-way:

- spacedock = crew-loop with first-officer + ensign dispatch
- direct-structured = bare claude-cli + procedure prompt (`## Use the
  database. ## Verify your answer.` etc.)
- direct-minimal = bare claude-cli + task statement only

Reading the three-way: does the procedure prompt in direct-structured
provide measurable lift over direct-minimal? Does the spacedock crew
loop provide measurable lift over either direct variant? At N=1 the
per-stratum CI machinery is degenerate; the three numbers are point
estimates whose ordering is the research signal.

## Acceptance criteria

**AC-1 — Specs are post-hm canonical for direct-minimal matrix.**
The 12 direct-minimal specs at
`examples/specs/goal1/direct-minimal/*.yaml` carry the post-hm shape:
`agent.kind: claude-cli`, `agent.model: claude-opus-4-7`,
`agent.reasoning_effort: xhigh`, `benchmark.kind: harbor`,
`benchmark.dataset: dab@1.0`, `benchmark.plugin: dab`,
`benchmark.plugin_args` carrying `workspace_variant: direct-minimal`
+ `query_mode: batch`, `trials: 1`, and top-level
`experiment_meta.paper_baseline: 0.4376` (same paper direct_baseline
as direct-structured per DAB paper's reporting — paper does not break
out a separate direct-minimal baseline; the comparison point is the
same).
Verified by:
- `grep -l "workspace_variant: direct-minimal" examples/specs/goal1/direct-minimal/*.yaml` returns all 12.
- `grep -l "reasoning_effort: xhigh" examples/specs/goal1/direct-minimal/*.yaml` returns all 12.
- `grep -l "paper_baseline" examples/specs/goal1/direct-minimal/*.yaml` returns all 12 (file or migrate if absent).
- `grep -l "kind: harbor_dab" examples/specs/goal1/direct-minimal/*.yaml` returns 0.

**AC-2 — Per-cell freeze + `rk run --explain` pre-flight passes.**
For each of the 12 specs, `rk freeze` produces `spec.frozen.yaml`
+ `provenance.yaml` (clean exit 0); `rk run --explain --explain-format json`
on the frozen spec resolves to expected shape with
`reasoning_effort: xhigh` threaded into the resolved kwargs
(per k4's post-merge translator behavior).
Verified by:
- Shell loop runs both commands on all 12 specs; 12/12 exit 0; explain JSONs committed under `docs/razorback-implementation/_evidence/goal1-direct-minimal-v1/per-cell-preflight/`.
- For each cell, `explain.json` has `.agent.kwargs.reasoning_effort == "xhigh"` (jq assertion; verify dotted path empirically on first invocation).
- For each cell, `explain.json` shows `.benchmark.plugin == "dab"` and `.benchmark.plugin_args.workspace_variant == "direct-minimal"`.

**AC-3 — Full 12-cell run completes with audit gating per cell.**
`examples/drivers/dab-paper-matrix.sh --variants direct-minimal
--max-cell-budget-usd 10.0 --continue-on-fail` executes against a
fresh matrix root `_runs/goal1-direct-minimal-2026-MM-DD/`. The
driver runs rk-run → `rk audit --policy strict` → rk-score per cell.
Each cell produces `summary.json`, `provenance.yaml`, per-trial
`result.json` + `reward_per_query.json`, `audit.json`, and `score.json`.
Cell-level failure does not block subsequent cells.
Verified by: 12 run-dirs exist; their `summary.json` files parse;
per-cell `audit.json` exists; `dispatch-ledger.tsv` records every cell.

**AC-4 — Audit clean across the matrix.**
Aggregate the 12 `audit.json` verdicts. Every cell `clean` against
`rk audit --policy strict`. If `gv audit-scanner-subagent-jsonl-coverage`
has shipped by dispatch time, run the subagent-aware audit too; if
not, document the limitation in the stage report. AGNEWS is the
historical cheating-attack cell — special attention to its trace +
branch-(a)-vs-(b) naming.
Verified by:
- `jq -r '.taint_status' _runs/.../<cell>/audit.json` reports `clean` for all 12 cells.
- AGNEWS trace shows either branch (a) declined `load_dataset` outright OR branch (b) attempted-and-self-corrected, per the k3-established verifier shape.

**AC-5 — Per-query (stratified) headline emitted against paper direct baseline.**
The goal1 aggregator produces a stratified-per-query headline
(per_query_pass_at_1_mean_over_strata) for the 12 direct-minimal
cells, with per-cell sub-table.
A captain-facing report at
`docs/razorback-implementation/_evidence/goal1-direct-minimal-v1/report.md`
leads with the stratified-per-query number against
`paper direct_baseline=0.4376` (auto-pulled from spec frontmatter
via hm commit 5; NOT CLI --against-constant). Three-way comparison
table includes the d8 spacedock + 7q direct-structured stratified
numbers for the captain-relevant research signal.
Verified by:
- Report exists at the cited path with the headline + per-cell table + audit verdict block + provenance + three-way comparison.
- Verdict line cites stratified number vs paper direct_baseline.
- Aggregator's `per_query_verdict` field source = "spec.frontmatter" per 12/12 score.json files.

**AC-6 — Provenance pins the run; sealed_hash stable on sampled re-freeze.**
Per-cell `provenance.yaml` records `harbor_agent_kwargs_hash`, the
`reasoning_effort: xhigh` setting threaded through, the resolved
opus-4.7 model version, and the post-hm `kind: harbor + plugin: dab`
shape via plugin_args hash. `solver_workflow_content_hash` is null
for claude-cli (expected). A sampled re-freeze of one cell
(bookreview) produces the same sealed_hash.

## Test plan

- **Smoke first:** T0 mechanism check — `rk freeze` on bookreview direct-minimal spec succeeds; `rk run` smoke on bookreview confirms end-to-end exit. ~15-30 min, ~$0.50-2.
- **Full matrix:** sequential 12 cells per `concurrency.trials: 1`. ~2-3h wallclock, ~$25-40 cost envelope at $10/cell budget cap.
- **Audit + score gating** per the driver's per-cell rk-audit + rk-score sandwich.
- **Aggregator:** captain-facing report mirrors 7q's report shape; lead with stratified-per-query.

## Out of scope

- **N=5 paper-grade reproduction.** Same scope discipline as 7q — N=1 keeps cost in envelope.
- **Three-way pairwise CI machinery.** At N=1 there's no per-stratum CI; bootstrapping CIs for the three-way comparison is a separate methodology entity if captain wants statistical significance claims.
- **direct-structured rerun.** 7q just shipped; reusing 7q's number for the three-way is correct.
- **spacedock rerun.** d8 archived; reusing d8's stratified number is correct (today's audit probe confirms the score is genuine despite the audit-coverage gap).
- **Same-workflow-README-but-no-crew-loop variant.** Interpretation #3 from earlier captain question; not in scope.

## Depends on

- **k4 `translate-reasoning-effort-thread-through-claude-cli`**: DONE / archived. The translator now threads `reasoning_effort` on the claude-cli path; direct-minimal would silently run at default effort without k4 (same regression class that 7q's STOP-and-surface caught).
- **hm `generic-harbor-benchmark-surface-design`**: DONE / archived. Post-hm dispatch shape is what AC-1 verifies.
- **k3 `dab-workspace-readme-leak-guard-prose-port`**: DONE / archived. Leak-guard prose lands in the direct-minimal workspace README per k3's port to all 3 variants (the `_DIRECT_MINIMAL` template gained `## Rules` section per k3).
- **wp `dab-verify-stage-external-oracle-audit`**: DONE / archived. `rk audit --policy strict` gate at AC-3.
- **Aware-of:** `gv audit-scanner-subagent-jsonl-coverage` (backlog). If shipped before this entity's matrix burn, the audit verdict here gets subagent-JSONL coverage automatically. If not, document the limitation — direct-minimal is claude-cli single-session (no subagent dispatch), so the coverage gap doesn't affect this entity's audit verdict anyway.

## Resume hook

When this lands, the three-way comparison is complete:

| Variant | Stratified pass@1 | Paper baseline | Verdict |
|--|--|--|--|
| spacedock (d8) | 0.7055 | 0.577 | above |
| direct-structured (7q) | 0.6719 | 0.4376 | above |
| **direct-minimal (this entity)** | **?** | 0.4376 | ? |

The three-way's research interpretation: does the procedure prompt
in direct-structured provide measurable lift over direct-minimal?
Does the spacedock crew loop provide measurable lift over either?
At N=1 the three numbers are point estimates; CI machinery for
significance claims is a separate methodology question.

`auto-approve: false` because this is paper-comparable research
output — captain ack at every gate.

## Stage Report: plan

- DONE: Plan-output flex: 6 ACs but operationally simple (12-cell matrix dispatch + aggregate report) — recommend separate plan doc at `docs/razorback-implementation/plans/goal1-direct-minimal-dab-opus47-xhigh.md` mirroring 7q's plan shape. Cite 7q's archived plan as the structural template.
  Separate plan doc written at `docs/razorback-implementation/plans/goal1-direct-minimal-dab-opus47-xhigh.md`. Structural template explicitly cited as 7q's `docs/razorback-implementation/plans/goal1-direct-structured-dab-opus47-xhigh.md`; AC↔task map, surface map, mechanism-check, risk register, and definition-of-done sections all mirror 7q's shape, adapted for direct-minimal.
- DONE: Mechanism validation: confirm direct-minimal workspace_variant is a first-class path. The `_DIRECT_MINIMAL` template at `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py` declares the variant; k3 added leak-guard prose to it (verify the post-k3 file content). The matrix dispatcher supports `--variants direct-minimal` natively. Specs at `examples/specs/goal1/direct-minimal/*.yaml` should exist from hm commit 3's migration of 56 specs; if absent, file-gen task in plan.
  Static-trace mechanism check done in plan stage (plan §"Mechanism check"): WORKSPACE_VARIANTS tuple includes `direct-minimal` at `workspace_readme.py:7`; `_DIRECT_MINIMAL` template at `:10-30` carries k3's `## Rules` leak-guard block (HuggingFace/web/oracle forbidden); 12 specs already present at `examples/specs/goal1/direct-minimal/*.yaml` at post-hm shape (`kind: harbor + plugin: dab + plugin_args.workspace_variant: direct-minimal`, verified via grep counts = 12/12 for all sub-clauses except paper_baseline = 0/12). Matrix driver hard-codes `direct-minimal` at `dab-paper-matrix.sh:14,29,257`. Aggregator hard-codes `direct-minimal → ("direct_baseline", 0.4376)` at `aggregate-goal1-scores.py:26`. `rk score` auto-pulls `experiment_meta.paper_baseline` from frozen-spec frontmatter at `src/razorback/cli/score.py:40-65`. The ONE gap is the missing `experiment_meta.paper_baseline` block in the 12 source specs (hm commit 3 predated 7q's commit `de9cfba` paper_baseline injection); plan T2 is a targeted yaml edit mirroring 7q exactly. Generator at `examples/drivers/generate-dab-paper-matrix-specs.py` is stale (still emits legacy `kind: harbor_dab`, no paper_baseline injection) — plan explicitly forbids running it.
- DONE: Task sequence T0 (mechanism smoke) → T1 freeze + preflight → T2 bookreview smoke → T3 full 12-cell burn → T4 audit aggregate → T5 score + captain-facing report. Riskiest contract first per CLAUDE.md.
  Plan task sequence: T1 verify-shape → T2 inject paper_baseline (+ commit) → T3 freeze 12 specs → T4 `rk run --explain` preflight (12/12 + commit) → T5 bookreview mechanism-smoke gate (T0 equivalent — the smallest end-to-end exercise of the riskiest contract: minimal-README + claude-cli + DAB) → T6 full 12-cell dispatch (`--continue-on-fail`, $10/cell cap, background) → T7 per-cell artifact verification → T8 audit verdict aggregation (AC-4 + AGNEWS classification + gv coverage-gap note) → T9 captain-facing aggregator → T10 captain-facing report (STRATIFIED-PER-QUERY headline only, three-way table with d8=0.7055 + 7q=0.6719 verbatim). T5 is the riskiest-contract-first gate per CLAUDE.md's "validating new mechanisms" rule; T4 is the static-side counterpart that catches k4-class regressions before T5 spends API tokens.

### Summary

Plan stage produced `docs/razorback-implementation/plans/goal1-direct-minimal-dab-opus47-xhigh.md` — a 10-task separate plan doc mirroring 7q's direct-structured shape. The plan is a research-RUN plan, not a code-change plan: no Python source is modified; the one spec-data change is injecting `experiment_meta.paper_baseline: {name: direct, value: 0.4376}` into all 12 source specs (T2), which 7q did to direct-structured at commit `de9cfba` but the hm migration that touched direct-minimal at `40ed8a2` predated. Mechanism check confirms `direct-minimal` is a first-class path end-to-end (variant tuple → README template with k3 leak-guard → matrix driver → score auto-pull → aggregator hard-code → audit scanner); the riskiest contract for runtime validation is the **minimal** workspace README (shortest variant — agent gets only task statement + answer-file contract + leak-guard rules), gated by T5's bookreview smoke before T6 burns 2–3h on the full 12 cells. Captain standing directive (STRATIFIED ONLY in headline) is named explicitly in the plan's guardrails and in T10's report-shape.
