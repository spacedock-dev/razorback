---
id: r447te87yycw1wxmb5q3dp6s
title: Phase 4a — rk run budget gate (--max-budget-usd-running)
status: plan
source: plan Phase 4a + spec §3.1 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T07:03:12Z
completed:
verdict:
score: 0.8
worktree:
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
