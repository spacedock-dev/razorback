# spider2-dbt — source resolution + rk run materialization wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire spider2-dbt in as a recognized `kind: harbor` benchmark family so a `dataset: spider2-dbt/spider2-dbt@1.0` spec resolves source task dirs, runs each through `materialize_spider2_harbor_task_view`, and emits leakage-clean `TaskConfig(path=view_dir)` entries that `rk run --explain` can list.

**Architecture:** The wiring point is `_build_harbor` in `src/razorback/translate.py`. Today its pure pass-through branch (no `plugin:`) resolves a dataset ref into source task dirs via `_resolve_harbor_dataset_tasks`, applies the `exclude_tasks`/`n_tasks` selectors against the resolved source-dir names (`translate.py:312-317`), and emits them verbatim. We add a spider2-dbt detection branch with one load-bearing ordering rule: **selectors are applied to the resolved source paths first, then the surviving source dirs are materialized** through `materialize_spider2_harbor_task_view` into the run's `tasks_root`, and the emitted `TaskConfig.path` points at the materialized view (not the raw source). Filter-before-materialize is mandatory because the view-dir name is `<benchmark_kind>-<task_slug>` = `spider2-dbt-<source_slug>` (`materialize.py:143-146`); a post-materialization `p.name` filter (the generic-harbor pattern) would silently never match a source slug, so selectors must bind to original Harbor task names. Tests are fixture-backed against `tests/fixtures/spider2_dbt/` and inject the source-dir list through the same resolver-monkeypatch seam already used by the existing harbor-block tests, so the suite never touches the network. The AC-3 `rk run --explain` test runs the CLI **in-process** via Typer's `CliRunner` (same pattern as `tests/unit/test_rk_run_harbor_cache_dir.py`), so the `_resolve_harbor_dataset_tasks` monkeypatch reaches the resolver — there is **no production env seam**. The live `harbor download spider2-dbt@1.0 --export` smoke (the bare CLI ref) stays a non-gating validation-report probe (PKG-40 recorded its git-checkout failure).

> **Rework note (plan-gate cycle 1):** This revision resolves the three Codex-surfaced defects. (1) The user-facing dataset-ref contract is the fully-qualified `spider2-dbt/spider2-dbt@1.0` everywhere; the bare `spider2-dbt@1.0` is the `harbor download` CLI smoke only, with no schema support added (captain option B). (2) The previously-proposed `RAZORBACK_SPIDER2_DBT_SOURCE_ROOT` production-resolver seam is **removed** — the offline test seam is a pytest monkeypatch only, applied in-process via `CliRunner`, so it can never route a non-spider2 `kind: harbor` dataset to the fixture tree. (3) `exclude_tasks`/`n_tasks` are applied to **source paths before materialization**, with T3b proving `exclude_tasks=[source_slug]` drops the excluded spider2 task.

**Tech Stack:** Python 3.12, pydantic v2 spec models, Typer CLI (`rk run`), pytest (+ `integration` marker), `uv` for the live smoke.

## Global Constraints

- `auto-approve: false` — this task touches the spec/translate surface; changes are reviewed before merge. (entity frontmatter + Problem §)
- Tests run against a local fixture source tree so the suite stays deterministic; the live `harbor download spider2-dbt@1.0` (bare CLI ref) is a smoke, not a gating AC. The user-facing spec contract is the fully-qualified `spider2-dbt/spider2-dbt@1.0`. (spec Problem § + AC-1)
- Out of scope: the dbt-deps image layer / preflight (`spider2-dbt-harbor-view-ade-parity`), the verifier (`spider2-dbt-duckdb-match-verifier`), and any local raw-dataset generator fallback (deferred unless the live smoke fails). (spec Out of scope §)
- Materialized views MUST be leakage-clean: `materialize_spider2_harbor_task_view` already excludes `SPIDER2_DBT_DENY_GLOBS` (`src/razorback/benchmarks/spider2_dbt/harbor_view.py:10`); do not weaken it.
- Errors must surface as `SpecError` so `rk run` returns SPEC_ERROR exit code, matching the existing pass-through and harbor-local branches. (`translate.py:431-432`, `_build_harbor_local` `translate.py:240`)

---

## AC ↔ Task map

| AC | Requirement (verbatim, abbreviated) | Tasks | Governing cites |
| --- | --- | --- | --- |
| AC-1 | A `kind: harbor` / `dataset: spider2-dbt/spider2-dbt@1.0` spec resolves to N spider2 task-view dirs; each emitted dir has `task.toml` and is leakage-clean (`rg -l 'gold\|expected\|golden'` → no matches). | T1 (family detect), T2 (filter-then-materialize in `_build_harbor`), T3 (multi-task + leakage-clean), T3b (`exclude_tasks` on source slug) | spec AC-1; `translate.py:_build_harbor` 260-330; `harbor_view.py:materialize_spider2_harbor_task_view` 17-38; `SPIDER2_DBT_DENY_GLOBS` 10-14; `materialize.py:_view_name` 143-146 |
| AC-2 | Each materialized view carries `RAZORBACK_BENCHMARK_KIND=spider2-dbt` and `RAZORBACK_BENCHMARK_TASK_ID`. | T4 (env assertion on emitted view `task.toml`) | spec AC-2; `harbor_view.py:31-35`; `materialize.py:_patch_task_toml` 122-140 |
| AC-3 | `rk run <fixture-spec>.frozen.yaml --explain` exits 0 and prints one task line per fixture instance. | T5 (fixture frozen spec), T6 (in-process `CliRunner` `--explain` test with resolver monkeypatch) | spec AC-3 + Test plan; `cli/run.py:run_command` 145 + `spec_to_job_config` call 307; `cli/run_explain.py:_sample_task_prompt_inputs` 37-59; `tests/unit/test_rk_run_harbor_cache_dir.py` (CliRunner pattern) |
| — | Live `uv run harbor download spider2-dbt@1.0 --export` smoke (non-gating, **bare** CLI ref); record exit status + task-dir count; re-check PKG-40 blocker; name raw-dataset-generator fallback decision if it still fails. | T7 (documented live smoke + fallback decision in validation handoff) | spec Test plan + Out of scope; `notes/pkg40-spider2-harbor-surface.md:44-56` |

