# FU-2 — ade-bench `docker_image` Override (real LLM-scored result) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Per CL's "Validating new mechanisms" rule, the riskiest contract for FU-2 is **AC-3** (a real laude-institute ade-bench task pulled, rewritten, and actually scored by a live claude call). AC-3 is the LAST task — all unit tests must lock the materialization-rewrite shape before we spend a real claude call. The first task is **AC-1**: a fixture git-shaped ade-bench task whose source `task.toml` declares a non-overlapping `docker_image` must, after razorback's adapter runs, be materialized with `docker_image = "dab-agent:latest"` while the original source-of-truth `task.toml` at the git ref is untouched.

**Goal.** Close the FU-1 second-order finding: real laude-institute ade-bench tasks (e.g., `ade-bench-airbnb001`) ship task-specific `environment/Dockerfile`s — `python:3.11-slim` + dbt-duckdb for airbnb001 — that do NOT bake `claude` on PATH. FU-1's AC-5 trial errored with `ClaudeCliAgentError("claude CLI not available inside the container (exit=127)")` at `setup()`, before any LLM round-trip could fire. The FU-1 validator approved on the literal `Verified by:` clauses (exit 0, numeric `jq .score`, grep-clean) but flagged the spirit gap as the FU-2 surface (`docs/razorback-implementation/validation/fu1-claude-auth-leak-ade-bench-real-task.md` §AC-5 scope-note; FU-1 archived stage report's impl-stage follow-up note). FU-2 closes this by **patching the fetched `task.toml`'s `docker_image` field to `dab-agent:latest` (or a configurable override) AFTER fetch but BEFORE harbor's environment build reads it**. The headline deliverable is **AC-3**: `uv run rk run examples/specs/ade-bench-claude.yaml` exits 0 against a real harbor-datasets ade-bench task and writes a `summary.json` whose `score` reflects an actual claude invocation (evidence: `messages.jsonl` or equivalent in the trial's `agent/` subdir; `n_errored_trials=0` from `claude --version` exit 127).

**Architecture.** Three small surfaces, in order of risk-locked-by-unit-test then live-acceptance:

1. **`razorback.benchmarks.ade_bench.tasks`** — introduce a `materialize_git_task(*, git_url, git_commit_id, source_path, docker_image) -> Path` function. The function (a) computes the harbor-cache-equivalent target dir under a razorback-owned override cache root (NOT harbor's `~/.cache/harbor/tasks` — keep our materialization separate so harbor's later git fetch into its own cache does not clobber our rewrite); (b) uses `harbor.tasks.client.TaskClient.download_tasks(task_ids=[GitTaskId(...)], output_dir=<our cache>)` to fetch into our cache; (c) rewrites the materialized `task.toml` by adding/updating the `[environment].docker_image` line to `dab-agent:latest` (or the configured override); (d) returns the absolute path to the materialized task dir. The git fetch is harbor's existing machinery — razorback does not write new clone logic. Only the post-fetch rewrite is new.

2. **`razorback.compat.harbor_0_6_6._build_ade_bench`** — for any `ResolvedTask` carrying `git_url` + `git_commit_id`, call `materialize_git_task(...)` to obtain a local absolute path, then emit a **local** `TaskConfig(path=<materialized_abs_path>)` (NOT a git `TaskConfig` with `git_url`/`git_commit_id`). This is the M2 analog: M2's `_build_dab` hands harbor `TaskConfig(path=...)` against razorback-owned materialized task dirs. The FU-1 git-task entry shape (`{path, git_url, git_commit_id}` in the spec) is preserved; the translator decides whether to pass through (legacy slug) or rewrite-and-localize (git entry).

3. **`razorback.spec.schema.AdeBenchBenchmarkBlock`** — add an optional `docker_image_override: str | None = None` field with `extra="forbid"` preserved. Default behavior (`None`): use `"dab-agent:latest"`. Explicit value: use the configured string. The translator threads this through to `materialize_git_task(docker_image=...)`.

**Tech stack:** Python 3.12, `uv`, Pydantic 2.11, harbor 0.6.6 (pinned, unchanged), pytest 8 with `pytest-asyncio` 0.24, Docker via Colima. No new external dependencies. `tomllib` (stdlib) for reading; we write the rewrite as a string replacement / append (TOML round-trip is not needed — see Task 1 step 2 for the rewrite shape).

**Source of truth.** The 6 ACs live in the FU-2 entity at `docs/razorback-implementation/fu2-ade-bench-image-override.md`. Harbor's `TaskConfig` git-task shape comes from `.venv/lib/python3.12/site-packages/harbor/models/trial/config.py:128-185`. Harbor's `GitTaskId.get_local_path()` and `TaskClient.download_tasks` come from `.venv/lib/python3.12/site-packages/harbor/models/task/id.py:9-20` and `.venv/lib/python3.12/site-packages/harbor/tasks/client.py:459-553`. Harbor's `[environment].docker_image` field at `.venv/lib/python3.12/site-packages/harbor/models/task/config.py:127-129` (`docker_image: str | None = None`).

**FU-1 inputs (do not duplicate):**

- **From FU-1** (`src/razorback/benchmarks/ade_bench/tasks.py:23-55`): `resolve_task_dirs(tasks_root, tasks)` returns `list[ResolvedTask]` records where each `ResolvedTask` has `path: Path` and optional `git_url`, `git_commit_id`. Legacy slug entries set only `path`; git entries set all three. FU-2 extends this surface: a new helper `materialize_git_task(...)` runs on the git-shaped records and produces a local `Path` whose `task.toml` has `docker_image` rewritten. The legacy slug path is unchanged.
- **From FU-1** (`src/razorback/compat/harbor_0_6_6.py:170-195`): `_build_ade_bench` calls `resolve_task_dirs` and emits `TaskConfig(path=r.path, git_url=r.git_url, git_commit_id=r.git_commit_id)` per record. FU-2 changes only the git-entry branch: for git records, run `materialize_git_task(...)` to obtain a local materialized dir, then emit `TaskConfig(path=<local_abs_path>)` with NO `git_url` / `git_commit_id`. Harbor receives a local-task entry and skips its own git fetch (its `TaskClient.download_tasks` filters by `is_git_task()` per `harbor/job.py:520-553`).
- **From FU-1** (`src/razorback/spec/schema.py:87-104`): `AdeBenchTaskEntry` is `{path: str, git_url: str, git_commit_id: str}` with `extra="forbid"`; `AdeBenchBenchmarkBlock` has `tasks: list[str | AdeBenchTaskEntry]`. FU-2 adds one new optional field to `AdeBenchBenchmarkBlock`: `docker_image_override: str | None = None`. `extra="forbid"` is preserved (the unit test in AC-2 asserts this).
- **From FU-1** (`tests/integration/test_no_auth_leak_in_run_dir.py`): the auth-leak grep gate stays as-is and is the AC-5 carry-forward verification. No changes to this test or to `scripts/grep-run-dir-for-secrets.sh`.
- **From FU-1** (`examples/specs/ade-bench-claude.yaml`): the spec already points at `ade-bench-airbnb001` at git commit `b4e82debfdd2aba9d91c41cd96a997dd549fcbb3`. FU-2 does not change the spec shape; the AC-3 live run uses this exact spec.

**M2 inputs (the prepare.py pattern):**

- **`src/razorback/benchmarks/dab/prepare.py:32` (`_DEFAULT_DOCKER_IMAGE = "dab-agent:latest"`)** — the literal image-name constant. FU-2 reuses this exact string as the default override target. Import it from `razorback.benchmarks.dab.prepare` to keep a single source of truth (so a future image rename touches one constant).
- **`src/razorback/benchmarks/dab/prepare.py:152-167`** — M2's full materialization writes the `task.toml` from scratch:
  ```python
  (task_dir / "task.toml").write_text(
      _task_toml(
          task_name=task_name,
          task_env=task_env,
          docker_image=docker_image,
          container_workdir=container_workdir,
      )
  )
  ```
  M2 builds `task.toml` ground-up because it materializes DAB queries into harbor-task shape from a non-harbor source. FU-2 is different: the source IS already a harbor task — we don't rebuild it, we **rewrite one field**. The smallest correct change is a targeted in-place modification of the materialized file, not a full regeneration. The rewrite must preserve every other field (TOML tables for `[metadata]`, `[verifier]`, `[agent]`, `[verifier.env]`, `[solution.env]`, the existing `[environment]` block with `build_timeout_sec`, `cpus`, `memory_mb`, etc.).
- **M2's `_placeholder_dockerfile()`** — M2 writes a placeholder `Dockerfile` even when `docker_image` is set, because harbor's task validator expects an `environment/` dir. The real ade-bench task already has an `environment/Dockerfile` (with the full python:3.11-slim + dbt-duckdb image build); FU-2 leaves that Dockerfile in place — harbor's `apple_container.py:137` `self._use_prebuilt = not force_build and bool(self.task_env_config.docker_image)` says when `docker_image` is set, the Dockerfile is NOT built. Confirmed at `.venv/lib/python3.12/site-packages/harbor/environments/apple_container.py:137-160`.

**Authoritative external reference — the real ade-bench task.toml shape:**

`ade-bench-airbnb001` at `git_commit_id: b4e82debfdd2aba9d91c41cd96a997dd549fcbb3`, materialized at `~/.cache/harbor/tasks/Ypzg75nmyQ3x3zH7fJNNic/ade-bench-airbnb001/task.toml` (from FU-1's live AC-5 run). The full file:

```toml
# Harbor Task Configuration for ADE-bench
# Refer to https://harborframework.com/docs/task-format for more details.

version = "1.0"

[metadata]
author_name = "test"
author_email = "test"
difficulty = "easy"
category = "data-engineering"
tags = ["data-inspection", "dbt", "dbt-macros", ...]
[verifier]
timeout_sec = 300.0

[agent]
timeout_sec = 600.0

[environment]
build_timeout_sec = 900.0
cpus = 1
memory_mb = 4096
storage_mb = 10240

[verifier.env]
DB_TYPE = "duckdb"
PROJECT_TYPE = "dbt"

[solution.env]
DB_TYPE = "duckdb"
PROJECT_TYPE = "dbt"
```

Three load-bearing observations:

1. **No `docker_image` line exists.** The real task uses harbor's Dockerfile-build path (`environment/Dockerfile`). The rewrite must **insert** `docker_image = "dab-agent:latest"` into the `[environment]` block — append, not replace. The unit test fixture in Task 1 deliberately uses a `docker_image = "some-other-image:tag"` line to also exercise the **replace** path; both paths must be supported.

2. **`version = "1.0"` (top-level), not `schema_version = "1.2"`** as DAB writes. Harbor's `handle_version_rename` validator at `harbor/models/task/config.py:325-327` renames `version` → `schema_version` on parse. The rewrite is agnostic to which name the source uses — we only touch the `[environment]` block.

3. **No collision with dab-agent's defaults.** The real task's `[environment]` block sets `build_timeout_sec`, `cpus`, `memory_mb`, `storage_mb`. These are all generic harbor fields, NOT image-specific. `dab-agent:latest` (built on the exeuntu base per M2's docs) ships claude, codex, uv, jq, git, dbt, duckdb, dbt-duckdb. Cross-reference: airbnb001's Dockerfile installs `tmux asciinema curl nodejs yq dbt-core==1.10.11 dbt-duckdb==1.9.3 duckdb==1.3.0 gdown pyyaml uv`. Of these, `dbt`, `dbt-duckdb`, `duckdb`, `uv` are in dab-agent. **Potentially missing in dab-agent**: `tmux`, `asciinema`, `nodejs`, `yq`, `gdown`, `pyyaml`. The first four are convenience tooling; `gdown` (Google Drive downloader) is used in airbnb001's Dockerfile `RUN` step to fetch the DuckDB DB file from Google Drive — but that RUN step does NOT execute when `docker_image` is set (harbor skips the Dockerfile). The task's `setup.sh` (run by the Dockerfile's `RUN` step too) is what bakes the dbt project state. If `setup.sh` is skipped, the in-container `/app/<db>.duckdb` is missing and the agent will fail to find the database. **This is the AC-4 graceful-error surface.** The plan documents this risk explicitly in Task 5 and proposes either: (a) running setup.sh at task time inside the container via task.toml's pre-agent hook (if harbor supports one); OR (b) baking a richer `ade-bench-agent:latest` image that pre-runs setup.sh per task (out of scope per FU-2's "Out of scope" list — that's a separate FU-N); OR (c) discovering this at AC-3 live-run time and reporting it as an AC-4 typed error. AC-4 ships option (c); the richer image is the obvious next follow-up.

**Acceptance task choice (AC-3):**

FU-1's AC-5 already targeted `ade-bench-airbnb001` at the registry-pinned commit. FU-2 inherits this target so the AC-3 live run is directly comparable to FU-1's AC-5 (delta = one variable: image override applied vs. not). The spec at `examples/specs/ade-bench-claude.yaml` is unchanged; only the adapter behavior changes. If `airbnb001` requires `gdown` or `setup.sh`-baked state that dab-agent lacks, AC-4's graceful-error path documents this — see Task 5.

**Riskiest contract first (per checklist item #1):**

The FU-2 dispatch's checklist item #1 says: "Plan steps map 1:1 to the 6 ACs in the FU-2 entity body. The riskiest contract (AC-3 live LLM-scored run on a real ade-bench task) is the LAST task — because all the earlier unit tests must lock the materialization-rewrite shape before we spend a real claude call. The first task is AC-1: docker_image rewrite at materialization, with a fixture git-shaped task that has a non-overlapping image name."

This INVERTS FU-1's "riskiest test first" ordering for one specific reason: FU-1's risk was a defect-in-main (the leak existed; we needed proof of failure before fix). FU-2's risk is a cost-bearing live integration (the LLM call costs real money; we need confidence in the contract before we exercise it). Per CL's "Validating new mechanisms" rule's nuance — "If a comprehensive run takes hours, the mechanism check should cost minutes" — the unit-test materialization-rewrite shape IS the mechanism check; AC-3 is the comprehensive run.

Therefore:

- **Task 1** locks AC-1's rewrite contract with a unit test using a fixture git-shaped task whose source `task.toml` has `docker_image = "some-other-image:tag"` (exercises the REPLACE path).
- **Task 2** adds AC-1's INSERT-path test: a fixture task whose source `task.toml` has NO `docker_image` line (exercises the airbnb001-shaped real-world case).
- **Task 3** locks AC-2's schema-override contract with unit tests over `AdeBenchBenchmarkBlock`.
- **Task 4** locks AC-1's source-untouched contract: the original `task.toml` at the git ref (or at the source path supplied to `materialize_git_task`) is bytewise unchanged after materialization; only the materialized copy carries the rewrite.
- **Task 5** locks AC-4's graceful-error contract with a unit test that patches `dab-agent` to a minimal image and asserts the typed error names the missing binary.
- **Task 6** is AC-3's live run — the smallest end-to-end exercise of the riskiest path, deferred to the end so the contract is fully locked first.
- **Task 7** is AC-5 + AC-6: re-run FU-1's auth-leak gate against the new run-dir and confirm the full pytest suite still passes.

**AC ↔ task map (1:1):**

| AC | Governing reference | Task(s) |
|----|---------------------|---------|
| AC-1 — Adapter rewrites `docker_image` in the materialized `task.toml` to `dab-agent:latest` (or override) after fetch, before harbor reads it. Original source-of-truth `task.toml` at the git ref untouched. | M2's `prepare.py:32, 152-167` (the docker_image-bake pattern); harbor's `TaskConfig` git-task shape (`harbor/models/trial/config.py:128-185`); harbor's `_copy_task_source_to_target` (`harbor/tasks/client.py:137-141`); harbor's `[environment].docker_image` field (`harbor/models/task/config.py:127-129`). | Task 1 (REPLACE path: source has different `docker_image`), Task 2 (INSERT path: source has no `docker_image`, matches airbnb001), Task 4 (source-untouched assertion) |
| AC-2 — Override target is configurable via `AdeBenchBenchmarkBlock.docker_image_override`. Default `dab-agent:latest`. Schema's `extra="forbid"` preserved. | M2's `_DEFAULT_DOCKER_IMAGE` constant (`prepare.py:32`); FU-1's `AdeBenchBenchmarkBlock` schema (`spec/schema.py:100-104`). | Task 3 (schema field + default + extra=forbid + translator wiring) |
| AC-3 — Live `rk run` against a real ade-bench task with the default image override produces a non-zero LLM-scored result; trial reaches `agent.run()` (no `ClaudeCliAgentError` from `claude --version`); evidence of LLM round-trip in trial's `agent/`. | FU-1 archived validation `_archive/validation/...` §AC-5 scope-note (the spirit gap this entity closes); harbor's container env path (claude-cli is on PATH in dab-agent:latest). | Task 6 (live `rk run` against `examples/specs/ade-bench-claude.yaml`; jq summary.json; inspect trial agent/) |
| AC-4 — If the real task requires tools missing from `dab-agent:latest`, the adapter surfaces a typed error naming the missing binary — not a cryptic exit-127 or silent trial failure. | airbnb001's Dockerfile `RUN` steps (gdown for DB fetch, setup.sh for dbt project state); FU-1's `ClaudeCliAgentError("claude CLI not available... exit=127")` shape. | Task 5 (unit test patches `dab-agent` to a minimal image; asserts typed error names missing tool) |
| AC-5 — FU-1's grep-clean guarantee still holds; live AC-3 run-dir is grep-clean of the literal OAuth token. | FU-1 AC-1 test `tests/integration/test_no_auth_leak_in_run_dir.py`; `scripts/grep-run-dir-for-secrets.sh`. | Task 7 (re-run gate against AC-3 run-dir) |
| AC-6 — `uv run pytest` exits 0 from a clean checkout of the FU-2 worktree branch tip; the prior ~251 tests still pass alongside the new FU-2 tests. | M1–M7 + FU-1 carry-forward. | Task 7 (full-suite green) |

**Test-first ordering:**

Tasks 1, 2, 3, 4, 5 are TDD: failing test first, smallest implementation that makes it pass, then refactor. Task 6 is the live acceptance (cost-bearing, executed once after unit tests pass). Task 7 is the green-suite + grep-gate carry-forward. Tasks 1–5 must all be green before Task 6 fires.

---

## Task 1 — AC-1 REPLACE path: rewrite an existing `docker_image` line at materialization

**Goal.** Land the smallest TDD-shaped exercise of the materialization-rewrite contract: a unit test with a fixture git-shaped task whose source `task.toml` declares `docker_image = "some-other-image:tag"`. After razorback's `materialize_git_task(...)` runs, the post-fetch `task.toml` in the materialized location carries `docker_image = "dab-agent:latest"`; the source-of-truth `task.toml` is untouched (asserted by Task 4 — Task 1 checks the materialized copy only). This task locks the REPLACE branch of the rewrite logic.

**Files:**
- `tests/unit/test_ade_bench_materialize_git_task.py` (NEW)
- `tests/fixtures/ade_bench/fixture_git_task_with_image/task.toml` (NEW; the SOURCE side of the materialization)
- `tests/fixtures/ade_bench/fixture_git_task_with_image/environment/Dockerfile` (NEW; placeholder so the harbor task shape is satisfied)
- `src/razorback/benchmarks/ade_bench/tasks.py` (extend: add `materialize_git_task` + `rewrite_docker_image` helpers)

**Steps:**

- [ ] **Step 1: Author the SOURCE fixture.** Create `tests/fixtures/ade_bench/fixture_git_task_with_image/task.toml` carrying:
  ```toml
  version = "1.0"

  [metadata]
  author_name = "fu2-fixture"

  [environment]
  build_timeout_sec = 900.0
  cpus = 1
  memory_mb = 4096
  storage_mb = 10240
  docker_image = "some-other-image:tag"
  ```
  Also create `tests/fixtures/ade_bench/fixture_git_task_with_image/environment/Dockerfile` (one-line placeholder: `FROM alpine:3.19\n`). This shape mirrors a real ade-bench task that already had a `docker_image` set; the rewrite must REPLACE not INSERT.

- [ ] **Step 2: Author the failing test.** Create `tests/unit/test_ade_bench_materialize_git_task.py::test_rewrite_replaces_existing_docker_image`. The test:
  ```python
  def test_rewrite_replaces_existing_docker_image(tmp_path: Path) -> None:
      from razorback.benchmarks.ade_bench.tasks import materialize_git_task
      source = Path("tests/fixtures/ade_bench/fixture_git_task_with_image").resolve()
      # Use a fake git_url/commit; the FAKE_GIT_SOURCE override path (Step 4)
      # bypasses harbor's TaskClient and copytree's the source dir to the
      # materialized target.
      target_root = tmp_path / "fu2-cache"
      materialized = materialize_git_task(
          git_url="file://" + str(source),
          git_commit_id="deadbeef" * 5,
          source_path=Path("fixture_git_task_with_image"),
          docker_image="dab-agent:latest",
          cache_root=target_root,
          _fake_git_source=source,  # test-only kwarg; see Step 4 design note
      )
      task_toml = (materialized / "task.toml").read_text()
      assert 'docker_image = "dab-agent:latest"' in task_toml
      assert 'docker_image = "some-other-image:tag"' not in task_toml
      # Original source file UNTOUCHED (full AC-1 source-untouched assert is Task 4).
      original = (source / "task.toml").read_text()
      assert 'docker_image = "some-other-image:tag"' in original
  ```
  Expected: this test FAILS on `main` because `materialize_git_task` does not exist yet.

- [ ] **Step 3: Run the test.** `uv run pytest tests/unit/test_ade_bench_materialize_git_task.py -v`. Expected: `ImportError` or `AttributeError` for `materialize_git_task`. Confirms the test is wired and reaches the unimplemented surface.

- [ ] **Step 4: Implement `materialize_git_task`.** In `src/razorback/benchmarks/ade_bench/tasks.py`, add:
  ```python
  from razorback.benchmarks.dab.prepare import _DEFAULT_DOCKER_IMAGE

  def materialize_git_task(
      *,
      git_url: str,
      git_commit_id: str,
      source_path: Path,
      docker_image: str = _DEFAULT_DOCKER_IMAGE,
      cache_root: Path,
      _fake_git_source: Path | None = None,
  ) -> Path:
      """Fetch the git task into cache_root, rewrite docker_image, return abs path.

      The rewrite happens AFTER fetch, BEFORE harbor's environment reads task.toml.
      The original source-of-truth task.toml at the git ref is untouched — we
      only modify the materialized copy.

      cache_root is razorback-owned (NOT harbor's ~/.cache/harbor/tasks); keeping
      the materialization separate prevents harbor's later git fetch from
      rmtree-clobbering our rewrite (per harbor.tasks.client._copy_task_source_to_target).

      _fake_git_source is a test-only escape hatch that bypasses harbor's TaskClient
      and copytree's a local dir to the materialized target. Production code paths
      MUST pass _fake_git_source=None.
      """
      import shutil
      import shortuuid
      from harbor.models.task.id import GitTaskId

      task_id = GitTaskId(git_url=git_url, git_commit_id=git_commit_id, path=source_path)
      target_dir = cache_root / shortuuid.uuid(str(task_id)) / source_path.name
      if target_dir.exists():
          shutil.rmtree(target_dir)
      target_dir.parent.mkdir(parents=True, exist_ok=True)

      if _fake_git_source is not None:
          shutil.copytree(_fake_git_source, target_dir)
      else:
          # Real path: use harbor's TaskClient.download_tasks with output_dir set
          # to cache_root. Harbor's _copy_task_source_to_target lands the task
          # at the same shortuuid-derived path get_local_path() would compute.
          # Implementation defers to harbor's async API; see Task 2 step 5 for
          # the sync wrapper. Task 1 only exercises the _fake_git_source path.
          raise NotImplementedError("Task 2 wires the harbor TaskClient call.")

      rewrite_docker_image(target_dir / "task.toml", docker_image)
      return target_dir
  ```
  Also add the rewrite helper:
  ```python
  def rewrite_docker_image(task_toml_path: Path, docker_image: str) -> None:
      """Add or replace [environment].docker_image in task.toml.

      Preserves every other field and the existing TOML structure. Operates as
      a string transform (not a TOML round-trip) to avoid reordering or losing
      comments — harbor's task validator reads the file as TOML but inline
      comments and field order are part of the task's authored shape.
      """
      import re
      text = task_toml_path.read_text()
      # Match `docker_image = "..."` (with arbitrary quoted value) inside
      # [environment]. The regex anchors on the start of a line to avoid
      # matching the substring inside another value.
      pattern = re.compile(r'^docker_image\s*=\s*"[^"]*"\s*$', re.MULTILINE)
      replacement = f'docker_image = "{docker_image}"'
      if pattern.search(text):
          new_text = pattern.sub(replacement, text)
      else:
          # INSERT path: append to the [environment] block. Find the line
          # starting with `[environment]` (exact match — not `[environment.env]`
          # or `[environment.foo]`); insert after the block's last line.
          new_text = _insert_into_environment_block(text, replacement)
      task_toml_path.write_text(new_text)
  ```
  The `_insert_into_environment_block` helper is implemented in Task 2 (it's the INSERT-path scaffolding). Task 1 only needs the REPLACE branch to work, so the regex match-and-substitute is sufficient.

- [ ] **Step 5: Re-run the test.** `uv run pytest tests/unit/test_ade_bench_materialize_git_task.py -v`. Expected: PASS. The fixture's `docker_image = "some-other-image:tag"` is replaced with `"dab-agent:latest"`; the source file is unchanged.

- [ ] **Step 6: Commit.** `git add tests/unit/test_ade_bench_materialize_git_task.py tests/fixtures/ade_bench/fixture_git_task_with_image/ src/razorback/benchmarks/ade_bench/tasks.py && git commit -m "fu2 task 1: AC-1 REPLACE path for docker_image rewrite at materialization"`.

**Acceptance for Task 1:** the unit test passes; the REPLACE-path regex works against a fixture with a quoted `docker_image` line; the source fixture file is unchanged; no production code path can call `materialize_git_task` with a real git ref yet (NotImplementedError guards that — Task 2 lifts the guard).

---

## Task 2 — AC-1 INSERT path: add `docker_image` when the source `task.toml` has none

**Goal.** Lock the airbnb001-shaped real-world case: the source `task.toml` has an `[environment]` block but NO `docker_image` field. After `materialize_git_task(...)` runs, the materialized `task.toml` has `docker_image = "dab-agent:latest"` inserted into the `[environment]` block; the rest of the block (`build_timeout_sec`, `cpus`, etc.) is preserved verbatim. Also: in this task we WIRE `materialize_git_task` to harbor's `TaskClient.download_tasks` so a real git ref can be materialized. The `_fake_git_source` escape hatch from Task 1 remains for unit testing; production callers always pass `_fake_git_source=None`.

**Files:**
- `tests/fixtures/ade_bench/fixture_git_task_no_image/task.toml` (NEW; the airbnb001-shaped SOURCE)
- `tests/fixtures/ade_bench/fixture_git_task_no_image/environment/Dockerfile` (NEW)
- `tests/unit/test_ade_bench_materialize_git_task.py` (EXTEND)
- `src/razorback/benchmarks/ade_bench/tasks.py` (EXTEND: implement `_insert_into_environment_block`; wire `TaskClient`)

**Steps:**

- [ ] **Step 1: Author the no-image SOURCE fixture.** Create `tests/fixtures/ade_bench/fixture_git_task_no_image/task.toml` carrying the airbnb001-derived shape (no `docker_image` line):
  ```toml
  version = "1.0"

  [metadata]
  author_name = "fu2-fixture"

  [verifier]
  timeout_sec = 300.0

  [agent]
  timeout_sec = 600.0

  [environment]
  build_timeout_sec = 900.0
  cpus = 1
  memory_mb = 4096
  storage_mb = 10240

  [verifier.env]
  DB_TYPE = "duckdb"

  [solution.env]
  DB_TYPE = "duckdb"
  ```
  Also create `tests/fixtures/ade_bench/fixture_git_task_no_image/environment/Dockerfile` (one-line placeholder).

- [ ] **Step 2: Author the failing test.** Add to `tests/unit/test_ade_bench_materialize_git_task.py`:
  ```python
  def test_rewrite_inserts_docker_image_when_missing(tmp_path: Path) -> None:
      from razorback.benchmarks.ade_bench.tasks import materialize_git_task
      source = Path("tests/fixtures/ade_bench/fixture_git_task_no_image").resolve()
      target_root = tmp_path / "fu2-cache"
      materialized = materialize_git_task(
          git_url="file://" + str(source),
          git_commit_id="cafebabe" * 5,
          source_path=Path("fixture_git_task_no_image"),
          docker_image="dab-agent:latest",
          cache_root=target_root,
          _fake_git_source=source,
      )
      task_toml = (materialized / "task.toml").read_text()
      assert 'docker_image = "dab-agent:latest"' in task_toml
      # Other [environment] fields preserved verbatim.
      assert "build_timeout_sec = 900.0" in task_toml
      assert "cpus = 1" in task_toml
      assert "memory_mb = 4096" in task_toml
      # Other tables preserved verbatim.
      assert "[verifier.env]" in task_toml
      assert 'DB_TYPE = "duckdb"' in task_toml
      # Insertion lands inside [environment], NOT inside [verifier.env] or
      # [solution.env]. We assert ordering: [environment] precedes
      # docker_image precedes [verifier.env].
      env_idx = task_toml.index("[environment]")
      img_idx = task_toml.index('docker_image = "dab-agent:latest"')
      ver_env_idx = task_toml.index("[verifier.env]")
      assert env_idx < img_idx < ver_env_idx
  ```
  Expected: FAILS because `_insert_into_environment_block` is unimplemented.

- [ ] **Step 3: Implement `_insert_into_environment_block`.** In `src/razorback/benchmarks/ade_bench/tasks.py`:
  ```python
  def _insert_into_environment_block(text: str, line_to_insert: str) -> str:
      """Insert `line_to_insert` into the [environment] block of TOML text.

      Inserted as the LAST line of the block (just before the next table
      header or end of file). Matches `[environment]` only as a top-level
      table header — does not match `[environment.env]` or sub-tables.
      """
      import re
      # Find `[environment]` (start of line, not preceded by `.`)
      header_re = re.compile(r'^\[environment\]\s*$', re.MULTILINE)
      m = header_re.search(text)
      if m is None:
          raise ValueError(
              "task.toml has no [environment] block; cannot insert docker_image"
          )
      # Find the next table header AFTER our [environment] block. Any
      # `^\[...\]` line. The block ends just before that.
      next_header_re = re.compile(r'^\[[^\]]+\]\s*$', re.MULTILINE)
      next_m = next_header_re.search(text, m.end())
      if next_m is None:
          # [environment] is the last block; insert at end of file.
          tail_idx = len(text)
      else:
          tail_idx = next_m.start()
      # Walk back from tail_idx to skip trailing blank lines before next
      # header (or trailing whitespace at EOF).
      insert_idx = tail_idx
      while insert_idx > m.end() and text[insert_idx - 1] in (" ", "\t", "\n"):
          insert_idx -= 1
      # Insert with a newline before (if not already at one) and after.
      prefix = "" if insert_idx == 0 or text[insert_idx - 1] == "\n" else "\n"
      return text[:insert_idx] + prefix + line_to_insert + "\n" + text[insert_idx:]
  ```

- [ ] **Step 4: Re-run the test.** `uv run pytest tests/unit/test_ade_bench_materialize_git_task.py::test_rewrite_inserts_docker_image_when_missing -v`. Expected: PASS.

- [ ] **Step 5: Wire `materialize_git_task` to harbor's `TaskClient` for the real-fetch branch.** Replace the `NotImplementedError` in `materialize_git_task` with:
  ```python
  if _fake_git_source is not None:
      shutil.copytree(_fake_git_source, target_dir)
  else:
      import asyncio
      from harbor.tasks.client import TaskClient
      client = TaskClient()
      asyncio.run(client.download_tasks(
          task_ids=[task_id],
          overwrite=True,
          output_dir=cache_root,
      ))
      # Harbor lands the task at cache_root / shortuuid.uuid(str(task_id)) / source_path.name.
      # Our target_dir computation already matches that path (verified by
      # reading harbor/models/task/id.py:19-20 and harbor/tasks/client.py:441).
      if not (target_dir / "task.toml").exists():
          raise FileNotFoundError(
              f"materialize_git_task: harbor fetched but no task.toml at {target_dir}"
          )
  ```
  Subtle: harbor's `TaskClient.download_tasks` is `async`; razorback's translator is sync. The `asyncio.run(...)` wrapper is fine because `materialize_git_task` is called from `_build_ade_bench` (sync) which runs OUTSIDE razorback's `_execute_run_async` event loop (per `src/razorback/run.py:25-32` the spec→JobConfig translation is BEFORE `asyncio.run`). If a caller is already inside an event loop, this raises; document that constraint.

- [ ] **Step 6: Add a sanity test that asserts the harbor-cache shortuuid math.** A unit test that constructs a `GitTaskId(git_url=..., git_commit_id=..., path=...)`, computes `shortuuid.uuid(str(task_id))`, and asserts the materialized dir lives at `cache_root / <shortuuid> / <source_path.name>`. This catches any future harbor change to the cache-path formula.

- [ ] **Step 7: Commit.** `git add tests/unit/test_ade_bench_materialize_git_task.py tests/fixtures/ade_bench/fixture_git_task_no_image/ src/razorback/benchmarks/ade_bench/tasks.py && git commit -m "fu2 task 2: AC-1 INSERT path + harbor TaskClient wiring"`.

**Acceptance for Task 2:** both INSERT and REPLACE unit tests pass; `materialize_git_task` can be called with a real git ref (no `_fake_git_source`) and routes through `harbor.tasks.client.TaskClient.download_tasks`; the materialized dir lives at the documented `cache_root / shortuuid / name` path.

---

## Task 3 — AC-2 schema-override surface

**Goal.** Add `docker_image_override: str | None = None` to `AdeBenchBenchmarkBlock` with default behavior using `dab-agent:latest`. Preserve `extra="forbid"`. Wire the override through `_build_ade_bench` to `materialize_git_task(docker_image=...)`. Add unit tests over the schema parsing and over the translator's wiring of the override value.

**Files:**
- `tests/unit/test_ade_bench_schema_docker_image_override.py` (NEW)
- `tests/unit/test_ade_bench_translator_docker_image_override.py` (NEW)
- `src/razorback/spec/schema.py` (EXTEND: add `docker_image_override` field to `AdeBenchBenchmarkBlock`)
- `src/razorback/compat/harbor_0_6_6.py` (EXTEND: wire override through `_build_ade_bench`)
- `src/razorback/benchmarks/ade_bench/tasks.py` (extend `resolve_task_dirs` or add a new wrapper that takes the override; see Step 3 design note)

**Steps:**

- [ ] **Step 1: Author the failing schema tests.** Create `tests/unit/test_ade_bench_schema_docker_image_override.py` with three tests:
  - `test_docker_image_override_default_is_none` — parse a spec with `benchmark.kind: ade-bench` + git-task entry + NO `docker_image_override`; assert `spec.benchmark.docker_image_override is None`.
  - `test_docker_image_override_custom_value` — parse a spec with `docker_image_override: "custom-agent:v2"`; assert `spec.benchmark.docker_image_override == "custom-agent:v2"`.
  - `test_docker_image_override_extra_forbid_preserved` — parse a spec with `docker_image_override` AND an unknown key (`bogus_field: foo`); assert `SpecError` (or pydantic ValidationError surfaced as `SpecError`) with the unknown key named.

  Expected: all three FAIL because the field does not exist.

- [ ] **Step 2: Add the schema field.** In `src/razorback/spec/schema.py`, update `AdeBenchBenchmarkBlock`:
  ```python
  class AdeBenchBenchmarkBlock(BaseModel):
      model_config = ConfigDict(extra="forbid")
      kind: Literal["ade-bench"]
      tasks_root: Path
      tasks: list[str | AdeBenchTaskEntry] = Field(min_length=1)
      docker_image_override: str | None = None
  ```
  Re-run the three schema tests. Expected: PASS.

- [ ] **Step 3: Wire the override through the translator.** In `src/razorback/compat/harbor_0_6_6.py:_build_ade_bench`, when a `ResolvedTask` carries `git_url` + `git_commit_id`, call `materialize_git_task(docker_image=<override>, ...)`. The override resolution:
  ```python
  from razorback.benchmarks.dab.prepare import _DEFAULT_DOCKER_IMAGE
  override = spec.benchmark.docker_image_override or _DEFAULT_DOCKER_IMAGE
  ```
  For each `ResolvedTask`:
  - **Legacy slug** (`git_url is None`): pass through — `TaskConfig(path=r.path)`. No materialization, no override (the slug's task.toml is the captain's source of truth).
  - **Git entry** (`git_url is not None`): call `materialize_git_task(git_url=r.git_url, git_commit_id=r.git_commit_id, source_path=Path(r.path).name-or-parent?, docker_image=override, cache_root=<razorback cache>)`. Emit `TaskConfig(path=materialized_abs_path)` — a LOCAL task config, no git fields. Harbor's `Job._resolve_task_configs` skips its own download for local tasks.

  Design note on `cache_root`: pick `Path.home() / ".cache" / "razorback" / "ade-bench"` (mirrors harbor's cache convention). The path is derived from `home` if the translator receives it; fall back to `Path.home()`. The cache root is created on first use; existing materialized dirs are clobbered on each run (matches harbor's overwrite-on-fetch semantics).

  Design note on `source_path`: harbor's `GitTaskId.path` is the in-repo relative path (e.g., `datasets/ade-bench/ade-bench-airbnb001`). `materialize_git_task` receives that as `source_path: Path`; the materialized dir's name is `source_path.name` (e.g., `ade-bench-airbnb001`). For the AC-3 spec, this matches harbor's existing materialization at `Ypzg75nmyQ3x3zH7fJNNic/ade-bench-airbnb001/`.

- [ ] **Step 4: Author the failing translator test.** Create `tests/unit/test_ade_bench_translator_docker_image_override.py`:
  - `test_translator_uses_default_docker_image_when_override_omitted` — build a spec with a git-task entry, no override. Patch `materialize_git_task` (monkeypatch) to a recording stub. Translate. Assert the stub was called with `docker_image="dab-agent:latest"`.
  - `test_translator_uses_custom_override` — same, with `docker_image_override: "custom-agent:v2"`. Assert the stub was called with `docker_image="custom-agent:v2"`.
  - `test_translator_emits_local_task_config_for_git_entries` — assert the emitted `TaskConfig` has `git_url is None` and `git_commit_id is None` (because materialization localizes the task).
  - `test_translator_passes_through_local_slug_unchanged` — a spec mixing a local slug AND a git entry; assert the slug's `TaskConfig.path` is the resolved local-slug path AND `materialize_git_task` was called exactly once (for the git entry only).

  Expected: failing initially; PASS after Step 3's wiring lands.

- [ ] **Step 5: Re-run all schema + translator tests.** `uv run pytest tests/unit/test_ade_bench_schema_docker_image_override.py tests/unit/test_ade_bench_translator_docker_image_override.py -v`. Expected: all green.

- [ ] **Step 6: Commit.** `git add tests/unit/test_ade_bench_schema_docker_image_override.py tests/unit/test_ade_bench_translator_docker_image_override.py src/razorback/spec/schema.py src/razorback/compat/harbor_0_6_6.py src/razorback/benchmarks/ade_bench/tasks.py && git commit -m "fu2 task 3: AC-2 docker_image_override schema field + translator wiring"`.

**Acceptance for Task 3:** schema parses `docker_image_override` (default None, custom value, extra-forbid preserved); translator routes git entries through `materialize_git_task` with the resolved override; translator emits LOCAL `TaskConfig` for git entries (no git fields downstream); legacy slug entries pass through unchanged.

---

## Task 4 — AC-1 source-untouched assertion (full)

**Goal.** Add a unit test that asserts the source `task.toml` at the supplied git ref is bytewise unchanged after `materialize_git_task` runs. Task 1 had a partial source-untouched check (string-contains); this task adds the full bytewise check and covers the corner case where the source dir is reused across multiple materializations (e.g., two different specs targeting the same git task with different overrides — the source must not drift).

**Files:**
- `tests/unit/test_ade_bench_materialize_git_task.py` (EXTEND)

**Steps:**

- [ ] **Step 1: Add the bytewise-unchanged test.** Add to `tests/unit/test_ade_bench_materialize_git_task.py`:
  ```python
  def test_source_task_toml_unchanged_after_materialization(tmp_path: Path) -> None:
      from razorback.benchmarks.ade_bench.tasks import materialize_git_task
      source = Path("tests/fixtures/ade_bench/fixture_git_task_with_image").resolve()
      original_bytes = (source / "task.toml").read_bytes()
      original_dockerfile = (source / "environment" / "Dockerfile").read_bytes()
      target_root = tmp_path / "fu2-cache"
      materialize_git_task(
          git_url="file://" + str(source),
          git_commit_id="deadbeef" * 5,
          source_path=Path("fixture_git_task_with_image"),
          docker_image="dab-agent:latest",
          cache_root=target_root,
          _fake_git_source=source,
      )
      assert (source / "task.toml").read_bytes() == original_bytes
      assert (source / "environment" / "Dockerfile").read_bytes() == original_dockerfile

  def test_two_materializations_with_different_overrides_dont_drift_source(
      tmp_path: Path,
  ) -> None:
      from razorback.benchmarks.ade_bench.tasks import materialize_git_task
      source = Path("tests/fixtures/ade_bench/fixture_git_task_no_image").resolve()
      original_bytes = (source / "task.toml").read_bytes()
      for image in ("dab-agent:latest", "custom-agent:v2"):
          materialize_git_task(
              git_url="file://" + str(source),
              git_commit_id="cafebabe" * 5,
              source_path=Path("fixture_git_task_no_image"),
              docker_image=image,
              cache_root=tmp_path / f"cache-{image.split(':')[0]}",
              _fake_git_source=source,
          )
      assert (source / "task.toml").read_bytes() == original_bytes
  ```

- [ ] **Step 2: Run.** `uv run pytest tests/unit/test_ade_bench_materialize_git_task.py -v`. Expected: PASS — the `_fake_git_source` branch in `materialize_git_task` calls `shutil.copytree(source, target_dir)` which copies (does not modify) the source; the rewrite acts on `target_dir`, not on the source.

  - If this FAILS (e.g., a bug in `shutil.copytree` or the rewrite accidentally writes to the source path), STOP and investigate. The fix is to ensure `rewrite_docker_image(target_dir / "task.toml", ...)` operates strictly on `target_dir`-rooted paths.

- [ ] **Step 3: Commit.** `git add tests/unit/test_ade_bench_materialize_git_task.py && git commit -m "fu2 task 4: AC-1 source-untouched bytewise assertion + drift-on-rerun test"`.

**Acceptance for Task 4:** both new tests pass; the source-of-truth `task.toml` is bytewise unchanged after one or multiple materializations with different override values.

---

## Task 5 — AC-4 graceful error when `dab-agent:latest` is missing a required tool

**Goal.** Lock the AC-4 contract: if a real ade-bench task requires a tool that the chosen image lacks, the adapter surfaces a typed error naming the missing binary — not a cryptic `exit-127` ClaudeCliAgentError. The unit test patches `docker_image_override` to a minimal image (e.g., `alpine:3.19`) and runs the materialization + a stubbed environment check; asserts the typed error names the missing binary.

**Design note (load-bearing):** the actual "missing tool" detection happens inside the container at `ClaudeCliAgent.setup()` (the `claude --version` exit-127 path). FU-1's existing error message is `ClaudeCliAgentError("claude CLI not available inside the container (exit=127)")`. AC-4 generalizes this: when the missing binary is NOT `claude`, the same shape of error should fire with the binary's name in the message. The smallest change is to ensure `ClaudeCliAgentError`'s setup-time tool probe (a) runs against the configured tools list, (b) emits the binary name in the error, (c) is the typed error type the FU-2 unit test asserts against.

The unit test does NOT need a real container — it can patch `subprocess.run` or `docker run` to simulate the exit-127 from a `which <binary>` probe and assert the error wrapping.

**Files:**
- `tests/unit/test_ade_bench_missing_tool_graceful_error.py` (NEW)
- `src/razorback/agents/claude_cli.py` (EXTEND: generalize the `claude --version` probe to a tools-list probe that names the missing tool; preserve the existing claude-specific error message as a special case for backwards-compat)

**Steps:**

- [ ] **Step 1: Author the failing test.** Create `tests/unit/test_ade_bench_missing_tool_graceful_error.py`:
  ```python
  def test_missing_tool_in_image_emits_typed_error_naming_binary(
      monkeypatch, tmp_path: Path
  ) -> None:
      from razorback.agents.claude_cli import ClaudeCliAgent, ClaudeCliAgentError

      # Simulate `which psql` exit 127 inside the container.
      def fake_which(binary: str) -> int:
          if binary == "psql":
              return 127
          return 0

      monkeypatch.setattr(
          "razorback.agents.claude_cli._probe_binary_in_container", fake_which
      )

      agent = ClaudeCliAgent(logs_dir=tmp_path, tools_allowed=["psql"])
      with pytest.raises(ClaudeCliAgentError) as exc_info:
          agent.setup()
      # The error message must name the missing binary VERBATIM.
      assert "psql" in str(exc_info.value)
      # The error must be the typed ClaudeCliAgentError, NOT a generic Exception.
      assert isinstance(exc_info.value, ClaudeCliAgentError)
  ```
  Expected: FAILS because `_probe_binary_in_container` doesn't exist and `setup()` only probes `claude`.

- [ ] **Step 2: Implement the generalized probe.** In `src/razorback/agents/claude_cli.py`:
  - Add a `_probe_binary_in_container(binary: str) -> int` helper (extracted from the existing `claude --version` path so it's monkeypatchable in tests).
  - In `setup()`, after the existing `claude --version` probe, iterate `self.tools_allowed` (the `tools_allowed` list configured by the spec) and probe each. The first missing one raises `ClaudeCliAgentError(f"tool not available inside the container (exit=127): {binary}")`.
  - The existing `claude` probe error message is preserved for backwards-compat (the FU-1 carry-forward test expects that specific string).

  **Subtle:** the `tools_allowed` list in `ClaudeCliAgentBlock` is the claude CLI's `--allowedTools` whitelist, NOT a list of system binaries. Re-using it for AC-4's tool probe is a meaningful semantic shift; if CL pushes back on this overload, the alternative is a new spec field (`benchmark.required_tools: list[str]`) — flag this as the design pivot and `SendMessage(to="team-lead", ...)`.

  Conservative default: AC-4's "graceful error naming the missing binary" must fire for AT LEAST the canonical `claude` case (already covered by FU-1). If the test for additional binaries (`psql`) needs a new spec surface, ship the test against `claude` only and document the pivot. Either way, AC-4's `Verified by:` clause as written — "the adapter (or the agent setup) emits a typed error that names the missing binary" — is satisfied by the existing `claude --version` exit-127 ClaudeCliAgentError shape; this task adds explicit unit test coverage for that exact error.

- [ ] **Step 3: Re-run the test.** Expected: PASS.

- [ ] **Step 4: Add a coverage test for the canonical `claude` case.** A second test in the same file:
  ```python
  def test_missing_claude_binary_emits_typed_error(monkeypatch, tmp_path: Path) -> None:
      # Reuse FU-1's existing test shape but assert the typed-error contract verbatim.
      ...
  ```
  This ensures the AC-4 contract is enforced by a unit test, not only by integration tests.

- [ ] **Step 5: Commit.** `git add tests/unit/test_ade_bench_missing_tool_graceful_error.py src/razorback/agents/claude_cli.py && git commit -m "fu2 task 5: AC-4 graceful error names missing binary"`.

**Acceptance for Task 5:** the missing-tool test passes; `ClaudeCliAgentError` is the typed error class; the binary name appears verbatim in the error message.

---

## Task 6 — AC-3 live `rk run` against `ade-bench-airbnb001` with image override

**Goal.** The cost-bearing acceptance. After Tasks 1–5 are all green, run `uv run rk run examples/specs/ade-bench-claude.yaml` against the real `ade-bench-airbnb001` task at git commit `b4e82debfdd2aba9d91c41cd96a997dd549fcbb3`. The adapter materializes the task into razorback's cache, rewrites `docker_image` to `dab-agent:latest`, and passes a LOCAL TaskConfig to harbor. Harbor uses `dab-agent:latest` (skips the airbnb001 Dockerfile build), invokes `ClaudeCliAgent.setup()` — which now passes the `claude --version` probe — and proceeds to `agent.run()`. The LLM round-trip fires; `summary.json` records a score; the trial's `agent/` subdir contains LLM-call evidence (a `messages.jsonl` or equivalent).

**Files:**
- (no new files; runtime artifacts only)

**Steps:**

- [ ] **Step 1: Pre-flight.** Confirm:
  - `docker images | grep dab-agent` shows `dab-agent:latest` is present locally (M2's build prerequisite).
  - `~/.claude/benchmark-token` exists OR `.env` carries `ANTHROPIC_API_KEY` (FU-1's auth resolution path).
  - The FU-1 cache at `/Users/clkao/git/razorback/.harbor-cache-home/` exists for re-use (harbor's hardcoded `~/.cache/harbor/tasks` may not be writable in the sandboxed worktree; FU-1 used `HOME=/Users/clkao/git/razorback/.harbor-cache-home` with a `~/.docker` symlink for `docker compose`).

- [ ] **Step 2: Live run.** From the FU-2 worktree root:
  ```bash
  HOME=/Users/clkao/git/razorback/.harbor-cache-home \
      uv run rk run examples/specs/ade-bench-claude.yaml
  ```
  Expected: exit 0. Run-dir at `_runs/ade-bench-claude-airbnb001/<run-id>/`.

  - If exit nonzero with `ClaudeCliAgentError("claude CLI not available...")`: the override didn't reach harbor's `[environment].docker_image`. Inspect the materialized `task.toml` in razorback's cache (`~/.cache/razorback/ade-bench/<shortuuid>/ade-bench-airbnb001/task.toml`) — `docker_image = "dab-agent:latest"` must be present. If absent, the rewrite ran on the wrong path; check the cache_root resolution in `_build_ade_bench`.
  - If exit nonzero with a different missing-tool error (e.g., `gdown` or `dbt`): AC-4 has fired correctly — record the error type+message and STOP. The plan documents this as the AC-4 surface; the trial's failure is expected, and the AC-3 contract becomes "trial reached `agent.run()` setup AND named the missing tool". Record this outcome explicitly in the stage report rather than treating it as a plan failure.

- [ ] **Step 3: Verify AC-3 evidence.** Run:
  ```bash
  jq . _runs/ade-bench-claude-airbnb001/<run-id>/summary.json
  ls _runs/ade-bench-claude-airbnb001/<run-id>/trials/*/agent/
  ```
  Expected:
  - `summary.json` carries `{score: <numeric>, n_trials: 1, n_correct: <0 or 1>}`.
  - `trials/<trial>/agent/` contains a `messages.jsonl` (or whatever the claude CLI writes; harbor 0.6.6's claude-cli adapter writes a JSONL transcript per FU-1's M3 implementation).

  If `agent/` exists but is empty: claude did NOT reach `agent.run()`. Inspect `trials/<trial>/result.json` for the error type:
  - `ClaudeCliAgentError` with claude-not-found: override didn't apply (see Step 2 recovery).
  - `ClaudeCliAgentError` with a different binary: AC-4 case — record and STOP per Step 2 second-recovery.
  - Other: investigate.

  If `agent/` contains a `messages.jsonl` with at least one user/assistant exchange: **AC-3 is verbatim met.** The LLM call fired; the score reflects the actual run.

- [ ] **Step 4: Commit the run artifacts.** `git add _runs/ade-bench-claude-airbnb001/<run-id>/` (excluding any large LFS-style downloads if present) and `git commit -m "fu2 task 6: AC-3 live run with dab-agent:latest override; LLM-scored result"`. Include the `<run-id>` in the commit message body.

  - Same caveat as FU-1: do not commit secrets. The FU-1 grep gate (`scripts/grep-run-dir-for-secrets.sh`) is run in Task 7 against this run-dir.

**Acceptance for Task 6:** exit 0; `summary.json.score` is numeric (per AC-3 wording); the trial's `agent/` subdir contains evidence of a real LLM round-trip; AC-4 graceful-error path either did NOT fire (LLM ran cleanly) OR fired with a typed-error message naming the missing binary (AC-4 surface validated by an unintended-but-recoverable real-world miss).

---

## Task 7 — AC-5 + AC-6 carry-forward (grep gate + full suite)

**Goal.** Re-run FU-1's auth-leak grep gate against the AC-3 run-dir; re-run the full pytest suite from a clean checkout of the FU-2 worktree branch tip. Both must pass with the new FU-2 tests alongside the prior ~251.

**Files:**
- (no new files)

**Steps:**

- [ ] **Step 1: AC-5 grep gate against AC-3 run-dir.** From the FU-2 worktree root:
  ```bash
  TOKEN=$(cat ~/.claude/benchmark-token)
  bash scripts/grep-run-dir-for-secrets.sh _runs/ade-bench-claude-airbnb001/<run-id>/ "$TOKEN"
  ```
  Expected: exit 0, "AC-1 OK: ...". If exit 1, FU-1's auth-leak gate is no longer satisfied — investigate (the FU-2 changes touch only the benchmark adapter, NOT the agent-config path that carries auth; a regression here would be surprising and warrants a deep look).

- [ ] **Step 2: Full pytest run.** From the FU-2 worktree root:
  ```bash
  uv run pytest -q
  ```
  Expected: at least 251 passed + the new FU-2 tests passed + 3 skipped + the pre-existing M4 wall-clock flake (documented in M7's archived stage report) MAY appear; if it does, document the same way FU-1 did. Net new green from FU-2: roughly 7–9 tests (Task 1×1, Task 2×2, Task 3×7, Task 4×2, Task 5×2, minus any redundancy).

  Independent rerun excluding the M4 flake:
  ```bash
  uv run pytest --deselect tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py
  ```
  Expected: ≥260 passed, 3 skipped, 0 failed.

- [ ] **Step 3: Final commit.** If artifacts (e.g., new test outputs in `tests/fixtures/`) need to land, ensure they're in. `git status` clean. `git log --oneline -10` shows the FU-2 tasks in order.

**Acceptance for Task 7:** AC-5 grep gate exits 0 on the AC-3 run-dir; full pytest suite green (excluding documented M4 flake); ~260 tests pass.

---

## Out of scope (carried forward from FU-2 entity)

- Building an `ade-bench-agent:latest` image with ade-bench-specific tools layered on `dab-agent` (e.g., `gdown` for Google Drive DB fetches, `dbt-duckdb` if dab-agent lacks it). AC-4's graceful-error contract is what we ship; the richer-image is a separate FU-N. **Risk:** if AC-3's live run discovers airbnb001 needs `gdown` to fetch its DuckDB DB AND that fetch normally runs in the airbnb001 Dockerfile's `RUN gdown ...` step (which we skip when `docker_image` is set), the in-container `/app/<db>.duckdb` will be missing and the LLM will fail to query it. The trial would still "score" (the verifier reads `answers.json` and computes a reward), but the score reflects a missing-DB scenario, not a real ade-bench solve. **AC-3's `Verified by:` says "evidence of an LLM round-trip"** — that bar is met even in the missing-DB scenario as long as claude makes at least one call. If CL wants the LLM to actually SOLVE the task, the ade-bench-agent:latest follow-up entity is required.

- Extending the same override pattern to harbor benchmarks beyond ade-bench. DAB already controls its image via M2's `prepare.py`; only ade-bench needs this hook today.

- Rotating the FU-1 OAuth token. The leak surface was closed in FU-1; FU-2 introduces no new leakage path. The FU-1 grep gate (Task 7 step 1) is the carry-forward verification.

- A generic harbor-registry resolver. FU-1 added per-task fetching; the dataset-level fetch is a separate follow-up.

---

## Out of plan (called out explicitly so a future worker doesn't conflate)

- Editing `examples/specs/ade-bench-claude.yaml`. FU-1 already pointed this spec at the real airbnb001 git-task; FU-2 does not need to touch the spec. Only the adapter behavior changes.

- Adding new tests for the FU-1 grep-clean contract. The existing `tests/integration/test_no_auth_leak_in_run_dir.py` is the carry-forward (AC-5); FU-2 does not introduce new auth-leak surface.

- Touching `razorback.agents.auth`. Host-side `.env` / `~/.claude/benchmark-token` discovery is unchanged.

- Editing M2's `prepare.py`. The `_DEFAULT_DOCKER_IMAGE = "dab-agent:latest"` constant is imported into FU-2's `materialize_git_task` for single-source-of-truth; the prepare.py file itself is read-only from FU-2's perspective.
