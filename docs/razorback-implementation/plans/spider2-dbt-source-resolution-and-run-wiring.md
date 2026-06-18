# spider2-dbt — source resolution + rk run materialization wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire spider2-dbt in as a recognized `kind: harbor` benchmark family so a `dataset: spider2-dbt@1.0` spec resolves source task dirs, runs each through `materialize_spider2_harbor_task_view`, and emits leakage-clean `TaskConfig(path=view_dir)` entries that `rk run --explain` can list.

**Architecture:** The wiring point is `_build_harbor` in `src/razorback/translate.py`. Today its pure pass-through branch (no `plugin:`) resolves a dataset ref into source task dirs via `_resolve_harbor_dataset_tasks` and emits them verbatim. We add a spider2-dbt detection branch: when the dataset ref names the spider2-dbt family, each resolved source dir is run through `materialize_spider2_harbor_task_view` into the run's `tasks_root`, and the emitted `TaskConfig.path` points at the materialized view (not the raw source). Selectors (`exclude_tasks`, `n_tasks`) continue to apply on the post-resolution list. Tests are fixture-backed against `tests/fixtures/spider2_dbt/` and inject the source-dir list through the same resolver-monkeypatch seam already used by the existing harbor-block tests, so the suite never touches the network. The live `harbor download spider2-dbt@1.0 --export` smoke stays a non-gating validation-report probe (PKG-40 recorded its git-checkout failure).

**Tech Stack:** Python 3.12, pydantic v2 spec models, Typer CLI (`rk run`), pytest (+ `integration` marker), `uv` for the live smoke.

## Global Constraints

- `auto-approve: false` — this task touches the spec/translate surface; changes are reviewed before merge. (entity frontmatter + Problem §)
- Tests run against a local fixture source tree so the suite stays deterministic; the live `spider2-dbt@1.0` download is a smoke, not a gating AC. (spec Problem §)
- Out of scope: the dbt-deps image layer / preflight (`spider2-dbt-harbor-view-ade-parity`), the verifier (`spider2-dbt-duckdb-match-verifier`), and any local raw-dataset generator fallback (deferred unless the live smoke fails). (spec Out of scope §)
- Materialized views MUST be leakage-clean: `materialize_spider2_harbor_task_view` already excludes `SPIDER2_DBT_DENY_GLOBS` (`src/razorback/benchmarks/spider2_dbt/harbor_view.py:10`); do not weaken it.
- Errors must surface as `SpecError` so `rk run` returns SPEC_ERROR exit code, matching the existing pass-through and harbor-local branches. (`translate.py:431-432`, `_build_harbor_local` `translate.py:240`)

---

## AC ↔ Task map

| AC | Requirement (verbatim, abbreviated) | Tasks | Governing cites |
| --- | --- | --- | --- |
| AC-1 | A `kind: harbor` / `dataset: spider2-dbt@1.0` spec resolves to N spider2 task-view dirs; each emitted dir has `task.toml` and is leakage-clean (`rg -l 'gold\|expected\|golden'` → no matches). | T1 (family detect), T2 (materialize-on-resolve in `_build_harbor`), T3 (multi-task + leakage-clean integration test) | spec AC-1; `translate.py:_build_harbor` 260-330; `harbor_view.py:materialize_spider2_harbor_task_view` 17-38; `SPIDER2_DBT_DENY_GLOBS` 10-14 |
| AC-2 | Each materialized view carries `RAZORBACK_BENCHMARK_KIND=spider2-dbt` and `RAZORBACK_BENCHMARK_TASK_ID`. | T4 (env assertion on emitted view `task.toml`) | spec AC-2; `harbor_view.py:31-35`; `materialize.py:_patch_task_toml` 122-140 |
| AC-3 | `rk run <fixture-spec>.frozen.yaml --explain` exits 0 and prints one task line per fixture instance. | T5 (fixture frozen spec + deterministic source seam), T6 (`rk run --explain` end-to-end test) | spec AC-3 + Test plan; `cli/run.py:307` (`spec_to_job_config` call), `cli/run_explain.py:_sample_task_prompt_inputs` 37-59 + `_preparation_plan` 161-165 |
| — | Live `uv run harbor download spider2-dbt@1.0 --export` smoke (non-gating); record exit status + task-dir count; re-check PKG-40 blocker; name raw-dataset-generator fallback decision if it still fails. | T7 (documented live smoke + fallback decision in validation handoff) | spec Test plan + Out of scope; `notes/pkg40-spider2-harbor-surface.md:44-56` |

