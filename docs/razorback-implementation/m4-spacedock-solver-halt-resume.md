---
id: 8c53p5jxwwckfkqzm3mg5drs
title: M4 — SpacedockSolverAgent with halt-resume
status: implementation
source: design §8
started: 2026-05-19T08:23:23Z
completed:
verdict:
score: 0.7
worktree: .worktrees/spacedock-ensign-m4-spacedock-solver-halt-resume
issue:
pr:
mod-block:
---

## Problem

Staged agent with halt-resume capability. `SpacedockSolverAgent`
reads `stages`, `seed.{default,per_dataset}`, `prompts`, and
`tools_allowed` from `AgentConfig.kwargs` (validated by
razorback's pydantic registry before `AgentConfig` is constructed,
§6.2), commits the agent workspace to a private git repo at
`logs_dir/agent_freeze/.git` at each freeze point, and refuses to
resume when sealed-stage inputs (model, sampling, prompt content)
do not match the seed's frozen spec (§6.2 third bullet). Per-stage
cost rollups land in `logs_dir/agent_freeze/phase_stats.json`
(§6.8). End-to-end against DAB through harbor. See §8.M4 and §6.2,
§6.8.

## Acceptance criteria

**AC-1 — Halt-resume against a mismatched seed exits with
`SeedMismatchError` (exit code 20).**
Verified by: an integration fixture where `agent.prompt_file`
content hash differs between the seed run and the resume spec;
the agent exits with `SeedMismatchError`, the CLI exit code is
20, and the run-dir's `crash.json` (or equivalent) records the
mismatched fields per the §3.2 contract.

**AC-2 — Razorback's pydantic registry validates the agent
kwargs before harbor sees them.**
Verified by: a unit test feeds a spec whose `agent.stages` block
violates the registered schema and asserts a typed `SpecError`
is raised with the offending field path; harbor's `AgentConfig`
is never constructed.

**AC-3 — Prompt files are content-hashed at freeze time and
pinned into `spec.frozen.yaml`; the agent reads content from
the frozen spec, not the file path.**
Verified by: a unit test mutates a prompt file between freeze
and run; the agent refuses with a hash-drift error citing the
pinned hash in the frozen spec.

**AC-4 — `agent_freeze/.git` is a real git repo committed by the
agent at each stage boundary, sealed against the host's working
copy.**
Verified by: an integration test that runs the agent through a
freeze point asserts `logs_dir/agent_freeze/.git` is a valid
repo (`git rev-parse --git-dir` works inside it) and that the
HEAD commit captures the agent's workspace at the freeze
boundary.

**AC-5 — `phase_stats.json` is written into
`logs_dir/agent_freeze/` at each stage boundary with the
schema in §6.8.**
Verified by: a unit test inspects a fixture run-dir and asserts
`phase_stats.json` has `model`, `analyze`, `verify` keys each
with `tokens_in`, `tokens_out`, `cost_usd`, `wallclock_s`. The
schema cite is §6.8.

**AC-6 — `tools_allowed` enforcement at agent setup scrubs the
environment and filters MCP servers.**
Verified by: a unit test runs setup with a non-empty
`tools_allowed` list and asserts the disallowed MCP servers are
filtered out of the agent's settings.json (matching the
`DISALLOWED_TOOLS` discipline at `run_experiment.py:1531-1549`).

**AC-7 — Razorback never writes inside harbor's `agent/`
directory; all razorback-owned state lives under
`logs_dir/agent_freeze/`.**
Verified by: a code-level check (`grep -rn 'agent_dir' src/
razorback/agents/` returns no writes) and an integration test
inspecting a finished trial dir confirms `agent_freeze/` is the
only razorback subtree.

## Test plan

- **Unit tests:** registry schema validation; prompt content
  hashing + drift detection; phase_stats schema; tools_allowed
  MCP filtering.
- **Integration test:** halt-resume against bookreview through
  harbor's docker environment. One trial seeds, second trial
  resumes; mutation of a sealed input is exercised in a separate
  test.
- **Acceptance command:** `uv run rk run examples/specs/
  bookreview-spacedock-seed.yaml` followed by `uv run rk run
  examples/specs/bookreview-spacedock-resume.yaml`.

## Out of scope

- `CodexCliAgent` — separate milestone.
- Provenance resolution across the agent's full freeze surface
  — §M5 lands provenance.
- Full DAB scoring — §M5.
- `runs diff` halt-resume seed-mismatch refusal — §M6.

## Stage Report: plan

- DONE: Plan steps map 1:1 to the 7 ACs in the M4 entity body, each with the §-cite that governs it (§6.2 BaseAgent + registry, §6.4 prompts, §6.8 phase_stats.json and per-stage cost, §3.2 SeedMismatchError = exit code 20, §6.3 logs_dir/agent_freeze/ ownership). AC↔task map at the top of the plan.
  AC↔task map table at `plans/m4-spacedock-solver-halt-resume.md` top; each AC names its §-cite. AC-1 → Task 1; AC-2 → Task 2; AC-3 → Task 3; AC-4 → Task 5; AC-5 → Tasks 5+6; AC-6 → Task 4; AC-7 → Task 7.
- DONE: The riskiest contract for M4 — that the seed-mismatch refusal (AC-1) actually fires when a sealed-stage input differs between seed and resume — is plan Task 1, BEFORE the staged-execution / git-freeze machinery scaffolds. The fixture explicitly mutates `agent.prompt_file` content hash between seed and resume specs; the test asserts the agent exits SeedMismatchError before reaching harbor.Job.create, and the CLI exit code is 20.
  Task 1 lands two tests (in-process `test_spacedock_seed_mismatch.py` and CLI `test_spacedock_cli_seed_mismatch_exit_code.py`) before Tasks 2-7 scaffold the registry, freeze, setup(), run(), and git-freeze machinery. The in-process test monkeypatches `harbor.Job.create` to raise if invoked — proving the refusal happens before harbor I/O.
- DONE: The plan inherits the M3 BaseAgent pattern from docs/razorback-implementation/plans/m3-claude-cli-agent.md (registry/schema/required-env/env-scrub) and adds M4-specific scope: stages config in AgentConfig.kwargs (validated by the registry), per-trial git-freeze repo at logs_dir/agent_freeze/.git, phase_stats.json schema, content-hashed prompts pinned into spec.frozen.yaml. Cross-references the M3 plan's relevant tasks rather than duplicating them.
  M3 cross-references: registry pattern (M3 Task 2), proxy block (M3 Task 5), auth loader (M3 Task 3), `claude_invoke.py` extracted from M3 Task 4. M4-specific divergence (sealed_hash extends M3's "content-hash one prompt" to "model + sampling + stages + every prompt") explicitly named in plan preamble under "M4 sealed-input definition".

### Summary

Plan written to `docs/razorback-implementation/plans/m4-spacedock-solver-halt-resume.md` on `main` (10 tasks, ~1500 lines). Task 1 lands the riskiest contract (SeedMismatchError + exit code 20) before any scaffolding; Tasks 2-7 add registry/freeze/setup/run/git-freeze/phase_stats/AC-7-audit one AC at a time, TDD throughout; Task 8 wires the translator and end-to-end halt-resume integration test against bookreview. The §6.8 phase_stats.json schema is locked in Task 6 with a public `assert_phase_stats_schema` helper for M5's aggregator to import. The M4 sealed_hash divergence from M3's prompt-only hashing (M4 seals model + sampling + stages + per-stage prompts) is explicitly named in the preamble. No worktree created — plan stage stays on `main` per Spacedock discipline.
