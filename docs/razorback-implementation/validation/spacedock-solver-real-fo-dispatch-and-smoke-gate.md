# Validation report — SpacedockSolverAgent real FO dispatch + smoke gate

Entity: `ne9e1dpbwxs3rp11j07epa81`
Branch: `spacedock-ensign/spacedock-solver-real-fo-dispatch-and-smoke-gate` (HEAD `6e30875`)
Worktree: `.worktrees/spacedock-ensign-spacedock-solver-real-fo-dispatch-and-smoke-gate`
Verdict: **REJECT — back to implementation**

## TL;DR

The implementation correctly wires the FO dispatch contract (AC-1 satisfied end-to-end — claude CLI gets `--plugin-dir /tmp/razorback-plugins/spacedock --agent spacedock:first-officer`, the spacedock plugin loads, and 3 `Agent` tool_use events fire `spacedock:ensign` workers on a live bookreview cell). However, AC-2 (per-cell subagent-trace-manifest.json) fails in production because the writer hook is attached to `SpacedockSolverAgent.cleanup()`, and **harbor's trial runner never invokes `cleanup` on agents** — `BaseAgent` has no such method. Only `setup`, `run`, and `populate_context_post_run` are called. Consequently AC-3 (smoke gate REJECTS on captured=0) misfires: every spacedock cell now exits with `manifest-missing` (exit code 3) even when subagent dispatch actually happened. The matrix dispatcher rejected the live bookreview cell with `subagent-dispatch-missing` despite the claude-code.txt holding 3 valid dispatches.

The fix is one move: write the manifest from `populate_context_post_run` (which harbor does call) instead of `cleanup`. The integration test `test_cleanup_writes_manifest_adjacent_to_provenance` masks the bug because it manually invokes `cleanup`; it should exercise `populate_context_post_run` instead.

## Acceptance criteria

### AC-1 — Real FO dispatch — PASS

Live evidence from the bookreview pilot cell (`/Users/clkao/git/razorback/.worktrees/spacedock-ensign-spacedock-solver-real-fo-dispatch-and-smoke-gate/runs/spacedock-fo-final-smoke/spacedock/bookreview/goal1-spacedock-bookreview/703817880c73e047`):

- Inner-agent CLI argv (from `job.log`):
  ```
  claude --verbose --output-format=stream-json --permission-mode=bypassPermissions \
    --max-turns 200 --effort xhigh \
    --allowedTools Bash,Read,Write,Edit,Glob,Grep \
    --disallowedTools '...' \
    --plugin-dir /tmp/razorback-plugins/spacedock \
    --agent spacedock:first-officer \
    --print -- 'ROLE: You are the first-officer ...'
  ```
- Both required flags present, ROLE prefix prepended, spacedock plugin staged into the container at `/tmp/razorback-plugins/spacedock` via `_stage_plugin_dirs` (commit `e38f642`).
- `claude-code.txt` (`bookreview__jqSDLFT/agent/claude-code.txt`, 260925 bytes, 231 lines): JSON-parsing `tool_use` events with `name in {Task, Agent}` yields **3 dispatches**, all targeting `subagent_type: spacedock:ensign`.
- `Task: 0, Agent: 3` confirms the T0 wire-shape finding: CLI 2.1.148 emits the dispatch primitive as `Agent` even when session-init advertises `Task`.

AC-1 verified end-to-end. The fix here closed the original gap: zero dispatches in the prior `goal1-rerun` runs became 3 dispatches with real FO routing.

### AC-2 — Per-cell subagent-trace manifest — FAIL

The writer module (`razorback.agents.subagent_traces.write_subagent_trace_manifest`) is correct. Manually invoking it against the live cell produced the expected manifest:

```json
{
  "schema_version": "razorback-subagent-traces-v1",
  "expected": null,
  "captured": 3,
  "dispatches": [
    {"tool_use_id": "toolu_01VqN71PEwV9VwPejizEBpKe", "subagent_type": "spacedock:ensign", ...},
    {"tool_use_id": "toolu_01HaNoC2D6gPC4kj2Eg2oVHN", "subagent_type": "spacedock:ensign", ...},
    {"tool_use_id": "toolu_017Kj5JhjUhdCKmzC8FZfuiV", "subagent_type": "spacedock:ensign", ...}
  ],
  "parent_agent": {"model": "claude-opus-4-7"},
  "capture_source": "razorback-claude-cli-trace"
}
```

`jq -e '.captured >= 1 and (.dispatches | length) == .captured'` returns `true`. Schema matches the AC-2 contract.

**But the manifest is never written during a real run.** The harbor trial loop completed successfully (`result.json.stats.n_completed_trials == 1`, reward `0.667`), yet no `subagent-trace-manifest.json` appeared next to `result.json`. Root cause:

- The writer is invoked from `SpacedockSolverAgent.cleanup()` at `src/razorback/agents/spacedock_solver.py:433-437`.
- Harbor's `BaseAgent` (`.venv/.../harbor/agents/base.py`) declares only `setup` and `run` plus the synchronous `populate_context_post_run` hook. It has no `cleanup` method.
- Harbor's trial runner (`.venv/.../harbor/trial/trial.py`) invokes `self._agent.setup(...)`, `self._agent.run(...)`, and `self._agent.populate_context_post_run(...)` (lines 352, 371/558, 472). It never calls `cleanup`.
- Result: `_maybe_write_subagent_trace_manifest()` is dead code in production. The integration test `test_cleanup_writes_manifest_adjacent_to_provenance` passes because it calls `cleanup` directly, hiding the gap.

**Fix:** move the `_maybe_write_subagent_trace_manifest()` call out of `cleanup` and into `populate_context_post_run` (after the inner-agent delegation), where harbor will actually trigger it. The same path math (`logs_dir.parents[3]`) is correct — verified by running the writer manually against the live cell, which produced the manifest at the right location.

### AC-3 — Smoke gate REJECTS captured=0 cells — PASS in isolation, FAILS in concert with AC-2

`razorback.agents.subagent_smoke` exit codes verified directly:

- Synthetic cell with `captured: 0` → exit code `2`, stderr `subagent-dispatch-missing` (validation V2 task).
- Synthetic cell with `captured: 3` (from real bookreview manifest) → exit code `0` (validation post-fix sanity).
- Missing manifest → exit code `3`, stderr `manifest-missing`.

The matrix dispatcher's hook also fires correctly: live smoke produced `REJECT [1/1] spacedock/bookreview — subagent-dispatch-missing` and the ledger row carries `status='subagent-dispatch-missing'` per the `examples/drivers/dab-paper-matrix.sh:189-218` block. Subprocess wiring + ledger writeback work as designed.

The validator and dispatcher hook are correct. AC-3 fails operationally only because AC-2's writer never runs. Once AC-2 is fixed, AC-3 will pass naturally.

### AC-4 — Pilot smoke bundled — PASS (with caveats)

- T0 standalone CLI mechanism gate cited in the implementation stage report ($0.26, 26s, 4 turns, 1 dispatch tool_use).
- Validation-stage live bookreview cell:
  - `claude-code.txt`: 231 lines, 260925 bytes.
  - `Task` events: 0. `Agent` events: 3. Total dispatch tool_uses: 3.
  - Subagent types dispatched: `spacedock:ensign` × 3.
  - All hashes recorded in the manifest (see AC-2).
- Cost: not surfaced in `result.json` (`cost_usd: null`) — separate cost-telemetry issue tracked elsewhere; out of scope for this entity.

### AC-5 — Existing tests cover the contract — PASS for owned tests; one branch-introduced regression

Targeted owned-test suite (validation V1 task):

```
tests/unit/test_runtime_claude_fo_dispatch.py          6 passed
tests/unit/test_spacedock_solver_fo_dispatch.py        2 passed
tests/unit/test_subagent_traces_writer.py              4 passed
tests/unit/test_subagent_smoke_validator.py            3 passed
tests/integration/test_dab_paper_matrix_spacedock_gate.py     3 passed
tests/integration/test_spacedock_cleanup_writes_trace_manifest.py  2 passed
                                                      ===========
                                                       20 passed in 0.46s
```

All 20 owned tests green.

**However, `test_spacedock_cleanup_writes_trace_manifest.py` is a false-positive test.** Both cases manually invoke `await agent.cleanup(env)` to drive the manifest write. The production runtime never calls `cleanup`, so these tests do not exercise the production code path. Recommend rewriting them to drive `agent.populate_context_post_run(context)` (after the AC-2 fix), so the test catches the next time this hook is moved.

Full pytest (validation V4):
- 624 passed, 12 skipped, 22 warnings, **10 failed** plus 1 collection error.
- Collection error: `tests/unit/test_task_identity_scoring.py` — `ModuleNotFoundError: razorback.score.load`. Reproduces on `main` (the missing module exists on neither branch nor main). Pre-existing.
- Of the 10 failures, **9 reproduce on `main` baseline** (verified by running the same test set against `main`): 5 × `test_generate_matrix_specs*` (sibling 7q `build_spec` signature drift), 2 × `test_claude_benchmark_spec_generator`, 1 × `test_worktree_teardown_preserves_runs` (uv-venv-collision), 1 × `test_generate_matrix_specs::test_matrix_specs_carry_query_mode_batch`. All pre-existing and named in the entity body's acceptable list.
- **1 failure is branch-introduced**: `tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::test_harbor_jobs_resume_round_trip_with_new_trial_name` errors with `TypeError: object MagicMock can't be used in 'await' expression` from the new `_stage_plugin_dirs` (commit `e38f642`). The test's `fake_env.upload_dir` is a sync `MagicMock`, not an `AsyncMock`. This test passes on `main`. The impl ensign's stage report claims "12 → 9 failed"; the actual count after the docker-stage commit is 10. One-line fix in the test fixture (`fake_env.upload_dir = AsyncMock()`) restores it.

## Code review findings

### Blocking