**Riskiest-mechanism-first ordering note:** T2 (materialize-on-resolve inside `_build_harbor`) is the load-bearing contract — it is the smallest end-to-end exercise of "resolved source dir → materialized leakage-clean view → `TaskConfig`". It is implemented and proven (T3) before the CLI-level `--explain` test (T6) and before the live smoke (T7). The live registry path is known-blocked (PKG-40), so it is deliberately the *last*, non-gating step; the fixture-backed seam is the gating path throughout.

---

## File Structure

- `src/razorback/translate.py` — **modify**. Add spider2-dbt family detection + a materialize-on-resolve branch inside `_build_harbor`. This is the single wiring point; no new module needed because `materialize_spider2_harbor_task_view` and `_resolve_harbor_dataset_tasks` already exist.
- `src/razorback/benchmarks/spider2_dbt/harbor_view.py` — **read-only** reference (already exports `materialize_spider2_harbor_task_view` + `SPIDER2_DBT_DENY_GLOBS`). Do not edit.
- `tests/unit/test_translate_spider2_dbt.py` — **create**. Unit + integration-level translator coverage for the new branch (family detect, materialize-on-resolve, leakage-clean, env, selectors), using the resolver-monkeypatch seam.
- `tests/fixtures/spider2_dbt/harbor_task_minimal/` — **extend**. Add a second fixture instance (`spider2-fixture-002`) so AC-3's "one task line per fixture instance" exercises N>1, and so AC-1's "N task-view dirs" is genuinely plural.
- `tests/fixtures/spider2_dbt/specs/spider2-dbt-fixture.frozen.yaml` — **create**. A frozen `kind: harbor` spider2-dbt spec for the AC-3 `rk run --explain` command.
- `tests/integration/test_rk_run_spider2_dbt_explain.py` — **create**. End-to-end `rk run --explain` test (AC-3).
- `docs/razorback-implementation/validation/spider2-dbt-source-resolution-and-run-wiring.md` — **created by validation stage** (T7 names what the live-smoke section must contain; the plan does not pre-write it).

---

## Design decision locked at plan time

**How spider2-dbt is recognized for routing through the materializer.** The captain chose the harbor-package source path "mirroring the ade-bench dataset-ref flow." So the dataset ref stays the resolution mechanism and we detect the family by the dataset's short-name being `spider2-dbt`. Concretely: parse `block.dataset` with `harbor.models.package.reference.PackageReference.parse` (already imported in the schema validator at `spec/schema.py:210`) and treat `parsed.short_name == "spider2-dbt"` as the family signal. This avoids a new spec field (YAGNI) and keeps `kind: harbor` generic. Rationale recorded here so the implementer does not invent a `family:` field.

**Why `parsed.short_name`, not a raw string match:** verified at plan time — `PackageReference.parse("spider2-dbt@1.0")` (the bare short form) *raises* a pydantic ValidationError ("name must be in 'org/name' format"), while `PackageReference.parse("spider2-dbt/spider2-dbt@1.0")` succeeds with `short_name == "spider2-dbt"` and `org == "spider2-dbt"`. So `short_name` is the stable detection signal, and `_is_spider2_dbt_dataset` returns False for the unparseable short form (it catches the exception). `spec/schema.py:209-226` *requires* `<org>/<name>@<ref>` when `plugin is None`, which aligns: the fixture frozen spec (T5) uses the fully-qualified `spider2-dbt/spider2-dbt@1.0` (org==name parses fine — confirmed) to stay schema-valid without a schema change. The bare `spider2-dbt@1.0` form is purely the `harbor download` CLI concept and is exercised only by the non-gating live smoke (T7), never as a spec dataset ref.

**Deterministic test seam.** The existing harbor-block tests monkeypatch `razorback.translate._resolve_harbor_dataset_tasks` to return fixed source dirs (`tests/unit/test_translate_harbor_block.py:103-108`). T3/T4 reuse exactly that seam: the patched resolver returns the fixture instance dirs under `tests/fixtures/spider2_dbt/harbor_task_minimal/`, and the new `_build_harbor` branch materializes them into `tmp_path`. For the CLI-level AC-3 test (T6), the seam is the frozen spec pointing at fixture sources is not enough on its own (the resolver would hit the live registry); see T5 for how `--explain` stays offline.

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

