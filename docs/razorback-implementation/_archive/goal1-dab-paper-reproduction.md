---
id: ayf9mczntgnp808z8ggpjzf4
title: Goal 1 — DAB paper reproduction (opus-4.7 + hints × 3 variants × 12 datasets × N=5)
status: done
source: handoff "Two named research goals" + reconciliation plan Phase 4a end note
started: 2026-05-20T16:33:40Z
completed: 2026-05-21T06:01:51Z
verdict: PARTIAL
score: 0.65
worktree: 
issue:
pr:
mod-block:
archived: 2026-05-21T06:01:51Z
---

## Problem

Goal 1 reproduces the dataagentbench paper's headline result. The
matrix shape: opus-4.7 + hints ON × three workspace-README variants
(`direct-minimal`, `direct-structured`, `spacedock`) × 12 DAB
datasets × N=5 = 180 cells. Total estimated cost: ~$300-500.

The dispatch shape is captain-driven, no spacedock workflow needed
at this stage: `for spec in matrix: rk freeze; rk run
--max-budget-usd-running budget.json; rk score --against-constant
stratified_pass_at_1=0.577; rk audit --policy strict`. The matrix
dispatcher script lives at `examples/drivers/dab-paper-matrix.sh`
per AC-4a.12. Failure-recovery and partial-resume semantics are
scripted (idempotent re-dispatch on `rk run`'s
`(jobs_dir, job_name)` content-hash determinism). The
comparison against the paper's published 0.577 (spacedock) /
0.4376 (direct-baseline) is via `rk score --against-constant`'s
inside-CI / outside-CI verdict per stratum.

Goal 1 ships only after Phase 4a is complete — every surface
(`rk freeze` extended, `rk run` budget gate, `rk score`
against-constant + Wilson CIs, `rk audit` Layer 3 leak guard,
`tools_denied` PreToolUse hooks via the v2 agent) must exist and
be smoke-validated before $300-500 burns.

## Acceptance criteria

**AC-1 — Matrix dispatcher script exists and is idempotent.**
`examples/drivers/dab-paper-matrix.sh` (or equivalent Python
driver) iterates the 180-cell matrix, dispatching each cell as
`rk freeze + rk run --max-budget-usd-running + rk score
--against-constant + rk audit --policy strict`. Re-running the
driver after a partial failure skips already-completed cells.
Verified by: dry-run mode prints the 180-cell plan without
dispatching; a partial run + re-dispatch produces the same final
state as a single fresh dispatch. Per plan AC-4a.12.

**AC-2 — Each cell's spec is frozen with v2 sealed inputs.**
Per-cell `provenance.yaml` includes `solver_workflow_hash`,
`spacedock_skill_version`, `harbor_agent_kwargs_hash`, model alias
resolved, image digest, agent CLI binary hash, prompt content
hashes, harbor version, and `tools_denied` populated with DAB's
full DISALLOWED_TOOLS list.
Verified by: a sampled cell's `provenance.yaml` parses against the
v2 schema and carries the named fields. Per plan AC-4a.4 +
AC-4a.11.

**AC-3 — Budget gate enforced across the matrix.**
The dispatcher passes a single `budget.json` to every `rk run`
invocation. If the cumulative cost would exceed the matrix's
declared `experiment.max_budget_usd` (e.g., $500), the offending
cell refuses with `BudgetExceededError` (exit 22). The dispatcher
surfaces the refusal and pauses for captain decision.
Verified by: fixture test simulates a matrix-level budget overage
mid-dispatch and asserts the dispatcher's pause behavior. Per plan
AC-4a.10.

**AC-4 — Audit is clean across all 180 cells.**
`rk audit --policy strict` over every cell's run-dir exits 0; no
cell's trajectory contains forbidden tool invocations (DAB's
DISALLOWED_TOOLS or web-search), heredoc-decoded forbidden
patterns, or `python -c`-decoded forbidden patterns.
Verified by: a per-cell audit report committed alongside the
matrix's run-dir set; the aggregate report's `n_tainted` is 0.
Per plan AC-4a.7 + AC-4a.8.

