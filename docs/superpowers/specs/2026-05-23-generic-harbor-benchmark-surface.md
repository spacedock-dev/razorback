# Generic harbor benchmark surface — collapse per-benchmark kinds

**Status:** Proposal, awaiting captain decision at validation gate.
**Source:** Captain directive 2026-05-23 — "if dabstep is already on
harbor, there should be just simple config, no additional
classes/plugin needed."
**Sibling spec:** `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
(v2 spec — architectural source of truth; this proposal amends §6.1
non-breakingly).
**Entity:** `docs/razorback-implementation/generic-harbor-benchmark-surface-design.md`.

## Abstract

Razorback's `spec.benchmark` discriminator carries one Pydantic class
per benchmark today: `LocalBenchmarkBlock`, `HarborDabBenchmarkBlock`,
`AdeBenchBenchmarkBlock`, `Spider2DbtBenchmarkBlock` (plus the legacy
SUPERSEDED `DabBenchmarkBlock`). Every new harbor-published benchmark
(dabstep, swe-bench-verified, terminal-bench-2, lawbench,
replicationbench, medagentbench, swe-bench-pro, ...) currently costs
three PRs of wiring even though its full task definition already lives
in Harbor's registry. The captain's framing — *"if dabstep is already
on harbor, there should be just simple config, no additional
classes/plugin needed"* — matches v2 spec §1.3 verbatim:
*"Razorback is not a benchmark library. ... Razorback ships no
benchmark adapters."*

This proposal adds a single generic `kind: harbor` block alongside
the existing per-benchmark kinds. The new block resolves any
Harbor-published dataset via the existing
`PackageDatasetClient` path and threads selector flags
(`--include-task-name`, `--exclude-task-name`, `--n-tasks`) through
to `harbor run`. Benchmarks that require razorback-side prep work
(today: only DAB, via the `razorback-plugin-dab generate` subprocess)
keep that prep through an optional `prep:` discriminator. New
harbor-published benchmarks become a one-line spec with zero
razorback code change. The existing per-benchmark blocks stay
untouched; the v2 spec §6.1 example YAML grows a sibling
`kind: harbor` paragraph rather than a breaking rewrite.

**Recommendation:** ship the generic block as a non-breaking
addition (option (b) — collapse-partial). See §11.

## §1 The current per-benchmark surface

Four active `BenchmarkBlock` discriminated-union members today
(`src/razorback/spec/schema.py:297-305`):

```python
BenchmarkBlock = Annotated[
    Union[
        LocalBenchmarkBlock,          # kind: local       (line 101-104)
        HarborDabBenchmarkBlock,      # kind: harbor_dab  (line 125-183)
        AdeBenchBenchmarkBlock,       # kind: ade-bench   (line 203-285)
        Spider2DbtBenchmarkBlock,     # kind: spider2-dbt (line 288-294)
    ],
    Field(discriminator="kind"),
]
```

Plus the legacy `DabBenchmarkBlock` at lines 107-122 — kept in the
module for `_legacy` imports but excluded from `BenchmarkBlock`
itself. The docstring reads *"Active specs no longer include this
class in `BenchmarkBlock`; use `benchmark.kind: harbor_dab`."* This
is the collapse precedent: razorback has already retired one
benchmark kind in favor of a sibling.

Four matching builders in `src/razorback/translate.py`:

- `_build_local` — line 193
- `_build_ade_bench` — line 211
- `_build_harbor_dab` — line 312
- `_build_spider2_dbt` — line 442

`_build_harbor_dab` is the only builder that does generative work:
it spawns `uv run razorback-plugin-dab generate ...` (lines 379-396)
to materialize per-query task directories under
`workspace_variant ∈ {direct-minimal, direct-structured, spacedock}`
× `query_mode ∈ {batch, per-query}`. `_build_ade_bench` is pure
config translation (resolve `<org>/<name>@<ref>` via
`PackageDatasetClient.download_dataset`, apply image overrides, emit
JobConfig). `_build_local` and `_build_spider2_dbt` just glob a local
`tasks_root` / `task_paths`.

**Per-new-benchmark cost.** Adding dabstep today costs:

1. A new `DabstepBenchmarkBlock` Pydantic class in `schema.py`
   with `kind: Literal["dabstep"]`, a `dataset:` field, optional
   selectors.
2. A new `_build_dabstep()` method in `translate.py` that wraps the
   same `PackageDatasetClient.download_dataset` call ADE already
   uses, threads selector flags through to JobConfig.
3. Optionally, a sibling `razorback-plugin-dabstep` package if any
   dabstep-specific prep is needed (none for dabstep itself — its
   `task.toml` already carries the full task definition).

The actual code added would be ~120 LOC, ~80 of it boilerplate. The
class plus builder pair would be near-identical to the
`AdeBenchBenchmarkBlock` + `_build_ade_bench` pair, minus the ADE-specific
`db_type` / `project_type` / `docker_image_override` / `batch_mode`
fields.

**Why this contradicts §1.3.** v2 spec §1.3 (lines 52-67) reads:

> Razorback is not a benchmark library. Benchmarks live in harbor's
> catalog as adapters publishable via `harbor publish`. Razorback
> ships no benchmark adapters.

A new Pydantic class + builder + plugin per harbor-published benchmark
IS shipping an adapter, just a thin one. The spec's intent is that
razorback be the orchestration layer and harbor own the per-benchmark
knowledge. The implementation has drifted from this intent through
incremental specialization.

## §2 What harbor already exposes

Harbor's CLI already accepts every selector razorback needs.
`harbor.cli.jobs.start()` (function defined at line 471 of
`.venv/lib/python3.12/site-packages/harbor/cli/jobs.py`) declares
the following dataset/task selectors in its parameter block at
lines 804-898:

| Flag | Lines | Purpose |
|---|---|---|
| `-p / --path` | 804-813 | Local task or dataset directory |
| `--task-git-url` | 814-821 | Git URL for a task repository |
| `--task-git-commit` | 822-830 | Git commit pin (paired with `--task-git-url`) |
| `-d / --dataset <name@version>` | 831-840 | Harbor-published dataset reference |
| `--registry-url` | 841-849 | Remote registry override |
| `--registry-path` | 850-858 | Local registry override |
| `-t / --task <org/name[@ref]>` | 859-868 | Single task from registry |
| `-i / --include-task-name <glob>` | 869-878 | Task subset selector (repeatable) |
| `-x / --exclude-task-name <glob>` | 879-888 | Task exclusion selector (repeatable) |
| `-l / --n-tasks <int>` | 889-898 | Task-count cap (applied after other filters) |

The `--dataset` flag's help text reads literally
*"Dataset name@version (e.g., 'dataset@1.0')"* (line 836). This is
the same surface the dabstep hub page recommends:
`harbor run -d adyen/dabstep`.

**Dataset manifest schema.** Harbor's `DatasetManifest`
(`.../harbor/models/dataset/manifest.py:153-279`) defines the
canonical TOML schema served by the registry:

```toml
schema_version = "1.0"

