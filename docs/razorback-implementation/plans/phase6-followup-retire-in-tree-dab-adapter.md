# Retire In-Tree DAB Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `benchmark.kind: harbor_dab` and `packages/razorback-plugin-dab` the only active DAB materialization path, then move the old `src/razorback/benchmarks/dab/` adapter under `_legacy`.

**Architecture:** This is a retirement task, not a dataset-model redesign. The active translator must keep the existing plugin subprocess path for `harbor_dab`, remove the `DabBenchmarkBlock` dispatch branch, and stop importing `razorback.benchmarks.dab` directly or indirectly. The in-tree adapter moves to `_legacy` with legacy import paths updated there only; active plugin, example-generator, and scoring tests stay green.

**Tech Stack:** Python 3.12, Pydantic spec schema, Harbor `JobConfig`, Typer CLI, pytest, uv workspace package `packages/razorback-plugin-dab`.

---

## Spec And Workflow Anchors

- Entity AC-1: active DAB specs route through `benchmark.kind: harbor_dab`; active translator no longer imports `razorback.benchmarks.dab`.
- Entity AC-2: `src/razorback/benchmarks/dab/` is moved to `_legacy/benchmarks/dab/` or deleted after active imports are gone.
- Entity AC-3: plugin-backed DAB tests and active example-generator tests pass.
- v2 spec section 6.1: Razorback translates benchmark blocks into Harbor task/dataset config; Harbor adapters are offline task generators, not runtime dispatch targets.
- v2 spec section 6.2: `spacedock_solver` carries leak-guard fields such as `tools_denied`; DAB only publishes recommended lists/docs.
- reconciliation plan Phase 6 AC-6.4 commit 2: `src/razorback/benchmarks/dab/` moves to `_legacy/benchmarks/dab/` because the harbor-DAB adapter replaces it.
- Phase 6 validation cycle 2: approved the core canonical solver merge while explicitly deferring active DAB retirement to this follow-up.
- Coordination boundary: `docs/razorback-implementation/dab-harbor-dataset-definition.md` owns dataset definition / dataset-ref work. Do not add `dataset.toml`, dataset refs, or a new DAB inventory source in this task.

## Current Inventory

The active replacement path already exists:

- `src/razorback/translate.py::_build_harbor_dab` shells out to `uv run razorback-plugin-dab generate` for `benchmark.kind: harbor_dab`.
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py` emits task directories and `tests/stratum.json`.
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/verify/verify.py` and `verify_batch.py` own verifier reward emission.
- `examples/specs/**` and `examples/drivers/**` use `kind: harbor_dab` for active DAB examples.

Active in-tree references to retire:

- `src/razorback/translate.py` imports `DabBenchmarkBlock`, dispatches `_build_dab`, and imports `razorback.benchmarks.dab.prepare`.
- `src/razorback/translate.py` and `src/razorback/benchmarks/ade_bench/tasks.py` import `_DEFAULT_DOCKER_IMAGE` from `razorback.benchmarks.dab.prepare`.
- `src/razorback/spec/schema.py` still includes `DabBenchmarkBlock` in the active `BenchmarkBlock` union.
- `src/razorback/spec/parse.py` aliases `in_tree_dab` to `dab`.
- Active tests import `razorback.benchmarks.dab.*` for prepare, verify, aggregate, and reset behavior.
- `tests/conftest.py` still ignores `tests/unit/test_translator_harbor_dab.py`, even though this task needs that plugin translator test active again.

Allowed legacy/plugin references after the task:

- `src/razorback/_legacy/**` may reference `razorback._legacy.benchmarks.dab`.
- `tests/_legacy/**` may cover legacy behavior if the implementer chooses to preserve those tests.
- `packages/razorback-plugin-dab/**` may mention the old port source in comments and may import only `razorback_plugin_dab.*`, not `razorback.benchmarks.dab`.

## File Structure

Modify active translator/schema:

