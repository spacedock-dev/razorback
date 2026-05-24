# Validation report (cycle 3) — SpacedockSolverAgent real FO dispatch + smoke gate

Entity: `ne9e1dpbwxs3rp11j07epa81`
Branch: `spacedock-ensign/spacedock-solver-real-fo-dispatch-and-smoke-gate` (HEAD `4b51770`)
Worktree: `.worktrees/spacedock-ensign-spacedock-solver-real-fo-dispatch-and-smoke-gate`
Verdict: **PASS**

## TL;DR

Cycle 3 closes the cycle-1 AC-2 blocker. The trace-manifest write now lives in `SpacedockSolverAgent.run()` after `await self._inner.run(...)` (commit `944297e`), which is the only outer-agent hook harbor's trial runner invokes on a plain `BaseAgent` subclass — both `cleanup()` (no BaseAgent lifecycle) and `populate_context_post_run()` (gated to `BaseInstalledAgent` at `harbor/trial/trial.py:466-471`) are dead-code for this agent. The path-math fix in commit `130815f` (`logs_dir.parents[1]` instead of `parents[3]`) accounts for harbor relocating `agent_dir` contents into `steps/<step>/agent/` only AFTER `run()` returns (`harbor/trial/trial.py:673`). Live bookreview cell now writes the manifest at the right path with `captured: 3`, the smoke validator exits 0, and the matrix dispatcher reports `ok=1`.

All five ACs verified end-to-end on the live revalidation pilot. Full pytest result identical to the cycle-1 baseline (no new regressions from cycle-3 changes). The single pre-existing branch-introduced regression (`test_harbor_jobs_resume_round_trip_with_new_trial_name`, missing `AsyncMock` on `fake_env.upload_dir` after the docker-stage commit) carries over from cycle 1 — captain pre-acknowledged it as the known exception.

## Acceptance criteria

### AC-1 — Real FO dispatch — PASS (carryover)

Inner-agent CLI argv from `job.log` of the cycle-3 pilot cell:

```
claude --verbose --output-format=stream-json --permission-mode=bypassPermissions \
  --max-turns 200 --effort xhigh \
  --allowedTools Bash,Read,Write,Edit,Glob,Grep \
  --disallowedTools '...' \
  --plugin-dir /tmp/razorback-plugins/spacedock \
  --agent spacedock:first-officer \
  --print -- 'ROLE: You are the first-officer ...'
```

Identical to cycle 1. The two required flags are still present, the spacedock plugin is staged into the container at `/tmp/razorback-plugins/spacedock`, the ROLE prefix is prepended.

`claude-code.txt` (post-relocation at `<trial>/steps/main/agent/`, 237 lines, 471320 bytes): JSON-parsing `tool_use` events with `name in {Task, Agent}` yields **3 dispatches** (`Task: 0, Agent: 3`), all targeting `subagent_type: spacedock:ensign`. T0's wire-shape finding holds.

### AC-2 — Per-cell subagent-trace manifest — PASS (the fix target)

Manifest now written automatically by `SpacedockSolverAgent.run()` (commit `944297e`) at `<cell-run-dir>/subagent-trace-manifest.json`:

```json
{
  "schema_version": "razorback-subagent-traces-v1",
  "expected": null,
  "captured": 3,
  "dispatches": [
    {"tool_use_id": "toolu_01NBP9FLbzaWzCuuE2QDNDrB", "subagent_type": "spacedock:ensign", "prompt_sha256": "5c74df5b...", "spawn_index": 0},
    {"tool_use_id": "toolu_01UwfMmymTNGEGiRo7h1XrFi", "subagent_type": "spacedock:ensign", "prompt_sha256": "97b19037...", "spawn_index": 1},
    {"tool_use_id": "toolu_01BbzoXTrCsQ1zwSo36T1P68", "subagent_type": "spacedock:ensign", "prompt_sha256": "1e87359c...", "spawn_index": 2}
  ],
  "parent_agent": {"model": "claude-opus-4-7"},
  "capture_source": "razorback-claude-cli-trace"
}
```

`jq -e '.captured >= 1 and (.dispatches | length) == .captured' <cell>/subagent-trace-manifest.json` → `true`.

Manifest count matches claude-code.txt event count (3 = 3).

