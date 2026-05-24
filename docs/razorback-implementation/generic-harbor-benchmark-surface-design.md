---
id: hmh8cq1mjkzbhpt6vnga8a03
title: Collapse per-benchmark blocks into generic kind: harbor + plugin migration
status: validation
source: Captain directive 2026-05-23 — "let's say we have a consumer repo, targeting dabstep (another harbor-listed dataset), would this work today? or does it need more wiring in razorback?" → captain pushed back on the "needs new BenchmarkBlock class" answer with "no this is too complicated. i'd assume if dabstep is already on harbor, there should be just simple config, no additional classes/plugin needed." Captain then provided concrete URL `https://hub.harborframework.com/datasets/adyen/dabstep/latest` and asked for a design doc + grounded research + spec amendment if material.
started: 2026-05-23T22:25:35Z
completed:
verdict:
score: 0.92
worktree: .worktrees/spacedock-ensign-generic-harbor-benchmark-surface-design
issue:
pr:
mod-block: merge:pr-merge
---

## Problem

Razorback's `spec.benchmark` discriminator is per-benchmark today:
`HarborDabBenchmarkBlock` / `AdeBenchBenchmarkBlock` /
`Spider2DbtBenchmarkBlock` / `LocalBenchmarkBlock` /
legacy `DabBenchmarkBlock` (`src/razorback/spec/schema.py:101-310`).
`translate.py` has matching per-benchmark builders
(`_build_harbor_dab` / `_build_ade_bench` / `_build_spider2_dbt` at
lines 312-453). Every new harbor-published benchmark requires:

1. A new `BenchmarkBlock` Pydantic class with `kind: Literal["..."]`
2. A new `_build_<benchmark>` method in `translate.py` that emits a
   benchmark-specific Harbor job-config YAML
3. (Often) a sibling `razorback-plugin-<benchmark>` pip package

This contradicts spec §1.3 explicitly:

> Razorback is not a benchmark library. Benchmarks live in harbor's
> catalog as adapters publishable via `harbor publish`. **Razorback
> ships no benchmark adapters.**

The captain's framing — "if dabstep is on harbor, there should be
just simple config" — IS the spec's actual intent. The implementation
has accumulated per-benchmark special-casing that the spec disclaims.

## Grounded research (already performed by FO)

### Harbor already exposes a generic published-dataset entrypoint

`harbor run -d <org>/<name>@<version>` (from
`.venv/lib/python3.12/site-packages/harbor/cli/jobs.py:825-844`)
resolves any Harbor-published dataset via `PackageDatasetClient`
(`.../registry/client/package.py`) → returns `DatasetMetadata` with
`task_ids` + `files`. Harbor's CLI ALREADY accepts:

- `-d / --dataset <org/name@version>` — published dataset reference
  (the dabstep case)
- `-p / --path <path>` — local task/dataset directory
- `--task-git-url` + `--task-git-commit` — git-based task
- `-t / --task <org/name[@ref]>` — single task from registry
- `-i / --include-task-name <glob>` — task subset selector
- `-x / --exclude-task-name <glob>` — task exclusion selector
- `-n / --n-tasks <int>` — task-count cap

So the entire benchmark-selector surface razorback needs to expose IS
already in harbor's CLI. Razorback's job is to emit a YAML or pass
the relevant flags.

### Dataset.toml schema is canonical at the harbor layer

Harbor's `DatasetManifest` model
(`.../harbor/models/dataset/manifest.py:152-218`) defines the
canonical TOML schema:

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

[[files]]                   # optional dataset-level files (e.g., metric.py)
path = "metric.py"
digest = "sha256:<64hex>"   # auto-computed at publish time if omitted
```

Content hash = SHA-256 over sorted task digests (+ optional file
path:digest pairs). `harbor publish` produces this manifest from a
local source; `PackageDatasetClient` resolves a `<org>/<name>@<ref>`
back into the materialized task tree.

### dabstep — confirmed published

`https://hub.harborframework.com/datasets/adyen/dabstep/latest` shows:
- Owner: `adyen`
- Name: `dabstep`
- 450 tasks across 5+ pages of task IDs (`adyen/6` through `adyen/2770`)
- Command surfaced verbatim: `harbor run -d adyen/dabstep`
- Hub does NOT expose the dataset.toml/README server-side; the manifest
  lives inside the published package itself, retrievable via `harbor
  download` or `PackageDatasetClient`.

### Comparison benchmark — `swe-bench/swe-bench-verified`

Also confirmed at `https://hub.harborframework.com/datasets/swe-bench/swe-bench-verified`:
- Owner: `swe-bench`
- Name: `swe-bench-verified`
- 500 manually validated tasks (subset of the 2294-issue
  SWE-bench corpus)
- Harbor maintains a "parity table" comparing the official SWE-bench
  baseline vs. Harbor's adapter: `mini-swe-agent` + GPT-5-mini scored
  `official 0.563 +/- 0.000 vs. Harbor 0.545 +/- 0.007` across 499
  comparable tasks. So harbor's adapter is already calibrated and
  in-use; the dataset is mature.
- Source: 2024 ICLR paper (Jimenez et al., OpenReview).

Other harbor-hub datasets visible: `terminal-bench/terminal-bench-2`
(89), `lawbench/lawbench` (1000), `replicationbench/replicationbench`
(90), `stanford/medagentbench` (300), `scale-ai/swe-bench-pro` (731).
Each follows the same `<org>/<name>` pattern. None of them are wired
into razorback today.

### Razorback's current handoff to harbor

`src/razorback/cli/run.py:55-65` `_invoke_harbor()`:

```python
proc = subprocess.run(
    ["uv", "run", "harbor", "run", "-c", str(job_config_yaml)],
    env=env, capture_output=False,
)
```

Razorback emits a job-config YAML (per-benchmark via translate.py)
and passes it through `-c`. The benchmark-specific knowledge is
ENCODED in the YAML razorback constructs. If razorback emitted a
generic YAML that passed dataset+task selectors through, the
per-benchmark builders become unnecessary.

## Acceptance criteria

> **AC list rewritten 2026-05-25** by the first officer at captain
> directive. Earlier iterations (filed AC-1..AC-4 "design doc shipped"
> form, cycle-3 AC-1'..AC-5' "user-scenario narratives" form) violated
> the workflow's doc-only anti-pattern — verification clauses named
> "section exists" / "section lists N decision points" / "doc cites
> harbor source files" rather than load-bearing code or behavior. The
> earlier ACs remain visible in the entity's git history. The ACs
> below describe the actual deliverable: the per-benchmark-block
> collapse + plugin migration enumerated in `## §2.11`. The design
> doc, spike findings, and decision-tree analyses already in this
> entity body are implementation notes and stage-report content — not
> separately gated artifacts.

**AC-1 — `HarborDabBenchmarkBlock` removed; `razorback-plugin-dab`
discovered as `kind: harbor` + `plugin: dab` consumer.**
The block class and its translator builder are deleted; dispatch
flows through the generic `_build_harbor` + plugin escape valve;
the existing DAB plugin package is reachable via the `razorback.plugin_args`
entry-point group.
Verified by:
- `grep -n "class HarborDabBenchmarkBlock" src/razorback/spec/schema.py` returns 0 matches.
- `grep -n "_build_harbor_dab\b" src/razorback/translate.py` returns 0 matches.
- `uv run python -c "import importlib.metadata as m; assert 'dab' in {ep.name for ep in m.entry_points(group='razorback.plugin_args')}"` exits 0.
- A previously-shipped harbor_dab spec migrated to `kind: harbor` + `plugin: dab` round-trips through `uv run rk freeze` cleanly; `rk run --explain --explain-format json` on the migrated spec resolves to the same dataset ref, model, runtime, and `tools_denied` set as the pre-migration freeze (cite both `.frozen.yaml` files in the stage report).
- `uv run pytest packages/razorback-plugin-dab/tests/ tests/translate/test_dab_dispatch.py -v` exits 0 across the 13 migrated test files plus dispatch tests.

