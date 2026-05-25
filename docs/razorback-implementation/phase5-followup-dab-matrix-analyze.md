---
id: zhzokycis7ppv1dsl8mzs3t3
title: Phase 5 follow-up — DAB-paper matrix analyze-stage prompt
status: backlog
source: phase5-workflow-templates implementation, T-5c branching rule
started:
completed:
verdict:
score: 0.6
worktree:
issue:
pr:
mod-block:
auto-approve: false
---

## Problem

Phase 5 ships the experiment-workflow template's analyze stage with the
single-benchmark task-binary path only. The DAB-paper multi-dataset
matrix-aggregator path (12 cells over the DAB dataset, rolled up via
`examples/drivers/aggregate-goal1-scores.py`) is deferred to this
follow-up.

Reason for split (recorded at phase5 implementation-stage dispatch,
2026-05-25): entity
`goal1-matrix-aggregator-stratified-verdict-fix` (id
`08ghk1yvkq9vzs71gzecx5bf`) was at `implementation` stage — NOT
archived. The aggregator's bug at
`examples/drivers/aggregate-goal1-scores.py:189` (computing
`per_query_verdict` from `pooled_per_query_ci` instead of the
stratified mean) blocks the DAB-matrix analyze prompt from
referencing the aggregator's verdict field correctly. Per the phase 5
plan's T-5c branching rule, T-5c splits to this entity and phase 5
ships with the single-benchmark path only.

The phase-5 template at
`src/razorback/templates/experiment-workflow/README.md` already
includes a "DAB-paper multi-dataset matrices (deferred to follow-up)"
section that cites this entity. This follow-up replaces that section
with the actual DAB-matrix analyze prose once entity 08 lands.

## Acceptance criteria

**AC-1 — Entity 08 archived precondition.**
`goal1-matrix-aggregator-stratified-verdict-fix` is at `done` /
archived before this entity moves off backlog.
Verified by: the aggregator's
`per_query_verdict` field at
`examples/drivers/aggregate-goal1-scores.py` (or successor) computes
against the stratified mean (NOT pooled CI); test or aggregate-score
output confirms the fix.

**AC-2 — DAB-matrix analyze prompt replaces the deferred-section
placeholder.**
The experiment-workflow template's analyze stage gains a sibling
prose block that:
- documents using `examples/drivers/aggregate-goal1-scores.py` (or
  successor) for DAB-paper multi-dataset matrices
- cites the `per_query_pass_at_1_mean_over_strata` field as the
  paper-canonical lens for DAB
- cites the aggregator's stratified-mean-based verdict field (the
  output of entity 08's fix)
- preserves the stratified-only headline directive (no pooled / no
  binary-pooled in the headline)
Verified by: `grep -F "per_query_pass_at_1_mean_over_strata"
src/razorback/templates/experiment-workflow/README.md` returns ≥1
match; `grep -F "aggregate-goal1-scores.py"
src/razorback/templates/experiment-workflow/README.md` returns ≥1
match.

**AC-3 — Phase-5 content-lint test extended.**
`tests/unit/test_workflow_templates_content.py` (or sibling) asserts
the new DAB-matrix phrases verbatim. Verified by: failing-test-first
TDD — the test fails before AC-2 lands and passes after.

**AC-4 — `uv run pytest` exits 0.**
Verified by: `uv run pytest -q` exits 0 with the new DAB-matrix
content-lint test passing.

## Test plan

- Extend `tests/unit/test_workflow_templates_content.py` with grep
  assertions on the new DAB-matrix prose phrases.
- Re-run the AC-4 wheel-shipping test; confirm the updated template
  still ships from the installed wheel.

## Out of scope

- Aggregator fix itself (entity 08's job).
- Multi-paper / non-DAB matrices (no consumer materializes a
  non-DAB matrix yet).

## Depends on

**Hard preconditions:**

- `goal1-matrix-aggregator-stratified-verdict-fix` (id
  `08ghk1yvkq9vzs71gzecx5bf`) must be archived. Phase 5 cannot ship
  this entity's analyze-prose changes against a buggy aggregator.

**Phase 5 parent:**

- `phase5-workflow-templates` (id `zgaactcgj955qn04t0jaj7dg`) —
  this follow-up replaces the "DAB-paper matrix (deferred)" section
  of the experiment-workflow template's analyze stage.