**Riskiest-mechanism-first ordering note:** T2 (filter-then-materialize inside `_build_harbor`) is the load-bearing contract — it is the smallest end-to-end exercise of "resolved source dir → selector filter on source slug → materialized leakage-clean view → `TaskConfig`". It is implemented and proven (T3, T3b) before the CLI-level `--explain` test (T6) and before the live smoke (T7). The selector-ordering subtlety (filter must precede materialize) is the highest-risk correctness trap, so T3b pins it with a dedicated test immediately after T3. The live registry path is known-blocked (PKG-40), so it is deliberately the *last*, non-gating step; the in-process monkeypatch seam is the gating path throughout.

---

## File Structure

- `src/razorback/translate.py` — **modify**. Add spider2-dbt family detection (`_is_spider2_dbt_dataset`) + a filter-then-materialize branch inside `_build_harbor`. This is the single wiring point; no new module needed because `materialize_spider2_harbor_task_view` and `_resolve_harbor_dataset_tasks` already exist. **No env-var seam is added to `_resolve_harbor_dataset_tasks`** — it is left untouched.
- `src/razorback/benchmarks/spider2_dbt/harbor_view.py` — **read-only** reference (already exports `materialize_spider2_harbor_task_view` + `SPIDER2_DBT_DENY_GLOBS`). Do not edit.
- `tests/unit/test_translate_spider2_dbt.py` — **create**. Unit + integration-level translator coverage for the new branch (family detect, filter-then-materialize, leakage-clean, env, `exclude_tasks`/`n_tasks` on source slugs), using the `_resolve_harbor_dataset_tasks` monkeypatch seam.
- `tests/fixtures/spider2_dbt/harbor_task_minimal/` — **extend**. Add a second fixture instance (`spider2-fixture-002`) so AC-3's "one task line per fixture instance" exercises N>1, AC-1's "N task-view dirs" is genuinely plural, and T3b's `exclude_tasks` has a second task to keep after dropping one.
- `tests/fixtures/spider2_dbt/specs/spider2-dbt-fixture.frozen.yaml` — **create**. A frozen `kind: harbor` spider2-dbt spec (fully-qualified `dataset: spider2-dbt/spider2-dbt@1.0`) for the AC-3 `rk run --explain` command.
- `tests/integration/test_rk_run_spider2_dbt_explain.py` — **create**. In-process `CliRunner` `rk run --explain` test (AC-3); monkeypatches `_resolve_harbor_dataset_tasks` to return fixture sources — no subprocess, no env seam.
- `docs/razorback-implementation/validation/spider2-dbt-source-resolution-and-run-wiring.md` — **created by validation stage** (T7 names what the live-smoke section must contain; the plan does not pre-write it).

---

## Design decision locked at plan time

**How spider2-dbt is recognized for routing through the materializer.** The captain chose the harbor-package source path "mirroring the ade-bench dataset-ref flow." So the dataset ref stays the resolution mechanism and we detect the family by the dataset's short-name being `spider2-dbt`. Concretely: parse `block.dataset` with `harbor.models.package.reference.PackageReference.parse` (already imported in the schema validator at `spec/schema.py:210`) and treat `parsed.short_name == "spider2-dbt"` as the family signal. This avoids a new spec field (YAGNI) and keeps `kind: harbor` generic. Rationale recorded here so the implementer does not invent a `family:` field.

**Why `parsed.short_name`, not a raw string match:** verified live at plan time (rework cycle 1) — `PackageReference.parse("spider2-dbt@1.0")` (the bare short form) *raises* a pydantic ValidationError ("Package name must be …"), while `PackageReference.parse("spider2-dbt/spider2-dbt@1.0")` succeeds with `short_name == "spider2-dbt"` and `org == "spider2-dbt"`. So `short_name` is the stable detection signal, and `_is_spider2_dbt_dataset` returns False for the unparseable bare form (it catches the exception). `spec/schema.py:209-226` *requires* `<org>/<name>@<ref>` (must contain both `/` and `@`) when `plugin is None`, which aligns: the fixture frozen spec (T5) uses the fully-qualified `spider2-dbt/spider2-dbt@1.0` (org==name parses fine — confirmed) to stay schema-valid without a schema change. The bare `spider2-dbt@1.0` form is purely the `harbor download` CLI concept and is exercised only by the non-gating live smoke (T7), never as a spec dataset ref. **Captain decision (cycle 1, option B):** no schema support is added for the bare ref.

**Selector ordering — filter source paths BEFORE materialization (locked).** Today the generic `_build_harbor` applies `exclude_tasks`/`n_tasks` against `p.name` of the resolved list (`translate.py:312-317`). For spider2-dbt this list would be the materialized *view* dirs, whose names are `spider2-dbt-<source_slug>` (`materialize.py:_view_name` 143-146, confirmed live). A user writing `exclude_tasks: ["spider2-fixture-001"]` (the Harbor source slug) would therefore silently match nothing. Decision: the spider2-dbt branch applies the selectors to the resolved **source paths** first, then materializes only the surviving source dirs. This keeps selector semantics bound to original Harbor task names, identical to the generic harbor path. The generic (non-spider2) path is unchanged. T3b proves `exclude_tasks=["spider2-fixture-001"]` drops exactly that source task from the emitted views.

