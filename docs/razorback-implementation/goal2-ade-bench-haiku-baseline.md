---
id: jjv58hxgfknqwbsehkashqj8
title: Goal 2 — Full ade-bench Haiku baseline (48 tasks × N≥3)
status: implementation
source: handoff "Two named research goals" + reconciliation plan Phase 4a end note
started: 2026-05-21T00:09:44Z
completed:
verdict:
score: 0.6
worktree: .worktrees/spacedock-ensign-goal2-ade-bench-haiku-baseline
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

## Stage Report: plan

- DONE: Plan ships as separate plan doc at docs/razorback-implementation/plans/goal2-ade-bench-haiku-baseline.md (8 ACs, multi-subsystem — standard, not inline). AC↔task map at top; spec §-cites per task.
  Plan written at `docs/razorback-implementation/plans/goal2-ade-bench-haiku-baseline.md`; AC↔task map table at line ~73; "Source of truth" section cites v2 spec §3.2, §6.2, §6.4, §8.1, §9.4 + PKG-19 validation report + PKG-17 archive + Goal 1 plan as architectural template.
- DONE: Plan folds the ade-bench probe (Phase 2-5 — task-shape end-to-end through v2 surface stack with PKG-19's bind-mount) as the FIRST task, gating subsequent matrix-dispatch tasks. Probe is single-task smoke at N=1 with Haiku; passes → matrix dispatch greenlit; fails → captain decision before $0-burn.
  T0 (probe phase 2-5) is the first task in §Tasks. "Riskiest contract first" section names T0 as the gate ("T1-T6 dispatch only after T0 is green"); T0 step 6 specifies the verdict protocol ("If any step fails, STOP and surface to captain ... DO NOT dispatch T1+").
- DONE: Plan explicitly overrides AC-4a.14/AC-5: N=1 per captain directive, NOT N≥3. Result-doc honesty caveat: per-task Wilson CIs at N=1 are degenerate ([0, 1] for any single observation); the baseline is reported as a point estimate with the N=1 caveat named in the result doc. Aggregate stratified pass@1 is still computable. The exact ack-language: 'Captain directive 2026-05-20: scope to N=1 to ship the number fast; raising N is a separate follow-up entity.'
  "Captain directive (2026-05-20)" section at the top of the plan carries the verbatim ack-language. AC-5 revision is named explicitly ("per-task Wilson CIs degenerate by construction"). T5 step 2's score aggregator bakes the N=1 honesty caveat into the JSON body. T6 step 1 + step 7 carry the caveat into the result doc; T6 step 3 names aggregate stratified pass@1 as the headline. The no-`--against-constant` framing (establishing measurement, not reproduction) is explicit in the Captain Directive section and in T6 step 3.

### Summary

Plan covers all 7 ACs with the captain's N=1 directive folded into the structure: T0 = probe phase 2-5 (single-task Haiku smoke gating the matrix); T1-T3 = generator + driver + idempotence/dispatch; T4-T5 = budget/audit/score/provenance aggregation; T6 = result summary with the N=1 honesty caveat + ML-reviewer F1 stratum-collapse note + registered-baseline value. The probe is the first live exercise of PKG-19's bind-mount path through `rk run` against a real ade-bench task (PKG-19's AC-7 was SKIPPED in validation due to sandbox env blockers), so it's the genuine riskiest contract for this matrix. No code changes in plan stage; plan doc committed to main alongside this entity stage report.

## Stage Report: implementation

- FAILED: T0 probe Phase 2-5 executes first: 1 ade-bench task × Haiku × N=1 through harbor-ade-bench with PKG-19's bind-mount.
  T0 Phase 2 (rk run) FAILED. Root cause: PKG-19's `materialize_local_task` (src/razorback/benchmarks/ade_bench/tasks.py) does not synthesize `environment/Dockerfile` or `environment/docker-compose.yaml` under the materialized view-dir. Harbor 0.6.6's `DockerEnvironment._validate_definition` (harbor/environments/docker/docker.py:316) requires at least one. The synthesized `task.toml` only carries `docker_image = "dab-agent:latest"`. ade-bench tasks ship NO per-task `environment/` — they share `~/git/ade-bench/shared/defaults/docker-compose.yaml`. Failure log: docs/razorback-implementation/validation/goal2-t0-probe-dispatch-failure.log. Additional blockers surfaced: (a) sandbox blocks `~/.cache/razorback/` creation (PKG-19's cache_root), worked around via HOME=worktree/.cache_home; (b) HOME override broke docker context resolution, fixed by exporting DOCKER_HOST=unix:///Users/clkao/.colima/default/docker.sock; (c) host disk free is ~10 GiB, not 58 GiB promised in dispatch preconditions. Phase 5 also implicitly FAILED — the provenance.yaml that was written carries only `image_digest`, `agent_cli_hash`, `harness_git_sha`, `harbor_version`, `prompt_file_hashes`, `plugins`; AC-2's v2 sealed-input set (`solver_workflow_hash`, `spacedock_skill_version`, `harbor_agent_kwargs_hash`, `tools_denied`) is absent. Phases 3-4 (rk score / rk audit) were not exercised because Phase 2 bailed before any trial completed (`n_completed_trials=0, n_pending_trials=1` in result.json).
- SKIPPED: Matrix driver examples/drivers/ade-bench-haiku-matrix.sh exists, is idempotent, --dry-run prints the 48-cell plan (48 tasks × N=1 — captain directive overriding entity AC-4a.14 N≥3), and re-dispatch after partial failure skips completed cells.
  Skipped per dispatch directive #2: "If any phase fails, STOP and report via SendMessage(to='team-lead'). Do NOT proceed to matrix dispatch on failure." T0's failure gates T1+.
- SKIPPED: Full 48-cell matrix dispatched (or paused cleanly at budget gate). rk audit aggregate (n_tainted), per-task rk score artifacts, cost ledger committed to runs/goal2/. Result summary at docs/superpowers/plans/2026-05-19-goal2-haiku-baseline.md captures aggregate stratified pass@1, N=1 degenerate-CI caveat, stratum-collapse caveat, baseline value registration for AC-7.
  Skipped: T0 is the hard gate. Matrix dispatch blocked.

### Summary

T0 Phase 2 surfaced a PKG-19 contract gap: the materializer emits no `environment/Dockerfile` or `environment/docker-compose.yaml`, and Harbor 0.6.6's docker env strictly requires one. ade-bench tasks share a single `shared/defaults/docker-compose.yaml` upstream; PKG-19 didn't symlink/synthesize it into the per-task view-dir. PKG-19's AC-7 (live probe) was SKIPPED in validation due to sandbox blockers — T0 here is the first live exercise that would have caught the gap, and it caught it. Captain decision required: (a) fix the materializer to symlink/synthesize an `environment/` directory from `<ade_bench_root>/shared/defaults/`, OR (b) reshape the spec to point harbor at the shared defaults explicitly. Two ancillary blockers also surfaced (sandbox `~/.cache/razorback/` creation; DOCKER_HOST not auto-resolved when HOME is overridden) and were worked around in T0. Provenance.yaml fields list is short of AC-2's v2 sealed-input set — separate code-change ask if the cache_root path doesn't also surface a different freeze codepath.