[dataset]
name = "org/name"           # required, org/name format
description = "..."
authors = [{name = "...", email = "..."}]
keywords = ["..."]

[[tasks]]
name = "org/task-name"      # required, org/name format
digest = "sha256:<64hex>"   # required, pins exact task version

[[files]]                   # optional dataset-level files
path = "metric.py"
digest = "sha256:<64hex>"   # auto-computed at publish time if omitted
```

Validated:
`DatasetManifest.model_fields.keys()` = `['schema_version',
'dataset', 'tasks', 'files']`. Content hash is sha256 over sorted
task digests + optional `path:digest` pairs joined with `;`
(`compute_content_hash`, lines 237-254).

Supporting types:

- `DatasetTaskRef` (name + sha256 digest, org/name validators) —
  lines 23-69.
- `DatasetFileRef` (path + digest) — lines 72-108.
- `DatasetInfo` (name/description/authors/keywords) — lines 111-150.

**Registry resolver.** `PackageDatasetClient`
(`.../harbor/registry/client/package.py:14-124`) takes an
`<org>/<name>[@<ref>]` and returns a `DatasetMetadata` carrying
`task_ids`, `dataset_version_id`, and `dataset_version_content_hash`:

- `_get_dataset_metadata(name)` — lines 19-60.
- `download_dataset_files()` — lines 62-91.
- `download_dataset()` — lines 93-121.

Validated:
`hasattr(PackageDatasetClient, "_get_dataset_metadata")` = `True`.

**Razorback's current handoff.** `src/razorback/cli/run.py:54-68`
`_invoke_harbor`:

```python
proc = subprocess.run(
    ["uv", "run", "harbor", "run", "-c", str(job_config_yaml)],
    env=env, capture_output=False,
)
```

Razorback emits a job-config YAML and passes it through `-c`. All
benchmark-specific knowledge is encoded INSIDE that YAML. If
razorback emitted a YAML that just declared `dataset:` and the
selector flags, harbor would do the rest.

**Dabstep download probe (plan stage, recorded verbatim from plan
worker's run):**

- Command: `uv run harbor download adyen/dabstep@latest -o /tmp/dabstep_probe --cache`
- Exit code: 0
- Wallclock: ~3s
- Auth: none required (public dataset, anonymous HTTPS)
- Materialized: 450 task directories under
  `/tmp/dabstep_probe/adyen/<task-id>/<sha256>/{task.toml,instruction.md}`
- Sample `task.toml` (verbatim, `adyen/1507`):
  ```toml
  version = "1.0"
  [task]
  name = "adyen/1507"
  authors = []
  keywords = []
  [metadata]
  author_name = ""
  author_email = ""
  difficulty = "hard"
  category = "data-analysis"
  tags = ["dabstep", "data-analysis", "financial", "hard"]
  [verifier]
  timeout_sec = 600.0
  [agent]
  timeout_sec = 1800.0
  [environment]
  build_timeout_sec = 600.0
  cpus = 1
  memory_mb = 4096
  storage_mb = 8192
  gpus = 0
  allow_internet = true
  mcp_servers = []
  [verifier.env]
  [solution.env]
  ```

**Material implication.** Dabstep's full task definition (image
specs, timeouts, prompt, verifier setup) lives in the downloaded
`task.toml` + `instruction.md`. Razorback's job is literally just to
pass `-d adyen/dabstep` (plus optional `-i` task subset and `-l`
n-tasks cap) through to harbor. Zero razorback-side prep. No
subprocess. No plugin. No per-task transform.

### Research-validation evidence (impl-stage re-confirmed)

Run before writing this doc, all four commands at expected output:

```
$ uv run python -c "import harbor; from importlib.metadata import version; print(version('harbor'))"
0.6.6

