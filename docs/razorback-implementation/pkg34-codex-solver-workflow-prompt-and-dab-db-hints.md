---
id: 0pkj0eznqq1he64hmc73y7v5
title: PKG-34 Codex solver workflow prompt and DAB DB hints
status: validation
source: goal3 DAB Codex clean-score blocker
started: 2026-05-21T10:32:17Z
completed:
verdict:
score: 0.94
worktree: .worktrees/spacedock-ensign-pkg34-codex-solver-workflow-prompt-and-dab-db-hints
issue:
pr:
mod-block: merge:pr-merge
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

## Inline Implementation Plan

I'm using the writing-plans skill to create the implementation plan. FO sized
this as a tiny task, so keep the plan inline on the entity instead of creating a
separate plan document.

**Goal:** Make Codex BookReview solves follow the committed solver workflow and
task-local DAB database instructions, then prove the rerun is scored and
strict-audit clean.

**Spec anchors:** v2 spec §4.3.2 and §4.3.3 require `SpacedockSolverAgent` to
bootstrap/configure the inner runtime from the solver workflow; §5.3 defines the
solver workflow README contract; §6.1/§6.2 define the spec and agent-block
translation surfaces; §8.2 covers solver-workflow content hashing; §8.4 covers
the runtime adapter delegation; §9.4 defines the leak-guard layers and why
post-hoc strict audit is still required.

**Files to touch:**

- `tests/unit/test_spacedock_solver_v2_class.py` — add the AC-1 failing unit
  test for `SpacedockSolverAgent.run` prompt composition.
- `src/razorback/agents/spacedock_solver_v2.py` — read
  `solver_workflow/README.md` and pass one composed instruction to the inner
  runtime with workflow text before task text.
- `tests/unit/test_codex_benchmark_spec_generator.py` — assert generated Codex
  DAB specs and the checked-in smoke spec use the structured DAB workspace
  default.
- `examples/drivers/generate-codex-benchmark-specs.py` — change Codex DAB
  generated benchmark blocks to `workspace_variant: direct-structured` while
  keeping the benchmark condition unchanged with `hints: false`.
- `examples/specs/codex-dab-smoke.yaml` — update the checked-in Codex DAB smoke
  spec to match the generator default while keeping `hints: false`.
- `examples/solver_workflows/codex-benchmark-solver/README.md` — make the
  solver-side no-probing rules explicit.

**TDD checkpoints:**

1. **AC-1 prompt-composition test first.** Add
   `test_run_sends_solver_workflow_readme_before_task_instruction` to
   `tests/unit/test_spacedock_solver_v2_class.py`. Construct a valid v2
   `SpacedockSolverAgent` with a temporary `solver/README.md`, assign an
   `AsyncMock` inner agent to `agent._inner`, call
   `await agent.run("task instruction", environment, context)`, and assert the
   inner agent is called once with an instruction where the README text appears
   before `"task instruction"`. Run:
   `uv run --frozen pytest tests/unit/test_spacedock_solver_v2_class.py::test_run_sends_solver_workflow_readme_before_task_instruction -q`.
   Expected before implementation: fail because `run()` forwards only the raw
   task instruction. Implement the smallest helper in
   `src/razorback/agents/spacedock_solver_v2.py` to read README text and compose
   the delegated instruction; rerun the same test to pass. This satisfies
   §4.3.2, §4.3.3, §5.3, and §8.4.

2. **AC-2 generator/spec tests before edits.** In
   `tests/unit/test_codex_benchmark_spec_generator.py`, extend
   `test_emit_dab_codex_spec_uses_solver_v2_codex_and_harbor_dab` to assert
   `payload["benchmark"]["workspace_variant"] == "direct-structured"` and
   `payload["benchmark"]["hints"] is False`. Add a small test that loads
   `examples/specs/codex-dab-smoke.yaml` and asserts the same benchmark fields.
   Run:
   `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py -q`.
   Expected before implementation: fail on the current direct-minimal smoke and
   generator defaults. Update `examples/drivers/generate-codex-benchmark-specs.py`
   and `examples/specs/codex-dab-smoke.yaml`, then rerun to pass. This covers
   §6.1/§6.2 and keeps the frozen-spec input path aligned with §8.2.

3. **AC-3 README edit and review checkpoint.** Update
   `examples/solver_workflows/codex-benchmark-solver/README.md` so the operating
   rules tell the solver to read task-local instructions, workspace `README.md`,
   and `db_config.yaml` before choosing a database access path; use only
   documented service names such as `dab-postgres` and `dab-mongo`; and do not
   probe Docker, Docker sockets, host networking, `curl`, `wget`, package
   installs, public network lookups, or remote APIs while solving. Review the
   diff against AC-3 and §5.3/§9.4 before running live validation.

4. **Focused validation before live spend.** Run:
   `uv run --frozen pytest tests/unit/test_spacedock_solver_v2_class.py tests/unit/test_codex_benchmark_spec_generator.py -q`.
   If either fails, stop and fix before any benchmark rerun.

