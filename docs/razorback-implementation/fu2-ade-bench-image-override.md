---
id: bbc6xyn89fqde0vxqc50yw7m
title: FU-2 — ade-bench image override (real LLM-scored result)
status: validation
source: post-FU1 follow-up (CL 2026-05-19)
started: 2026-05-19T17:59:13Z
completed:
verdict:
score: 0.95
worktree: .worktrees/spacedock-ensign-fu2-ade-bench-image-override
issue:
pr:
mod-block:
---

## Problem

FU-1 closed the M3 auth-leak code path and wired razorback's
ade-bench adapter to fetch real tasks from
`laude-institute/harbor-datasets.git` via harbor's git-task shape.
The literal AC-5 verbatim clauses (exit 0, numeric `score`,
grep-clean run-dir) were all satisfied; the validator approved.

But the spirit of "real ade-bench result" — an LLM call actually
firing against a real ade-bench task and producing a scored
outcome — is **not** met. The real laude-institute ade-bench tasks
ship their own task-specific Dockerfiles (`environment/Dockerfile`
per task) that do not have `claude` on PATH. When the
`ClaudeCliAgent` ran its `setup()` step against the fetched
`ade-bench-airbnb001` task, `claude --version` exited 127 inside
the container, the agent raised `ClaudeCliAgentError` before any
LLM round-trip could fire, and the trial scored 0.0 from the
fallback path.

M2's DAB adapter solves the analogous problem differently: M2
**constructs** each task's harbor manifest itself
(`src/razorback/benchmarks/dab/prepare.py:152-167`), baking in
`docker_image = "dab-agent:latest"` regardless of what the source
materials say. The ade-bench adapter fetches tasks as-is from
git, so razorback never owns the materialized `task.toml` and
never gets a chance to override the image.

FU-2 closes the spirit gap by patching the fetched
`task.toml`'s `docker_image` after fetch but before harbor sees
it.

## Acceptance criteria

**AC-1 — Razorback's ade-bench adapter rewrites `docker_image` in
the materialized task.toml to `dab-agent:latest` (or an
equivalent claude-bearing image) after fetching from
`git_url`/`git_commit_id`, before harbor's `TaskConfig.path`
points at the directory.**
Verified by: a unit test fetches a fixture git-shaped task into
a tmp dir whose source `task.toml` declares `docker_image =
"some-other-image:tag"`; after razorback's adapter runs, the
post-fetch `task.toml` in the materialized location has
`docker_image = "dab-agent:latest"` (or the configured override
value). The original source-of-truth `task.toml` at the git ref
is untouched.

**AC-2 — The override target is configurable via the
`AdeBenchBenchmarkBlock`.**
Verified by: a unit test parses an ade-bench spec with
`benchmark.docker_image_override: "custom-agent:v2"` and
asserts the override is honored at materialization. When the
field is omitted, the default `dab-agent:latest` applies. The
schema's `extra="forbid"` is preserved (other unknown keys still
reject).

**AC-3 — Live `rk run` against a real ade-bench task with the
default `dab-agent:latest` image override produces a non-zero
LLM-scored result.**
Verified by: `uv run rk run examples/specs/ade-bench-claude.yaml`
(using a real `laude-institute/harbor-datasets.git` ade-bench
task, e.g., `ade-bench-airbnb001`) exits 0, the trial actually
reaches `agent.run()` (i.e., no `ClaudeCliAgentError` from
`claude --version` at setup), and `summary.json` records
`n_trials: 1` with a `score` that reflects an actual claude
invocation. The trial's `agent/` subdirectory contains evidence
of an LLM round-trip (a `messages.jsonl` or equivalent — exact
shape depends on what the claude CLI writes).

