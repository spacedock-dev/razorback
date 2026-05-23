---
id: z6kwy5t2dz3rnrcyctz2cfx0
title: PKG-32 — disable Codex web search and shell egress for v2 benchmark runs
status: done
source: Goal 3 bookreview probe — Codex used native `web_search` during DAB q3, invalidating the run
started: 2026-05-21T09:16:00Z
completed: 2026-05-21T09:25:00Z
verdict: PASSED
score: 1.00
worktree:
issue:
pr:
mod-block:
---

## Problem

The first DAB Codex cell reached live task execution but the trace
used native `web_search`. That makes the score indefensible under
the DAB leak policy. Codex CLI supports `web_search = "disabled"` in
config, and Razorback already has proxy/offline env constants for
shell-level egress blocking.

## Acceptance Criteria

**AC-1 — Codex native web search is disabled.**
The Razorback Codex runtime always appends a Codex CLI config flag
that disables native web search.
Verified by: unit test on the constructed inner agent flags and a
live smoke trace with no `web_search` items.

**AC-2 — Shell HTTP egress is blocked for v2 Harbor environments.**
Spacedock solver v2 JobConfig environments carry the proxy/offline
block env in addition to the freeze mount.
Verified by: translator test asserts representative proxy/offline
keys in `cfg.environment.env`.

**AC-3 — DAB smoke no longer uses web search.**
The bookreview probe can be rerun without native `web_search` in the
Codex trace. Any remaining failure is classified separately.

## Depends on

- `pkg30-codex-supported-default-model`
- `pkg31-codex-generator-relative-out-root`

## Stage Report: implementation

- DONE: Codex native web search is disabled.
  `RazorbackCodex.build_cli_flags()` appends `-c 'web_search="disabled"'`; the Harbor smoke job log shows that exact flag and the smoke trace contains no `web_search` items.
- DONE: Shell HTTP egress is blocked for v2 Harbor environments.
  `_environment_config()` now includes the proxy/offline env for Spacedock solver v2 jobs, and the translator test asserts `HTTP_PROXY` plus `HF_DATASETS_OFFLINE`.
- DONE: Setup-time installs remain possible.
  Git bootstrap and Codex installer commands clear proxy env only for their package-install phase; the benchmark agent instruction run keeps the egress block.

### Validation

- `uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_spacedock_solver_v2_lifecycle.py tests/integration/test_v2_freeze_dir_mechanism.py -q` passed: 28 tests.
- `uv run rk freeze examples/specs/_codex-smoke-v2.yaml --allow-missing` exited 0.
- `uv run rk run examples/specs/_codex-smoke-v2.frozen.yaml --runs-dir runs/pkg32-codex-egress-guard-smoke --allow-plugin-drift --allow-alias-drift` exited 0 with one trial, zero exceptions, and reward `1.0`.
