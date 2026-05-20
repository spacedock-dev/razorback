---
id: taf9venjw6wr17pdqhfy5r2z
title: Phase 4a — rk runs cost
status: validation
source: plan Phase 4a + spec §3.3 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T07:12:27Z
completed:
verdict:
score: 0.8
worktree: .worktrees/spacedock-ensign-phase4a-rk-runs-cost
issue:
pr:
mod-block:
---

## Problem

Phase 4a ships `rk runs cost` as the cost-summary surface for a
directory of run-dirs. Given a root containing N runs, it reads each
run's cost (from `summary.json` or the harbor-emitted cost field)
and emits the cumulative sum. It pairs with the per-experiment
budget gate (`phase4a-rk-run-budget-gate`): the experiment
workflow's smoke/full stage prompts instruct the operator to run
`rk runs cost <root>` before dispatch and refuse if the running
total plus the next invocation's estimate exceeds
`experiment.max_budget_usd`. The invocation-time backstop is the
`--max-budget-usd-running <file>` flag on `rk run`.

`rk runs cost` extends the `rk runs list/show` surface filed under
`r0` pkg1-v2-rk-runs-cli; the same JSON-stable output discipline
applies under spec §3.3's semver promise.

## Acceptance criteria

**AC-1 — `rk runs cost [--root <dir>] [--experiment <name>]` emits
JSON with cumulative cost across the run-dirs under the root,
optionally filtered by experiment label.**
Verified by: unit test against a `tmp_path` populated with three
synthetic run-dirs (costs 1.50, 2.25, 0.75 USD) asserts the
emitted `total_usd` is 4.50. With `--experiment foo` only foo's
runs contribute. Unit test path:
`tests/unit/test_runs_cost.py`. Per plan AC-4a.9; spec §3.3.

**AC-2 — Per-run cost breakdown included in the output.**
The JSON document carries `runs: [{path, experiment, cost_usd,
created_at}, ...]` alongside the top-level `total_usd` aggregate.
Verified by: same unit test asserts the per-run list is present and
each element carries the four named fields.

**AC-3 — Cost source is `summary.json` (or the harbor-emitted cost
field).**
Verified by: unit test with two fixture run-dirs (one with cost in
`summary.json`, one with cost in harbor's emitted alternate field)
asserts both parse correctly and contribute to the total. The
implementation prefers `summary.json` when both are present and
documents the precedence rule.

**AC-4 — Missing cost data is named, not silently dropped.**
A run-dir missing both cost sources flags `cost_unknown: true` and
the run is excluded from `total_usd` with a warning in the output.
Verified by: unit test feeds a run-dir lacking cost data and
asserts the warning + exclusion behavior.

**AC-5 — Exit code 2 on nonexistent root.**
Verified by: unit test passes a nonexistent path and asserts exit
code 2 (USAGE) with an error message naming the missing input.
Mirrors `rk runs show`'s exit-code discipline per `r0` AC-3.

**AC-6 — JSON output stable under spec §3.3's semver promise.**
Verified by: snapshot test pins the output JSON schema; CI fails on
field rename or removal within the major version. Mirrors `r0`
pkg1-v2-rk-runs-cli AC-4.

**AC-7 — `uv run pytest` exits 0.**

## Test plan

- **Unit tests:** cumulative-sum math (three-run fixture); per-run
  breakdown shape; cost-source precedence (summary.json vs
  harbor-emitted); missing-cost warning; nonexistent-root exit
  code; JSON-key snapshot.
- **Integration test:** none required — filesystem-only command.
- **Acceptance command:** `uv run rk runs cost --root
  <fixture-root> --experiment <fixture-experiment>` exits 0 with
  the expected JSON.

## Out of scope

- Per-trial cost breakdown. `rk runs cost` summarizes at the
  run-dir level; per-trial accounting belongs in
  `summary.json`-shape decisions owned by harbor.
- Budget-gate enforcement. `phase4a-rk-run-budget-gate` ships
  `--max-budget-usd-running <file>` on `rk run`; `rk runs cost`
  is read-only.
- Markdown formatting. Spec §3.1 names JSON as default; defer
  human-readable polish until consumer demand surfaces.
- Cost-estimation for not-yet-run specs. The estimator that the
  budget gate consumes is owned by the budget-gate entity; `rk
  runs cost` reads completed runs only.

## Depends on

- `phase1-rk-run-v2-wrapper` (rk run produces the cost data this
  command consumes; the `summary.json` cost field shape comes from
  Phase 1's run-dir contract)
- `r0` pkg1-v2-rk-runs-cli (rk runs list/show CLI surface — `rk
  runs cost` extends the same JSON-stable shape and shares its
  filtering flags)

## Stage Report: plan

- DONE: Plan covers rk runs cost: enumerates run-dirs and sums cost_usd across trials. Cite spec §3.3 (rk runs subcommands) where rk runs cost lives.
  Plan at `docs/razorback-implementation/plans/phase4a-rk-runs-cost.md`; spec §3.2 cites `rk runs cost <root>` in the first-ship surface and §3.3 the JSON-key stability promise; Task 2 implements per-trial cost summation via the `result_step_agent` precedence level reading `step_results[].agent_result.cost_usd`; Task 3 aggregates into `total_usd`.
- DONE: Plan acknowledges the cost-telemetry gap: subscription-billed Claude leaves agent_result.cost_usd:null (per phase0 baseline-rerun). rk runs cost MUST distinguish 'cost data present' from 'cost data missing' in its output; null aggregation is a real first-class output, not a silent-zero.
  Plan's "Cost-telemetry gap discipline" section + AC-4 + Tasks 2/3/5 surface this: per-run `cost_unknown: true`, top-level `n_unknown` counter, non-empty `warnings` list; `total_usd: 0.0 + n_unknown: N + warnings: [...]` is a §3.3-distinct document from `total_usd: 0.0 + n_unknown: 0 + warnings: []`; Task 5 pins the subscription-auth all-null fixture end-to-end; cites Phase 0 baseline-rerun §"Phase 0 side findings" item C.
- DONE: Plan integrates with pkg1-v2 (rk runs list/show, already implemented), rk runs cost is a sibling subcommand under rk runs. Cite pkg1-v2's runs/inspect.py shape.
  Task 4 attaches `cost_command` to the existing `runs_app` at `src/razorback/cli/runs.py` next to pkg1-v2's `list_command`/`show_command`; Task 3 reuses `list_run_dirs(root, experiment=...)` from `razorback.runs.inspect` (pkg1-v2 t2) for enumeration and propagates `created_at` from its output verbatim; the new `read_run_cost` primitive lives in a sibling `src/razorback/runs/cost.py` so `inspect.py` is unchanged; Task 1 extends pkg1-v2 t1's `make_run_dir` factory rather than reimplementing it. Cross-plan note pins coordination with `phase4a-rk-run-budget-gate.read_actual_cost_from_run_dir` on the shared cost-source precedence.

### Summary

Wrote a separate-doc plan (8 tasks, ~25 unit tests) because the entity has 7 ACs, over the ≤3-AC inline threshold. Riskiest contract is cost-source precedence (must match `phase4a-rk-run-budget-gate`'s reader on `summary.json` → `result.json.stats.cost_usd`, then extends with a third per-trial fallback observed in the real run-dir). The cost-telemetry gap is first-class: every unknown surfaces as `cost_unknown: true` + a `warnings` entry; `total_usd` sums known-only; `n_runs == n_known + n_unknown` is invariant. Acceptance pass exercises the real subscription-auth fixture at `.runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/` where `summary.json` has no cost field and per-trial `agent_result.cost_usd` is null.
