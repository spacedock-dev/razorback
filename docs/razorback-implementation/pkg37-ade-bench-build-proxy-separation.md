---
id: 76e3zhyq7wvk89zq4eqay30x
title: PKG-37 — ade-bench Docker build proxy separation
status: implementation
source: Goal 4 smoke failure 2026-05-21 — Docker build inherited runtime egress block
started: 2026-05-21T15:24:59Z
completed:
verdict:
score: 0.88
worktree: .worktrees/spacedock-ensign-pkg37-ade-bench-build-proxy-separation
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

## Stage Report: implementation

- DONE: A focused unit test proves build commands remove `HTTP_PROXY`/`HTTPS_PROXY` from the compose subprocess env.
  `uv run pytest tests/unit/test_docker_environment_proxy_separation.py tests/unit/test_translate_spacedock_solver_import_path.py -q` -> 4 passed; build subprocess env also asserts lowercase proxy keys and no-proxy keys are absent.
- DONE: A focused test proves normal exec/runtime env still includes `HTTP_PROXY=http://127.0.0.1:1` and the OpenAI no-proxy list.
  `tests/unit/test_docker_environment_proxy_separation.py::test_runtime_exec_keeps_proxy_block_env` asserts runtime `exec` emits `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY` with `api.openai.com`.
- DONE: Translator tests prove v2 solver jobs emit the wrapper environment import path and preserve the freeze mount.
  `tests/unit/test_translate_spacedock_solver_import_path.py::test_spacedock_solver_v2_uses_proxy_separated_environment` asserts `EnvironmentConfig.import_path`, `delete=False`, proxy env, and `/razorback-freeze` mount.

### Summary

Added `razorback.environments.docker.ProxySeparatedDockerEnvironment`, a Harbor DockerEnvironment subclass that strips proxy-related `PROXY_BLOCK_ENV` keys from `docker compose build` subprocess env while leaving runtime `exec` env merging intact. Updated v2 solver translation to use the wrapper import path and preserve the existing `delete=False`, runtime proxy env, and sealed freeze bind mount.

Focused verification run: `uv run pytest tests/unit/test_docker_environment_proxy_separation.py tests/unit/test_translate_spacedock_solver_import_path.py tests/unit/test_spacedock_solver_v2_lifecycle.py -q` -> 16 passed, 4 Harbor deprecation warnings.
