# Validation Report: DAB batch verifier packages common_scaffold imports

Entity: `296yjetkwygm8es8fve7yqy3`
Branch: `spacedock-ensign/dab-batch-verifier-common-scaffold-import`
Validated head: `4fc352e`
Base checked: `main` at `7d80be4`

Gate decision: PASSED, approve to `done`.

## AC-1 - Batch DAB tasks make common_scaffold importable to validators

Status: PASS.

Verified by the materialization regression:

```text
UV_FROZEN=1 uv run --frozen pytest packages/razorback-plugin-dab/tests/unit/test_prepare_batch_query_mode.py::test_batch_mode_materializes_common_scaffold_for_upstream_validators -q
.                                                                        [100%]
1 passed in 0.09s
```

Verified independently against a real affected upstream validator from
`/home/exedev/dataagentbench/data/query_PANCANCER_ATLAS/query2/validate.py`:

```text
uv run --frozen python - <<'PY'
...
PY
imported validate_q2.py from /tmp/tmp94wq7ihk/tasks/PANCANCER_ATLAS/tests
common_scaffold module: /tmp/tmp94wq7ihk/tasks/PANCANCER_ATLAS/tests/common_scaffold/validate/levenshtein.py
has validate: True
```

Inspection confirmed batch materialization copies `data_root/common_scaffold`
into the generated task's `tests/common_scaffold` before installing
`validate_qN.py` files.

## AC-2 - Batch verification emits score artifacts for affected validators

Status: PASS.

Verified by the positive verifier smoke and negative missing-import guard:

```text
UV_FROZEN=1 uv run --frozen pytest packages/razorback-plugin-dab/tests/unit/test_verify_batch_reward_shape.py::test_batch_verify_writes_artifacts_when_validator_imports_common_scaffold packages/razorback-plugin-dab/tests/unit/test_verify_batch_reward_shape.py::test_batch_verify_does_not_mask_validator_import_errors -q
..                                                                       [100%]
2 passed in 0.15s
```

Verified by the env-backed affected-dataset smoke:

```text
DAB_DATA_ROOT=/home/exedev/dataagentbench/data DAB_AFFECTED_DATASET=PANCANCER_ATLAS UV_FROZEN=1 uv run --frozen pytest packages/razorback-plugin-dab/tests/integration/test_batch_common_scaffold_smoke.py::test_affected_dataset_batch_emits_reward_artifacts -q
.                                                                        [100%]
1 passed in 0.22s
```

Verified explicitly by running generated `verify_batch.py` on
`PANCANCER_ATLAS` and parsing both spec §7 verifier artifacts:

```text
returncode=0
reward.json={'reward': 0.0}
reward_per_query_keys=['q1', 'q2', 'q3']
stderr_lines=3
```

The negative missing-import guard still fails loudly and does not emit score
artifacts:

```text
returncode=1
stderr_contains_ModuleNotFoundError=True
stderr_contains_missing_dependency=True
reward_exists=False
reward_per_query_exists=False
```

## AC-3 - Existing DAB batch and per-query behavior stays green

Status: PASS by justified equivalent.

The literal task-body command could not be used as written because
`tests/unit/test_rk_score.py` does not exist in this branch. Running the same
shape from the repo root with the current score test files also hits the
pre-existing package-name collision between repo-level `tests` and
`packages/razorback-plugin-dab/tests`:

```text
UV_FROZEN=1 uv run --frozen pytest packages/razorback-plugin-dab/tests tests/unit/test_runs_aggregate.py tests/unit/test_cli_score.py tests/unit/test_score_render.py tests/unit/test_score_verdict.py tests/unit/test_score_json_schema_snapshot.py -q
ModuleNotFoundError: No module named 'tests.integration.test_ac9_missing_dataset'
ModuleNotFoundError: No module named 'tests.unit.test_cli_surface'
...
!!!!!!!!!!!!!!!!!!! Interrupted: 34 errors during collection !!!!!!!!!!!!!!!!!!!
34 errors in 1.07s
```

I used the equivalent split command pattern already required by the project
layout: DAB plugin tests from the plugin directory, and scoring/runs tests from
the repo root.

```text
cd packages/razorback-plugin-dab
UV_FROZEN=1 uv run --frozen pytest tests/unit -q
...............................s....................................s [ 51%]
....................................................................     [100%]
138 passed, 2 skipped in 3.69s
```

```text
UV_FROZEN=1 uv run --frozen pytest tests/unit/test_runs_aggregate.py tests/unit/test_cli_score.py tests/unit/test_score_render.py tests/unit/test_score_verdict.py tests/unit/test_score_json_schema_snapshot.py -q
....................................                                     [100%]
36 passed in 1.10s
```

Additional broad root-unit sweep, not used as the AC-3 gate, still has an
unrelated stale collection failure in an unchanged test:

```text
UV_FROZEN=1 uv run --frozen pytest tests/unit -q
E   ModuleNotFoundError: No module named 'razorback.score.load'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 1.86s
```

`git diff --name-only main...HEAD -- tests/unit/test_task_identity_scoring.py src/razorback/score`
produced no output, and `git ls-tree main` shows `src/razorback/score/load.py`
is also absent on `main`, so this is not branch-local fallout.

## Code Review

Blocking findings: none.

Non-blocking code findings: none.

Manual review notes:

- Production diff is narrowly scoped to batch task materialization:
  `_materialize_batch_task_dir()` now calls `_install_common_scaffold()` after
  copying `verify_batch.py`, and `_install_common_scaffold()` copies only
  `data_root/common_scaffold` to generated `tests/common_scaffold`, ignoring
  `__pycache__`.
- `verify_batch.py` was not changed. Import failures still propagate before
  `reward.json` or `reward_per_query.json` are written, which keeps verifier
  infrastructure failures distinct from solver wrong-answer failures.
- Solver instructions, workdir materialization, compose generation, and core
  scoring code were not modified.

Validation notes, not code-review findings:

- Requested skill `superpowers:requesting-code-review` is not a registered
  callable skill in this Codex session; the available skill list only contains
  Spacedock/Codex skills. I performed the independent review manually.
- The repo-root form of `pytest packages/razorback-plugin-dab/tests ...` is not
  usable because both the repo and the plugin define a `tests` package. Running
  plugin tests from `packages/razorback-plugin-dab` works and is the correct
  equivalent command for this layout.
- The optional broad `pytest tests/unit` sweep has an unrelated stale import of
  `razorback.score.load` in unchanged root tests. This should be handled
  separately, not on this DAB verifier packaging task.

## Gate Decision

PASSED. AC-1, AC-2, and AC-3 are independently verified with command output;
the real affected DAB validator import resolves from generated task material,
the generated verifier emits parseable `reward.json` and
`reward_per_query.json`, and focused DAB plus score/runs regressions are green.
No blocking code-review findings were found.
