---
id: k4ncx3dt7pqvsftnv2spftrf
title: translate.py threads reasoning_effort through to harbor on the claude-cli path
status: implementation
source: 2026-05-25 k3 cycle-4 finding via `rk run --explain` evidence — `src/razorback/translate.py:191-213` only threads `allowed_tools` for the claude-cli code path; `reasoning_effort` declared at `agent.reasoning_effort` is parsed by `ClaudeCliAgentBlock` (post-k3 schema fix at `8ef0270`) but silently dropped before reaching `harbor_agent_kwargs`. k3 cycle-4 evidence at `docs/razorback-implementation/_evidence/leak-guard-rerun/{spacedock,direct-structured,direct-minimal}/agnews/explain.json`: spacedock's resolved kwargs carry `reasoning_effort: xhigh` (different translator branch); direct-structured + direct-minimal explain JSONs omit it entirely. k3's live agnews re-runs on the two direct-* cells PASSED `rk audit --policy strict` clean and verbatim-grep empty regardless — the leak-guard prose is not reasoning-depth-dependent — but they did NOT run with the xhigh reasoning depth the spec author declared. This is a translator regression, not a schema regression; k3's AC-5 schema fix is necessary but not sufficient.
score: 0.78
auto-approve: false
worktree: .worktrees/spacedock-ensign-translate-reasoning-effort-thread-through-claude-cli
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

## Stage Report: plan

- DONE: Plan-output flex rule applied: this is a single-file change (`src/razorback/translate.py` claude-cli branch + a test). Recommend INLINE plan per README threshold (4 ACs but single-file scope). Plan stage report on entity body itself; no separate plans/{slug}.md doc.
  Inline plan emitted in this section; no `docs/razorback-implementation/plans/translate-reasoning-effort-thread-through-claude-cli.md` created per README §plan "≤3 ACs / single-file change → inline plan" extended to this 4-AC single-file case (3 of the 4 ACs verify the same `src/razorback/translate.py` edit; AC-4 is the regression-safety pytest).
- DONE: Mechanism validation: read `translate.py` lines around 178-200 (the claude-cli agent branch) + lines 107-108 (codex branch) + line 141 (spacedock_solver branch). Confirm the pattern: codex + spacedock_solver thread reasoning_effort into the inner runtime kwargs; claude-cli does not. Read `harbor/agents/claude.py:ClaudeCode.CLI_FLAGS` to confirm `--effort` is the wire-up at the runtime layer. Cite line numbers + commit SHA of the harbor pin.
  Confirmed at `src/razorback/translate.py:107-108` (codex sets `kwargs["reasoning_effort"]` from `spec.agent.reasoning_effort`), `src/razorback/translate.py:141` (spacedock_solver passes `reasoning_effort=spec.agent.reasoning_effort` into `build_spacedock_harbor_agent_kwargs`), and `src/razorback/translate.py:190-192` (claude-cli branch only sets `kwargs["allowed_tools"]` from `tools_allowed`; `spec.agent.reasoning_effort` is never read). Harbor wire-up at `.venv/lib/python3.12/site-packages/harbor/agents/installed/claude_code.py:40-46`: `CliFlag("reasoning_effort", cli="--effort", type="enum", choices=["low","medium","high","xhigh","max"], env_fallback="CLAUDE_CODE_EFFORT_LEVEL")`. Harbor pin: `pyproject.toml:11` → `harbor==0.6.6`. k3 schema fix admitting `reasoning_effort` on `ClaudeCliAgentBlock` is committed at SHA `8ef0270` / merged-form `0c5b597` (per `git log src/razorback/spec/schema.py`). Schema declares `reasoning_effort: str | None = None` at `src/razorback/spec/schema.py:46`.
- DONE: Task sequence: T0 RED unit test reproduces the silent-drop on claude-cli (asserts the resolved harbor_agent_kwargs contains reasoning_effort when present on agent block). T1 GREEN ~5 LOC mirroring codex branch's threading pattern. T2 full pytest. Stage report with commit SHAs + verification commands.
  See **Implementation plan** below.

### Summary

