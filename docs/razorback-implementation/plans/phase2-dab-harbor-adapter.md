# Phase 2: DAB harbor adapter (sibling package), Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Entity:** `docs/razorback-implementation/phase2-dab-harbor-adapter.md`
(id `51f3z613j7xns0r38nma537r`).

**Goal.** Ship the DAB harbor adapter as a parallel sibling package
at `packages/razorback-plugin-dab/` (per captain decision D5). The
package emits one harbor-shaped task directory per `(dataset,
query_id)` for all 12 upstream DAB datasets, wires the live-DB
compose stack (postgres + mongo + agent on `dab-net`) into each
task's environment, carries the three workspace-README variants and
the verbatim `DISALLOWED_TOOLS` denylist published by upstream DAB,
and emits stratum-tagged trial output that razorback's `rk score` /
`rk diff` consume per spec §3.2 (`rk score`) and §8.3a /
§9.4 (stratum tagging). Razorback core is unchanged in this
phase; the only cross-repo touchpoint is `pyproject.toml` adding
`packages/razorback-plugin-dab/` to the uv workspace.

**Architecture.** The sibling package follows harbor's offline
benchmark-adapter contract probed in AC-0.2
(`docs/superpowers/plans/2026-05-19-harbor-entry-point-probe.md`):
a standalone Python package invoked as `uv run razorback-plugin-dab
…` that writes a tree of harbor task directories to disk; harbor
consumes them via `JobConfig.tasks[].path`. The plugin **does not**
register a harbor agent or environment via `import_path`; it is a
task-directory generator that runs upstream of `harbor run`, per
the entry-point probe's adapter-dispatch verdict. Razorback's `rk
run` (Phase 1) drives this by translating `benchmark: harbor_dab`
spec blocks into a list of harbor-shaped `tasks:` entries that
point at the plugin's output tree.

