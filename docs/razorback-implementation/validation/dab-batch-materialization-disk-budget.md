# Validation: DAB batch materialization fits ext4 disk budget

**Entity:** `docs/razorback-implementation/dab-batch-materialization-disk-budget.md`  
**Branch:** `spacedock-ensign/dab-batch-materialization-disk-budget`  
**Validated commits:** `78f610c`, `077a025`, `5d9fad7`  
**Validation date:** 2026-05-24  
**Role asset read:** `/home/exedev/.codex/plugins/cache/spacedock/spacedock/0.12.0/skills/ensign/SKILL.md`

## Baseline

Clean checkout before validation:

```text
$ git status --short --branch
## spacedock-ensign/dab-batch-materialization-disk-budget
```

Required full sweep:

```text
$ uv run pytest
collected 739 items / 1 error
ERROR tests/unit/test_task_identity_scoring.py
E   ModuleNotFoundError: No module named 'razorback.score.load'
```

This collection error is pre-existing on `main`: `git ls-tree main:src/razorback/score` contains only `__init__.py`, `render.py`, and `verdict.py`, and this branch does not modify `tests/unit/test_task_identity_scoring.py` or `src/razorback/score`.

Focused branch suites:

```text
$ uv run pytest packages/razorback-plugin-dab/tests/unit/test_prepare_bind_materialize.py -v
11 passed, 1 skipped in 0.35s

$ uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_bindmount_source.py -v
6 passed in 0.04s

$ uv run pytest packages/razorback-plugin-dab/tests/integration/test_file_backed_db_readonly_mount.py -v -s
1 passed, 2 warnings in 13.62s

$ uv run pytest packages/razorback-plugin-dab/tests/unit/ -q
141 passed, 2 skipped in 3.90s
```

## AC-1 - PASS

**Verified by:** `rk run --explain --explain-format json` exits 0 and the JSON assertions from `docs/razorback-implementation/plans/dab-full-batch-codex-explain-preflight.md` T3/T4 pass.

Command:

```text
$ mkdir -p _runs/validation/dab-batch-materialization-disk-budget/explain && \
  DATAAGENTBENCH_DATA_ROOT=/home/exedev/dataagentbench/data \
  uv run rk run /home/exedev/razorback/.worktrees/spacedock-ensign-dab-full-batch-codex-explain-preflight/_runs/dab-full-batch-codex-explain-preflight/specs/dab-full-batch-codex-spacedock.frozen.yaml \
    --runs-dir _runs/validation/dab-batch-materialization-disk-budget/explain/runs \
    --explain --explain-format json \
    > _runs/validation/dab-batch-materialization-disk-budget/explain/explain.json \
    2> _runs/validation/dab-batch-materialization-disk-budget/explain/explain.stderr.txt
exit_code 0
20661 _runs/validation/dab-batch-materialization-disk-budget/explain/explain.json
    0 _runs/validation/dab-batch-materialization-disk-budget/explain/explain.stderr.txt
```

T3 JSON assertions:

```text
$ uv run python - <<'PY'  # predecessor T3 assertions, pointed at validation explain.json
dataset_ref dab@1.0
task_count 12
solver_variant spacedock-workflow
agent spacedock_solver codex gpt-5.5
reasoning_effort xhigh
prompt_mode spacedock-codex-first-officer
PY
```

T4 no-Harbor/no-model assertions:

```text
$ uv run python - <<'PY'  # predecessor T4 assertions, pointed at validation explain.json
run_dir /home/exedev/razorback/.worktrees/spacedock-ensign-dab-batch-materialization-disk-budget/_runs/validation/dab-batch-materialization-disk-budget/explain/runs/dab-full-batch-codex-gpt55-xhigh-spacedock/cfc71ad8f27836df
no_job_config True
no_harbor_trials True
no_model_or_score_artifacts True
PY
```

Run-dir/task materialization contract check:

```text
$ uv run python - <<'PY'  # inspect explain run-dir tasks
task_dir_count 12
task_dirs DEPS_DEV_V1,GITHUB_REPOS,PANCANCER_ATLAS,PATENTS,agnews,bookreview,crmarenapro,googlelocal,music_brainz_20k,stockindex,stockmarket,yelp
required_paths_missing []
readonly_file_db_mounts 21
whole_query_dataset_main_mounts []
physical_db_copies_at_mount_targets []
PY
```

## AC-2 - PASS

**Verified by:** a focused test or measured probe proves generated task views stay under a declared budget while preserving readable SQLite/DuckDB access.

