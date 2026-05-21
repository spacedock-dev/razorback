---
id: 68b1z4ct15jfcxmvdkxezf73
title: PKG-39 benchmark variant spec generation for Codex ADE/DAB
status: backlog
source: captain request 2026-05-21
started:
completed:
verdict:
score:
worktree:
issue:
pr:
mod-block:
---

## Problem

The Codex benchmark runs need first-class spec-generation support for solver
workflow variants instead of one-off edited YAML. ADE should have a reusable
dbt-repair solver workflow that matches the smoked end state, and DAB should
expose the workspace and hint axes needed to try the context-freezing/resume
and batch-query variants found in `~/git/dataagentbench`.

## Acceptance criteria

**AC-1 — ADE has a checked-in Codex dbt-repair solver workflow.**
Verified by: `test -f examples/solver_workflows/codex-ade-dbt-repair/README.md`
and review of the workflow text confirming the graded artifact is the repaired
project state, not an `answers.json` file.

**AC-2 — Codex spec generation can select solver workflow variants and Harbor-shaped ADE data.**
Verified by: `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py`
covering custom solver workflow selection, variant metadata, and ADE roots laid
out as `harbor-data/ade-bench/<task>/task.toml`.

**AC-3 — DAB spec generation exposes workspace/hints variant knobs for current experiments.**
Verified by: `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py`
covering DAB workspace variant and hints overrides without changing default
spec output.

**AC-4 — The DAB variants found in `~/git/dataagentbench` are documented for run planning.**
Verified by: a concise checked-in note naming the batch, context-fresh, and
context-resume axes and the readme/query-mode inputs they require.

## Test plan

Run the focused generator unit tests with `uv run --frozen pytest
tests/unit/test_codex_benchmark_spec_generator.py`. Freeze one ADE spec from
the Harbor-shaped `runs/goal4-ade-bench-codex-clean/harbor-data/ade-bench`
root using the new ADE workflow to prove the generated spec seals.

## Out of scope

This task does not run the full DAB or ADE benchmark datasets. It only makes
the variant specs reproducible and documents the DAB variant candidates so the
benchmark operations can run from generated/frozen specs.
