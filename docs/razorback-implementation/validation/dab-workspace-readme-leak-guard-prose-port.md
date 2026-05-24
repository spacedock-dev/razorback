# Validation report — DAB workspace READMEs (leak-guard prose port)

- entity: `docs/razorback-implementation/dab-workspace-readme-leak-guard-prose-port.md`
- branch: `spacedock-ensign/dab-workspace-readme-leak-guard-prose-port`
- HEAD validated: `d8671d3` (10+ commits ahead of `main` at `5c4edfb`)
- baseline for AC-4: `main` HEAD `5c4edfb9f102f567d0ebb37c9d19c508b556ea16`

## AC-1 — leak-guard prose present in all three razorback workspace variants

**Verified by (per AC):**
- per-variant Python render assert that `'datasets.load_dataset'` ∈ `render_workspace_readme(variant=v, container_workdir='/workspace')` for `v` in `{direct-minimal, direct-structured, spacedock}`
- `grep -F 'UNABLE TO DETERMINE' packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py`

**Reproduced output:**

```
=== AC-1.a: per-variant Python render assert ===
--- variant=direct-minimal ---
OK direct-minimal
--- variant=direct-structured ---
OK direct-structured
--- variant=spacedock ---
OK spacedock
=== AC-1.b: grep UNABLE TO DETERMINE across workspace_readme.py ===
29:The workspace databases are the only authoritative source. ... return `"UNABLE TO DETERMINE"`.
62:The workspace databases are the only authoritative source. ... return `"UNABLE TO DETERMINE"`.
105:The workspace databases are the only authoritative source. ... return `"UNABLE TO DETERMINE"`.
```

Render-assert was widened to all 7 leak-guard phrases (`HuggingFace`, `datasets.load_dataset`, `hf://`, `Public CSV`, `Web search engines`, `UNABLE TO DETERMINE`, `Use only the workspace data`) for each variant; all three returned `OK`. Grep returns 3 matches (one per variant), as required.

**Verdict: PASS**

## AC-2 — live agnews re-run rejects the load_dataset attack path

**Verified by (per AC):** `rk audit --policy strict` clean + verbatim `grep -F 'canonical' .../claude-code.txt | grep -i 'ag news\|dataset'` empty + no Bash exec of `load_dataset`.

**Reproduced output (per-cell audit summary):**

```
spacedock/agnews         summary={clean:1, tainted:0, coverage_missing:0}
direct-structured/agnews summary={clean:2, tainted:0, coverage_missing:0}
direct-minimal/agnews    summary={clean:2, tainted:0, coverage_missing:0}
```

All three audit.json files (`docs/razorback-implementation/_evidence/leak-guard-rerun/{spacedock,direct-structured,direct-minimal}/agnews/audit.json`) report `tainted: 0`, `coverage_missing: 0`, `findings: []`.

**Verbatim AC-2 grep across the 3 evidence dirs:**

```
=== AC-2 verbatim grep per cell ===
--- spacedock ---
verbatim grep -F 'canonical' | grep -i 'ag news\|dataset':
(EMPTY)
matched article_id count: 0
fancyzhx count: 0
--- direct-structured ---
verbatim grep -F 'canonical' | grep -i 'ag news\|dataset':
(EMPTY)
matched article_id count: 0
fancyzhx count: 0
--- direct-minimal ---
verbatim grep -F 'canonical' | grep -i 'ag news\|dataset':
(EMPTY)
matched article_id count: 0
fancyzhx count: 0
```

**Branch (a) decline confirmed for all 3 cells** (no Bash exec of `load_dataset`):

```
spacedock          total-lines-with-mention=1  bash-exec-with-load_dataset=0
direct-structured  total-lines-with-mention=1  bash-exec-with-load_dataset=0
direct-minimal     total-lines-with-mention=1  bash-exec-with-load_dataset=0
```

