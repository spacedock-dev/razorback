---
id: ayf9mczntgnp808z8ggpjzf4
title: Goal 1 — DAB paper reproduction (opus-4.7 + hints × 3 variants × 12 datasets × N=5)
status: implementation
source: handoff "Two named research goals" + reconciliation plan Phase 4a end note
started: 2026-05-20T16:33:40Z
completed:
verdict:
score: 0.65
worktree: .worktrees/spacedock-ensign-goal1-dab-paper-reproduction
issue:
pr:
mod-block:
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