5. **AC-4 smallest end-to-end BookReview rerun.** Use a caller-supplied
   `DAB_DATA_ROOT` and repo-relative scratch paths so no local machine path is
   tracked:

   ```bash
   uv run --frozen python examples/drivers/generate-codex-benchmark-specs.py \
     --benchmark dab \
     --dab-data-root "$DAB_DATA_ROOT" \
     --out-root .runs/pkg34/specs \
     --write
   uv run --frozen rk freeze .runs/pkg34/specs/dab/bookreview.yaml
   RUN_DIR=.runs/pkg34/bookreview-codex
   rm -rf "$RUN_DIR"
   uv run --frozen rk run .runs/pkg34/specs/dab/bookreview.frozen.yaml --runs-dir "$RUN_DIR"
   uv run --frozen rk score "$RUN_DIR" --format json
   uv run --frozen rk audit "$RUN_DIR" --policy strict --format json
   ```

   Pass condition: score reports all 3 BookReview trials complete, and strict
   audit exits 0 with 3 clean trials and no tainted or coverage-missing trials.

## Stage Report: plan

- DONE: The inline plan maps AC-1 to a concrete `SpacedockSolverAgent.run` prompt-composition test and implementation.
  Evidence: The inline plan names the exact unit test, failing behavior, implementation file, and spec cites for the README-before-task composed instruction.
- DONE: The inline plan maps AC-2/AC-3 to concrete generator/spec and solver README edits.
  Evidence: The inline plan names the generator, checked-in smoke spec, generator test, and solver README edits required for structured workspace service details, `hints: false`, and no-probing rules.
- DONE: The inline plan names validation commands, including the BookReview score/audit rerun for AC-4.
  Evidence: The inline plan includes focused unit pytest commands plus the generated BookReview freeze/run/score/audit command sequence.

### Summary

Added an inline implementation plan because the FO sizing decision marked this
as a tiny task. No separate plan document was created; the plan keeps validation
portable by using repo-relative scratch paths and a caller-supplied data root.

## Stage Report: implementation

- DONE: `SpacedockSolverAgent.run` composes solver workflow README text before task instruction, covered by a focused unit test.
  Evidence: `test_run_sends_solver_workflow_readme_before_task_instruction` fails before the code change and passes after README-before-task composition in `src/razorback/agents/spacedock_solver_v2.py`.
- DONE: Codex DAB generated specs and checked-in smoke spec use `workspace_variant: direct-structured` while preserving `hints: false`, covered by generator tests.
  Evidence: `tests/unit/test_codex_benchmark_spec_generator.py` asserts both emitted DAB specs and `examples/specs/codex-dab-smoke.yaml` use `direct-structured` with `hints: false`.
- DONE: Codex benchmark solver README explicitly forbids Docker/socket/host-network/shell-network probing and package/public-network lookup while solving.
  Evidence: `examples/solver_workflows/codex-benchmark-solver/README.md` now directs solvers to task-local instructions, workspace `README.md`, and `db_config.yaml`, and forbids Docker/socket/host-network/shell-network and package/public-network probing.
- DONE: Focused unit tests pass, and the entity report names the BookReview score/audit rerun still required for validation.
  Evidence: `uv run --frozen pytest tests/unit/test_spacedock_solver_v2_class.py tests/unit/test_codex_benchmark_spec_generator.py -q` passed with `13 passed`; the generated BookReview freeze/run/score/audit rerun remains required in validation.

### Summary

Implemented PKG-34 by injecting the solver workflow README into the inner runtime prompt before task text, changing Codex DAB generated/smoke specs to structured workspaces without enabling DAB hints, and tightening the Codex benchmark workflow no-probing rules. Live BookReview score/audit validation was not run in this stage; validation still needs the caller-supplied DAB data root and the generated BookReview rerun to prove 3 clean strict-audit trials.

## Stage Report: validation

- DONE: Validation independently verifies AC-1 through AC-3 with tests/review and confirms `hints: false` is preserved.
  Evidence: `uv run --frozen pytest tests/unit/test_spacedock_solver_v2_class.py tests/unit/test_codex_benchmark_spec_generator.py -q` passed with `13 passed`; review confirmed README-before-task prompt composition, `direct-structured`, and `hints: false`.
- DONE: Validation runs the generated BookReview Codex rerun and captures score output showing all 3 trials complete.
  Evidence: `.runs/pkg34/bookreview-codex/codex-dab-bookreview/32e361679554f5e4`; `rk score` reported `n_total=3`, `n_completed=3`, `n_pass=3`, and `stratified_pass_at_1=1.0`.
- DONE: Validation runs strict audit on that rerun and captures whether it is clean or tainted, with a clear gate decision.
  Evidence: `rk audit --policy strict` reported `clean=3`, `coverage_missing=0`, and `tainted=0`; gate decision is PASS.

### Summary

Validation independently reran the focused unit suite, reviewed the implementation against AC-1 through AC-3, generated the BookReview frozen spec from the local DAB data root, and ran the live BookReview Codex rerun. Score and strict audit both pass for the generated job, so PKG-34 is ready to pass the validation gate.