**Tech stack.** Python 3.12, `uv` (workspace), Pydantic 2.11, PyYAML
6, harbor (pinned by razorback core), docker via Colima with a
shared `dab-net` bridge network, postgres:17, mongo:8 (matching
dataagentbench/benchmark/setup.sh's pinned images), pytest 8 with
`pytest-asyncio` 0.24.

**Source of truth.** The v2 spec at
`docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`. Section
anchors below cite it by §-number (NOT by exact wording, since `ra`
is concurrently editing benchmark-adapter framing in §2 + §3 +
§8.4). The 9 ACs live in the entity body. Inherited content:

- Live-DB compose-stack design from archived PKG-3 at
  `docs/razorback-implementation/_archive/pkg3-dab-live-db-services-preflight.md`.
- Workspace-README variants (`direct-minimal`,
  `direct-structured`, `spacedock`) and DISALLOWED_TOOLS denylist
  from archived PKG-9 at
  `docs/razorback-implementation/_archive/pkg9-paper-reproduction-harness.md`.
- In-tree DAB adapter ported from
  `src/razorback/benchmarks/dab/{prepare,verify,reset,aggregate}.py`
  (Phase 1 leaves this unchanged; Phase 2 ports its logic into
  the sibling package).

**Phase 1 inputs (do not duplicate).**

- `rk run` Phase 1 wrapper translates razorback spec blocks into
  `harbor JobConfig` with `AgentConfig.import_path` populated and
  `tasks:` paths pointed at harbor-shaped task dirs. Phase 2 adds
  a new `benchmark: harbor_dab` block variant; Phase 1's
  translator extends to recognize it and resolve it to the
  sibling-plugin's emitted task tree.
- The in-tree DAB adapter at `src/razorback/benchmarks/dab/`
  stays untouched and continues to back `benchmark: dab` (now
  re-labelled `benchmark: in_tree_dab` for clarity in test specs;
  see AC-7 below).
- The walking-skeleton acceptance command from Phase 1 AC-1
  (`uv run rk run examples/specs/bookreview-claude.frozen.yaml`)
  is the canary; Phase 2 adds a second spec variant pointed at
  the new adapter and both must produce a run-dir.

**Cross-repo coordination.** `packages/razorback-plugin-dab/` is a
new top-level directory under the razorback repo. uv workspace
members are declared in the top-level `pyproject.toml` under
`[tool.uv.workspace.members]`. The plugin is **a separate
distributable wheel**, not a subpackage of razorback. Razorback
core does not import from it at runtime; razorback's spec format
gains a new benchmark-block kind (`harbor_dab`) that references
the plugin only by command-line invocation (`uv run
razorback-plugin-dab generate …`) inside `rk run`'s translator.

**AC ↔ task map (1:1).**

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-1 walking skeleton on both `in_tree_dab` and `harbor_dab` | §2 (architecture), §3.2 (`rk run`), §7 (run-dir contract) | Tasks 1, 2, 3, 14 |
| AC-2 sibling package builds + installs into razorback's venv | §2 (architecture), §4.5 (registration), AC-0.2 probe (adapter contract) | Tasks 1, 2, 4 |
| AC-3 all 12 DAB datasets ported as harbor task definitions | §2 (architecture), §7 (run-dir contract) | Tasks 5, 6, 7, 8 |
| AC-4 live-DB mode confirmed by trajectory evidence | §6.5 (per_trial_state_reset.compose_services), §9.4 (leak guard), also archived PKG-3 §AC-1 through §AC-5 | Tasks 7, 8, 14 |
| AC-5 live-DB baseline committed and promoted | §3.2 (`rk score --against-constant`) | Task 15 |
| AC-6 expected-shift bands pre-registered | Captain methodology guardrail (NOT in spec; recorded in baseline doc) | Task 12 (pre-run); Task 15 (post-run reconciliation) |
| AC-7 in-tree adapter still functional | §2 (architecture, sibling packaging) | Tasks 3, 14 |
| AC-8 cross-dataset aggregation contract honored | §3.2 (`rk score`), §8.3a (stratified Wilson) | Tasks 9, 10, 14 |
| AC-9 dataset hydration semantics named and honored | §2 (architecture), captain methodology guardrail | Tasks 6, 11, 13 |

**Riskiest contract first.** Two contracts must be locked before any
of the 12-dataset port lands:

1. **Plugin discoverability** (AC-2). Until harbor will accept the
   emitted task directories from a pip-installed sibling package,
   the rest of the work is unverifiable. **Task 1 builds the
   smallest possible plugin skeleton (one fixture task, no DAB
   data) and gets `harbor run` to execute it end-to-end.** Per
   CL's "Validating new mechanisms" rule and per the AC-0.2 probe
   methodology (a one-task `ProbeAgent` to validate dispatch
   shape before the real agent lands).
2. **Live-DB compose-stack reachability** (AC-4). The bookreview
   task's `db_config.yaml` declares both postgres and sqlite
   clients; until a containerized agent can `psql --host
   dab-postgres` from inside the trial environment, the 12-dataset
   matrix is unrunnable. **Task 7 spins up the compose stack
   against bookreview alone (smallest dataset by query count,
   first in the AC-9 hydration validator) BEFORE porting the
   other 11.** Per CL's mechanism-validation discipline:
   integration-level riskiest path goes first, comprehensive runs
   after.

**AC-9 hydration decision.**

The plan chooses **option (b) enforced prereq with a clean
missing-dataset error message at adapter-invocation time.** Trade-offs
considered:

| Option | Pros | Cons |
|---|---|---|
| (a) auto-hydrate on first use | zero-friction operator experience | mixes data acquisition with task generation; LFS pull is a slow operation that should be observable as its own step; failures during hydration are hard to disambiguate from generation failures |
| (b) enforced prereq with clean error | single responsibility (adapter only generates; operator runs `git lfs pull` themselves); fail-fast with a documented fix message; matches upstream DAB's setup.sh discipline (line 84) | one extra manual step for first-time operators |
| (c) hybrid (cache check + lazy pull) | combines (a)'s friction-free path with a fast-path skip | adds a cache-state machine that must be tested; doubles the surface for "did hydration happen?" debugging |

**Why (b).** The pre-registered shift-band methodology (AC-6) and
the live-DB compose stack (AC-4) already impose a careful operator
workflow. Adding auto-hydration would make first-run timing
unpredictable (LFS pulls take 1-5 minutes on first checkout)
without removing the failure mode where the operator forgets to
hydrate before a 12-dataset matrix run. A clean missing-dataset
error message that names the fix (`run: cd /path/to/dataagentbench/data && git lfs pull`)
gives the operator the same information at the same point in time
as a successful auto-pull, without conflating responsibilities.
The validator deletes the cached dataset, observes the error
message, runs `git lfs pull`, and re-runs (per AC-9's text).

**Implementation contract for AC-9.** The plugin's `generate`
command performs a pre-flight check on the configured
`data_root`: for each requested dataset, it verifies that
`query_dataset/` (or each `sql_file:` named in `db_config.yaml`)
points at a real file with non-pointer content (LFS pointer files
are 130-150 bytes of `version https://git-lfs.github.com/spec/v1`
text). If any pointer file is detected, the plugin exits with
exit code 2 and a stderr message of the exact form:

```
razorback-plugin-dab: dataset <name> not hydrated, found LFS pointer at <path>.
Hydrate with:
  cd <data_root> && git lfs pull
```

The validator in Task 13 confirms this exact behavior.

**Working agreements.**

- Repo layout: new `packages/razorback-plugin-dab/` directory
  with its own `pyproject.toml`, `src/razorback_plugin_dab/`,
  `tests/`. The package is named `razorback-plugin-dab` (PyPI
  shape) and exposes the Python module `razorback_plugin_dab`.
- All Python source files start with the `ABOUTME:` two-line
  comment header (per CL's global rules).
- macOS+Colima only mounts `/Users/<user>/` into the docker VM.
  Generated task dirs and run-dirs MUST land under `/Users/...`.
  Tests reuse the v1 `colima_safe_tmp_path` fixture.
- TDD: every behavior task writes the failing test first, runs
  it red, then makes it green, then commits.
- Commits: one focused commit per task. Format:
  `phase2: <short summary>`. Plan-doc edits (this file) carry
  `phase2 plan: <short summary>`.

---

## File structure

Files created or modified by this plan. Existing files (from
Phase 1) marked `[existing]`.

```
pyproject.toml                                            [existing: extend uv workspace members]
packages/                                                 [new]
└── razorback-plugin-dab/
    ├── pyproject.toml                                    [new]: wheel-buildable; entry-point: razorback-plugin-dab
    ├── README.md                                         [new]: operator-facing usage + AC-9 hydration prereq
    ├── src/
    │   └── razorback_plugin_dab/
    │       ├── __init__.py                               [new]
    │       ├── __main__.py                               [new]: `python -m razorback_plugin_dab`
    │       ├── cli.py                                    [new]: Typer commands: generate, list, validate
    │       ├── datasets.py                               [new]: DAB_DATASETS catalog (12 datasets)
    │       ├── hydration.py                              [new]: LFS-pointer check + missing-dataset error (AC-9)
    │       ├── generate/
    │       │   ├── __init__.py                           [new]
    │       │   ├── prepare.py                            [new]: per-(dataset, query) task-dir materializer
    │       │   ├── compose.py                            [new]: multi-service compose generator (postgres/mongo/agent)
    │       │   ├── workspace_readme.py                   [new]: 3 README variants (direct-minimal/structured/spacedock)
    │       │   ├── tools_denied.py                       [new]: verbatim DISALLOWED_TOOLS list
    │       │   └── stratum.py                            [new]: per-trial stratum metadata emitter
    │       └── verify/
    │           ├── __init__.py                           [new]
    │           └── verify.py                             [new]: in-container reward emitter (ported from in-tree)
    └── tests/
        ├── unit/
        │   ├── test_datasets_catalog.py                  [new] AC-3 (12 datasets)
        │   ├── test_hydration_check.py                   [new] AC-9 (LFS-pointer detection + error message)
        │   ├── test_prepare_per_query.py                 [new] AC-3 (task-dir shape)
        │   ├── test_compose_postgres.py                  [new] AC-4 (postgres-only fixture)
        │   ├── test_compose_mongo.py                     [new] AC-4 (mongo-only fixture)
        │   ├── test_compose_hybrid.py                    [new] AC-4 (postgres + mongo + agent)
        │   ├── test_workspace_readme_variants.py         [new] PKG-9 carry-forward; per-variant content
        │   ├── test_tools_denied_verbatim.py             [new] PKG-9 carry-forward; DISALLOWED_TOOLS verbatim
        │   ├── test_stratum_tagging.py                   [new] AC-8 stratum metadata shape
        │   └── test_verify_reward_shape.py               [new] in-tree carry-forward; reward shape
        ├── integration/
        │   ├── test_harbor_consumes_emitted_tasks.py     [new] AC-2 (fixture task → harbor run)
        │   ├── test_bookreview_live_db.py                [new] AC-4 (bookreview live-DB compose end-to-end)
        │   └── test_score_consumes_stratum.py            [new] AC-8 (rk score against fixture run-dir)
        └── fixtures/
            ├── synthetic_db_config_postgres.yaml         [new]
            ├── synthetic_db_config_mongo.yaml            [new]
            ├── synthetic_db_config_hybrid.yaml           [new]
            ├── lfs_pointer_file.txt                      [new] AC-9 (130-byte pointer fixture)
            └── stratum_run_dir/                          [new] AC-8 fixture run-dir
                ├── trials/.../summary.json
                └── spec.frozen.yaml
examples/
├── specs/
│   ├── bookreview-claude-in-tree-dab.frozen.yaml         [new] AC-1, AC-7
│   ├── bookreview-claude-harbor-dab.frozen.yaml          [new] AC-1, AC-4
│   └── dab-claude-harbor-adapter.frozen.yaml             [new] AC-5 (12-dataset matrix, N=1)
src/razorback/
└── spec/
    └── schema.py                                         [existing: extend with HarborDabBenchmarkBlock]
docs/superpowers/plans/
└── 2026-05-19-reconciliation-baseline.md                 [existing: extend with pre-registration table + new headline]
```

---

## Task 0: Pre-flight: confirm Phase 1 surfaces and DAB data root

**Files:** none.

- [ ] **Step 1: Verify environment matches Phase 1's expectations**

```bash
cd /Users/clkao/git/razorback
uv --version
docker info | head -3
.venv/bin/python -c "import harbor; print(harbor.__version__)"
ls /Users/clkao/git/dataagentbench/data/ | grep -c '^query_'
```

Expected: `uv` reports a version; docker info succeeds (Colima up);
harbor version matches Phase 1's pin; the dataset count is exactly
**12**.

- [ ] **Step 2: Confirm Phase 1 ships on `main`**

```bash
git log --oneline -1 -- src/razorback/run.py
git log --oneline -1 -- src/razorback/spec/schema.py
```

Each must show a `phase1:` commit (or, before Phase 1 merges, a
plan/intermediate worktree commit). If Phase 1 has not yet landed,
Task 1 can still start (the plugin scaffold is independent), but
Task 14 (end-to-end `rk run`) blocks on Phase 1.

- [ ] **Step 3: No commit. This is a check, not a change.**

---

## Task 1: Sibling package skeleton + uv-workspace registration

**ACs:** AC-2 (riskiest contract first, package builds + harbor
finds the emitted task tree).

**Files:**

- `pyproject.toml` (existing, extend `[tool.uv.workspace]`).
- `packages/razorback-plugin-dab/pyproject.toml` (new).
- `packages/razorback-plugin-dab/README.md` (new).
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/{__init__,__main__,cli}.py`
  (new, minimal Typer skeleton with one `generate --datasets
  hello-fixture --out <dir>` command that writes a single
  harbor-shaped task dir under `<dir>/hello-fixture/`).
- `packages/razorback-plugin-dab/tests/integration/test_harbor_consumes_emitted_tasks.py`
  (new).

- [ ] **Step 1: Failing test, package builds, installs, and harbor
  runs an emitted task.**

The test fixture spawns `uv build` inside the package, installs the
wheel into a throwaway venv, runs `uv run razorback-plugin-dab
generate --datasets hello-fixture --out <tmp>`, then constructs a
minimal harbor `JobConfig` with `tasks: [{path: <tmp>/hello-fixture}]`
and one `agents: [{name: nop}]`, invokes `harbor run` against it,
and asserts the resulting trial completes with exit 0.

The test is expected to fail because the package does not exist yet.

- [ ] **Step 2: Build the smallest package that passes.**

- `[project] name = "razorback-plugin-dab"`, scripts entry
  `razorback-plugin-dab = "razorback_plugin_dab.cli:app"`.
- `cli.py` ships ONE command: `generate` with `--datasets` and
  `--out`. For `--datasets hello-fixture` it writes a tiny
  harbor-shaped task dir (single-step, nop-friendly, no DAB data).
- `pyproject.toml` workspace registration in the top-level
  razorback `pyproject.toml` adds the package as a workspace
  member; `uv sync` installs both packages into the same venv.

- [ ] **Step 3: Run the test green.**

- [ ] **Step 4: Commit.** `phase2: scaffold razorback-plugin-dab
  sibling package + uv-workspace registration`.

**Why this comes before everything else.** AC-0.2's adapter-dispatch
verdict was "harbor consumes task directories on disk, not a
runtime entry-point". This task verifies that contract one more
time against razorback's actual sibling-package shape (not the
`/tmp/razorback-probe-agent/` shape the probe used). If harbor's
consumption shape has drifted since the AC-0.2 probe, every
downstream task changes; finding out here costs minutes.

---

## Task 2: `HarborDabBenchmarkBlock` in razorback's spec schema

**ACs:** AC-1, AC-2.

**Files:**

- `src/razorback/spec/schema.py` (existing, extend).
- `tests/unit/test_spec_harbor_dab_block.py` (new).

- [ ] **Step 1: Failing test, spec parser accepts a new benchmark
  variant.**

```yaml
benchmark:
  kind: harbor_dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets: [bookreview]
  workspace_variant: direct-minimal           # PKG-9 carry-forward
  hints: false                                # PKG-9 carry-forward
```

The test asserts: the spec parses without error; the resulting
block has `.kind == "harbor_dab"`; `workspace_variant` defaults to
`direct-minimal` if omitted; `hints` defaults to `False`; invalid
`workspace_variant` values raise `SpecError`.

- [ ] **Step 2: Extend the existing `BenchmarkBlock` discriminated
  union with `HarborDabBenchmarkBlock`.**

Fields:

- `kind: const "harbor_dab"`
- `data_root: Path` (must exist at freeze time)
- `datasets: list[str]` (one or more dataset names; validated
  against the 12-name catalog in Task 5)
- `workspace_variant: Literal["direct-minimal", "direct-structured", "spacedock"] = "direct-minimal"`
- `hints: bool = False`

- [ ] **Step 3: Re-label the existing block.** Rename `kind: dab`
  to `kind: in_tree_dab` in the schema, parser, and translator. v1
  specs that read `kind: dab` continue to parse via a one-line
  alias in the parser (no behavior change). Update three example
  specs (`bookreview-nop.yaml`, `bookreview-claude.yaml`,
  `dab-dev-claude.yaml`) to use the new label.

- [ ] **Step 4: Run the test green.**

- [ ] **Step 5: Commit.** `phase2: add HarborDabBenchmarkBlock spec
  variant + rename dab → in_tree_dab`.

---

## Task 3: `rk run` translator: `harbor_dab` → plugin-emitted task tree

**ACs:** AC-1, AC-2, AC-7.

**Files:**

- `src/razorback/run.py` or Phase 1's translator module
  (existing, extend).
- `tests/unit/test_translator_harbor_dab.py` (new).
- `tests/unit/test_translator_in_tree_dab.py` (existing, assert
  no regression).
- `examples/specs/bookreview-claude-in-tree-dab.frozen.yaml` (new).
- `examples/specs/bookreview-claude-harbor-dab.frozen.yaml` (new).

- [ ] **Step 1: Failing tests for both `in_tree_dab` and
  `harbor_dab` translation paths.**

For `harbor_dab`: the translator invokes the plugin via subprocess
(`uv run razorback-plugin-dab generate --datasets bookreview
--data-root <…> --workspace-variant direct-minimal --out
<tmp>/dab-tasks`), then constructs a harbor `JobConfig` whose
`tasks:` is a list of `TaskConfig(path=<tmp>/dab-tasks/bookreview-q1)`
entries, one per emitted task dir. The test mocks subprocess to
avoid invoking the plugin and asserts the constructed `JobConfig`'s
`tasks[].path` is the expected list.

For `in_tree_dab`: the existing translator path continues to
produce the v1-shaped `JobConfig`. The test pins this behavior so
AC-7 (in-tree adapter unchanged) is enforced by a regression test,
not by inspection.

- [ ] **Step 2: Extend the translator.** When `benchmark.kind ==
  "harbor_dab"`, invoke the plugin as a subprocess, collect the
  emitted task-dir paths, build `tasks: [TaskConfig(path=p) for p
  in emitted_paths]`. When `benchmark.kind == "in_tree_dab"`, the
  Phase 1 path is unchanged.

- [ ] **Step 3: Author the two frozen-spec examples.** Both target
  the bookreview dataset. The `in_tree_dab` spec is the existing
  Phase 1 acceptance command's spec, renamed; the `harbor_dab` spec
  uses the new block shape.

- [ ] **Step 4: Run all translator tests green.**

- [ ] **Step 5: Commit.** `phase2: rk run translator dispatches
  harbor_dab to sibling plugin`.

---

## Task 4: `razorback-plugin-dab` CLI surface

**ACs:** AC-2.

**Files:**

- `packages/razorback-plugin-dab/src/razorback_plugin_dab/cli.py`
  (existing, extend).
- `packages/razorback-plugin-dab/tests/unit/test_cli_surface.py` (new).

- [ ] **Step 1: Failing test, three commands exposed.**

Asserts the plugin's CLI has exactly three commands at `--help`:

- `generate`, emit task dirs for one or more datasets.
- `list`, print the 12-dataset catalog as JSON
  (machine-readable; consumed by `rk run` for spec validation).
- `validate`, read an emitted task tree and check its schema
  (the local-discovery equivalent of `harbor adapter list` cited
  in AC-3).

- [ ] **Step 2: Implement the three Typer commands** with no
  business logic beyond what Task 1 has, generate emits the
  hello-fixture, list prints `[{"name": "bookreview", ...}, ...]`
  with the 12-name catalog stubbed (Task 5 fills the real
  metadata), validate runs harbor's task-schema validator
  (importable from harbor as a library function; if not
  importable, validate runs `harbor adapter review <path>` as a
  subprocess).

- [ ] **Step 3: Run the test green.**

- [ ] **Step 4: Commit.** `phase2: razorback-plugin-dab CLI surface
  (generate / list / validate)`.

---

## Task 5: 12-dataset catalog + per-dataset metadata

**ACs:** AC-3.

**Files:**

- `packages/razorback-plugin-dab/src/razorback_plugin_dab/datasets.py` (new).
- `packages/razorback-plugin-dab/tests/unit/test_datasets_catalog.py` (new).

- [ ] **Step 1: Failing test, catalog enumerates 12 datasets with
  the expected metadata.**

```python
def test_catalog_size_and_names():
    catalog = DAB_DATASETS
    assert len(catalog) == 12
    assert {d.name for d in catalog} == {
        "agnews", "bookreview", "crmarenapro", "DEPS_DEV_V1",
        "GITHUB_REPOS", "googlelocal", "music_brainz_20k",
        "PANCANCER_ATLAS", "PATENTS", "stockindex", "stockmarket",
        "yelp",
    }

def test_per_dataset_backend_kinds():
    # Each dataset declares one or more of: postgres, mongo, sqlite.
    for d in DAB_DATASETS:
        assert d.backends, f"{d.name} has no backend declared"
        assert set(d.backends).issubset({"postgres", "mongo", "sqlite"})
```

- [ ] **Step 2: Author the catalog.** Each entry:

```python
DAB_DATASETS = [
    DabDataset(
        name="bookreview",
        backends=["postgres", "sqlite"],     # from db_config.yaml
        query_count=3,
    ),
    # … 11 more
]
```

The catalog is derived from inspecting
`/Users/clkao/git/dataagentbench/data/query_<name>/db_config.yaml`
under the local checkout. The per-dataset query count is verified
against `ls /Users/clkao/git/dataagentbench/data/query_<name>/ |
grep -c '^query[0-9]'` (one-shot recorded in the test's docstring,
not run at test time, since the upstream layout is stable).

- [ ] **Step 3: Run the test green.**

- [ ] **Step 4: Commit.** `phase2: DAB 12-dataset catalog (name,
  backends, query_count)`.

---

## Task 6: Hydration check (AC-9)

**ACs:** AC-9.

**Files:**

- `packages/razorback-plugin-dab/src/razorback_plugin_dab/hydration.py` (new).
- `packages/razorback-plugin-dab/tests/unit/test_hydration_check.py` (new).
- `packages/razorback-plugin-dab/tests/fixtures/lfs_pointer_file.txt` (new).

- [ ] **Step 1: Failing test, `check_hydrated(data_root,
  dataset_name)` distinguishes pointer files from real files.**

Two cases:

- LFS-pointer fixture in place of `books_info.sql` → raises
  `DatasetNotHydratedError` whose message contains the exact text
  ``razorback-plugin-dab: dataset bookreview not hydrated, found
  LFS pointer at <path>.`` and a follow-up line ``Hydrate with: …``.
- Real binary content in place of `books_info.sql` (the fixture
  copies a non-pointer file of ≥1KB) → returns silently.

- [ ] **Step 2: Implement `check_hydrated`.** Reads
  `<data_root>/query_<name>/db_config.yaml`, enumerates each
  `sql_file:`, `db_path:`, and `query_dataset/` reference, and
  for each file path checks the first 200 bytes for the LFS
  pointer marker (`version https://git-lfs.github.com/spec/v1`).
  If any pointer is detected, raises with exit code 2.

- [ ] **Step 3: Wire the check into `cli.py::generate`.** Before
  any task-dir materialization, run `check_hydrated` for every
  requested dataset; fail fast with the documented error.

- [ ] **Step 4: Run the test green.**

- [ ] **Step 5: Commit.** `phase2: AC-9 hydration check ,
  enforced-prereq with clean missing-dataset error`.

---

## Task 7: Live-DB compose-stack generator (postgres / mongo / hybrid)

**ACs:** AC-4. Inherits AC-1, AC-2, AC-3, AC-4 from archived PKG-3.

**Files:**

- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py` (new).
- Three unit tests:
  - `test_compose_postgres.py` (new), bookreview shape, postgres
    + sqlite-as-bind-mount → compose declares `dab-postgres` with
    `postgres:17` and the agent on a shared `dab-net`.
  - `test_compose_mongo.py` (new), a mongo-backed dataset →
    `dab-mongo` with `mongo:8`.
  - `test_compose_hybrid.py` (new), postgres + mongo + agent
    triple.

- [ ] **Step 1: Failing tests for the three fixture shapes.** Each
  test feeds a synthetic `db_config.yaml` to
  `generate_compose(...)` and asserts the resulting
  `docker-compose.yaml` text contains:
  - `services.main` (the agent container).
  - For postgres-backed datasets: `services.dab-postgres` with
    `image: postgres:17`, `POSTGRES_DB`, `POSTGRES_USER`, and a
    healthcheck (`pg_isready`).
  - For mongo-backed datasets: `services.dab-mongo` with
    `image: mongo:8` and a healthcheck (`mongosh --eval
    'db.runCommand({ping:1})'`).
  - `networks.dab-net` declared and joined by every service.
  - Dump-file loading via `docker-entrypoint-initdb.d/` bind mounts.

- [ ] **Step 2: Implement `generate_compose(db_config, dataset_name,
  data_root) -> str`.** This is the surviving body of the archived
  PKG-3 plan (its §AC-1 + §AC-2). Port the logic, do NOT re-derive
  the design.

- [ ] **Step 3: Integration test, bookreview live-DB stack spins
  up and `psql --host dab-postgres -c 'SELECT 1'` works from the
  agent container.** This is the riskiest-contract gate; without
  this, the comparison run (Task 15) is unverifiable. The
  integration test:
  1. Generates the bookreview task tree via `generate`.
  2. Invokes `docker compose up -d` on the emitted compose file.
  3. Waits for healthchecks.
  4. `docker exec dab-bookreview-q1-main psql --host dab-postgres
     -U dabench -c 'SELECT 1' bookreview_db` exits 0.
  5. Tears down.

- [ ] **Step 4: Run the tests green.**

- [ ] **Step 5: Commit.** `phase2: live-DB compose generator
  (postgres + mongo), bookreview reachability verified`.

---

## Task 8: Per-(dataset, query) task-dir materializer

**ACs:** AC-3, AC-4 (carries compose into per-task env config).

**Files:**

- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py` (new).
- `packages/razorback-plugin-dab/tests/unit/test_prepare_per_query.py` (new).

- [ ] **Step 1: Failing test, `prepare_dataset_tasks(data_root,
  dataset, out_dir, workspace_variant, hints)` produces the
  expected file tree for bookreview.**

Asserted shape per query (e.g., `<out>/bookreview-q1/`):

```
bookreview-q1/
├── task.toml            # harbor schema 1.2; [environment].docker_compose: docker-compose.yaml
├── docker-compose.yaml  # from Task 7
├── instruction.md
├── environment/
│   ├── Dockerfile       # placeholder (unused, image set in task.toml)
│   └── settings.json    # PreToolUse hooks (Task 10)
├── tests/
│   ├── verify.py        # ported from in-tree
│   ├── validate.py      # copied from data_root/query_<dataset>/query<N>/validate.py
│   └── test.sh
└── steps/
    └── main/
        ├── instruction.md
        └── workdir/
            ├── README.md            # workspace-variant content (Task 9)
            ├── query.json
            ├── db_config.yaml
            ├── db_description.txt
            ├── db_description_withhint.txt
            └── query_dataset/       # the safe parts only, no answer_key
```

The test asserts:
- `task.toml` schema_version 1.2 and declares `[environment].docker_compose`.
- `tests/validate.py` was copied from upstream's `query<N>/validate.py`.
- `workdir/` does NOT contain `ground_truth.csv` or
  `validate.py` (AC-2 from the in-tree adapter, ported verbatim).
- `workdir/` does NOT contain any LFS-pointer file (the
  hydration check in Task 6 would have failed earlier, but the
  prepare path enforces it again as belt-and-braces).

- [ ] **Step 2: Implement the materializer.** Port the in-tree
  `src/razorback/benchmarks/dab/prepare.py` logic into the
  sibling package, then add: compose-file emission (call into
  Task 7), workspace-variant README emission (call into Task 9),
  PreToolUse settings emission (call into Task 10), per-query
  stratum metadata injection (Task 11).

- [ ] **Step 3: Run the test green.**

- [ ] **Step 4: Commit.** `phase2: per-(dataset, query) task-dir
  materializer with compose + readme + tools_denied`.

---

## Task 9: Three workspace-README variants

**ACs:** AC-3 (per-task hook config); carries PKG-9 archived
content.

**Files:**

- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py` (new).
- `packages/razorback-plugin-dab/tests/unit/test_workspace_readme_variants.py` (new).

- [ ] **Step 1: Failing tests, three variants produce the
  paper-§3-prescribed structure.**

For one query (bookreview-q1), feed the prepare path each variant
and assert the generated `workdir/README.md` contains
variant-specific text:

- `direct-minimal`: terse task statement only (the query.json
  question + the output contract).
- `direct-structured`: task statement + canonical workspace layout
  description (paths to db_config.yaml, query_dataset/, etc.).
- `spacedock`: task + workspace + spacedock-solver framing prose
  (the "you are the first officer of …" preamble that points the
  spacedock skill at the workspace).

- [ ] **Step 2: Implement the three template-renderers.** The
  variant content cites paper §3 verbatim where the paper specifies
  the variant text. The spacedock framing prose is taken from
  razorback's existing solver-workflow README templates
  (`docs/templates/run-workflow/README.md` when Phase 5 lands;
  for Phase 2 ship, use the prose currently in the v1 in-tree
  spacedock spec at `examples/specs/bookreview-spacedock-seed.yaml`).

- [ ] **Step 3: Run the tests green.**

- [ ] **Step 4: Commit.** `phase2: workspace-readme variants
  (direct-minimal / direct-structured / spacedock)`.

---

## Task 10: `DISALLOWED_TOOLS` PreToolUse hook config

**ACs:** AC-3; carries PKG-9 archived content; Layer-2 leak guard
per spec §9.4.

**Files:**

- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/tools_denied.py` (new).
- `packages/razorback-plugin-dab/tests/unit/test_tools_denied_verbatim.py` (new).

- [ ] **Step 1: Failing test, the per-task `settings.json` carries
  the verbatim DISALLOWED_TOOLS list from upstream DAB.**

```python
def test_disallowed_tools_verbatim():
    settings = generate_settings_json("bookreview-q1")
    denials = settings["permissions"]["deny"]
    # Sourced verbatim from
    # /Users/clkao/git/dataagentbench/benchmark/run_experiment.py:1531-1549
    assert "Bash(pip install datasets*)" in denials
    assert "Bash(pip install dataagentbench*)" in denials
    assert "Bash(huggingface-cli login*)" in denials
    # … the full upstream list
```

- [ ] **Step 2: Implement.** Carry the upstream list verbatim into
  `tools_denied.py` as a `DISALLOWED_TOOLS: tuple[str, ...]` and
  emit it into each task-dir's `environment/settings.json`. Cite
  the upstream line range in the source-file comment.

- [ ] **Step 3: Run the test green.**

- [ ] **Step 4: Commit.** `phase2: DISALLOWED_TOOLS PreToolUse
  denylist (verbatim from upstream DAB run_experiment.py:1531-1549)`.

---

## Task 11: Per-trial stratum tagging (AC-8)

**ACs:** AC-8.

**Files:**

- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/stratum.py` (new).
- `packages/razorback-plugin-dab/tests/unit/test_stratum_tagging.py` (new).
- `packages/razorback-plugin-dab/tests/integration/test_score_consumes_stratum.py` (new).
- `packages/razorback-plugin-dab/tests/fixtures/stratum_run_dir/` (new).

- [ ] **Step 1: Failing test, per-trial stratum metadata in
  `summary.json`.**

The plugin emits per-task `stratum` metadata into a side-channel
file the harbor verifier copies into the trial's `summary.json`
(or into `agent/stratum.json`, depending on where Phase 1 fixed
the side-channel location). For bookreview, every trial carries:

```json
{
  "stratum": {
    "dataset": "bookreview",
    "query_id": 1,
    "backends": ["postgres", "sqlite"]
  }
}
```

The unit test asserts: `prepare_dataset_tasks` writes stratum
metadata for every emitted task; the metadata is read back as a
dict; the dict has the expected keys.

- [ ] **Step 2: Implement the stratum emitter.** A small JSON
  file `stratum.json` written into each task's
  `tests/` subtree; the verifier's `test.sh` copies it into
  `/logs/verifier/stratum.json` at trial end so it ends up in the
  trial's run-dir.

- [ ] **Step 3: Integration test, `rk score <fixture-run-dir>`
  computes per-stratum readout.** The fixture is a hand-built
  run-dir with three bookreview trials carrying stratum tags;
  `rk score` emits per-stratum Wilson CI per spec §3.2 / §8.3a.
  This is `rk score`'s side of the contract; Phase 2 ships only
  the producer (the adapter writes stratum tags). The integration
  test pins the producer↔consumer contract so a Phase 4a `rk
  score` change does not silently desync.

- [ ] **Step 4: Run the tests green.**

- [ ] **Step 5: Commit.** `phase2: per-trial stratum tagging ,
  rk score consumes via stratum.json`.

---

## Task 12: Pre-register expected-shift bands for all 12 datasets

**ACs:** AC-6.

**Files:**

- `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`
  (existing, extend).

This task ships BEFORE Tasks 13-15 (the comparison runs). Per
AC-6's verbatim text: "the baseline doc's pre-registration table
is committed in a commit that precedes the run-dir commit".

- [ ] **Step 1: Pre-register expected-shift band per dataset.**

Append a table to the baseline doc:

| Dataset | v1 dump-file score (pre-correction) | Expected direction (live-DB vs dump-file) | Expected magnitude | Reasoning |
|---|---|---|---|---|
| bookreview | <existing v1 cell> | ↓ (agent loses sqlite/file-grep shortcut) | -0.10 to -0.30 | bookreview's 1.000 v1 run almost certainly grepped books_info.sql per archived PKG-3 |
| agnews | … | … | … | … |
| … (12 rows total) | | | | |

For each dataset, the operator records the direction (`↑` /
`↓` / `≈`) and a rough magnitude band (`-0.30 to -0.10`,
`+0.05 to +0.20`, etc.). Reasoning cites the dataset's `db_config.yaml`
backend mix: postgres-heavy datasets expected to shift down (the
agent must learn live SQL); mongo-heavy datasets expected to
shift the same direction; mixed-backend datasets like bookreview
expected to shift down hardest.

- [ ] **Step 2: Acceptance criterion text.** Append to the same
  doc, immediately below the table:

> AC-6 acceptance criterion: observed shifts fall within the
> pre-registered direction; magnitudes fall within 2× of the
> predicted band. A reversed direction flags a real bug
> (mechanism failure, not statistical noise). Per-trial
> stratification with Wilson 95% CI from `rk score` is the
> readout shape.

- [ ] **Step 3: Commit.** `phase2 plan: pre-register expected-shift
  bands for 12 DAB datasets (AC-6)`.

**Important.** This commit precedes Tasks 13-15. The next run-dir
commit is the first opportunity for AC-6's pre-registration
ordering to be enforced.

---

## Task 13: AC-9 validator: missing-dataset error message

**ACs:** AC-9.

**Files:**

- `packages/razorback-plugin-dab/tests/integration/test_ac9_missing_dataset.py` (new).

- [ ] **Step 1: Failing test, fresh-checkout scenario raises the
  documented error.**

The test:
1. Creates a tmp DAB data root that contains ONLY the LFS pointer
   files for bookreview (the actual pointers are 130-150 byte
   files copied from a fresh `git clone` without `git lfs pull`).
2. Invokes `uv run razorback-plugin-dab generate --datasets
   bookreview --data-root <tmp> --out <out>`.
3. Asserts: exit code 2; stderr matches the regex
   `^razorback-plugin-dab: dataset bookreview not hydrated, found
   LFS pointer at .*\nHydrate with:\n  cd .* && git lfs pull\n$`.
4. Hydrates the tmp data root (`git lfs pull` within tmp).
5. Re-runs `generate`; asserts exit 0 and the expected task tree.

- [ ] **Step 2: Confirm the implementation in Task 6 passes the
  validator unchanged.** If it does not, fix Task 6 (do NOT add a
  second implementation); per CL's rule "if your first fix doesn't
  work, STOP and re-analyze rather than adding more fixes".

- [ ] **Step 3: Run the test green.**

- [ ] **Step 4: Commit.** `phase2: AC-9 validator ,
  enforced-prereq behavior under fresh-checkout scenario`.

---

## Task 14: End-to-end: `rk run` against both `in_tree_dab` and `harbor_dab` on bookreview

**ACs:** AC-1, AC-4, AC-7, AC-8.

**Files:**

- `tests/integration/test_rk_run_phase2_bookreview.py` (new).

- [ ] **Step 1: Failing tests, both spec variants produce a
  run-dir.**

Two invocations (sequential, share an env):

```bash
uv run rk run examples/specs/bookreview-claude-in-tree-dab.frozen.yaml
uv run rk run examples/specs/bookreview-claude-harbor-dab.frozen.yaml
```

The test asserts:

- Both exit 0.
- Both produce a run-dir under `/Users/.../jobs/...`.
- For `in_tree_dab`: the run matches Phase 1's recorded bookreview
  output byte-for-byte on the deterministic fixtures
  (AC-0.1(b)-grade comparison; AC-7 enforcement).
- For `harbor_dab`: `events.jsonl` contains either a `psql --host
  dab-postgres` invocation OR a `dab-postgres:5432` connection
  string (AC-4 enforcement). The grep is captured into the
  validation report.
- For `harbor_dab`: every trial in `summary.json` carries a
  `stratum: {dataset: bookreview, query_id: <n>, ...}` record
  (AC-8 enforcement).

- [ ] **Step 2: Make both invocations green.** This is the
  cost-bearing step: each `harbor_dab` run is ~$1-3 against Claude
  at bookreview's three queries. The `in_tree_dab` run is the
  same as Phase 1's; no incremental cost.

- [ ] **Step 3: Capture grep evidence into the validation
  report.** Write `docs/razorback-implementation/validation/phase2-bookreview-live-db.txt`
  with the `events.jsonl` grep output verbatim.

- [ ] **Step 4: Commit.** `phase2: end-to-end bookreview run via
  harbor-DAB adapter (AC-1, AC-4, AC-7, AC-8 confirmed)`.

---

## Task 15: Full 12-dataset matrix + baseline reconciliation

**ACs:** AC-5, AC-6.

**Files:**

- `examples/specs/dab-claude-harbor-adapter.frozen.yaml` (existing
  from Task 3; extended here).
- `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`
  (existing, extend with post-run section).

- [ ] **Step 1: Author the matrix spec.** All 12 datasets, N=1,
  `workspace_variant: direct-minimal`, hints OFF. Live-DB shape.

- [ ] **Step 2: Invoke the matrix run.**

```bash
uv run rk run examples/specs/dab-claude-harbor-adapter.frozen.yaml
```

Cost band: ~$30-60 at Claude (12 datasets × avg 4 queries × N=1).
The run is gated by Phase 1's `--max-budget-usd-running` flag set
to a conservative ceiling.

- [ ] **Step 3: Score the run.**

```bash
uv run rk score <run-dir> --format markdown
```

Captures: per-stratum (per-dataset) Wilson 95% CI; overall
stratified pass@1.

- [ ] **Step 4: Reconcile against pre-registered bands (AC-6).**

For each dataset, append a row to the baseline doc:

| Dataset | v1 dump-file | Pre-registered direction | Pre-registered magnitude | Observed v2 live-DB | Observed shift | Verdict |
|---|---|---|---|---|---|---|
| bookreview | … | ↓ | -0.10 to -0.30 | … | … | within band / out-of-band / reversed |

Verdict rule: `within band` if observed shift is in the
pre-registered direction AND within 2× the magnitude band;
`reversed` if direction is wrong (flag as bug, do not proceed
to AC-5 promotion until investigated); `out-of-band` if direction
is right but magnitude is more than 2× off (investigation; do
proceed to AC-5 with a note).

- [ ] **Step 5: Append headline + per-dataset breakdown (AC-5).**

The reconciliation-baseline doc's AC-0.1(a) v1 dump-file section
is retroactively marked as "pre-correction reference" with a
linked methodological-taint explanation (archived PKG-3's
"Methodological implication for M5's 0.6746 result" section
content, ported verbatim under attribution).

The new Phase 2 live-DB headline becomes the canonical anchor for
Phase 3+ comparisons. The doc states this transition explicitly.

- [ ] **Step 6: Commit.** `phase2: live-DB baseline promoted to
  canonical anchor, v1 dump-file marked pre-correction (AC-5,
  AC-6)`.

---

## TDD checkpoints summary

| Checkpoint | Test | First red | First green | Why this order |
|---|---|---|---|---|
| Plugin discoverability | `test_harbor_consumes_emitted_tasks.py` | Task 1 Step 1 | Task 1 Step 3 | Riskiest contract: if harbor doesn't accept the emitted task tree, every later task is wasted work. |
| Live-DB reachability | `test_bookreview_live_db.py` (Task 7 Step 3) | Task 7 Step 1 | Task 7 Step 4 | Riskiest integration: 11 datasets cannot be ported until one dataset proves the compose stack works. |
| AC-9 hydration semantics | `test_ac9_missing_dataset.py` | Task 13 Step 1 | Task 13 Step 3 | The chosen behavior (enforced prereq with clean error) is captain-flagged; the validator pins it before the comparison run depends on it. |
| AC-6 pre-registration ordering | Git log (the table commit precedes the run-dir commit) | Task 12 | Task 15 | Pre-registration is methodologically void if it lands after the data. Commit ordering is the enforcement. |
| Producer↔consumer contract for stratum | `test_score_consumes_stratum.py` | Task 11 Step 3 | Task 11 Step 4 | A Phase 4a `rk score` change must not silently desync from the adapter's stratum-tag shape. |

---

## Open questions (file as issues if they block any task)

1. **PKG-9 paper-reproduction hints corpus.** AC-9 of archived
   PKG-9 references `hints/{task}.md` files from upstream DAB. The
   local checkout at `/Users/clkao/git/dataagentbench/data/hints/`
   appears empty in the current snapshot. Tasks 2 and 9 carry the
   `hints: bool` spec field forward, but the hints-ON path is
   deferred until the upstream `hints/` corpus is locatable. This
   is OUT OF SCOPE for Phase 2's 9 ACs (none reference hints
   content); recorded here so a future PKG-9 plan can pick it up.

2. **`rk run`'s `--max-budget-usd-running` interaction with the
   12-dataset matrix.** Phase 4a's running-total file (spec §3.2,
   §8.1) is the budget gate the matrix dispatcher relies on. Task
   15 invokes the matrix via a single `rk run`; the running-total
   flag is a single value across the 12 datasets, not a per-dataset
   budget. If Phase 4a ships first, Task 15 uses its flag directly;
   if Phase 4a is not yet merged, Task 15 ships without the flag
   and relies on the operator's monitoring. Recorded as a
   dependency-ordering question, not a blocker.

3. **`harbor adapter list` vs local-discovery equivalent.** AC-3's
   verification command is "`harbor adapter list` (or
   local-discovery equivalent)". Per AC-0.2's probe, harbor has no
   adapter-registry runtime call, adapters are filesystem outputs
   consumed via `JobConfig.tasks[].path`. Task 4's
   `razorback-plugin-dab list` is the local-discovery equivalent
   AC-3 anticipates. No upstream-harbor work required.

---

## Acceptance command (matches AC-5 / AC-6 / AC-1 / AC-7)

After all tasks land:

```bash
# AC-1, AC-7, walking skeleton on both paths
uv run rk run examples/specs/bookreview-claude-in-tree-dab.frozen.yaml
uv run rk run examples/specs/bookreview-claude-harbor-dab.frozen.yaml

# AC-2, sibling wheel builds + installs
(cd packages/razorback-plugin-dab && uv build)
uv pip install packages/razorback-plugin-dab/dist/razorback_plugin_dab-*.whl

# AC-3, 12 datasets enumerated
uv run razorback-plugin-dab list | jq 'length == 12'

# AC-9, fresh-checkout missing-dataset error
rm -rf /tmp/dab-no-lfs && mkdir /tmp/dab-no-lfs
# … copy LFS pointer files only …
uv run razorback-plugin-dab generate --datasets bookreview \
    --data-root /tmp/dab-no-lfs --out /tmp/dab-out
# expected: exit 2; stderr matches AC-9's documented message

# AC-5 / AC-6, full 12-dataset matrix
uv run rk run examples/specs/dab-claude-harbor-adapter.frozen.yaml
# then: reconcile observed shifts against Task 12's pre-registration table.
```

`uv run pytest packages/razorback-plugin-dab/tests/` exits 0 across
both unit and integration test suites.