**AC-4 — If the real ade-bench task requires tools not present
in `dab-agent:latest`, the adapter surfaces a clear error
naming the missing tool — not a cryptic exit-127 or silent
trial failure.**
Verified by: a unit test patches `dab-agent` to a minimal image
missing a tool the ade-bench task expects (e.g., `psql`); the
adapter (or the agent setup) emits a typed error that names the
missing binary. This is a graceful-degradation contract — we may
discover real tools are missing in AC-3's live run.

**AC-5 — AC-1's grep-clean guarantee from FU-1 still holds.**
Verified by: the same `tests/integration/test_no_auth_leak_in_run_dir.py`
test (or its successor) stays green; the live AC-3 run-dir is
grep-clean of the literal OAuth token. No regressions on the
auth-leak surface.

**AC-6 — All carry-forward tests stay green.**
Verified by: `uv run pytest` from a clean checkout of the FU-2
worktree branch tip exits 0 with the prior ~251 tests still
passing alongside the new FU-2 tests.

## Test plan

- **Unit tests:** docker_image override path (default value,
  custom override, omitted field); ade-bench spec schema rejects
  partial/conflicting overrides; missing-tool graceful error.
- **Integration test:** real-task fetch + image-override applied
  + claude invocation reaches `agent.run()`. Skipped if
  `dab-agent:latest` is not built locally.
- **Acceptance command:** `uv run rk run examples/specs/
  ade-bench-claude.yaml` against a real ade-bench task; jq the
  resulting `summary.json` for a meaningful score, inspect the
  trial's agent/ subtree for LLM-call evidence.

## Out of scope

- Building an `ade-bench-agent:latest` image with ade-bench-
  specific tools layered on `dab-agent`. If the real task needs
  tools dab-agent lacks (e.g., `snowflake` CLI), document it as a
  separate FU-N; AC-4's graceful-error contract is what we ship
  here.
- Extending the same image-override pattern to harbor benchmarks
  beyond ade-bench. The DAB path already controls the image; only
  ade-bench needs this hook today.
- Rotating the OAuth token. The leak surface was closed in FU-1;
  no new leakage path is introduced by FU-2.
- A generic "registry-resolver" path that fetches whole datasets
  from harbor's registry rather than individual git-shaped tasks.
  FU-1 added per-task fetching; the dataset-level fetch is a
  separate follow-up.

## Stage Report: plan

- DONE: Plan steps map 1:1 to the 6 ACs in the FU-2 entity body. The riskiest contract (AC-3 live LLM-scored run on a real ade-bench task) is the LAST task — because all the earlier unit tests must lock the materialization-rewrite shape before we spend a real claude call. The first task is AC-1: docker_image rewrite at materialization, with a fixture git-shaped task that has a non-overlapping image name.
  Plan AC↔task map table in the header explicitly orders Tasks 1–5 as TDD unit-test gates and Task 6 as the live cost-bearing AC-3 acceptance. Task 1 lands the REPLACE-path unit test with fixture `tests/fixtures/ade_bench/fixture_git_task_with_image/task.toml` declaring `docker_image = "some-other-image:tag"` — a deliberately non-overlapping image name that exercises the regex replace branch. Plan at `docs/razorback-implementation/plans/fu2-ade-bench-image-override.md` on main; CL's "Validating new mechanisms" rule is cited verbatim in the riskiest-contract-first preamble explaining the AC-3-last ordering.
