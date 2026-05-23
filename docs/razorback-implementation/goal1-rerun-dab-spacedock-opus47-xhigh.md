---
id: an2znvdzjsp8q1v5a4wrg51p
title: Goal 1 re-run — DAB spacedock matrix, opus-4.7, reasoning_effort=xhigh, batch, parallel=1
status: validation
source: Captain directive 2026-05-23 — "do a fresh dab+spacedock on opus-4.7/xhigh, batch mode, parallel=1" issued after the gb/qh identity-layer ergonomics sprint landed
started: 2026-05-23T13:57:32Z
completed:
verdict:
score: 0.95
worktree: .worktrees/spacedock-ensign-goal1-rerun-dab-spacedock-opus47-xhigh
issue:
pr:
mod-block: merge:pr-merge
---

## Problem

The post-sprint state — phase6 promoted v2 to canonical `spacedock_solver`,
qh shipped DAB dataset definitions, gb shipped ADE dataset-ref tiers, zb
shipped per-query `rk score`, f1 shipped freeze CAS, x9 shipped runs_dir
outside worktree — is the cleanest moment to produce a fresh Goal-1 DAB
spacedock baseline against the canonical infrastructure.

This entity captures a single research run, not a code change:

- Benchmark: DAB (`kind: harbor_dab`, `dataset: dab@1.0` from the
  plugin-shipped `dataset.toml`)
- Variant: `workspace_variant: spacedock` (the three-stage solver loop
  `model → analyze → verify`)
- Coverage: all 12 DAB datasets (54 queries total)
- Model: `claude-opus-4-7`
- Reasoning effort: `reasoning_effort: xhigh`
- Query mode: `query_mode: batch`
- Concurrency: `concurrency.trials: 1` (sequential)
- Trials per cell: `N=1` (first-cut headline; promote to N=5 later if
  the headline warrants a paper-comparable reproduction)

This is the first Goal-1-shaped run executed against:
- Per-query `rk score` (zb): the headline number is paper-faithful out
  of the box
- runs_dir at `$XDG_DATA_HOME/razorback/runs/` (x9): artifacts survive
  worktree teardown
- Freeze CAS at `$XDG_DATA_HOME/razorback/freeze/<sealed_hash>/` (f1):
  re-runs hit the same sealed_hash → resume branch
- Canonical `kind: spacedock_solver` (phase6): no `_v2` suffix
- `dataset: dab@1.0` via qh's `dataset.toml`: identity-layer canonical

## Acceptance criteria

**AC-1 — Specs regenerated against the canonical post-sprint shape.**
`examples/drivers/generate-dab-paper-matrix-specs.py` emits 12
spacedock spec cells under `examples/specs/goal1/spacedock/` carrying
`kind: spacedock_solver` + `dataset: dab@1.0` + `reasoning_effort:
xhigh` + `query_mode: batch`. The pre-existing local-root-style shape
(`data_root + datasets + workspace_variant` without `dataset:`) does
NOT appear in the regenerated specs.
Verified by: `grep -L "^benchmark:" examples/specs/goal1/spacedock/*.yaml`
empty; `grep -l "reasoning_effort: xhigh" examples/specs/goal1/spacedock/*.yaml`
returns all 12.

**AC-2 — Each spec freezes cleanly.**
`rk freeze` runs against each of the 12 spec files and produces
`spec.frozen.yaml` + `provenance.yaml` adjacent. No `SpecError` or
`AliasDriftError` raised. `provenance.yaml` records
`solver_workflow_content_hash` + the post-phase6 canonical kind.
Verified by: a shell loop runs `rk freeze` per spec and captures
exit codes; all 12 = 0.

**AC-3 — Full 12-cell run completes.**
`rk run <spec.frozen.yaml>` executes sequentially against all 12
cells (`concurrency.trials: 1`). Each invocation produces a run-dir
under `$XDG_DATA_HOME/razorback/runs/` with `summary.json`,
`provenance.yaml`, per-trial result.json + reward_per_query.json,
and a freeze tree under `$XDG_DATA_HOME/razorback/freeze/<sealed_hash>/`.
Failure of an individual cell does not block subsequent cells.
Verified by: 12 run-dirs exist; their summary.json files are
parseable JSON; freeze CAS root contains 12 sealed_hash subdirs.

