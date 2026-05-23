# SpacedockSolverAgent — real first-officer dispatch + subagent-trace smoke gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Entity:** `docs/razorback-implementation/spacedock-solver-real-fo-dispatch-and-smoke-gate.md`

**Goal:** Make `agent.kind: spacedock_solver` actually run as a spacedock crew loop (claude as first-officer, dispatched ensign workers via the `Task` tool) and add a per-cell smoke gate that REJECTS cells whose spacedock variant degraded back to single-agent execution. Today the runtime is a prompt-prefixed single-claude invocation; the entity's evidence (`yelp__Cc94VEd/.../claude-code.txt`) shows zero `Task` tool_use events across all 12 cells.

**Tech stack:** Python 3.12, pytest, bash. Harbor's `ClaudeCode` subclassed at `src/razorback/agents/_runtime/claude.py:RazorbackClaudeCode`. Spacedock skill source on host at `/Users/clkao/git/spacedock/` (plugin manifest at `.claude-plugin/plugin.json`, first-officer + ensign skills under `skills/`).

---

## AC ↔ Task map

| AC | Description | Tasks |
|---|---|---|
| AC-1 | `agent.kind: spacedock_solver` produces a `claude-code.txt` with ≥1 `Task` tool_use; claude argv carries `--agent spacedock:first-officer` + `--plugin-dir <spacedock-source>`; the spacedock plugin is staged so the first-officer skill is discoverable | T0 (mechanism gate), T2 (RED unit), T3 (RED integration), T4 (GREEN: extend `RazorbackClaudeCode` flag surface), T5 (GREEN: plugin staging + ROLE prefix in `SpacedockSolverAgent._compose_run_instruction`), T6 (GREEN: thread sub_agent through `build_inner_agent`) |
| AC-2 | Each spacedock cell writes `subagent-trace-manifest.json` adjacent to `provenance.yaml`, schema `razorback-subagent-traces-v1`, `dispatches[]` with `tool_use_id` + `subagent_type` + `prompt_sha256` + `spawn_index`, asserted by `jq` | T7 (smoke validator module + RED unit on fixture), T8 (GREEN writer), T9 (wire writer into `RazorbackClaudeCode.populate_context_post_run`) |
| AC-3 | Matrix dispatcher REJECTS cells where `captured == 0`; `dispatch-ledger.tsv` carries `status: subagent-dispatch-missing`; aggregator surfaces the status | T10 (RED bash integration test on synthetic `captured: 0` cell), T11 (GREEN: dispatcher hook in `examples/drivers/dab-paper-matrix.sh`), T12 (aggregator pass-through) |
| AC-4 | 1-cell pilot smoke (bookreview) runs end-to-end with `Task` ≥1 + `captured` ≥1 before any matrix-level work | T0 (mechanism gate, plan-stage if cheap; otherwise first task in implementation) |
| AC-5 | Existing claude-cli tests stay green; new spacedock-mode test RED → GREEN | T2 (RED), T4–T6 (GREEN); pytest at end of T6 |

**Riskiest contract first (the mechanism gate, per CLAUDE.md):**
> "spacedock-skill-mount + `--agent` flag + first-officer dispatch produces ≥1 `Task` tool_use event end-to-end inside the trial environment on a real bookreview cell."

If the `claude` CLI inside razorback's trial environment refuses `--plugin-dir`, OR if `--agent spacedock:first-officer` can't find the plugin even when mounted, the wiring approach changes (fallback paths in **Risk register**). T0 is sequenced as the FIRST implementation task; everything past T0 inherits its verdict.

---

## Mechanism check — TO BE DONE in T0 of implementation stage

The plan-stage worker did NOT pay this bill (the entity body is explicit that "the smoke gate cannot validate anything in isolation — without item (1) it would just emit `dispatches: 0` forever"). Implementation stage's T0 runs the smallest end-to-end exercise of the riskiest path BEFORE writing any production code. The minimum-viable T0:

