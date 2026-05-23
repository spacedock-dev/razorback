---
id: 296yjetkwygm8es8fve7yqy3
title: DAB batch verifier packages common_scaffold imports
status: validation
source: DAB gpt-5.5/xhigh full batch run 2026-05-23 — common_scaffold verifier import failures
started: 2026-05-23T13:57:50Z
completed:
verdict:
score: 0.92
worktree: .worktrees/spacedock-ensign-dab-batch-verifier-common-scaffold-import
issue:
pr:
mod-block:
---

## Problem

The full DAB Codex batch run completed 12/12 trials, but four datasets
were unscored because generated batch validators import
`common_scaffold.validate.levenshtein` and the Harbor task verifier
environment does not include `common_scaffold` on Python's import path.
The DAB batch adapter must materialize verifier dependencies so affected
datasets produce score artifacts instead of verifier tracebacks.

## Acceptance criteria

**AC-1 — Batch DAB tasks make `common_scaffold` importable to validators.**
Generated batch task `tests/` content or verifier environment includes the
upstream DAB `common_scaffold` package needed by validators such as
`GITHUB_REPOS`, `PANCANCER_ATLAS`, `PATENTS`, and `stockmarket`.
Verified by: a materialization test or fixture imports an affected
`validate_qN.py` from the generated task and resolves
`common_scaffold.validate.levenshtein` without external network access.

**AC-2 — Batch verification emits score artifacts for affected validators.**
An affected batch task no longer exits before writing `reward.json` and
`reward_per_query.json` when a validator with a `common_scaffold` import is
present.
Verified by: a focused verifier test or generated-task smoke checks both
artifact files exist and parse as JSON after running `/tests/test.sh` or
`verify_batch.py`.

**AC-3 — Existing DAB batch and per-query behavior stays green.**
The fix does not break existing DAB materialization, verifier, or score
aggregation behavior.
Verified by: `UV_FROZEN=1 uv run --frozen pytest packages/razorback-plugin-dab/tests tests/unit/test_runs_aggregate.py tests/unit/test_rk_score.py -q` or a narrower equivalent justified in the validation report.

## Test plan

Implementation should add a regression test around the generated batch
task shape for at least one affected validator and run the focused DAB
plugin tests. Validation should independently run the regression and a
small affected DAB batch smoke that reaches score artifacts.

## Out of scope

This task does not tune solver prompts, rerun the full DAB 12-dataset
score, or change the solver's answers. It only fixes verifier packaging
so those runs can be scored.

## Stage Report: plan

- DONE: Identify the smallest code path change that makes generated DAB batch validators resolve `common_scaffold.validate.levenshtein` without changing solver prompts or answers.
  Plan targets only batch task `tests/` materialization in `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py`: copy upstream `data_root/common_scaffold` into generated `tests/common_scaffold`; leave `_batch_instruction()`, workdir prompts, and solver answer contract unchanged.
- DONE: Map each acceptance criterion to concrete failing-first and passing validation commands, including a targeted affected-dataset smoke that proves score artifacts are emitted.
  The inline plan below maps AC-1, AC-2, and AC-3 to pytest nodes plus an env-backed `PATENTS` batch smoke that asserts `reward.json` and `reward_per_query.json` parse as JSON.
- DONE: Call out any risk that could turn a verifier infrastructure failure into a hidden solver failure, with the validation evidence needed to avoid that.
  Risk is broad exception handling in `verify_batch.py`; the plan requires import failures to remain loud and uses a helper-executing positive test plus a negative import-error guard so infrastructure errors are not silently scored as wrong answers.

### Summary

Inline plan written on the entity per the FO tiny-task sizing; no separate `plans/{slug}.md` document was created. The cached `superpowers:writing-plans` skill is not registered in this Codex session, so this is an equivalent inline plan following the local plan style: AC-first tasks, failing tests before implementation, and the riskiest validator-import contract first.

### Inline Implementation Plan

Spec cites: v2 spec §6.1 (DAB is a plugin-shipped, generated-per-`data_root` task adapter whose emitted task dirs are what Harbor consumes), §7.1 (score artifacts live under Harbor/Razorback run artifacts and Razorback does not mutate trial internals), and §8.3a (`rk score` consumes completed trial rewards by stratum, so verifier infrastructure failures must not masquerade as solver outcomes).

