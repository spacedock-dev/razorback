---
id: jjv58hxgfknqwbsehkashqj8
title: Goal 2 — Full ade-bench Haiku baseline (48 tasks × N≥3)
status: plan
source: handoff "Two named research goals" + reconciliation plan Phase 4a end note
started: 2026-05-21T00:09:44Z
completed:
verdict:
score: 0.6
worktree:
issue:
pr:
mod-block:
---

## Problem

Goal 2 establishes the Haiku-on-ade-bench baseline. The matrix
shape: ade-bench's full 48 tasks × N≥3 trials per task. Per
AC-4a.14, N=1 was rejected because Wilson CIs at N=1 are
uninterpretable; the captain's decision recorded under AC-4a.14
selects N≥3 (paying the additional ~$60-120) for usable
per-task CIs. Total estimated cost: ~$60-120.

The dispatch shape mirrors Goal 1: `for spec in matrix: rk freeze;
rk run --max-budget-usd-running budget.json; rk score; rk audit
--policy strict`. Unlike Goal 1, there is no `--against-constant`
target — Goal 2 is an establishing measurement, not a reproduction
claim. The output is the Haiku baseline run-dir set + its
stratified pass@1 with per-stratum (per-task) Wilson 95% CIs.

Goal 2 ships only after Phase 4a is complete, by the same gate as
Goal 1. It can run before or after Goal 1; the two are
independent matrices.

## Acceptance criteria

**AC-1 — Matrix dispatcher dispatches 48 × N≥3 cells.**
A dispatcher (the same `examples/drivers/` script family or a
sibling) iterates the ade-bench matrix at the captain-selected N
(per AC-4a.14). Re-dispatch after a partial failure skips
completed cells.
Verified by: dry-run mode prints the N×48 cell plan; partial
dispatch + re-dispatch reproduces the final state. Per plan
AC-4a.12.

**AC-2 — Per-cell `provenance.yaml` carries v2 sealed inputs.**
Same field set as Goal 1's AC-2 (solver_workflow_hash,
spacedock_skill_version, harbor_agent_kwargs_hash, model alias
resolved, image digest, agent CLI binary hash, prompt content
hashes, harbor version, tools_denied).
Verified by: a sampled cell's `provenance.yaml` parses against
the v2 schema. Per plan AC-4a.4.

**AC-3 — Budget gate enforced across the matrix.**
Per Goal 1's AC-3. Total stays at or below the declared
`experiment.max_budget_usd` (e.g., $120); the budget gate catches
any overage attempt.
Verified by: the dispatcher's final `budget.json` total is at or
below the declared cap.

**AC-4 — Audit is clean across all cells.**
`rk audit --policy strict` over every cell's run-dir exits 0;
ade-bench's task set should not trigger DAB-specific tool denials,
but heredoc / `python -c` / web-search patterns still apply.
Verified by: aggregate audit report's `n_tainted` is 0. Per plan
AC-4a.7.

**AC-5 — `rk score` produces per-task Wilson CIs + stratified
pass@1.**
With N≥3, per-task Wilson 95% CIs are interpretable; the
stratified mean is the headline baseline number.
Verified by: `rk score` output committed alongside the matrix's
run-dir set; the per-task CI half-widths are non-degenerate
(reflecting the N≥3 trial count). Per plan AC-4a.2 + AC-4a.14.

**AC-6 — Result summary committed.**
A `docs/superpowers/plans/2026-05-19-goal2-haiku-baseline.md`
document captures the headline number, per-task `rk score`
output, the audit pass/fail, and the matrix cost ledger.
Verified by: the document exists; each subsection cites the
underlying run-dir paths.

**AC-7 — Result usable as a registered baseline.**
The matrix's run-dir set is suitable as the `--against-constant`
target for a future Haiku improvement run via `rk score
--against-constant haiku_baseline_stratified_pass_at_1=<value>`.
Verified by: the result summary names the registered baseline
value + its CI; the value's commit hash is reproducible from the
run-dir set.

## Test plan

- **Dry-run test:** dispatcher's `--dry-run` prints the N×48 cell
  plan.
- **Idempotency test:** partial dispatch + interrupt + re-dispatch
  reproduces the final state.
- **Smoke before burn:** AC-4a.13 mechanism-validation smoke clean
  (same hard pre-condition as Goal 1); additionally, a Haiku-on-
  ade-bench single-task smoke at N=3 confirms ade-bench's task
  shape works through the v2 surface before the full burn.
- **Aggregate audit:** `rk audit` across all cells reports
  `n_tainted: 0`.
- **Acceptance command:** `bash
  examples/drivers/ade-bench-haiku-matrix.sh --n 3 --budget 120
  --output-dir runs/goal2/` exits 0 after dispatching all 48 × 3
  cells.

## Out of scope

- Comparison against other models (opus, sonnet). Goal 2 is the
  Haiku baseline only.
- N>3 trial counts. AC-4a.14's captain decision selects the N for
  this entity; raising N is a separate question.
- Paired comparison against any other baseline. Goal 2 is an
  establishing measurement; paired comparisons ship via `rk diff`
  in Phase 4b when needed.
- Goal 1 (DAB paper reproduction). Separate entity:
  `goal1-dab-paper-reproduction`.
- ade-bench task set extensions or modifications. Goal 2 runs
  against the existing 48-task set; any additions are a separate
  research question.
- harbor-native ade-bench adapter port. ade-bench currently lives
  in `src/razorback/benchmarks/ade_bench/`; Goal 2 may run against
  the in-tree adapter or against a future harbor-ade-bench port
  depending on what is available at dispatch time.

## Depends on

- `phase4a-rk-score-wilson-stratified` (analyze command — `rk
  score` per-task Wilson CIs require N≥3; the captain decision
  recorded under AC-4a.14 is the source for N)
- `phase4a-rk-audit-taint-port` (`rk audit --policy strict`)
- `phase4a-rk-run-budget-gate` (`--max-budget-usd-running`)
- `phase4a-rk-runs-cost` (cost ledger)
- `72` pkg8-v2-rk-freeze-pinning (extended `rk freeze`)
- `phase3-spacedock-solver-v2` (v2 agent class + claude runtime;
  Haiku is a claude model)
- `phase1-rk-run-v2-wrapper` (`rk run` base)
- AC-4a.13 mechanism-validation smoke clean
- AC-4a.14 N decision recorded (captain selects N≥3)
