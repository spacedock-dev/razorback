---

id: etm8kjzn1vcvptabc341wnww
title: translate.py threads prompt_file through to harbor on the claude-cli path
status: backlog
source: '2026-05-24 k4 plan-stage AC-3 schema audit (entity `translate-reasoning-effort-thread-through-claude-cli`, validation report `## Stage Report: validation` and the entity body `## Implementation plan (inline)` T4 audit table). The audit enumerated `ClaudeCliAgentBlock`''s 6 fields against the post-fix claude-cli kwargs builder in `src/razorback/translate.py:178-202`. Five fields threaded correctly post-k4-merge; `prompt_file` is the one remaining declared-but-not-threaded field — schema admits it but the translator never reads it. Captain authorized deferral to a follow-on entity at k4 plan stage 2026-05-24; k4 ensign filed the follow-on recommendation in its impl stage report.'
score: 0.78
auto-approve: false
worktree:
issue:
pr:
mod-block:
started:
completed:
verdict:
---

## Problem

`ClaudeCliAgentBlock` (`src/razorback/spec/schema.py:39-46`) declares a
`prompt_file: str | None = None` attribute. The claude-cli translator
branch at `src/razorback/translate.py:178-202` builds the runtime kwargs
dict but never reads `spec.agent.prompt_file`. Result: a spec author can
set `agent.prompt_file: ./my-prompt.md` on a claude-cli spec, the spec
freezes cleanly, `rk run --explain` reports the spec valid — but the
runtime agent never sees the file.

Harbor's `ClaudeCode` runtime accepts a `system_prompt` (or equivalent)
mechanism for an externally-loaded prompt; the contract is documented
in `.venv/lib/python3.12/site-packages/harbor/agents/installed/claude_code.py`.
The fix mirrors k4's approach for `reasoning_effort`: a ~2-LOC edit in the
claude-cli kwargs builder, plus a translator-level unit test that pins
the round-trip.

This is the second silent-drop bug uncovered by k4's discipline of
auditing every schema field against its threading status — the audit
table is the right discipline for catching this class of regression
before it ships.

## Acceptance criteria

**AC-1 — `translate.py` reads `spec.agent.prompt_file` and threads its
contents (or path, per harbor's convention) into `AgentConfig.kwargs`
on the claude-cli branch.**
Verified by:
- `grep -n "prompt_file" src/razorback/translate.py` returns ≥1 match inside the `if getattr(spec.agent, "kind", None) == "claude-cli":` branch (lines around 178-202; cite post-fix line numbers in the impl stage report).
- A unit test at `tests/unit/test_translate_claude_cli_kwargs.py` (extending k4's file) asserts that translating a spec with `agent.prompt_file: <fixture-path>` produces an `AgentConfig.kwargs` dict whose entry for the harbor system-prompt key equals the expected file contents or the resolved path (per harbor's contract). The test is RED on pre-fix `main`, GREEN on the post-fix branch; both commit SHAs cited.

**AC-2 — `rk run --explain` surfaces the loaded prompt_file content (or path)
on a claude-cli spec.**
Verified by:
- Construct a minimal claude-cli spec with `agent.prompt_file: ./fixture-prompt.md` (fixture committed under `tests/fixtures/`).
- `uv run rk run --explain --explain-format json <spec>.frozen.yaml | jq '.agent.kwargs'` (or the empirically-discovered correct dotted path per k4's note about jq paths) shows the prompt content or path threaded through.
- Spacedock variant remains unaffected (the spacedock_solver branch handles its own prompt-prefix logic; cross-check that `system_prompt` doesn't double up on the spacedock path).

**AC-3 — Schema audit table re-closed: zero declared-but-not-threaded fields on `ClaudeCliAgentBlock`.**
The impl stage report's audit table mirrors k4's T4 table and shows all 6 fields accounted for: `kind` / `model` / `sampling` / `tools_allowed` / `reasoning_effort` (post-k4) / `prompt_file` (post-this-entity). Every threading-status cell either cites a translator line that reads the field, or names a captain-acknowledged out-of-scope reason.
Verified by: the table is in the stage report; impl ensign confirms by direct read of `src/razorback/spec/schema.py:39-46` against `src/razorback/translate.py:178-202` post-fix.

**AC-4 — Existing pytest stays green; no regressions on the claude-cli or spacedock dispatch paths.**
Verified by:
- `uv run pytest tests/` exits 0 modulo pre-existing failures byte-identical to baseline `main` (the k4-baseline shape: 5 failed / 705 passed / 12 skipped / 1 pre-existing collection error, modulo the +1/-1 from the new RED→GREEN test in this entity).
- `test_translate_claude_cli_kwargs.py`'s existing tests (including k4's `test_claude_cli_threads_reasoning_effort_into_kwargs`) remain GREEN unchanged.

## Test plan

- **Mechanism check first:** read harbor's `ClaudeCode` source for the
  prompt-loading contract (system_prompt? prompt_file CLI flag?
  embedded-in-message?). The k4 audit pointed at
  `harbor.agents.installed.claude_code:ClaudeCode.CLI_FLAGS` — confirm
  which flag (if any) corresponds to prompt loading and whether the
  contract is path-passing or content-passing. If harbor lacks a
  prompt_file mechanism for claude-cli (unlikely but possible), surface
  to captain at plan stage rather than inventing a non-conforming wire-up.
- **TDD:** RED unit test asserting the round-trip → confirm RED on
  baseline `main` → ~2-LOC GREEN edit mirroring k4's pattern → confirm
  GREEN → full pytest sweep.
- **Integration check:** `rk run --explain` on a fixture spec confirms
  the prompt threads through visibly.

## Out of scope

- **Threading prompt_file on the codex branch.** Codex's branch at
  `translate.py:107-108` doesn't currently read prompt_file either,
  but no codex spec in-tree declares it. If a future codex spec needs
  it, file a sibling at that time.
- **Spacedock-solver prompt_file handling.** Spacedock has its own
  workflow-README prepend logic at `agents/spacedock_solver.py`. The
  prompt_file convention on `ClaudeCliAgentBlock` doesn't apply to the
  spacedock_solver path. Confirm this is the case via the AC-2
  cross-check; if it ISN'T (e.g., the spacedock path also reads
  agent.prompt_file unintentionally), surface as a Material finding.
- **Refactor of the `_build_agent_config` claude-cli branch.** The fix
  is mechanical; refactoring to extract common kwarg-builder logic
  across branches is a follow-on entity if the audit pattern keeps
  finding gaps.

## Depends on

- (none — k4 shipped on main; this entity's fix layers atop the same
  claude-cli kwargs builder)

## Resume hook

When this lands, `ClaudeCliAgentBlock`'s schema audit is closed: zero
declared-but-not-threaded fields. Future spec authors who set
`agent.prompt_file` on a claude-cli spec get the prompt loaded into
the runtime instead of silently dropped. The audit-table-discipline
that k4 established now stays in place for any future
`ClaudeCliAgentBlock` field additions.

`auto-approve: false` because the translator is captain-facing
runtime surface — kwargs that thread to harbor are the agent's
actual configuration.