1. Stand up a freshly-frozen bookreview spec with `kind: spacedock_solver` + opus-4.7 (existing `examples/specs/goal1/spacedock/bookreview.frozen.yaml` from goal1-rerun, or regen via `examples/drivers/generate-dab-paper-matrix-specs.py`).
2. Hand-patch `src/razorback/agents/_runtime/claude.py` locally (not committed) to:
   - Pass `--plugin-dir /Users/clkao/git/spacedock` and `--agent spacedock:first-officer` to the inner CLI via `extra_flags` injection.
   - Prepend a `SPACEDOCK_PROMPT_PREFIX_TEMPLATE`-style ROLE block to the instruction.
3. Dispatch ONE bookreview cell:
   ```bash
   uv run rk run examples/specs/goal1/spacedock/bookreview.frozen.yaml \
       --runs-dir "$XDG_DATA_HOME/razorback/runs/spacedock-fo-mechanism-smoke" \
       --concurrency.trials 1
   ```
4. Parse the resulting `claude-code.txt`:
   ```bash
   python -c "import json; \
       n=sum(1 for ln in open('<cell>/steps/main/agent/claude-code.txt') \
       if json.loads(ln).get('message', {}).get('content', [{}])[0].get('name') == 'Task'); \
       print(n)"
   ```
   **Verdict (must be ≥1):** GREEN → proceed with T2 onward; the wiring shape is sound.
   **Verdict (= 0 with `--agent` accepted):** the spacedock skill is mounted but the FO didn't dispatch. Re-read the FO skill source (`/Users/clkao/git/spacedock/skills/first-officer/SKILL.md`) — the ROLE prefix may need adjustment.
   **Verdict (`--agent` or `--plugin-dir` rejected by CLI):** wiring approach changes — see Risk register fallbacks.
5. Revert the hand-patch. Implementation stage proceeds with the verified shape baked into the production diff.

**Why T0 belongs in implementation stage (not plan stage):** mechanism check requires a live opus-4.7 API call (~$1–3 for bookreview at xhigh). Plan-stage workers don't burn API budget; that's an implementation-stage gate per CLAUDE.md's "Validating new mechanisms" (the comprehensive run gets the small bill first, but the smallest bill itself is implementation work). T0 is sequenced explicitly to NOT spend $60 on a 12-cell matrix until the 1-cell wiring is proven.

---

## Surface map — what changes

