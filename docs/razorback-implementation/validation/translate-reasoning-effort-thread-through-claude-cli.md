# Validation: translate.py threads reasoning_effort through to harbor on the claude-cli path

Entity: `translate-reasoning-effort-thread-through-claude-cli`
Branch: `spacedock-ensign/translate-reasoning-effort-thread-through-claude-cli`
Reviewed commits: `3c44cbb` (RED test), `3f56615` (GREEN fix)
Validation worktree HEAD at start of validation: `eb8b405` (impl stage report)

## AC verdicts

### AC-1 — `translate.py` threads `reasoning_effort` to `harbor_agent_kwargs` on the claude-cli path

**PASS.**

- `grep -n "reasoning_effort" src/razorback/translate.py` matches at lines 108, 110, 141, 194. Line 194 is the new claude-cli kwargs assignment inside the `if getattr(spec.agent, "kind", None) == "claude-cli":` branch (translate.py:178-202).
- Unit test at `tests/unit/test_translate_claude_cli_kwargs.py::test_claude_cli_threads_reasoning_effort_into_kwargs` reproduces RED→GREEN:
  - RED at pre-fix translate.py state (commit `3c44cbb`): `1 failed in 0.12s` with diff `Right contains 1 more item: {'reasoning_effort': 'xhigh'}` against `agent_cfg.kwargs`.
  - GREEN at post-fix state (commit `3f56615` and entity HEAD `eb8b405`): `1 passed in 0.10s`.
- The 2-line diff at translate.py:193-194 mirrors the established codex-branch pattern at translate.py:107-108.

### AC-2 — `rk run --explain` surfaces `reasoning_effort` on all three workspace variants

**PASS.**

JSON path is `.agent.kwargs.reasoning_effort` for the claude-cli direct shape, and `.agent.kwargs.harbor_agent_kwargs.reasoning_effort` for the spacedock-solver nested shape — confirmed empirically. The AC text is normative on the value `"xhigh"`, not on the dotted path.

```
$ DATAAGENTBENCH_DATA_ROOT=... uv run rk run --explain --explain-format json --runs-dir .worktree-runs \
    examples/specs/goal1/direct-structured/agnews.yaml | jq '.agent.kwargs'
{
  "allowed_tools": "Bash,Read,Write,Edit,Glob,Grep",
  "reasoning_effort": "xhigh"
}

$ ... examples/specs/goal1/direct-minimal/agnews.yaml | jq '.agent.kwargs.reasoning_effort'
"xhigh"

$ ... /tmp/k4-validation/spacedock-agnews.frozen.yaml | jq '.agent.kwargs.harbor_agent_kwargs.reasoning_effort'
"xhigh"
```

The spacedock variant required `rk freeze --allow-missing` first because direct `rk run --explain` rejects unfrozen spacedock_solver specs (`SpecError: spacedock_solver spec must be frozen`). Freeze produced a side-effect write to `examples/specs/goal1/spacedock/provenance.yaml`; that artifact is gitignored (not tracked in working tree post-freeze) — verified clean via `git status` after the run. No regression on the spacedock path: it continues to surface `reasoning_effort: "xhigh"` correctly.

### AC-3 — Audit for declared-but-dropped agent fields on `ClaudeCliAgentBlock`

**PASS.**

Schema enumeration at `src/razorback/spec/schema.py:39-46` declares exactly 6 fields. Cross-checked against the post-fix kwargs builder at `src/razorback/translate.py:178-202`:

| Schema field | Schema cite | Threading status | Code cite (post-fix) |
|---|---|---|---|
| `kind: Literal["claude-cli"]` | schema:41 | dispatch metadata (literal, not a kwarg) | translate.py:178 |
| `model: str = "claude-opus-4-5"` | schema:42 | threaded as `AgentConfig.model_name` | translate.py:197 |
| `sampling: SamplingBlock` | schema:43 | guarded: `SpecError` if `temperature` non-zero (harbor ClaudeCode has no temperature kwarg) | translate.py:183-188 |
| `tools_allowed: list[str]` | schema:44 | threaded as `kwargs["allowed_tools"]` (comma-joined) | translate.py:191-192 |
| `prompt_file: Path \| None` | schema:45 | **NOT threaded — captain-approved deferral at plan stage; recommend sibling entity** | translate.py:178-200 (absent) |
| `reasoning_effort: str \| None` | schema:46 | threaded as `kwargs["reasoning_effort"]` (post-fix) | translate.py:193-194 |

