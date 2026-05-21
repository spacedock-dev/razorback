---
id: kzd3zabn0magv2ezxrdvtd8a
title: PKG-26 — reshape ClaudeCliAgent to subclass harbor's ClaudeCode (close wrapper drift)
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

PKG-26's revised scope (per captain 2026-05-21: "i thought the
intiial design was to subclass it"):

**Reshape `ClaudeCliAgent` to subclass harbor's `ClaudeCode`**
rather than independently implement. The current 118-line wrapper
extends `harbor.agents.base.BaseAgent` directly, paralleling
harbor's 1155-line `ClaudeCode` instead of inheriting from it.
That was a missed design — the initial intent was a subclass.

The subclass gets, for free, all of harbor's:
- `--output-format=stream-json --print` invocation
- `total_cost_usd` parsing (claude_code.py:491)
- Session JSONL harvesting (`<project_root>/projects/<task>/*.jsonl`,
  lines 167-196) — exactly what `rk audit`'s taint scanner
  (`src/razorback/audit/taint.py:46`) needs
- Token usage, cache reads, multi-message accumulation

Razorback overrides ONLY what needs razorback-specific behavior:
- Co-mingled auth check (the `ANTHROPIC_API_KEY` +
  `CLAUDE_CODE_OAUTH_TOKEN` mutual exclusion at lines 52-55)
- `tools_allowed` → harbor's `allowed_tools` kwarg mapping
- `sampling_temperature` → harbor's sampling config

Matrix correction (separate but coupled):
- Spacedock variant → `agent.kind: spacedock_solver_v2` (halt/
  resume + skill injection + cost — razorback's native, no
  upstream equivalent for these features)
- Direct-minimal + direct-structured → `agent.kind: claude-cli`
  (still razorback's kind name; the implementation is now a
  proper ClaudeCode subclass)

This corrects ML reviewer F8 (the partial-ship caveat that
"variants differ by ~4 lines of prose framing") — variants now
differ by AGENT ARCHITECTURE for spacedock vs. direct, matching
the paper's design intent.

## Acceptance criteria

**AC-1 — `ClaudeCliAgent` subclasses `harbor.agents.installed.claude_code.ClaudeCode`.**
`src/razorback/agents/claude_cli.py` changes from
`class ClaudeCliAgent(BaseAgent)` to
`class ClaudeCliAgent(ClaudeCode)`. The class keeps its razorback-
specific surface (the co-mingled-auth check, tools_allowed
mapping, sampling_temperature handling) but inherits ALL of
harbor's behavior (stream-json invocation, cost parsing, session
JSONL harvesting).
Verified by: existing `claude_cli.py` tests stay green; a new
unit test asserts `isinstance(ClaudeCliAgent(...), ClaudeCode)`.

**AC-2 — Translator unchanged; AgentConfig kwargs map cleanly.**
`src/razorback/translate.py:_build_agent`'s `ClaudeCliAgentBlock`
branch continues to point at `CLAUDE_CLI_IMPORT_PATH`. The
kwargs emitted (tools_allowed, sampling_temperature) are mapped
INSIDE `ClaudeCliAgent.__init__` to harbor's expected names
(allowed_tools, etc.) before delegating to `super().__init__(...)`.
Verified by: existing translator tests stay green; a new
integration test runs a live trial against bookreview-q1 and
asserts that the trial's run-dir contains a non-empty
`claude-output.jsonl` AND `summary.json` includes a non-null
`cost_usd`.