The focused materializer and compose tests pass, including no physical SQLite/DuckDB copies in bind mode, copy-mode preservation, read-only main mounts, no Postgres/Mongo dump mounts into `main`, and no hardlink use:

```text
$ uv run pytest packages/razorback-plugin-dab/tests/unit/test_prepare_bind_materialize.py -v
11 passed, 1 skipped in 0.35s

$ uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_bindmount_source.py -v
6 passed in 0.04s
```

Independent real-data materialization probe:

```text
$ DATAAGENTBENCH_DATA_ROOT=/home/exedev/dataagentbench/data uv run python - <<'PY'
data_root /home/exedev/dataagentbench/data
preflight_free_bytes 4021936128
focused_scratch _runs/validation/dab-batch-materialization-disk-budget/20260524T155820Z/focused
focused_datasets PATENTS,stockmarket,GITHUB_REPOS
focused_task_count 3
focused_readonly_file_db_mounts 5
focused_physical_delta_bytes 905216
focused_budget_bytes 134217728
full_scratch _runs/validation/dab-batch-materialization-disk-budget/20260524T155820Z/full
full_datasets agnews,bookreview,crmarenapro,DEPS_DEV_V1,GITHUB_REPOS,googlelocal,music_brainz_20k,PANCANCER_ATLAS,PATENTS,stockindex,stockmarket,yelp
full_task_count 12
full_readonly_file_db_mounts 21
full_physical_delta_bytes 3616768
full_budget_bytes 536870912
definition_ref dab@1.0
definition_dataset_count 12
PY
```

The probe asserted that every SQLite/DuckDB `db_path` source exists, is readable, is absent from the physical workdir, appears as `<source>:/workspace/<db_path>:ro`, and that no `main` mount targets `/workspace/query_dataset` as a whole directory.

## AC-3 - PASS

**Verified by:** a regression test writes or attempts to write through the materialized task path and proves the source data file is unchanged or mounted read-only.

```text
$ uv run pytest packages/razorback-plugin-dab/tests/integration/test_file_backed_db_readonly_mount.py -v -s
packages/razorback-plugin-dab/tests/integration/test_file_backed_db_readonly_mount.py::test_file_backed_db_main_mount_is_readable_and_read_only PASSED
1 passed, 2 warnings in 13.62s
```

The test uses Harbor `DockerEnvironment`, validates merged compose `read_only: true` for `/workspace/query_dataset/tiny.sqlite`, reads the SQLite header through the mounted task path, attempts `printf X >> /workspace/query_dataset/tiny.sqlite`, asserts non-zero exit, and rehashes the source file unchanged.

## AC-4 - PASS

**Verified by:** the preflight entity records green explain JSON evidence or a different blocker class with command/log path.

The resumed full DAB batch preflight command is the AC-1 command above. It exited 0 and produced fresh validation evidence at:

- JSON: `_runs/validation/dab-batch-materialization-disk-budget/explain/explain.json`
- stderr: `_runs/validation/dab-batch-materialization-disk-budget/explain/explain.stderr.txt`
- run dir: `_runs/validation/dab-batch-materialization-disk-budget/explain/runs/dab-full-batch-codex-gpt55-xhigh-spacedock/cfc71ad8f27836df`

No non-disk blocker was encountered.

## Code Review

`superpowers:requesting-code-review` is not exposed as a callable Codex skill/tool in this runtime. I read the installed skill workflow from `/home/exedev/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.7/skills/requesting-code-review/SKILL.md` and applied its `code-reviewer.md` template manually against:

```text
Base: f2a56b56b11163675bc36a57c8d0008176407a10
Head: 5d9fad72d32aa577449865003d58d996be05c75e

$ git diff --stat main..HEAD
7 files changed, 410 insertions(+), 31 deletions(-)

$ git diff --check main..HEAD
# no output
```

Review focus:

- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py`
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py`
- new and updated DAB unit/integration tests
- plan constraints: no whole `query_dataset` mount into `main`, no hardlinks, explain-only full DAB preflight, source DB write protection, generated task views under budget

Blocking findings: none.

Non-blocking findings: none.

External residual risk: full root `uv run pytest` remains blocked by the pre-existing `razorback.score.load` collection error described in Baseline. It is not introduced by this branch.

## Gate Decision

Approve to `done`.

AC-1 through AC-4 pass with independent command output. The branch stays scoped to per-file read-only SQLite/DuckDB `main.volumes` plus path-aware bind-mode exclusion, does not introduce hardlinks or whole `query_dataset` main mounts, protects source DBs from writes, keeps the full DAB command explain-only, and fits the declared ext4 disk budgets.
