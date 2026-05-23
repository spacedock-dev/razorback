# DAB consumes Harbor dataset definitions — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the wrapped DAB benchmark consume a Harbor-style dataset definition as its source
of truth — same shape ADE-Bench will consume `ade-bench@1.0` (sibling entity
`ade-bench-harbor-dataset-ref`). The DAB benchmark identity (which tasks exist, their strata,
which variants ship) lives in a `dataset.toml` shipped by the `razorback-plugin-dab` package;
`data_root` stays as an adapter/materialization input only.

**Architecture:** A new `dataset.toml` in `packages/razorback-plugin-dab/src/razorback_plugin_dab/`
becomes the single source of truth for the 12-dataset DAB inventory + variant catalog. The
existing `datasets.py` becomes a thin loader. `HarborDabBenchmarkBlock` grows a `dataset:` field
(e.g. `dataset: dab@1.0`) that names the dataset def; when set, `datasets:` / `workspace_variant`
become *task selectors over the def*, and `data_root` is purely a materialization input (env
default `${DATAAGENTBENCH_DATA_ROOT:-~/dataagentbench/data}`). The Goal 1 generator
(`examples/drivers/generate-dab-paper-matrix-specs.py`) reads task ids from the def. The
in-tree `kind: dab` path (legacy `DabBenchmarkBlock` + `src/razorback/benchmarks/dab/prepare.py`)
is marked dev-only with a deprecation warning; canonical DAB is the plugin-backed `harbor_dab`
path. Old `harbor_dab` specs lacking `dataset:` keep working behind an explicit compatibility
branch (AC-2 requirement).

**Tech Stack:** Python 3.12, pydantic v2, tomllib (stdlib), pytest, uv. Razorback core in
`src/razorback/`, plugin in `packages/razorback-plugin-dab/`, examples in `examples/`.

---

## AC ↔ task map

| AC | Task(s) |
|---|---|
| AC-1 — DAB has a Harbor-style dataset definition source of truth | Task 1 (dataset.toml + loader), Task 2 (parser tests) |
| AC-2 — Razorback DAB specs can consume that definition | Task 3 (schema `dataset:` field), Task 4 (translator wiring), Task 5 (compat branch for old specs) |
| AC-3 — Goal 1 generation reads the dataset definition | Task 6 (generator switch), Task 7 (round-trip test against fixture) |
| AC-4 — Scoring consumes adapter-provided strata | Task 8 (stratum from def), Task 9 (aggregate-goal1 reads def) |
| AC-5 — Old DAB adapter split is reduced | Task 10 (deprecate `kind: dab`), Task 11 (validation report cite of remaining entry points) |

**Spec §-cites:** §6.1 (benchmark block translation contract) governs Tasks 3–5. §6.5 (DAB
stratified pass@1) governs Tasks 8–9. §1.3 ("Razorback ships no adapter") governs Task 10 —
the plugin remains the adapter, the in-tree path was always a v1 holdover.

---

## File Structure

**New files:**

- `packages/razorback-plugin-dab/src/razorback_plugin_dab/dataset.toml` — the dataset
  definition itself. Shipped inside the package, loaded at import. Contents: dataset name +
  version + description, per-dataset entries with `name/backends/query_ids/schema_version`,
  workspace-variant catalog (`direct-minimal/direct-structured/spacedock`).
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/dataset_def.py` — pydantic model +
  loader. `DabDatasetDefinition` carries the parsed shape; `load_default_definition()` reads
  the package-shipped `dataset.toml`; `load_definition_from(path)` reads an arbitrary file
  (for fixtures + tests).
- `packages/razorback-plugin-dab/tests/unit/test_dataset_definition.py` — parser tests
  (Task 2).
- `tests/unit/test_harbor_dab_dataset_ref.py` — razorback-core schema + translator tests
  for the new `dataset:` field (Tasks 3–4).
- `tests/unit/test_generate_dab_paper_matrix_from_definition.py` — generator round-trip
  test against a fixture def (Task 7).
- `tests/unit/test_aggregate_goal1_from_definition.py` — aggregator reads def for stratum
  enumeration (Task 9).
- `tests/fixtures/dab_dataset_minimal.toml` — 2-dataset minimal fixture for generator and
  aggregator round-trip tests.

**Modified files:**

- `packages/razorback-plugin-dab/src/razorback_plugin_dab/datasets.py` — becomes a thin
  shim that re-exports `DAB_DATASETS` derived from `load_default_definition()`. Keeps
  `DabDataset` dataclass and `by_name()` so existing callers (the plugin's `cli.py`,
  `generate/prepare.py`) keep working unchanged.
- `packages/razorback-plugin-dab/pyproject.toml` — add `dataset.toml` to
  `tool.hatch.build.targets.wheel` / package-data so it ships with the package.
- `src/razorback/spec/schema.py:141-160` — add `dataset: str | None = None` to
  `HarborDabBenchmarkBlock`; relax `datasets: list[str]` to allow empty when `dataset:` is
  set; add a `model_validator` enforcing the new shape.
- `src/razorback/translate.py:376-465` — `_build_harbor_dab` reads the dataset def when
  `dataset:` is set; resolves task selection through it before invoking the plugin
  subprocess.
- `examples/drivers/generate-dab-paper-matrix-specs.py:14-65` — replace `DAB_DATASETS`
  import with `load_default_definition()`; spec construction names `dataset: dab@1.0`
  instead of `data_root + datasets + workspace_variant`.
- `examples/drivers/aggregate-goal1-scores.py:13-75` — read stratum enumeration from
  `load_default_definition()` rather than `DAB_DATASETS` (transitively the same after
  Task 1, but the explicit dependency is what AC-4 requires).
- `src/razorback/spec/parse.py:13-18` — extend `_BENCHMARK_KIND_ALIASES` docstring noting
  `kind: dab` is now dev-only.
- `src/razorback/benchmarks/dab/prepare.py` — emit a `DeprecationWarning` on first call
  pointing at `harbor_dab` as the canonical path (Task 10).

**Out of touch:**

- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py` — the
  per-task generator stays unchanged (the plugin subprocess interface is the boundary).
- `src/razorback/benchmarks/dab/aggregate.py` — `_build_summary` already derives strata
  from the trial outcomes, not from `DAB_DATASETS`. No change needed (verified by reading
  the file).
- Harbor's `Registry` / `DatasetSpec` (in `.venv`) — we do NOT register DAB in Harbor's
  central `registry.json`. Reason: DAB tasks are *generated* (per-`data_root`), not
  source-controlled `GitTaskId` / `LocalTaskId` entries, so the Harbor `Registry` shape
  doesn't fit. The DAB `dataset.toml` is a *parallel* Harbor-style definition that the
  plugin owns. The sibling entity `ade-bench-harbor-dataset-ref` uses Harbor's actual
  `Registry` because ADE tasks are published `PackageTaskId`s. This asymmetry is
  intentional — confirmed by the entity's Notes section ("don't remove the need for
  local DAB data when materializing").

---

## Task 1: Ship the `dataset.toml` source of truth + loader (AC-1)

