---
id: ne9e1dpbwxs3rp11j07epa81
title: SpacedockSolverAgent — real FO subagent dispatch + smoke gate enforcing subagent jsonl trace
status: plan
source: Captain directive 2026-05-23 — "the spacedock solver run pilot should validate the jsonl log actually has dispatch and emits subagent jsonl. see also the dataagentbench's smoke validation." — surfaced after FO investigation of `an goal1-rerun` / `d8` trace shape revealed that `SpacedockSolverAgent.run()` is a prompt-prefixing wrapper around a single `claude` CLI invocation (no `--agent spacedock:first-officer`, no `--plugin-dir spacedock`), so the cycle ran as one flat claude session with workflow README as system-prompt prose and zero `Task` tool calls. The "spacedock variant" label was misleading because the runtime did not dispatch subagents.
started: 2026-05-23T21:20:41Z
completed:
verdict:
score: 0.95
worktree:
issue:
pr:
mod-block:
---

## Problem

`SpacedockSolverAgent` at `src/razorback/agents/spacedock_solver.py:345-352`
implements the spacedock variant by prepending the workflow README to the
task instruction and handing the composed prompt to a single inner-agent
invocation (`RazorbackClaudeCode` → harbor's `ClaudeCode.run` → `claude -p
<prompt>`). The CLI invocation does NOT pass `--agent
spacedock:first-officer`, does NOT pass `--plugin-dir <spacedock>`, and does
NOT install the spacedock skill into the agent container — so the inner
`claude` session has no first-officer skill loaded and no ensign dispatch
contract. The agent self-organizes through the model→analyze→verify stages
in its system prompt via TodoWrite, but never spawns subagents via the
`Task` tool.

Concrete evidence: every cell in `_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/<dataset>/.../yelp__Cc94VEd/steps/main/agent/claude-code.txt`
shows `tool_use` events for `Bash`, `TodoWrite`, `ToolSearch` and ZERO
events for `Task` or any spawn primitive across all 12 cells (verified by
JSON-parsing each cell's claude-code.txt). The session-init system event
DOES advertise `Task` as available — the agent simply has no skill that
tells it to use it.

DAB upstream
(`~/git/dataagentbench/benchmark/lib/run_experiment.py:1308`) dispatches
its spacedock variant via
`run_cli_agent(..., sub_agent="spacedock:first-officer",
prompt_prefix=SPACEDOCK_PROMPT_PREFIX_TEMPLATE.format(...))`, which renders
`claude -p <prompt> --agent spacedock:first-officer --plugin-dir
<spacedock-plugin>` and prefixes a ROLE instruction that explicitly tells
claude to enter first-officer mode, read the workspace README, and
dispatch worker subagents via `spawn_agent` / `wait_agent`. The spacedock
skill is staged into the container before the run. DAB also instruments a
trace-capture hook
(`~/git/dataagentbench/benchmark/lib/subagent_traces.py`) that logs every
`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`
event from the inner agent and writes a `traces/manifest.json` per
attempt asserting expected-vs-captured subagent count
(`write_trace_manifest_json` test fixtures show `expected=1, captured=1`
shape).

This entity ships two paired changes that close the gap:

1. **Real first-officer dispatch:** wire `SpacedockSolverAgent` (via its
   `_runtime/claude.py` builder) to pass `--agent spacedock:first-officer`
   + `--plugin-dir <razorback's spacedock skill source>` to the inner
   claude CLI, and to install the spacedock skill into the agent
   container's claude-config path. Add the ROLE-as-first-officer prompt
   prefix analogous to DAB's `SPACEDOCK_PROMPT_PREFIX_TEMPLATE`.

2. **Subagent-trace smoke gate:** add a per-cell post-run validator that
   parses the inner agent's `claude-code.txt`, counts `Task` /
   spawn-primitive tool-use events, and writes a
   `subagent-trace-manifest.json` next to the existing
   `provenance.yaml`. Wire the matrix dispatcher's per-cell smoke check
   to REJECT a cell when the spacedock variant's trace records zero
   subagent dispatches.

The smoke gate cannot validate anything in isolation — without item (1)
it would just emit `dispatches: 0` forever. Both must land together.

## Acceptance criteria

**AC-1 — Razorback's `SpacedockSolverAgent` dispatches through the first
officer.**
A bookreview cell run via `agent.kind: spacedock_solver` produces a
`claude-code.txt` whose tool-use stream contains `>= 1` `Task` tool_use
events. The spacedock skill is mounted into the agent container at the
canonical claude-config location and the `claude` CLI invocation carries
`--agent spacedock:first-officer` + `--plugin-dir <spacedock-source>`.
Verified by: dispatch one bookreview cell; `python -c "import json;
n=sum(1 for ln in open('<cell>/steps/main/agent/claude-code.txt') if
'\"name\":\"Task\"' in ln); print(n)"` returns an integer >= 1; the
inner-agent claude argv (captured via DAB-style debug logging or the
docker exec stdout) shows the two flags.

**AC-2 — Per-cell subagent-trace manifest.**
Every spacedock-variant cell run writes a
`subagent-trace-manifest.json` under the per-cell trial directory
adjacent to `provenance.yaml`. The manifest carries:
`{schema_version: "razorback-subagent-traces-v1", expected: <int|null>,
captured: <int>, dispatches: [{tool_use_id, subagent_type, prompt_sha256,
spawn_index}], parent_agent: {model, ...}, capture_source:
"razorback-claude-cli-trace"}`. The schema and writer are unit-tested
against a synthetic claude-code.txt fixture.
Verified by: `jq -e '.captured >= 1 and (.dispatches | length) ==
.captured' <cell>/subagent-trace-manifest.json` on a real bookreview
cell returns true; pytest covers the writer end-to-end.

**AC-3 — Smoke gate REJECTS cells whose spacedock variant ran without
subagent dispatch.**
The matrix dispatcher (`examples/drivers/dab-paper-matrix.sh`) — or a
sibling post-cell validator the dispatcher invokes — flags any
`spacedock` variant cell whose `subagent-trace-manifest.json.captured ==
0` as failed. The cell's `dispatch-ledger.tsv` row records
`status: subagent-dispatch-missing` (or equivalent), and the
captain-facing aggregator MUST surface that status in its per-cell
sub-table.
Verified by: build a synthetic cell with `captured: 0`; run the
validator; assert exit code != 0 (or the ledger row carries the failed
status). A real bookreview cell post-AC-1 returns `captured > 0` and
the validator passes.

**AC-4 — A 1-cell pilot smoke (bookreview) is bundled in the entity's
test plan.**
Per CLAUDE.md mechanism-validation rule, the riskiest contract
(spacedock-skill-mount + `--agent` flag + first-officer-dispatch
end-to-end inside the dab-agent container) runs against ONE cell
before any matrix-level work. The captain-facing report cites the
pilot's `claude-code.txt` line-count of `Task` events.
Verified by: pilot smoke ledger entry + cited line counts in the
report's "Mechanism gate" section.

**AC-5 — Razorback's existing tests cover the spacedock-skill-mount
contract.**
Unit/integration tests assert that
`razorback.agents._runtime.claude.build_inner_agent` (or its FO-aware
analog) routes spacedock-kind agents through the FO dispatch path and
plain `claude-cli`-kind agents through the existing direct path.
Existing claude-cli tests stay green; new spacedock-mode tests RED
before the wiring lands and GREEN after.
Verified by: `uv run pytest tests/unit/test_runtime_claude_*` (or
equivalent) passes; one new test exercises the FO dispatch arg
construction.

## Test plan

- **Mechanism smoke first (per CLAUDE.md):** before touching the matrix
  dispatcher, run the bookreview pilot. Confirm the spacedock skill
  mounts, `claude` CLI accepts `--agent spacedock:first-officer` +
  `--plugin-dir`, the FO prompt-prefix bootstraps FO mode, the inner
  session emits at least one `Task` tool-use, and the trace manifest is
  written with `captured >= 1`.
- **Unit tests:** spacedock-runtime-builder argv construction; trace
  manifest schema + writer; smoke validator exit-code logic.
- **Integration:** one bookreview cell end-to-end on the live
  `dab-agent:latest` image with isolated networking.
- **Full pytest:** stays green; pre-existing failures (LFS-hydration,
  etc.) unaffected.
- **Out of test plan:** running a full 12-cell matrix to compare the
  new spacedock numbers vs the old single-agent ones. That comparison
  is a sibling entity; this entity ships the wiring + smoke gate.

## Out of scope

- **Recomputing or re-running goal1 spacedock numbers against the
  fixed FO-dispatch path.** Sibling entity if/when captain wants the
  true crew-loop spacedock vs single-agent-prompt-prefix head-to-head.
  The post-1s headline 0.722 stays as the "spacedock-as-prompt-prefix"
  number; a future entity ships the "spacedock-with-real-FO-dispatch"
  number against the same matrix.
- **Codex / Pi runtime adapters.** This entity scopes claude only.
  Sibling entities can mirror the pattern for codex (which DAB
  upstream already implements at
  `~/git/dataagentbench/benchmark/lib/run_experiment.py:1295-1360`).
- **Trace-manifest schema convergence with DAB upstream.** The
  manifest shape can diverge from
  `dab-subagent-traces-v1` if Harbor/razorback layering makes
  alignment expensive; the contract is "expected-vs-captured count is
  inspectable + asserted." Sibling entity if the captain wants byte
  alignment.
- **Renaming the existing single-agent variant.** The current
  `agent.kind: spacedock_solver` keeps its name; once this entity
  ships, `spacedock_solver` actually behaves as a spacedock solver.
  Documentation update is part of this entity's AC-1 work.

## Depends on

- **`an goal1-rerun-dab-spacedock-opus47-xhigh`**: DONE / archived.
  Established the spacedock-variant matrix dispatcher pattern and
  the per-cell evidence layout the smoke gate consumes.
- **`d8 goal1-rerun-headline-per-query-recompute`**: DONE / archived.
  Establishes the canonical-reducer + per-query reporting pattern
  that the future re-comparison entity (if filed) consumes.
- **DAB upstream's `subagent_traces` module** at
  `~/git/dataagentbench/benchmark/lib/subagent_traces.py`: reference
  implementation for trace-capture + manifest contract; razorback
  adopts the same shape, adapted for the claude runtime (not codex).

## Resume hook

When this lands, the spacedock variant's name finally matches its
runtime behavior, AND a permanent smoke gate prevents a silent
regression where the variant degrades back to single-agent execution.
The fixed contract sets up a clean future comparison: re-run goal1
under the real FO dispatch path and contrast the per-query headline
against d8's 0.722 (which is the single-agent-with-prompt-prefix
number). If FO-dispatch produces a meaningfully different number
(higher or lower), the spacedock crew loop's value is finally measured
in isolation from the prompt-engineering effect.
