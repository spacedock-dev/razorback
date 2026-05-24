# DAB Batch Materialization Disk Budget Implementation Plan

**Entity:** `docs/razorback-implementation/dab-batch-materialization-disk-budget.md`

**Goal:** Make the DAB full-batch `rk run --explain --explain-format json` path fit this VM's ext4 root filesystem without deleting run history, pruning Docker images, or launching the scored DAB run.

**Boundary:** This task changes DAB task materialization only. It may add focused unit/integration tests, run bounded materialization probes, and rerun the predecessor explain command. It must not run `rk run` without `--explain`, `rk score`, or `rk audit` for the full DAB launch.

**Spec cites:** v2 spec §6.1 (plugin-shipped DAB dataset definition, task-view materialization, `dataset: dab@1.0` identity), §6.2 (DAB `spacedock_solver` launch shape), §6.3 (`rk freeze` validation), §7.1 (run-dir `_razorback/task_views` layout), §8.1 (`rk run` pass-through/explain boundary), §8.2 (frozen provenance), §8.4 (spacedock runtime adaptation).

## AC to Task Map

| AC | Governing cites | Tasks | Evidence |
| --- | --- | --- | --- |
| AC-1 - Full DAB batch explain completes without filling `/dev/root`. | spec §6.1, §6.2, §6.3, §8.1 | T0, T5, T6 | `rk run --explain --explain-format json` for the existing full DAB Codex spec exits 0 and the predecessor plan's JSON assertions pass. |
| AC-2 - Materialization has a bounded disk footprint on non-reflink ext4. | spec §6.1, §7.1 | T0, T1, T2, T4, T5 | Synthetic and full-definition materialization probes show task views stay under the declared physical-disk budget while SQLite/DuckDB files remain readable at the container workdir paths. |
| AC-3 - Source data remains protected from agent writes. | spec §6.1, §7.1, §9.4 | T1, T3, T4 | Unit tests assert read-only main-service mounts for file-backed DBs; a docker-gated regression attempts a write through the mounted path and proves the source bytes/hash are unchanged. |
| AC-4 - The DAB explain preflight can resume and finish. | spec §8.1, §8.2 | T6, T7 | The predecessor preflight worktree records green explain JSON evidence, or a new blocker class with command/log path if the failure is no longer disk exhaustion. |

## Current Root Cause

The predecessor `dab-full-batch-codex-explain-preflight` task resolved `dab@1.0` to 12 datasets / 54 queries and froze the intended `spacedock_solver` Codex `gpt-5.5` / `xhigh` batch spec. Its explain attempt failed before JSON emission because `/dev/root` filled during DAB task-view materialization.

The disk pressure is in the DAB plugin's bind-mode workdir materializer, not in Harbor/model execution:

- `prepare_dataset_tasks(query_mode="batch")` emits one task per DAB dataset and calls `_materialize_batch_task_dir`.
- Bind mode excludes Postgres SQL dumps and Mongo dump folders via `_dump_basenames(db_config)`.
- SQLite/DuckDB `db_path` files are intentionally not excluded today, so `_clone_or_copy_tree()` materializes them into each task workdir.
- On Linux `_clone_or_copy_tree()` runs `cp --reflink=auto`. On this ext4 `/dev/root`, that command can return success while falling back to a full physical copy.
- This VM currently has about 3.7 GiB free under `/home/exedev`, while the DAB source tree has about 7.9 GiB of data. The largest file-backed DB payloads alone include PATENTS SQLite (~5.17 GiB), stockmarket DuckDB (~920 MiB), GITHUB_REPOS SQLite+DuckDB (~885 MiB), DEPS_DEV_V1 SQLite+DuckDB (~524 MiB), and PANCANCER_ATLAS DuckDB (~280 MiB). A full-copy fallback for the 12 batch task views cannot fit the current ext4 budget.

The plan-time spike below proves Harbor 0.6.6 preserves read-only `main.volumes` from a DAB-generated task compose file through Harbor's DockerEnvironment compose merge. The implementation should therefore start from **read-only file bind mounts for SQLite/DuckDB files in the `main` service**, with those files omitted from the physical task workdir. This preserves the existing in-container paths (`/workspace/...`), avoids hardlinks, avoids symlinks that escape the mounted task root, and lets Docker enforce `:ro` for agent write attempts.

## Plan-Time Spike Evidence

**Purpose:** Answer the rejected plan-gate question before implementation: does the smallest real DAB/Harbor path preserve a read-only `main.volumes` file mount and make it readable but write-protected at the intended workdir path?

**Command run from repo root:** `uv run python - <<'PY' ... PY`