Path-math fix (cycle commit `130815f`): during `run()`, `logs_dir` is `<trials-job-dir>/<trial>/agent/` — harbor's `_relocate_dir_contents(self._trial_paths.agent_dir, step_agent_dir)` at `harbor/trial/trial.py:673` only fires AFTER `run()` returns. So the cell-run-dir (adjacent to `provenance.yaml`) is `logs_dir.parents[1]`, not `parents[3]`. Verified by the manifest appearing at the right path on the live cell.

### AC-3 — Smoke gate REJECTS captured=0 cells — PASS

- Smoke validator exit codes (synthetic) unchanged from cycle 1: `0` on captured≥1, `2` on captured=0, `3` on missing manifest.
- Live cell: `uv run python -m razorback.agents.subagent_smoke <cell>` → exit `0`.
- Matrix dispatcher ledger row (`runs/spacedock-fo-cycle3-revalidate/dispatch-ledger.tsv`): `status=ok exit_code=0`.
- Matrix summary: `Matrix done: ok=1 failed=0 skipped=0 (total=1)`. No `subagent-dispatch-missing`.

The cycle-1 misfire (rejecting every cell with `manifest-missing`) is gone.

### AC-4 — Pilot smoke bundled — PASS

- Live cycle-3 pilot cell: `runs/spacedock-fo-cycle3-revalidate/spacedock/bookreview/goal1-spacedock-bookreview/703817880c73e047`.
- claude-code.txt line count: 237. Task events: 0. Agent events: 3. Total dispatch tool_uses: 3.
- Subagent types dispatched: `spacedock:ensign` × 3.
- Reward: `0.667` (matches cycle 1's reward — deterministic since sealed_hash is the same).
- T0 mechanism gate cited from the original implementation stage report still stands.

### AC-5 — Existing tests cover the contract — PASS for owned tests; 1 known regression carries over

Targeted owned-test suite + cycle-3-rewritten integration tests + cycle-1-regression test:

```
tests/unit/test_runtime_claude_fo_dispatch.py                       6 passed
tests/unit/test_spacedock_solver_fo_dispatch.py                     2 passed
tests/unit/test_subagent_traces_writer.py                           4 passed
tests/unit/test_subagent_smoke_validator.py                         3 passed
tests/integration/test_dab_paper_matrix_spacedock_gate.py           3 passed
tests/integration/test_spacedock_cleanup_writes_trace_manifest.py   2 passed  (rewritten cycle 3 — now drives `await agent.run(...)`, not `cleanup`)
tests/integration/test_spacedock_solver_freeze_dir_mechanism.py    10 passed, 1 failed (cycle-1 regression)
tests/unit/test_tools_denied_claude_hook.py                         2 passed
                                                                   ==========
                                                                   32 passed, 1 failed in 0.72s
```

The 1 failure is the same cycle-1 branch-introduced regression: `test_harbor_jobs_resume_round_trip_with_new_trial_name` fails with `TypeError: object MagicMock can't be used in 'await' expression` from `_stage_plugin_dirs` because `fake_env.upload_dir` is sync `MagicMock`. The fix is one line in the test fixture (`fake_env.upload_dir = AsyncMock()`); captain pre-acknowledged this as a known exception in the cycle-3 re-validation directive.

Critically, the cycle-3 rewrite of `test_spacedock_cleanup_writes_trace_manifest.py` now actually exercises the production path. The test drives `await agent.run(...)` with a `_FakeInnerAgent` stub that writes a synthetic claude-code.txt during its `run()` call — exactly the lifecycle harbor exposes for `BaseAgent` subclasses. The pre-relocation directory layout in the test fixture (`<cell-run-dir>/<trial>/agent/`) matches what harbor exposes during `run()`. The test no longer masks a hook-vs-lifecycle mismatch.

Full pytest (`uv run pytest --ignore=tests/unit/test_task_identity_scoring.py`):
- 624 passed, 12 skipped, 22 warnings, **10 failed**.
- Failure breakdown identical to cycle 1: 9 pre-existing-on-main + 1 branch-introduced regression carried over from cycle 1. No new regressions from cycle-3 changes.
- The `test_task_identity_scoring.py` collection error is pre-existing on main (`razorback.score.load` missing from both branches).

## Code review findings (cycle 3 delta)

### Blocking

None.

### Non-blocking (carried over from cycle 1)

1. **Branch-introduced test regression** (`test_harbor_jobs_resume_round_trip_with_new_trial_name`) — captain pre-acknowledged.
2. **Silent error-swallow in `_maybe_write_subagent_trace_manifest`** (catches `FileNotFoundError`/`IndexError`/`OSError` → `logger.debug`). Now that the writer correctly fires on every claude-runtime run, the silent path is reachable only when claude-code.txt is genuinely missing (e.g., cell errored before the inner agent produced output). Acceptable, recommend narrowing in a follow-up.
3. **`_stage_plugin_dirs` silent no-op on missing `upload_dir` attribute** — test-only path; acceptable.
4. **`SPACEDOCK_PROMPT_PREFIX_TEMPLATE` hard-codes `/workspace`** — acceptable as harbor's current behavior; document the coupling.
5. **`subagent_smoke.main` exits `64` on bad argv** — undocumented but conventional.

### New (cycle 3)

6. **Stale `ABOUTME` comment in `test_spacedock_cleanup_writes_trace_manifest.py`** (line 2: "logs_dir.parents[3]") — the docstring on the test function correctly says `parents[1]` after cycle commit `130815f`, but the two-line ABOUTME header still says `parents[3]`. Cosmetic; one-line fix.
7. **`cleanup()` and `populate_context_post_run()` are now empty delegates** carrying explanatory comments. The comments correctly name the harbor gate (`BaseInstalledAgent` at `trial.py:466-471`) and warn against re-introducing the dead-code mistake. Good defensive practice.

## Recommended action

**PASS**. The cycle-3 fix correctly addresses the AC-2 blocker (writer now invoked from the actual outer-agent hook harbor calls), the cycle-3 path-math fix correctly accounts for harbor's post-run relocation, the integration test is no longer a false positive, and live revalidation reproduces the impl ensign's claim (`captured: 3`, `Matrix done: ok=1 failed=0`). All other ACs verified end-to-end; full-suite results identical to cycle-1 baseline. Recommend FO proceed with mod-block + local no-ff merge + archive per captain's pre-authorization.

The follow-up entity `m2 spacedock-solver-base-installed-agent-feasibility` (filed by captain during cycle 2) tracks the larger refactor of having `SpacedockSolverAgent` subclass `BaseInstalledAgent` instead of `BaseAgent`, which would relocate the manifest write to the more canonical `populate_context_post_run` hook. That is investigation-only and orthogonal to this entity's verdict.

## Test-plan output (commands actually run)

- `uv run pytest tests/unit/test_runtime_claude_fo_dispatch.py tests/unit/test_spacedock_solver_fo_dispatch.py tests/unit/test_subagent_traces_writer.py tests/unit/test_subagent_smoke_validator.py tests/integration/test_dab_paper_matrix_spacedock_gate.py tests/integration/test_spacedock_cleanup_writes_trace_manifest.py tests/integration/test_spacedock_solver_freeze_dir_mechanism.py tests/unit/test_tools_denied_claude_hook.py -v` → `32 passed, 1 failed in 0.72s` (the 1 failure is the cycle-1 carryover).
- `uv run pytest --ignore=tests/unit/test_task_identity_scoring.py` → `624 passed, 12 skipped, 10 failed in 52.82s`. Failure set identical to cycle 1.
- `RAZORBACK_SPACEDOCK_PLUGIN_DIR=/Users/clkao/git/spacedock DATAAGENTBENCH_DATA_ROOT=/Users/clkao/git/dataagentbench/data bash examples/drivers/dab-paper-matrix.sh --variants spacedock --datasets bookreview --output-dir <writable> --max-cell-budget-usd 5.0` → `Matrix done: ok=1 failed=0 skipped=0`. Manifest written automatically at cell-run-dir; smoke validator exits 0; ledger row `status=ok`. claude-code.txt has 3 `Agent` tool_use events targeting `spacedock:ensign`. Reward `0.667`.

## Cell paths (for the captain-facing summary)

- Pilot cell-run-dir: `/Users/clkao/git/razorback/.worktrees/spacedock-ensign-spacedock-solver-real-fo-dispatch-and-smoke-gate/runs/spacedock-fo-cycle3-revalidate/spacedock/bookreview/goal1-spacedock-bookreview/703817880c73e047`
- claude-code.txt (post-relocation): `<cell>/bookreview__wCUsswN/steps/main/agent/claude-code.txt` (237 lines, 471320 bytes, 3 `Agent` events)
- Manifest: `<cell>/subagent-trace-manifest.json` (`captured: 3`)
- Dispatch ledger: `runs/spacedock-fo-cycle3-revalidate/dispatch-ledger.tsv` (single row, `status=ok exit_code=0`)
