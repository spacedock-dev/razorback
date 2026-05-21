---
id: 76e3zhyq7wvk89zq4eqay30x
title: PKG-37 — ade-bench Docker build proxy separation
status: backlog
source: Goal 4 smoke failure 2026-05-21 — Docker build inherited runtime egress block
started:
completed:
verdict:
score: 0.88
worktree:
issue:
pr:
mod-block:
---

## Problem

Harbor-downloaded ade-bench tasks build Docker images from per-task Dockerfiles.
The v2 Spacedock solver currently places the runtime egress-block proxy in the
Harbor Docker environment config, which Docker Compose also inherits during
`build`. The build then cannot pull `python:3.11-slim`, so ade-bench fails before
Codex starts.

## Acceptance criteria

**AC-1 — Docker build commands do not inherit the dead runtime proxy.**
Verified by: a focused unit test covers the Razorback Docker environment wrapper
and proves `HTTP_PROXY`/`HTTPS_PROXY` are removed for `docker compose build`.

**AC-2 — Runtime `environment.exec` commands still receive the egress-block env.**
Verified by: a focused test or integration assertion proves normal exec commands
still pass `HTTP_PROXY=http://127.0.0.1:1` and the existing OpenAI no-proxy list.

**AC-3 — `spacedock_solver_v2` jobs use the wrapper environment.**
Verified by: translator tests assert the emitted `EnvironmentConfig.import_path`
for v2 solver jobs points at the Razorback wrapper and preserves the freeze mount.

## Test plan

Run focused translator/environment tests, then rerun the ade-bench airbnb001 smoke.

## Out of scope

Changing the benchmark score logic or relaxing the runtime agent egress policy is
out of scope. This task only separates build-time network from runtime exec env.