**Files:**
- Create: `packages/razorback-plugin-dab/src/razorback_plugin_dab/dataset.toml`
- Create: `packages/razorback-plugin-dab/src/razorback_plugin_dab/dataset_def.py`
- Modify: `packages/razorback-plugin-dab/src/razorback_plugin_dab/datasets.py`
- Modify: `packages/razorback-plugin-dab/pyproject.toml`

- [ ] **Step 1.1: Write the failing test for the loader**

Create `packages/razorback-plugin-dab/tests/unit/test_dataset_definition.py`:

```python
# ABOUTME: AC-1 — DAB dataset definition parses from dataset.toml.
# ABOUTME: Verifies inventory, variant catalog, and round-trip with the 12-dataset shape.

from razorback_plugin_dab.dataset_def import (
    DabDatasetDefinition,
    load_default_definition,
)


def test_default_definition_loads():
    definition = load_default_definition()
    assert isinstance(definition, DabDatasetDefinition)
    assert definition.name == "dab"
    assert definition.version == "1.0"


def test_default_definition_has_twelve_datasets():
    definition = load_default_definition()
    names = {d.name for d in definition.datasets}
    expected = {
        "agnews", "bookreview", "crmarenapro", "DEPS_DEV_V1",
        "GITHUB_REPOS", "googlelocal", "music_brainz_20k",
        "PANCANCER_ATLAS", "PATENTS", "stockindex", "stockmarket",
        "yelp",
    }
    assert names == expected


def test_default_definition_lists_workspace_variants():
    definition = load_default_definition()
    assert set(definition.workspace_variants) == {
        "direct-minimal", "direct-structured", "spacedock",
    }


def test_bookreview_metadata_round_trip():
    definition = load_default_definition()
    ds = definition.get_dataset("bookreview")
    assert ds.backends == ("postgres", "sqlite")
    assert ds.query_count == 3
    assert ds.query_ids == (1, 2, 3)
    assert ds.schema_version == "v1"


def test_query_ids_match_query_count_for_all_datasets():
    definition = load_default_definition()
    for ds in definition.datasets:
        assert len(ds.query_ids) == ds.query_count, (
            f"{ds.name}: query_ids length {len(ds.query_ids)} != query_count {ds.query_count}"
        )
```

- [ ] **Step 1.2: Run test to verify it fails**

```
uv run pytest packages/razorback-plugin-dab/tests/unit/test_dataset_definition.py -v
```
Expected: FAIL with `ModuleNotFoundError: razorback_plugin_dab.dataset_def`.

- [ ] **Step 1.3: Create the `dataset.toml` source of truth**

Create `packages/razorback-plugin-dab/src/razorback_plugin_dab/dataset.toml`:

```toml
# DAB dataset definition — Harbor-style identity + inventory for the 12 upstream DAB tasks.
# Source: /Users/clkao/git/dataagentbench/data/query_<name>/db_config.yaml.
# Local data_root materializes these tasks; this file IS the benchmark identity.

name = "dab"
version = "1.0"
description = "Data Agent Bench — 12 datasets, 12 backends, stratified pass@1 (paper baseline)."

workspace_variants = ["direct-minimal", "direct-structured", "spacedock"]

[[datasets]]
name = "agnews"
backends = ["mongo", "sqlite"]
query_count = 4
query_ids = [1, 2, 3, 4]
schema_version = "v1"

[[datasets]]
name = "bookreview"
backends = ["postgres", "sqlite"]
query_count = 3
query_ids = [1, 2, 3]
schema_version = "v1"

[[datasets]]
name = "crmarenapro"
backends = ["duckdb", "postgres", "sqlite"]
query_count = 13
query_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
schema_version = "v1"

[[datasets]]
name = "DEPS_DEV_V1"
backends = ["duckdb", "sqlite"]
query_count = 2
query_ids = [1, 2]
schema_version = "v1"

[[datasets]]
name = "GITHUB_REPOS"
backends = ["duckdb", "sqlite"]
query_count = 4
query_ids = [1, 2, 3, 4]
schema_version = "v1"

[[datasets]]
name = "googlelocal"
backends = ["postgres", "sqlite"]
query_count = 4
query_ids = [1, 2, 3, 4]
schema_version = "v1"

[[datasets]]
name = "music_brainz_20k"
backends = ["duckdb", "sqlite"]
query_count = 3
query_ids = [1, 2, 3]
schema_version = "v1"

[[datasets]]
name = "PANCANCER_ATLAS"
backends = ["duckdb", "postgres"]
query_count = 3
query_ids = [1, 2, 3]
schema_version = "v1"

[[datasets]]
name = "PATENTS"
backends = ["postgres", "sqlite"]
query_count = 3
query_ids = [1, 2, 3]
schema_version = "v1"

[[datasets]]
name = "stockindex"
backends = ["duckdb", "sqlite"]
query_count = 3
query_ids = [1, 2, 3]
schema_version = "v1"

[[datasets]]
name = "stockmarket"
backends = ["duckdb", "sqlite"]
query_count = 5
query_ids = [1, 2, 3, 4, 5]
schema_version = "v1"

[[datasets]]
name = "yelp"
backends = ["duckdb", "mongo"]
query_count = 7
query_ids = [1, 2, 3, 4, 5, 6, 7]
schema_version = "v1"
```

> Note: `query_ids` must be confirmed against
> `/Users/clkao/git/dataagentbench/data/query_<name>/query*/`. If a dataset has
> non-contiguous query ids (e.g. some upstream renames skip numbers), the
> implementer must list the actual ids on disk. Step 1.6 verifies this — if it
> fails, fix `dataset.toml` to match what the in-tree adapter currently emits.

- [ ] **Step 1.4: Create the loader**

Create `packages/razorback-plugin-dab/src/razorback_plugin_dab/dataset_def.py`:

```python
# ABOUTME: DAB dataset definition loader — pydantic shape for dataset.toml.
# ABOUTME: Used by Razorback core (translator + generator) as the source of truth for AC-1..AC-5.

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class DabDatasetEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    backends: tuple[str, ...]
    query_count: int = Field(ge=1)
    query_ids: tuple[int, ...]
    schema_version: str = "v1"


class DabDatasetDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    version: str
    description: str = ""
    workspace_variants: tuple[str, ...]
    datasets: tuple[DabDatasetEntry, ...]

    def get_dataset(self, name: str) -> DabDatasetEntry:
        for d in self.datasets:
            if d.name == name:
                return d
        raise KeyError(f"unknown DAB dataset: {name!r}")

    @property
    def ref(self) -> str:
        return f"{self.name}@{self.version}"


def load_definition_from(path: Path) -> DabDatasetDefinition:
    raw = tomllib.loads(Path(path).read_text())
    return DabDatasetDefinition.model_validate(raw)


def load_default_definition() -> DabDatasetDefinition:
    pkg_files = resources.files("razorback_plugin_dab")
    toml_path = pkg_files / "dataset.toml"
    with resources.as_file(toml_path) as concrete:
        return load_definition_from(Path(concrete))
```

- [ ] **Step 1.5: Make `pyproject.toml` ship `dataset.toml`**

Modify `packages/razorback-plugin-dab/pyproject.toml`. Find the build section
(`[tool.hatch.build.targets.wheel]` or equivalent — read the file first). Add
the toml file to the include list:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/razorback_plugin_dab"]

