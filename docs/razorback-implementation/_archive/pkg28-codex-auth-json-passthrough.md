---
id: rp427jekvxca47zj5k4zssy2
title: PKG-28 — Codex auth.json passthrough for spacedock_solver_v2
status: done
source: Goal 3/4 unblocker 2026-05-21 — local Codex CLI is authenticated via auth.json while Razorback currently requires OPENAI_API_KEY
started: 2026-05-21T08:12:39Z
completed: 2026-05-21T08:26:09Z
verdict: PASSED
score: 0.95
worktree: 
issue:
pr:
mod-block:
archived: 2026-05-21T08:26:15Z
---

## Problem

PKG-26 made the Codex runtime adapter functional, but `rk run`
currently refuses before Harbor dispatch unless `OPENAI_API_KEY`
exists in the project `.env`. That blocks benchmark runs on machines
where Codex CLI is already logged in with its standard `auth.json`
file.

Harbor's installed Codex agent already supports auth-file injection:
`CODEX_AUTH_JSON_PATH=<path>` uploads that auth file into the trial
container and links it into `CODEX_HOME/auth.json`. Razorback needs
to resolve and pass that path through `AgentConfig.env` when no API
key is configured.

## Acceptance criteria

**AC-1 — Codex auth resolves from API key or auth.json.**
`resolve_codex_auth` keeps the existing `OPENAI_API_KEY` path, but
falls back to a caller-supplied or default Codex `auth.json` file
when present. The returned env contains `CODEX_AUTH_JSON_PATH` for
auth-file mode and does not require `OPENAI_API_KEY`.
Verified by: unit tests cover `.env` API-key precedence, explicit
`CODEX_AUTH_JSON_PATH`, and default home auth-file fallback.

**AC-2 — `rk run` no longer preflights out when Codex auth.json is
available.**
For `spacedock_solver_v2` with `runtime: codex`, translation passes
`home` through to Codex auth resolution so the user's Codex auth file
can be discovered before Harbor stages its synthetic HOME.
Verified by: a translator test builds a Codex v2 job config with a
temporary home containing `.codex/auth.json` and asserts
`AgentConfig.env["CODEX_AUTH_JSON_PATH"]` points at that file.

**AC-3 — Missing Codex credentials still fail clearly.**
If neither `OPENAI_API_KEY` nor a readable auth file is present,
Razorback raises `AuthDiscoveryError` with a portable message naming
the supported credential options.
Verified by: unit test for missing credentials.

**AC-4 — Smoke run reaches Harbor/Codex execution boundary.**
With local Codex auth configured, the Codex smoke spec should pass
the Razorback auth preflight. If Docker/Harbor execution blocks
later, the failure must be a later-stage infrastructure or benchmark
failure, not `AuthDiscoveryError`.
Verified by: `uv run rk freeze examples/specs/_codex-smoke-v2.yaml
--allow-missing` and `uv run rk run
examples/specs/_codex-smoke-v2.frozen.yaml --runs-dir
runs/pkg28-codex-auth-smoke --allow-plugin-drift --allow-alias-drift`
does not fail with `AuthDiscoveryError` when Codex auth.json exists.

## Depends on

- `pkg26-codex-spacedock-solver-runtime` — shipped.

## Stage Report: implementation

- DONE: `resolve_codex_auth` supports API-key precedence, explicit `CODEX_AUTH_JSON_PATH`, and default home auth.json fallback without embedding machine-specific paths in tracked fixtures.
  Evidence: `tests/unit/test_claude_cli_auth_dotenv_only.py` covers `.env` API-key precedence over home auth.json, explicit temp `CODEX_AUTH_JSON_PATH`, default temp `<home>/.codex/auth.json`, and portable missing-credentials text.
- DONE: `spacedock_solver_v2` translation passes Codex auth-file env through to Harbor `AgentConfig.env` and tests the missing-credentials failure path.
  Evidence: `tests/integration/test_v2_freeze_dir_mechanism.py` asserts Codex v2 `AgentConfig.env["CODEX_AUTH_JSON_PATH"]` from temp `<home>/.codex/auth.json` and raises `AuthDiscoveryError` when all credential sources are absent.
- DONE: Stage report records exact test commands and whether `_codex-smoke-v2` reaches past Razorback `AuthDiscoveryError` in this environment.
  Evidence: commands recorded below; `_codex-smoke-v2` reached Harbor and failed later with `SpacedockSolverAgentError` (`git init` rc=127), not `AuthDiscoveryError`.

### Summary

Implemented Codex auth-file discovery in `src/razorback/agents/auth.py` and wired `home` through the Codex branch in `src/razorback/translate.py`; Harbor-facing auth remains on `AgentConfig.env` only. Verification commands: `uv run pytest tests/unit/test_claude_cli_auth_dotenv_only.py tests/integration/test_v2_freeze_dir_mechanism.py -q` (`19 passed`), `uv run ruff check src/razorback/agents/auth.py src/razorback/translate.py tests/unit/test_claude_cli_auth_dotenv_only.py tests/integration/test_v2_freeze_dir_mechanism.py` (`All checks passed`), `uv run pytest tests/unit -q` (`481 passed`), `uv run rk freeze examples/specs/_codex-smoke-v2.yaml --allow-missing` (exit 0), and `uv run rk run examples/specs/_codex-smoke-v2.frozen.yaml --runs-dir runs/pkg28-codex-auth-smoke --allow-plugin-drift --allow-alias-drift` (exit 0; Harbor reported one `SpacedockSolverAgentError` after auth preflight).

## Stage Report: validation

- DONE: Validation independently verifies AC-1 through AC-3 with exact unit/integration commands and reviews that auth file contents are never written to tracked files.
  Evidence: `uv run pytest tests/unit/test_claude_cli_auth_dotenv_only.py tests/integration/test_v2_freeze_dir_mechanism.py -q` returned `19 passed`; `uv run pytest tests/unit -q` returned `481 passed`; tracked-file token scan found only an existing sentinel fixture.
- DONE: Validation independently attempts AC-4 smoke run and confirms any failure is past `AuthDiscoveryError`, recording the exact later-stage failure.
  Evidence: freeze exited 0; run exited 0 and reported `SpacedockSolverAgentError: resume restore via git checkout failed at <worktree>/runs/pkg28-codex-auth-smoke/_codex-smoke-v2/_razorback/freeze/cdfe61ef1efa1d4f4504af3aaa3061b1 (rc=127)`.
- DONE: Validation report gives a clear PASS/REJECT gate decision with blocking findings separated from non-blocking findings.
  Evidence: `docs/razorback-implementation/validation/pkg28-codex-auth-json-passthrough.md` recommends APPROVE with zero blocking findings and one non-blocking UX note.

### Summary

AC-1 through AC-4 PASS. The smoke run reached Harbor/Codex execution and failed after auth discovery with `SpacedockSolverAgentError`, not `AuthDiscoveryError`; run-dir artifacts include the expected manifest, summary, result, provenance, job config, event log, and per-trial files. Gate decision: APPROVE to `done`.