**AC-5 — `rk score --against-constant stratified_pass_at_1=0.577`
produces a verdict per variant + dataset.**
Each of the three workspace-README variants produces a stratified
pass@1 with Wilson 95% CI; the `--against-constant` verdict
(inside-CI / outside-CI) is recorded per stratum (dataset) and at
the aggregate (stratified) level. The verdict for the `spacedock`
variant is the primary reproduction claim. The verdict for
`direct-baseline` compares against the paper's 0.4376.
Verified by: per-variant `rk score` output committed alongside the
matrix's run-dir set; the verdict table is the analyze-step
artifact. Per plan AC-4a.6.

**AC-6 — Result summary committed.**
A `docs/superpowers/plans/2026-05-19-goal1-paper-reproduction.md`
document captures the headline finding (reproduced / not
reproduced), per-variant `rk score` output, the audit pass/fail,
and the matrix cost ledger.
Verified by: the document exists; each subsection cites the
underlying run-dir paths.

**AC-7 — Total cost stays within budget.**
The dispatcher's final `budget.json` total is at or below the
declared `experiment.max_budget_usd` (e.g., $500); the budget gate
caught any overage attempt.

## Test plan

- **Dry-run test:** dispatcher's `--dry-run` mode prints the 180
  cell plan without invoking `rk run`.
- **Idempotency test:** partial dispatch + interrupt + re-dispatch
  produces the same final state as a single fresh dispatch.
- **Smoke before burn:** the v2-class × harbor-DAB end-to-end smoke
  at N=3 bookreview (AC-4a.13) ran clean before Goal 1 dispatches.
  This is a hard pre-condition; the captain does not authorize the
  $300-500 burn until the smoke confirms every surface works.
- **Aggregate audit:** `rk audit` across all 180 cells reports
  `n_tainted: 0`.
- **Acceptance command:** `bash
  examples/drivers/dab-paper-matrix.sh --budget 500
  --output-dir runs/goal1/` exits 0 after dispatching all 180
  cells.

## Out of scope

- Goal 2 (ade-bench Haiku baseline). Separate entity:
  `goal2-ade-bench-haiku-baseline`.
- Paper publication / write-up beyond the result summary doc.
  External publication is a captain decision.
- Cross-model comparison (sonnet, haiku). Goal 1's matrix is
  opus-4.7 only; cross-model is a later research question.
- N>5 trials. The paper's N=5 is the reproduction target; raising N
  is a separate question about variance characterization.
- Failure-mode analysis of failed trials. `1k`
  pkg11-failure-mode-analysis-workflow ships the FMA workflow for
  the autoresearch loop; Goal 1 reports the score, not the
  failure modes.

## Depends on

- `phase4a-rk-score-wilson-stratified` (analyze command — `rk
  score --against-constant`)
- `phase4a-rk-audit-taint-port` (`rk audit --policy strict`)
- `phase4a-rk-run-budget-gate` (`--max-budget-usd-running`)
- `phase4a-rk-runs-cost` (cost ledger)
- `72` pkg8-v2-rk-freeze-pinning (extended `rk freeze` per AC-2's
  sealed-input set)
- `v4` pkg9-v2-tools-denied-field (PreToolUse hook installation;
  DAB DISALLOWED_TOOLS list)
- `phase3-spacedock-solver-v2` (v2 agent class + per-runtime
  adapter for claude)
- `phase2-dab-harbor-adapter` (harbor-DAB adapter the matrix runs
  against)
- `phase1-rk-run-v2-wrapper` (`rk run` base)
- AC-4a.13 mechanism-validation smoke clean (every surface
  exercised at N=3 bookreview before the $300-500 burn)

## Stage Report: plan

- DONE: Plan names the dispatch shape: matrix-driver script at examples/drivers/dab-paper-matrix.sh per AC-4a.12 (create if absent); 3 workspace-README variants × 12 datasets × N=5 = 180 trials; opus-4.7 + hints ON.
  Plan §Architecture + §Tasks T1/T2 names the script path and its flag surface (`--budget`, `--output-dir`, `--dry-run`, `--continue-on-fail`); T1 generates the 36 frozen specs (3 variants × 12 datasets) carrying `model: claude-opus-4-7`, `hints: true`, `trials: 5`; the loop dispatches 36 specs × N=5 = 180 trials. Script does not yet exist on main (verified `ls examples/drivers/` returned no such directory); T2 creates it.
- DONE: Plan acknowledges T14 cost-shape evidence and names cost-verification step BEFORE the matrix burn.
  T0 is the explicit cost-shape verification task with two branches: Branch A (subscription covers opus-4.7) records "$0/trial" and proceeds; Branch B (subscription does NOT cover opus-4.7) projects the matrix cost from a measured per-trial `cost_usd`, sets `experiment.max_budget_usd: 600` (20% headroom above $500), and gates on captain approval before T2 dispatches. T0 explicitly precedes T1-T5 in the riskiest-contract-first ordering.