## Task 2: Materialize-on-resolve for spider2-dbt in `_build_harbor`

**Files:**
- Modify: `src/razorback/translate.py` (`_build_harbor` pass-through branch `302-310` and `tasks_root` threading)
- Test: `tests/unit/test_translate_spider2_dbt.py` (extend)

**Interfaces:**
- Consumes: `_is_spider2_dbt_dataset` (T1); `_resolve_harbor_dataset_tasks(*, dataset_ref, tasks, cache_root) -> list[Path]` (`translate.py:422`); `materialize_spider2_harbor_task_view(*, source_task_dir, view_root, task_slug, docker_image=None, view_mode="copy") -> Path` (`harbor_view.py:17`); `tasks_root: Path | None` already passed to `_build_harbor` (`translate.py:74-80`).
- Produces: for a spider2-dbt dataset, `job_config.tasks[i].path` points at a materialized view dir under `tasks_root` (one per resolved source dir, post-`exclude_tasks`/`n_tasks`). For non-spider2 datasets, behavior is unchanged.

**Design note:** Today `tasks_root` is only consumed by the `plugin:` branch (`translate.py:296-301`); the pass-through branch ignores it. We extend the pass-through branch so that *when the family is spider2-dbt and `tasks_root` is set*, each resolved source dir is materialized into `tasks_root`. When `tasks_root` is None (e.g. the existing unit tests that call `spec_to_job_config` without it), raise a `SpecError` for spider2-dbt — the run orchestrator always passes `run_dir / "tasks"` (`cli/run.py:311`), so a None `tasks_root` for spider2-dbt is a programming error, mirroring the plugin branch's guard at `translate.py:291-295`.

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

In `src/razorback/translate.py`, add the import at the top of `_build_harbor` (or module scope):

```python
from razorback.benchmarks.spider2_dbt.harbor_view import (
    materialize_spider2_harbor_task_view,
)
```

Replace the pass-through `else:` block (`translate.py:302-310`) so spider2-dbt materializes:

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
            view_root = Path(tasks_root)
            task_paths = [
                materialize_spider2_harbor_task_view(
                    source_task_dir=src,
                    view_root=view_root,
                    task_slug=src.name,
                )
                for src in source_paths
            ]
        else:
            task_paths = source_paths
        trial_name_map = {}
```

Note: keep the existing `exclude_tasks` / `n_tasks` post-filter (`translate.py:312-317`) below this block unchanged — it now filters on the view dir names. Because `_view_name` derives from `<benchmark_kind>-<task_slug>` (`materialize.py:143-146`), confirm in T3 whether selectors should match source slugs or view names; if a mismatch is found, escalate rather than silently changing selector semantics.

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

## Task 5: Fixture frozen spec + offline source seam for `rk run --explain`

**Files:**
- Create: `tests/fixtures/spider2_dbt/specs/spider2-dbt-fixture.frozen.yaml`

**Interfaces:**
- Consumes: nothing new at runtime — the spec is parsed by `parse_spec_file` (`cli/run.py:202`).
- Produces: a schema-valid frozen `kind: harbor` spider2-dbt spec used by T6.

**Why a seam is needed:** `rk run --explain` calls the *real* `_resolve_harbor_dataset_tasks`, which hits the live registry — blocked per PKG-40. The integration test (T6) must stay offline and deterministic. Decision: the T6 test sets the env var `RAZORBACK_SPIDER2_DBT_SOURCE_ROOT` (read by a small branch in `_resolve_harbor_dataset_tasks`) to point resolution at the local fixture tree. This is the minimal offline seam that keeps the live code path otherwise intact; the env var is unset in production, so the live registry path is the default.

- [ ] **Step 1: Add the offline source-root seam to `_resolve_harbor_dataset_tasks`**

In `src/razorback/translate.py`, at the top of `_resolve_harbor_dataset_tasks` (before the `PackageDatasetClient` import at `436`), add:

```python
    import os

    override_root = os.environ.get("RAZORBACK_SPIDER2_DBT_SOURCE_ROOT")
    if override_root:
        root = Path(override_root)
        dirs = sorted(
            p.parent for p in root.rglob("task.toml")
        )
        if not dirs:
            raise SpecError(
                f"RAZORBACK_SPIDER2_DBT_SOURCE_ROOT={override_root!r} "
                "contains no task.toml dirs"
            )
        if tasks is None:
            return dirs
        by_name = {p.name: p for p in dirs}
        missing = [t for t in tasks if t not in by_name]
        if missing:
            raise SpecError(
                f"source-root override: requested task(s) {missing!r} not found"
            )
        return [by_name[t] for t in tasks]
