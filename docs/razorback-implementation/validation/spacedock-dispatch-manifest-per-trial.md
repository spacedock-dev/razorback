# Validation: Spacedock dispatch manifests are per trial

Entity: `bpb83at5rrcm0z77maf6bbqb`  
Branch: `spacedock-ensign/spacedock-dispatch-manifest-per-trial`  
Worktree: `/home/exedev/razorback/.worktrees/spacedock-ensign-spacedock-dispatch-manifest-per-trial`  
Implementation range reviewed: `dc3750d60e1867c19f2a1b4425e245666f5c7608..68d9e8cbf9203283892ad9d03edf31905ce8493a`

Gate decision: APPROVE to `done`.

## Files Changed

Command:

```bash
git diff --name-only dc3750d60e1867c19f2a1b4425e245666f5c7608..68d9e8cbf9203283892ad9d03edf31905ce8493a
```

Output:

```text
docs/razorback-implementation/spacedock-dispatch-manifest-per-trial.md
src/razorback/agents/spacedock_solver.py
src/razorback/agents/subagent_smoke.py
src/razorback/agents/subagent_traces.py
src/razorback/audit/cli.py
src/razorback/audit/dispatch_manifests.py
tests/integration/test_dab_paper_matrix_spacedock_gate.py
tests/integration/test_spacedock_cleanup_writes_trace_manifest.py
tests/unit/audit/conftest.py
tests/unit/audit/test_rk_audit_cli.py
tests/unit/test_subagent_smoke_validator.py
tests/unit/test_subagent_traces_writer.py
```

Command:

```bash
git diff --check dc3750d60e1867c19f2a1b4425e245666f5c7608..68d9e8cbf9203283892ad9d03edf31905ce8493a
```

Output: no output; exit 0.

## Acceptance Criteria

### AC-1 - PASS

Full parallel runs emit one dispatch manifest per trial. Verified by: an automated fixture with at least two parallel Spacedock trials asserts both trial directories contain distinct manifests.

Command:

```bash
uv run pytest tests/integration/test_spacedock_cleanup_writes_trace_manifest.py tests/unit/test_subagent_traces_writer.py -x -v
```

Output proving the clause:

```text
collected 9 items
tests/integration/test_spacedock_cleanup_writes_trace_manifest.py::test_parallel_spacedock_runs_write_distinct_trial_manifests PASSED [ 44%]
tests/unit/test_subagent_traces_writer.py::test_writer_counts_codex_spawn_agent_events PASSED [ 88%]
============================== 9 passed in 0.28s ===============================
```

Artifact/files checked: `src/razorback/agents/spacedock_solver.py`, `src/razorback/agents/subagent_traces.py`, `tests/integration/test_spacedock_cleanup_writes_trace_manifest.py`, `tests/unit/test_subagent_traces_writer.py`.

### AC-2 - PASS

Job-level provenance no longer overwrites trial provenance. Verified by: tests assert a two-trial run has two distinct manifest payloads plus any rollup inventory, with no shared final-write collapse.

Command:

```bash
uv run pytest tests/integration/test_spacedock_cleanup_writes_trace_manifest.py tests/unit/test_subagent_traces_writer.py -x -v
```

Output proving the clause:

```text
tests/integration/test_spacedock_cleanup_writes_trace_manifest.py::test_parallel_spacedock_runs_write_distinct_trial_manifests PASSED [ 44%]
============================== 9 passed in 0.28s ===============================
```

The passing fixture asserts `not (run_dir / "subagent-trace-manifest.json").exists()` and checks distinct per-trial `tool_use_id` values for `trial-a__aaaa` and `trial-b__bbbb`.

### AC-3 - PASS

Strict audit can fail closed on missing trial manifests. Verified by: an audit fixture with one manifest-bearing trial and one missing trial emits a coverage failure for the missing trial.

Command:

```bash
uv run pytest tests/unit/audit/test_rk_audit_cli.py -x -v
```

Output proving the clause:

```text
collected 16 items
tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_strict_fails_on_missing_spacedock_trial_manifest PASSED [ 87%]
tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_strict_passes_when_spacedock_trial_manifests_present PASSED [ 93%]
tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_strict_accepts_legacy_single_spacedock_root_manifest PASSED [100%]
============================== 16 passed in 2.00s ==============================
```

Independent CLI probe:

```text
"summary": {
  "clean": 1,
  "coverage_missing": 1,
  "tainted": 0
}
"trial_id": "trial-b__bbbb"
"missing_reason": "spacedock_dispatch_manifest_absent"
TaintFindingsError: rk audit --policy strict found 1 non-clean trial(s) (tainted=0, coverage_missing=1)
exit=23
```