[tool.hatch.build.targets.wheel.shared-data]
"src/razorback_plugin_dab/dataset.toml" = "razorback_plugin_dab/dataset.toml"
```

> If the file already uses `setuptools` or a different layout, follow that
> layout's convention. The goal is: `dataset.toml` ships *inside* the installed
> `razorback_plugin_dab` package so `importlib.resources.files(...)` finds it.

- [ ] **Step 1.6: Run the test to verify it passes**

```
uv run pytest packages/razorback-plugin-dab/tests/unit/test_dataset_definition.py -v
```
Expected: all 5 tests PASS. If `test_query_ids_match_query_count_for_all_datasets` fails
for one dataset, the upstream query dir layout has a gap — re-read
`/Users/clkao/git/dataagentbench/data/query_<dataset>/` and update `dataset.toml`'s
`query_ids` for that entry only.

- [ ] **Step 1.7: Rewire `datasets.py` to read from the definition**

Replace `packages/razorback-plugin-dab/src/razorback_plugin_dab/datasets.py` with:

```python
# ABOUTME: DAB dataset catalog — thin loader over dataset.toml (the Harbor-style def).
# ABOUTME: Preserves DabDataset dataclass + by_name() for legacy callers.

from __future__ import annotations

from dataclasses import dataclass

from razorback_plugin_dab.dataset_def import load_default_definition


@dataclass(frozen=True)
class DabDataset:
    name: str
    backends: tuple[str, ...]
    query_count: int
    schema_version: str = "v1"


def _build_catalog() -> tuple[DabDataset, ...]:
    definition = load_default_definition()
    return tuple(
        DabDataset(
            name=d.name,
            backends=d.backends,
            query_count=d.query_count,
            schema_version=d.schema_version,
        )
        for d in definition.datasets
    )


DAB_DATASETS: tuple[DabDataset, ...] = _build_catalog()


def by_name(name: str) -> DabDataset:
    for d in DAB_DATASETS:
        if d.name == name:
            return d
    raise KeyError(f"unknown DAB dataset: {name!r}")
```

- [ ] **Step 1.8: Run the existing catalog tests to verify nothing broke**

```
uv run pytest packages/razorback-plugin-dab/tests/unit/test_datasets_catalog.py -v
```
Expected: all 6 tests PASS. The test file at lines 7-44 verifies the exact same
inventory; if a query_count mismatches, fix `dataset.toml` (not the test).

- [ ] **Step 1.9: Commit**

```
git add packages/razorback-plugin-dab/src/razorback_plugin_dab/dataset.toml \
        packages/razorback-plugin-dab/src/razorback_plugin_dab/dataset_def.py \
        packages/razorback-plugin-dab/src/razorback_plugin_dab/datasets.py \
        packages/razorback-plugin-dab/pyproject.toml \
        packages/razorback-plugin-dab/tests/unit/test_dataset_definition.py
git commit -m "feat: DAB dataset.toml + loader; datasets.py reads the definition (AC-1)"
```

---

## Task 2: AC-1 verification — no in-code catalog reads in tests (AC-1)

**Files:**
- Modify: `packages/razorback-plugin-dab/tests/unit/test_dataset_definition.py`

- [ ] **Step 2.1: Add the AC-1 `Verified by:` test**

Append to `packages/razorback-plugin-dab/tests/unit/test_dataset_definition.py`:

```python
def test_definition_drives_inventory_not_hardcoded_list():
    """AC-1 Verified by: 'tests parse the dataset definition and confirm the expected DAB
    task inventory and metadata without consulting hardcoded generated spec lists.'"""
    definition = load_default_definition()
    actual_query_count = sum(d.query_count for d in definition.datasets)
    # Paper baseline: 53 queries across 12 datasets. If the upstream layout
    # changes, this test catches it BEFORE the generator silently mis-counts.
    assert actual_query_count == 53
    assert len(definition.datasets) == 12
```

- [ ] **Step 2.2: Run test**

```
uv run pytest packages/razorback-plugin-dab/tests/unit/test_dataset_definition.py::test_definition_drives_inventory_not_hardcoded_list -v
```
Expected: PASS. If the count differs from 53, that's an upstream-data
discrepancy worth surfacing — re-verify against `data/query_*/query*/` dirs and
either fix `dataset.toml` or raise the discrepancy back to team-lead before
proceeding.

- [ ] **Step 2.3: Commit**

```
git add packages/razorback-plugin-dab/tests/unit/test_dataset_definition.py
git commit -m "test: AC-1 Verified-by check — definition drives inventory (53 queries / 12 datasets)"
```

---

## Task 3: Schema — `HarborDabBenchmarkBlock.dataset` field (AC-2)

**Files:**
- Create: `tests/unit/test_harbor_dab_dataset_ref.py`
- Modify: `src/razorback/spec/schema.py:141-160`

- [ ] **Step 3.1: Write the failing schema tests**

Create `tests/unit/test_harbor_dab_dataset_ref.py`:

```python
# ABOUTME: AC-2 — HarborDabBenchmarkBlock accepts dataset: <name>@<version> in place of data_root+datasets.
# ABOUTME: Old-shape specs still parse (compat). Mixed shapes raise.

from pathlib import Path

import pytest

from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text
from razorback.spec.schema import HarborDabBenchmarkBlock


def _spec(benchmark_yaml: str) -> str:
    return (
        "version: 1\n"
        "experiment: ac2-test\n"
        "agent:\n"
        "  kind: nop\n"
        f"benchmark:\n{benchmark_yaml}\n"
        "trials: 1\n"
    )


def test_harbor_dab_accepts_dataset_ref_without_data_root() -> None:
    spec = parse_spec_text(_spec(
        "  kind: harbor_dab\n"
        "  dataset: dab@1.0\n"
        "  workspace_variant: spacedock\n"
    ))
    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)
    assert spec.benchmark.dataset == "dab@1.0"
    assert spec.benchmark.datasets == []
    assert spec.benchmark.data_root is None


def test_harbor_dab_dataset_ref_with_subset() -> None:
    spec = parse_spec_text(_spec(
        "  kind: harbor_dab\n"
        "  dataset: dab@1.0\n"
        "  datasets: [bookreview, agnews]\n"
        "  workspace_variant: spacedock\n"
    ))
    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)
    assert spec.benchmark.dataset == "dab@1.0"
    assert spec.benchmark.datasets == ["bookreview", "agnews"]


def test_harbor_dab_legacy_shape_still_parses(tmp_path: Path) -> None:
    """AC-2 compat: old harbor_dab specs (no `dataset:`) keep working."""
    spec = parse_spec_text(_spec(
        "  kind: harbor_dab\n"
        f"  data_root: {tmp_path}\n"
        "  datasets: [bookreview]\n"
    ))
    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)
    assert spec.benchmark.dataset is None
    assert spec.benchmark.data_root == tmp_path


def test_harbor_dab_legacy_shape_requires_data_root_when_no_dataset_ref(
    tmp_path: Path,
) -> None:
    with pytest.raises(SpecError, match="(?i)data_root.*required"):
        parse_spec_text(_spec(
            "  kind: harbor_dab\n"
            "  datasets: [bookreview]\n"
        ))