- DONE: Plan covers the scoring step: rk score --against-constant against 0.577 (spacedock) and 0.4376 (direct-baseline).
  Plan §Architecture "Scoring contract" table maps each variant to its `--against-constant` target (spacedock=0.577, direct-minimal/direct-structured=direct_baseline=0.4376); T5 dispatches per-cell `rk score --against-constant` and the aggregate-per-variant script computes the stratified-mean pass@1 + Wilson CI + per-stratum verdicts; T7's result summary section 2 carries the headline reproduction verdict for each variant.
- DONE: Plan records the PKG-13 blocker surfaced mid-plan by the team lead.
  Top-level "Blocker" section names PKG-13 — harbor-DAB compose generator workdir-path correctness — as the gate on T1+; explains the two coupled defects (bind-mount source resolving to non-existent `./workdir/` instead of `steps/main/workdir/`; verifier silently defaulting to `reward=1.0`); names the PKG-13 success criteria (corrected mount path, real verifier, fail-closed smoke, T14-shape re-run); states the matrix-dispatch design itself remains valid, only the burn is blocked.

### Summary

Wrote a 7-task plan at `docs/razorback-implementation/plans/goal1-dab-paper-reproduction.md` covering all 7 ACs. T0 (cost-shape verification) precedes T1-T7 per riskiest-contract-first discipline; T1 generates 36 frozen specs (3 variants × 12 datasets); T2-T4 ship the bash matrix driver + budget-gate threading; T5 wires per-cell and aggregate `rk score --against-constant` and `rk audit --policy strict`; T6 spot-checks provenance for AC-2; T7 commits the result-summary doc. The plan explicitly blocks on PKG-13 (harbor-DAB compose generator bind-mount fix; T14's 100% bookreview was a false positive per captain's docker-ps review); the design is unchanged but T1+ cannot start until PKG-13 ships and the corrected smoke supersedes the T14 entry in the baseline doc.

## Stage Report: implementation

- DONE: T0 cost-shape verification runs first (1 trial opus-4.7). If subscription does NOT cover (cost_usd != null and > $0), STOP and report projected matrix cost; do not proceed to T2+ without captain approval.
  T0 ran 1-trial opus-4.7 bookreview probe (`runs/goal1/t0/`); 3 sub-trials completed, all `cost_usd: null`, budget ledger `cost_known: false` → Branch A confirmed (subscription covers opus-4.7). No captain approval gate triggered. Probe also surfaced bookreview 0/3 reward (agent did not write `/workspace/answers.json`).
- DONE: Matrix driver examples/drivers/dab-paper-matrix.sh exists, is idempotent, and its --dry-run mode prints the 36-cell plan (3 variants x 12 datasets x N=1). N=1 per cell per captain directive — NOT N=5 as written in the plan body.
  Driver lives at `examples/drivers/dab-paper-matrix.sh` (commit 2dbe9c4 area). `--dry-run` enumerates 36 cells; idempotence verified by 2nd-dispatch SKIP messages over already-completed cells (`runs/goal1/matrix-dispatch-2.log` shows 19 SKIPs out of 21 completed). N=1 per cell encoded in `examples/specs/goal1/{variant}/{dataset}.yaml` and confirmed in driver output.
- FAILED: Full 36-cell matrix dispatched (or paused cleanly at budget gate). Per-variant `rk score --against-constant` output + `rk audit --policy strict` aggregate (n_tainted) + cost ledger committed to runs/goal1/. Result summary at docs/superpowers/plans/2026-05-19-goal1-paper-reproduction.md captures 3 per-variant stratified-pass@1 numbers with Wilson 95% CIs.
  Matrix dispatched 20 of 36 cells before host ENOSPC at direct-structured/PANCANCER_ATLAS (root cause: `_materialize_task_dir` shutil.copytree of per-question SQLite dbs — PKG-14 bind-mount didn't reach this path; PKG-21 just shipped to main and closes the gap). After FO disk-recovery cleanup of tasks/ subdirs, the surviving artifacts cover: direct-minimal 12/12 cells (10 strata scored, pooled pass@1=0.0 [0.000, 0.102]), direct-structured 8/12 cells (7 strata scored, pooled pass@1=0.433 [0.274, 0.608] — matches paper's 0.4376), spacedock 0/12 (never ran). NO spacedock number to report; the paper's headline 0.577 cannot be reproduced or refuted from this run. Result doc at `docs/superpowers/plans/2026-05-19-goal1-paper-reproduction.md` carries the two partial variant numbers + the seven caveats (a-h) per FO/captain directive. Resume blocked on PKG-21 + PKG-15-mongo-followup + PKG-24 + PKG-25.

