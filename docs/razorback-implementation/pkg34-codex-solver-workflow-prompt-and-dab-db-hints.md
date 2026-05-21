---
id: 0pkj0eznqq1he64hmc73y7v5
title: PKG-34 Codex solver workflow prompt and DAB DB hints
status: plan
source: goal3 DAB Codex clean-score blocker
started: 2026-05-21T10:32:17Z
completed:
verdict:
score: 0.94
worktree:
issue:
pr:
mod-block:
---

## Problem

The guarded Codex BookReview probe scored 3/3 but strict audit correctly marked
q2 and q3 tainted. The solver workflow README is currently hashed for
provenance but not injected into the runtime prompt, and the generated Codex DAB
specs use the terse workspace variant that does not place service host and
credential hints in the workspace README. Codex therefore inferred local service
access by probing Docker/socket surfaces instead of following documented task
files.

## Acceptance criteria

**AC-1 — `spacedock_solver_v2` sends the solver workflow instructions to the
inner runtime.**
Verified by: a unit test where a v2 solver with a workflow `README.md` calls
`run("task instruction", ...)` and the inner agent receives one instruction
containing the workflow text before the task text.

**AC-2 — Codex DAB generated specs use structured DAB workspace hints.**
Verified by: `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py -q`
showing emitted DAB specs carry `workspace_variant: direct-structured`, and the
checked-in Codex DAB smoke spec matches that default.

**AC-3 — The Codex benchmark workflow explicitly forbids solver-side container,
host, and shell-network probing.**
Verified by: review of `examples/solver_workflows/codex-benchmark-solver/README.md`
showing it tells the solver to read task-local instructions and
`db_config.yaml`/workspace README first, use documented service names, and not
run commands such as `docker`, Docker socket inspection, `curl`, `wget`,
package installs, or public network lookups while solving.

**AC-4 — BookReview rerun is both scored and audit-clean.**
Verified by: rerunning the Codex BookReview frozen spec generated after this
change, then running `uv run --frozen rk score <run-dir> --format json` and
`uv run --frozen rk audit <run-dir> --policy strict --format json`; score must
complete all 3 trials, and strict audit must report 3 clean trials with no
tainted or coverage-missing trials.

## Test plan

Add focused unit coverage for prompt composition and generator defaults. Run the
affected unit tests before the live BookReview rerun.

## Out of scope

This task does not run the full DAB or ade-bench matrices. It creates the clean
BookReview gate needed before spending the full-dataset budget.