**AC-4 — Aggregate `stratified_pass_at_1` reported.**
`rk score` against each run-dir + a captain-facing aggregator pass
across the 12 run-dirs emits a single headline number for the
spacedock variant of Goal 1. The number is compared against the
paper's `spacedock = 0.577` target via `--against-constant
paper=0.577`. The per-query Wilson CI is reported at each
`(dataset, query_id)` cell; the stratum-level CI is `null` per zb's
design.
Verified by: a final report includes the aggregate number + the
`--against-constant` verdict (inside-CI / above / below) per dataset
and overall.

**AC-5 — Provenance artifacts pin the run.**
Every cell's `provenance.yaml` records: `solver_workflow_content_hash`,
`spacedock_skill_version`, `harbor_agent_kwargs_hash`, the
`reasoning_effort: xhigh` setting, and the resolved opus-4.7 model
version (`pin_model_version: true`). A future re-run from the same
spec reproduces the same `sealed_hash` and discovers the existing
freeze tree.
Verified by: per-cell `provenance.yaml` enumerated in the final
report; all 5 fields present per cell.

## Test plan

- **Smoke:** `rk freeze` one cell (bookreview) and confirm the post-qh
  schema accepts `dataset: dab@1.0` + the new `reasoning_effort:
  xhigh` field. If `reasoning_effort: xhigh` is rejected by Anthropic's
  API at first `rk run` invocation, fall back to `reasoning_effort:
  high` and document the deviation.
- **End-to-end smoke:** one cell (bookreview, N=1) completes; record
  wallclock + cost.
- **Full matrix:** all 12 cells; collect summary.json each.
- **Aggregate:** captain-facing report.

## Out of scope

- N=5 paper-comparable trial replication. Filed as a follow-up if the
  N=1 headline warrants paper-grade reproduction.
- Direct-minimal + direct-structured variants. Captain directive
  scoped this run to spacedock; the other variants are sibling
  entities if the comparison surfaces.
- Cost-projection pre-flight. The full matrix at N=1 with opus-4.7
  + xhigh is roughly `12 × ~$5/cell ≈ $60` based on the prior
  goal1-resume reconstruction; the `--max-budget-usd-running`
  ceiling backstops a runaway.

## Depends on

- gb ade-bench-harbor-dataset-ref: done (DAB doesn't consume gb's
  resolver — DAB uses qh's plugin dataset.toml — but gb's shipping
  closes the identity-layer sprint cleanly)
- qh dab-harbor-dataset-definition: done
- zb rk-score-uses-benchmark-aggregator: done
- f1 freeze-tree-content-addressable-store: done
- x9 razorback-runs-outside-worktree: done
- z5 fo-no-force-worktree-remove: done
- t1 phase6-promote-v2-canonical: done

## Resume hook

After this entity merges, the captain has a fresh DAB spacedock
headline against the post-sprint canonical infrastructure. If the
number is within paper's expected band, file an N=5 follow-up. If
it's surprising, the per-query Wilson CIs at the cell level surface
which (dataset, query_id) cells diverge.

## Stage Report: plan

- DONE: Separate plan doc at docs/razorback-implementation/plans/goal1-rerun-dab-spacedock-opus47-xhigh.md per the README's 4+-AC rule. AC↔task map; spec the per-cell command sequence + the aggregator step.
  Plan written; AC↔task table, surface map, T0-T8 task list, risk register, definition of done all present. 5 ACs → 8 tasks; T0+T1 are RED/GREEN unit pair, T2-T8 are dispatch+observation.
- DONE: Validate the reasoning_effort=xhigh contract end-to-end on a single bookreview cell BEFORE committing to the full 12-cell matrix. Specifically: regenerate the bookreview spec via the post-qh generator (with `--reasoning-effort xhigh` if the generator supports it; add the field manually otherwise), run `rk freeze`, then run `rk run` (or a dry-run if possible) and confirm the agent kwargs flow through to harbor without an Anthropic-API-side rejection. If `xhigh` is rejected, document the actual accepted values and surface to captain before scaling up.
  Generator does NOT support `--reasoning-effort`; field added manually to bookreview.yaml. `rk freeze --allow-missing` produced `bookreview.frozen.yaml` with `agent.reasoning_effort: xhigh` + `agent.sealed_hash: 377bd09522713c54668a004eb8a06834`. Claude-runtime adapter probe (`claude_adapter.build_inner_agent(harbor_agent_kwargs={'reasoning_effort': 'xhigh'})`) emitted CLI flags including `--effort xhigh`; harbor's `ClaudeCode.CLI_FLAGS` declares `xhigh` in its `choices` list. No API-side rejection at flag-build time. Side fix: added missing `model_validator` import to src/razorback/spec/schema.py (pre-existing bug from cf52c26 broke every `rk` CLI entry).
- DONE: Specify the dispatch shape for the full matrix in the plan: which order, how summary.json from each cell is named/collected, how the captain-facing aggregator gathers them, and the budget guardrail (`--max-budget-usd-running` with a captain-acceptable ceiling). Name the failure-mode containment: if cell N fails, do cells N+1..12 still run?
  Plan T4-T8 specify: alphabetical order within spacedock, dispatcher at `examples/drivers/dab-paper-matrix.sh --variants spacedock`, per-cell summary.json at `${OUTPUT_DIR}/spacedock/<dataset>/<run>/<job>/summary.json`, aggregator at `examples/drivers/aggregate-goal1-scores.py`. Budget guardrail: `--max-cell-budget-usd 10.0` (2× the $5/cell estimate). Failure containment: `--continue-on-fail` flag on dispatcher — cell N+1..12 DO run after cell N failure; failures recorded in `dispatch-failures.tsv` and rolled into T8 final report.

### Summary

Plan stage produced a separate plan doc at `docs/razorback-implementation/plans/goal1-rerun-dab-spacedock-opus47-xhigh.md` with an AC↔task map (5 ACs → 8 tasks), per-cell command sequence, aggregator wiring, budget + failure-containment guardrails, and a risk register. The riskiest contract (`reasoning_effort: xhigh` threading through spec → frozen sealed_hash → claude-cli `--effort` flag) was validated end-to-end on bookreview during plan stage, so implementation stage inherits a green mechanism gate. A pre-existing schema.py import bug (`model_validator` not imported despite usage on `HarborDabBenchmarkBlock`, introduced in `cf52c26`) was fixed in the same plan-stage commit because it blocked every `rk` CLI entry point.