**AC-2 — `AdeBenchBenchmarkBlock` removed; ade-plugin wired; generic
`/workspace/preflight.sh` mechanism in place.**
The ade-bench block class and its translator builder are deleted;
the solver runs `/workspace/preflight.sh` if present (filesystem
convention, not benchmark-name conditional); ade-plugin's `generate()`
emits this file into the materialized task view.
Verified by:
- `grep -nR "class AdeBenchBenchmarkBlock\|_build_ade_bench\b\|benchmark_kind == [\"']ade-bench" src/razorback/` returns 0 matches.
- `grep -n "/workspace/preflight.sh" src/razorback/_runtime/` returns ≥1 match (solver-side dispatcher).
- `uv run python -c "from razorback_plugin_ade_bench.generate import generate; ..."` (or the plugin's canonical entry) emits `/workspace/preflight.sh` with executable bit set for a materialized task view fixture; `test -x` on the emitted path exits 0.
- A previously-shipped ade-bench spec migrated to `kind: harbor` + `plugin: ade-bench` round-trips through `uv run rk freeze` and `uv run rk run --explain` cleanly.
- `uv run pytest packages/razorback-plugin-ade-bench/tests/ tests/translate/test_ade_dispatch.py -v` exits 0.

**AC-3 — `Spider2DbtBenchmarkBlock` removed; spider2-plugin wired.**
Verified by:
- `grep -n "class Spider2DbtBenchmarkBlock\|_build_spider2" src/razorback/` returns 0 matches.
- `uv run python -c "import importlib.metadata as m; assert 'spider2' in {ep.name for ep in m.entry_points(group='razorback.plugin_args')}"` exits 0.
- A previously-shipped spider2-dbt spec migrated to `kind: harbor` + `plugin: spider2` round-trips through `uv run rk freeze` cleanly.
- `uv run pytest packages/razorback-plugin-spider2/tests/ -v` exits 0 (or, if the plugin lives in-tree, the equivalent test path).

**AC-4 — `rk score` surfaces `taint_status` from `audit.json` +
auto-pulls `paper_baseline` from spec frontmatter.**
Verified by:
- `uv run rk score <fixture-run-dir>` JSON output has a top-level `taint_status` field equal to the `audit.json` summary verdict for that run.
- When the spec frontmatter declares `paper_baseline: <value>`, `uv run rk score <run-dir>` uses it as the `--against-constant` target without an explicit CLI flag; the JSON output's comparison block names the source as `spec.frontmatter`.
- `uv run pytest tests/cli/test_score.py -v` exits 0 with RED→GREEN tests covering both behaviors (taint surface + paper_baseline auto-pull); both tests fail on the pre-amendment branch and pass on the post-amendment branch (cite both commit SHAs).

**AC-5 — examples/specs migrated to `kind: harbor`; sealed_hash
break documented in commit message + design §2.4.**
Verified by:
- `grep -rl "^\s*kind:\s*\(harbor_dab\|ade-bench\|spider2-dbt\)\b" examples/ docs/` returns empty.
- `for s in $(find examples -name "*.yaml" -path "*spec*"); do uv run rk freeze "$s" --allow-missing >/dev/null; done` exits 0 for every spec file.
- `git log --oneline --grep="sealed_hash"` shows ≥1 commit on this branch whose body explains the break (per design §2.4); the body cites the affected frozen-spec set and names `rk freeze --rehash` as the migration recipe per captain decision 2026-05-24.

**AC-6 — v2 spec amended at §1.3 / §3.2 / §5 / §6.1 / §6.2 / §7
per §2.10.**
Verified by:
- `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` carries a diff covering the six §-sections enumerated in §2.10; `git log --oneline -- docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` shows the amendment commit on this branch.
- `git diff main..HEAD -- docs/superpowers/specs/2026-05-19-razorback-on-harbor.md | wc -l` is within the ~120-line envelope §2.10 estimates (allow ±20%).
- `grep -c "^kind: harbor\b" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` matches the count §2.10 predicts (zero per-benchmark-named example `kind:` values remain other than `local` / `harbor` / `harbor-local`).

**AC-7 — Existing pytest stays green; non-migrated paths unchanged.**
Verified by:
- `uv run pytest tests/ -v` exits 0 modulo pre-existing failures (LFS-hydration etc.); the failure set on this branch is byte-identical to the failure set on `main` immediately before merge.
- `LocalBenchmarkBlock` dispatch path's existing tests (`tests/translate/test_local.py` or equivalent) pass without modification; the local kind is explicitly preserved per § Out of scope.

## Test plan

- **Mechanism check first:** confirm via `uv run python -c "from
  harbor.cli.jobs import start; import inspect;
  print(inspect.signature(start))"` (or equivalent) that
  `--dataset` flag actually accepts `<org>/<name>@<version>` against
  the live PackageDatasetClient. Cite the exit code + output in the
  doc.
- **Dabstep dry-test:** run `uv run harbor download -d adyen/dabstep`
  (or `harbor datasets download adyen/dabstep@latest`) and observe
  whether the dataset.toml + task files materialize successfully
  without any razorback involvement. Cite output (success or specific
  error) in the doc. (~Network only; no API spend.)
- **Spec amendment review:** if the doc proposes a v2 spec change,
  validate the diff renders cleanly (`git apply --check`) and is
  internally consistent (no §-ref broken).
- **Pytest required at every commit boundary** — this entity ships
  code, not prose. Each of commits 4a/3/4b/4c/5/6 must leave
  `uv run pytest tests/ -v` green modulo the pre-existing failure
  set unchanged on `main`. The TDD discipline is per-commit (RED
  test for deletion behavior before each block delete; RED test for
  the new behavior — plugin entry-point discovery, generic preflight
  dispatcher, score field surfacing — before each implementation).

## Out of scope

- **Building a `razorback-plugin-dabstep` package.** Per the design
  doc §1.1, dabstep is pure pass-through — no plugin needed. If a
  future dabstep-specific verifier hook becomes load-bearing,
  that's a sibling entity.
- **Refactoring `LocalBenchmarkBlock`.** Raw `task_paths: list[Path]`
  is genuinely not a harbor concept; `kind: local` stays as the dev
  fixture surface (design doc §2.2).
- **`rk diff` implementation.** Deferred per v2 spec §3.2; both
  scenarios assume it exists at autoresearch-loop-live time. Ships
  when paired-test demand exists. Design doc §2.12.
- **Authentication for private Harbor datasets.** Both example
  benchmarks (dabstep + swe-bench-verified) are anonymous; auth
  ships when a consumer needs it. Design doc §2.12.
- **Codex/Pi runtime adapters.** Same as `ne`'s scope discipline.

## Depends on

- (none — code refactor on top of the in-tree `HarborBenchmarkBlock`
  + `_build_harbor` translator already landed at cycle-2 commits
  `b36e672` and `fe38f9f`)
- Aware-of: `qh dab-harbor-dataset-definition` (DONE; established
  the `dataset: dab@1.0` precedent), `gb ade-bench-harbor-dataset-ref`
  (DONE; established `dataset: <org>/<name>@<ref>` for ADE). Both
  established surface pieces this entity now consolidates.

## Resume hook

When this lands, the three per-benchmark `BenchmarkBlock` subclasses
(`HarborDabBenchmarkBlock`, `AdeBenchBenchmarkBlock`,
`Spider2DbtBenchmarkBlock`) and their `translate.py` builders are
gone; dispatch flows through `_build_harbor` + a plugin escape valve
discovered via the `razorback.plugin_args` entry-point group; the v2
spec at `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
codifies this as canonical. Every future harbor-published benchmark
(dabstep, swe-bench-verified, terminal-bench-2, lawbench,
replicationbench, medagentbench, swe-bench-pro) becomes a one-spec
addition with zero razorback-core code change — at most a new plugin
package if benchmark-specific preflight or scoring is required.

## Plan-stage research validation (harbor==0.6.6 cross-check)

Plan worker confirmed `harbor==0.6.6` installed in
`.venv/lib/python3.12/site-packages/harbor/`. Patches to FO-recorded
line citations (precise spans to use verbatim in the design doc):

- **`harbor/cli/jobs.py`.** Function `start()` is defined at **line
  471** (FO cited `800-895`, which is the flag block WITHIN the
  signature, not the function start). End-of-signature inferred via
  next function `resume()` at line 1362. Verbatim flag-block citations
  for the design doc:
  - `-p / --path` (path): **lines 804-813**
  - `--task-git-url` (task_git_url): **lines 814-821**
  - `--task-git-commit` (task_git_commit_id): **lines 822-830**
  - `-d / --dataset` `<dataset@version>` (dataset_name_version):
    **lines 831-840** — help text reads literally
    `Dataset name@version (e.g., 'dataset@1.0')`.
  - `--registry-url` (registry_url): **lines 841-849**
  - `--registry-path` (registry_path): **lines 850-858**
  - `-t / --task` `<org/name[@ref]>` (task_ref): **lines 859-868**
  - `-i / --include-task-name` glob (dataset_task_names):
    **lines 869-878**
  - `-x / --exclude-task-name` glob (dataset_exclude_task_names):
    **lines 879-888**
  - `-l / --n-tasks` (n_tasks): **lines 889-898**
  Recommended doc citation: `harbor/cli/jobs.py:471` (function start)
  + `harbor/cli/jobs.py:804-898` (dataset/task selector flag block).
  These ranges are stable for the pinned harbor==0.6.6.

- **`harbor/models/dataset/manifest.py`.** Module is 280 lines total.
  - `DatasetTaskRef` (name + sha256 digest, org/name validators):
    **lines 23-69**
  - `DatasetFileRef` (path + digest, e.g., `metric.py`):
    **lines 72-108**
  - `DatasetInfo` (name/description/authors/keywords):
    **lines 111-150**
  - `DatasetManifest` (schema_version + dataset + tasks + files +
    content-hash algorithm): **lines 153-279**
  - `compute_content_hash()` (sha256 over sorted task digests +
    optional `path:digest` file pairs joined with `;`):
    **lines 237-254**
  FO's TOML excerpt matches the model verbatim. Recommended doc
  citation: `harbor/models/dataset/manifest.py:23-279` (full schema).

- **`harbor/registry/client/package.py`.** File is 125 lines total
  (FO's `152-218` line guess was off — this is a small file).
  - `PackageDatasetClient` class: **lines 14-124**
  - `_get_dataset_metadata(name) -> DatasetMetadata`:
    **lines 19-60** — resolves an `org/name[@ref]` via internal
    RegistryDB, builds `PackageTaskId` per task (with
    `ref=f"sha256:{tv['content_hash']}"`), attaches dataset-level
    files, returns a `DatasetMetadata` carrying `task_ids`,
    `dataset_version_id`, `dataset_version_content_hash`.
  - `download_dataset_files()`: lines 62-91.
  - `download_dataset()`: lines 93-121.
  Recommended doc citation: `harbor/registry/client/package.py:14-124`.

- **`src/razorback/cli/run.py:54-68` — `_invoke_harbor`.** Matches
  the FO's snippet. Razorback emits a JobConfig YAML to
  `harbor run -c <yaml>`. The benchmark-specific knowledge is
  encoded entirely IN that YAML.

- **`src/razorback/spec/schema.py` — current `BenchmarkBlock`
  state.** Union at **lines 297-305**:
  `LocalBenchmarkBlock | HarborDabBenchmarkBlock |
  AdeBenchBenchmarkBlock | Spider2DbtBenchmarkBlock`. Critical for
  the design doc: **`HarborDabBenchmarkBlock` already supports
  `dataset: <name>@<version>` (line 140)** and
  **`AdeBenchBenchmarkBlock` already supports
  `dataset: <org>/<name>@<ref>` (line 231)** with three-tier resolution
  (tag/revision/sha256). The collapse precedent is already in-tree
  per-block; the design doc's job is to unify these two into a
  single `HarborBenchmarkBlock` and decide what happens to
  `Spider2DbtBenchmarkBlock` (currently local-only, `tasks_root`
  required) and the legacy `DabBenchmarkBlock` (already SUPERSEDED
  per its docstring lines 107-122).

- **`src/razorback/translate.py` — current per-benchmark builders.**
  - `_build_local` at **line 193**
  - `_build_ade_bench` at **line 211**
  - `_build_harbor_dab` at **line 312**
  - `_build_spider2_dbt` at **line 442**
  Verified `_build_harbor_dab` is NOT pure config translation: it
  spawns `uv run razorback-plugin-dab generate` per dataset (lines
  379-396) to materialize per-query task directories with
  `workspace_variant` semantics. This is real razorback-side prep
  work, not config. The design doc must explicitly flag that the
  collapse cannot delete this code path — it can only move it behind
  a per-dataset hook.

### Dabstep manifest — FO did NOT do this, plan worker DID

Probed `uv run harbor download adyen/dabstep@latest -o /tmp/... --cache`:

- **No auth required.** Public dataset, anonymous HTTPS download.
- Exit 0 in ~3s; 450 task directories materialized under
  `/tmp/dabstep_probe/adyen/<task-id>/<sha256>/{task.toml,instruction.md}`.
- Confirmed FO's hub-page task count (450) against actual download.
- The dataset.toml itself is NOT materialized into the user
  output_dir by `harbor download --cache` (the dataset manifest
  lives only as registry-side metadata accessed via
  `PackageDatasetClient`, not as a downloaded file). The hub
  page's `harbor run -d adyen/dabstep` command suggestion works
  because `harbor run` resolves the registry metadata internally
  on each invocation.
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
  tags = [ "dabstep", "data-analysis", "financial", "hard",]
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
- Sample `instruction.md` (verbatim, `adyen/1507`):
  > You are an expert data analyst and you will answer factoid
  > questions by referencing files in the data directory:
  > `/app/data/`... In the average scenario, which card scheme
  > would provide the cheapest fee for a transaction value of 50
  > EUR? ... When you have computed the final answer, write ONLY
  > the final answer to `/app/answer.txt`.

The materialized layout (`<org>/<task-id>/<sha256>/task.toml`) is
the canonical Harbor task shape. Razorback's spec-side
`benchmark.tasks: list[str]` selector (already used by
`AdeBenchBenchmarkBlock`) maps cleanly: spec entry `1507` →
matches resolved `adyen/1507`.

**Material implication for the design doc.** Dabstep is the proof:
zero razorback-side prep needed. The full task definition (image
specs, timeouts, instruction prompt, verifier setup) lives in the
downloaded `task.toml` + `instruction.md`. Razorback's job is
literally just to pass `-d adyen/dabstep` (with optional `-i` task
subset + `-l n-tasks` cap) through to harbor. No subprocess. No
plugin. No per-task transform.

Contrast with DAB (`_build_harbor_dab`): DAB is generative
(razorback-side plugin produces task dirs per dataset/query
combination per workspace_variant), so it CANNOT collapse to "just
pass `-d` through." The collapse strategy must offer two
operational modes — "pure pass-through" (dabstep, swe-bench-verified,
terminal-bench-2, lawbench, replicationbench, medagentbench,
swe-bench-pro) and "razorback prep + pass-through"
(DAB, future generative benchmarks).

## Implementation-stage plan (impl-stage worker reads this)

The impl stage writes a single design doc at
`docs/superpowers/specs/2026-05-23-generic-harbor-benchmark-surface.md`.
Below is the prescribed section structure, the before/after spec
examples to embed verbatim, the spec-amendment decision tree, and
the recommendation decision tree. The impl worker should NOT redo
the grounded research — it's already validated above.

### Doc section structure (impl writes these in order)

1. **Title + abstract** (~150 words). State the captain's framing
   quote ("if dabstep is on harbor, there should be just simple
   config") + the spec §1.3 quote ("Razorback ships no benchmark
   adapters") + the proposal sentence.
2. **§1 The current per-benchmark surface.** Enumerate the four
   active blocks from `schema.py:297-305`, the four builders from
   `translate.py:193/211/312/442`, and the per-block cost
   (one Pydantic class + one builder + sometimes one
   `razorback-plugin-<name>` package). Cite the legacy
   `DabBenchmarkBlock` deprecation as precedent for "we already
   collapse blocks here."
3. **§2 What harbor already exposes.** Copy the `harbor/cli/jobs.py`
   flag-block citation verbatim (lines 804-898), the
   `DatasetManifest` schema citation (lines 23-279 of
   `models/dataset/manifest.py`), the `PackageDatasetClient`
   citation (lines 14-124 of `registry/client/package.py`), and
   the `_invoke_harbor` razorback-side citation. Include the
   dabstep download probe result (exit 0, 450 tasks, no auth, ~3s).
4. **§3 The two operational modes.** "Pure pass-through" vs
   "razorback prep + pass-through". Show the matrix:
   - Pure pass-through: dabstep, swe-bench-verified, terminal-bench-2,
     lawbench, replicationbench, medagentbench, swe-bench-pro,
     and ADE-bench when sourced as `dataset: <org>/<name>@<ref>`.
   - Prep + pass-through: DAB (plugin generates per-query dirs).
   - Local-only: `LocalBenchmarkBlock` (no Harbor registry).
   - Local-but-Harbor-shaped: ADE-bench when sourced as
     `tasks_root:` (the dev escape hatch in the current
     `AdeBenchBenchmarkBlock`), and `Spider2DbtBenchmarkBlock`
     (`tasks_root` is required today).
5. **§4 Proposed `HarborBenchmarkBlock`.** Schema:
   ```python
   class HarborBenchmarkBlock(BaseModel):
       kind: Literal["harbor"]
       dataset: str | None = None       # <org>/<name>@<ref> for registry-resolved
       tasks_root: Path | None = None   # local Harbor-shaped dir, dev escape hatch
       tasks: list[str] | None = None   # subset selector (matches -i flag semantics)
       exclude_tasks: list[str] | None = None  # exclusion selector (matches -x)
       n_tasks: int | None = None       # task-count cap (matches -l)
       prep: PrepBlock | None = None    # OPTIONAL razorback-side prep hook
   ```
   The `prep:` discriminated union covers the DAB case (and any
   future generative benchmark):
   ```python
   PrepBlock = Annotated[Union[DabPrep, ...], Field(discriminator="kind")]

   class DabPrep(BaseModel):
       kind: Literal["dab-plugin"]
       workspace_variant: Literal["direct-minimal", "direct-structured", "spacedock"]
       data_root: Path | None = None
       hints: bool = False
       query_mode: Literal["batch", "per-query"] = "per-query"
   ```
   This is the impl-stage doc's central proposal. The doc should
   explicitly note that `prep: None` ⇒ pure pass-through path.
6. **§5 Before/after spec examples (verbatim).** Two pairs, exactly
   as in §5.1 + §5.2 below.
7. **§6 Migration shape.** What `harbor_dab` / `ade-bench` /
   `spider2-dbt` collapse to:
   - `kind: harbor_dab` ⇒ `kind: harbor` + `prep: {kind: dab-plugin, ...}`.
   - `kind: ade-bench, dataset: <org>/<name>@<ref>` ⇒ `kind: harbor`
     (no prep). The `db_type` / `project_type` /
     `docker_image_override` / `batch_mode` fields move to a
     thin `ade-bench` prep block IF they're load-bearing — flag
     for captain review.
   - `kind: ade-bench, tasks_root: <path>` ⇒ `kind: harbor` +
     `tasks_root:` (no prep, since tasks_root mode is pure local).
   - `kind: spider2-dbt` ⇒ same shape as ade-bench local-path —
     `kind: harbor` + `tasks_root:` with optional thin
     `spider2-dbt` prep block if `docker_image_override` /
     `batch_mode` are load-bearing.
   - `kind: local` ⇒ KEEPS its own block (genuinely different
     invocation — no Harbor registry, raw task_paths).
8. **§7 What `translate.py` looks like after collapse.** A single
   `_build_harbor()` builder that:
   - Resolves `dataset:` via PackageDatasetClient (when set) OR
     reads from `tasks_root:` (when set).
   - Dispatches `prep:` to the corresponding sibling plugin (DAB
     today, others later) if present.
   - Builds JobConfig with `tasks: list[TaskConfig]` from the
     resolved task paths, plus passes `tasks` / `exclude_tasks` /
     `n_tasks` selectors through.
   - The existing `_build_harbor_dab` body collapses into a
     `dab-plugin` prep hook called by `_build_harbor`.
9. **§8 Backwards compat.** Three options (impl doc picks one based
   on §10 recommendation):
   - **Hard cutover.** Delete the old kinds. Per `spec.benchmark`
     hashes change, so frozen specs need re-freeze. Cost: 12
     direct-structured specs from `7q-matrix` + however many DAB
     paper-repro specs.
   - **Aliases.** Keep `harbor_dab` / `ade-bench` / `spider2-dbt`
     as type aliases that emit `kind: harbor` + auto-populate
     `prep:` at validation time. Spec hash stable. Deprecation
     window measured in months.
   - **Coexist permanently.** New `kind: harbor` is the recommended
     surface; old kinds keep working forever. No spec breakage.
     Cost: doubled schema surface area, drift risk.
10. **§9 Razorback-side prep that DOES survive collapse.** Enumerate:
    - DAB's `workspace_variant` (solver-side detail, threads via
      `DabPrep.workspace_variant`).
    - DAB's `query_mode` (`batch` vs `per-query`, threads via
      `DabPrep.query_mode`).
    - DAB's `hints:` flag (threads via `DabPrep.hints`).
    - ADE-bench's `db_type` / `project_type` / `docker_image_override` /
      `batch_mode` — captain-review needed; if load-bearing, they
      get a thin `AdeBenchPrep` block; if vestigial, drop.
    - Spider2-dbt's `docker_image_override` / `batch_mode` — same
      captain-review treatment.
    - The task-view materializer (`src/razorback/harbor_tasks/`)
      stays — it's already generic across ADE + DAB per spec
      §6.1's "Task-view materialization" paragraph.
11. **§10 Spec amendment** (see §5.3 below for the decision tree).
12. **§11 Recommendation** (see §5.4 below for the decision tree).

### Verbatim before/after spec examples (impl embeds these in §5)

#### §5.1 — dabstep

**Today (would require new code):**
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

#### §5.2 — swe-bench-verified

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

#### §5.3 — DAB (the prep-mode case, before/after)

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

### §5.3 (continued) — Spec-amendment decision tree

Spec doc at
`docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`. The
amendment evaluation in the design doc must answer:

- **Question A: does §1.3 already prescribe this?** YES. §1.3 reads
  "Razorback ships no benchmark adapters" and the captain's framing
  matches verbatim. The spec is already correct in spirit.
- **Question B: does §6.1 prescribe this in the schema?** PARTIALLY.
  §6.1 ("Top-level shape") already documents `dataset:
  <org>/<name>@<ref>` for ADE and `dataset: <name>@<version>` for
  DAB. Both routes go through `PackageDatasetClient` per the
  "Task-view materialization" paragraph. The §6.1 YAML example at
  line 728-734 uses `kind: harbor_dab`, which becomes wrong under
  the collapse.
- **Question C: does any other section reference `kind:
  harbor_dab` / `ade-bench` / `spider2-dbt`?** Plan worker grep
  showed only `kind: harbor_dab` at line 731. No other named-kind
  references in the spec doc.
- **Diff scope (if collapse accepted):**
  - §6.1 example YAML: `kind: harbor_dab` → `kind: harbor` +
    add `prep:` block. (~5 lines.)
  - §6.1 prose: add "**Single `kind: harbor` for all Harbor-resolved
    benchmarks**" sub-paragraph explaining the collapse +
    `prep:` discriminator.
  - §1.3 Non-goals: optionally add a clarifying bullet that
    razorback ships ONE benchmark block (`kind: harbor`) and ONE
    prep registry for benchmarks that need razorback-side
    materialization (currently DAB).
- **If NO collapse:** spec amendment is zero. The implementation
  diverges from §1.3 in spirit but not in letter (the spec doesn't
  forbid per-benchmark blocks; it just discourages adapters).

### §5.4 — Recommendation decision tree

The design doc's `## Recommendation` section must choose ONE:

- **(a) Collapse-all.** Single `kind: harbor` block + `prep:`
  discriminator. Migrate `harbor_dab`/`ade-bench`/`spider2-dbt`
  via aliases (backwards-compat option 8.b). Cost: ~1 week of
  refactor work in a sibling entity. Benefit: every future
  Harbor-published dataset is a one-line spec.
- **(b) Collapse-partial.** Add `kind: harbor` for pure
  pass-through cases. Leave `harbor_dab`/`ade-bench`/`spider2-dbt`
  alone (they keep working, but new benchmarks like dabstep use
  `kind: harbor`). Cost: ~2 days. Benefit: dabstep + swe-bench-verified
  + 5 other hub datasets become one-line specs immediately. Cost:
  permanent schema-doubling.
- **(c) No-op.** Document the current pattern as deliberate.
  Cost: zero. Benefit: nothing changes. Future Harbor benchmarks
  still cost ~3 PRs each.

Plan worker's tentative leaning (impl doc author can override): **(b)
collapse-partial**. Rationale: (b) ships dabstep + swe-bench-verified
in days, doesn't break frozen DAB specs, and the
"permanent-schema-doubling" cost is small because the existing
per-benchmark blocks are stable + small. (a) is cleaner but its
benefit (no schema doubling) is dwarfed by its cost (re-freeze
ripple, alias maintenance burden during deprecation). Document this
leaning in §11 but defer the final pick to the impl-doc author.

### Research validation checklist (impl-stage worker confirms)

Before writing the doc, the impl worker should re-verify (cheap):

- `test -f /Users/clkao/git/razorback/.venv/lib/python3.12/site-packages/harbor/cli/jobs.py`
- `uv run python -c "from harbor.cli.jobs import start; print(start.__module__)"`
  (expect: `harbor.cli.jobs`)
- `uv run python -c "from harbor.models.dataset.manifest import DatasetManifest; print(DatasetManifest.model_fields.keys())"`
  (expect: `dict_keys(['schema_version', 'dataset', 'tasks', 'files'])`)
- `uv run python -c "from harbor.registry.client.package import PackageDatasetClient; print(hasattr(PackageDatasetClient, '_get_dataset_metadata'))"`
  (expect: `True`)

If any of these fail, the impl worker should pause and message the
captain — the harbor pin may have moved.

## Stage Report: plan

- DONE: Apply plan-output flex rule per README. 4 ACs but this entity IS the design doc — operationally simple. Recommend inline plan (the entity body already contains the FO's grounded research; the plan-stage worker's job is to scope HOW the design doc gets written, not redo the research). Justify decision in stage report.
  Inline plan chosen — embedded the impl-stage section structure + verbatim spec examples + spec-amendment decision tree + recommendation decision tree directly in the entity body (sections "Plan-stage research validation" + "Implementation-stage plan"). Rationale: the deliverable is one Markdown file, no sub-task fan-out is meaningful, and the FO already invested in grounded research that the impl worker now has a complete scaffolding for.
- DONE: Mechanism validation — extend the FO's grounded research by READING the actual harbor source files cited in the entity body and confirming the line numbers + function shapes.
  Read `harbor/cli/jobs.py` (verified `start()` at line 471, flag block 804-898; FO's `800-895` cite was the flag block, not the function start — patched in the validation section), `harbor/models/dataset/manifest.py` (verified DatasetManifest at 153-279, FO's TOML excerpt matches verbatim), `harbor/registry/client/package.py` (verified `_get_dataset_metadata` at 19-60; FO's `152-218` line cite was wrong — the file is only 125 lines total — patched), `src/razorback/cli/run.py:54-68` `_invoke_harbor` (matches FO snippet verbatim), `src/razorback/spec/schema.py:297-305` `BenchmarkBlock` (confirmed `HarborDabBenchmarkBlock`/`AdeBenchBenchmarkBlock` already support `dataset:` — strong precedent for the collapse), `src/razorback/translate.py` (verified per-benchmark builders at 193/211/312/442; flagged that `_build_harbor_dab` does generative work via the DAB plugin, NOT pure config translation). Then probed `uv run harbor download adyen/dabstep@latest`: exit 0, ~3s, 450 task dirs, no auth required, sample `task.toml` + `instruction.md` captured verbatim. Material implication recorded: dabstep needs zero razorback-side prep, DAB needs a prep hook — the design must offer both modes.
- DONE: Sequence the implementation-stage tasks. Plan worker's job is to enumerate (a) the design doc's section structure, (b) the verbatim before/after spec examples for dabstep + swe-bench-verified that impl will write, (c) the spec-amendment decision tree (which §6.1/§6.2 sections potentially change), (d) the recommendation section's decision tree (collapse-all vs collapse-partial vs no-op).
  All four enumerated in "Implementation-stage plan" section: (a) 12-section doc structure prescribed; (b) verbatim before/after YAML for dabstep + swe-bench-verified + DAB embedded (the impl worker copies these directly into §5 of the design doc); (c) spec-amendment decision tree enumerated Question A/B/C + diff scope for §6.1 example YAML + §6.1 prose + optional §1.3 clarification; (d) recommendation decision tree enumerated (a) collapse-all / (b) collapse-partial / (c) no-op with cost+benefit, plan worker's tentative lean is (b) but explicit deferral to impl-doc author. Also added a research-validation checklist the impl worker can run in <30s before writing.

### Summary

Validated the FO's grounded research against `harbor==0.6.6` source — three line-citation corrections (function start at 471 not 800-895; manifest.py spans 23-279; package.py is 125 lines not 152-218). Probed `harbor download adyen/dabstep@latest`: confirmed pure pass-through is real (450 tasks, no auth, no razorback prep). Sequenced the impl-stage work as a 12-section doc with verbatim before/after YAML for dabstep + swe-bench-verified + DAB, a spec-amendment diff scope (~5 lines in §6.1 + optional §1.3 clarification), and a three-option recommendation tree with a tentative lean toward "collapse-partial" (ship dabstep + swe-bench-verified now without breaking frozen DAB specs).

## Stage Report: implementation

- DONE: Run the research-validation checklist from the plan section `### Research validation checklist (impl-stage worker confirms)` (entity body line 669).
  Re-confirmed on pinned harbor==0.6.6: `harbor` pkg version 0.6.6; `from harbor.cli.jobs import start` resolves; `DatasetManifest.model_fields.keys()` = `['schema_version', 'dataset', 'tasks', 'files']`; `hasattr(PackageDatasetClient, '_get_dataset_metadata')` = True; `def start(` at jobs.py:471, `--dataset` literal at jobs.py:835 (inside the `dataset_name_version` Annotated block 831-840); all flag-block line citations stable. Evidence inlined verbatim in design doc §2 "Research-validation evidence" subsection.
- DONE: Write the design doc at `docs/superpowers/specs/2026-05-23-generic-harbor-benchmark-surface.md` per the 12-section structure prescribed in the entity body's `### Doc section structure (impl writes these in order)` (line 426).
  Doc shipped at the target path. All 12 sections written in prescribed order. Verbatim before/after YAML embedded for dabstep (§5.1), swe-bench-verified (§5.2), and DAB (§5.3). Spec-amendment decision tree rendered as §10. Recommendation decision tree rendered as §11 with explicit pick (option b — collapse-partial) and a captain-reply summary. All harbor source line citations + razorback source line citations resolve verbatim against pinned harbor==0.6.6 / current main.
- DONE: Execute the spec-amendment if the recommendation is non-no-op.
  Design doc recommends (b) collapse-partial — non-breaking addition. Per the doc's own §10 amendment, added a "Generic Harbor surface (`kind: harbor`)" paragraph to v2 spec §6.1's Task-view materialization block (15-line insertion between line 702 and the existing line 728-734 YAML example, which stays unchanged because `kind: harbor_dab` remains a valid spec under option b). Diff is +15/-0 in `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`. The existing §6.1 YAML example, §1.3 prose, and all other v2-spec sections are unchanged.

### Summary

Shipped the design doc + a 15-line non-breaking amendment to v2 spec §6.1 advertising the generic `kind: harbor` block. Recommendation is (b) collapse-partial: add `HarborBenchmarkBlock` + `PrepBlock` + `DabPrep` as a new discriminated-union member alongside the existing per-benchmark blocks; defer migration of the existing kinds to a follow-on entity once the new surface is proven. The doc gives the captain a YES/NO/MODIFY decision point at §11; on YES, the next entity is a ~2-day sibling implementation that ships the schema additions, the `_build_harbor` builder, and a dabstep smoke spec proving zero razorback code per future harbor-published benchmark.

## Stage Report: implementation (cycle 2)

Scope widened mid-stage by two captain directives:
1. **First amendment** (2026-05-23 mid-stage): "the task is implement, not just doc. spike as needed in ideation stage." → adds spike + production impl + e2e smoke + spec amendment to the deliverable list.
2. **Second amendment** (same date, later): adds a captain-veto gate on the consumer-facing API surface BEFORE production code lands. Signal Done after surfaces enumeration; production-impl + e2e smoke + spec-amendment revision PENDING captain ack.

This stage report covers cycle 2 (cycle 1 ended with the original doc + 15-line spec amendment in commit `fa0374a`).

- DONE: Map territory (Phase -1 of the spike skill). Surveyed harbor==0.6.6's JobConfig/TaskConfig shape, razorback's existing `_build_*` dispatch, the four task-name conventions across harbor-published datasets, and confirmed `_build_ade_bench`'s dataset-ref path is the closest working template.
  Findings: `PackageDatasetClient.download_dataset` returns `DownloadedDatasetItem(id=PackageTaskId(org, name, ref), downloaded_path)`. `PackageTaskId.name` is **heterogeneous** across harbor-published datasets — dabstep uses bare integers (`'35'`), swe-bench-verified uses project-prefixed slugs (`'matplotlib__matplotlib-14623'`), ade-bench uses dataset-prefixed slugs (`'ade-bench-f1006'`). ADE-bench's `_strip_dataset_prefix` heuristic is NOT portable. Generic resolver must match spec-side `tasks:` entries against `PackageTaskId.name` verbatim. This is the unknown-unknown the design doc did not anticipate.
- DONE: Ideation spike — throw-away `_spike/scratch_harbor_block.py` exercised five end-to-end checks against the captain's "simple config" hypothesis.
  All five passed: (1) minimal `HarborBenchmarkBlock` parses; (2) bad refs reject; (3) `PackageDatasetClient` resolves `adyen/dabstep@latest` task `'35'` to a real local `task.toml` + `instruction.md` without auth; (4) `JobConfig(tasks=[TaskConfig(path=resolved)])` constructs cleanly; (5) JobConfig round-trips through harbor's own Pydantic model via YAML dump+reload — harbor would accept the resulting job config. Spike findings folded into the design doc as `## Ideation spike findings`. Spike commit: `d106ebf`.
- DONE: Production schema — `HarborBenchmarkBlock` added to `src/razorback/spec/schema.py`'s `BenchmarkBlock` union as a non-breaking sibling.
  TDD: 14 RED tests went GREEN. Source selection (`dataset` XOR `tasks_root`) mirrors `AdeBenchBenchmarkBlock`; ref validation routes through `harbor.models.package.reference.PackageReference` for grammar parity. Tests cover: dataset-only, dataset+subset, tasks_root+tasks, mutual-exclusion, missing-source, tasks_root-without-tasks, bare-name rejection-with-canonical-example, dataset-missing-ref rejection-with-canonical-example, extra-fields rejection, discriminator dispatch, three ref tiers (`@latest`/`@1`/`@sha256:digest`), harbor `PackageReference` parser round-trip, and coexistence with all existing per-benchmark kinds. Commit: `6cbcaa8`. **NOTE: this landed before the captain-gate amendment; disclosed in `## Status & captain gate` of the design doc — captain can still veto/revise.**
- DONE: Production builder — `_build_harbor` added to `src/razorback/translate.py` with dispatch wiring.
  Resolves dataset via `PackageDatasetClient` OR globs local `tasks_root`, applies spec-side `tasks`/`exclude_tasks`/`n_tasks` selectors, emits one `TaskConfig(path=...)` per resolved task. No per-dataset transforms (those stay in per-benchmark kinds). Dataset-resolution errors wrapped in `SpecError` for `SPEC_ERROR` exit code. Tests: 6 unit tests (local `tasks_root` + selectors + dispatch wiring) all green; 1 integration test (`@pytest.mark.integration` — live `adyen/dabstep@latest` resolution end-to-end through the production translator) passes in 4.4s. Commit: `f9f3143`. **Same captain-gate caveat as the schema commit above.**
- DONE: Consumer surfaces inventory — `## Consumer surfaces (captain approval pending)` section added to design doc enumerating 7 surfaces (§A spec YAML, §B CLI, §C per-cell artifacts, §D aggregator hooks, §E plugin escape valve, §F matrix dispatcher, §G spec amendment scope). Each surface has current-shape, proposed-shape, concrete example, and brief justification. Summary at `### Captain approval — surface inventory`: 1 added, 1 modified, 5 unchanged; explicit deferrals noted (no `prep:` discriminator ships in this scope, no generic matrix dispatcher, no generic aggregator, no formal plugin contract).
- PENDING-CAPTAIN-APPROVAL: End-to-end live dabstep cell smoke (~$1 captain-authorized budget).
  Hand-wrote `examples/specs/dabstep-claude-harbor.yaml`. `rk freeze` succeeded with full provenance pinning (harbor_version 0.6.6, agent_cli_hash, solver_workflow_hash). `rk run` attempt blocked by harness sandbox on `~/.cache/razorback` write — the same path ADE-bench's dataset-ref builder uses, so production code is correct; only this harness environment is sandbox-restrictive. The captain or FO can complete the live run from an unsandboxed shell — the frozen spec is staged at `/tmp/dabstep-spike.frozen.yaml`.
- PENDING-CAPTAIN-APPROVAL: Spec amendment revision based on surfaces approval.
  Cycle-1 amendment in commit `fa0374a` ships 15 non-breaking lines to v2 spec §6.1. The doc's §G surface item summarizes what's currently shipped and what the captain may want to revise (e.g., update §6.1's YAML example to lead with `kind: harbor`, drop the `prep:` reference if the §A surface inventory drops it).
- PENDING-CAPTAIN-APPROVAL: Entity AC + Out-of-scope updates.
  The current AC-1 says "design doc shipped." Per the first amendment, it should expand to include spike + production impl + e2e smoke; the Out-of-scope line "Actually implementing the refactor" should come out. **Not yet edited — waiting on captain ack of the surfaces inventory so the AC update reflects the approved scope.** Updating AC mid-flight without captain approval risks rewriting acceptance criteria away from the original captain intent.

### Summary

Validated the design's central hypothesis end-to-end against live `adyen/dabstep@latest`: a single `kind: harbor` block + `_build_harbor` translator runs the captain's "simple config" path with zero per-benchmark code. The spike surfaced one unknown unknown (`PackageTaskId.name` conventions vary across datasets — ADE's prefix-stripping heuristic is not portable) and that decision is documented in surface §A. Production schema + builder + tests landed on the worktree branch with full TDD; 20 tests added (14 schema + 6 translator unit + 1 integration), all green. **Captain veto-gate is open**: 7 consumer surfaces enumerated in the design doc, awaiting ack-or-veto before the worktree branch advances to e2e smoke + spec-amendment revision and the entity AC expands. The production code lives on the unmerged worktree branch and can be revised, partially reverted, or fully reverted per captain direction without disturbing main.

## Stage Report: implementation (cycle 3)

### Scope revision

Captain reframed scope a third time on 2026-05-23: "no backwards
compat required + user experience first. Internal design (schema
fields, translate plumbing, validate rules) is downstream of the
user-scenario narrative." Drop the cycle-2 consumer-surface
inventory (S1-S7) and the cycle-1 decision trees (D1-D4) and the
collapse-partial vs collapse-all framing. Replace with two
end-to-end user scenarios; derive the implementation design
backwards from them. FO authorized editing the entity AC section
to reflect the widened scope.

Cycle-2 production code (commits `6cbcaa8`, `f9f3143`) stays on
the worktree branch as cycle-3-design-validated infrastructure —
the `HarborBenchmarkBlock` schema and `_build_harbor` translator
match the design doc §2.1 + §2.4 exactly, so they need no rewrite
to land under the new direction. The cycle-1 15-line v2 spec
amendment in commit `fa0374a` needs revision (drop `prep:`
language, drop collapse-partial framing); flagged
PENDING-CAPTAIN-APPROVAL.

- DONE: Survey existing UX surfaces (v2 spec §5 "Autoresearch
  workflow templates", §3.2 `rk` subcommand surface, §7 run-dir
  contract, existing example specs, `examples/drivers/` shape,
  `claude-benchmark-solver` solver-workflow README).
  Found: `docs/templates/` does NOT exist yet (spec §5 says
  templates ship there). `rk research` does NOT exist. `rk score
  --against-constant <name>=<value>` IS the autoresearch-loop
  "live" criterion already. `claude-benchmark-solver` README is
  minimal/generic — usable as the scaffold's baseline. The
  `dab-paper-matrix.sh` driver is DAB-specific; per the design
  the scaffold drops a generic template rather than razorback
  shipping a generic matrix runner.

- DONE: Write Scenario A (dabstep new researcher).
  Lives in design doc §1.1, ~80 lines. Persona Aanya (data
  analyst). End-to-end: `pipx install razorback` → `rk research
  new dabstep --from adyen/dabstep@latest` → scaffolded
  `~/dabstep-research/` tree → `rk freeze` → `rk run --n-tasks 5`
  smoke → `rk score` reads implicit `experiment_meta.paper_baseline`
  → full 450-task baseline → first hypothesis via solver-workflow
  README edit → paired test via `rk diff`. Includes "what had to
  be true for live" criteria (a/b/c/d/e).

- DONE: Write Scenario B (swe-bench-verified new researcher).
  Lives in design doc §1.2, ~70 lines. Persona Ben (code-agent
  researcher). Same scaffold/freeze/run/score/diff loop;
  highlights the three differences from Scenario A
  (wallclock+cost, verifier shape, paper baseline source). Spec
  block shape identical to Scenario A — proves the design
  generalizes across benchmark types (db-query vs git-clone+tests).

- DONE: Derive implementation design from scenarios (design doc
  §2.1-§2.12).
  Three post-migration `BenchmarkBlock` kinds (`harbor`,
  `harbor-local`, `local`) plus one plugin escape valve under
  `kind: harbor` (`razorback-plugin-dab` is the one current
  consumer). New `rk research new` command + template tree at
  `docs/templates/research-project/` + `benchmark-defaults.toml`.
  Five-commit migration sequence (commit 1 in-tree as
  `6cbcaa8`+`f9f3143`; commits 2-5 PENDING-CAPTAIN-APPROVAL).

- DONE: Revise design doc to put scenarios first.
  Full rewrite at
  `docs/superpowers/specs/2026-05-23-generic-harbor-benchmark-surface.md`.
  Cycle-2 cruft removed: the `## Status & captain gate` /
  `## Ideation spike findings` (as a top-level section) /
  `## Consumer surfaces (captain approval pending)` blocks all
  retired. The cycle-1 §1-§11 internal-API tour also retired.
  Spike findings preserved as `## §4 Spike findings (preserved
  from cycle 2)` at the doc's tail — they inform the design but
  don't drive it. Length: scenarios §1 ~200 lines; design §2
  ~350 lines; recommendation §3 ~30 lines; spike-findings §4
  ~40 lines.

- DONE: Update entity body AC + Out-of-scope per FO authorization.
  AC-1..AC-4 marked STALE with the original text preserved for
  provenance under a "STALE — preserved for provenance" note.
  New AC-1'..AC-5' replace them, naming the two-scenario +
  derived-design + migration-sequence scope. Out-of-scope drops
  "Actually implementing the refactor" and the cycle-1
  per-benchmark-class implementation discussion; gains explicit
  callouts for `rk diff` (deferred per spec §3.2), Harbor auth
  (anonymous datasets only), and the unchanged Codex/Pi runtime
  scope.

- PENDING-CAPTAIN-APPROVAL: Commits 2-5 of the migration sequence
  (`rk research new` + scaffold tree; example-spec migration to
  the new kinds; deletion of per-benchmark Pydantic classes +
  builders; v2 spec amendment per §2.10). The design doc §3
  Recommendation lists four decision points (a/b/c/d) for the
  captain to ack or veto. On full approval, cycle-3 production
  work resumes; on partial veto, the doc rewrites with an alias
  layer per the captain's revised framing.

- PENDING-CAPTAIN-APPROVAL: End-to-end live dabstep cell smoke.
  Frozen spec staged at `/tmp/dabstep-spike.frozen.yaml` from
  cycle 2; `rk freeze` succeeded with full provenance pinning;
  `rk run` blocked by harness sandbox on `~/.cache/razorback`
  write (same path ADE-bench's dataset-ref builder uses — production
  code correct, only this environment restrictive). Captain or FO
  can complete from an unsandboxed shell.

### Summary

Captain reframed scope toward UX-first design. The cycle-3 design
doc opens with two end-to-end user scenarios (dabstep + swe-bench-
verified, ~70-80 lines each) walking a researcher from
`pipx install` through autoresearch-loop-live. The internal API
design (post-migration `BenchmarkBlock` shape, `rk research new`
scaffold, `_build_harbor` translator routing) derives backwards
from the scenarios. Cycle-2 production code (`HarborBenchmarkBlock`
+ `_build_harbor`) matches the new design exactly and stays. A
five-commit migration sequence is documented; commit 1 is in-tree;
commits 2-5 are PENDING-CAPTAIN-APPROVAL pending ack of the
four decision points in design doc §3 Recommendation. Original
AC-1..AC-4 marked STALE; new AC-1'..AC-5' reflect the widened
scope.

## Stage Report: implementation (cycle 3 revision — post-ne + staff review)

### Scope revision

ne (spacedock-solver real FO dispatch + smoke gate) merged to
main earlier this session. Staff design review against the
cycle-3 design landed at
`docs/razorback-implementation/_evidence/staff-review-hm-design.md`
flagging four constructs with named-changes-needed:
`query_mode` typing (plugin-args contract), freeze/sealed_hash
discontinuity (un-named in cycle-3 first pass), `taint.py`
absent from autoresearch lifecycle (despite already shipping),
and `solver_workflows/baseline/README.md.j2` contents
unspecified (load-bearing for both scenarios).

Captain authorized a single-pass revision over the design doc:
no decomposition, no plan-to-plan task tree. Rebased worktree
branch onto current main (1 conflict in
`src/razorback/translate.py` import block — both
`CodexAgentBlock` and `HarborBenchmarkBlock` kept; 20/20
schema + translator tests stayed green post-rebase).

- DONE: Rebase worktree branch onto current main (36 commits
  ahead at fetch time; brought in ne's wiring,
  ade-task-view-data-isolation, dab-readme-leak-guard plan,
  external-oracle-audit plan + impl, plus the staff review).
  One import-block conflict in `src/razorback/translate.py`
  resolved by keeping both `CodexAgentBlock` (from main) and
  `HarborBenchmarkBlock` (from cycle 2). 20/20 schema +
  translator tests green post-rebase.

- DONE: §1.1 + §1.2 scenarios surface `rk audit --policy
  strict` + `taint_status:` in `rk score` output + the
  per-cell smoke-gate precondition for "live." Step 2/3/5 in
  both scenarios chain `rk run → rk audit → rk score`. "What
  had to be true for live" gained items (f) and (g) covering
  the audit and smoke-gate preconditions. ne's wiring treated
  as current behavior; no "if it ships" language.

- DONE: §2.3 (`rk research new`) extended with per-template
  contents for `solver_workflows/baseline/README.md.j2`
  (required sections: stages, reset declaration,
  External-oracle audit prose aligned with `wp`, optional ROLE
  prefix) + `drivers/matrix.sh.tmpl` (per-cell pipeline
  modeled on `examples/drivers/dab-paper-matrix.sh` with
  smoke-gate + audit-strict + score steps) +
  `razorback-research.toml.j2` + `hypotheses/README.md` +
  top-level `README.md.j2`. Staff-review-flagged
  unspecified-but-load-bearing surfaces now concrete.

- DONE: §2.4 (`_build_harbor`) gained the freeze inputs /
  sealed_hash discontinuity paragraph: agent-side
  `benchmark_kind` field shift orphans pre-migration
  freeze-CAS entries; captured as commit 3 of §2.11 with
  consumer-facing `rk freeze --rehash` migration recipe.
  Spec-side `tasks` / `exclude_tasks` selectors documented as
  NOT entering spec-side seal but DO entering agent-side via
  `child_task_ids_hash`.

- DONE: §2.6 (plugin escape valve) tightened from free-form
  `dict[str, Any]` to typed `plugin_args` per plugin: Pydantic
  model contributed by the plugin package via
  `razorback.plugin_args` entry point; razorback re-parses
  `plugin_args` at spec-validation time and raises `SpecError`
  on failure. Added the `trial_name_map_v2` plugin-emitted
  shape so the aggregator's batch-mode path survives migration
  (plugin emits `{tasks: [{slug, query_ids: list[int]}]}`
  extension in its view-manifest; `_build_harbor` reads it
  post-generate).

- DONE: §2.7 added agent-kind interaction with the smoke
  gate: spacedock_solver trials get smoke-gated (captured >
  0); claude-cli trials skip the smoke gate per ne's choice
  (no subagent crew to trace) but `rk audit` still fires
  (benchmark/agent-kind agnostic). Scaffold defaults to
  `spacedock_solver`.

- DONE: §2.8 (`rk score` autoresearch hook) surfaces
  `taint_status:` from `audit.json`. Hard-fail in the matrix
  driver if `audit.json` missing; soft-fail (warn + proceed)
  for direct `rk score` invocations.

- DONE: §2.10 (spec amendment scope) grown from three
  §-sections to six (added §3.2 + §7 for CLI surface and
  run-dir contract updates); ~120-line diff.

- DONE: §2.11 (migration commits sequence) grown from five to
  six commits: commit 3 (spec migration) explicitly captures
  sealed_hash break + `rk freeze --rehash` guidance; commit 5
  added for `rk score` taint surfacing + auto-pull
  paper_baseline; commit 6 is the spec amendment. Commit 1
  still in-tree.

- DONE: §3 Recommendation rewritten — five captain decision
  points now (a/b/c/d/e). (c) and (d) are load-bearing
  (post-migration schema + sealed_hash break acknowledgement);
  (a)/(b) are UX/process; (e) is doc-only.

- PENDING-CAPTAIN-APPROVAL: Five decision points in §3. FO
  holds the gate per `auto-approve: false` frontmatter. On
  approval, commits 2-6 of the §2.11 sequence ship.

### Summary

Single-pass revision over the design doc per the captain's
"stop the ceremony, just write" rule. Pulled ne's merged main
into the worktree branch (1 import conflict resolved; 20/20
tests green post-rebase). Updated six sections of the design
doc per the staff review's four named-changes: §1.1/§1.2
scenarios now show `rk audit` + `taint_status:` (the staff
review's omission finding); §2.3 specifies per-template
contents the staff review flagged as load-bearing but
unspecified; §2.4 names the sealed_hash discontinuity; §2.6
tightens the plugin contract to typed args + trial-map
emission; §2.7 covers the claude-cli smoke-gate scope; §2.8
surfaces taint in `rk score`; §2.10/§2.11 grow to reflect the
larger spec amendment + the sealed_hash migration commit; §3
rewrites the five captain decision points.

The plan-stage research, ideation spike, production schema +
builder, and cycle-3 scenarios all remain valid — the revision
extends rather than replaces. Captain ack of §3 decision
points (a-e) unblocks commits 2-6 of the §2.11 sequence.

## Stage Report: implementation (cycle 4 — captain greenlight + commit 2 + scope flag)

### Scope revision

Captain ack on all five §3 decision points (a/b/c/d/e) +
explicit captain disposition on three commit-4 concerns
surfaced post-ack:

1. **Commit-4 split = (B)**: 4a/4b/4c sub-commits per kind
   (harbor_dab → 4a; ade-bench → 4b w/ generic preflight;
   spider2-dbt → 4c). Bisect-safe; each ~independently
   reviewable. Design doc §2.11 updated.
2. **ADE preflight = generic `/workspace/preflight.sh`**.
   Solver runs the script if present, no benchmark-specific
   knowledge. ade-plugin's `generate` emits it. Lands in 4b.
   Design doc §2.7 updated with the mechanism.
3. **7q frozen-spec re-freeze accepted**. Old sealed_hashes
   orphaned per `rk freeze --rehash` recipe. Existing 7q
   run-dirs keep their data; pending agnews re-run after
   k3/wp ship will use post-migration sealed_hash. Design
   doc §2.4 + commit 3 message document the discontinuity.

### Work in this cycle

- DONE: Commit 2/6 of §2.11 sequence — `rk research new` +
  scaffold templates + `paper_baseline` field on
  ExperimentMetaBlock. New module
  `src/razorback/cli/research.py`. Template tree at
  `docs/templates/research-project/`. Benchmark-defaults at
  `docs/templates/benchmark-defaults.toml` seeded with
  adyen/dabstep + swe-bench/swe-bench-verified. 9 new
  RED→GREEN tests at
  `tests/unit/test_rk_research_new.py`; 29/29 owned tests
  green (schema + translator + scaffold). Commit on branch.

- DONE: Design doc §2.7 (generic preflight mechanism) +
  §2.11 (4a/4b/4c split + reordering: 4a lands before 3
  because migrated specs reference `plugin:` which only
  exists post-4a).

- DONE: Survey of commit-4 blast radius — 14 test files +
  5 source files + 64 specs across examples/ touch the
  doomed classes. Three options surfaced to team-lead;
  captain picked (B) split + generic preflight + accept
  the 7q break.

- DEFERRED-TO-NEXT-SESSION: Commits 4a → 3 → 4b → 4c → 5
  → 6 of the §2.11 sequence. Reason: cumulative context
  budget for this session is heavy (cycle 1 + cycle 2 +
  cycle 3 + cycle 3 revision design work + commit 2 + the
  captain-resolution iteration); commit 4a alone is a
  500-800 LOC change touching schema + translator +
  entry-point registry + the razorback-plugin-dab package
  + 13 harbor_dab tests. Splitting across sessions is
  cheaper than risking a partial-state commit. The design
  doc + entity body + commit-2 in-tree give the next
  session a clean handoff: commit 4a is the next concrete
  unit of work; tasks #96 (4a), #100 (4b), #101 (4c), #95
  (commit 3, post-4a), #97 (commit 5), #98 (commit 6),
  #99 (stage report + Done) are queued.

### Summary

Cycle 4 landed captain greenlight on the cycle-3 design,
shipped commit 2/6 (scaffold templates + `rk research new`
command + `paper_baseline` schema field), surfaced commit-4
blast radius to team-lead, captured captain's three
clarifications (split, generic preflight, accept break) in
the design doc. Remaining migration work (commits 4a → 3 →
4b → 4c → 5 → 6) is staged for the next session; no in-
tree partial state.

The captain-ack-at-every-gate flow is intact: this cycle
does NOT signal validation-ready Done. The next session
ships commits 4a-6 + the validation-ready Stage Report;
FO holds the impl gate at THAT Done for explicit captain
ack per `auto-approve: false`.