$ uv run python -c "from harbor.cli.jobs import start; print(start.__module__)"
harbor.cli.jobs

$ uv run python -c "from harbor.models.dataset.manifest import DatasetManifest; print(list(DatasetManifest.model_fields.keys()))"
['schema_version', 'dataset', 'tasks', 'files']

$ uv run python -c "from harbor.registry.client.package import PackageDatasetClient; print(hasattr(PackageDatasetClient, '_get_dataset_metadata'))"
True
```

Function line-number spot-check on pinned harbor==0.6.6:

```
$ grep -n "^def start\|^def resume" .venv/lib/python3.12/site-packages/harbor/cli/jobs.py
471:def start(
1362:def resume(

$ grep -n "\"--dataset\"\|\"--include-task-name\"\|\"--exclude-task-name\"\|\"--n-tasks\"" .venv/lib/python3.12/site-packages/harbor/cli/jobs.py
835:            "--dataset",
873:            "--include-task-name",
883:            "--exclude-task-name",
893:            "--n-tasks",
```

All line citations in this doc match the pinned harbor==0.6.6
source tree.

## §3 The two operational modes

Harbor-published benchmarks split into two classes from razorback's
perspective:

**Pure pass-through.** Razorback does nothing benchmark-specific.
It resolves the `<org>/<name>@<ref>` via `PackageDatasetClient`,
attaches optional task selectors, hands the JobConfig to harbor.
The task definition (image, prompts, verifier) is fully self-described
in the downloaded `task.toml`.

| Benchmark | Hub ref | Tasks | Notes |
|---|---|---|---|
| dabstep | `adyen/dabstep` | 450 | Captain's motivating example |
| swe-bench-verified | `swe-bench/swe-bench-verified` | 500 | Harbor parity table records `official 0.563 ± 0.000 vs Harbor 0.545 ± 0.007` against `mini-swe-agent` + GPT-5-mini, 499 comparable tasks |
| terminal-bench-2 | `terminal-bench/terminal-bench-2` | 89 | |
| lawbench | `lawbench/lawbench` | 1000 | |
| replicationbench | `replicationbench/replicationbench` | 90 | |
| medagentbench | `stanford/medagentbench` | 300 | |
| swe-bench-pro | `scale-ai/swe-bench-pro` | 731 | |
| ade-bench (when sourced as dataset ref) | `dbt-labs/ade-bench@latest` | varies | Already the `dataset:` path in `AdeBenchBenchmarkBlock` |

**Prep + pass-through.** Razorback runs a benchmark-specific
generator subprocess that materializes task directories before
handing them to harbor. The benchmark's task set is computed per-spec
(e.g., DAB's task set depends on `workspace_variant` × `query_mode`).

| Benchmark | Prep work |
|---|---|
| DAB (`razorback-plugin-dab`) | `uv run razorback-plugin-dab generate` emits per-query task dirs under chosen `workspace_variant` and `query_mode` |

**Genuinely-not-harbor.** Local task lists with no Harbor registry
involvement. These stay outside the generic block.

| Benchmark | Why local |
|---|---|
| `LocalBenchmarkBlock` | Raw `task_paths: list[Path]`. No dataset ref. Used for ad-hoc dev and test fixtures. |

**Local-but-Harbor-shaped.** Local-path directories that already
follow the `<task-id>/{task.toml, instruction.md}` layout Harbor
emits. Today: `AdeBenchBenchmarkBlock`'s `tasks_root:` mode (dev
escape hatch for working off a checked-out adapter repo) and
`Spider2DbtBenchmarkBlock`'s mandatory `tasks_root:`. These are
strictly local but use the same task shape; the generic block can
absorb them via a `tasks_root:` field.

## §4 Proposed `HarborBenchmarkBlock`

```python
class HarborBenchmarkBlock(BaseModel):
    """Generic Harbor-resolved benchmark block.

    Covers any benchmark whose tasks live in Harbor's registry
    (dataset ref) or as a local Harbor-shaped directory (tasks_root).
    Benchmarks that require razorback-side task generation set an
    optional `prep:` block; benchmarks that do not (the common case
    for harbor-published datasets) leave it None.
    """
    model_config = ConfigDict(extra="forbid")
    kind: Literal["harbor"]

    # Source selection — exactly one of dataset / tasks_root.
    dataset: str | None = None        # <org>/<name>@<ref> for registry resolution
    tasks_root: Path | None = None    # local Harbor-shaped task directory

    # Task selectors — pass through to `harbor run` flags 1:1.
    tasks: list[str] | None = None             # → -i / --include-task-name
    exclude_tasks: list[str] | None = None     # → -x / --exclude-task-name
    n_tasks: int | None = None                 # → -l / --n-tasks

    # Optional razorback-side prep hook (DAB today; future generative
    # benchmarks later). `prep: None` ⇒ pure pass-through path.
    prep: PrepBlock | None = None
```

The `prep:` discriminator covers benchmarks that need
razorback-side materialization:

```python
PrepBlock = Annotated[
    Union[DabPrep, ...],
    Field(discriminator="kind"),
]

class DabPrep(BaseModel):
    """DAB plugin prep — runs `razorback-plugin-dab generate` to
    materialize per-query task directories under the chosen workspace
    variant."""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["dab-plugin"]
    workspace_variant: Literal["direct-minimal", "direct-structured", "spacedock"] = "direct-minimal"
    data_root: Path | None = None
    hints: bool = False
    query_mode: Literal["batch", "per-query"] = "per-query"
```

The proposal's central claim: `prep: None` is the common path. New
harbor-published benchmarks (dabstep, swe-bench-verified, the seven
others enumerated in §3) all live here and need zero new razorback
code.

**Source-selection rule.** `dataset` and `tasks_root` are mutually
exclusive; at least one must be set. Modeled after
`AdeBenchBenchmarkBlock`'s existing validator
(`schema.py:239-285`) — the same constraint, lifted up.

**Validation rules** (model_validator):

- `dataset` follows the Harbor `<org>/<name>@<ref>` form. Reuse
  `harbor.models.package.reference.PackageReference.parse` for shape
  parity with `AdeBenchBenchmarkBlock`.
- `dataset` and `tasks_root` cannot both be set.
- If `tasks_root` is set, `tasks` must be a non-empty list (matches
  the existing `AdeBenchBenchmarkBlock` and
  `Spider2DbtBenchmarkBlock` rule).
- `prep` is optional and orthogonal to source selection (DAB-style
  generative benchmarks set both `dataset: <name>@<version>` AND
  `prep: {kind: dab-plugin, ...}`).

## §5 Before/after spec examples (verbatim)

### §5.1 — dabstep

**Today** (would require new code):

```yaml
# Requires: new DabstepBenchmarkBlock class in spec/schema.py +
# new _build_dabstep() in translate.py + (optionally) a
# razorback-plugin-dabstep package. Roughly 3 PRs of work to add
# a benchmark whose entire definition already lives on harbor.
benchmark:
  kind: dabstep              # ← NEW Pydantic class needed
  dataset: adyen/dabstep@latest
  tasks: [adyen/1507, adyen/2712]
```

**Under the proposal:**

```yaml
benchmark:
  kind: harbor
  dataset: adyen/dabstep@latest
  tasks: [adyen/1507, adyen/2712]   # optional subset
  n_tasks: 10                        # optional cap
```

Zero razorback code change. New harbor-published benchmark → one
spec, one line.

### §5.2 — swe-bench-verified

**Today:** would require the same triad as dabstep above
(`SweBenchVerifiedBenchmarkBlock` + `_build_swe_bench_verified` +
optional plugin).

**Under the proposal:**

```yaml
benchmark:
  kind: harbor
  dataset: swe-bench/swe-bench-verified@latest
  n_tasks: 50                        # impl-stage smoke subset
```

### §5.3 — DAB (the prep-mode case, before/after)

**Today:**

```yaml
benchmark:
  kind: harbor_dab
  dataset: dab@1.0
  datasets: [bookreview, agnews, crmarenapro]
  workspace_variant: direct-structured
  query_mode: per-query
```

**Under the proposal:**

```yaml
benchmark:
  kind: harbor
  dataset: dab@1.0
  prep:
    kind: dab-plugin
    workspace_variant: direct-structured
    query_mode: per-query
  tasks: [bookreview, agnews, crmarenapro]  # subset selector,
                                             # same `-i` semantics
```

The DAB plugin's existing per-query materialization stays — the
plugin subprocess is invoked through the `prep:` dispatch
(implementation detail of `_build_harbor`).

## §6 Migration shape

Each existing block has a 1:1 representation in the generic block:

- **`kind: harbor_dab`** ⇒ `kind: harbor` + `dataset: dab@1.0` +
  `prep: {kind: dab-plugin, workspace_variant: ..., query_mode: ...,
  hints: ..., data_root: ...}` + `tasks: [...]` (from the old
  `datasets:` field — renamed for selector parity).

- **`kind: ade-bench, dataset: <org>/<name>@<ref>`** ⇒
  `kind: harbor` + `dataset: <org>/<name>@<ref>` + `tasks: [...]`
  (no prep). The fields `db_type` / `project_type` /
  `docker_image_override` / `batch_mode` move EITHER into a thin
  `AdeBenchPrep` block IF they're load-bearing for ADE's harbor
  adapter, OR drop entirely if they're vestigial. **Captain decision
  needed** — the FO's grounded research did not assert whether ADE's
  harbor adapter consumes these fields at run time. The validator
  for this proposal should flag the open question rather than
  guess.

- **`kind: ade-bench, tasks_root: <path>`** ⇒ `kind: harbor` +
  `tasks_root: <path>` + `tasks: [...]` (no prep — `tasks_root`
  mode is pure local pass-through).

- **`kind: spider2-dbt`** ⇒ same shape as the ade-bench local path:
  `kind: harbor` + `tasks_root: <path>` + `tasks: [...]`. If
  `docker_image_override` / `batch_mode` are load-bearing, they
  migrate into a thin `Spider2DbtPrep` block; if not, drop. **Same
  captain decision needed.**

- **`kind: local`** KEEPS its own block. `LocalBenchmarkBlock`'s
  invocation surface (raw `task_paths: list[Path]`, no Harbor
  registry, no Harbor task-shape requirement) is genuinely different
  from the generic block. Collapsing it would force a Harbor-shaped
  directory layout on ad-hoc dev fixtures.

**Order of operations.** This proposal lands the generic block as
a non-breaking addition. The existing blocks stay unchanged.
Migration of `harbor_dab` / `ade-bench` / `spider2-dbt` to the
generic shape is a follow-on entity the captain greenlights
separately based on the chosen backwards-compat strategy in §8.

## §7 What `translate.py` looks like after collapse

A single `_build_harbor()` builder replaces three of the four current
builders (`_build_ade_bench`, `_build_harbor_dab`,
`_build_spider2_dbt`) once migration completes:

```python
def _build_harbor(block: HarborBenchmarkBlock, ...) -> JobConfig:
    # 1. Resolve source.
    if block.dataset is not None:
        metadata = PackageDatasetClient(...).download_dataset(
            block.dataset, output_dir=..., export=True,
        )
        resolved_task_dirs = metadata.task_ids   # PackageTaskId list
    else:
        resolved_task_dirs = _glob_local_tasks_root(block.tasks_root)

    # 2. Run prep hook if present (DAB today; future plugins later).
    if block.prep is not None:
        prep_runner = _PREP_REGISTRY[block.prep.kind]
        resolved_task_dirs = prep_runner.materialize(
            block.prep, resolved_task_dirs, output_dir=...,
        )

    # 3. Apply task-view materializer (already generic per spec §6.1).
    view_dir = materialize_task_views(
        resolved_task_dirs, benchmark_kind="harbor",
    )

    # 4. Build JobConfig threading selectors through to harbor flags.
    return JobConfig(
        tasks=[TaskConfig(path=p) for p in view_dir.iterdir()],
        # ...plus -i/-x/-l selectors as JobConfig fields
    )
```

The existing `_build_harbor_dab` body migrates into a `DabPrepRunner`
class registered under `_PREP_REGISTRY["dab-plugin"]`. The
`razorback-plugin-dab` package stays; only its entry point changes.

`_build_local` stays as-is alongside `_build_harbor` (the two
benchmark kinds that survive the collapse — local and harbor).

## §8 Backwards compat

Three options. The recommendation in §11 picks one.

**(a) Hard cutover.** Delete `kind: harbor_dab` / `kind: ade-bench` /
`kind: spider2-dbt` from `BenchmarkBlock`. All existing specs
rewrite to `kind: harbor`. Pro: schema is minimal; the spec's
"single kind" claim holds in code. Con: spec hash changes for every
frozen spec — at minimum the 12 direct-structured specs from
`7q-matrix`, plus every frozen DAB paper-repro spec. Each frozen
spec carries a `spec.frozen.yaml` + `provenance.yaml` pair under
its run-dir; re-freezing them ripples through validation evidence.

**(b) Coexist permanently.** New `kind: harbor` ships alongside
the existing kinds. The old kinds keep working forever; new
benchmarks use `kind: harbor`. Pro: zero ripple; frozen specs stay
valid; one PR ships the new surface. Con: schema doubles surface
area; future readers see two ways to express ADE-bench-with-dataset.
Mitigation: docstring on each old block points to `HarborBenchmarkBlock`
as the recommended surface for new specs; old kinds get a TODO/FIXME
header marking them "kept for backwards compat".

**(c) Aliases with deprecation window.** Keep
`HarborDabBenchmarkBlock` / `AdeBenchBenchmarkBlock` /
`Spider2DbtBenchmarkBlock` as Pydantic aliases that emit
`kind: harbor` + auto-populate `prep:` at parse time. Spec hash
stays stable (the alias resolves to the same canonical form). After
a deprecation window (measured in months), remove the aliases.
Pro: gradual, no ripple. Con: alias-time auto-population is subtle;
debugging "why is `prep:` populated when my spec didn't have it"
costs reader-context.

## §9 Razorback-side prep that survives the collapse

The following knowledge stays in razorback — it's solver-side or
materialization-side, not benchmark-identity:

- **DAB's `workspace_variant`** (`direct-minimal` / `direct-structured`
  / `spacedock`). Threaded via `DabPrep.workspace_variant`. This is
  a per-trial agent-configuration knob, not a property of the DAB
  benchmark.

- **DAB's `query_mode`** (`batch` / `per-query`). Threaded via
  `DabPrep.query_mode`. Materialization mode, not benchmark identity.

- **DAB's `hints` flag**. Threaded via `DabPrep.hints`. Experimental
  ablation, not benchmark identity.

- **ADE-bench's `db_type` / `project_type` /
  `docker_image_override` / `batch_mode`.** Captain-review needed.
  Possible outcomes:
  - Load-bearing (ADE's harbor adapter consumes them at run time)
    ⇒ thin `AdeBenchPrep` block carrying these four fields.
  - Vestigial (no longer used after the spec §3.x flag conversion
    work) ⇒ drop.
  - Mixed (some load-bearing, some not) ⇒ thin `AdeBenchPrep` block
    carrying only the load-bearing ones.

- **Spider2-dbt's `docker_image_override` / `batch_mode`.** Same
  captain-review treatment as ADE-bench.

- **The task-view materializer** (`src/razorback/harbor_tasks/`).
  Stays. Already generic across ADE + DAB per v2 spec §6.1's
  "Task-view materialization" paragraph (lines 690-702): image
  overrides, leakage deny-globs, per-task Dockerfile additions,
  `RAZORBACK_BENCHMARK_KIND` env injection, solution-file exclusion.
  Each transform reads its config from the resolved task directories,
  not the benchmark kind discriminator.

What does NOT survive: per-benchmark Pydantic classes, per-benchmark
builders, per-benchmark plugin packages for non-generative benchmarks
(only DAB needs a plugin; future generative benchmarks would too).

## §10 Spec amendment

**Decision tree** (mirrors entity body line 607):

- **Question A: does §1.3 already prescribe this?** YES. §1.3
  (lines 52-67) reads "Razorback ships no benchmark adapters" and
  the captain's framing matches verbatim. The spec is already
  correct in spirit.
- **Question B: does §6.1 prescribe this in the schema?** PARTIALLY.
  §6.1 ("Top-level shape") already documents `dataset:
  <org>/<name>@<ref>` for ADE (lines 660-676) and
  `dataset: <name>@<version>` for DAB (lines 678-688). Both routes
  go through `PackageDatasetClient` per the "Task-view materialization"
  paragraph (lines 690-702). The §6.1 YAML example at line 728-734
  uses `kind: harbor_dab`, which is unaffected if the collapse is
  additive (option b) and rewrites cleanly if the collapse is
  hard-cutover (option a).
- **Question C: does any other section reference `kind:
  harbor_dab` / `ade-bench` / `spider2-dbt`?** No. Plan-stage grep
  showed `kind: harbor_dab` at line 731 only; no other named-kind
  references in the v2 spec doc.

**Recommended amendment** (paired with option (b) collapse-partial):

Add a new paragraph at the end of §6.1's "Task-view materialization"
block, before the YAML example, with the following text:

> **Generic Harbor surface (`kind: harbor`).** Any harbor-published
> dataset is addressable through a single generic block:
> `kind: harbor` + `dataset: <org>/<name>@<ref>` + optional task
> selectors (`tasks`, `exclude_tasks`, `n_tasks` — matching harbor's
> `-i` / `-x` / `-l` flags) + optional `prep:` discriminator for
> benchmarks that require razorback-side task materialization
> (currently DAB, via the `razorback-plugin-dab` subprocess). The
> per-benchmark blocks `harbor_dab`, `ade-bench`, and `spider2-dbt`
> stay supported as the existing path; new harbor-published
> benchmarks (dabstep, swe-bench-verified, terminal-bench-2,
> lawbench, replicationbench, medagentbench, swe-bench-pro, ...)
> use `kind: harbor` and cost zero razorback code per addition.
> See [`2026-05-23-generic-harbor-benchmark-surface.md`](./2026-05-23-generic-harbor-benchmark-surface.md)
> for the migration shape and prep-block discriminator.

No other §6.1 changes required for option (b). The YAML example at
line 728-734 stays as-is (`kind: harbor_dab` is still a valid
spec).

**For option (a) hard cutover:** additionally, the YAML example at
line 728-734 rewrites from `kind: harbor_dab` to `kind: harbor` +
`prep: {kind: dab-plugin, ...}`; §1.3 gains a clarifying bullet
that razorback ships one benchmark block (`kind: harbor`) plus
`kind: local` and one prep registry. Optional.

**For option (c) aliases:** same §6.1 amendment as (b), plus a
deprecation table somewhere (probably §6.1's "Top-level shape"
prose) listing alias kinds and their removal window.

This proposal lands the (b)-shape amendment alongside the schema
addition. See the diff under §11.

## §11 Recommendation

**Recommendation: (b) coexist-permanently / collapse-partial.**

Ship `HarborBenchmarkBlock` as a non-breaking addition. Leave
`HarborDabBenchmarkBlock`, `AdeBenchBenchmarkBlock`, and
`Spider2DbtBenchmarkBlock` in place. Document the new block as the
recommended surface for new specs; document the old blocks as
"existing path kept for backwards compat" via docstring headers.
Amend v2 spec §6.1 per §10 above to advertise the generic surface.

**Cost.**
- ~2 days of implementation work in a sibling entity:
  - New `HarborBenchmarkBlock` + `PrepBlock` + `DabPrep` classes in
    `spec/schema.py` (~80 LOC including validators).
  - New `_build_harbor` builder in `translate.py` (~120 LOC,
    factoring out the prep registry).
  - Wire `DabPrepRunner` adapter around the existing
    `_build_harbor_dab` body (no plugin changes).
  - Pydantic unit tests for the new block (validators, source
    selection, prep dispatch).
  - One end-to-end smoke spec using dabstep to prove pure
    pass-through works.
  - v2 spec §6.1 amendment per §10 above.
- Zero spec-hash ripple — existing frozen specs stay valid.

**Benefit.**
- Every future harbor-published benchmark is a one-line spec
  addition. Seven benchmarks already on the hub (dabstep,
  swe-bench-verified, terminal-bench-2, lawbench, replicationbench,
  medagentbench, swe-bench-pro) become available immediately.
- Razorback's implementation aligns with §1.3's stated intent.
- The proof case (dabstep) ships in the same sibling entity as a
  smoke spec.

**Why not (a) hard cutover.** The benefit (single canonical kind in
schema) is dwarfed by the cost: re-freezing every existing frozen
spec across the 7q matrix and any DAB paper-repro work, plus the
ripple through validation evidence and provenance sidecars. Hard
cutover is the right call once the generic block has been in
production for some months and the old blocks are demonstrably
unused — at which point this becomes a routine deprecation rather
than a risky migration.

**Why not (c) aliases.** Alias-time auto-population is subtle and
adds debugging surface area. The benefit over (b) — automatic
silent migration of existing specs — is small because frozen specs
don't re-parse and active specs can be migrated by hand as they're
touched. Aliases are a useful tool for hard-cutover sunsetting; for
a non-breaking addition, the alias machinery is overkill.

**Why not (c) no-op.** The current pattern is real friction for any
captain who wants to spec-add a harbor benchmark. The dabstep
question that motivated this design doc is going to recur for
swe-bench-verified, terminal-bench-2, and every future hub
publication. Two days of work amortizes across all of them and
realigns with §1.3 in the bargain.

**Decision-point summary (for captain reply).**

> YES / NO / MODIFY: ship `HarborBenchmarkBlock` as non-breaking
> addition per §4. File sibling implementation entity. Amend v2
> spec §6.1 per §10. Defer migration of the existing per-benchmark
> blocks until the new surface is proven in production.

If YES: this doc + the v2 spec amendment merge; a sibling
implementation entity is filed in `docs/razorback-implementation/`
for the schema additions, the `_build_harbor` builder, and the
dabstep smoke. If MODIFY (e.g., "do option (a) hard cutover
instead", "skip the spec amendment", "scope the prep registry
differently"), this doc updates per captain direction and the
sibling entity reflects the modified scope. If NO: this doc lands
as a recorded analysis under `docs/superpowers/specs/`; the
implementation does not change.