**No production env seam (locked).** The CLI-level AC-3 test does NOT need a `RAZORBACK_SPIDER2_DBT_SOURCE_ROOT` env branch in `_resolve_harbor_dataset_tasks` (that branch would be reached for every `kind: harbor` dataset and could route any leaked env var to the spider2 fixture tree — defect 2). Instead T6 invokes `rk run --explain` **in-process** with Typer's `CliRunner` (the established pattern in `tests/unit/test_rk_run_harbor_cache_dir.py`, which patches `razorback.cli.run.*` in-process). Because the resolver lives in-process under `CliRunner`, a pytest `monkeypatch.setattr("razorback.translate._resolve_harbor_dataset_tasks", ...)` reaches it — no subprocess, no env var, no production-code seam. `_resolve_harbor_dataset_tasks` is left entirely untouched.

**Deterministic test seam.** The existing harbor-block tests monkeypatch `razorback.translate._resolve_harbor_dataset_tasks` to return fixed source dirs (`tests/unit/test_translate_harbor_block.py:103-108`). T3/T3b/T4 reuse exactly that seam: the patched resolver returns the fixture instance dirs under `tests/fixtures/spider2_dbt/harbor_task_minimal/`, and the new `_build_harbor` branch filters then materializes them into `tmp_path`. T6 reuses the same seam through `CliRunner` so the CLI-level `--explain` path is offline and deterministic too.

---

## Task 1: Detect the spider2-dbt family inside `_build_harbor`

**Files:**
- Modify: `src/razorback/translate.py` (`_build_harbor`, around the `else:` pass-through branch at `260-330`)
- Test: `tests/unit/test_translate_spider2_dbt.py` (create)

**Interfaces:**
- Consumes: `block.dataset: str` (from `HarborBenchmarkBlock`, `spec/schema.py:190`); `harbor.models.package.reference.PackageReference.parse` (already used at `spec/schema.py:210`).
- Produces: a module-level helper `_is_spider2_dbt_dataset(dataset_ref: str) -> bool` in `translate.py`, consumed by T2.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_translate_spider2_dbt.py
from razorback.translate import _is_spider2_dbt_dataset


def test_detects_spider2_dbt_fully_qualified():
    # Spec datasets with plugin=None must be fully qualified <org>/<name>@<ref>
    # (spec/schema.py:209-226). PackageReference.parse rejects the bare short
    # form, so only the qualified form is a valid spec dataset.
    assert _is_spider2_dbt_dataset("spider2-dbt/spider2-dbt@1.0") is True


def test_rejects_non_spider2_dataset():
    assert _is_spider2_dbt_dataset("adyen/dabstep@latest") is False


def test_rejects_unparseable_short_form():
    # The bare `spider2-dbt@1.0` form is the `harbor download` CLI concept,
    # NOT a valid spec dataset ref — PackageReference.parse raises on it, and
    # the helper swallows the error and returns False. Verified at plan time.
    assert _is_spider2_dbt_dataset("spider2-dbt@1.0") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/unit/test_translate_spider2_dbt.py -k "spider2_dbt or non_spider2 or short_form" -v`
Expected: FAIL — `ImportError: cannot import name '_is_spider2_dbt_dataset'`

- [ ] **Step 3: Write minimal implementation**

Add near the other `_build_harbor` helpers in `src/razorback/translate.py`:

```python
SPIDER2_DBT_SHORT_NAME = "spider2-dbt"


