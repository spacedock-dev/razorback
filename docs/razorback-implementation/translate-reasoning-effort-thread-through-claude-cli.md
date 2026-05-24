---
id: k4ncx3dt7pqvsftnv2spftrf
title: translate.py threads reasoning_effort through to harbor on the claude-cli path
status: backlog
source: 2026-05-25 k3 cycle-4 finding via `rk run --explain` evidence — `src/razorback/translate.py:191-213` only threads `allowed_tools` for the claude-cli code path; `reasoning_effort` declared at `agent.reasoning_effort` is parsed by `ClaudeCliAgentBlock` (post-k3 schema fix at `8ef0270`) but silently dropped before reaching `harbor_agent_kwargs`. k3 cycle-4 evidence at `docs/razorback-implementation/_evidence/leak-guard-rerun/{spacedock,direct-structured,direct-minimal}/agnews/explain.json`: spacedock's resolved kwargs carry `reasoning_effort: xhigh` (different translator branch); direct-structured + direct-minimal explain JSONs omit it entirely. k3's live agnews re-runs on the two direct-* cells PASSED `rk audit --policy strict` clean and verbatim-grep empty regardless — the leak-guard prose is not reasoning-depth-dependent — but they did NOT run with the xhigh reasoning depth the spec author declared. This is a translator regression, not a schema regression; k3's AC-5 schema fix is necessary but not sufficient.
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

After k3 landed the schema fix accepting `reasoning_effort` on
`ClaudeCliAgentBlock`, `rk freeze` correctly admits specs carrying
`agent.reasoning_effort: xhigh`. But `rk run --explain` on those
specs surfaces a downstream bug: the resolved `harbor_agent_kwargs`
emitted to harbor does NOT carry `reasoning_effort` for the
claude-cli code path (variants `direct-structured` and
`direct-minimal`). The spacedock variant carries it correctly
because it goes through a different translator branch.

Root location: `src/razorback/translate.py:191-213` (the claude-cli
kwargs-builder). Per the cycle-4 finding, only `allowed_tools` is
threaded; `reasoning_effort` (and possibly other agent-level
sampling/runtime fields) is silently dropped.

Consequence: every direct-structured and direct-minimal spec on
the matrix paper that declares `reasoning_effort: xhigh` actually
runs with whatever Harbor's claude-cli default is — not xhigh.
The post-k3 schema accept doesn't fix this; it just lets the spec
load. The behavior remains broken.

The fix is mechanical: extend the claude-cli kwargs builder to
include `reasoning_effort` (and any other declared-but-dropped
field surfaced in the same audit) when present on the agent block.

## Acceptance criteria

**AC-1 — `translate.py` threads `reasoning_effort` to
`harbor_agent_kwargs` on the claude-cli path.**
Verified by:
- `grep -n "reasoning_effort" src/razorback/translate.py` returns ≥1 match within the claude-cli kwargs-builder block (lines around 191-213 in pre-fix state; cite post-fix line numbers in the impl stage report).
- A unit test at `tests/unit/test_translate_claude_cli_kwargs.py` (or extension of the closest existing translate test) asserts that translating a spec with `agent.reasoning_effort: xhigh` produces a `harbor_agent_kwargs` dict whose `reasoning_effort` key equals `"xhigh"`. The test is RED on baseline `main` (pre-fix), GREEN on the post-fix branch; both commit SHAs cited.

**AC-2 — `rk run --explain` surfaces `reasoning_effort` on all three workspace variants.**
Verified by:
- `uv run rk run --explain --explain-format json examples/specs/goal1/direct-structured/agnews.yaml | jq '.agent.harbor_agent_kwargs.reasoning_effort'` outputs `"xhigh"`.
- Same invocation on `direct-minimal/agnews.yaml` outputs `"xhigh"`.
- Same invocation on the spacedock variant continues to output `"xhigh"` (regression check on the path that was already correct).

**AC-3 — Audit pass for any other declared-but-dropped agent fields.**
The impl stage report enumerates every field on `ClaudeCliAgentBlock`
that the schema admits, and confirms each one either (a) appears in
the resolved `harbor_agent_kwargs` per `rk run --explain` JSON, or
(b) is documented in the report as deliberately not-threaded (with
a one-line reason citing the field's intended use).
Verified by: the report's audit table maps each schema field to its
threading status; no field is unaccounted for.

**AC-4 — Existing pytest stays green; no regressions in spacedock kwargs threading.**
Verified by:
- `uv run pytest tests/` exits 0 modulo pre-existing failures (LFS-hydration, mongo_init_docker); the failure set is byte-identical to post-merge `main`.
- The pre-existing `tests/unit/test_translate*.py` tests pass without modification.

## Test plan

- **Mechanism check first:** read `src/razorback/translate.py:191-213` and locate the claude-cli kwargs-builder block. Confirm the structural shape (dict construction with explicit-keys vs unpacked-dict).
- **RED unit test:** write the AC-2 round-trip assertion as a unit test against an in-memory `Spec` fixture; confirm RED before any translator edit.
- **GREEN:** thread `reasoning_effort` through the builder; confirm RED test goes GREEN; spacedock test stays GREEN.
- **Schema audit:** enumerate every `ClaudeCliAgentBlock` field and cross-check against the kwargs-builder's output keys. Surface any other dropped fields in the stage report.
- **Integration check:** `rk run --explain` on each of the three k3 evidence specs; cite the new JSON's `harbor_agent_kwargs.reasoning_effort` value.

## Out of scope

- **Re-running the k3 direct-* agnews cells with corrected
  reasoning_effort.** k3 already shipped AC-2 PASS evidence on
  these cells under audit-clean + grep-empty discipline; the
  leak-guard prose is reasoning-depth-independent and the
  evidence stands. If a later research question depends on
  rerunning these cells with xhigh actually wired, that's a
  follow-on entity not gated by this fix.
- **Threading additional fields not surfaced by the schema
  audit.** If AC-3 surfaces other dropped fields beyond
  `reasoning_effort`, the impl ensign decides per-field whether
  to thread it in this entity (mechanical) or file as a
  separate entity (semantically meaningful).
- **spacedock-side kwargs builder.** That path already threads
  `reasoning_effort` correctly per the cycle-4 explain.json
  evidence; no work needed there.

## Depends on

- (none — k3's schema fix at `8ef0270` is in `main` after k3
  merges; that's the prerequisite for this translator change
  to have anything to thread.)

## Resume hook

When this lands, `reasoning_effort` (and any other audit-surfaced
declared-but-dropped agent fields) is correctly threaded through
to harbor for the claude-cli code path. Future direct-structured
and direct-minimal cells declaring xhigh (or other reasoning
depths) actually run with that setting. The `rk run --explain`
JSON output becomes a reliable belt+suspenders gate against this
class of silent-drop bug for any spec author.

`auto-approve: false` because the translator is captain-facing
runtime surface — kwargs that thread to harbor are the model's
actual configuration, not just spec validation.