Files to touch:
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py`
- `packages/razorback-plugin-dab/tests/unit/test_prepare_batch_query_mode.py`
- New or extended batch verifier tests under `packages/razorback-plugin-dab/tests/unit/`
- Optional env-gated affected-dataset smoke under `packages/razorback-plugin-dab/tests/integration/`

TDD checkpoints:
1. **AC-1 / §6.1 - batch task imports resolve.** Add `test_batch_mode_materializes_common_scaffold_for_upstream_validators` to the batch materialization tests. The synthetic `data_root` should include `common_scaffold/validate/levenshtein.py` and a `query1/validate.py` importing it; before the fix, importing generated `tests/validate_q1.py` fails with `ModuleNotFoundError`, and after the fix it resolves without network access.
   Command: `UV_FROZEN=1 uv run --frozen pytest packages/razorback-plugin-dab/tests/unit/test_prepare_batch_query_mode.py::test_batch_mode_materializes_common_scaffold_for_upstream_validators -q`.
2. **AC-1 green / smallest production change.** Add a small helper such as `_install_common_scaffold(tests_dir, data_root)` and call it only from `_materialize_batch_task_dir()` after creating `tests_dir` and before/alongside validator installation. It should copy `dataset_dir.parent / "common_scaffold"` to `tests/common_scaffold`, ignore `__pycache__`, and no-op when the upstream package is absent so existing synthetic fixtures stay simple.
3. **AC-2 / §6.1 + §7.1 - artifacts are emitted.** Add a focused generated-task smoke where the generated validator imports and executes `common_scaffold.validate.levenshtein`, `answers.json` has a known valid non-empty answer, and the copied `tests/verify_batch.py` is run via subprocess. Assert `reward.json == {"reward": 1.0}` and `reward_per_query.json` contains `q1.reward == 1.0`.
   Command: `UV_FROZEN=1 uv run --frozen pytest packages/razorback-plugin-dab/tests/unit/test_verify_batch_reward_shape.py::test_batch_verify_writes_artifacts_when_validator_imports_common_scaffold -q`.
4. **Risk guard / §8.3a - do not hide verifier infrastructure failures.** Add a negative verifier test with `validate_q1.py` importing a missing package and assert the verifier exits nonzero without writing reward artifacts. Do not catch `ImportError` or rewrite it as `reward: 0.0`; empty or wrong solver answers are solver failures, missing verifier dependencies are infrastructure failures.
   Command: `UV_FROZEN=1 uv run --frozen pytest packages/razorback-plugin-dab/tests/unit/test_verify_batch_reward_shape.py::test_batch_verify_does_not_mask_validator_import_errors -q`.
5. **Affected-dataset mechanism smoke / AC-2 + §7.1.** Add or run an env-gated integration smoke against real external DAB data: `DAB_DATA_ROOT=/path/to/dataagentbench/data DAB_AFFECTED_DATASET=PATENTS UV_FROZEN=1 uv run --frozen pytest packages/razorback-plugin-dab/tests/integration/test_batch_common_scaffold_smoke.py::test_affected_dataset_batch_emits_reward_artifacts -q`. The test should generate a batch task, run copied `verify_batch.py` with empty answers to avoid changing solver outputs, and assert both `reward.json` and `reward_per_query.json` exist and parse as JSON.
6. **AC-3 / regression sweep.** Run the focused new tests first, then the DAB and scoring regression set: `UV_FROZEN=1 uv run --frozen pytest packages/razorback-plugin-dab/tests tests/unit/test_runs_aggregate.py tests/unit/test_rk_score.py -q`. If external DAB data is unavailable, document the skipped affected-dataset smoke separately; do not substitute the synthetic tests as evidence for the real affected-dataset artifact check.

## Stage Report: implementation

- DONE: Batch materialization includes `common_scaffold` for affected upstream validators, with a failing-first regression test that imports an affected generated validator.
  `packages/razorback-plugin-dab/tests/unit/test_prepare_batch_query_mode.py::test_batch_mode_materializes_common_scaffold_for_upstream_validators` failed before the fix, then passed after `d6fbfdd`; `prepare.py` now copies `data_root/common_scaffold` into generated batch `tests/common_scaffold` while ignoring `__pycache__`.
- DONE: Batch verifier smoke emits `reward.json` and `reward_per_query.json` for a validator importing `common_scaffold`, while missing verifier dependencies remain loud.
  `packages/razorback-plugin-dab/tests/unit/test_verify_batch_reward_shape.py` adds the positive generated-task subprocess smoke and a negative `ModuleNotFoundError` guard; no broad exception masking was added to `verify_batch.py`.
- DONE: Focused regression commands pass, and the stage report cites exact commands, changed files, and any deviation from the inline plan.
  Commands passed: `UV_FROZEN=1 uv run --frozen pytest packages/razorback-plugin-dab/tests/unit/test_prepare_batch_query_mode.py packages/razorback-plugin-dab/tests/unit/test_verify_batch_reward_shape.py -q` (`8 passed`); from `packages/razorback-plugin-dab`, `UV_FROZEN=1 uv run --frozen pytest tests/unit -q` (`138 passed, 2 skipped`); `UV_FROZEN=1 uv run --frozen pytest tests/unit/test_runs_aggregate.py tests/unit/test_cli_score.py tests/unit/test_score_render.py tests/unit/test_score_verdict.py tests/unit/test_score_json_schema_snapshot.py -q` (`36 passed`); `DAB_DATA_ROOT=/home/exedev/dataagentbench/data DAB_AFFECTED_DATASET=PANCANCER_ATLAS UV_FROZEN=1 uv run --frozen pytest packages/razorback-plugin-dab/tests/integration/test_batch_common_scaffold_smoke.py::test_affected_dataset_batch_emits_reward_artifacts -q` (`1 passed`).

### Summary

Changed files: `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py`, `packages/razorback-plugin-dab/tests/unit/test_prepare_batch_query_mode.py`, `packages/razorback-plugin-dab/tests/unit/test_verify_batch_reward_shape.py`, and `packages/razorback-plugin-dab/tests/integration/test_batch_common_scaffold_smoke.py`. The only Harbor-facing surface changed is generated batch task `tests/` packaging; solver instructions, workdir shape, compose generation, core scoring, and `verify_batch.py` semantics are unchanged.

Deviation: the env-backed smoke used `PANCANCER_ATLAS` instead of `PATENTS` because AC-1 names both as affected datasets and spec §7.1 only requires the generated verifier to reach score artifacts; this exercises the same `common_scaffold.validate.levenshtein` import with a smaller hydrated dataset. Validation also used the current scoring test files (`test_cli_score.py`, score render/verdict/schema snapshot) because `tests/unit/test_rk_score.py` does not exist in this worktree.