def test_harbor_dab_rejects_unknown_dataset_ref_format() -> None:
    with pytest.raises(SpecError, match="(?i)dataset.*format"):
        parse_spec_text(_spec(
            "  kind: harbor_dab\n"
            "  dataset: dab-no-version\n"
        ))
```

- [ ] **Step 3.2: Run test to verify it fails**

```
uv run pytest tests/unit/test_harbor_dab_dataset_ref.py -v
```
Expected: 5 FAILs (likely ValidationError — `dataset` field unknown, or
data_root missing).

- [ ] **Step 3.3: Update the schema**

Replace `HarborDabBenchmarkBlock` in `src/razorback/spec/schema.py` (lines
141-160). Existing class definition is at line 141:

```python
class HarborDabBenchmarkBlock(BaseModel):
    """Phase 2 — DAB harbor adapter (sibling-package task generator).

    Translates in `rk run` to a subprocess invocation of
    `razorback-plugin-dab generate`, then a harbor `JobConfig` whose
    `tasks:` references the emitted task directories. Razorback core
    never imports from the plugin at runtime.

    `dataset:` (AC-2) names a Harbor-style dataset definition ref of the form
    `<name>@<version>`. When set, `data_root` becomes optional and falls back
    to the env-default at materialization time; `datasets:` is treated as a
    task-subset selector over the definition (empty = all datasets in the def).
    """
    model_config = ConfigDict(extra="forbid")
    kind: Literal["harbor_dab"]
    dataset: str | None = None
    data_root: Path | None = None
    datasets: list[str] = Field(default_factory=list)
    workspace_variant: Literal["direct-minimal", "direct-structured", "spacedock"] = "direct-minimal"
    hints: bool = False
    query_mode: Literal["batch", "per-query"] = "per-query"

    @field_validator("data_root", mode="before")
    @classmethod
    def _expand_data_root(cls, value: object) -> object:
        if value is None:
            return None
        return _expand_path(value)

    @field_validator("dataset")
    @classmethod
    def _validate_dataset_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if "@" not in value:
            raise ValueError(
                f"benchmark.dataset must be in the form '<name>@<version>'; "
                f"got dataset format {value!r}"
            )
        name, version = value.split("@", 1)
        if not name or not version:
            raise ValueError(
                f"benchmark.dataset must be '<name>@<version>' with non-empty parts; "
                f"got dataset format {value!r}"
            )
        return value

    @model_validator(mode="after")
    def _dataset_or_data_root(self) -> "HarborDabBenchmarkBlock":
        if self.dataset is None:
            # Legacy compat path: require data_root + datasets.
            if self.data_root is None:
                raise ValueError(
                    "benchmark.data_root is required when benchmark.dataset is not set"
                )
            if not self.datasets:
                raise ValueError(
                    "benchmark.datasets must be non-empty when benchmark.dataset is not set"
                )
        return self
```

- [ ] **Step 3.4: Run test to verify pass**

```
uv run pytest tests/unit/test_harbor_dab_dataset_ref.py -v
```
Expected: all 5 PASS.

- [ ] **Step 3.5: Run the existing `harbor_dab` block tests to confirm no regression**

```
uv run pytest tests/unit/test_spec_harbor_dab_block.py -v
```
Expected: all 9 existing tests still PASS. If the
`test_harbor_dab_block_parses_with_defaults` fails because the existing test
omits `data_root`, that means our `_dataset_or_data_root` validator broke
it — but the existing tests already supply `data_root: {tmp_path}`, so this
should be green. If it isn't, re-read the existing test file and adjust the
validator (not the test).

- [ ] **Step 3.6: Commit**

```
git add tests/unit/test_harbor_dab_dataset_ref.py src/razorback/spec/schema.py
git commit -m "feat: HarborDabBenchmarkBlock.dataset field — Harbor-style dataset ref (AC-2)"
```

---

## Task 4: Translator — resolve dataset ref before invoking plugin (AC-2)

**Files:**
- Modify: `src/razorback/translate.py:376-465` (`_build_harbor_dab`)
- Modify: `tests/unit/test_harbor_dab_dataset_ref.py` (add translator-level test)

- [ ] **Step 4.1: Write the failing translator test**

Append to `tests/unit/test_harbor_dab_dataset_ref.py`:

```python
def test_translator_uses_dataset_ref_to_enumerate_datasets(
    tmp_path: Path, monkeypatch
) -> None:
    """When `dataset:` is set and `datasets:` is empty, the translator
    enumerates ALL datasets from the definition. Mock the plugin subprocess so
    we just observe the dataset list that was passed."""
    from razorback.spec.parse import parse_spec_text
    from razorback.translate import spec_to_job_config

    captured_datasets: list[str] = []

    def fake_run(cmd, capture_output, text):
        # Pull --datasets value out of the cmd.
        for i, arg in enumerate(cmd):
            if arg == "--datasets":
                captured_datasets.append(cmd[i + 1])
        # Emit a single empty task dir to satisfy translator iteration.
        out_idx = cmd.index("--out") + 1
        out_dir = Path(cmd[out_idx])
        out_dir.mkdir(parents=True, exist_ok=True)
        task_dir = out_dir / captured_datasets[-1]
        task_dir.mkdir(exist_ok=True)
        class R:
            returncode = 0
            stderr = ""
        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setenv(
        "DATAAGENTBENCH_DATA_ROOT", str(tmp_path / "fake-data"),
    )

    spec = parse_spec_text(
        "version: 1\n"
        "experiment: ac2-translator\n"
        "agent:\n  kind: nop\n"
        "benchmark:\n"
        "  kind: harbor_dab\n"
        "  dataset: dab@1.0\n"
        "  workspace_variant: spacedock\n"
        "  query_mode: batch\n"
        "trials: 1\n"
    )
    jobs_dir = tmp_path / "jobs"
    cfg, _ = spec_to_job_config(
        spec, job_name="j", jobs_dir=jobs_dir, tasks_root=tmp_path / "tr"
    )
    assert sorted(captured_datasets) == sorted([
        "agnews", "bookreview", "crmarenapro", "DEPS_DEV_V1",
        "GITHUB_REPOS", "googlelocal", "music_brainz_20k",
        "PANCANCER_ATLAS", "PATENTS", "stockindex", "stockmarket", "yelp",
    ])
