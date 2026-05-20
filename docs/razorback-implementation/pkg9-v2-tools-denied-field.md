---
id: v4fz9wwrm3f2cv800zdp6wdv
title: PKG-9 v2 — tools_denied agent block field
status: backlog
source: spec §6.2 + §8.5 + §9.4 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started:
completed:
verdict:
score:
worktree:
issue:
pr:
mod-block:
---

## Problem

Original PKG-9's hook-blocking concern collapses to a single spec
field. Spec §6.2 introduces `tools_denied` on the `spacedock_solver`
agent block: a list of strings installed as PreToolUse hooks in the
inner runtime that block matching tool invocations at execution time.
This is Layer 2 of the three-layer leak guard (§9.4); the field
replaces the leak-guard, tool-deny-runtime, cost-ceiling, and
baseline-compare mods from the prior design (§8.5 names the
collapse). The DAB benchmark adapter publishes its recommended
denylist (the verbatim `DISALLOWED_TOOLS` list from dataagentbench's
reference impl) as documentation; the captain pastes it into the
spec. PKG-9 v2's scope is razorback-core only: the spec field, its
parser acceptance, and the runtime contract that pushes the list
into the harbor agent's PreToolUse hook config. Hint variants and
workspace README variants ship with the DAB adapter in Phase 2, not
with razorback core.

## Acceptance criteria

**AC-1 — The spec parser accepts `agent.tools_denied: list[str]` on
`spacedock_solver` agent blocks and validates it during `rk freeze`.**
Verified by: unit test feeds a spec with a five-entry
`tools_denied` list and asserts the frozen spec preserves the list
verbatim. A second test feeds a spec with `tools_denied: "string"`
(wrong type) and asserts `SpecError` (exit 10) with a message
naming the field. A third test omits the field and asserts
`tools_denied` defaults to an empty list. Unit test path:
`tests/unit/test_tools_denied_parse.py`.

**AC-2 — `SpacedockSolverAgent` at construction time installs the
`tools_denied` list as PreToolUse hooks in the inner runtime's
configuration.**
Verified by: unit test constructs `SpacedockSolverAgent` with
`runtime: claude` and a `tools_denied` list containing the four
DAB-recommended denials (`Bash(pip install datasets*)`,
`Bash(pip install dataagentbench*)`, `Bash(huggingface-cli
login*)`, `Bash(curl https://huggingface.co/*)`); asserts the
generated claude-runtime settings.json carries the PreToolUse
permissions section with the four entries verbatim. Cite spec
§6.2 in the implementation comment.

**AC-3 — Live runtime probe: a forbidden command is denied during a
smoke run.**
Verified by: integration test runs a fixture spec whose agent is
prompted to attempt `pip install datasets`; asserts the run-dir's
`events.jsonl` carries a PreToolUse denial event citing the hook
rule and that the agent did not execute the install. Test path:
`tests/integration/test_tools_denied_live.py`.

**AC-4 — `tools_denied` survives spec freezing and re-loading
unchanged.**
Verified by: unit test runs `rk freeze` on a spec with a
`tools_denied` list, then loads the frozen yaml, then asserts the
list is byte-identical to the input.

**AC-5 — Carry-forward tests stay green.**
Verified by: `uv run pytest` exits 0 from a clean checkout of the
worktree branch tip with all prior tests passing alongside the new
PKG-9 v2 tests.

## Test plan

- **Unit tests:** spec parser acceptance + rejection (wrong type +
  missing field + empty list); `SpacedockSolverAgent` PreToolUse
  hook generation for each supported runtime (claude first, codex
  + pi stubs marked NotImplemented per AC-0.7's D2 default);
  `tools_denied` round-trip through `rk freeze`; carry-forward.
- **Integration test:** one live smoke run that exercises the
  PreToolUse hook against a known-denied command, asserting the
  denial event appears in `events.jsonl`.
- **Acceptance command:** `uv run rk freeze <fixture-spec>` then
  `uv run rk run <frozen>.frozen.yaml` against a spec whose agent
  attempts a denied command; exit code reflects the denial path.

## Out of scope

- Hint variants. Spec §9.4 places hints content with the DAB
  benchmark adapter (Phase 2), not razorback core.
- Workspace README variants (`direct-minimal`, `direct-structured`,
  `spacedock`). Same Phase 2 placement.
- The paper-reproduction grid spec (`examples/specs/paper-
  reproduction.yaml`). Captain-driven matrix dispatcher under spec
  §3.2 + the matrix script at `examples/drivers/dab-paper-matrix.sh`
  owns this; razorback core ships `tools_denied` + `rk score
  --against-constant` and stops there.
- The six leak-guard mods from the prior design (`leak-guard`,
  `tool-deny-runtime`, `baseline-compare`, `cost-ceiling`,
  `stage-boundary-freeze`, `phase-stats-writer`). Spec §8.5 explains
  the collapse; they do not ship.
- Layer 3 post-hoc trajectory scanning (`rk audit`). Tracked
  separately under Phase 4a per the reconciliation plan.
- Codex and pi `tools_denied` translation. Per AC-0.7's D2 default,
  these ship as NotImplemented stubs until a consumer surfaces.
