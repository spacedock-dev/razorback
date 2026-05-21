---
id: z11r44jhnz87fapt2y7tsp6x
title: PKG-27 — harbor.verifier vs ade-bench SQL-tests contract gap (Goal 2 layer-5)
status: plan
source: PKG-23 validation 2026-05-21 (commit 7073050 on archived branch spacedock-ensign/pkg23-harbor-shaped-compose-for-ade-bench) — live `rk run` cleared compose-up and reached the agent turn, then failed in harbor.verifier vs ade-bench's SQL-tests contract. The spike-flagged unknown-unknown layer-5 gap is now known.
started: 2026-05-21T15:42:32Z
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
mod-block:
---

## Problem

PKG-23 (T_BENCH_* env threading) shipped and got the airbnb001
trial past harbor's `DockerEnvironment._validate_definition` AND
past `docker compose up`. The trial now reaches harbor's
verifier step — and fails there.

The failure is the **layer-5 unknown-unknown** that the PKG-23
spike flagged: ade-bench's tasks are verified by SQL-tests
(against the `client` DBT/duckdb workspace), and harbor's verifier
contract doesn't speak that. ade-bench upstream runs its own
verifier via `client`'s shared docker socket; harbor expects a
verifier function declared on the task that returns a bool.

Goal 2 cannot produce a real per-task pass@1 number until this
gap is closed. PKG-23 cleared the structural blocker; PKG-27
closes the semantic one.

The exact failure mode + PKG-27's design space requires reading
PKG-23's validation report at
`docs/razorback-implementation/validation/pkg23-harbor-shaped-compose-for-ade-bench.md`
(or equivalent in the archived worktree branch) + the harbor
verifier surface at `harbor.task.verifier` (referenced as the
contract-holder).

Design options to evaluate at plan stage:
- **A.** Bridge: harbor verifier proxies to ade-bench's SQL-tests
  via the `client` socket (run upstream's verifier verbatim;
  marshall the bool back).
- **B.** Port: razorback re-implements the SQL-tests contract
  inside harbor's verifier shape (extract test SQL from
  `<task>/tests/` and run against `client`'s duckdb).
- **C.** Sidecar: a razorback-specific verifier-runner sibling
  that bypasses harbor.verifier for ade-bench tasks (parallel
  surface to spacedock_solver_v2's invention).

(B) is most upstream-faithful (no parallel runner); (A) is
fastest to ship; (C) drifts. Plan stage picks one with rationale.

## Acceptance criteria

**AC-1 — Goal 2 airbnb001 trial reaches a non-degenerate verdict.**
A live `rk run` against the goal2 T0 frozen spec (airbnb001 ×
Haiku × N=1) produces a `summary.json` with a meaningful
`mean_reward` (0.0 or 1.0, NOT null and NOT a verifier-error
short-circuit).
Verified by: live `rk run` from a clean worktree; result.json
shows the verifier ran and produced a verdict.

**AC-2 — Verifier path is upstream-faithful where possible.**
The chosen design option (per plan-stage decision) follows
ade-bench upstream's SQL-tests model rather than inventing a
parallel runner.
Verified by: plan-stage Stage Report names the chosen option
with rationale + AC-2 explicitly grades whether the impl matches
upstream.

**AC-3 — DAB regression.**
Harbor-DAB's verifier path (DAB postgres / mongo / sqlite
verifications) stays unchanged. PKG-27 touches only the
ade-bench verifier surface.
Verified by: existing DAB verifier tests stay green; a regression
test asserts the harbor-DAB verifier flow is not invoked by
ade-bench tasks.

**AC-4 — Goal 2's 48-cell matrix produces real per-task pass@1.**
After PKG-27 ships + goal2 re-dispatches, the matrix produces a
stratified pass@1 over the 48 ade-bench tasks (with the N=1
degenerate-CI caveat from Goal 2's existing entity).
Verified by: goal2-resume entity ships PASSED with verdict
recorded.

## Test plan

- **Unit:** scope per chosen design option (A/B/C). At minimum, a
  unit test asserts the verifier surface returns bool from the
  ade-bench task fixture.
- **Integration:** live `rk run` against airbnb001 produces
  meaningful reward.
- **Acceptance:** Goal 2's matrix dispatch.

## Out of scope

- ade-bench-client image build path (separate follow-up; PKG-23
  Out of scope already named it).
- Goal 2's 48-cell matrix dispatch (separate goal2-resume entity
  after PKG-27 ships).
- Goal 1 (different adapter, harbor-DAB; not affected).

## Depends on

- PKG-19 (shipped) — ade-bench data bind-mount
- PKG-20 (shipped) — ade-bench env-definition synthesis
- PKG-23 (shipped) — T_BENCH_* env threading
- harbor 0.6.6 `harbor.task.verifier` contract

## Resume hook

After PKG-27 ships, file `goal2-resume` (analog of
`goal1-resume-spacedock-first` for Goal 2's matrix) and dispatch.
Goal 2's archived worktree at
`.worktrees/spacedock-ensign-goal2-ade-bench-haiku-baseline`
keeps its T0 failure history but is no longer the active dispatch
surface.