```

- [ ] **Step 4.2: Run test to verify it fails**

```
uv run pytest tests/unit/test_harbor_dab_dataset_ref.py::test_translator_uses_dataset_ref_to_enumerate_datasets -v
```
Expected: FAIL — translator currently errors when `dataset:` is set but
`datasets:` is empty (or `data_root` is None).

- [ ] **Step 4.3: Update `_build_harbor_dab`**

In `src/razorback/translate.py`, modify `_build_harbor_dab` (starts at
line 376). At the top of the function, after the `assert isinstance(...)`
line, insert:

```python
    # AC-2: dataset ref resolution. If `dataset:` is set, the definition supplies
    # the dataset inventory; `benchmark.datasets` (if present) is a subset selector.
    # `data_root` falls back to env default — local data is still needed at
    # materialize time (per entity Notes).
    if spec.benchmark.dataset is not None:
        from razorback_plugin_dab.dataset_def import load_default_definition

        definition = load_default_definition()
        if definition.ref != spec.benchmark.dataset:
            raise SpecError(
                f"benchmark.dataset {spec.benchmark.dataset!r} does not match "
                f"the plugin's shipped definition {definition.ref!r}; "
                f"upgrade razorback-plugin-dab or pin the matching version."
            )
        if spec.benchmark.datasets:
            known = {d.name for d in definition.datasets}
            unknown = [d for d in spec.benchmark.datasets if d not in known]
            if unknown:
                raise SpecError(
                    f"benchmark.datasets subset references unknown DAB datasets "
                    f"{unknown!r}; definition {definition.ref} knows {sorted(known)}"
                )
            resolved_datasets = list(spec.benchmark.datasets)
        else:
            resolved_datasets = [d.name for d in definition.datasets]
        if spec.benchmark.data_root is not None:
            data_root = Path(spec.benchmark.data_root).resolve()
        else:
            import os
            env_default = os.environ.get(
                "DATAAGENTBENCH_DATA_ROOT",
                str(Path.home() / "dataagentbench" / "data"),
            )
            data_root = Path(env_default).expanduser().resolve()
    else:
        # Legacy compat path (AC-2 compat clause).
        resolved_datasets = list(spec.benchmark.datasets)
        data_root = Path(spec.benchmark.data_root).resolve()
```

Then replace the per-dataset loop's `for dataset in spec.benchmark.datasets:`
with `for dataset in resolved_datasets:`, and the
`--data-root str(Path(spec.benchmark.data_root).resolve())` arg with
`str(data_root)`. Other args (`--workspace-variant`, `--query-mode`, hints
flag) stay unchanged.

- [ ] **Step 4.4: Run translator test to verify pass**

```
uv run pytest tests/unit/test_harbor_dab_dataset_ref.py::test_translator_uses_dataset_ref_to_enumerate_datasets -v
```
Expected: PASS.

- [ ] **Step 4.5: Run existing translator tests to verify no regression**

```
uv run pytest tests/unit/test_translator_harbor_dab.py -v
```
Expected: all existing tests PASS. If anything broke, the existing tests rely
on `spec.benchmark.data_root` being non-None — fix the new branch (don't touch
the tests).

- [ ] **Step 4.6: Commit**

```
git add src/razorback/translate.py tests/unit/test_harbor_dab_dataset_ref.py
git commit -m "feat: translator resolves harbor_dab dataset ref against plugin definition (AC-2)"
```

---

## Task 5: Compat-path test — old `harbor_dab` specs route through the legacy branch (AC-2)

**Files:**
- Modify: `tests/unit/test_harbor_dab_dataset_ref.py`

- [ ] **Step 5.1: Write the failing compat test**

Append to `tests/unit/test_harbor_dab_dataset_ref.py`:

```python
def test_translator_legacy_shape_still_works(tmp_path: Path, monkeypatch) -> None:
    """AC-2 compat: old harbor_dab specs (no `dataset:`) still route through
    the translator without consulting the dataset definition."""
    from razorback.spec.parse import parse_spec_text
    from razorback.translate import spec_to_job_config

    seen_data_root: list[str] = []

    def fake_run(cmd, capture_output, text):
        for i, arg in enumerate(cmd):
            if arg == "--data-root":
                seen_data_root.append(cmd[i + 1])
        out_idx = cmd.index("--out") + 1
        out_dir = Path(cmd[out_idx])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "bookreview").mkdir(exist_ok=True)
        class R:
            returncode = 0
            stderr = ""
        return R()

    monkeypatch.setattr("subprocess.run", fake_run)

    fake_data = tmp_path / "fake-data"
    fake_data.mkdir()
    spec = parse_spec_text(
        "version: 1\n"
        "experiment: ac2-legacy\n"
        "agent:\n  kind: nop\n"
        "benchmark:\n"
        "  kind: harbor_dab\n"
        f"  data_root: {fake_data}\n"
        "  datasets: [bookreview]\n"
        "  query_mode: batch\n"
        "trials: 1\n"
    )
    spec_to_job_config(
        spec, job_name="j", jobs_dir=tmp_path / "jobs", tasks_root=tmp_path / "tr",
    )
    assert seen_data_root == [str(fake_data.resolve())]
```

- [ ] **Step 5.2: Run test**

```
uv run pytest tests/unit/test_harbor_dab_dataset_ref.py::test_translator_legacy_shape_still_works -v
```
Expected: PASS (the legacy branch in Task 4 already handles this).

- [ ] **Step 5.3: Commit**

```
git add tests/unit/test_harbor_dab_dataset_ref.py
git commit -m "test: AC-2 compat — legacy harbor_dab specs route through translator unchanged"
```

---

## Task 6: Goal 1 generator reads dataset definition (AC-3)

**Files:**
- Modify: `examples/drivers/generate-dab-paper-matrix-specs.py:14-65`

- [ ] **Step 6.1: Replace the in-code catalog import with the definition load**

In `examples/drivers/generate-dab-paper-matrix-specs.py`, replace
lines 14-15:

```python
from razorback_plugin_dab.datasets import DAB_DATASETS
from razorback_plugin_dab.generate.workspace_readme import WORKSPACE_VARIANTS
```

with:

```python
from razorback_plugin_dab.dataset_def import load_default_definition
```

And then in `build_spec` (line 48) and `main` (line 94), use the definition
instead.

Replace lines 18-22:

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = "${DATAAGENTBENCH_DATA_ROOT:-~/dataagentbench/data}"
SOLVER_WORKFLOW_PATH = "./examples/solver_workflows/dab_paper_matrix"
```

with:

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
SOLVER_WORKFLOW_PATH = "./examples/solver_workflows/dab_paper_matrix"
_DEFINITION = load_default_definition()
```

Replace `build_spec` (lines 48-71) with:

```python
def build_spec(variant: str, dataset: str) -> dict:
    experiment = f"goal1-{variant}-{dataset.lower()}"
    return {
        "version": 1,
        "experiment": experiment,
        "agent": _build_agent_block(variant),
        "benchmark": {
            "kind": "harbor_dab",
            "dataset": _DEFINITION.ref,
            "datasets": [dataset],
            "workspace_variant": variant,
            "hints": True,
            "query_mode": "batch",
        },
        "trials": 1,
        "experiment_meta": {
            "max_budget_usd": 20.0,
            "estimated_cost_usd": 2.0,
        },
        "observers": [
            {"kind": "jsonl", "path": "events.jsonl"},
            {"kind": "stdout"},
        ],
    }
```

In `main` (lines 110-125), replace the `WORKSPACE_VARIANTS` and `DAB_DATASETS`
references:

```python
    for variant in _DEFINITION.workspace_variants:
        for ds_entry in _DEFINITION.datasets:
            spec_path = emit_spec(out_root / variant, variant, ds_entry.name)
            emitted.append(spec_path)
            print(f"wrote {spec_path.relative_to(REPO_ROOT)}")

    if args.freeze:
        for spec_path in emitted:
            print(f"freezing {spec_path.relative_to(REPO_ROOT)}")
            freeze_spec(spec_path)

    expected = len(_DEFINITION.workspace_variants) * len(_DEFINITION.datasets)
    print(
        f"emitted {len(emitted)} specs "
        f"({len(_DEFINITION.workspace_variants)} variants x {len(_DEFINITION.datasets)} datasets); "
        f"expected {expected}."
    )