The bounded script created `/tmp/rb-dab-main-volumes-spike/data/query_bookreview` with a synthetic `db_config.yaml` containing `db_type: sqlite` and `db_path: query_dataset/tiny.sqlite`, then called:

```python
prepare_dataset_tasks(
    data_root=Path("/tmp/rb-dab-main-volumes-spike/data"),
    dataset="bookreview",
    tasks_root=Path("/tmp/rb-dab-main-volumes-spike/tasks"),
    docker_image="python:3.12",
    container_workdir="/workspace",
    materialize_mode="bind",
    query_mode="batch",
)
```

After generation, the script injected the proposed candidate mount into the generated file `/tmp/rb-dab-main-volumes-spike/tasks/bookreview/environment/docker-compose.yaml`:

```yaml
services:
  main:
    volumes:
    - /tmp/rb-dab-main-volumes-spike/data/query_bookreview/query_dataset/tiny.sqlite:/workspace/query_dataset/tiny.sqlite:ro
```

It then instantiated Harbor's real Docker path:

```python
DockerEnvironment(
    environment_dir=task_dir / "environment",
    environment_name="rb-dab-main-volumes-spike",
    session_id="rb-dab-main-volumes-spike",
    trial_paths=TrialPaths(trial_dir=Path("/tmp/rb-dab-main-volumes-spike/trial")),
    task_env_config=EnvironmentConfig(
        docker_image="python:3.12",
        workdir="/workspace",
        allow_internet=True,
    ),
)
```

and ran `start(force_build=False)`, Harbor's merged `docker compose config --format json`, `test -r /workspace/query_dataset/tiny.sqlite && head -c 16 ...`, `printf X >> /workspace/query_dataset/tiny.sqlite`, and `mount | grep tiny.sqlite`.

**Result:** pass. Harbor's merged main service volumes included Harbor's three log/artifact binds plus the task-authored DB bind:

```json
{
  "type": "bind",
  "source": "/tmp/rb-dab-main-volumes-spike/data/query_bookreview/query_dataset/tiny.sqlite",
  "target": "/workspace/query_dataset/tiny.sqlite",
  "read_only": true
}
```

The read probe exited `0` and returned the SQLite header bytes `53 51 4c 69 74 65 20 66 6f 72 6d 61 74 20 33 00`. The write probe exited `1` with `Read-only file system`. The source SHA256 stayed `56c5c0984ef99e386244c2cadb8d311e5c66d7176b816d9fc1c2db23e1359f18` before and after the attempted write. `mount | grep tiny.sqlite` showed `/workspace/query_dataset/tiny.sqlite type ext4 (ro,relatime)`.

**Files inspected:** `/tmp/rb-dab-main-volumes-spike/tasks/bookreview/environment/docker-compose.yaml`, Harbor's merged `docker compose config --format json` output, and `/tmp/rb-dab-main-volumes-spike/data/query_bookreview/query_dataset/tiny.sqlite`.

**Design consequence:** `main.volumes` is not dropped. Do not use the fallback symlink/source-root design for this task unless implementation discovers a narrower DAB-specific regression that this spike did not cover.

## Surface Map

| Path | Action |
| --- | --- |
| `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py` | Add path-aware classification for SQLite/DuckDB `db_path` files; omit those files from bind-mode physical copies while keeping parent directories and small safe files. |
| `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py` | Add read-only `main` service bind mounts from `DATAAGENTBENCH_DATA_ROOT/query_<dataset>/<db_path>` to `<container_workdir>/<db_path>` for SQLite/DuckDB clients only. Do not mount Postgres/Mongo dumps into `main`. |
| `packages/razorback-plugin-dab/tests/unit/test_prepare_bind_materialize.py` | Extend materialization tests for no physical SQLite/DuckDB copy, bounded disk delta, readable placeholder/path shape, and copy-mode regression. |
| `packages/razorback-plugin-dab/tests/unit/test_compose_bindmount_source.py` or a new adjacent unit file | Assert `main.volumes` entries are absolute, target the existing workdir-relative DB paths, carry `:ro`, and exclude Postgres/Mongo dump sources from `main`. |
| `packages/razorback-plugin-dab/tests/integration/test_file_backed_db_readonly_mount.py` | Docker-gated write-attempt regression for source-data protection. Skip cleanly when Docker or the selected local image is unavailable. |
| `src/razorback/translate.py` | Read-only inspection first. Touch only if the DAB translator fails to preserve the generated compose/task shape through `TaskConfig(path=...)`. |
| `docs/razorback-implementation/dab-full-batch-codex-explain-preflight.md` | The implementation worker may update that predecessor entity only when rerunning its assigned preflight stage or when instructed by FO; this plan-stage worker does not change it. |