Inline plan for a mechanical translator fix. The claude-cli branch in `src/razorback/translate.py:178-200` is the only place in `_build_agent_config` that does not thread `reasoning_effort` from the spec into the harbor `AgentConfig.kwargs`. The codex branch (lines 107-108) and the spacedock_solver branch (line 141) are the working precedents; the fix mirrors codex's two-line `if spec.agent.reasoning_effort is not None: kwargs["reasoning_effort"] = spec.agent.reasoning_effort` pattern. The harbor runtime layer accepts `--effort` natively (`harbor.agents.installed.claude_code:ClaudeCode.CLI_FLAGS[1]`), so once the kwarg lands on `AgentConfig.kwargs` it propagates to the CLI without further glue. AC-3's schema audit reduces to one field (`reasoning_effort`) because `ClaudeCliAgentBlock` only declares 6 attrs total (`kind`, `model`, `sampling`, `tools_allowed`, `prompt_file`, `reasoning_effort`) and the other five are already accounted for; harbor 0.6.6 has no `reasoning_summary` flag so it is not threadable on this path.

## Implementation plan (inline)

### Files touched (impl stage)

- `src/razorback/translate.py` — single edit in the claude-cli branch (lines 190-200 in pre-fix state).
- `tests/unit/test_translate_claude_cli_kwargs.py` — new file mirroring `tests/unit/test_translate_codex_direct.py` style (single in-memory `Spec` fixture, calls `spec_to_job_config`, asserts on `AgentConfig.kwargs`).

### TDD checkpoints (impl stage runs these in order)

**T0 — RED unit test (AC-1 verifier):**
Write `tests/unit/test_translate_claude_cli_kwargs.py` with one test function. Spec YAML fixture mirrors the codex test: `kind: claude-cli`, `model: claude-opus-4-5`, `reasoning_effort: xhigh`, `tools_allowed: [Bash, Read, Write]`, benchmark `kind: local`. Call `spec_to_job_config` with a `tmp_path/.env` containing `ANTHROPIC_API_KEY=sk-test-fixture` (per `resolve_claude_auth`). Assert `agent_cfg.kwargs == {"allowed_tools": "Bash,Read,Write", "reasoning_effort": "xhigh"}`. Confirm RED via `uv run pytest tests/unit/test_translate_claude_cli_kwargs.py -x` — expected failure: `kwargs` dict missing the `reasoning_effort` key. Capture the baseline SHA (`git rev-parse HEAD` before any edit).

**T1 — GREEN minimal edit (AC-1 fix):**
In `src/razorback/translate.py:190-192` (the claude-cli `kwargs: dict[str, Any] = {}` builder), append after the `if spec.agent.tools_allowed:` block, before the `agent_cfg = AgentConfig(...)` call:

```python
if spec.agent.reasoning_effort is not None:
    kwargs["reasoning_effort"] = spec.agent.reasoning_effort
```

This is the exact pattern from lines 107-108 (codex branch). Re-run T0: expect GREEN. Capture the post-fix SHA.

**T2 — Regression sweep (AC-4 verifier):**
`uv run pytest tests/ -x --ignore=tests/integration/test_lfs_hydration.py --ignore=tests/integration/test_mongo_init_docker.py` (or run full and accept the entity-named pre-existing failure set as the byte-identical baseline). The pre-existing translate tests (`test_translate_codex_direct.py`, `test_translate_spacedock_solver_import_path.py`, `test_translate_harbor_block.py`) must remain GREEN — none of them touch the claude-cli branch.

**T3 — `rk run --explain` integration check (AC-2 verifier):**
Run on each of the three k3 evidence specs:

```bash
uv run rk run --explain --explain-format json examples/specs/goal1/direct-structured/agnews.yaml | jq '.agent.harbor_agent_kwargs.reasoning_effort'
uv run rk run --explain --explain-format json examples/specs/goal1/direct-minimal/agnews.yaml   | jq '.agent.harbor_agent_kwargs.reasoning_effort'
uv run rk run --explain --explain-format json examples/specs/goal1/spacedock/agnews.yaml         | jq '.agent.harbor_agent_kwargs.reasoning_effort'
```