```

- [ ] **Step 6.2: Run the generator end-to-end (smallest mechanism check)**

> Per CL's "validating new mechanisms" rule: pay the small bill first.

```
uv run python examples/drivers/generate-dab-paper-matrix-specs.py --out-root /tmp/dab-matrix-probe
```
Expected: prints `emitted 36 specs (3 variants x 12 datasets); expected 36.`
and the on-disk files exist at `/tmp/dab-matrix-probe/<variant>/<dataset>.yaml`.

- [ ] **Step 6.3: Spot-check one emitted spec has the dataset ref**

```
grep -A 2 "kind: harbor_dab" /tmp/dab-matrix-probe/spacedock/bookreview.yaml
```
Expected: shows `dataset: dab@1.0` on the line below `kind: harbor_dab`, and
`datasets: [bookreview]` immediately after. If any of those are missing,
re-check Step 6.1 — don't proceed.

- [ ] **Step 6.4: Commit**

```
git add examples/drivers/generate-dab-paper-matrix-specs.py
git commit -m "feat: Goal 1 generator reads DAB dataset definition (AC-3)"
```

---

## Task 7: Generator round-trip test against a fixture definition (AC-3)

**Files:**
- Create: `tests/fixtures/dab_dataset_minimal.toml`
- Create: `tests/unit/test_generate_dab_paper_matrix_from_definition.py`

- [ ] **Step 7.1: Create the fixture**

Create `tests/fixtures/dab_dataset_minimal.toml`:

```toml
# 2-dataset fixture used by AC-3 generator round-trip tests.
name = "dab-fixture"
version = "0.1"
description = "AC-3 fixture — 2 datasets, 2 variants."

workspace_variants = ["direct-minimal", "spacedock"]

[[datasets]]
name = "tinyset"
backends = ["sqlite"]
query_count = 2
query_ids = [1, 2]
schema_version = "v1"

[[datasets]]
name = "smallset"
backends = ["duckdb", "sqlite"]
query_count = 1
query_ids = [1]
schema_version = "v1"
```

- [ ] **Step 7.2: Write the failing round-trip test**

Importing a script with a hyphen in the filename is impossible via the standard
import system, so the test uses `runpy.run_path` and patches the loader symbol
that the generator imports.

Create `tests/unit/test_generate_dab_paper_matrix_from_definition.py`:

```python
# ABOUTME: AC-3 — Goal 1 generator emits cells matching the dataset definition.
# ABOUTME: Uses a 2x2 fixture instead of the production 3x12 to keep the test fast.

from __future__ import annotations

import runpy
from pathlib import Path

import yaml

from razorback_plugin_dab.dataset_def import load_definition_from


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "dab_dataset_minimal.toml"
GENERATOR = Path(__file__).resolve().parents[2] / "examples" / "drivers" / "generate-dab-paper-matrix-specs.py"