## Tasks

### T0 - Establish the Budget Guard and Failure Shape

**ACs:** AC-1, AC-2

**Goal:** Add a cheap, non-destructive measurement harness before changing behavior, so implementation never proves the fix by consuming the remaining root filesystem.

1. Add a helper test/probe that computes the declared file-backed DB payload total from DAB `db_config.yaml` files without copying data.
2. Add a targeted synthetic fixture with one large SQLite file and one DuckDB file under `query_dataset/`.
3. Record the implementation budget as: full DAB batch task-view materialization must consume **less than 512 MiB of additional physical free space** on this VM, excluding the already-present `DATAAGENTBENCH_DATA_ROOT` and Docker state.
4. Guard live/full-definition probes with a preflight free-space check. If `/home/exedev` has less than 2 GiB free, fail with a typed `disk-budget-precheck` blocker instead of materializing.

Expected red signal before the fix: bind mode either copies the synthetic file-backed DB into the task workdir or the measured full-definition projection exceeds the 512 MiB budget.

### T1 - RED: Read-Only Main-Service Mount Shape for SQLite/DuckDB

**ACs:** AC-2, AC-3

**Goal:** Codify the proven spike mechanism before implementation: file-backed DBs are mounted into `main` read-only at the same paths agents already use.

Add unit tests that generate a mixed `db_config.yaml` fixture with SQLite, DuckDB, Postgres, and Mongo clients and assert:

- `main.volumes` contains one `:ro` bind mount per SQLite/DuckDB `db_path`.
- Each source is an absolute path under the dataset's `query_<dataset>/...` directory.
- Each target is `<container_workdir>/<db_path>`, preserving existing prompt and verifier expectations.
- Postgres SQL dumps and Mongo dump folders remain mounted only into their sidecar services, not into `main`.
- The generated task's `query_dataset` directory exists so the later Harbor/container mount has parent directories for file targets.

Run:

```bash
uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_bindmount_source.py -v
```

Expected: fails because `main` currently has no SQLite/DuckDB read-only volumes.

### T2 - GREEN: Omit File-Backed DB Copies in Bind Mode

**ACs:** AC-2

**Goal:** Stop `cp --reflink=auto` from deciding the disk budget for SQLite/DuckDB live DB files.

Implement path-aware file-backed DB exclusion in `prepare.py`:

- Derive relative `db_path` entries for `db_type in {"sqlite", "duckdb"}`.
- In `materialize_mode="bind"`, skip those relative paths during `_clone_or_copy_tree()` while preserving parent directories and non-DB safe files.
- Keep `materialize_mode="copy"` unchanged: copy mode still physically copies SQLite/DuckDB and dump files for provenance-strict runs.
- Avoid basename-only exclusion if a fixture exposes two files with the same basename in different directories.

Run:

```bash
uv run pytest packages/razorback-plugin-dab/tests/unit/test_prepare_bind_materialize.py -v
```

Acceptance: the synthetic large SQLite/DuckDB fixture consumes only scaffolding-sized disk, the workdir does not contain physical DB copies in bind mode, and copy mode still produces distinct inodes/full copies.

### T3 - RED/GREEN: Harbor Source Write Protection Regression

**ACs:** AC-3

**Goal:** Prove the space-saving mechanism does not trade disk safety for source-data mutability.

Add a docker-gated integration test based on the plan-time spike: use a small synthetic SQLite or DuckDB file, materialize a task in bind mode, then run Harbor's DockerEnvironment or an equivalent Harbor compose stack through the generated main-service mount shape and attempt:

```bash
printf X >> /workspace/query_dataset/<db-file>
```

The test must assert one of:

- the command fails with a read-only filesystem/permission error, or
- the source file's SHA256 is unchanged after the attempted write.

Also assert a read path succeeds, for example `test -r /workspace/query_dataset/<db-file>` or reading a known header, and inspect the merged compose config for `read_only: true` on the DB target. If Docker or the selected local image is unavailable, the test skips with a message that names AC-3.

Run:

```bash
uv run pytest packages/razorback-plugin-dab/tests/integration/test_file_backed_db_readonly_mount.py -v -s
```

### T4 - Focused Real-Data Materialization Probe

**ACs:** AC-2, AC-3

**Goal:** Exercise the largest real datasets without running Harbor or the model.

Using `/home/exedev/dataagentbench/data` or the exported `DATAAGENTBENCH_DATA_ROOT`, call the DAB plugin materializer directly into a scratch path owned by this task, starting with the riskiest datasets:

1. `PATENTS` (largest SQLite, ~5.17 GiB source file).
2. `stockmarket` (large DuckDB, ~920 MiB).
3. `GITHUB_REPOS` (large SQLite+DuckDB pair, ~885 MiB total).

Measure filesystem free-space before/after with `os.statvfs`, not `du`, because apparent size is not the budget that filled `/dev/root`. Assert the physical delta stays under 128 MiB for these three datasets combined. Inspect generated compose for `:ro` `main` file mounts and no Postgres/Mongo dumps in `main`.

If this probe exceeds budget, stop and classify `file-backed-main-mount-budget` before trying the full 12-dataset explain path.

### T5 - Full DAB Batch Materialization Probe

**ACs:** AC-1, AC-2

**Goal:** Validate the exact materialization scale that blocked the predecessor explain command, still without Harbor/model execution.

Run a bounded plugin-level or `rk run --explain` dry materialization over `dataset: dab@1.0`, `query_mode: batch`, and all 12 datasets. Use the same scratch root convention as T4 and the same free-space measurement. Assert:

- 12 task dirs are produced.
- The task list matches the DAB definition datasets.
- Physical disk delta is under the declared 512 MiB budget.
- Every SQLite/DuckDB `db_path` appears as a read-only `main` mount.
- No scored run artifacts are produced.

This task is the comprehensive mechanism gate. Do not proceed to the predecessor explain rerun until it passes.

### T6 - Resume the Exact Explain Preflight

**ACs:** AC-1, AC-4

**Goal:** Return to the original blocked command after the smallest mechanism and full materialization probes pass.

From the predecessor worktree or its approved current branch, rerun the exact explain command from `docs/razorback-implementation/plans/dab-full-batch-codex-explain-preflight.md`:

```bash
DATAAGENTBENCH_DATA_ROOT=/home/exedev/dataagentbench/data \
  uv run rk run _runs/dab-full-batch-codex-explain-preflight/specs/dab-full-batch-codex-spacedock.frozen.yaml \
    --runs-dir _runs/dab-full-batch-codex-explain-preflight/runs \
    --explain --explain-format json
```

Adjust only paths needed to match the predecessor worktree's actual frozen spec and run root. Preserve its JSON assertions from T3/T4:

- `schema_version == "rk-run-explain-v1"`.
- `explain_only is true`.
- `benchmark.dataset == "dab@1.0"`.
- `query_mode == "batch"`.
- `prompt.task_count == 12`.
- `agent.runtime == "codex"`.
- `agent.model == "gpt-5.5"`.
- `harbor_agent_kwargs.reasoning_effort == "xhigh"`.
- no `_job_config.yaml`, `trials/`, `result.json`, `summary.json`, `score.json`, or `audit.json`.

If the command fails with a non-disk error, record the new blocker class, command, stdout/stderr path, and remaining free space. Do not retry with a full scored run.

### T7 - Regression Sweep and Report

**ACs:** AC-1, AC-2, AC-3, AC-4

**Goal:** Package the implementation evidence cleanly for validation.

Run the focused suites first, then the adjacent plugin suite:

```bash
uv run pytest packages/razorback-plugin-dab/tests/unit/test_prepare_bind_materialize.py -v
uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_bindmount_source.py -v
uv run pytest packages/razorback-plugin-dab/tests/integration/test_file_backed_db_readonly_mount.py -v -s
uv run pytest packages/razorback-plugin-dab/tests/unit/ -q
```

Write the implementation stage report with:

- the physical disk budget and measured deltas for T4/T5;
- the exact explain command and JSON artifact path for T6;
- whether the docker-gated source-write test passed or skipped, with rationale;
- any blocker class if T6 fails for a non-disk reason.

## Prohibited Actions

- Do not delete prior run history or historical `_runs/`, `runs/`, or workflow evidence directories to make the explain pass.
- Do not prune Docker images, containers, volumes, or build cache.
- Do not launch the full scored DAB run. In this task, every `rk run` command must include `--explain`.
- Do not replace `cp --reflink=auto` with hardlinks. Hardlinks are source-mutation unsafe on ext4.
- Do not mount the whole `query_dataset` directory into `main`; that would re-expose Postgres/Mongo dump files that bind mode intentionally keeps out of the agent workspace.

## Fallback Boundary

The previously open Harbor compose-preservation decision is resolved by the plan-time spike: per-file read-only `main` bind mounts are the implementation mechanism. If implementation later finds a narrower failure, stop with a typed blocker and only then evaluate the fallback design: mount a read-only source-data root at a stable container path and replace workdir DB files with container-visible symlinks. That fallback must get its own write-protection test before any full DAB explain rerun.