- DONE: The plan reads M2's prepare.py at src/razorback/benchmarks/dab/prepare.py:152-167 to understand the M2 image-baking pattern. The plan also reads FU-1's just-landed ade-bench adapter (src/razorback/benchmarks/ade_bench/tasks.py and the git-task fetch path) to understand where to insert the docker_image rewrite.
  Plan §"M2 inputs (the prepare.py pattern)" cites `prepare.py:32` (the `_DEFAULT_DOCKER_IMAGE = "dab-agent:latest"` constant, reused via import) and `prepare.py:152-167` (the M2 full-write pattern), and explains the FU-2 divergence: M2 writes task.toml ground-up (DAB sources aren't harbor tasks); FU-2 rewrites a single field of an already-harbor-shaped task.toml (preserving every other field). Plan §"FU-1 inputs (do not duplicate)" cites `ade_bench/tasks.py:23-55` (`resolve_task_dirs` returning `ResolvedTask` with optional `git_url`/`git_commit_id`) and `compat/harbor_0_6_6.py:170-195` (`_build_ade_bench` emitting `TaskConfig(path=..., git_url=..., git_commit_id=...)`) — and proposes the smallest change: for git records, the translator now calls `materialize_git_task(...)` and emits a LOCAL `TaskConfig(path=<materialized_abs_path>)`, no git fields.
- DONE: The plan reads one or two real laude-institute/harbor-datasets ade-bench task.toml files (e.g., ade-bench-airbnb001 — the one FU-1 used as the AC-5 acceptance target) to understand: (a) what docker_image the real task ships with; (b) what other environment fields might collide with the dab-agent base; (c) whether the task expects any tool dab-agent doesn't have (informs AC-4's graceful-error scope). Cite the actual paths and quote the relevant TOML.
  Plan §"Authoritative external reference — the real ade-bench task.toml shape" reads and quotes `~/.cache/harbor/tasks/Ypzg75nmyQ3x3zH7fJNNic/ade-bench-airbnb001/task.toml` from FU-1's live AC-5 cache; documents three load-bearing observations: (a) the real task has NO `docker_image` line — harbor uses `environment/Dockerfile` instead, so the rewrite must INSERT not REPLACE (motivating Task 2's INSERT path with `_insert_into_environment_block`); (b) `version = "1.0"` (vs DAB's `schema_version = "1.2"`) is handled by harbor's `handle_version_rename` validator — the rewrite stays agnostic; (c) airbnb001's `environment/Dockerfile` installs dbt/duckdb/uv (in dab-agent) PLUS gdown/tmux/asciinema/nodejs/yq/pyyaml (likely NOT in dab-agent) — the `gdown` step fetches the DuckDB DB from Google Drive at image-build time, so skipping the Dockerfile means the in-container DB is missing. This is the AC-4 graceful-error surface and is also flagged in the "Out of scope" section as the obvious next FU-N (ade-bench-agent:latest image with task setup baked in).

### Summary

Wrote a TDD-shaped 7-task plan for FU-2: AC-1 REPLACE path (Task 1: regex-replace an existing `docker_image` line in a fixture git task), AC-1 INSERT path (Task 2: insert `docker_image` into the `[environment]` block when the source has none, matches airbnb001 shape) + harbor `TaskClient` wiring for real git fetch, AC-2 schema override (Task 3: `docker_image_override: str | None` field on `AdeBenchBenchmarkBlock` with `extra="forbid"` preserved + translator wires the override through `materialize_git_task`), AC-1 source-untouched (Task 4: bytewise-unchanged assertion + multi-rerun-no-drift test), AC-4 graceful error (Task 5: typed `ClaudeCliAgentError` names the missing binary), AC-3 live run (Task 6: `uv run rk run examples/specs/ade-bench-claude.yaml` against airbnb001 with the override applied; assert summary.json + LLM-call evidence in trial agent/), AC-5 + AC-6 carry-forward (Task 7: re-run FU-1 grep gate + full pytest suite). The materialization pattern: razorback owns a separate cache root (`~/.cache/razorback/ade-bench/`), uses `harbor.tasks.client.TaskClient.download_tasks(output_dir=<our cache>)` to fetch, rewrites `docker_image` in-place at our cache, then emits a LOCAL `TaskConfig(path=...)` so harbor skips its own git fetch (avoiding the `_copy_task_source_to_target` rmtree-clobber risk). Plan at `docs/razorback-implementation/plans/fu2-ade-bench-image-override.md` on `main` (no worktree — per dispatch instructions, plan stage stays on main).