def test_generator_emits_cell_per_variant_dataset_from_fixture(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_def = load_definition_from(FIXTURE)

    # Patch the loader the generator imports.
    monkeypatch.setattr(
        "razorback_plugin_dab.dataset_def.load_default_definition",
        lambda: fixture_def,
    )

    out_root = tmp_path / "out"
    monkeypatch.setattr("sys.argv", [
        "generate-dab-paper-matrix-specs.py",
        "--out-root", str(out_root),
    ])

    # runpy executes the script; SystemExit(0) propagates from main().
    try:
        runpy.run_path(str(GENERATOR), run_name="__main__")
    except SystemExit as exc:
        assert exc.code == 0

    emitted = sorted(out_root.glob("*/*.yaml"))
    assert len(emitted) == 4, f"expected 2 variants x 2 datasets = 4 specs; got {len(emitted)}"

    cells = {p.parent.name: p.stem for p in emitted}
    assert set(p.parent.name for p in emitted) == {"direct-minimal", "spacedock"}
    assert set(p.stem for p in emitted) == {"tinyset", "smallset"}


def test_generator_emits_dataset_ref_in_each_spec(tmp_path: Path, monkeypatch) -> None:
    fixture_def = load_definition_from(FIXTURE)
    monkeypatch.setattr(
        "razorback_plugin_dab.dataset_def.load_default_definition",
        lambda: fixture_def,
    )
    out_root = tmp_path / "out"
    monkeypatch.setattr("sys.argv", [
        "generate-dab-paper-matrix-specs.py", "--out-root", str(out_root),
    ])
    try:
        runpy.run_path(str(GENERATOR), run_name="__main__")
    except SystemExit:
        pass

    for spec_path in out_root.glob("*/*.yaml"):
        spec = yaml.safe_load(spec_path.read_text())
        assert spec["benchmark"]["kind"] == "harbor_dab"
        assert spec["benchmark"]["dataset"] == "dab-fixture@0.1"
        assert spec["benchmark"]["query_mode"] == "batch"
        assert spec["benchmark"]["workspace_variant"] in {"direct-minimal", "spacedock"}
```

- [ ] **Step 7.3: Run the test**

```
uv run pytest tests/unit/test_generate_dab_paper_matrix_from_definition.py -v
```
Expected: 2 PASS. If `monkeypatch.setattr` for the module-level `_DEFINITION`
doesn't work because `_DEFINITION` is captured at module load before the
patch takes effect, the fix is one of: (a) move `_DEFINITION` loading to
inside `main()` so the patch lands before `main()` runs, or (b) read the
definition path from an env var the test sets. Pick (a) — it's a one-line
move in `examples/drivers/generate-dab-paper-matrix-specs.py`.

- [ ] **Step 7.4: If `_DEFINITION` capture-at-import breaks the patch, fix the generator**

In `examples/drivers/generate-dab-paper-matrix-specs.py`, replace the
top-level `_DEFINITION = load_default_definition()` line with an in-`main()`
local:

```python
def main() -> int:
    parser = argparse.ArgumentParser()
    # ... existing parser setup ...
    args = parser.parse_args()

    definition = load_default_definition()
    out_root = Path(args.out_root)
    emitted: list[Path] = []
    for variant in definition.workspace_variants:
        for ds_entry in definition.datasets:
            spec_path = emit_spec(out_root / variant, variant, ds_entry.name, definition.ref)
            # ...
```

And thread `definition.ref` through `emit_spec` → `build_spec` as a parameter.
This makes the test's monkeypatch land cleanly because `load_default_definition`
is called at `main()` time, after the patch.

- [ ] **Step 7.5: Rerun the test**

```
uv run pytest tests/unit/test_generate_dab_paper_matrix_from_definition.py -v
```
Expected: 2 PASS.

- [ ] **Step 7.6: Re-run the smoke check from Step 6.2**

```
uv run python examples/drivers/generate-dab-paper-matrix-specs.py --out-root /tmp/dab-matrix-probe2
```
Expected: still emits 36 specs (the refactor in Step 7.4 keeps behavior).

- [ ] **Step 7.7: Commit**

```
git add tests/fixtures/dab_dataset_minimal.toml \
        tests/unit/test_generate_dab_paper_matrix_from_definition.py \
        examples/drivers/generate-dab-paper-matrix-specs.py
git commit -m "test: AC-3 round-trip — generator emits cells matching dataset definition"
```

---

## Task 8: Stratum tagging reads from the definition (AC-4)

**Files:**
- Modify: `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/stratum.py`
- Modify: `packages/razorback-plugin-dab/tests/unit/test_stratum_tagging.py`

> **AC-4 reality check:** `src/razorback/benchmarks/dab/aggregate.py:_build_summary`
> already derives stratum (dataset, query_id) keys from the per-trial outcomes
> themselves, NOT from `DAB_DATASETS`. The current AC-4 weakness is that
> *stratum_payload()* (in stratum.py) is invoked with `backends` from
> `DAB_DATASETS` (already a definition consumer after Task 1, so technically
> done) — but the AC's actual ask is "scoring uses dataset/task metadata
> emitted by the dataset definition/task view." Task 8 makes that path
> *explicit* rather than transitive.

- [ ] **Step 8.1: Write the failing test**

Append to `packages/razorback-plugin-dab/tests/unit/test_stratum_tagging.py`
(read the file first to know the existing structure):

```python
def test_stratum_payload_metadata_from_definition():
    """AC-4 Verified by: stratum metadata is sourced from the dataset definition,
    not from an ad-hoc catalog. Same definition source the generator uses."""
    from razorback_plugin_dab.dataset_def import load_default_definition
    from razorback_plugin_dab.generate.stratum import stratum_payload

    definition = load_default_definition()
    ds = definition.get_dataset("bookreview")
    payload = stratum_payload(
        dataset=ds.name, query_id=1, backends=ds.backends,
    )
    assert payload == {
        "stratum": {
            "dataset": "bookreview",
            "query_id": 1,
            "backends": ["postgres", "sqlite"],
        }
    }
```

- [ ] **Step 8.2: Run test**

```
uv run pytest packages/razorback-plugin-dab/tests/unit/test_stratum_tagging.py::test_stratum_payload_metadata_from_definition -v
```
Expected: PASS (stratum.py already accepts backends as a parameter; the test
is the AC's Verified-by check).

- [ ] **Step 8.3: Commit**

```
git add packages/razorback-plugin-dab/tests/unit/test_stratum_tagging.py
git commit -m "test: AC-4 — stratum payload metadata sourced from dataset definition"
```

---

## Task 9: Goal 1 aggregator reads stratum enumeration from the definition (AC-4)

**Files:**
- Modify: `examples/drivers/aggregate-goal1-scores.py:13-75`
- Create: `tests/unit/test_aggregate_goal1_from_definition.py`

- [ ] **Step 9.1: Write the failing test**

Create `tests/unit/test_aggregate_goal1_from_definition.py`:

```python
# ABOUTME: AC-4 — Goal 1 aggregator enumerates strata from the dataset definition.
# ABOUTME: Mocks per-cell result.json reads; verifies the stratum loop visits exactly the def's datasets.

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path


AGGREGATOR = Path(__file__).resolve().parents[2] / "examples" / "drivers" / "aggregate-goal1-scores.py"


def test_aggregator_strata_match_definition(tmp_path: Path, monkeypatch) -> None:
    from razorback_plugin_dab.dataset_def import load_default_definition

    definition = load_default_definition()
    matrix_root = tmp_path / "matrix"
    variant_dir = matrix_root / "spacedock"
    variant_dir.mkdir(parents=True)
    # Plant a stub result.json under each dataset cell so find_result_json finds it.
    for ds_entry in definition.datasets:
        cell = variant_dir / ds_entry.name / "trial0" / "step0"
        cell.mkdir(parents=True)
        (cell / "result.json").write_text(json.dumps({"stats": {"evals": {}}}))

    out_path = tmp_path / "summary.json"
    monkeypatch.setattr("sys.argv", [
        "aggregate-goal1-scores.py",
        "--matrix-root", str(matrix_root),
        "--out", str(out_path),
        "--variant", "spacedock",
    ])
    try:
        runpy.run_path(str(AGGREGATOR), run_name="__main__")
    except SystemExit:
        pass

    summary = json.loads(out_path.read_text())
    assert set(summary["strata"].keys()) == {d.name for d in definition.datasets}
    assert summary["n_strata_total"] == len(definition.datasets)
```

- [ ] **Step 9.2: Run test to verify it fails**

```
uv run pytest tests/unit/test_aggregate_goal1_from_definition.py -v
```
Expected: FAIL — the aggregator currently reads `DAB_DATASETS` (which works
transitively but the test's explicit-source assertion may still pass if the
12-dataset count matches). If it passes already, that's fine — Step 9.3 still
makes the dependency explicit.

- [ ] **Step 9.3: Update the aggregator imports**

In `examples/drivers/aggregate-goal1-scores.py`, replace line 13:

```python
from razorback_plugin_dab.datasets import DAB_DATASETS
```

with:

```python
from razorback_plugin_dab.dataset_def import load_default_definition
```

Read the aggregator file end-to-end first (it's ~200 lines). Replace usages
of `DAB_DATASETS` (lines 75 and 129 per the earlier grep) with the definition
load result. A clean way: load `_DEFINITION = load_default_definition()` once
at module top and iterate `_DEFINITION.datasets` (each element has `.name`).
The aggregator only uses `.name`, so the substitution is mechanical.

If `--matrix-root`, `--out`, `--variant` arg names differ from the test, read
the aggregator's `argparse` block and either adjust the test's `sys.argv` to
match, or extend the aggregator's argparse to accept these names. Do NOT
invent flags the script doesn't have — read first, then test.

- [ ] **Step 9.4: Run the test**

```
uv run pytest tests/unit/test_aggregate_goal1_from_definition.py -v
```
Expected: PASS.

- [ ] **Step 9.5: Commit**

```
git add examples/drivers/aggregate-goal1-scores.py tests/unit/test_aggregate_goal1_from_definition.py
git commit -m "feat: Goal 1 aggregator strata enumeration sources from dataset definition (AC-4)"
```

---

## Task 10: Deprecate the in-tree `kind: dab` path (AC-5)

**Files:**
- Modify: `src/razorback/benchmarks/dab/prepare.py` (add DeprecationWarning)
- Modify: `src/razorback/spec/parse.py:13-18` (extend alias docstring)
- Create: `tests/unit/test_in_tree_dab_deprecation.py`

- [ ] **Step 10.1: Write the failing deprecation test**

Create `tests/unit/test_in_tree_dab_deprecation.py`:

```python
# ABOUTME: AC-5 — kind: dab (in-tree) is dev-only; emits DeprecationWarning naming harbor_dab.
# ABOUTME: harbor_dab stays as the canonical path the warning recommends.

from __future__ import annotations

import warnings

import pytest

from razorback.benchmarks.dab.prepare import prepare_dataset_tasks


def test_in_tree_dab_emits_deprecation_warning(tmp_path) -> None:
    # Set up minimal data_root layout so prepare_dataset_tasks gets past the
    # existence check and into the deprecation warning. The warning should fire
    # BEFORE any heavy materialization work — assert it fires at all.
    data_root = tmp_path / "data"
    (data_root / "query_bookreview").mkdir(parents=True)

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        try:
            prepare_dataset_tasks(
                data_root=data_root,
                dataset="bookreview",
                tasks_root=tmp_path / "tr",
            )
        except Exception:
            # The function will likely error after the warning because the
            # query dir is empty. We only care that the warning fired.
            pass

    dep_warnings = [w for w in captured if issubclass(w.category, DeprecationWarning)]
    assert dep_warnings, "expected DeprecationWarning from in-tree DAB prepare"
    msg = str(dep_warnings[0].message)
    assert "harbor_dab" in msg
    assert "dab" in msg.lower()
```

- [ ] **Step 10.2: Run test**

```
uv run pytest tests/unit/test_in_tree_dab_deprecation.py -v
```
Expected: FAIL — no warning is emitted today.

- [ ] **Step 10.3: Add the deprecation warning**

In `src/razorback/benchmarks/dab/prepare.py`, at the very top of
`prepare_dataset_tasks` (after the docstring), add:

```python
import warnings

warnings.warn(
    "in-tree DAB adapter (kind: dab) is dev-only; "
    "use kind: harbor_dab + dataset: dab@1.0 for canonical runs.",
    DeprecationWarning,
    stacklevel=2,
)
```

- [ ] **Step 10.4: Update the alias docstring**

In `src/razorback/spec/parse.py`, replace lines 13-18 with:

```python
_BENCHMARK_KIND_ALIASES = {
    # v2 spelling for the v1 in-tree DAB adapter. Both forms parse; the
    # internal model still uses kind="dab" so the existing translator path
    # is unchanged. AC-5: in-tree DAB is dev-only; canonical DAB is
    # kind: harbor_dab + dataset: dab@<version> (see entity
    # dab-harbor-dataset-definition).
    "in_tree_dab": "dab",
}
```

- [ ] **Step 10.5: Run the test**

```
uv run pytest tests/unit/test_in_tree_dab_deprecation.py -v
```
Expected: PASS.

- [ ] **Step 10.6: Run the existing in-tree dab tests to confirm they still pass (warning is non-fatal)**

```
uv run pytest tests/unit/test_dab_translator_twelve.py tests/unit/test_dab_spec_parse.py -v
```
Expected: PASS. If pytest is configured to treat warnings as errors, the
tests that hit `prepare_dataset_tasks` will fail. In that case, add
`filterwarnings = ["ignore::DeprecationWarning:razorback.benchmarks.dab.prepare"]`
to `pyproject.toml`'s `[tool.pytest.ini_options]` — but ONLY if pytest is
already strict; do not invent strictness.

- [ ] **Step 10.7: Commit**

```
git add src/razorback/benchmarks/dab/prepare.py src/razorback/spec/parse.py tests/unit/test_in_tree_dab_deprecation.py
git commit -m "feat: deprecate in-tree DAB adapter; canonical path is harbor_dab + dataset ref (AC-5)"
```

---

## Task 11: Validation report — cite remaining DAB entry points (AC-5)

This task is the AC-5 "Verified by: validation report cites the remaining DAB
benchmark entry points and shows examples/tests route through the canonical
dataset-definition path." It produces no code — it produces documentation.
Validation stage will own the report; the plan-stage worker only needs to
make sure the docs *can* be produced by the validator.

**Files:**
- Verify (no edit needed unless gaps surface):
  - `docs/razorback-implementation/dab-harbor-dataset-definition.md` — entity
    body (Notes section already describes the boundary)
  - `examples/specs/dab-dev-claude.yaml` — currently uses `kind: dab`; leave
    as-is (it's the dev-only path now) but add a one-line comment naming it
    as legacy.

- [ ] **Step 11.1: Add a header comment to the legacy spec**

In `examples/specs/dab-dev-claude.yaml`, replace the existing header (look
at the file — it currently has no header). Add at the top:

```yaml
# ABOUTME: Dev-only DAB spec — uses legacy kind: dab. Canonical path is
# ABOUTME: kind: harbor_dab + dataset: dab@1.0 (see goal1-paper-matrix specs).
```

- [ ] **Step 11.2: Verify other example specs already use harbor_dab**

```
rg "^benchmark:|kind: dab\b|kind: harbor_dab\b" examples/specs -A 1 | head -60
```
Expected: examples under `goal1/`, `codex-dab-smoke.yaml`,
`bookreview-claude-harbor-dab.yaml`, etc. use `harbor_dab`. Only the dev
specs (`dab-dev-claude.yaml`, `dab-dev-claude-subset.yaml`,
`bookreview-claude-in-tree-dab.yaml`) use `kind: dab`. If any production
goal-1 spec is still on `kind: dab`, raise it back to team-lead before
proceeding — that's a scope leak.

- [ ] **Step 11.3: Add a header comment to the other in-tree specs**

For each of `examples/specs/dab-dev-claude-subset.yaml` and
`examples/specs/bookreview-claude-in-tree-dab.yaml`, add the same two-line
ABOUTME header. (Read each file first; if a header already exists, append
the "dev-only / canonical = harbor_dab + dataset:" sentence to it.)

- [ ] **Step 11.4: Commit**

```
git add examples/specs/dab-dev-claude.yaml \
        examples/specs/dab-dev-claude-subset.yaml \
        examples/specs/bookreview-claude-in-tree-dab.yaml
git commit -m "docs: mark in-tree DAB example specs as dev-only (AC-5)"
```

---

## Mechanism-first ordering rationale

Per CL's "validating new mechanisms" rule and the README's "smallest end-to-end
exercise of the riskiest contract first": the riskiest contract here is the
*shape of the dataset.toml + how the translator reads it*. Tasks 1–4 exercise
that full path end-to-end (definition → schema → translator → plugin
subprocess) before Task 5+ pile on examples, generators, and aggregators.
Task 6's smoke run (`generate-dab-paper-matrix-specs.py --out-root /tmp/...`)
is the integration-level mechanism check — it would invalidate every later
task if broken, so it runs before the round-trip test in Task 7.

The plugin subprocess shape (`razorback-plugin-dab generate --datasets X
--data-root Y --out Z ...`) is NOT changed by this plan; the dataset
definition layer sits *above* it. That keeps the riskiest external contract
(the plugin CLI) stable while the new layer matures.

## Out of scope

- Adding DAB to Harbor's `registry.json` — DAB tasks are *generated*, not
  source-controlled. The sibling entity `ade-bench-harbor-dataset-ref`
  consumes Harbor's actual `Registry` because ADE tasks are published
  `PackageTaskId`s. This asymmetry is deliberate.
- Removing the in-tree `DabBenchmarkBlock` / `src/razorback/benchmarks/dab/`
  module. AC-5 says "reduced," not "removed" — and the captain's directive
  said "don't remove the need for local DAB data." Deprecation + dev-only
  marking satisfies AC-5; deletion is a follow-up task.
- Materialization changes. `data_root` still names the local DAB data root;
  the plugin subprocess still receives `--data-root`. AC-2's Notes section
  reads: "Local `data_root` remains available only for adapter
  generation/materialization."
- Multi-version dataset definitions. A single `dataset.toml` shipping
  `version = "1.0"` is enough for Goal 1. Future re-versioning (e.g. when
  upstream DAB adds queries) goes through a separate task.
- Caching / digest-pinning the dataset definition. Harbor's `Registry`
  carries `dataset_version_content_hash`; we can add it to
  `DabDatasetDefinition` later if provenance asks for it. For now,
  `name@version` is enough.