Per the dispatch instruction, `prompt_file` is captain-authorized as deferred-to-sibling per plan-stage approval and is NOT re-raised as REJECT-blocking. No additional silently-dropped fields beyond `prompt_file` exist on `ClaudeCliAgentBlock`. Harbor 0.6.6 (`harbor/agents/installed/claude_code.py:40-46`) has no `reasoning_summary` CLI flag, so there is no analog of the codex-branch `reasoning_summary` threading (translate.py:109-110) to mirror on the claude-cli path.

### AC-4 — Existing pytest stays green; no regressions in spacedock kwargs threading

**PASS.**

Pytest invocation: `DATAAGENTBENCH_DATA_ROOT=... uv run pytest tests/ --continue-on-collection-errors` (the `--continue-on-collection-errors` flag is required because `tests/unit/test_task_identity_scoring.py` references the deleted `razorback.score.load` module — a pre-existing baseline condition unrelated to translator kwargs threading).

| State | translate.py | pytest result |
|---|---|---|
| Pre-fix (commit `3c44cbb`) | RED branch (only `allowed_tools` threaded) | `6 failed, 704 passed, 12 skipped, 22 warnings, 1 error` |
| Post-fix (entity HEAD `eb8b405`) | GREEN branch (both kwargs threaded) | `5 failed, 705 passed, 12 skipped, 22 warnings, 1 error` |

Delta = exactly +1 test passing (the new AC-1 test `test_claude_cli_threads_reasoning_effort_into_kwargs`), -1 failure. The remaining 5 failures + 1 collection error are byte-identical across pre- and post-fix runs:

- `tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::test_codex_runtime_dispatch_constructs_inner_agent`
- `tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::test_harbor_jobs_resume_round_trip_with_new_trial_name`
- `tests/integration/test_worktree_teardown_preserves_runs.py::test_worktree_remove_force_does_not_destroy_runs`
- `tests/unit/test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch`
- `tests/unit/test_rk_research_new.py::test_rk_research_new_creates_scaffold_tree`
- `ERROR tests/unit/test_task_identity_scoring.py` (collection-time `ModuleNotFoundError: razorback.score.load`)

None of these touch the claude-cli kwargs builder. Pre-existing `tests/unit/test_translate_codex_direct.py`, `tests/unit/test_translate_spacedock_solver_import_path.py`, `tests/unit/test_translate_harbor_block.py` remain GREEN.

## Code review

Review performed inline by the validation ensign (no Agent dispatch available in this runtime). Scope: the 2 substantive commits — `3c44cbb` (RED test) and `3f56615` (GREEN fix, 2-line edit at translate.py:193-194).

### Strengths

- Pattern mirrors `translate.py:107-108` (codex branch) exactly: same `is not None` guard, same kwargs key, same minimal scope. No clever divergence.
- Two-commit TDD discipline (RED then GREEN) with both SHAs reproducibly cited; the RED→GREEN transition was independently re-run in this validation pass.
- Test fixture is hermetic: in-memory YAML through `parse_spec_text`, `tmp_path/.env` for `resolve_claude_auth`, calls real `spec_to_job_config` end-to-end (no mocks on internal logic).
- Test asserts full `kwargs` dict equality rather than key presence — catches drift in either direction.
- ABOUTME headers on the new test file follow repo convention.
- Schema audit in impl stage report exhaustively enumerates all 6 `ClaudeCliAgentBlock` fields. Independent re-enumeration in this validation pass confirms the table.

### Findings

**Blocking (REJECT-class): none.**

**Non-blocking (captain-visibility):**
1. The impl recommends filing a follow-on entity for `prompt_file` threading. This is captain-approved deferral, not a defect, but the sibling entity is not yet filed. Surfaced for captain visibility per dispatch instructions.
2. The freeze step on the spacedock variant for AC-2 verification writes `examples/specs/goal1/spacedock/provenance.yaml` as a side effect. The artifact is gitignored and did not persist in working-tree state after `git status` — but a captain rerunning AC-2 should be aware that `rk freeze --allow-missing` is currently required for the spacedock path.

No evidence of additional silently-dropped fields beyond `prompt_file`.

### Assessment

**Ready to merge.** Implementation is a 2-line mechanical translator fix that mirrors an established same-file precedent, locked by a hermetic unit test, with no behavioral regressions outside the targeted code path. All 4 ACs verified independently.

## Evidence artifacts

- `/tmp/k4-validation/pytest-green.txt` — full pytest output on entity HEAD
- `/tmp/k4-validation/pytest-baseline.txt` — full pytest output on pre-fix (`3c44cbb`)
- `/tmp/k4-validation/spacedock-agnews.frozen.yaml` — frozen spec used for AC-2 spacedock-variant explain

## Gate decision: APPROVE