def _is_spider2_dbt_dataset(dataset_ref: str) -> bool:
    """True when a `kind: harbor` dataset ref names the spider2-dbt family.

    Mirrors the ade-bench dataset-ref flow: the dataset ref is the family
    signal. Both the short `spider2-dbt@1.0` and fully-qualified
    `<org>/spider2-dbt@<ref>` forms resolve to short_name == "spider2-dbt".
    """
    from harbor.models.package.reference import PackageReference

    try:
        parsed = PackageReference.parse(dataset_ref)
    except Exception:
        return False
    return parsed.short_name == SPIDER2_DBT_SHORT_NAME
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/unit/test_translate_spider2_dbt.py -k "spider2_dbt or non_spider2 or short_form" -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_translate_spider2_dbt.py src/razorback/translate.py
git commit -m "feat(translate): detect spider2-dbt dataset family by short name"
```

---

## Task 2: Filter-then-materialize for spider2-dbt in `_build_harbor`

**Files:**
- Modify: `src/razorback/translate.py` (`_build_harbor` pass-through branch `302-310`, the shared selector block `312-317`, and `tasks_root` threading)
- Test: `tests/unit/test_translate_spider2_dbt.py` (extend)

**Interfaces:**
- Consumes: `_is_spider2_dbt_dataset` (T1); `_resolve_harbor_dataset_tasks(*, dataset_ref, tasks, cache_root) -> list[Path]` (`translate.py:422`); `materialize_spider2_harbor_task_view(*, source_task_dir, view_root, task_slug, docker_image=None, view_mode="copy") -> Path` (`harbor_view.py:17`); `tasks_root: Path | None` already passed to `_build_harbor` (`translate.py:74-80`).
- Produces: for a spider2-dbt dataset, `job_config.tasks[i].path` points at a materialized view dir under `tasks_root`, one per resolved source dir that survives the `exclude_tasks`/`n_tasks` filter applied to **source** names. For non-spider2 datasets, behavior is unchanged.

**Design note:** Today `tasks_root` is only consumed by the `plugin:` branch (`translate.py:296-301`); the pass-through branch ignores it, and the shared selector block at `312-317` filters the resolved list by `p.name`. The fix has two parts:

1. **Filter before materialize.** For the spider2-dbt branch the selector filter MUST run on the resolved *source* paths (whose `.name` is the Harbor source slug, e.g. `spider2-fixture-001`), not on materialized view dirs (whose `.name` is `spider2-dbt-<slug>`, `materialize.py:143-146`). The cleanest structure: hoist the existing `exclude_tasks`/`n_tasks` filter so it runs on `source_paths` inside the `else:` (non-plugin) branch, then materialize the survivors. The generic (non-spider2) path keeps identical behavior because it filtered source dirs by name already — only the *location* of the filter relative to a new materialize step changes, and only for spider2-dbt. (The `plugin:` branch retains its own post-filter; see Step 3.)

2. **`tasks_root` guard.** When the family is spider2-dbt and `tasks_root` is None (e.g. unit tests calling `spec_to_job_config` without it), raise a `SpecError` — the run orchestrator always passes `run_dir / "tasks"` (`cli/run.py:311`), so a None `tasks_root` for spider2-dbt is a programming error, mirroring the plugin branch's guard at `translate.py:291-295`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_translate_spider2_dbt.py  (append)
from pathlib import Path

import pytest

from razorback.spec.schema import HarborBenchmarkBlock, NopAgentBlock, Spec
from razorback.translate import spec_to_job_config

FIXTURE_ROOT = (
    Path(__file__).parent.parent
    / "fixtures" / "spider2_dbt" / "harbor_task_minimal"
)


def _spec(benchmark):
    return Spec(
        version=1,
        experiment="spider2-translator-smoke",
        agent=NopAgentBlock(kind="nop"),
        benchmark=benchmark,
        trials=1,
        observers=[],
    )


def test_spider2_dataset_materializes_views(tmp_path, monkeypatch):
    source = FIXTURE_ROOT / "spider2-fixture-001"

    def fake_resolver(*, dataset_ref, tasks, cache_root):
        return [source]

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks", fake_resolver
    )
    spec = _spec(
        HarborBenchmarkBlock(
            kind="harbor", dataset="spider2-dbt/spider2-dbt@1.0"
        )
    )
    job_config, trial_name_map = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) == 1
    view_dir = job_config.tasks[0].path
    # emitted path is a materialized VIEW under tasks_root, not the raw source
    assert (tmp_path / "tasks") in view_dir.parents
    assert (view_dir / "task.toml").is_file()
    assert trial_name_map == {}


def test_spider2_dataset_requires_tasks_root(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: [FIXTURE_ROOT / "spider2-fixture-001"],
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="spider2-dbt/spider2-dbt@1.0")
    )
    with pytest.raises(Exception) as exc:
        spec_to_job_config(spec, job_name="job", jobs_dir=tmp_path, tasks_root=None)
    assert "tasks_root" in str(exc.value).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/unit/test_translate_spider2_dbt.py -k "materializes or requires_tasks_root" -v`
Expected: FAIL — `test_spider2_dataset_materializes_views` asserts the emitted path is under `tasks_root`, but the unchanged pass-through branch emits the raw source dir; `test_spider2_dataset_requires_tasks_root` does not raise.

- [ ] **Step 3: Write minimal implementation**

In `src/razorback/translate.py`, add the import at module scope:

```python
from razorback.benchmarks.spider2_dbt.harbor_view import (
    materialize_spider2_harbor_task_view,
)
```

Add a small selector helper near the other `_build_harbor` helpers so both the source-path filter and any future caller share one definition:

```python
def _apply_task_selectors(
    paths: list[Path], *, exclude_tasks: list[str] | None, n_tasks: int | None
) -> list[Path]:
    """Filter task dirs by name, then cap. Operates on whatever `.name` the
    caller passes — for spider2-dbt this MUST be source-slug paths, applied
    BEFORE materialization (view names are `spider2-dbt-<slug>`)."""
    result = paths
    if exclude_tasks:
        excluded = set(exclude_tasks)
        result = [p for p in result if p.name not in excluded]
    if n_tasks is not None:
        result = result[:n_tasks]
    return result
```

Replace the pass-through `else:` block (`translate.py:302-310`) so spider2-dbt filters source paths, then materializes:

```python
    else:
        home_dir = Path(home) if home is not None else Path.home()
        cache_root = home_dir / ".cache" / "razorback" / "harbor" / "datasets"
        source_paths = _resolve_harbor_dataset_tasks(
            dataset_ref=block.dataset,
            tasks=block.tasks,
            cache_root=cache_root,
        )
        if _is_spider2_dbt_dataset(block.dataset):
            if tasks_root is None:
                raise SpecError(
                    "`kind: harbor` spider2-dbt dataset requires tasks_root "
                    "(the run orchestrator passes it)."
                )
            # Filter on SOURCE slugs BEFORE materialization so selectors bind
            # to Harbor task names, not the `spider2-dbt-<slug>` view names.
            selected_sources = _apply_task_selectors(
                source_paths,
                exclude_tasks=block.exclude_tasks,
                n_tasks=block.n_tasks,
            )
            view_root = Path(tasks_root)
            task_paths = [
                materialize_spider2_harbor_task_view(
                    source_task_dir=src,
                    view_root=view_root,
                    task_slug=src.name,
                )
                for src in selected_sources
            ]
            trial_name_map = {}

            cfg = JobConfig(
                job_name=job_name,
                jobs_dir=jobs_dir,
                n_concurrent_trials=spec.concurrency.trials,
                n_attempts=spec.trials,
                agents=[agent_cfg],
                tasks=[TaskConfig(path=p) for p in task_paths],
                verifier=VerifierConfig(disable=False),
                retry=RetryConfig(max_retries=0),
                environment=_environment_config(agent_cfg, run_dir),
            )
            return cfg, trial_name_map

        task_paths = source_paths
        trial_name_map = {}
```