```

- [ ] **Step 2: Write a failing unit test for the seam**

```python
# tests/unit/test_translate_spider2_dbt.py  (append)
def test_source_root_override_resolves_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("RAZORBACK_SPIDER2_DBT_SOURCE_ROOT", str(FIXTURE_ROOT))
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="spider2-dbt/spider2-dbt@1.0")
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) >= 1
    for task in job_config.tasks:
        assert (task.path / "task.toml").is_file()
```

- [ ] **Step 3: Run test to verify it passes**

Run: `uv run --frozen pytest tests/unit/test_translate_spider2_dbt.py::test_source_root_override_resolves_offline -v`
Expected: PASS — the override returns fixture dirs without touching the network; T2's branch then materializes them.

- [ ] **Step 4: Create the fixture frozen spec**

Write `tests/fixtures/spider2_dbt/specs/spider2-dbt-fixture.frozen.yaml`. Use a NOP agent so `--explain` needs no auth, and the fully-qualified dataset ref so the schema validator accepts it (see "Design decision locked at plan time"):

```yaml
# ABOUTME: Fixture frozen spec — kind:harbor spider2-dbt for rk run --explain (AC-3).
# ABOUTME: Resolution is offline via RAZORBACK_SPIDER2_DBT_SOURCE_ROOT in the test.
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

- [ ] **Step 5: Verify the spec parses (schema validity check)**

Run (import path confirmed at plan time — `parse_spec_file` lives in `src/razorback/spec/parse.py:26`):
```bash
uv run --frozen python -c "from razorback.spec.parse import parse_spec_file; from pathlib import Path; s = parse_spec_file(Path('tests/fixtures/spider2_dbt/specs/spider2-dbt-fixture.frozen.yaml')); print(s.benchmark.dataset)"
```
Expected: prints `spider2-dbt/spider2-dbt@1.0` with no validation error (org==name confirmed to parse at plan time).

- [ ] **Step 6: Commit**

```bash
git add src/razorback/translate.py tests/unit/test_translate_spider2_dbt.py \
        tests/fixtures/spider2_dbt/specs/spider2-dbt-fixture.frozen.yaml
git commit -m "feat(translate): offline source-root seam + fixture frozen spec for spider2-dbt"
```

---

## Task 6: `rk run --explain` lists resolved tasks (AC-3)

**Files:**
- Create: `tests/integration/test_rk_run_spider2_dbt_explain.py`

**Interfaces:**
- Consumes: the fixture frozen spec (T5); the offline seam (T5); `rk run ... --explain` (`cli/run.py:186-197`, `cli/run_explain.py`).
- Produces: proof of AC-3 — exit 0 and one task line per fixture instance.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_rk_run_spider2_dbt_explain.py
# ABOUTME: AC-3 — rk run --explain on a fixture spider2-dbt spec lists resolved tasks.
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "tests" / "fixtures" / "spider2_dbt" / "specs" / "spider2-dbt-fixture.frozen.yaml"
SOURCE_ROOT = REPO / "tests" / "fixtures" / "spider2_dbt" / "harbor_task_minimal"


