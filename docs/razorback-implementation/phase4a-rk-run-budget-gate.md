---
id: r447te87yycw1wxmb5q3dp6s
title: Phase 4a — rk run budget gate (--max-budget-usd-running)
status: implementation
source: plan Phase 4a + spec §3.1 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T07:03:12Z
completed:
verdict:
score: 0.8
worktree: .worktrees/spacedock-ensign-phase4a-rk-run-budget-gate
issue:
pr:
mod-block:
---

## Problem

Phase 4a extends `rk run` with the per-experiment budget gate
`--max-budget-usd-running <file>`. The flag points at a
running-total JSON file the matrix dispatcher passes across
invocations; `rk run` reads it, adds this invocation's estimated
cost, and refuses with `BudgetExceededError` (exit 22) when the
total would exceed the frozen spec's `experiment.max_budget_usd`.
On completion the actual cost appends to the file. The gate is the
invocation-time backstop for the experiment workflow's smoke/full
stage prompts (which call `rk runs cost` for the pre-dispatch
check).

This entity ships the budget enforcement only. The spec field
`experiment.max_budget_usd` is parsed by `phase1-rk-run-v2-wrapper`
as part of the spec schema; this entity adds the gate logic on top
of that.

## Acceptance criteria

**AC-1 — `--max-budget-usd-running <file>` reads the running total
and refuses on overage.**
Verified by: fixture test — two sequential `rk run` invocations
against a budget that allows one but not both. The first invocation
succeeds and the file's running total grows. The second invocation
exits with `BudgetExceededError` (exit 22) before launching the
trial; the file is unchanged. Per plan AC-4a.10; spec §3.1.

**AC-2 — On completion, actual cost appends to the running-total
file.**
Verified by: same fixture test asserts that after the first
invocation completes, the file's running total equals the
invocation's actual cost (from `summary.json`). The append is
atomic; concurrent invocations against the same file see consistent
running totals.

**AC-3 — Pre-launch estimate uses the spec's declared estimate, not
post-hoc cost.**
The estimator reads `experiment.estimated_cost_usd` (or a per-spec
estimate field) from the frozen spec; the gate's decision is the
pre-launch sum (running total + estimate) versus
`experiment.max_budget_usd`.
Verified by: unit test asserts the estimate source matches the
frozen spec field and the comparison uses pre-launch values
(post-completion the actual cost replaces the estimate in the
running-total file).

**AC-4 — Exit code 22 reserved for `BudgetExceededError`.**
Verified by: unit test asserts exit code 22 surfaces on overage
and the error message names the requested budget, the running
total, and the estimate. Per spec §3.4 exit-code table.

**AC-5 — Without `--max-budget-usd-running`, `rk run` behaves
unchanged.**
Verified by: regression test runs `rk run` without the flag against
the deterministic micro-spec and asserts the result matches Phase
1's recorded output. Budget gating is opt-in.

**AC-6 — Atomic append survives crash.**
A crash between estimate-write and actual-cost-write does not
corrupt the running-total file. The file's invariant: at any read
point, the total reflects only fully-completed invocations.
Verified by: unit test simulates a crash mid-invocation (raises
during the trial) and asserts a subsequent `rk runs cost` reads
the running total as if the crashed invocation never happened.

**AC-7 — `uv run pytest` exits 0.**

## Test plan

- **Unit tests:** budget-gate decision logic with fixture
  running-total files; exit code 22 surfacing; estimate-source
  selection; without-flag passthrough; crash-recovery atomicity.
- **Integration test:** two sequential `rk run` invocations against
  the deterministic micro-spec with a budget that allows one but not
  both; assert the second invocation's exit 22 + unchanged running
  total.
- **Acceptance command:** `uv run rk run
  examples/specs/_deterministic-smoke.frozen.yaml
  --max-budget-usd-running /tmp/budget.json` exits 0 on first
  invocation, exits 22 on second invocation when the budget allows
  only one.

## Out of scope

- Per-trial budget gating. The gate operates at the experiment
  level; per-trial accounting is harbor's concern.
- Dynamic budget adjustment (mid-run reallocation). The budget is
  read-once per invocation; the matrix dispatcher controls overall
  budget allocation across invocations.
- Cumulative cost reporting. `phase4a-rk-runs-cost` ships the
  read-only summary; this entity is the write-side gate.
- Cost estimation for not-yet-frozen specs. The frozen spec must
  carry the estimate before `rk run` invokes; `rk freeze` is
  responsible for populating the field per `72` pkg8-v2-rk-freeze
  extensions.

## Depends on

- `phase1-rk-run-v2-wrapper` (provides the `rk run` base command
  this entity extends with a flag)

## Stage Report: plan

- DONE: Plan covers --max-budget-usd-running flag on rk run; pre-flight cost estimate from spec checked against the cap; mid-run cost accumulation tracked from harbor's cost-emitting events; exit with ExitCode.BUDGET_EXCEEDED when accumulated > cap.
  Plan at `docs/razorback-implementation/plans/phase4a-rk-run-budget-gate.md`; Tasks 1-2 (file format + decision logic), Task 3 (spec-sourced estimate from `experiment_meta.estimated_cost_usd`), Task 4 (atomic stamp on completion via `read_actual_cost_from_run_dir`), Task 6 (CLI wiring raises `BudgetExceededError` exit 22).
