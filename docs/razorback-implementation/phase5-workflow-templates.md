---
id: zgaactcgj955qn04t0jaj7dg
title: Phase 5 — solver workflow README templates
status: backlog
source: plan Phase 5 + spec §5 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started:
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
mod-block:
---

## Problem

Phase 5 ships the two workflow README templates per spec §5:
`docs/templates/experiment-workflow/README.md` (six stages: pending,
propose, smoke, full, analyze, conclude) and
`docs/templates/run-workflow/README.md` (four stages: pending,
reconciling, completed, failed). Both ship as package data so a
captain can copy them into a new research repo. No razorback-shipped
mods — per-stage prompt content carries the stage-level behavior the
prior mod design enumerated (leak-guard at propose, budget-check
prompt at smoke/full, analyze prompt calls `rk score
--against-constant` or `rk diff`).

Phase 5 ships AFTER Phase 6 because Phase 6 promotes v2 to canonical
`agent.kind: spacedock_solver`; Phase 5's templates reference the
canonical name, so they must come after the rename or they dangle on
`spacedock_solver`. The end-to-end hypothesis smoke (AC-5.4) is
the strongest single demonstration of v2 razorback's integration
shape working as a unit.

## Acceptance criteria

**AC-1 — Walking skeleton holds.**
Razorback continues to run DAB end-to-end via the direct CLI; Phase
5 adds the workflow templates without breaking direct CLI use.
Verified by: deterministic micro-spec passes both before and after
the template add. Per plan AC-5.1.

**AC-2 — `docs/templates/experiment-workflow/README.md` exists with
six stages and the required per-stage prompt content.**
- six stages: pending, propose, smoke, full, analyze, conclude
- sd-b32 ID style
- `experiment.max_budget_usd` declared in the template spec
- **propose** prompt: instructs the operator-ensign on what the
  solver-workflow README must not reference (answer keys,
  ground-truth columns, per-task hints); captain reviews at the gate
- **smoke** / **full** prompts: instruct the operator to run `rk
  runs cost <root>` before dispatch and refuse if running total +
  estimate exceeds `experiment.max_budget_usd`; the `rk run
  --max-budget-usd-running <file>` flag is the invocation-time
  backstop
- **analyze** prompt: instructs the operator to run `rk score
  --against-constant <baseline-headline>` (initial) or `rk diff`
  (when shipped); paste JSON into entity body; write a verdict
Verified by: the template parses against spacedock's workflow-README
schema; the propose / smoke / full / analyze stage prompts contain
the named guidance verbatim. Per plan AC-5.2.

**AC-3 — `docs/templates/run-workflow/README.md` exists with four
stages.**
Four stages (pending, reconciling, completed, failed). No
stage-completion-signal mods required because halt-resume's real-mod
machinery defers per AC-3.6's hand-fake note (spec §5.2).
Verified by: the template parses against spacedock's workflow-README
schema. Per plan AC-5.2.

**AC-4 — Package data shipping.**
`pyproject.toml` ships `docs/templates/` so a captain can copy
templates into a new project.
Verified by: `python -c "import importlib.resources; print(list(
importlib.resources.files('razorback').joinpath('templates').iterdir()))"`
lists both template directories from an installed razorback wheel.
Per plan AC-5.3.

**AC-5 — End-to-end hypothesis smoke (AC-5.4).**
A captain copies the experiment-workflow template into a fresh dir,
instantiates it against DAB via the new harbor adapter, and runs ONE
hypothesis end-to-end (propose → freeze → smoke → analyze →
conclude). The full path works.
Verified by: integration test executes the smoke end-to-end:
- propose-stage prompt + captain gate catch a deliberate leak-guard
  violation (the smoke's propose stage tries to reference an
  answer-key column; the captain gate rejects)
- smoke-stage prompt enforces budget via `rk runs cost`
- analyze stage produces `rk score --against-constant` output in
  the entity body
- conclude stage is reachable

Per plan AC-5.4. This is Phase 5's strongest single demonstration.

**AC-6 — `uv run pytest` exits 0.**
Per plan AC-5.5.

## Test plan

- **Schema tests:** both templates parse against spacedock's
  workflow-README schema (likely via spacedock's own parser).
- **Package data test:** the installed wheel exposes
  `templates/experiment-workflow/` + `templates/run-workflow/` via
  `importlib.resources`.
- **Stage-prompt content test:** propose / smoke / full / analyze
  prompts contain the named guidance phrases verbatim.
- **End-to-end smoke (AC-5):** the AC-5.4 hypothesis cycle runs
  against the harbor-DAB adapter; outputs land per the named
  expectations.
- **Acceptance command:** captain copies the template into a fresh
  dir, dispatches one hypothesis end-to-end; the analyze stage's
  entity body carries `rk score --against-constant` output.

## Out of scope

- Razorback-shipped workflow mods (leak-guard, tool-deny-runtime,
  baseline-compare, cost-ceiling, stage-boundary-freeze,
  phase-stats-writer). Spec §8.5 documents the collapse: the first
  four collapse to per-stage prompt content + spec block field
  (`tools_denied`) + CLI flag (`--max-budget-usd-running`); the
  last two defer with halt-resume's real-mod machinery.
- `rk init` scaffolding subcommand. D4's default: defer until
  consumer materializes; templates ship as copy-and-modify.
- Failure-mode-analysis workflow template. `1k`
  pkg11-failure-mode-analysis-workflow filed as post-v2 follow-up.

## Depends on

- `phase6-promote-v2-canonical` (must land first — templates
  reference `agent.kind: spacedock_solver` which Phase 6 produces
  by renaming v2; per plan's sequencing note)
- `phase4a-rk-runs-cost` (smoke/full stage prompts call this
  command)
- `phase4a-rk-run-budget-gate` (invocation-time backstop the
  smoke/full prompts reference)
- `phase4a-rk-score-wilson-stratified` (analyze stage prompt calls
  `rk score --against-constant`)
- `phase4a-rk-audit-taint-port` (smoke / full stage prompts may
  invoke `rk audit --policy strict` as part of the leak-guard
  discipline; optional but reasonable to include)
