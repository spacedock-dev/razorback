---
id: 93fpren96j0by11d3y5fccs1
title: M3 — ClaudeCliAgent end-to-end
status: plan
source: design §8
started: 2026-05-19T07:58:58Z
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
mod-block:
---

## Problem

First custom `BaseAgent` subclass: `ClaudeCliAgent` wraps the
`claude -p` CLI. Implements `setup()` (env scrub plus token
injection through harbor's required-env declaration), `run()`
(one CLI invocation per dataset), and `supported_sampling()`
returning `{"temperature"}` only (Anthropic does not honor seed).
Wired through harbor's docker environment against the M2 DAB
adapter. Produces a non-zero score on bookreview. See §6.2 and
§8.M3.

`claude -p` auth pattern is inherited from
`/Users/clkao/git/dataagentbench/benchmark/lib/run_experiment.py`
(see lines 1440-2010): two modes, `ANTHROPIC_API_KEY` (preferred,
from project-root `.env` via `dotenv_values`) or
`CLAUDE_CODE_OAUTH_TOKEN` (read from `~/.claude/...`). The chosen
token is forwarded into the harbor container via harbor's `env`
block on `AgentConfig` (and surfaced via harbor's settings.json
mechanism for secret hygiene if applicable), so it never appears
in `docker inspect Config.Env`.

## Acceptance criteria

**AC-1 — `ClaudeCliAgent` declares its required env vars via
harbor's required-env mechanism.**
Verified by: a unit test inspects the agent class's required-env
declaration and asserts it lists either `ANTHROPIC_API_KEY` or
`CLAUDE_CODE_OAUTH_TOKEN` (alternation, not both required).

**AC-2 — `setup()` scrubs env, injects exactly the chosen auth
token, and never co-mingles both.**
Verified by: a unit test exercises `setup()` with both env vars
present and asserts only `ANTHROPIC_API_KEY` reaches the agent
process (precedence rule from `run_experiment.py:1995-2003`); a
second test asserts `CLAUDE_CODE_OAUTH_TOKEN` is injected when
only it is present.

**AC-3 — Auth tokens are loaded from project-root `.env` via
`dotenv_values`, not from `os.environ` directly.**
Verified by: a unit test using `monkeypatch` to set a process-env
value confirms the agent does NOT pick it up unless it is also
declared in `.env` — matches the
`run_experiment.load_env_api_key()` discipline.

**AC-4 — `version()` returns the `claude` CLI version reported by
`claude --version`.**
Verified by: a unit test mocks `subprocess.run("claude
--version")` and asserts the parsed string flows through
`version()`.

**AC-5 — `supported_sampling()` returns exactly
`{"temperature"}`.**
Verified by: a unit test asserts the returned set is
`{"temperature"}` — no `top_p`, no `seed`.

**AC-6 — End-to-end bookreview run produces a non-zero score.**
Verified by: `uv run rk run examples/specs/bookreview-
claude.yaml` against the real `claude` CLI produces a
`summary.json` whose bookreview pass@1 is strictly greater than
0.0. (One trial per query is sufficient; the AC is "non-zero",
not "matches a baseline".)

**AC-7 — The agent runs in harbor's docker environment with the
proxy block from `run_experiment.py:1497-1525`.**
Verified by: a unit test inspecting the spec → JobConfig
translator's output for a claude DAB spec asserts the
`EnvironmentConfig.env` block contains the proxy lock-down
(`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` exempting anthropic +
statsig + pypi).

## Test plan

- **Unit tests:** required-env declaration; setup's env-scrub
  precedence; `.env`-only auth discovery; version parsing;
  supported_sampling shape; translator's proxy block.
- **Integration test:** one-trial bookreview run against the
  real claude CLI (cost: a few cents per run). Skipped on CI
  unless `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` is
  present.
- **Acceptance command:** `uv run rk run examples/specs/
  bookreview-claude.yaml` plus the agent's unit tests.

## Out of scope

- `CodexCliAgent` — design ships it but M3 is claude-only; codex
  lands in a follow-up.
- `SpacedockSolverAgent` halt-resume — §M4.
- `tools_allowed` enforcement audit — §9.2 of the design lays out
  the contract; the in-shim enforcement is M3, the audit pass
  against `events.jsonl` is later.
- Full DAB (12 datasets) — §M5.