- `src/razorback/translate.py` - remove the active `DabBenchmarkBlock` branch, delete `_build_dab`, and keep `_build_harbor_dab` as the only DAB translator branch.
- `src/razorback/spec/schema.py` - keep `HarborDabBenchmarkBlock` active; remove `DabBenchmarkBlock` from the active `BenchmarkBlock` union. If the class is retained for `_legacy` import compatibility, mark it legacy-only and do not include it in active parsing.
- `src/razorback/spec/parse.py` - remove the `in_tree_dab` to `dab` alias and surface a clear parse failure that points users to `harbor_dab`.
- `src/razorback/benchmarks/ade_bench/tasks.py` - replace the DAB `_DEFAULT_DOCKER_IMAGE` import with a local ADE default constant or a neutral shared constant.
- `src/razorback/benchmarks/__init__.py` - update comments if they still imply an active DAB subpackage.

Move legacy adapter:

- Move `src/razorback/benchmarks/dab/` to `src/razorback/_legacy/benchmarks/dab/`.
- Add `src/razorback/_legacy/benchmarks/__init__.py` if needed.
- Update internal imports in the moved files from `razorback.benchmarks.dab` to `razorback._legacy.benchmarks.dab`.
- Update `_legacy` consumers such as `src/razorback/_legacy/run.py` and `src/razorback/_legacy/compat/harbor_0_6_6.py` to import the moved adapter path if keeping them importable.

Retarget tests:

- `tests/unit/test_translator_harbor_dab.py` - make active again; remove the old in-tree path regression test; add assertions that the plugin subprocess path remains the materializer.
- `tests/unit/test_spec_harbor_dab_block.py` - keep `harbor_dab` parse coverage; replace old `dab` / `in_tree_dab` acceptance tests with rejection tests.
- Add `tests/unit/test_dab_retirement.py` - grep-level active import and directory retirement checks.
- Move or delete active tests that import `razorback.benchmarks.dab.*`; keep only plugin-backed equivalents or legacy-only tests under `tests/_legacy/`.
- Preserve `tests/unit/test_generate_matrix_specs.py` and `tests/unit/test_codex_benchmark_spec_generator.py` as active example-generator coverage.

Do not modify:

- `docs/razorback-implementation/dab-harbor-dataset-definition.md`.
- Plugin catalog/dataset-definition shape beyond tests required to prove existing plugin behavior still passes.
- Production code outside the active DAB translator/schema/import boundary unless a failing test identifies a direct import leak.

## AC To Task Map

| AC | Governing cites | Tasks |
| --- | --- | --- |
| AC-1 Active DAB specs route through plugin-backed Harbor shape | entity AC-1; v2 spec section 6.1; Phase 6 validation deferred AC-4 DAB item | Tasks 1, 2, 4 |
| AC-2 In-tree DAB adapter is legacy-only | entity AC-2; reconciliation Phase 6 AC-6.4 commit 2 | Tasks 1, 3 |
| AC-3 DAB score/materialization tests still pass | entity AC-3; v2 spec section 6.1; existing plugin README CLI contract | Tasks 4, 5 |

## Commit Boundaries

1. `test: cover DAB adapter retirement gates` - failing tests only for active import inventory, `dab` parse rejection, and active `test_translator_harbor_dab.py` restoration.
2. `translate: route active DAB only through plugin` - remove `DabBenchmarkBlock` active dispatch, remove in-tree imports, fix ADE default-image import, pass focused translator/schema tests.
3. `sideline: in-tree DAB adapter -> _legacy` - move `src/razorback/benchmarks/dab/` to `_legacy`, update legacy imports, move/delete active in-tree tests.
4. `test: keep plugin DAB and examples green` - final test retargeting plus any focused test fixture cleanup needed for the required validation command.

Keep the sideline move as its own commit. Do not combine it with translator edits or plugin/example test edits.

## Task 1: Failing Retirement Tests

**Files:**

- Create: `tests/unit/test_dab_retirement.py`
- Modify: `tests/conftest.py`
- Modify: `tests/unit/test_spec_harbor_dab_block.py`
- Modify: `tests/unit/test_translator_harbor_dab.py`

- [ ] **Step 1: Add an active import inventory test**

Create `tests/unit/test_dab_retirement.py` with:

```python
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_active_code_does_not_import_in_tree_dab_adapter() -> None:
    active_roots = [
        REPO_ROOT / "src" / "razorback",
        REPO_ROOT / "tests",
        REPO_ROOT / "examples",
    ]
    forbidden = [
        "razorback.benchmarks.dab",
        "benchmarks/dab",
    ]
    offenders: list[str] = []
    for root in active_roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if "/_legacy/" in f"/{rel}/" or rel.startswith("tests/_legacy/"):
                continue
            if path.suffix not in {".py", ".md", ".yaml", ".yml", ".toml"}:
                continue
            text = path.read_text(errors="ignore")
            for needle in forbidden:
                if needle in text or needle in rel:
                    offenders.append(f"{rel}: {needle}")
    assert offenders == []
```

- [ ] **Step 2: Add an active directory retirement test**

Append to `tests/unit/test_dab_retirement.py`:

```python
def test_in_tree_dab_adapter_directory_is_not_active() -> None:
    assert not (REPO_ROOT / "src" / "razorback" / "benchmarks" / "dab").exists()
```

- [ ] **Step 3: Add schema rejection coverage for old DAB kinds**

In `tests/unit/test_spec_harbor_dab_block.py`, replace the current tests that assert `dab` or `in_tree_dab` parses as `DabBenchmarkBlock` with:

```python
import pytest

from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text


def test_in_tree_dab_kind_is_retired_from_active_specs(tmp_path) -> None:
    with pytest.raises(SpecError) as exc_info:
        parse_spec_text(
            "version: 1\n"
            "experiment: retired-dab\n"
            "agent:\n"
            "  kind: nop\n"
            "benchmark:\n"
            "  kind: in_tree_dab\n"
            f"  data_root: {tmp_path}\n"
            "  datasets: [bookreview]\n"
            "trials: 1\n"
        )
    assert "harbor_dab" in str(exc_info.value) or "Input tag" in str(exc_info.value)


def test_dab_kind_is_retired_from_active_specs(tmp_path) -> None:
    with pytest.raises(SpecError) as exc_info:
        parse_spec_text(
            "version: 1\n"
            "experiment: retired-dab\n"
            "agent:\n"
            "  kind: nop\n"
            "benchmark:\n"
            "  kind: dab\n"
            f"  data_root: {tmp_path}\n"
            "  datasets: [bookreview]\n"
            "trials: 1\n"
        )
    assert "harbor_dab" in str(exc_info.value) or "Input tag" in str(exc_info.value)
```

Keep the existing `harbor_dab` positive tests.

- [ ] **Step 4: Restore active plugin translator tests**

Remove `"unit/test_translator_harbor_dab.py"` from `collect_ignore_glob` in `tests/conftest.py`.

In `tests/unit/test_translator_harbor_dab.py`, delete
`test_in_tree_dab_translator_path_unchanged` and keep the existing bodies of
these plugin-path tests unchanged:

- `test_harbor_dab_translator_invokes_plugin_and_builds_tasks`
- `test_translator_harbor_dab_batch_emits_list_keyed_map`
- `test_harbor_dab_translator_propagates_plugin_failure`
- `test_harbor_dab_requires_tasks_root`

Do not introduce a direct Python import of `razorback_plugin_dab` into `src/razorback/translate.py`; the current subprocess boundary is the active replacement path and avoids duplicating plugin ownership.

- [ ] **Step 5: Run the focused failing tests**

Run:

```bash
uv run pytest tests/unit/test_dab_retirement.py tests/unit/test_spec_harbor_dab_block.py tests/unit/test_translator_harbor_dab.py -q
```

Expected before implementation: failures naming active `src/razorback/translate.py`, `src/razorback/benchmarks/dab`, and the old `dab` / `in_tree_dab` acceptance behavior.

- [ ] **Step 6: Commit failing tests**

```bash
git add tests/unit/test_dab_retirement.py tests/conftest.py tests/unit/test_spec_harbor_dab_block.py tests/unit/test_translator_harbor_dab.py
git commit -m "test: cover DAB adapter retirement gates"
```

## Task 2: Remove Active Translator Dependency

**Files:**

- Modify: `src/razorback/translate.py`
- Modify: `src/razorback/spec/schema.py`
- Modify: `src/razorback/spec/parse.py`
- Modify: `src/razorback/benchmarks/ade_bench/tasks.py`

- [ ] **Step 1: Remove `DabBenchmarkBlock` from active dispatch**

In `src/razorback/translate.py`:

- Remove `DabBenchmarkBlock` from the `from razorback.spec.schema import` import list.
- Delete this branch from `spec_to_job_config`:

```python
if isinstance(spec.benchmark, DabBenchmarkBlock):
    if tasks_root is None:
        raise SpecError("DAB specs require tasks_root.")
    return _build_dab(
        spec=spec,
        job_name=job_name,
        jobs_dir=jobs_dir,
        tasks_root=Path(tasks_root),
        agent_cfg=agent_cfg,
        task_env=task_env,
    )
```

- Delete the whole `_build_dab` function.
- Keep the `HarborDabBenchmarkBlock` branch and `_build_harbor_dab` function.

- [ ] **Step 2: Remove active in-tree default-image imports**

In `src/razorback/benchmarks/ade_bench/tasks.py`, replace:

```python
from razorback.benchmarks.dab.prepare import _DEFAULT_DOCKER_IMAGE
```

with a local constant:

```python
DEFAULT_ADE_BENCH_DOCKER_IMAGE = "dab-agent:latest"
```

Then replace the default argument:

```python
docker_image: str = DEFAULT_ADE_BENCH_DOCKER_IMAGE,
```

In `src/razorback/translate.py`, remove the local import:

```python
from razorback.benchmarks.dab.prepare import _DEFAULT_DOCKER_IMAGE
```

and use the ADE constant instead:

```python
from razorback.benchmarks.ade_bench.tasks import (
    DEFAULT_ADE_BENCH_DOCKER_IMAGE,
    materialize_git_task,
    resolve_task_dirs,
)
docker_image = spec.benchmark.docker_image_override or DEFAULT_ADE_BENCH_DOCKER_IMAGE
```

If importing that constant creates a circular import, define the same local string constant in `translate.py` as `DEFAULT_ADE_BENCH_DOCKER_IMAGE = "dab-agent:latest"` and leave a short comment that PKG-24 owns the future image rename.

- [ ] **Step 3: Remove active parsing of old DAB kinds**

In `src/razorback/spec/schema.py`, remove `DabBenchmarkBlock` from `BenchmarkBlock`:

```python
BenchmarkBlock = Annotated[
    Union[
        LocalBenchmarkBlock,
        HarborDabBenchmarkBlock,
        AdeBenchBenchmarkBlock,
        Spider2DbtBenchmarkBlock,
    ],
    Field(discriminator="kind"),
]
```

If `_legacy` modules still import `DabBenchmarkBlock`, keep the class definition above `HarborDabBenchmarkBlock` with this docstring:

```python
class DabBenchmarkBlock(BaseModel):
    """Legacy-only schema block retained for `_legacy` imports.

    Active specs no longer include this class in `BenchmarkBlock`; use
    `benchmark.kind: harbor_dab`.
    """
```

In `src/razorback/spec/parse.py`, remove `_BENCHMARK_KIND_ALIASES` and the mutation block that maps `in_tree_dab` to `dab`.

- [ ] **Step 4: Run the focused tests**

Run:

```bash
uv run pytest tests/unit/test_dab_retirement.py tests/unit/test_spec_harbor_dab_block.py tests/unit/test_translator_harbor_dab.py -q
```

Expected after this task: schema and translator tests pass except the directory-retirement test may still fail until Task 3.

- [ ] **Step 5: Commit active translator cleanup**

```bash
git add src/razorback/translate.py src/razorback/spec/schema.py src/razorback/spec/parse.py src/razorback/benchmarks/ade_bench/tasks.py
git commit -m "translate: route active DAB only through plugin"
```

## Task 3: Move In-Tree DAB Adapter To Legacy

**Files:**

- Move: `src/razorback/benchmarks/dab/` to `src/razorback/_legacy/benchmarks/dab/`
- Create: `src/razorback/_legacy/benchmarks/__init__.py`
- Modify: `src/razorback/_legacy/run.py`
- Modify: `src/razorback/_legacy/compat/harbor_0_6_6.py`
- Move or delete active tests importing `razorback.benchmarks.dab.*`

- [ ] **Step 1: Move the package**

Run:

```bash
mkdir -p src/razorback/_legacy/benchmarks
git mv src/razorback/benchmarks/dab src/razorback/_legacy/benchmarks/dab
```

Add `src/razorback/_legacy/benchmarks/__init__.py`:

```python
# ABOUTME: Legacy benchmark adapters preserved during Phase 6 retirement.
```

- [ ] **Step 2: Update legacy imports inside the moved adapter**

In `src/razorback/_legacy/benchmarks/dab/__init__.py`, replace:

```python
from razorback.benchmarks.dab.reset import per_trial_state_reset
```

with:

```python
from razorback._legacy.benchmarks.dab.reset import per_trial_state_reset
```

In `src/razorback/_legacy/benchmarks/dab/prepare.py`, replace:

```python
import razorback.benchmarks.dab.verify as verify_module
```

with:

```python
import razorback._legacy.benchmarks.dab.verify as verify_module
```

- [ ] **Step 3: Update `_legacy` consumers**

In `src/razorback/_legacy/run.py`, replace:

```python
from razorback.benchmarks.dab.aggregate import aggregate_job_result
```

with:

```python
from razorback._legacy.benchmarks.dab.aggregate import aggregate_job_result
```

In `src/razorback/_legacy/compat/harbor_0_6_6.py`, replace:

```python
from razorback.benchmarks.dab.prepare import _DEFAULT_DOCKER_IMAGE, prepare_dataset_tasks
```

with:

```python
from razorback._legacy.benchmarks.dab.prepare import (
    _DEFAULT_DOCKER_IMAGE,
    prepare_dataset_tasks,
)
```

- [ ] **Step 4: Retarget or retire active in-tree tests**

For each active test importing `razorback.benchmarks.dab.*`, choose one of these outcomes:

- If the behavior is already covered by `packages/razorback-plugin-dab/tests/**`, delete the duplicate active test.
- If the behavior is historical only, move the file to `tests/_legacy/dab/` and update imports to `razorback._legacy.benchmarks.dab.*`.
- If the behavior is still active scoring behavior, rewrite the test against `src/razorback/runs/aggregate.py` or the plugin-emitted `stratum.json` behavior instead of the in-tree aggregate module.

Known files to handle:

```text
tests/unit/test_dab_prepare.py
tests/unit/test_dab_verify.py
tests/unit/test_dab_aggregate.py
tests/unit/test_dab_aggregate_batch_query_mode.py
tests/unit/test_dab_aggregate_grep.py
tests/unit/test_dab_aggregate_twelve_datasets.py
tests/unit/test_dab_per_trial_state_reset.py
tests/unit/test_diff_per_trial_outcomes_sidecar.py
tests/unit/test_ade_bench_translator_test_sh_gating.py
```

For `tests/unit/test_diff_per_trial_outcomes_sidecar.py`, prefer rewriting to an active run-dir aggregation fixture because `per_trial_outcomes.json` is an active `src/razorback/runs/aggregate.py` contract.

- [ ] **Step 5: Run the retirement grep**

Run:

```bash
rg -n "razorback\\.benchmarks\\.dab|benchmarks/dab" src/razorback tests examples packages
```

Expected: no hits outside `_legacy` paths, docs if included manually, or `packages/razorback-plugin-dab` comments.

- [ ] **Step 6: Run the focused tests**

Run:

```bash
uv run pytest tests/unit/test_dab_retirement.py tests/unit/test_spec_harbor_dab_block.py tests/unit/test_translator_harbor_dab.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit the sideline move**

```bash
git add src/razorback/_legacy/benchmarks src/razorback/_legacy/run.py src/razorback/_legacy/compat/harbor_0_6_6.py tests
git add -u src/razorback/benchmarks
git commit -m "sideline: in-tree DAB adapter -> _legacy"
```

## Task 4: Plugin And Example Regression Checkpoints

**Files:**

- Modify only tests needed by failures from this task.
- Do not modify `packages/razorback-plugin-dab/src/**` unless the package tests reveal an import leak introduced by the move.

- [ ] **Step 1: Run plugin-backed DAB materialization tests**

Run:

```bash
uv run pytest packages/razorback-plugin-dab/tests -q
```

Expected: all plugin tests pass. If a test fails because of a lingering import from `razorback.benchmarks.dab`, change it to the plugin-owned module (`razorback_plugin_dab.generate.prepare`, `razorback_plugin_dab.verify.verify`, or `razorback_plugin_dab.verify.verify_batch`).

- [ ] **Step 2: Run active schema and generator tests**

Run:

```bash
uv run pytest tests/unit/test_spec_harbor_dab_block.py tests/unit/test_generate_matrix_specs.py tests/unit/test_codex_benchmark_spec_generator.py -q
```

Expected: all pass and emitted specs still use `benchmark.kind: harbor_dab`.

- [ ] **Step 3: Run the required entity validation command**

Run exactly:

```bash
uv run pytest packages/razorback-plugin-dab/tests tests/unit/test_spec_harbor_dab_block.py tests/unit/test_generate_matrix_specs.py tests/unit/test_codex_benchmark_spec_generator.py -q
```

Expected: all pass.

- [ ] **Step 4: Commit plugin/example test cleanup if needed**

If Task 4 required test-only changes:

```bash
git add packages/razorback-plugin-dab/tests tests/unit/test_spec_harbor_dab_block.py tests/unit/test_generate_matrix_specs.py tests/unit/test_codex_benchmark_spec_generator.py
git commit -m "test: keep plugin DAB and examples green"
```

If no files changed, do not create an empty commit.

## Task 5: Final Validation Sweep

**Files:**

- No production edits expected.

- [ ] **Step 1: Verify AC-1 grep**

Run:

```bash
rg -n "razorback\\.benchmarks\\.dab|benchmarks/dab" src/razorback tests examples packages
```

Expected: hits are limited to `_legacy` paths and `packages/razorback-plugin-dab` comments. There must be no active `src/razorback/translate.py`, active test, or active example hit.

- [ ] **Step 2: Verify AC-2 directory removal**

Run:

```bash
test -d src/razorback/benchmarks/dab
```

Expected: exit code 1.

- [ ] **Step 3: Run required AC-3 command**

Run:

```bash
uv run pytest packages/razorback-plugin-dab/tests tests/unit/test_spec_harbor_dab_block.py tests/unit/test_generate_matrix_specs.py tests/unit/test_codex_benchmark_spec_generator.py -q
```

Expected: all pass.

- [ ] **Step 4: Run additional focused guardrails**

Run:

```bash
uv run pytest tests/unit/test_dab_retirement.py tests/unit/test_translator_harbor_dab.py tests/unit/test_runs_aggregate.py tests/unit/test_diff_per_trial_outcomes_sidecar.py -q
```

Expected: all pass. This confirms the active plugin translator path and active run-dir scoring sidecars did not regress while legacy aggregate tests moved away.

- [ ] **Step 5: Run full suite if time allows**

Run:

```bash
uv run pytest
```

Expected: pass or only pre-existing documented environment skips/failures. If this reveals unrelated failures, record them in the implementation stage report and keep the AC commands as the gate.

## Coordination Risks

- `dab-harbor-dataset-definition` may later replace `harbor_dab` fields with a dataset-definition or dataset-ref shape. This task must not preempt that by adding a parallel dataset source of truth.
- Benchmark scoring is in flux (`rk-score-uses-benchmark-aggregator` and `score-task-identity-strata`). Do not rewrite the score reducer here. Only preserve active DAB run-dir summary/per-trial behavior and avoid trial-name parsing regressions.
- ADE currently borrowed DAB's default image constant. Removing that import is required for AC-1, but the image rename itself belongs to `pkg24-vendor-dab-agent-dockerfile`.
- Some old tests exercise useful math from `benchmarks/dab/aggregate.py`; moving them to legacy is acceptable only if active scoring has equivalent `runs/aggregate.py` or plugin stratum coverage.
- The acceptance grep excludes `docs/`, but implementation comments in active code still matter. Avoid adding new active-code comments containing `razorback.benchmarks.dab` or `benchmarks/dab`.

## Self-Review

- AC-1 maps to Task 1 failing grep/schema tests and Task 2 translator/schema cleanup; the replacement path is the existing `harbor_dab` plugin subprocess, with no dataset-definition duplication.
- AC-2 maps to Task 3's standalone sideline commit and Task 5's `test -d` validation.
- AC-3 maps to Task 4's required pytest command plus Task 5's final validation.
- Riskiest contract first: active import/schema/translator tests are written before the move, so the plugin path is proven before the legacy package disappears from its active location.