| File | Change |
|---|---|
| `src/razorback/agents/_runtime/claude.py` | (a) Extend `RazorbackClaudeCode.CLI_FLAGS` (or override `build_cli_flags`) to emit `--plugin-dir <dir>` and `--agent <name>` when `plugin_dirs` / `sub_agent` kwargs are present. Add to `_CLAUDE_SUPPORTED_KWARGS`. (b) `build_inner_agent` accepts `plugin_dirs: list[Path] \| None` and `sub_agent: str \| None`, propagates to `RazorbackClaudeCode`. (c) Optional: `RazorbackClaudeCode.populate_context_post_run` writes `subagent-trace-manifest.json` via the new validator module (AC-2 wiring). |
| `src/razorback/agents/spacedock_solver.py` | (a) `_build_inner_agent` passes `plugin_dirs` + `sub_agent="spacedock:first-officer"` to the claude builder for `runtime="claude"` only — codex and pi paths unchanged. (b) `_compose_run_instruction` prepends `SPACEDOCK_PROMPT_PREFIX_TEMPLATE` (razorback-flavored — see §Prompt template below) ABOVE the existing workflow-README + task-instruction block. The README is still included so the first officer can read it, but the ROLE-as-first-officer block is what makes the model dispatch. |
| `src/razorback/agents/_runtime/__init__.py` *(if needed)* | Re-export `SPACEDOCK_PLUGIN_DIR_DEFAULT` + helper for spec-time resolution (defaults to the spacedock checkout discovered via `RAZORBACK_SPACEDOCK_PLUGIN_DIR` env var → packaged fallback). |
| `src/razorback/agents/subagent_traces.py` *(new)* | Per-cell trace-manifest writer. Reads `claude-code.txt` JSONL line-by-line, counts `tool_use` events where `name == "Task"`, materializes a `dispatches[]` entry per event with `tool_use_id`, `subagent_type` (from `input.subagent_type`), `prompt_sha256` (sha256 of `input.prompt`), `spawn_index` (0-based ordinal). Writes `subagent-trace-manifest.json` with schema `razorback-subagent-traces-v1`. The writer is the razorback analog of DAB's `subagent_traces.write_trace_manifest` at `~/git/dataagentbench/benchmark/lib/subagent_traces.py:677`, adapted for claude's `claude-code.txt` JSONL shape (DAB targets codex's `codex-output.jsonl`). |
| `src/razorback/agents/subagent_smoke.py` *(new — could be a thin module or a CLI entrypoint)* | Smoke validator. CLI shape: `python -m razorback.agents.subagent_smoke <cell-dir>`. Reads `<cell-dir>/subagent-trace-manifest.json`; exits 0 if `captured >= 1`, exits 2 if `captured == 0` (with stderr message `subagent-dispatch-missing`), exits 3 on manifest absent. Used by the matrix dispatcher's per-cell hook. |
| `tests/unit/test_runtime_claude_fo_dispatch.py` *(new)* | T2 RED → T4–T6 GREEN. Tests: (a) `build_inner_agent(plugin_dirs=[...], sub_agent="...")` constructs `RazorbackClaudeCode` whose `build_cli_flags()` includes `--plugin-dir /path/to/spacedock` and `--agent spacedock:first-officer`; (b) default (no plugin_dirs / sub_agent) preserves existing flag shape; (c) `_CLAUDE_SUPPORTED_KWARGS` rejects an unsupported new kwarg as before. |
| `tests/unit/test_spacedock_solver_fo_dispatch.py` *(new)* | T3 RED. Test: `SpacedockSolverAgent(runtime="claude", ...)._build_inner_agent()` returns a `RazorbackClaudeCode` whose `_sub_agent == "spacedock:first-officer"` and `_plugin_dirs` non-empty. T6 GREEN. |
| `tests/unit/test_spacedock_solver_compose_prompt.py` *(new)* | T3 RED. Test: `SpacedockSolverAgent._compose_run_instruction("...")` output starts with `"ROLE: You are the first-officer"`. T5 GREEN. |
| `tests/unit/test_subagent_traces_writer.py` *(new)* | T7 RED. Tests against a synthetic `claude-code.txt` fixture with 2 `Task` events: (a) writer emits `subagent-trace-manifest.json` with `captured == 2`, `dispatches` length 2, every entry has the 4 required fields; (b) `schema_version == "razorback-subagent-traces-v1"`; (c) zero-Task fixture → `captured == 0` and `dispatches == []`. T8 GREEN. |
| `tests/unit/test_subagent_smoke_validator.py` *(new)* | T10 RED. Tests: (a) `captured >= 1` → exit 0; (b) `captured == 0` → exit 2 + stderr `subagent-dispatch-missing`; (c) missing manifest → exit 3. T11 GREEN (the validator itself is exercised by the integration in T11). |
| `tests/integration/test_dab_paper_matrix_spacedock_gate.py` *(new)* | T10 RED → T11 GREEN. Builds a synthetic cell dir with a zero-`captured` manifest, invokes the dispatcher's per-cell hook (or a shell-out to the validator), asserts the ledger row carries `status: subagent-dispatch-missing` and the cell is marked failed. |
| `examples/drivers/dab-paper-matrix.sh` | T11. Add per-cell post-run hook (after `rk audit` / before `rk score`): when the spec's variant is `spacedock`, invoke `uv run python -m razorback.agents.subagent_smoke <cell-run-dir>`. On exit code 2, append `status: subagent-dispatch-missing` to the ledger row instead of `status: ok`, and skip score emission for that cell (treat as a failed cell for `--continue-on-fail` semantics). The aggregator (`examples/drivers/aggregate-goal1-scores.py`) already reads the ledger; the new status surfaces in its per-cell sub-table without aggregator-side changes. |
| `examples/drivers/aggregate-goal1-scores.py` | T12. Verify pass-through (or add a 1-line column rendering) — the new `subagent-dispatch-missing` status MUST appear in the captain-facing per-cell sub-table. If the aggregator already renders the ledger's `status` column verbatim, this is no-change. |

## Surface map — what stays

- `src/razorback/spec/schema.py` — no spec-level surface added. The plugin-dir + sub-agent values are runtime concerns (per-runtime-adapter responsibility), not spec inputs. Spec just says `kind: spacedock_solver`; the adapter handles the rest. This matches DAB upstream's shape (sub_agent passed by run_experiment, not by experiment.yaml).
- `src/razorback/spec/agent_kwargs.py` — no field added. `harbor_agent_kwargs` continues to hold runtime-tunable knobs only (`max_turns`, `reasoning_effort`, etc.).
- `src/razorback/agents/_runtime/codex.py` — unchanged. Codex is out-of-scope per entity body.
- `src/razorback/agents/_runtime/pi.py` — unchanged.
- Harbor's `ClaudeCode` — no upstream change. All flag surface extension happens in razorback's subclass.
- `examples/specs/goal1/spacedock/*.yaml` — no change to the 12 frozen specs. Once the runtime gets the FO dispatch wiring, the same frozen specs run differently (which is the whole point — the variant name finally matches behavior).
- Existing `test_spacedock_solver_*.py` tests — must stay green.

---

## Prompt template

A razorback-flavored `SPACEDOCK_PROMPT_PREFIX_TEMPLATE` constant lives in `src/razorback/agents/spacedock_solver.py` (or a sibling `spacedock_prompts.py` if it grows). Initial shape (adapted from DAB upstream's at `~/git/dataagentbench/benchmark/lib/run_experiment.py:1201`):

```
ROLE: You are the first-officer for this single-dataset spacedock workflow.
Your current working directory IS the workspace ({WORKSPACE_DIR}) — every file
and command in this prompt is relative to it. Do NOT cd to any other directory.

Your job is to orchestrate the stages defined in {WORKSPACE_DIR}/README.md by
dispatching workers via the Task tool (subagent_type="spacedock:ensign"). You
coordinate; workers execute.

You MUST NOT run queries against data files, write answers.json, or otherwise
perform stage work yourself. That work belongs to your dispatched workers.

Read {WORKSPACE_DIR}/README.md and dispatch the first stage worker. The final
{WORKSPACE_DIR}/answers.json will be written by the analyze-stage worker.

The task description below tells you WHICH dataset — it does not override
your first-officer role. Apply the task description to your workers, not to
yourself.

---
```

The existing `_compose_run_instruction` continues to inline the workflow README + task instruction AFTER the ROLE block. The ROLE block changes the model's frame; the README is still there for the model to read into its tool-call context.

`{WORKSPACE_DIR}` resolves to the harbor trial's workspace path (the dir where the `claude` CLI is invoked). For T5 verification, harbor's `EnvironmentPaths.workspace` is the canonical source; in DAB upstream the value comes from `run_cli_agent`'s `workspace` arg.

---

## Tasks

### T0 — Mechanism gate: bookreview pilot smoke (RISKIEST CONTRACT FIRST)

- **Goal:** Prove end-to-end that `--plugin-dir` + `--agent spacedock:first-officer` + ROLE-prefix produces ≥1 `Task` tool_use on a real bookreview cell before any production diff lands.
- **Steps:** see "Mechanism check" section above.
- **Run:** `python -c "..."` on the cell's `claude-code.txt`; expected count ≥ 1.
- **Gate:** if 0, stop and surface the verdict + the captured CLI argv + the first ~50 lines of `claude-code.txt` to the captain BEFORE writing any production code. The diff approach depends on this verdict.
- **Budget:** ~$1–3 (bookreview at opus-4.7 xhigh, single trial).
- **Spec §-cite:** Entity AC-1, AC-4. CLAUDE.md mechanism-validation rule.

### T2 — Runtime-builder argv unit test (RED)

- **Goal:** Add `tests/unit/test_runtime_claude_fo_dispatch.py`. Three tests assert the planned `build_inner_agent` signature accepts `plugin_dirs` + `sub_agent` and surfaces them as `--plugin-dir` / `--agent` flags.
- **Run:** `uv run pytest tests/unit/test_runtime_claude_fo_dispatch.py -x -v`; expected RED (TypeError on the new kwargs).
- **Spec §-cite:** Entity AC-1 verification (CLI argv shape), AC-5.

### T3 — Solver dispatch + prompt unit tests (RED)

- **Goal:** Add `tests/unit/test_spacedock_solver_fo_dispatch.py` and `tests/unit/test_spacedock_solver_compose_prompt.py`. Tests assert (a) `SpacedockSolverAgent._build_inner_agent` (runtime=claude) wires sub_agent + plugin_dirs through, (b) `_compose_run_instruction` output starts with the ROLE prefix.
- **Run:** `uv run pytest tests/unit/test_spacedock_solver_*.py -x -v`; expected RED.
- **Spec §-cite:** Entity AC-1, AC-5.

### T4 — Extend `RazorbackClaudeCode` flag surface (GREEN T2)

- **Goal:** Make T2 pass. `RazorbackClaudeCode` accepts `plugin_dirs: list[Path|str] | None` and `sub_agent: str | None` kwargs. These render as `--plugin-dir <p>` (repeatable) and `--agent <name>` in `build_cli_flags()`.
- **Implementation note:** Harbor's `CliFlag` mechanism doesn't natively handle a repeatable `--plugin-dir`. Two viable shapes:
  1. **Override `build_cli_flags`** in `RazorbackClaudeCode` to call `super().build_cli_flags()` and append `--plugin-dir` / `--agent` after. Simpler.
  2. **Extend `CLI_FLAGS`** with two new `CliFlag` entries — requires checking whether harbor's `CliFlag` supports `repeatable=True`. If not, option 1.
  Option 1 is recommended for the smallest diff.
- **Run:** `uv run pytest tests/unit/test_runtime_claude_fo_dispatch.py -x -v`; expected GREEN.
- **Spec §-cite:** Entity AC-1.

### T5 — ROLE prefix in `_compose_run_instruction` (GREEN T3 compose-prompt)

- **Goal:** Make `test_spacedock_solver_compose_prompt.py` pass. Add `SPACEDOCK_PROMPT_PREFIX_TEMPLATE` constant + thread `WORKSPACE_DIR` resolution into `_compose_run_instruction`.
- **Implementation note:** The current `_compose_run_instruction` only takes the instruction string. It needs access to the workspace path. Two viable shapes:
  1. Resolve workspace from the active harbor environment at run() time (pass it into `_compose_run_instruction` from `run()`).
  2. Use a placeholder string `{WORKSPACE_DIR}` and let the ROLE-prefix renderer be invoked from `run()` where the environment is in scope.
  Option 1 is cleaner; matches DAB upstream's `prompt_workspace` resolution pattern.
- **Run:** `uv run pytest tests/unit/test_spacedock_solver_compose_prompt.py -x -v`; expected GREEN.
- **Spec §-cite:** Entity AC-1 (ROLE block).

### T6 — Thread sub_agent + plugin_dirs from solver → builder (GREEN T3 fo-dispatch)

- **Goal:** Make `test_spacedock_solver_fo_dispatch.py` pass. `SpacedockSolverAgent._build_inner_agent` for `runtime="claude"` passes `plugin_dirs=[<spacedock-plugin-dir>]` and `sub_agent="spacedock:first-officer"` to `claude.build_inner_agent`. Codex and pi paths unchanged.
- **Spacedock plugin dir resolution:** `RAZORBACK_SPACEDOCK_PLUGIN_DIR` env var → fallback to a packaged-asset path discovered at import time (mirror harbor's plugin-discovery pattern; for now, env-var-only is acceptable with a clear error message).
- **Run:** `uv run pytest tests/unit/test_spacedock_solver_*.py -x -v`; expected GREEN.
- **Run all existing spacedock tests:** `uv run pytest tests/unit/ -k spacedock -x`; expected GREEN (AC-5).
- **Spec §-cite:** Entity AC-1, AC-5.

### T7 — Trace-manifest writer unit test (RED)

- **Goal:** Add `tests/unit/test_subagent_traces_writer.py`. Fixture: two synthetic `claude-code.txt` files (one with 2 `Task` events, one with 0). Tests assert the writer's manifest shape matches `razorback-subagent-traces-v1`.
- **Fixture content (2-Task variant):** raw JSONL lines copy-pasted from a real DAB trace (or hand-constructed minimal events matching claude's stream-json shape: `{"type":"assistant","message":{"content":[{"type":"tool_use","id":"toolu_01...","name":"Task","input":{"subagent_type":"spacedock:ensign","prompt":"..."}}]}}`).
- **Run:** `uv run pytest tests/unit/test_subagent_traces_writer.py -x -v`; expected RED (module doesn't exist yet).
- **Spec §-cite:** Entity AC-2.

### T8 — Trace-manifest writer (GREEN T7)

- **Goal:** Make T7 pass. Add `src/razorback/agents/subagent_traces.py` with `write_subagent_trace_manifest(cell_dir: Path) -> dict`. Parses `<cell_dir>/.../claude-code.txt` JSONL, counts `Task` tool_use events, writes `<cell_dir>/subagent-trace-manifest.json`.
- **Manifest shape (verbatim from entity AC-2):**
  ```json
  {
    "schema_version": "razorback-subagent-traces-v1",
    "expected": null,
    "captured": <int>,
    "dispatches": [
      {"tool_use_id": "...", "subagent_type": "...", "prompt_sha256": "...", "spawn_index": 0}
    ],
    "parent_agent": {"model": "claude-opus-4-7"},
    "capture_source": "razorback-claude-cli-trace"
  }
  ```
- **`expected: null` rationale:** unlike DAB upstream (which knows the workflow's stage count at dispatch time), razorback's spacedock workflow stage count varies per workflow README. `null` means "no pre-declared expectation — captured count is the ground truth." A future entity can wire workflow-README stage counting if the captain wants strict expected-vs-captured assertion.
- **`parent_agent.model` extraction:** read from the first `assistant` event's `message.model` field in `claude-code.txt`.
- **Run:** `uv run pytest tests/unit/test_subagent_traces_writer.py -x -v`; expected GREEN.
- **Spec §-cite:** Entity AC-2.

### T9 — Wire writer into post-run hook

- **Goal:** `RazorbackClaudeCode.populate_context_post_run` calls `write_subagent_trace_manifest(self.logs_dir.parent.parent.parent)` (or the equivalent run-dir resolution) when the parent is a `spacedock_solver`. The simplest gate: write the manifest unconditionally when `claude-code.txt` exists; for plain `claude-cli` agents the `captured` count is 0 and the manifest is harmless metadata.
- **Decision point:** writing the manifest unconditionally simplifies the gate but means non-spacedock cells get a manifest with `captured: 0` too. The smoke validator at T11 only runs on spacedock-variant cells (gated by the matrix driver). Cleaner: gate the write at `SpacedockSolverAgent.cleanup` (delegated to inner) — only spacedock-kind agents write the manifest.
- **Recommended:** gate at `SpacedockSolverAgent.cleanup` to keep the artifact scoped to the variant that needs it.
- **Verification:** rerun T0's bookreview cell with the production diff and verify the manifest exists.
- **Spec §-cite:** Entity AC-2.

### T10 — Smoke validator + bash integration test (RED)

- **Goal:** Add `tests/unit/test_subagent_smoke_validator.py` and `tests/integration/test_dab_paper_matrix_spacedock_gate.py`. The unit test exercises exit codes; the integration test invokes the dispatcher with a synthetic cell.
- **Run:** `uv run pytest tests/unit/test_subagent_smoke_validator.py tests/integration/test_dab_paper_matrix_spacedock_gate.py -x -v`; expected RED.
- **Spec §-cite:** Entity AC-3.

### T11 — Smoke validator module + dispatcher hook (GREEN T10)

- **Goal:** Add `src/razorback/agents/subagent_smoke.py` with `__main__` entry. Add per-cell post-run hook in `examples/drivers/dab-paper-matrix.sh`.
- **Hook placement (matrix driver):** after `rk run` for the cell completes, before `rk score`. Pseudocode:
  ```bash
  if [[ "$variant" == "spacedock" ]]; then
      if ! uv run python -m razorback.agents.subagent_smoke "$cell_run_dir"; then
          echo "subagent-dispatch-missing" >> "$LEDGER_TSV"  # actual format: replace 'ok' column for this row
          continue  # skip rk score; treat as failed cell
      fi
  fi
  ```
- **Run:** `uv run pytest tests/unit/test_subagent_smoke_validator.py tests/integration/test_dab_paper_matrix_spacedock_gate.py -x -v`; expected GREEN.
- **Spec §-cite:** Entity AC-3.

### T12 — Aggregator pass-through verification

- **Goal:** Confirm `examples/drivers/aggregate-goal1-scores.py` already renders the ledger's `status` column verbatim, so `subagent-dispatch-missing` surfaces in the captain-facing sub-table without aggregator-side changes. If it doesn't, add a 1-line column-passthrough.
- **Run:** synthesize a `dispatch-ledger.tsv` with one `status: subagent-dispatch-missing` row; run the aggregator; grep the output for `subagent-dispatch-missing`.
- **Spec §-cite:** Entity AC-3.

### T13 — Full pytest + 1-cell bookreview smoke with production diff

- **Goal:** Final sanity. Run `uv run pytest` (full suite); confirm no regressions beyond pre-existing failures. Re-dispatch the bookreview cell with the committed production diff; confirm `captured >= 1` and the smoke validator passes.
- **Run:**
  ```bash
  uv run pytest -x
  bash examples/drivers/dab-paper-matrix.sh --variants spacedock \
      --datasets bookreview --output-dir "$XDG_DATA_HOME/razorback/runs/spacedock-fo-final-smoke" \
      --max-cell-budget-usd 10.0
  jq -e '.captured >= 1' "$XDG_DATA_HOME/razorback/runs/spacedock-fo-final-smoke/spacedock/bookreview/.../subagent-trace-manifest.json"
  ```
- **Spec §-cite:** Entity AC-1, AC-2, AC-3, AC-4, AC-5 (composite verification).

---

## TDD checkpoints

| Pair | RED | GREEN |
|---|---|---|
| Runtime builder argv | T2 | T4 |
| Solver compose-prompt | T3 | T5 |
| Solver FO dispatch | T3 | T6 |
| Trace manifest writer | T7 | T8 |
| Smoke validator + matrix hook | T10 | T11 |

T0 is the integration-level mechanism gate per CLAUDE.md's "Validating new mechanisms" — it's not a TDD pair (it's an exploratory smoke that informs the production diff's shape).

T9 and T12 are wiring tasks (no new RED test of their own; covered transitively by T11 and T13).

---

## Risk register

| Risk | Mitigation |
|---|---|
| `claude` CLI inside razorback's trial env doesn't accept `--plugin-dir` | T0 catches this. Fallback: stage the spacedock skill into `$CLAUDE_CONFIG_DIR/skills/` via harbor's `skills_dir` kwarg (already plumbed through `RazorbackClaudeCode`), and pass `--agent spacedock:first-officer` alone. This matches DAB's codex path (`stage_codex_spacedock_package`) more than its claude path. |
| `--agent spacedock:first-officer` accepted but FO doesn't dispatch (Task count = 0 with FO skill loaded) | T0 catches this. Fallback: re-read `/Users/clkao/git/spacedock/skills/first-officer/SKILL.md` and align the ROLE prefix with what the skill expects. The skill itself may need an env-var or marker to enter dispatch mode. |
| Spacedock skill source path varies between dev machines / containers | Plan resolves the plugin dir via `RAZORBACK_SPACEDOCK_PLUGIN_DIR` env var. Production deployment to dab-agent container is OUT OF SCOPE — entity body scopes to "real first-officer dispatch wiring + smoke gate" not "production-grade plugin packaging." A sibling entity ships the canonical packaging once the wiring is proven. |
| Trace manifest schema diverges from DAB upstream | Entity body explicitly allows divergence ("the contract is 'expected-vs-captured count is inspectable + asserted'"). Schema convergence is OUT OF SCOPE — sibling entity if captain wants byte alignment. |
| Existing claude-cli cells (plain `kind: claude-cli`, not `spacedock_solver`) get a stray manifest | T9's gating at `SpacedockSolverAgent.cleanup` (not `RazorbackClaudeCode.populate_context_post_run`) confines the artifact to spacedock-kind cells. |
| Matrix dispatcher hook breaks `--continue-on-fail` semantics | T10's integration test exercises a synthetic failing cell to confirm the next cell still dispatches. |
| Pre-existing test failures (LFS-hydration, etc.) | T13 runs full pytest but the gate is "no new regressions"; pre-existing failures are documented in the implementation summary, not blockers. |
| T0 fails at the API call (auth) | Plan dispatcher reads `$CLAUDE_CODE_OAUTH_TOKEN` (or `~/.claude/benchmark-token`); T0 fails-fast if neither. Same auth shape as goal1-rerun. |

---

## Definition of done (plan-stage perspective)

The implementation stage signals done when:

- `src/razorback/agents/_runtime/claude.py` ships `plugin_dirs` + `sub_agent` plumbing; existing `_CLAUDE_SUPPORTED_KWARGS` unchanged.
- `src/razorback/agents/spacedock_solver.py` ships the ROLE prefix + FO-dispatch wiring for `runtime="claude"` only.
- `src/razorback/agents/subagent_traces.py` (writer) and `src/razorback/agents/subagent_smoke.py` (validator) exist with passing unit tests.
- `examples/drivers/dab-paper-matrix.sh` has the per-cell smoke hook; synthetic-failure integration test passes.
- T0 bookreview pilot cell shows `Task` event count ≥ 1 AND `subagent-trace-manifest.json` shows `captured >= 1`.
- Final 1-cell bookreview smoke with the committed diff (T13) shows the same.
- `uv run pytest` shows no new regressions vs `main` baseline.
- A short stage report under `## Implementation summary` in the entity body cites: the T0 bookreview cell's `claude-code.txt` Task-count, the `subagent-trace-manifest.json` `captured` value, the modules added.

---

## Out of scope (re-stated from entity body for plan-worker clarity)

- Re-running goal1's 12-cell matrix under the new FO dispatch path. Sibling entity.
- Codex / Pi runtime adapters. Claude only.
- Manifest schema byte-alignment with DAB upstream.
- Renaming `spacedock_solver` — once the wiring lands, the name finally matches behavior.
- Production-grade spacedock plugin packaging (a sibling entity ships the canonical packaging once T0 + T13 prove the wiring).