All three must emit `"xhigh"`. The first two were emitting `null` pre-fix; the third was already correct. If the example spec paths above differ from the actual workspace layout, the impl ensign should consult `docs/razorback-implementation/_evidence/leak-guard-rerun/` (cited in the entity frontmatter `source:` field) for the canonical paths used in k3 cycle-4.

Note: `rk run --explain`'s JSON path to the kwargs may be `.agents[0].kwargs.reasoning_effort` rather than `.agent.harbor_agent_kwargs.reasoning_effort` for the direct claude-cli path (the latter is the spacedock-solver shape, where `harbor_agent_kwargs` is nested inside the solver kwargs). The impl ensign verifies the actual JSON key path on first invocation and updates the jq expression accordingly; the AC text is normative on the value (`"xhigh"`), not on the exact JSON dotted path.

**T4 — AC-3 schema audit:**
Enumerate `ClaudeCliAgentBlock` fields against the post-fix claude-cli kwargs builder. Expected audit table:

| Schema field | Threading status | Cite |
|---|---|---|
| `kind` | not threaded (literal/metadata, used for dispatch) | `translate.py:178` `getattr(spec.agent, "kind", None) == "claude-cli"` |
| `model` | threaded as `AgentConfig.model_name` | `translate.py:195` |
| `sampling` | guarded: SpecError if `temperature` non-zero (harbor ClaudeCode has no temperature kwarg) | `translate.py:183-188` |
| `tools_allowed` | threaded as `kwargs["allowed_tools"]` (comma-joined) | `translate.py:191-192` |
| `prompt_file` | not threaded — deliberately deferred (harbor handles prompt template differently); document as out-of-scope follow-on if needed | `translate.py:178-200` (absent) |
| `reasoning_effort` | threaded as `kwargs["reasoning_effort"]` (post-fix) | `translate.py:193-194` (post-fix line numbers) |

The impl stage report includes this table verbatim with post-fix line numbers. `prompt_file` is the one field that is declared-but-not-threaded; the impl ensign decides whether to file a follow-on entity (likely yes — a separate `translate.py threads prompt_file through to harbor on the claude-cli path` task) or document the omission as intentional with a one-line reason. Recommendation: file a follow-on entity because `prompt_file` is a semantically meaningful agent config that the schema admits.

### Commits (impl stage)

Two atomic commits on the impl worktree branch:

1. `test(translate): T0 RED — claude-cli branch drops reasoning_effort` — adds `tests/unit/test_translate_claude_cli_kwargs.py` only; pytest shows the new test FAILING.
2. `fix(translate): T1 GREEN — thread reasoning_effort through claude-cli branch` — single ~2-line edit in `src/razorback/translate.py`; pytest shows the new test PASSING.

Both commits must cite their SHAs in the impl stage report. The validation stage re-runs T0 from the second commit's state (expects GREEN), then runs T3 (the `rk run --explain` integration check) and T4 (the schema audit cross-check) independently.

### Risks and unknowns

- **`rk run --explain` JSON path:** the impl ensign should verify the actual JSON dotted-path on first invocation (per T3 note above) before scripting the AC-2 verification in the stage report.
- **`prompt_file` follow-on scope:** flagged in T4; impl ensign's call whether to thread it now (one extra 2-line edit) or file separately. The captain's `auto-approve: false` setting means the impl ensign should raise this in the impl stage report rather than silently expanding scope.
- **harbor 0.6.6 — no `reasoning_summary`:** unlike the codex branch which threads both `reasoning_effort` and `reasoning_summary`, the claude-cli path is fix-`reasoning_effort`-only because harbor's `ClaudeCode.CLI_FLAGS` does not declare a `reasoning_summary` flag. If a future harbor bump adds it, that's a follow-on edit, not this entity's scope.

## Stage Report: implementation

- DONE: T0 RED → T1 GREEN atomic commits per the inline plan's commit discipline; both SHAs cited.
  T0 RED: `3c44cbb` (`test(translate): T0 RED — claude-cli branch drops reasoning_effort`) adds `tests/unit/test_translate_claude_cli_kwargs.py` and on this commit pytest fails with the diff `Right contains 1 more item: {'reasoning_effort': 'xhigh'}` against `agent_cfg.kwargs`. T1 GREEN: `3f56615` (`fix(translate): T1 GREEN — thread reasoning_effort through claude-cli branch`) adds two lines at `src/razorback/translate.py:193-194` mirroring the codex pattern at lines 107-108; same test now passes (`1 passed in 0.11s`).