The single `load_dataset` mention per cell is the rendered `## Rules` section being read back through the agent's prompt, never an executed Bash command. AC-2 branch (a) — "no `from datasets import load_dataset` event at all (agent saw the rule and declined)" — applies to every cell.

**Verdict: PASS**

## AC-3 — unit test pins the leak-guard prose

**Verified by (per AC):** `uv run pytest packages/razorback-plugin-dab/tests/unit/test_workspace_readme_leak_guard.py -v` passes.

**Reproduced output:**

```
collected 21 items
... (21 PASSED, one per variant × phrase)
============================== 21 passed in 0.01s ==============================
```

21 parametrized cases = 7 phrases × 3 variants. Any future edit that drops a forbidden-list phrase from any variant turns the matching parametrized case RED.

**Verdict: PASS**

## AC-4 — existing pytest stays green; mongo failure pre-existing on baseline

**Verified by (per AC):** `uv run pytest packages/razorback-plugin-dab/tests/ -v` green; pre-existing failures reproduce 1:1 on baseline `main`.

**Reproduced output (worktree branch):**

```
============= 1 failed, 165 passed, 3 skipped in 65.63s (0:01:05) ==============
FAILED packages/razorback-plugin-dab/tests/integration/test_mongo_init_docker.py::test_mongo_init_shim_loads_bsondump_on_first_start
E           AssertionError: shim did not load BSON; final count=-1
E           assert -1 > 0
```

**Baseline reproduction (main `5c4edfb9f102f567d0ebb37c9d19c508b556ea16`, same single test):**

```
                time.sleep(1)
>           assert count > 0, f"shim did not load BSON; final count={count}"
E           AssertionError: shim did not load BSON; final count=-1
E           assert -1 > 0

packages/razorback-plugin-dab/tests/integration/test_mongo_init_docker.py:146: AssertionError
FAILED packages/razorback-plugin-dab/tests/integration/test_mongo_init_docker.py::test_mongo_init_shim_loads_bsondump_on_first_start
========================= 1 failed in 62.01s (0:01:02) =========================
```

Byte-identical assertion text (`shim did not load BSON; final count=-1`); the single failure is environmental (docker-mongo init shim infra), not branch-introduced. Counts (165 passed / 3 skipped / 1 failed) match the impl ensign's cycle-3 stage report.

**Verdict: PASS**

## AC-5 — `ClaudeCliAgentBlock` accepts `reasoning_effort` and round-trips through `rk freeze`

**Verified by (per AC):** `uv run pytest tests/unit/test_freeze.py -v` GREEN on both new tests + fresh `rk freeze` on both `reasoning_effort: xhigh` specs.

**Reproduced output:**

```
collected 4 items
tests/unit/test_freeze.py::test_freeze_round_trips_input_keys PASSED
tests/unit/test_freeze.py::test_freeze_is_deterministic PASSED
tests/unit/test_freeze.py::test_claude_cli_agent_block_accepts_reasoning_effort PASSED
tests/unit/test_freeze.py::test_claude_cli_reasoning_effort_round_trips_through_freeze PASSED
============================== 4 passed in 0.07s ===============================
```

**Fresh `rk freeze` on goal1 direct-* specs (both carry `reasoning_effort: xhigh`):**

```
=== examples/specs/goal1/direct-structured/agnews.yaml ===
wrote examples/specs/goal1/direct-structured/agnews.frozen.yaml
wrote examples/specs/goal1/direct-structured/provenance.yaml
exit=0
=== examples/specs/goal1/direct-minimal/agnews.yaml ===
wrote examples/specs/goal1/direct-minimal/agnews.frozen.yaml
wrote examples/specs/goal1/direct-minimal/provenance.yaml
exit=0
```

**Frozen output preserves the field:**

```
examples/specs/goal1/direct-structured/agnews.frozen.yaml:  reasoning_effort: xhigh
examples/specs/goal1/direct-minimal/agnews.frozen.yaml:  reasoning_effort: xhigh
```