Artifact/files checked: `src/razorback/audit/dispatch_manifests.py`, `src/razorback/audit/cli.py`, `tests/unit/audit/conftest.py`, `tests/unit/audit/test_rk_audit_cli.py`.

### AC-4 - PASS

Smoke and legacy single-trial layouts keep working. Verified by: the existing Spacedock solver prompt/provenance tests and a single-trial audit fixture stay green.

Command:

```bash
uv run pytest tests/unit/test_subagent_smoke_validator.py tests/integration/test_dab_paper_matrix_spacedock_gate.py -x -v
```

Output proving the smoke clause:

```text
collected 9 items
tests/unit/test_subagent_smoke_validator.py::test_validator_accepts_legacy_single_trial_root_manifest PASSED [ 66%]
tests/integration/test_dab_paper_matrix_spacedock_gate.py::test_dispatcher_hook_invokes_smoke_validator_via_subprocess PASSED [ 77%]
============================== 9 passed in 0.51s ===============================
```

Command:

```bash
uv run pytest tests/unit/test_runs_aggregate.py tests/unit/test_diff_per_trial_outcomes_sidecar.py -x -v
```

Output proving the score guard:

```text
collected 13 items
tests/unit/test_diff_per_trial_outcomes_sidecar.py::test_run_dir_summary_shape_unchanged PASSED [ 92%]
============================== 13 passed in 0.79s ==============================
```

Artifact/files checked: `src/razorback/agents/subagent_smoke.py`, `tests/unit/test_subagent_smoke_validator.py`, `tests/integration/test_dab_paper_matrix_spacedock_gate.py`. No score reducer files changed in the implementation range.

## Acceptance Command

Command from plan T7:

```bash
uv run pytest tests/unit/test_subagent_traces_writer.py tests/integration/test_spacedock_cleanup_writes_trace_manifest.py tests/unit/test_subagent_smoke_validator.py tests/integration/test_dab_paper_matrix_spacedock_gate.py tests/unit/audit/test_rk_audit_cli.py -x -v
```

Output:

```text
collected 34 items
tests/integration/test_spacedock_cleanup_writes_trace_manifest.py::test_parallel_spacedock_runs_write_distinct_trial_manifests PASSED [ 26%]
tests/unit/test_subagent_smoke_validator.py::test_validator_accepts_legacy_single_trial_root_manifest PASSED [ 44%]
tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_strict_fails_on_missing_spacedock_trial_manifest PASSED [ 94%]
tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_strict_passes_when_spacedock_trial_manifests_present PASSED [ 97%]
tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_strict_accepts_legacy_single_spacedock_root_manifest PASSED [100%]
============================== 34 passed in 1.35s ==============================
```

## Full Test Run

Command:

```bash
uv run pytest
```

Output:

```text
collected 739 items / 1 error
ERROR collecting tests/unit/test_task_identity_scoring.py
tests/unit/test_task_identity_scoring.py:5: in <module>
    from razorback.score.load import load_run_dir
E   ModuleNotFoundError: No module named 'razorback.score.load'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 2.27s ===============================
```

Assessment: this is a pre-existing full-suite collection failure outside the implementation range. `git diff --name-only` shows no score package files changed, and `git ls-tree -r main --name-only | rg 'src/razorback/score|test_task_identity_scoring'` shows `tests/unit/test_task_identity_scoring.py` and no `src/razorback/score/load.py` on main.

## Code Review

Applied `superpowers:requesting-code-review` using the local skill definition at `/home/exedev/.codex/.tmp/plugins/plugins/superpowers/skills/requesting-code-review/SKILL.md` and template `/home/exedev/.codex/.tmp/plugins/plugins/superpowers/skills/requesting-code-review/code-reviewer.md`. Codex does not expose the Task subagent tool in this dispatch, so the template checks were applied manually against the implementation range.

Blocking findings: none.

Non-blocking findings: none.

Notes:

- The implementation keeps changes scoped to the manifest writer, Spacedock hook, smoke validator, audit discovery, and focused tests.
- The run-dir contract check uses `manifest.json.per_trial_paths` and `spec.frozen.yaml` to identify Spacedock trials for audit; new tests cover multi-trial, missing per-trial manifest, complete per-trial manifests, and legacy single-trial root fallback.
- Full `uv run pytest` remains blocked by the unrelated `razorback.score.load` collection error documented above.

## Gate

APPROVE to `done`. AC-1 through AC-4 pass with focused acceptance evidence, the score-adjacent guard passes, and no blocking or non-blocking code-review findings were found in the implementation range.