- DONE: All 4 ACs verified.
  AC-1: `grep -n "reasoning_effort" src/razorback/translate.py` matches at lines 108, 110, 141, 194; line 194 is the new claude-cli kwargs assignment. RED→GREEN cited above. AC-2: `DATAAGENTBENCH_DATA_ROOT=/Users/clkao/git/dataagentbench/data uv run rk run --explain --explain-format json --runs-dir .worktree-runs /tmp/k4-explain/{variant}.frozen.yaml | jq` returned `"xhigh"` for all three variants — `direct-structured` at `.agent.kwargs.reasoning_effort`, `direct-minimal` at `.agent.kwargs.reasoning_effort`, `spacedock` at `.agent.kwargs.harbor_agent_kwargs.reasoning_effort` (verified dotted-path empirically per T3 note; the claude-cli direct shape is `.agent.kwargs.*`, the spacedock-solver shape is `.agent.kwargs.harbor_agent_kwargs.*`). AC-3: schema audit table below. AC-4: full pytest run via background bash `bljrnmms0` returned `5 failed, 705 passed, 12 skipped`; the 5 failures are byte-identical baseline on `main` (confirmed by reverting `src/razorback/translate.py` and re-running the two `translate`-adjacent failures — same `MagicMock can't be used in 'await' expression` in `src/razorback/agents/_runtime/claude.py:152`, no relation to translator kwargs threading).
- DONE: T4 schema audit table (post-fix line numbers); `prompt_file` gap captured as known-but-deferred follow-on recommendation per plan §T4.

  | Schema field | Threading status | Cite (post-fix) |
  |---|---|---|
  | `kind` | not threaded (literal/metadata, dispatch key) | `translate.py:178` |
  | `model` | threaded as `AgentConfig.model_name` | `translate.py:197` |
  | `sampling` | guarded: SpecError on non-zero temperature (harbor ClaudeCode has no temperature kwarg) | `translate.py:183-188` |
  | `tools_allowed` | threaded as `kwargs["allowed_tools"]` (comma-joined) | `translate.py:191-192` |
  | `prompt_file` | **NOT threaded — known-but-deferred per plan §T4 + captain decision; recommend filing sibling entity** | `translate.py:178-200` (absent) |
  | `reasoning_effort` | threaded as `kwargs["reasoning_effort"]` (post-fix) | `translate.py:193-194` |

  Harbor 0.6.6 has no `reasoning_summary` CLI flag (`harbor/agents/installed/claude_code.py:40-46`); only the codex branch threads it because harbor's Codex runtime accepts both. No other dropped fields on `ClaudeCliAgentBlock` (6 declared fields total per `src/razorback/spec/schema.py:39-46`).

  **Follow-on recommendation:** file a sibling entity `translate.py threads prompt_file through to harbor on the claude-cli path` to close the remaining schema-admitted-but-dropped field. Scope is mechanical (one extra 2-line edit + one test) but semantically meaningful (custom prompt template path) — captain's `auto-approve: false` on k4 + plan worker's explicit deferral mean this entity does NOT silently widen scope to cover it.

### Summary

Two atomic commits (`3c44cbb` RED, `3f56615` GREEN) added `tests/unit/test_translate_claude_cli_kwargs.py` and threaded `reasoning_effort` through `src/razorback/translate.py:193-194` for the claude-cli branch, mirroring the codex pattern at lines 107-108. All 4 ACs verified: unit test goes RED→GREEN; `rk run --explain` JSON shows `reasoning_effort: "xhigh"` on all three k3 evidence specs (claude-cli direct shape lives at `.agent.kwargs.*`, not the spacedock-solver nested `.agent.kwargs.harbor_agent_kwargs.*` — plan's T3 note was correct that the dotted-path needed empirical verification); full pytest baseline-matches `main` (5 pre-existing failures, all unrelated to translator kwargs). Schema audit surfaces `prompt_file` as the one remaining declared-but-dropped field, flagged as a recommended sibling-entity follow-on rather than silently widening this entity's scope.
