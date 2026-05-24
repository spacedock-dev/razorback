---
id: et8q8rd845hkn8p2bdhb9k9w
title: DAB full batch Codex explain preflight
status: implementation
source: 2026-05-24 captain directive - explain the DAB full/batch Codex run before launching gpt-5.5/xhigh
started: 2026-05-24T04:29:18Z
completed:
verdict:
score: 0.9
worktree: .worktrees/spacedock-ensign-dab-full-batch-codex-explain-preflight
issue:
pr:
mod-block:
---

## Problem

Before spending a full DAB run, `rk run --explain` should prove the exact
full/batch Codex setup that would be launched: dataset-definition resolution,
batch query mode, solver variant, model/effort, prompt mode, and run
preparation. This is a preflight artifact, not the full score launch.

## Acceptance criteria

**AC-1 - The full DAB batch spec resolves through dataset definitions.**
The explain output shows the DAB dataset definition path or package ref used
for all intended DAB cells, without relying on a hard-coded local DAB root in
Razorback code.
Verified by: a committed or cited `rk run --explain --explain-format json`
artifact records the resolved DAB dataset source and task/cell count.

**AC-2 - Batch mode and Codex solver settings are explicit.**
The explain artifact names `query_mode: batch`, the solver variant
(`minimal`, `structured`, or `spacedock-workflow`), Codex model, and reasoning
effort intended for the full run.
Verified by: JSON inspection of the explain artifact reports the expected
agent kind, runtime, model, effort, prompt mode, and batch mode.

**AC-3 - Explain mode does not launch Harbor or the model.**
The preflight stops before `_job_config.yaml`, Harbor execution, or any model
trace is produced.
Verified by: the worker records the exact command, explain output path, and
absence of new scored run artifacts for that explain invocation.

**AC-4 - The next launch command and blockers are recorded.**
The task report states the exact full-run command to execute next, or lists the
remaining blocker with the failing command/log path.
Verified by: the stage report includes the command and either a green launch
recommendation or a concrete blocker classification.

## Test plan

Run `rk run --explain --explain-format json` against the intended DAB
full/batch Codex spec and inspect the JSON fields that determine run shape.
No full DAB model run is part of this task.

## Out of scope

Executing or scoring the full DAB dataset run.

## Stage Report: plan

- DONE: Plan identifies the intended DAB full/batch spec or how to locate it from dataset definitions.
  Plan doc `docs/razorback-implementation/plans/dab-full-batch-codex-explain-preflight.md` T0/T1 uses `benchmark.dataset: dab@1.0`, no `data_root` identity field, and verifies the plugin definition's 12 datasets / 54 queries.
- DONE: Plan defines exact `rk run --explain --explain-format json` evidence for solver, batch mode, model, effort, and prompt mode.
  Plan T2/T3 gives the exact command and JSON assertions for `query_mode: batch`, `spacedock-workflow`, `spacedock_solver`, `runtime: codex`, `model: gpt-5.5`, `reasoning_effort: xhigh`, and `spacedock-codex-first-officer`.
- DONE: Plan preserves the no-Harbor/no-model boundary and records the next full-run command or blocker.
  Plan T4 asserts no `_job_config.yaml`, `trials/`, model events, result, summary, score, or audit artifacts; T5 records the next `rk run` command or blocker class/log path.

### Summary

Wrote the standard separate plan doc for the four-AC preflight task. The implementation plan is evidence-only: create/freeze a run-local full DAB Codex spacedock spec, run explain JSON, inspect fields, prove the filesystem boundary, and stop before any full DAB model run.