The spider2-dbt branch returns early (it has already applied selectors to source paths). The plugin branch and the generic non-spider2 pass-through fall through to the existing shared selector block (`translate.py:312-317`) and the existing `JobConfig` construction (`319-330`) **unchanged** — non-spider2 behavior is byte-for-byte identical. (Alternative structure if the implementer prefers no early return: skip the shared block for spider2-dbt via an `is_spider2` flag; the early-return form above is preferred for locality. Either way, the spider2 filter runs on source paths and the generic filter on the generic list — never the reverse.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/unit/test_translate_spider2_dbt.py -k "materializes or requires_tasks_root" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full translator suite to confirm no regression in the generic harbor path**

Run: `uv run --frozen pytest tests/unit/test_translate_harbor_block.py -q`
Expected: PASS (existing pass-through / harbor-local tests unchanged — non-spider2 datasets must still emit raw source dirs)

- [ ] **Step 6: Commit**

```bash
git add tests/unit/test_translate_spider2_dbt.py src/razorback/translate.py
git commit -m "feat(translate): materialize spider2-dbt views during kind:harbor resolution"
```

---

## Task 3: Integration test — N task-view dirs, all leakage-clean (AC-1)

**Files:**
- Modify: `tests/fixtures/spider2_dbt/harbor_task_minimal/` — add `spider2-fixture-002` (copy of `-001` shape; second `task.toml` instance)
- Test: `tests/unit/test_translate_spider2_dbt.py` (extend)

**Interfaces:**
- Consumes: the `_build_harbor` spider2 branch (T2).
- Produces: proof of AC-1 — each emitted dir contains `task.toml` and `rg -l 'gold|expected|golden'` over the view returns no matches.

- [ ] **Step 1: Add the second fixture instance**

```bash
cp -R tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-001 \
      tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-002
```

Then edit `tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-002/task.toml` so `[task] name = "spider2-dbt/spider2-fixture-002"` (rename the `001` → `002` in the `name` field only; leave everything else).

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_translate_spider2_dbt.py  (append)
import subprocess


def test_spider2_resolves_n_views_all_leakage_clean(tmp_path, monkeypatch):
    sources = sorted(FIXTURE_ROOT.glob("spider2-fixture-*"))
    assert len(sources) >= 2, "need >1 fixture instance to prove N task-view dirs"

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="spider2-dbt/spider2-dbt@1.0")
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) == len(sources)
    for task in job_config.tasks:
        view = task.path
        assert (view / "task.toml").is_file()
        # leakage-clean: no gold/expected/golden survives the deny-globs
        hit = subprocess.run(
            ["rg", "-l", "gold|expected|golden", str(view)],
            capture_output=True, text=True,
        )
        assert hit.returncode == 1 and hit.stdout == "", (
            f"leakage in {view}: {hit.stdout}"
        )
