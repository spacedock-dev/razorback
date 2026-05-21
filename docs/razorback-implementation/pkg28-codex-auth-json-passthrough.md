---
id: rp427jekvxca47zj5k4zssy2
title: PKG-28 — Codex auth.json passthrough for spacedock_solver_v2
status: backlog
source: Goal 3/4 unblocker 2026-05-21 — local Codex CLI is authenticated via auth.json while Razorback currently requires OPENAI_API_KEY
started:
completed:
verdict:
score: 0.95
worktree:
issue:
pr:
mod-block:
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

