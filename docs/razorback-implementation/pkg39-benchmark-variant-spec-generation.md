---
id: 68b1z4ct15jfcxmvdkxezf73
title: PKG-39 benchmark variant spec generation for Codex ADE/DAB
status: validation
source: captain request 2026-05-21
started: 2026-05-21T19:57:39Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-pkg39-benchmark-variant-spec-generation
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

## Stage Report: plan

- DONE: The plan maps each PKG-39 AC to concrete files, tests, and freeze/smoke verification.
  Evidence: `docs/razorback-implementation/plans/pkg39-benchmark-variant-spec-generation.md` has an AC-to-task map, file table, focused pytest command, and ADE/DAB freeze smoke steps.
- DONE: The plan calls out Harbor-shaped ADE data support and DAB variant axes from `~/git/dataagentbench` without requiring full benchmark runs in this task.
  Evidence: plan Task 3 targets `harbor-data/ade-bench/<task>/task.toml`; DataAgentBench reconnaissance notes cite the local equivalent checkout and Task 5 documents batch/context-fresh/context-resume axes as planning-only.
- DONE: The plan keeps implementation scope conservative: checked-in ADE workflow, generator/test updates, and concise DAB variant documentation.
  Evidence: plan file structure limits implementation to the ADE workflow README, Codex generator/tests, and one note; schema/translator/ADE resolver are inspect-only unless red tests prove a gap.

### Summary

Wrote the standard separate plan doc at `docs/razorback-implementation/plans/pkg39-benchmark-variant-spec-generation.md`. The plan follows the existing generator and v2 spec surfaces, prioritizes generator unit tests plus freeze smoke over full benchmark runs, and records that `/home/exedev/dataagentbench` is the available equivalent of the dispatched `~/git/dataagentbench` path in this VM.

## Stage Report: implementation

- DONE: Tests are added before implementation and cover custom solver workflow selection, Harbor-shaped ADE roots, DAB workspace/hints knobs, and default-output preservation.
  Evidence: red run first showed 6 expected failures; final `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py` passed with 17/17 tests.
- DONE: Implementation adds `examples/solver_workflows/codex-ade-dbt-repair/README.md`, updates `examples/drivers/generate-codex-benchmark-specs.py`, and documents DAB batch/context-fresh/context-resume axes using the available DataAgentBench checkout evidence.
  Evidence: changed files include the ADE workflow README, Codex generator/tests, and `docs/razorback-implementation/notes/pkg39-dab-variant-axes.md`; DataAgentBench evidence came from `/home/exedev/dataagentbench`.
- DONE: Focused pytest passes and at least one generated/frozen ADE spec smoke is attempted or completed with exact command/output recorded; full DAB/ADE benchmark runs are not launched.
  Evidence: generated `runs/pkg39-spec-smoke/specs/ade-bench/example001.yaml`; `uv run rk freeze runs/pkg39-spec-smoke/specs/ade-bench/example001.yaml --allow-missing` exited 0 and wrote `example001.frozen.yaml` plus `provenance.yaml` with solver workflow hashes.

### Summary

Implemented PKG-39 in commits `d08c3ba`, `467c88a`, and `6c7d251`. The generator now supports `--solver-workflow`, Harbor-shaped ADE roots with string task entries, and DAB `--workspace-variant` plus `--hints/--no-hints` while preserving default DAB output. Verification commands run: missing-workflow red test, full red generator suite, focused pytest twice, generated ADE spec smoke, and freeze smoke; no full benchmark datasets were launched.

## Stage Report: validation

- DONE: Focused generator tests pass from the validation worktree, and validation records any `uv.lock` churn or confirms none.
  Evidence: `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py` passed 17/17; unfrozen validation commands briefly removed the existing `uv.lock` `[options] exclude-newer` block and it was restored before commit.
- DONE: AC-1 through AC-4 are independently verified with concrete file/spec/freeze/doc evidence, including the checked-in ADE dbt-repair workflow, Harbor-shaped ADE support, DAB workspace/hints knobs, and DAB variant note.
  Evidence: validation report `docs/razorback-implementation/validation/pkg39-benchmark-variant-spec-generation.md` records AC command output, generated Harbor-shaped ADE spec evidence, freeze hashes, and DAB note grep output.
- DONE: Code review covers the generator, tests, solver workflow, and DAB note, classifies findings as blocking/non-blocking, and gives a clear gate recommendation.
  Evidence: manual application of `superpowers:requesting-code-review` protocol found no PKG-39 blocking or non-blocking findings; gate recommendation is PASSED.

### Summary

Validation reran the focused acceptance suite, generated and froze a one-task Harbor-shaped ADE spec with `codex-ade-dbt-repair`, checked the DAB variant documentation, and reviewed the implementation diff. Full `uv run pytest` was attempted and failed on non-PKG-39 integration prerequisites/residuals; the focused ACs passed and the gate recommendation is PASSED to `done`.