```

- [ ] **Step 3: Run test to verify it fails (before fixture-002 exists, or to confirm leakage-clean)**

Run: `uv run --frozen pytest tests/unit/test_translate_spider2_dbt.py::test_spider2_resolves_n_views_all_leakage_clean -v`
Expected: PASS once Step 1's fixture exists and T2's materializer applies `SPIDER2_DBT_DENY_GLOBS`. (If it FAILS on the `rg` leakage check, the fixture's `tests/expected/answer.txt` was not excluded — verify `SPIDER2_DBT_DENY_GLOBS` includes `**/expected/**`, `harbor_view.py:11`.)

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-002 \
        tests/unit/test_translate_spider2_dbt.py
git commit -m "test(spider2): N leakage-clean task-view dirs from kind:harbor resolution (AC-1)"
```

---

## Task 3b: `exclude_tasks` on a source slug drops the spider2 task (AC-1, defect-3 proof)

**Files:**
- Test: `tests/unit/test_translate_spider2_dbt.py` (extend)

**Interfaces:**
- Consumes: the `_build_harbor` spider2 branch with filter-before-materialize (T2); the two fixture instances (T3).
- Produces: proof that selectors bind to the original Harbor source slug, not the `spider2-dbt-<slug>` view name — the load-bearing fix for Codex defect 3.

- [ ] **Step 1: Write the failing/guarding test**

```python
# tests/unit/test_translate_spider2_dbt.py  (append)
def test_exclude_tasks_drops_spider2_source_slug(tmp_path, monkeypatch):
    sources = sorted(FIXTURE_ROOT.glob("spider2-fixture-*"))
    assert len(sources) >= 2, "need >1 fixture instance to prove exclusion keeps the other"
    excluded_slug = sources[0].name  # e.g. "spider2-fixture-001" (SOURCE slug)

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )
    spec = _spec(
        HarborBenchmarkBlock(
            kind="harbor",
            dataset="spider2-dbt/spider2-dbt@1.0",
            exclude_tasks=[excluded_slug],
        )
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    # the excluded source produced no view; the others did
    assert len(job_config.tasks) == len(sources) - 1
    view_names = {t.path.name for t in job_config.tasks}
    # filter ran on the SOURCE slug, so neither the source slug nor its
    # `spider2-dbt-<slug>` view appears in the emitted set
    assert excluded_slug not in view_names
    assert f"spider2-dbt-{excluded_slug}" not in view_names
    # sanity: a surviving task's view IS the `spider2-dbt-<slug>` form
    kept_slug = sources[1].name
    assert f"spider2-dbt-{kept_slug}" in view_names
```

- [ ] **Step 2: Run test**

Run: `uv run --frozen pytest tests/unit/test_translate_spider2_dbt.py::test_exclude_tasks_drops_spider2_source_slug -v`
Expected: PASS with T2's filter-before-materialize. This test is the regression pin for defect 3: if a refactor moves the selector filter back after materialization, `excluded_slug` would match no view name, the excluded task would survive, `len(job_config.tasks)` would be `len(sources)` (not `-1`), and this test FAILS — exactly the catch we want.

- [ ] **Step 3: (optional) Prove n_tasks also slices source-side**

```python
# tests/unit/test_translate_spider2_dbt.py  (append)
def test_n_tasks_caps_spider2_before_materialize(tmp_path, monkeypatch):
    sources = sorted(FIXTURE_ROOT.glob("spider2-fixture-*"))
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )
    spec = _spec(
        HarborBenchmarkBlock(
            kind="harbor", dataset="spider2-dbt/spider2-dbt@1.0", n_tasks=1
        )
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) == 1
```

Run: `uv run --frozen pytest tests/unit/test_translate_spider2_dbt.py -k "exclude_tasks_drops or n_tasks_caps" -v`
Expected: PASS (2 passed).

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_translate_spider2_dbt.py
git commit -m "test(spider2): exclude_tasks/n_tasks bind to source slug before materialize (AC-1, defect 3)"
```

---

## Task 4: Each view carries the spider2-dbt benchmark env (AC-2)

**Files:**
- Test: `tests/unit/test_translate_spider2_dbt.py` (extend)

**Interfaces:**
- Consumes: the materialized view `task.toml` from T2; `harbor.models.task.config.TaskConfig.model_validate_toml` (used by the materializer at `materialize.py:129`).
- Produces: proof of AC-2.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_translate_spider2_dbt.py  (append)
from harbor.models.task.config import TaskConfig as HarborTaskConfig


def test_materialized_view_carries_benchmark_env(tmp_path, monkeypatch):
    source = FIXTURE_ROOT / "spider2-fixture-001"
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: [source],
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="spider2-dbt/spider2-dbt@1.0")
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    view_toml = job_config.tasks[0].path / "task.toml"
    cfg = HarborTaskConfig.model_validate_toml(view_toml.read_text())
    assert cfg.environment.env["RAZORBACK_BENCHMARK_KIND"] == "spider2-dbt"
    assert cfg.environment.env["RAZORBACK_BENCHMARK_TASK_ID"] == "spider2-fixture-001"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run --frozen pytest tests/unit/test_translate_spider2_dbt.py::test_materialized_view_carries_benchmark_env -v`
Expected: PASS — `materialize_spider2_harbor_task_view` injects both env keys (`harbor_view.py:31-35`) and `task_slug=src.name` (T2) gives `RAZORBACK_BENCHMARK_TASK_ID == "spider2-fixture-001"`.

(This test passes immediately because T2 already wires the env; it exists to *prove* AC-2 explicitly and to guard against a future refactor dropping `task_slug`.)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_translate_spider2_dbt.py
git commit -m "test(spider2): assert materialized view carries benchmark env (AC-2)"
```

---

## Task 5: Fixture frozen spec for `rk run --explain`

**Files:**
- Create: `tests/fixtures/spider2_dbt/specs/spider2-dbt-fixture.frozen.yaml`

**Interfaces:**
- Consumes: nothing new at runtime — the spec is parsed by `parse_spec_file` (`src/razorback/spec/parse.py:26`).
- Produces: a schema-valid frozen `kind: harbor` spider2-dbt spec used by T6.

**No env seam (defect 2 resolution):** the prior plan added a `RAZORBACK_SPIDER2_DBT_SOURCE_ROOT` branch to `_resolve_harbor_dataset_tasks` so the subprocess `--explain` test could resolve offline. That branch was reachable by *every* `kind: harbor` dataset and is removed. T6 instead runs `rk run --explain` in-process via `CliRunner` and monkeypatches `_resolve_harbor_dataset_tasks` directly — the resolver never reaches the live registry, and `_resolve_harbor_dataset_tasks` keeps no test-only code path. So Task 5 is now just the fixture spec; there is no production-code change here.

- [ ] **Step 1: Create the fixture frozen spec**

Write `tests/fixtures/spider2_dbt/specs/spider2-dbt-fixture.frozen.yaml`. Use a NOP agent so `--explain` needs no auth, and the fully-qualified dataset ref so the schema validator accepts it (see "Design decision locked at plan time"):

```yaml
# ABOUTME: Fixture frozen spec — kind:harbor spider2-dbt for rk run --explain (AC-3).
# ABOUTME: T6 resolves it offline by monkeypatching _resolve_harbor_dataset_tasks in-process.
version: 1
experiment: spider2-dbt-fixture
agent:
  kind: nop
benchmark:
  kind: harbor
  dataset: spider2-dbt/spider2-dbt@1.0
  tasks: null
  exclude_tasks: null
  n_tasks: null
  plugin: null
  plugin_args: null
trials: 1
concurrency:
  trials: 1
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
```

- [ ] **Step 2: Verify the spec parses (schema validity check)**

Run (import path confirmed at plan time — `parse_spec_file` lives in `src/razorback/spec/parse.py:26`):
```bash
uv run --frozen python -c "from razorback.spec.parse import parse_spec_file; from pathlib import Path; s = parse_spec_file(Path('tests/fixtures/spider2_dbt/specs/spider2-dbt-fixture.frozen.yaml')); print(s.benchmark.dataset)"
```
Expected: prints `spider2-dbt/spider2-dbt@1.0` with no validation error (org==name confirmed to parse at plan time). A bare `dataset: spider2-dbt@1.0` here would instead raise the schema validator's "required shape is `<org>/<name>@<ref>`" error (`spec/schema.py:221-226`) — confirming the contract.

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/spider2_dbt/specs/spider2-dbt-fixture.frozen.yaml
git commit -m "test(spider2): fixture frozen kind:harbor spec for rk run --explain (AC-3)"
```

---

## Task 6: `rk run --explain` lists resolved tasks (AC-3) — in-process, no env seam

**Files:**
- Create: `tests/integration/test_rk_run_spider2_dbt_explain.py`

**Interfaces:**
- Consumes: the fixture frozen spec (T5); `rk run ... --explain` via Typer `CliRunner` (`cli/run.py:run_command` 145, `--explain` short-circuit at `335-346`); `razorback.translate._resolve_harbor_dataset_tasks` (monkeypatched).
- Produces: proof of AC-3 — exit 0 and one task entry per fixture instance.

**Why in-process (defect 2):** the prior plan ran `rk run` as a subprocess and used the `RAZORBACK_SPIDER2_DBT_SOURCE_ROOT` env seam to keep it offline — the seam that defect 2 rejects. Running `rk run --explain` in-process via `CliRunner` (the pattern in `tests/unit/test_rk_run_harbor_cache_dir.py`) lets a `monkeypatch.setattr("razorback.translate._resolve_harbor_dataset_tasks", ...)` reach the resolver, so the test is offline with zero production-code seam. Confirmed at plan time: `--explain` returns at `cli/run.py:335-346` *before* `_invoke_harbor`, so no harbor subprocess is launched; and the fixture spec carries no `provenance:` block, so the model/harbor-drift pre-checks (`run.py:223-236`) are skipped — no model-resolution patch is needed.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_rk_run_spider2_dbt_explain.py
# ABOUTME: AC-3 — rk run --explain on a fixture spider2-dbt spec lists resolved tasks.
# ABOUTME: In-process via CliRunner; resolver is monkeypatched (offline, no env seam).
import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "tests" / "fixtures" / "spider2_dbt" / "specs" / "spider2-dbt-fixture.frozen.yaml"
SOURCE_ROOT = REPO / "tests" / "fixtures" / "spider2_dbt" / "harbor_task_minimal"


def test_rk_run_explain_lists_spider2_tasks(tmp_path, monkeypatch):
    sources = sorted(SOURCE_ROOT.glob("spider2-fixture-*"))
    n_instances = len(sources)
    assert n_instances >= 1

    # Offline + deterministic: the in-process resolver returns fixture sources.
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        app,
        [
            "run", str(SPEC),
            "--runs-dir", str(tmp_path / "_runs"),
            "--explain", "--explain-format", "json",
        ],
    )
    assert result.exit_code == 0, result.stderr or result.stdout

    payload = json.loads(result.stdout)
    # AC-3: one task entry per fixture instance.
    # task_paths nests under "prompt" (run_explain.py:254 → _prompt_plan
    # spreads **_sample_task_prompt_inputs which carries task_paths, :52).
    task_paths = payload["prompt"]["task_paths"]
    assert len(task_paths) == n_instances
    # emitted paths are materialized spider2-dbt views, not raw source dirs
    assert all(Path(p).name.startswith("spider2-dbt-") for p in task_paths)
```

- [ ] **Step 2: Run test to verify the explain payload shape, then make it pass**

Run: `uv run --frozen pytest tests/integration/test_rk_run_spider2_dbt_explain.py -v`
Confirmed JSON shape (verified at plan time): `_sample_task_prompt_inputs` (`run_explain.py:37-59`) emits `task_paths` / `task_count`; the top-level payload nests it under the `prompt` key (`run_explain.py:254`). So extraction is `payload["prompt"]["task_paths"]`.
Expected: PASS — exit 0, `len(task_paths) == n_instances`, every path is a `spider2-dbt-<slug>` view (proving materialization ran through the CLI path end-to-end).

- [ ] **Step 3: Verify the human-facing markdown command works too (optional manual check)**

The spec's literal acceptance command resolves live (registry, PKG-40-blocked), so the offline equivalent is the in-process JSON test above. For a markdown sanity check, run the same `CliRunner` invocation with `--explain` and no `--explain-format`, or add a second assertion on `result.stdout` containing `Tasks: \`{n_instances}\``. Optional; T6 Step 2 is the gating proof.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_rk_run_spider2_dbt_explain.py
git commit -m "test(spider2): rk run --explain lists resolved spider2-dbt tasks in-process (AC-3)"
```

---

## Task 7: Live smoke (non-gating) + raw-dataset-generator fallback decision

**Files:**
- The live-smoke result + fallback decision are recorded by the **validation stage** in `docs/razorback-implementation/validation/spider2-dbt-source-resolution-and-run-wiring.md`. This task documents exactly what that section must capture; it adds no gating test.

**Interfaces:**
- Consumes: nothing in the harness — this exercises the live registry path that the fixture seam deliberately bypasses.
- Produces: a recorded exit status + task-dir count, a re-check of the PKG-40 git-checkout blocker, and a named decision on the raw-dataset-generator fallback.

- [ ] **Step 1: Run the live smoke and capture exit status + task-dir count**

Run:
```bash
uv run harbor download spider2-dbt@1.0 \
  --output-dir runs/spider2-wiring-smoke/spider2-download --export --overwrite
echo "exit=$?"
find runs/spider2-wiring-smoke/spider2-download -maxdepth 3 -name task.toml | wc -l
```
Record both the exit status and the task.toml count verbatim in the validation report.

- [ ] **Step 2: Re-check the PKG-40 blocker and name the fallback decision**

Compare against PKG-40's recorded failure (`docs/razorback-implementation/notes/pkg40-spider2-harbor-surface.md:49-56`: `git checkout 82d1fb0c... exit 128`).

- **If the live download SUCCEEDS** (task-dir count > 0): note that the blocker has cleared; the fixture-backed tests remain the gating path, and add a (separate, future) integration-marked test that resolves `spider2-dbt@1.0` live — out of scope for this task, name it as a follow-up only.
- **If the live download STILL FAILS** (git-checkout blocker persists): record the exit status and stderr. Then name the fallback decision explicitly: per the spec's Out of scope §, a local raw-dataset generator is "deferred unless the live smoke fails." If it fails, the decision to surface to the captain is **defer vs. build the raw-dataset generator** — the recommendation is to defer (fixture-backed tests already gate AC-1/AC-2/AC-3; the generator is its own task), but the FO/captain owns the call. Do **not** build the generator inside this task.

- [ ] **Step 3: No commit for this task in the worktree**

The validation report lives on the state checkout / validation stage, not the implementation worktree. The implementation worktree is complete after T6. This task is a checklist the validation worker executes; it produces no code commit.

---

## Self-Review

**1. Spec coverage:**
- AC-1 → T1 (detect) + T2 (filter-then-materialize) + T3 (N dirs, leakage-clean) + T3b (`exclude_tasks` on source slug). ✓
- AC-2 → T4 (env on view `task.toml`). ✓
- AC-3 → T5 (fixture spec) + T6 (in-process `CliRunner` `rk run --explain`). ✓
- Test plan's live non-gating smoke (bare CLI ref) + PKG-40 re-check + fallback decision → T7. ✓
- Out of scope (image layer, verifier, raw-dataset generator) → honored; T7 explicitly defers the generator; image/verifier untouched. ✓

**2. Cycle-1 defect resolution (all three resolved in the plan, none deferred to the implementer):**
- **Defect 1 (dataset-ref contract, captain option B):** the user-facing contract is `spider2-dbt/spider2-dbt@1.0` in the entity Problem § + AC-1, the plan goal/architecture/design sections, and the T5 fixture spec. The bare `spider2-dbt@1.0` is the T7 `harbor download` CLI smoke only; no schema support added. Detection helper `_is_spider2_dbt_dataset` returns False on the bare form (it does not parse).
- **Defect 2 (env-override hijack):** the `RAZORBACK_SPIDER2_DBT_SOURCE_ROOT` production-resolver seam is removed entirely; `_resolve_harbor_dataset_tasks` is untouched. The offline seam is a pytest monkeypatch applied in-process (T6 via `CliRunner`), so it can never capture a non-spider2 `kind: harbor` dataset.
- **Defect 3 (`exclude_tasks` semantics):** T2 applies `exclude_tasks`/`n_tasks` to source paths BEFORE materialization (`_apply_task_selectors` on `source_paths`), so selectors bind to original Harbor slugs. T3b proves `exclude_tasks=[source_slug]` drops the excluded spider2 task and pins the ordering against regression.

**3. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step shows actual code; every command shows expected output.

**4. Type consistency:** `_is_spider2_dbt_dataset(dataset_ref: str) -> bool` defined T1, consumed T2. `_apply_task_selectors(paths, *, exclude_tasks, n_tasks) -> list[Path]` defined + consumed in T2. `materialize_spider2_harbor_task_view(*, source_task_dir, view_root, task_slug, ...)` used T2 matches `harbor_view.py:17`. `_resolve_harbor_dataset_tasks(*, dataset_ref, tasks, cache_root)` monkeypatched consistently across T2–T4 and T6 matches `translate.py:422`. `tasks_root` threading matches `spec_to_job_config`→`_build_harbor` (`translate.py:51,74-80`).

**Plan-time verifications (run live against the repo this cycle, not assumed):**
- `PackageReference.parse` rejects bare `spider2-dbt@1.0` (pydantic ValidationError) and accepts `spider2-dbt/spider2-dbt@1.0` (org==name, short_name=="spider2-dbt") — re-confirmed cycle 1. Detection + fixture-spec ref design rely on this.
- `spec/schema.py:209-226` requires `<org>/<name>@<ref>` (both `/` and `@`) when `plugin is None`, so the bare ref is rejected at spec-parse time — confirmed by reading the validator.
- `materialize.py:_view_name` (143-146) yields `spider2-dbt-<slug>`, so a post-materialization `p.name` filter can never match a source slug — the root cause of defect 3, confirmed by reading the function.
- `rk run --explain` short-circuits at `cli/run.py:335-346` (returns before `_invoke_harbor`); the JSON payload nests `task_paths` under `prompt` (`run_explain.py:254` + `:52`) — T6 in-process design + extraction confirmed.
- The `CliRunner` in-process invocation pattern for `rk run` exists in `tests/unit/test_rk_run_harbor_cache_dir.py`; the fixture spec has no `provenance:` block so model/harbor drift checks are skipped — T6 needs only the resolver monkeypatch.
- `parse_spec_file` lives at `src/razorback/spec/parse.py:26` — T5 Step 2 command confirmed.

**Open items:** none. The cycle-1 open item (selector-vs-view-name ambiguity) is now resolved as defect 3 with a locked decision and a dedicated regression test (T3b).
