---
id: vxt2v1vxmp38rd9m63wrysp2
title: PKG-31 — allow relative out-root for Codex spec generation
status: done
source: Goal 3 DAB generation attempt — relative `--out-root runs/...` wrote specs then crashed while rendering paths
started: 2026-05-21T08:55:00Z
completed: 2026-05-21T08:56:00Z
verdict: PASSED
score: 1.00
worktree:
issue:
pr:
mod-block:
---

## Problem

The Codex benchmark generator accepts `--out-root`, but a relative
path under the repo crashes when printing emitted files because
`Path.relative_to()` compares a relative path with an absolute repo
root. Goal 3 needs to generate untracked specs under `runs/`.

## Acceptance Criteria

- Relative `--out-root` under the repo prints a repo-relative path.
- Absolute `--out-root` under the repo prints a repo-relative path.
- Output paths outside the repo still print as absolute paths.

## Stage Report

- DONE: Added a display helper for emitted spec paths.
- DONE: Added unit coverage for relative, absolute in-repo, and external output paths.