### Summary

Goal 1 dispatched the 36-cell matrix (3 variants × 12 datasets × N=1) after T0 confirmed subscription-tier opus-4.7 ($0 cost). The matrix interrupted at cell 20/36 due to a SQLite/DuckDB workdir-copy ENOSPC (PKG-14 bind-mount gap; closed upstream by PKG-21 this session). Partial-result writeup committed at `docs/superpowers/plans/2026-05-19-goal1-paper-reproduction.md` with the two partial-variant numbers (direct-minimal 0/34, direct-structured 13/30) and full caveats: spacedock never ran (no reproduction claim), agnews+yelp mongo healthcheck failed (PKG-15 follow-up), direct-minimal agent never wrote answers.json (prompt-shape finding, not model capability), F1 stratum-collapse + F8 prose-prefix-vs-architecture caveats recorded. Verdict expected at validation: PARTIAL.

## Stage Report: validation

- DONE: Result doc at docs/superpowers/plans/2026-05-19-goal1-paper-reproduction.md is self-honest: NO reproduction claim against paper's 0.577 (insufficient data); 2 partial variant numbers reported with Wilson CIs computed from the actual completed cells; spacedock variant explicitly NOT reported (0/12 cells); caveats a-g from the implementation message all present.
  261-line doc reviewed; headline = "NOT ESTABLISHED"; per-variant table reports direct-minimal 0/34 + direct-structured 13/30 + spacedock no_data; all 7 caveats (a-h) cite specific follow-up entities (PKG-15/21/24/25); subscription-auth caveat in §Cost ledger.
- DONE: Per-cell aggregate is verifiable: spot-check 3 cells' result.json/summary.json/score.json against the result-doc table's mean rewards. Mongo healthcheck failures (agnews, possibly yelp) appear as mean=0 across all questions — surfaced in the doc as a known failure mode, not silently averaged in.
  Spot-checked direct-structured/bookreview (3/3, pass_at_1=1.0, CI [0.439, 1.0]); direct-structured/crmarenapro (10/13, 0.769, CI [0.497, 0.918]); direct-minimal/agnews (mongo failed, aggregate marks `pass_at_1=None error_reason=no_completed_trials_with_reward`, excluded from pooled). matrix-summary.json verdicts align with result-doc table bit-exactly.
- DONE: Code review on the worktree branch: scope of changes is examples/drivers/dab-paper-matrix.sh + aggregate-goal1-scores.py + result doc. Material vs polish findings. Verdict PARTIAL — the entity ships with verdict=PARTIAL (not PASSED, not REJECTED): the matrix-dispatch surface works; the matrix burned to completion is gated on PKG-21 (shipped) + PKG-15-mongo-followup (filed for next session) + future re-dispatch.
  Inline review of the small worktree diff (44 files, +2022/-2, no production code). Zero material/blocking findings. Five non-blocking findings recorded in validation report: hardcoded DATA_ROOT, brittle inline python3 heredoc, destructive rm -rf in retry helper, AC-2 sealed-input gap (PKG-8 owns), AC-4 audit-coverage gap (PKG-17 owns). dry-run verified live: 36 cells printed.

### Summary

Verdict **PARTIAL** per captain standing orders. AC-1/AC-3/AC-5/AC-6/AC-7 mechanisms verified end-to-end; AC-2 PARTIAL (`rk freeze` upstream sealed-input gap, PKG-8 owns); AC-4 PARTIAL-TRIVIAL (audit discovery shape mismatches harbor-DAB artifacts). Paper-reproduction headline is **NOT ESTABLISHED** (spacedock=0 data; direct-structured covers 7/12 strata). Validation report at `docs/razorback-implementation/validation/goal1-dab-paper-reproduction.md`. The FO merges `--no-ff` and archives; next session re-dispatches the 16 remaining cells after PKG-21 (shipped) + PKG-15 mongo follow-up land.