Schema diff is one line at `src/razorback/spec/schema.py:46` — `reasoning_effort: str | None = None`, matching the sibling field on `CodexAgentBlock` (line 59) and `SpacedockSolverAgentBlock`. `extra="forbid"` preserved on `ClaudeCliAgentBlock`.

**Verdict: PASS**

## Code review findings

Diff scope (branch since merge-base `d967c4c9`):

```
.../generate/workspace_readme.py                   | 30 ++
 .../tests/unit/test_workspace_readme_leak_guard.py | 29 ++
 src/razorback/spec/schema.py                       |  1 +
 tests/unit/test_freeze.py                          | 33 ++
 4 files changed, 93 insertions(+)
```

**Strengths:**
- Verbatim port from `~/git/dataagentbench/benchmark/workspace-readmes/workspace-readme.md` L77–83 with the 3 documented mechanical name swaps (`connections.yaml` → `db_config.yaml`, single-query reference, `_runs/` wording).
- Per-variant character preserved: `_DIRECT_MINIMAL` stays shortest (only adds `## Rules`); `_DIRECT_STRUCTURED` inserts `## Rules` between database-access and output-contract per plan; `_SPACEDOCK` keeps `model -> analyze -> verify` crew-loop framing.
- Test parametrization at `test_workspace_readme_leak_guard.py` = 7 phrases × 3 variants = 21 assertions; deleting any one phrase from any variant turns exactly one case RED.
- Schema fix is the minimal possible diff: 1 line, mirrors the sibling pattern on `CodexAgentBlock.reasoning_effort` and `SpacedockSolverAgentBlock`. `extra="forbid"` preserved.
- ABOUTME comments present on both new test files per CLAUDE.md.
- Mechanism-first task ordering observable in git history: T0 RED (`8a6e7ac`) → T1 GREEN (`34cc541`) → T6 RED schema (`d7d1e89`) → T7 GREEN schema (`8ef0270`).

**Minor (non-blocking):**
- `LEAK_GUARD_PHRASES` asserts phrase presence, not paragraph structure or section ordering. A future edit could fragment the paragraph and still pass. Acceptable: prose-presence is the load-bearing contract; the live agnews re-run is the empirical AC-2 gate, the unit test is the regression tripwire.
- `reasoning_effort: str | None = None` is untyped (no `Literal["low","medium","high","xhigh"]`). Consistent with `CodexAgentBlock.reasoning_effort` and `SpacedockSolverAgentBlock.reasoning_effort` already on the codebase. Strictness can come later as a sibling entity if needed; not in scope here.

**Blocking findings: none.**

## Cycle-4 translator finding (out-of-scope, sibling entity filed)

Cycle-4's `rk run --explain` pre-flight surfaced that `translate.py:191-213` silently drops `reasoning_effort` on the claude-cli code path: the `direct-structured` and `direct-minimal` `explain.json` artifacts at `docs/razorback-implementation/_evidence/leak-guard-rerun/<variant>/agnews/explain.json` show no `reasoning_effort` in `harbor_agent_kwargs`, while spacedock's correctly threads it. This means the two direct-* AC-2 cells ran without xhigh reasoning_effort despite the spec author's intent.

This does **NOT** affect any AC verdict:
- AC-2 — `rk audit --policy strict` returned `clean` on all 3 cells, verbatim grep returned EMPTY on all 3, and branch (a) decline applies to all 3. The leak-guard prose is not reasoning-depth-dependent; it deterred the `load_dataset` shortcut on direct-structured and direct-minimal even without xhigh.
- AC-5 — the AC explicitly gates on `parse_spec_text` accept + `freeze_spec` round-trip, both of which my reproduced output confirms PASS. The translator-layer drop is downstream of the AC-5 contract.

Team-lead has filed sibling entity `k4 translate-reasoning-effort-thread-through-claude-cli` to fix the translator drop. Discovered during k3 cycle-4 via `rk run --explain`; not blocking k3 verdict.

## Gate decision: APPROVE
