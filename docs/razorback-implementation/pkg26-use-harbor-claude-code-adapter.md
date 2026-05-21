---
id: kzd3zabn0magv2ezxrdvtd8a
title: PKG-26 — route claude-code through harbor's adapter; per-variant agent kinds for goal1
status: plan
source: Goal 1 RESUME T0 probe 2026-05-21 (commit 565daf2 on .worktrees/spacedock-ensign-goal1-resume-spacedock-first) — cost_usd=null on paid API; captain directive 2026-05-21 ("use upstream as much as possible, we don't want to drift too much from it" + "we also need to be able to do halt/resume, and our skill injection for spacedock")
started: 2026-05-21T15:38:07Z
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
mod-block:
---

## Problem

Razorback's matrix specs route ALL agent runs through
`razorback.agents.claude_cli:ClaudeCliAgent` (118 lines), a
lightweight wrapper that:
- Calls `claude -p <instruction>` and **discards the output**
- Does NOT emit `cost_usd` (telemetry gap)
- Does NOT write `claude-output.jsonl` (audit gap — `rk audit`
  taint scanner at `src/razorback/audit/taint.py:46` looks for
  exactly this file)
- Does NOT support halt/resume or skill injection (spacedock
  workflow primitives)

Harbor 0.6.6 ships `harbor.agents.installed.claude_code:ClaudeCode`
(1155 lines, upstream-maintained) that uses
`--output-format=stream-json --print`, parses `total_cost_usd`
(line 491), harvests per-task session JSONL transcripts from
`<project_root>/projects/<task>/*.jsonl` (lines 167-196), and is
the canonical Claude Code adapter for harbor benchmarks. We
should use it.

Razorback already has `spacedock_solver_v2`
(`src/razorback/agents/spacedock_solver_v2.py`) for the spacedock
variant's specific needs: halt/resume, skill injection, cost
telemetry. It is the right shape for the paper's spacedock
workflow architecture.

The Goal 1 matrix as previously dispatched (under both the
archived partial ship AND the in-flight RESUME) **runs all 3
variants through claude-cli**, which means:
1. Spacedock variant is NOT actually using the paper's spacedock
   architecture (no skill injection, no halt/resume)
2. Direct-minimal + direct-structured variants lose cost +
   audit-trail telemetry

PKG-26 corrects both:
- Spacedock variant → `agent.kind: spacedock_solver_v2`
- Direct-minimal + direct-structured → `agent.kind: claude-code`
  (routes to harbor's adapter)
- razorback's claude-cli kind stays available for users who
  explicitly want the minimal wrapper, but it's NOT what the
  matrix uses

This corrects ML reviewer F8 (the partial-ship caveat that
"variants differ by ~4 lines of prose framing") — variants now
differ by AGENT ARCHITECTURE for spacedock vs. direct, matching
the paper's design intent.

## Acceptance criteria

**AC-1 — `ClaudeCodeAgentBlock` spec block exists.**
A new agent block in `src/razorback/spec/schema.py` mirrors
`ClaudeCliAgentBlock` but routes through harbor's
`ClaudeCode` adapter. Accepts model, sampling, tools_allowed,
mcp_servers, skills_dir (per harbor's adapter signature).
Verified by: a unit test asserts the block schema + a frozen
spec round-trips correctly.

**AC-2 — Translator routes `claude-code` kind.**
`src/razorback/translate.py:_build_agent` adds a branch for
`ClaudeCodeAgentBlock` that constructs an `AgentConfig` pointing
at `harbor.agents.installed.claude_code:ClaudeCode`. The kwargs
shape matches harbor's `ClaudeCode.__init__` signature (not
razorback's ClaudeCliAgent signature — they differ).
Verified by: a unit test asserts the translator emits the
correct `AgentConfig` for a `ClaudeCodeAgentBlock` spec; an
integration test runs a live trial against airbnb001 or
bookreview-q1 and asserts that the trial's run-dir contains a
non-empty `claude-output.jsonl` AND `summary.json` includes a
non-null `cost_usd`.

**AC-3 — Goal 1 matrix specs are regenerated per-variant.**
`examples/drivers/generate-dab-paper-matrix-specs.py` emits:
- spacedock variant cells → `agent.kind: spacedock_solver_v2`
- direct-minimal + direct-structured cells →
  `agent.kind: claude-code`
The generator preserves the spacedock-first variant ordering
established by goal1-resume's T1.
Verified by: regenerated frozen spec for spacedock/bookreview
has `agent.kind: spacedock_solver_v2`; spec for
direct-minimal/bookreview has `agent.kind: claude-code`.

**AC-4 — Goal 1 matrix dispatch produces cost + audit artifacts.**
A live `rk run` against ONE re-frozen goal1 cell (spacedock or
direct-minimal — either kind) produces a run-dir whose
`summary.json` has non-null `cost_usd` AND whose `claude-output.jsonl`
is present and non-empty.
Verified by: live `rk run` against
examples/specs/goal1/spacedock/bookreview.frozen.yaml (after
PKG-26 regen). Documented in the validation report.

**AC-5 — Razorback's `claude_cli` adapter stays available but
deprecated for matrix use.** Existing
`ClaudeCliAgentBlock`-typed specs still work; the matrix
generator simply stops emitting `ClaudeCliAgentBlock`. The
adapter's tests remain green; no breaking changes to existing
callers.
Verified by: existing test suite for `claude_cli.py` stays green;
matrix generator's output uses claude-code or
spacedock_solver_v2 only.

## Test plan

- **Unit:** new `tests/unit/test_claude_code_agent_block.py` for
  spec schema + translator branch; extends
  `test_generate_matrix_specs.py` (or equivalent) for per-variant
  kind selection.
- **Integration:** live `rk run` against one goal1 cell of each
  agent kind (spacedock_solver_v2 + claude-code) asserts cost
  and audit artifacts present.
- **Acceptance:** Goal 1 RESUME T0 re-runs successfully under
  the new spec; cost_usd is non-null; `claude-output.jsonl` is
  scanned by `rk audit`.

## Out of scope

- Removing razorback's `claude_cli.py` entirely (deprecation only;
  removal is a follow-up after a deprecation window).
- ade-bench / Goal 2 matrix spec generator updates — Goal 2's
  matrix uses Haiku; will need a similar PKG entity after PKG-23
  ships and Goal 2 resumes. Filed as PKG-26 followup if needed.
- Backporting cost telemetry into razorback's claude_cli.py —
  captain directive is to use upstream, not parallel-implement.
- Multi-trial / N>1 retry semantics — PKG-26 changes the agent
  kind only; trial concurrency and retry logic are unchanged.

## Depends on

- harbor 0.6.6 `harbor.agents.installed.claude_code:ClaudeCode`
  (installed via dependencies)
- `spacedock_solver_v2` (already in razorback; has halt/resume +
  skill injection)
- Goal 1 RESUME is currently HOLDING on this; T0 done + T1 done
  + T2 paused.

## Resume hook

After PKG-26 merges:
1. Goal 1 RESUME ensign re-runs T1 (regenerate specs with the
   per-variant agent kinds) — same worktree, same branch.
2. Goal 1 RESUME T2 dispatches the 36-cell matrix; cost_usd
   non-null; audit traces present.
3. Goal 1's variant comparison is now meaningful: spacedock's
   architecture differs from direct's by more than prose.
