---
id: 93fpren96j0by11d3y5fccs1
title: M3 — ClaudeCliAgent end-to-end
status: implementation
source: design §8
started: 2026-05-19T07:58:58Z
completed:
verdict:
score: 0.85
worktree: .worktrees/spacedock-ensign-m3-claude-cli-agent
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

## Stage Report: plan

- DONE: Plan steps map 1:1 to the 7 ACs in the M3 entity body, each with the design-doc §-cite that governs it (§6.2 BaseAgent subclasses + registry, §6.4 prompt content hashing, §9.2 tools_allowed contract). AC↔task map table at the top of the plan.
  AC↔task map table at lines 79-87 of `docs/razorback-implementation/plans/m3-claude-cli-agent.md`; cites §6.2, §6.5, §9.2 plus the verbatim `run_experiment.py` line ranges. Note: §6.4 (prompt content hashing) is explicitly deferred to M5 per the design doc's prompt-freeze wording; M3 ships no prompt_file freeze — the plan calls this out in Task 2's `ClaudeCliAgentConfig` (prompt_file accepted, content-hashing not yet enforced).
- DONE: The riskiest contract for M3 — that `claude -p` actually runs inside harbor's docker container with the right env vars and reaches the Anthropic API past harbor's network isolation — is plan Task 1 as a live nop-or-claude-CLI smoke against bookreview, BEFORE any registry/schema scaffolding lands. If the claude-CLI-in-container path fails (auth mode mismatch, proxy block too tight, harbor's required-env declaration missing a field), STOP and escalate; do NOT scaffold around it.
  Task 1 sits before Tasks 2-6; lines 159-307 of the plan. Failure modes enumerated under "Step 2: Run the smoke" with explicit STOP-and-escalate directives.
- DONE: The plan reads /Users/clkao/git/dataagentbench/benchmark/lib/run_experiment.py lines 1440-2046 verbatim and inherits the OAuth/API-key precedence rule (ANTHROPIC_API_KEY from .env via dotenv_values first, fall back to CLAUDE_CODE_OAUTH_TOKEN via read_claude_token; never both, never from os.environ). The plan cites the source-file line ranges and adapts the discipline to harbor's required-env declaration mechanism without redesigning it.
  Task 3 implements `razorback.agents.auth.resolve_claude_auth` citing `run_experiment.py:1897-1917` and `:1993-2003`; Task 5's `razorback.agents.proxy` copies `:1497-1525` verbatim. AC-3's six tests (`test_claude_cli_auth_dotenv_only.py`) include the `os.environ` negative-path assertion that mirrors the entity's AC-3 verbatim.

### Summary

Wrote a TDD-shaped 8-task plan for M3 ClaudeCliAgent end-to-end. Task 1 is a risk-first claude-CLI-in-harbor-docker smoke that runs one bookreview query through a hand-rolled BaseAgent subclass, asserting the verifier emits a numeric reward — before any registry/schema/agent-class code lands. Auth, proxy-block, and required-env discipline are inherited verbatim from `dataagentbench/benchmark/lib/run_experiment.py:1440-2046` and `solve.sh:105`; harbor's `EnvironmentConfig.env` mechanism is the declaration surface for AC-1 and AC-7, with razorback resolving auth itself (via `dotenv_values`) to avoid the `os.environ` source AC-3 forbids. Plan lives at `docs/razorback-implementation/plans/m3-claude-cli-agent.md` on `main`.
