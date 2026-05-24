---
id: et8q8rd845hkn8p2bdhb9k9w
title: DAB full batch Codex explain preflight
status: backlog
source: 2026-05-24 captain directive - explain the DAB full/batch Codex run before launching gpt-5.5/xhigh
started:
completed:
verdict:
score: 0.9
worktree:
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