1. **`cleanup()` hook is dead code.** As detailed in AC-2 above. Move the trace-manifest write into `populate_context_post_run`, and rewrite the integration test to drive that hook. Without this, the smoke gate cannot reject a real degraded run — it rejects every run unconditionally.

### Non-blocking

2. **Branch-introduced test regression.** `test_harbor_jobs_resume_round_trip_with_new_trial_name` (see AC-5). One-line `fake_env.upload_dir = AsyncMock()` in the test fixture.
3. **Silent error-swallow in `_maybe_write_subagent_trace_manifest`.** Catches `FileNotFoundError`, `IndexError`, `OSError` into a `logger.debug` call. With AC-2's fix the manifest writer should be loud about failures — the only acceptable silent path is "this is a non-claude runtime." Recommend re-scoping the except clause to `FileNotFoundError` only, and only when the claude-code.txt is genuinely absent (e.g., the cell errored before any agent output).
4. **`_stage_plugin_dirs` silent skip on missing `upload_dir`.** Line `claude.py:141` treats a missing `upload_dir` attribute as "no-op." For real harbor `BaseEnvironment`s this attribute is always present, so the skip path is reachable only from tests. Acceptable as written but worth a comment that the no-op path is test-only.
5. **`subagent_smoke.subagent_smoke.main` exits `64` on bad argv.** Conventional but worth documenting alongside the named exit codes (0/2/3).
6. **`SPACEDOCK_PROMPT_PREFIX_TEMPLATE` hard-codes `/workspace`.** The comment cites session-init events as the source of truth. If harbor ever remounts the workspace at a different path the prefix silently lies. Consider deriving from the spec/runtime config instead of hard-coding.

## Recommended action

Send back to implementation with the AC-2 blocker. Fix is ~10 lines:

```python
def populate_context_post_run(self, context):
    # ...existing inner delegation...
    if self._runtime == "claude":
        self._maybe_write_subagent_trace_manifest()
```

…and adjust the integration test to invoke `populate_context_post_run` rather than `cleanup`. The `cleanup` method can stay (it's a harmless extension point for future harbor versions that grow such a hook) or be removed — either is fine.

After the fix, re-dispatch validation. The live smoke command (`bash examples/drivers/dab-paper-matrix.sh --variants spacedock --datasets bookreview --output-dir <writable-path-under-/Users> --max-cell-budget-usd 5.0` with `RAZORBACK_SPACEDOCK_PLUGIN_DIR=/Users/clkao/git/spacedock` and `DATAAGENTBENCH_DATA_ROOT=/Users/clkao/git/dataagentbench/data`) should produce a `subagent-trace-manifest.json` at `<cell-run-dir>/subagent-trace-manifest.json` with `captured >= 1` and exit cleanly through the smoke gate.

## Test-plan output (commands actually run)

- `uv run pytest tests/unit/test_runtime_claude_fo_dispatch.py tests/unit/test_spacedock_solver_fo_dispatch.py tests/unit/test_subagent_traces_writer.py tests/unit/test_subagent_smoke_validator.py tests/integration/test_dab_paper_matrix_spacedock_gate.py tests/integration/test_spacedock_cleanup_writes_trace_manifest.py -v` → `20 passed in 0.46s`.
- `python -m razorback.agents.subagent_smoke /tmp/validation-smoke-zero/cell-A` (synthetic captured=0) → exit `2`, stderr `subagent-dispatch-missing: ... captured=0`.
- `uv run pytest --ignore=tests/unit/test_task_identity_scoring.py` → `624 passed, 12 skipped, 10 failed in 53.07s`. 9 of 10 reproduce on main.
- `RAZORBACK_SPACEDOCK_PLUGIN_DIR=/Users/clkao/git/spacedock DATAAGENTBENCH_DATA_ROOT=/Users/clkao/git/dataagentbench/data bash examples/drivers/dab-paper-matrix.sh --variants spacedock --datasets bookreview --output-dir <cell-runs-dir> --max-cell-budget-usd 5.0` → trial completed (reward `0.667`), smoke gate rejected with `manifest-missing` (exit 3), claude-code.txt has 3 `Agent` tool_use events targeting `spacedock:ensign`.
- Manual writer invocation on the same cell produced the expected manifest (`captured: 3`); validator then exited 0.

## Cell paths (for re-dispatch)

- Live smoke cell-run-dir: `/Users/clkao/git/razorback/.worktrees/spacedock-ensign-spacedock-solver-real-fo-dispatch-and-smoke-gate/runs/spacedock-fo-final-smoke/spacedock/bookreview/goal1-spacedock-bookreview/703817880c73e047`
- claude-code.txt: `<cell>/bookreview__jqSDLFT/agent/claude-code.txt`
- Manually-written manifest: `<cell>/subagent-trace-manifest.json` (now present; produced via direct writer invocation, not via harbor).
- Dispatch ledger: `/Users/clkao/git/razorback/.worktrees/spacedock-ensign-spacedock-solver-real-fo-dispatch-and-smoke-gate/runs/spacedock-fo-final-smoke/dispatch-ledger.tsv`
- Smoke log: `<cell>/subagent-smoke.log`