def test_rk_run_explain_lists_spider2_tasks(tmp_path):
    n_instances = len(list(SOURCE_ROOT.glob("spider2-fixture-*")))
    assert n_instances >= 1
    env = {
        **os.environ,
        "RAZORBACK_SPIDER2_DBT_SOURCE_ROOT": str(SOURCE_ROOT),
    }
    result = subprocess.run(
        [
            sys.executable, "-m", "razorback.cli", "run", str(SPEC),
            "--runs-dir", str(tmp_path / "_runs"),
            "--explain", "--explain-format", "json",
        ],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    import json
    payload = json.loads(result.stdout)
    # AC-3: one task line per fixture instance.
    # task_paths is nested under "prompt" (run_explain.py:254 → _prompt_plan
    # spreads **task_inputs which carries task_paths, run_explain.py:52).
    task_paths = payload["prompt"]["task_paths"]
    assert len(task_paths) == n_instances
```

- [ ] **Step 2: Run test to verify the explain payload shape, then make it pass**

Run: `uv run --frozen pytest tests/integration/test_rk_run_spider2_dbt_explain.py -v`
Confirmed JSON shape (verified at plan time): `_sample_task_prompt_inputs` (`run_explain.py:37-59`) emits `task_paths` / `task_count`; `_prompt_plan` spreads `**task_inputs` (`run_explain.py:113-114`) and the top-level payload nests it under the `prompt` key (`run_explain.py:254`). So extraction is `payload["prompt"]["task_paths"]`.
Expected: PASS — exit 0, `len(task_paths) == n_instances`.

- [ ] **Step 3: Verify the human-facing command from the spec works too**

Run:
```bash
RAZORBACK_SPIDER2_DBT_SOURCE_ROOT=tests/fixtures/spider2_dbt/harbor_task_minimal \
  uv run --frozen python -m razorback.cli run \
  tests/fixtures/spider2_dbt/specs/spider2-dbt-fixture.frozen.yaml --explain
```
Expected: exit 0; markdown output lists one task per fixture instance (this is the spec's literal acceptance command, modulo the offline env var).

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_rk_run_spider2_dbt_explain.py
git commit -m "test(spider2): rk run --explain lists resolved spider2-dbt tasks (AC-3)"
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
- AC-1 → T1 (detect) + T2 (materialize-on-resolve) + T3 (N dirs, leakage-clean). ✓
- AC-2 → T4 (env on view `task.toml`). ✓
- AC-3 → T5 (fixture spec + offline seam) + T6 (`rk run --explain`). ✓
- Test plan's live non-gating smoke + PKG-40 re-check + fallback decision → T7. ✓
- Out of scope (image layer, verifier, raw-dataset generator) → honored; T7 explicitly defers the generator; image/verifier untouched. ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step shows actual code; every command shows expected output. Two deliberate *verify-the-real-shape-then-adjust* steps (T6 Step 2 explain-payload key path; T5 Step 5 `parse_spec_file` import) are framed as "confirm via grep, then adjust" with the exact grep — these are real codebase-confirmation actions, not placeholders.

**3. Type consistency:** `_is_spider2_dbt_dataset(dataset_ref: str) -> bool` defined T1, consumed T2. `materialize_spider2_harbor_task_view(*, source_task_dir, view_root, task_slug, ...)` used T2 matches `harbor_view.py:17`. `_resolve_harbor_dataset_tasks(*, dataset_ref, tasks, cache_root)` monkeypatched consistently across T2–T5 matches `translate.py:422`. `RAZORBACK_SPIDER2_DBT_SOURCE_ROOT` env var defined T5, consumed T5/T6 consistently. `tasks_root` threading matches `spec_to_job_config`→`_build_harbor` (`translate.py:51,74-80`).

**Plan-time verifications (run against the live repo, not assumed):**
- `PackageReference.parse` rejects bare `spider2-dbt@1.0` and accepts `spider2-dbt/spider2-dbt@1.0` (org==name, short_name=="spider2-dbt"). Detection + fixture-spec ref design both rely on this — confirmed.
- The `rk run --explain` JSON payload nests `task_paths` under the `prompt` key (`run_explain.py:254` + `:52`) — T6 extraction confirmed.
- `parse_spec_file` lives at `src/razorback/spec/parse.py:26` — T5 Step 5 command confirmed.

**Open item flagged inline (one) — confirm, don't guess:**
- `exclude_tasks`/`n_tasks` now filter on materialized view-dir names (`<benchmark_kind>-<task_slug>`, `materialize.py:143-146`) rather than raw source slugs. T2 Step 3 flags confirming the intended selector semantics before relying on it; if the spec intends source-slug matching, the post-filter must move *before* materialization — escalate rather than silently changing semantics.