**AC-3 — Goal 1 matrix specs split per-variant agent kind.**
`examples/drivers/generate-dab-paper-matrix-specs.py` emits:
- spacedock variant cells → `agent.kind: spacedock_solver_v2`
  (halt/resume + skill injection — razorback's native)
- direct-minimal + direct-structured cells → `agent.kind:
  claude-cli` (the now-subclassed ClaudeCode adapter)
The generator preserves the spacedock-first variant ordering
established by goal1-resume's T1.
Verified by: regenerated frozen spec for spacedock/bookreview
has `agent.kind: spacedock_solver_v2`; spec for
direct-minimal/bookreview has `agent.kind: claude-cli`.

**AC-4 — Goal 1 matrix dispatch produces cost + audit artifacts.**
A live `rk run` against ONE re-frozen goal1 cell of each kind
(spacedock and direct-minimal) produces a run-dir whose
`summary.json` has non-null `cost_usd` AND whose `claude-output.jsonl`
is present and non-empty.
Verified by: live `rk run` against
examples/specs/goal1/spacedock/bookreview.frozen.yaml AND
examples/specs/goal1/direct-minimal/bookreview.frozen.yaml.
Documented in the validation report.

**AC-5 — No drift in razorback-specific behavior.**
The co-mingled-auth check (lines 52-55 of the pre-PKG-26
claude_cli.py) is preserved by the subclass override; existing
tests for that check stay green. Any razorback-specific kwargs
not accepted by ClaudeCode (e.g., the temperature-only
supported_sampling assertion) are still enforced.
Verified by: PKG-9 v2 tools_denied tests stay green; the
co-mingled-auth ClaudeCliAgentError test stays green.

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

## Stage Report: plan

- DONE: Plan resolves the subclass shape: `ClaudeCliAgent(ClaudeCode)` constructor delegates to super().__init__() after the razorback-specific auth check; tools_allowed/sampling kwargs translate to harbor's names.
  Plan §"Task list" T1 specifies the `__init__` body; harbor's `ClaudeCode.__init__` (claude_code.py:104) + `BaseInstalledAgent.__init__` (installed/base.py:147) confirmed as the delegation target; `allowed_tools` is harbor's CLI_FLAG (claude_code.py:80-84) so razorback's `tools_allowed` (list) maps to a CSV string via `super().__init__(allowed_tools="Bash,Read,...")`.
- DONE: Plan size: 5 ACs, primary surface is src/razorback/agents/claude_cli.py + generate-dab-paper-matrix-specs.py + tests. Separate plan doc (multi-file change, non-trivial). AC↔task map.
  Plan written to `docs/razorback-implementation/plans/pkg26-reshape-claude-cli-subclass.md`; AC↔task table embedded in the "Task list" section (T0/T1 → AC-1/AC-5; T2 → AC-2; T3 → AC-3; T4 → AC-2/AC-3/AC-4).
- DONE: Plan TDD-orders: T0 RED unit asserting isinstance; T1 subclass refactor; T2 test cost_usd populated from a live trial; T3 update spec generator for per-variant kinds; T4 live `rk run` of spacedock-variant cell + direct-minimal-variant cell asserts cost + claude-output.jsonl present.
  Plan §"Task list" sequences T0 (RED isinstance + name + supported_sampling) → T1 (GREEN refactor) → T2 (kwarg mapping RED+GREEN) → T3 (spec generator per-variant kind RED+GREEN) → T4 (live `rk run` of one bookreview cell per kind; validates AC-2 + AC-4).

### Summary

Plan ships under `docs/razorback-implementation/plans/pkg26-reshape-claude-cli-subclass.md`. The load-bearing change is one file refactor (`src/razorback/agents/claude_cli.py`: 118 lines → ~50 line subclass) plus a per-variant branch in the goal1 spec generator. Two plan-review questions are flagged: (1) whether to symlink `claude-code.txt` → `claude-output.jsonl` inside `populate_context_post_run` to preserve the `rk audit` taint-scanner contract (preferred), and (2) which `solver_workflow` directory the goal1 spacedock variant should pin (default: create `examples/solver_workflows/dab_paper_matrix/`; alternative: reuse `_smoke`). T0 is riskiest-contract-first (subclass shape) — minutes-to-validate before the 36-cell matrix re-dispatch is unblocked.