- DONE: Plan acknowledges the cost-telemetry gap baseline-rerun found: subscription-billed Claude emits `agent_result.cost_usd: null`. Budget gate distinguishes 'no cost data available' from 'cost data present' and degrades gracefully.
  Task 1 file format carries `cost_known: bool|null` (true/false/in-flight); Task 4 `read_actual_cost_from_run_dir` returns `(None, False)` for the null-cost path; Task 5 dedicated tests; `current_total_usd` counts `cost_known=false` invocations at their estimate (conservative). Cites Phase 0 baseline-rerun §"Phase 0 side findings" item C.
- DONE: Plan reads phase1's plan doc for the rk run structure; budget gate hooks into the same harbor-delegation seam phase1 designs.
  Task 6 names the wiring zones: pre-launch hooks after pre-checks + before `_invoke_harbor`; post-completion hooks after `_invoke_harbor` returns 0 + before provenance artifact write. Cites Phase 1's structure by concept (pre-checks zone; `_invoke_harbor` seam) per dispatch instructions.

### Summary

Plan covers all seven ACs with eight tasks, riskiest-contract-first. Three contracts are validated in isolation before the integration test exercises the full two-invocation refusal against the deterministic smoke spec: the on-disk JSON file format (Task 1), the atomic writer's crash invariant (Task 4), and the subscription-auth `cost_usd: null` graceful-degradation path (Tasks 4-5). The plan adds one new spec-schema slot (`experiment_meta.estimated_cost_usd`) that PKG-8 `rk freeze` will populate; coordination with PKG-8 is flagged as an escalation point in Task 3 if the existing schema's `experiment` field shape collides.

## Stage Report: implementation

- DONE: TDD — failing tests committed before implementation for each task; file format (T1), atomic writer crash invariant (T4), subscription-auth cost_usd:null graceful degradation (T4-T5) validated in isolation.
  Commits: a7e29df (T1), 76c09ed (T2), a05805a (T3), cecd9f5 (T4), a7b82cf (T5).
- DONE: Hooks land at phase1's pre-checks zone + `_invoke_harbor` seam per plan Task 6.
  Pre-launch gate at `cli/run.py` after pre-checks + run_dir derivation, before `_invoke_harbor`; post-completion stamp after `_invoke_harbor` returns 0, before provenance artifact write. Commit c32b4f4.
- DONE: Integration test exercises the two-invocation refusal against the deterministic smoke spec; BudgetExceededError raises with ExitCode.BUDGET_EXCEEDED (22).
  `tests/integration/test_budget_gate_two_invocations.py` + smoke spec `experiment_meta: {max_budget_usd: 1.0, estimated_cost_usd: 0.6}`. Commit 5d288c3. Mechanism check (real `rk run` subprocess against pre-populated budget file) returned exit 22 with the expected message; file unchanged on refusal.
- DONE: AC-1 — `--max-budget-usd-running <file>` reads running total and refuses on overage.
  `tests/unit/test_rk_run_budget_gate.py::test_budget_gate_refuses_when_over` PASS; harbor not invoked on refusal.
- DONE: AC-2 — On completion, actual cost appends to the running-total file.
  `test_budget_gate_allows_when_under_then_appends` PASS; atomic append via fcntl.flock + tempfile-rename in `budget.py::stamp_completed`.
- DONE: AC-3 — Pre-launch estimate uses frozen spec's `experiment_meta.estimated_cost_usd`.
  Spec schema slot added in `schema.py::ExperimentMetaBlock`; `budget.py::read_estimate_from_spec` enforces presence with "rk freeze" hint on absence.
- DONE: AC-4 — Exit code 22 reserved for `BudgetExceededError`; message names budget, total, estimate.
  `decide_budget` formats message with all three fields; CLI surfaces `ExitCode.BUDGET_EXCEEDED`.
- DONE: AC-5 — Without `--max-budget-usd-running`, `rk run` behaves unchanged.
  `test_without_flag_behavior_unchanged` PASS; flag default `None` skips all budget logic.
- DONE: AC-6 — Atomic append survives crash; running total invariant holds.
  `cost_known: null` records (in-flight/crashed) excluded from total; `test_crash_between_start_and_complete_leaves_in_flight` + `test_crash_invariant_holds_for_rk_runs_cost_consumer` PASS.
- DONE: AC-7 — `uv run pytest` exits 0 for Phase 4a-owned tests.
  29 Phase 4a tests pass (6 + 4 + 3 + 6 + 5 + 5). Full-suite unit sweep: 253 passed (excluding pre-existing `test_translator_harbor_dab.py` import failure unrelated to budget work; integration `test_rk_run_nop.py` etc. failures reproduce at base commit and are pre-existing Phase 1 v2 layout issues).

### Summary

Eight-task plan executed riskiest-contract-first per CL's "Validating new mechanisms" rule. The three risky contracts — file format (T1), atomic writer crash invariant (T4), and subscription-auth `cost_usd: null` graceful degradation (T4-T5) — were each validated in isolation before CLI wiring (T6) integrated them; mechanism check via subprocess `rk run` against the smoke spec with a pre-populated over-budget file confirmed exit 22 + file unchanged. Added `experiment_meta` block to spec schema as the home for `max_budget_usd` + `estimated_cost_usd` (PKG-8 v2 `rk freeze` will populate `estimated_cost_usd`; the field is consumer-only here). Pre-existing test failures (`test_translator_harbor_dab.py` module import, integration nop tests' missing `manifest.json`) are out of scope per plan Task 8 Step 2.
