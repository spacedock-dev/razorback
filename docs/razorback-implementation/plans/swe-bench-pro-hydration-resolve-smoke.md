# swe-bench-pro — hydration + task-view materializer wiring smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire swe-bench-pro in as a recognized `kind: harbor` benchmark family so a `dataset: scale-ai/swe-bench-pro@<ref>` spec resolves source task dirs, routes each through the **generic** `materialize_harbor_task_view` with `benchmark_kind="swe-bench-pro"` + `environment_env={RAZORBACK_BENCHMARK_KIND, RAZORBACK_BENCHMARK_TASK_ID}`, and emits the view dirs as `TaskConfig(path=...)` entries that `rk run --explain --explain-format json` can list.

**Architecture:** The single wiring point is `_build_harbor` in `src/razorback/translate.py` (lives at `translate.py:299-424`; the spider2-dbt branch at `translate.py:361-401` is the template). Today that branch is spider2-only and dispatches to the benchmark-specific `materialize_spider2_harbor_task_view`. swe-bench-pro needs **no** benchmark-specific view transform (design doc "Architecture decision", `2026-06-24-swe-bench-pro-on-harbor-design.md:86-96`): it routes each resolved source dir through the **generic** `materialize_harbor_task_view` (`harbor_tasks/materialize.py:26`) directly — exactly the call the spider2/ade helpers wrap, but with no Dockerfile/preflight/verifier layering. The branch (not the materializer) passes `environment_env`; the materializer merges it into the view's `task.toml` via `_patch_task_toml` (`materialize.py:122-146`) and records `benchmark_kind`/`benchmark_task_id` in `view_manifest.json` (`materialize.py:73-95`). We refactor the existing spider2 branch into a small family-dispatch so both families share the filter-before-materialize / `tasks_root`-guard / `view_mode` scaffolding and differ only in **which materializer call** runs.

**Tech Stack:** Python 3.12, pydantic v2 spec models, Typer CLI (`rk run`), pytest (+ `integration` marker), `uv` for the live smoke. Harbor 0.6.6.

## Global Constraints

- `auto-approve: false` — this task touches the spec/translate surface; changes are reviewed before merge. (entity frontmatter + Problem §)
- The user-facing dataset-ref contract is the fully-qualified `scale-ai/swe-bench-pro@<ref>`. `HarborBenchmarkBlock` rejects a bare ref at parse time when `plugin is None` (`spec/schema.py:197-249`, specifically the `<org>/<name>@<ref>` requirement at `:209-232`). The bare `swe-bench-pro@<ref>` form is the `harbor download` CLI concept only (T7 live smoke), never a spec dataset ref — verified live: `PackageReference.parse("swe-bench-pro@latest")` raises, `PackageReference.parse("scale-ai/swe-bench-pro@latest")` succeeds with `short_name == "swe-bench-pro"`.
- Tests run against a local fixture source tree (`tests/fixtures/swe_bench_pro/`) so the suite stays deterministic and network-free; the live `harbor download scale-ai/swe-bench-pro@<ref>` smoke is **non-gating** (the ACs gate on the fixture). (entity Problem § + Test plan)
- swe-bench-pro uses the materializer's **default** deny-globs (`DEFAULT_SOLUTION_DENY_GLOBS`, `harbor_tasks/leakage.py:7-14`). Swe-specific deny-glob hardening (`*.patch` / `test_patch` / `gold`) is **out of scope** — it is entity E2 (`swe-bench-pro-leakage-audit-deny-globs`). Do NOT extend the deny-glob set here. (entity Out of scope §; design doc `:120-131`)
- The branch passes `environment_env` to the materializer; the materializer **merges** it into `task.toml` (`materialize.py:132-135`). It does NOT synthesize the env — the branch must pass it, exactly as `ade_bench`/`spider2_dbt` helpers do (`ade_bench/harbor_view.py:52-55`, `spider2_dbt/harbor_view.py:84-87`). (entity Problem §; design doc `:46-49`)
- Errors must surface as `SpecError` so `rk run` returns SPEC_ERROR exit code, matching the existing spider2 / plugin branches (`translate.py:331-335`, `:349-353`).
- The v2 spec run-dir contract: the run orchestrator passes `tasks_root=run_dir / "tasks"` and `materialize_mode` into `spec_to_job_config` → `_build_harbor` (`cli/run.py:307-313`); materialized views live under `run_dir/tasks/`. (`2026-05-19-razorback-on-harbor.md` — run-dir / harbor-view surface; mirrors the merged spider2 wiring at `translate.py:369`.)

---

## AC ↔ Task map

| AC | Requirement (verbatim, abbreviated) | Tasks | TDD checkpoint (failing test first) | Governing cites |
| --- | --- | --- | --- | --- |
| AC-1 | A `kind: harbor` / `dataset: scale-ai/swe-bench-pro@<ref>` spec resolves to N materialized task-view dirs via a `_build_harbor` swe-bench-pro branch; each emitted `TaskConfig.path` has `task.toml` + `view_manifest.json` with `benchmark_kind == "swe-bench-pro"`; the swe ref takes the new branch, NOT the generic pass-through. | T1 (family detect `_is_swe_bench_pro_dataset`), T2 (family-dispatch branch + generic-materializer call), T3 (fixture tree), T4 (N views + manifest assertion), T4b (`exclude_tasks` on source slug + NOT-pass-through guard) | T1 Step 1, T2 Step 1, T4 Step 1, T4b Step 1 each write the failing test before code | spec AC-1; design `:86-96`,`:107-118`; `translate.py:_build_harbor` 299-424 (spider2 template 361-401); `materialize.py:materialize_harbor_task_view` 26-96; `materialize.py:_view_name` 149-152 (`swe-bench-pro-<slug>`) |
| AC-2 | Each materialized view's `task.toml` carries `RAZORBACK_BENCHMARK_KIND=swe-bench-pro` and `RAZORBACK_BENCHMARK_TASK_ID` (passed by the branch as `environment_env`, merged by `materialize_harbor_task_view`). | T5 (env assertion on emitted view `task.toml`) | T5 Step 1 writes the failing env assertion | spec AC-2; design `:46-49`; `materialize.py:_patch_task_toml` 122-146; branch `environment_env` (T2) |
| AC-3 | `rk run <fixture-spec>.frozen.yaml --explain --explain-format json` exits 0 and `payload["prompt"]["task_paths"]` has one entry per fixture instance. | T6 (fixture frozen spec), T7 (in-process `CliRunner` `--explain --explain-format json` test, resolver monkeypatched) | T7 Step 1 writes the failing CliRunner test | spec AC-3 + Test plan; `cli/run.py` 307-313; `cli/run_explain.py` `_sample_task_prompt_inputs` 37-58 (`task_paths`) + payload nests under `prompt` `:254`; precedent `tests/integration/test_rk_run_spider2_dbt_explain.py` |
| — | Live `uv run harbor download scale-ai/swe-bench-pro@<ref>` smoke (**non-gating**, bare-org CLI ref): record exit + task-dir count + PKG-40-style `git checkout` blocker status; name fallback decision. | T8 (documented live smoke in validation handoff) | n/a — non-gating, no test | entity Test plan + Problem §; design `:107-118` (#1 risk); `harbor download --help` (confirmed `--export` is the *default*, `--cache` the alternative — see T8) |

**Riskiest-mechanism-first ordering note:** T2 (the family-dispatch `_build_harbor` branch + the **generic** `materialize_harbor_task_view` call with `benchmark_kind="swe-bench-pro"` + `environment_env`) is the load-bearing contract — the smallest end-to-end exercise of "resolved swe source dir → leakage-stripped view under `tasks_root` → manifest with `benchmark_kind` → `TaskConfig`". It is implemented and proven (T4, T4b, T5) **before** the CLI-level `--explain` test (T7) and **before** the non-gating live `harbor download` smoke (T8). Hydration (clone repo at base commit) is the #1 feasibility risk (design `:107-118`) and is known-blocked on the spider2 surface (PKG-40 git-checkout exit-128); it is deliberately the *last*, non-gating step. The in-process monkeypatch seam is the gating path throughout.

---

## File Structure

- `src/razorback/translate.py` — **modify**. (1) Add `_is_swe_bench_pro_dataset(dataset_ref: str) -> bool` next to the existing `_is_spider2_dbt_dataset` (`translate.py:48-66`). (2) Refactor the spider2-only branch in `_build_harbor` (`translate.py:361-401`) into a small family dispatch so swe-bench-pro routes through the **generic** `materialize_harbor_task_view` while spider2-dbt keeps its wrapper. No new module — `materialize_harbor_task_view`, `_resolve_harbor_dataset_tasks`, and `_apply_task_selectors` all already exist. **No env-var seam is added to `_resolve_harbor_dataset_tasks`** (it stays untouched, mirroring the spider2 cycle-1 defect-2 resolution).
- `src/razorback/harbor_tasks/materialize.py` — **read-only** reference. Already exports `materialize_harbor_task_view` (the generic transform). Do not edit.
- `src/razorback/benchmarks/spider2_dbt/harbor_view.py`, `ade_bench/harbor_view.py` — **read-only** reference (the `environment_env` shape to mirror). Do not edit.
- `tests/unit/test_translate_swe_bench_pro.py` — **create**. Unit + integration-level translator coverage for the new branch (family detect, generic-materializer dispatch, manifest `benchmark_kind`, env, `exclude_tasks`/`n_tasks` on source slugs, not-pass-through guard), using the `_resolve_harbor_dataset_tasks` monkeypatch seam.
- `tests/fixtures/swe_bench_pro/harbor_task_minimal/` — **create**. Two swe-bench-pro-shaped Harbor task dirs (`swe-bench-pro-fixture-001`, `swe-bench-pro-fixture-002`), each with `task.toml` + `instruction.md` + an `environment/Dockerfile`, plus a planted gold/test-patch-shaped file under a default-deny path to prove leakage stripping runs. Used network-free via the resolver monkeypatch.
- `tests/fixtures/swe_bench_pro/specs/swe-bench-pro-fixture.frozen.yaml` — **create**. A frozen `kind: harbor` swe-bench-pro spec (fully-qualified `dataset: scale-ai/swe-bench-pro@latest`) for the AC-3 `rk run --explain` command.
- `tests/integration/test_rk_run_swe_bench_pro_explain.py` — **create**. In-process `CliRunner` `rk run --explain --explain-format json` test (AC-3); monkeypatches `_resolve_harbor_dataset_tasks` to return fixture sources — no subprocess, no env seam.
- `docs/razorback-implementation/validation/swe-bench-pro-hydration-resolve-smoke.md` — **created by the validation stage** (T8 names what the live-smoke section must contain; the plan does not pre-write it).

---

## Design decisions locked at plan time

**1. How swe-bench-pro is recognized for routing through the materializer.** Mirror the spider2 family-signal pattern (`translate.py:51-66`): parse `block.dataset` with `harbor.models.package.reference.PackageReference.parse` and treat `parsed.short_name == "swe-bench-pro"` as the family signal. Verified live at plan time: `PackageReference.parse("scale-ai/swe-bench-pro@latest")` → `short_name == "swe-bench-pro"`, `org == "scale-ai"`, `ref == "latest"`; `PackageReference.parse("swe-bench-pro@latest")` raises (bare form is not a valid spec ref), so `_is_swe_bench_pro_dataset` returns False on it (it catches the exception). This avoids a new spec field (YAGNI) and keeps `kind: harbor` generic.

**2. swe-bench-pro uses the GENERIC materializer — no benchmark-specific wrapper.** Per the design doc Architecture decision (`:86-96`): "no benchmark-specific view logic needed, unlike spider2's dbt wrapper." So the swe branch calls `materialize_harbor_task_view` (`materialize.py:26`) **directly** — NOT a `materialize_swe_bench_pro_harbor_task_view` wrapper (none exists; do not create one — the entity Out of scope § says the generic materializer "is sufficient unless a probe proves otherwise"). The branch supplies the params the spider2/ade wrappers would otherwise hardcode:
  - `benchmark_kind="swe-bench-pro"`
  - `benchmark_task_id=src.name` (the Harbor source slug)
  - `transform_name="swe-bench-pro-harbor-task-view"` (string label recorded in the manifest; matches the `<benchmark>-harbor-task-view` convention at `spider2_dbt/harbor_view.py:82`, `ade_bench/harbor_view.py:50`)
  - `environment_env={"RAZORBACK_BENCHMARK_KIND": "swe-bench-pro", "RAZORBACK_BENCHMARK_TASK_ID": src.name}`
  - `exclude_globs=DEFAULT_SOLUTION_DENY_GLOBS` (the materializer's default — explicit pass is optional but kept implicit by omitting the arg; do not pass a hardened set, that is E2)
  - `view_mode` mapped from `materialize_mode` (`bind`→`"link"`, else `"copy"`), exactly as the spider2 branch maps it (`translate.py:376-378`)

**3. Refactor shape — family dispatch, not a second copy-pasted branch.** The current branch (`translate.py:361-401`) is `if is_spider2_dbt:` with an early `return`. Generalize to detect **either** family up front, then share the filter-before-materialize + `tasks_root` guard + `view_mode` map, differing only in the materializer call. Concrete structure in T2. The generic (non-spider2, non-swe) pass-through path (`translate.py:403-424`) stays **byte-for-byte unchanged** — proven by the unchanged `tests/unit/test_translate_harbor_block.py` suite.

**4. Selector ordering — filter source paths BEFORE materialization (locked, inherited from spider2 defect-3).** `materialize.py:_view_name` (149-152) yields `swe-bench-pro-<slug>`, so a post-materialization `p.name` filter (the generic-harbor pattern at `translate.py:406-411`) would silently never match a Harbor source slug. The swe branch applies `_apply_task_selectors` (`translate.py:69-81`) to the resolved **source paths** first, then materializes survivors. T4b proves `exclude_tasks=[source_slug]` drops exactly that task.

**5. No production env seam (locked, inherited from spider2 defect-2).** The AC-3 test runs `rk run --explain` **in-process** via Typer's `CliRunner` (precedent: `tests/integration/test_rk_run_spider2_dbt_explain.py`) and `monkeypatch.setattr("razorback.translate._resolve_harbor_dataset_tasks", ...)`. `_resolve_harbor_dataset_tasks` is left entirely untouched — no `RAZORBACK_*_SOURCE_ROOT` branch. Confirmed at plan time: `--explain` short-circuits before `_invoke_harbor` (the spider2 explain test proves this end-to-end on the same path), and a fixture spec with no `provenance:` block skips model/harbor-drift pre-checks.

**6. Deterministic test seam.** The existing harbor-block tests monkeypatch `razorback.translate._resolve_harbor_dataset_tasks` to return fixed source dirs (`tests/unit/test_translate_harbor_block.py:106-107`, `:129-130`). T4/T4b/T5 reuse exactly that seam; T7 reuses it through `CliRunner`.

---

## Task 1: Detect the swe-bench-pro family inside `translate.py`

**Files:**
- Modify: `src/razorback/translate.py` (add helper next to `_is_spider2_dbt_dataset` at `:48-66`)
- Test: `tests/unit/test_translate_swe_bench_pro.py` (create)

**Interfaces:**
- Consumes: `harbor.models.package.reference.PackageReference.parse` (already used at `spec/schema.py:213` and `translate.py:60`).
- Produces: a module-level helper `_is_swe_bench_pro_dataset(dataset_ref: str) -> bool` in `translate.py`, consumed by T2.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_translate_swe_bench_pro.py
# ABOUTME: AC-1/AC-2 — swe-bench-pro kind:harbor wiring through the generic materializer.
# ABOUTME: Fixture-backed, network-free via the _resolve_harbor_dataset_tasks monkeypatch seam.
from razorback.translate import _is_swe_bench_pro_dataset


def test_detects_swe_bench_pro_fully_qualified():
    # Spec datasets with plugin=None must be fully qualified <org>/<name>@<ref>
    # (spec/schema.py:209-232). PackageReference.parse rejects the bare short
    # form, so only the qualified form is a valid spec dataset.
    assert _is_swe_bench_pro_dataset("scale-ai/swe-bench-pro@latest") is True


def test_rejects_non_swe_dataset():
    assert _is_swe_bench_pro_dataset("adyen/dabstep@latest") is False
    assert _is_swe_bench_pro_dataset("spider2-dbt/spider2-dbt@1.0") is False


def test_rejects_unparseable_bare_form():
    # The bare `swe-bench-pro@latest` form is the `harbor download` CLI concept,
    # NOT a valid spec dataset ref — PackageReference.parse raises on it, and
    # the helper swallows the error and returns False. Verified at plan time.
    assert _is_swe_bench_pro_dataset("swe-bench-pro@latest") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/unit/test_translate_swe_bench_pro.py -k "swe_bench_pro or non_swe or bare_form" -v`
Expected: FAIL — `ImportError: cannot import name '_is_swe_bench_pro_dataset'`

- [ ] **Step 3: Write minimal implementation**

In `src/razorback/translate.py`, directly after `SPIDER2_DBT_SHORT_NAME` / `_is_spider2_dbt_dataset` (`:48-66`), add:

```python
SWE_BENCH_PRO_SHORT_NAME = "swe-bench-pro"


def _is_swe_bench_pro_dataset(dataset_ref: str) -> bool:
    """True when a `kind: harbor` dataset ref names the swe-bench-pro family.

    Mirrors the spider2-dbt / ade-bench dataset-ref flow: the dataset ref is
    the family signal. The fully-qualified `<org>/swe-bench-pro@<ref>` form
    (e.g. `scale-ai/swe-bench-pro@latest`) resolves to
    short_name == "swe-bench-pro"; the bare `swe-bench-pro@<ref>` form is the
    `harbor download` CLI concept (not a valid spec dataset) and raises on
    parse, so the helper swallows the error and returns False.
    """
    from harbor.models.package.reference import PackageReference

    try:
        parsed = PackageReference.parse(dataset_ref)
    except Exception:
        return False
    return parsed.short_name == SWE_BENCH_PRO_SHORT_NAME
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/unit/test_translate_swe_bench_pro.py -k "swe_bench_pro or non_swe or bare_form" -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_translate_swe_bench_pro.py src/razorback/translate.py
git commit -m "feat(translate): detect swe-bench-pro dataset family by short name"
```

---

## Task 2: Route swe-bench-pro through the generic materializer in `_build_harbor`

**Files:**
- Modify: `src/razorback/translate.py` (`_build_harbor`, the spider2 branch + dispatch at `:361-401`; add the generic-materializer import at module scope)
- Test: `tests/unit/test_translate_swe_bench_pro.py` (extend)

**Interfaces:**
- Consumes: `_is_swe_bench_pro_dataset` (T1); `_is_spider2_dbt_dataset` (`translate.py:51`); `_resolve_harbor_dataset_tasks(*, dataset_ref, tasks, cache_root) -> list[Path]` (`translate.py:516`); `_apply_task_selectors(paths, *, exclude_tasks, n_tasks) -> list[Path]` (`translate.py:69`); `materialize_harbor_task_view(*, source_task_dir, view_root, benchmark_kind, benchmark_task_id, transform_name, docker_image=None, environment_env=None, ..., view_mode="copy") -> Path` (`materialize.py:26-41`); `tasks_root: Path | None` + `materialize_mode` already passed into `_build_harbor` (`translate.py:306-307`).
- Produces: for a swe-bench-pro dataset, `job_config.tasks[i].path` points at a materialized view dir under `tasks_root` named `swe-bench-pro-<slug>`, one per surviving source dir; the view carries a `view_manifest.json` with `benchmark_kind == "swe-bench-pro"`. For non-swe, non-spider2 datasets, behavior is unchanged.

**Design note (the refactor):** Today `_build_harbor`'s `else:` (non-plugin) branch (`translate.py:342-404`) computes `is_spider2_dbt`, guards `tasks_root`, resolves source paths, and if spider2 runs filter→materialize→early-return; otherwise falls through to the generic pass-through. Generalize the family detection so swe-bench-pro shares the scaffolding:

1. Detect both families before the network resolve (the `tasks_root` guard is a cheap ref-parse, mirroring the existing spider2 fast-fail at `translate.py:343-353`).
2. After resolving `source_paths`, if **either** family matched, apply `_apply_task_selectors` to the source paths, map `view_mode`, then materialize survivors with the **family-appropriate** call, and early-return. spider2 keeps `materialize_spider2_harbor_task_view`; swe-bench-pro calls the generic `materialize_harbor_task_view` with the explicit `benchmark_kind`/`benchmark_task_id`/`transform_name`/`environment_env`.
3. The generic non-family pass-through (`translate.py:403-424`) is untouched.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_translate_swe_bench_pro.py  (append)
import json
from pathlib import Path

import pytest

from razorback.spec.schema import HarborBenchmarkBlock, NopAgentBlock, Spec
from razorback.translate import spec_to_job_config

FIXTURE_ROOT = (
    Path(__file__).parent.parent
    / "fixtures" / "swe_bench_pro" / "harbor_task_minimal"
)


def _spec(benchmark):
    return Spec(
        version=1,
        experiment="swe-bench-pro-translator-smoke",
        agent=NopAgentBlock(kind="nop"),
        benchmark=benchmark,
        trials=1,
        observers=[],
    )


def test_swe_dataset_materializes_views_with_manifest(tmp_path, monkeypatch):
    source = FIXTURE_ROOT / "swe-bench-pro-fixture-001"

    def fake_resolver(*, dataset_ref, tasks, cache_root):
        return [source]

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks", fake_resolver
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="scale-ai/swe-bench-pro@latest")
    )
    job_config, trial_name_map = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) == 1
    view_dir = job_config.tasks[0].path
    # emitted path is a materialized VIEW under tasks_root, not the raw source
    assert (tmp_path / "tasks") in view_dir.parents
    assert (view_dir / "task.toml").is_file()
    # the view took the materializer branch, NOT the generic pass-through:
    # only the materializer writes view_manifest.json with benchmark_kind.
    manifest = json.loads((view_dir / "view_manifest.json").read_text())
    assert manifest["benchmark_kind"] == "swe-bench-pro"
    assert trial_name_map == {}


def test_swe_dataset_requires_tasks_root(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: [FIXTURE_ROOT / "swe-bench-pro-fixture-001"],
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="scale-ai/swe-bench-pro@latest")
    )
    with pytest.raises(Exception) as exc:
        spec_to_job_config(spec, job_name="job", jobs_dir=tmp_path, tasks_root=None)
    assert "tasks_root" in str(exc.value).lower()
```

(This test will fail at collection if T3's fixture does not yet exist; implement T3's fixture before running T2 Step 2, OR run T2 Step 2 expecting the failure to be the assertion/branch behavior once the fixture is present. The recommended order is: do T3 Step 1 (create the fixture) first, then return here. The plan keeps T2 before T3 for code-locality of the branch logic; the implementer may create the fixture dir from T3 Step 1 first if running tests inline.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest tests/unit/test_translate_swe_bench_pro.py -k "materializes_views_with_manifest or requires_tasks_root" -v`
Expected: FAIL — `test_swe_dataset_materializes_views_with_manifest` asserts the emitted path is a view under `tasks_root` with a `view_manifest.json`, but the unchanged generic pass-through emits the raw source dir (no manifest); `test_swe_dataset_requires_tasks_root` does not raise.

- [ ] **Step 3: Write minimal implementation**

In `src/razorback/translate.py`, add the generic-materializer import at module scope (next to the spider2 import at `:17-19`):

```python
from razorback.harbor_tasks.materialize import materialize_harbor_task_view
```

Then refactor the `else:` (non-plugin) branch in `_build_harbor`. Replace the spider2 fast-fail block + the `if is_spider2_dbt:` branch (`translate.py:343-401`) with a family-dispatch that handles both. The replacement:

```python
    else:
        # Detect benchmark families up front. `_is_*` are cheap ref-parses;
        # a family dataset with `tasks_root is None` is mis-wired regardless of
        # resolution, so fail fast BEFORE the (network) resolve, mirroring the
        # plugin branch's guard.
        is_spider2_dbt = _is_spider2_dbt_dataset(block.dataset)
        is_swe_bench_pro = _is_swe_bench_pro_dataset(block.dataset)
        is_view_family = is_spider2_dbt or is_swe_bench_pro
        if is_view_family and tasks_root is None:
            family = "spider2-dbt" if is_spider2_dbt else "swe-bench-pro"
            raise SpecError(
                f"`kind: harbor` {family} dataset requires tasks_root "
                "(the run orchestrator passes it)."
            )
        home_dir = Path(home) if home is not None else Path.home()
        cache_root = home_dir / ".cache" / "razorback" / "harbor" / "datasets"
        source_paths = _resolve_harbor_dataset_tasks(
            dataset_ref=block.dataset,
            tasks=block.tasks,
            cache_root=cache_root,
        )
        if is_view_family:
            # Filter on SOURCE slugs BEFORE materialization so selectors bind
            # to Harbor task names, not the `<benchmark>-<slug>` view names.
            selected_sources = _apply_task_selectors(
                source_paths,
                exclude_tasks=block.exclude_tasks,
                n_tasks=block.n_tasks,
            )
            view_root = Path(tasks_root)
            # Map the spec-level materialize mode onto the view-materializer's
            # vocabulary: `bind` -> symlink the (large) task trees in place,
            # `copy` -> eagerly duplicate. Mirrors how ade-bench/spider2 thread
            # the mode (cli/run.py:313, translate.py:376-378).
            view_mode: Literal["copy", "link"] = (
                "link" if materialize_mode == "bind" else "copy"
            )
            if is_spider2_dbt:
                task_paths = [
                    materialize_spider2_harbor_task_view(
                        source_task_dir=src,
                        view_root=view_root,
                        task_slug=src.name,
                        view_mode=view_mode,
                    )
                    for src in selected_sources
                ]
            else:
                # swe-bench-pro uses the GENERIC materializer directly — no
                # benchmark-specific view transform (design doc Architecture
                # decision). The BRANCH passes environment_env; the materializer
                # MERGES it into the view's task.toml and records benchmark_kind
                # in view_manifest.json. Default deny-globs only (swe-specific
                # hardening is entity E2, out of scope here).
                task_paths = [
                    materialize_harbor_task_view(
                        source_task_dir=src,
                        view_root=view_root,
                        benchmark_kind="swe-bench-pro",
                        benchmark_task_id=src.name,
                        transform_name="swe-bench-pro-harbor-task-view",
                        environment_env={
                            "RAZORBACK_BENCHMARK_KIND": "swe-bench-pro",
                            "RAZORBACK_BENCHMARK_TASK_ID": src.name,
                        },
                        view_mode=view_mode,
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

The family branch returns early (selectors already applied to source paths). The plugin branch and the generic non-family pass-through fall through to the existing shared selector block (`translate.py:406-411`) and `JobConfig` construction (`:413-424`) **unchanged** — non-family behavior is byte-for-byte identical.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest tests/unit/test_translate_swe_bench_pro.py -k "materializes_views_with_manifest or requires_tasks_root" -v`
Expected: PASS (2 passed) — requires T3's fixture to exist.

- [ ] **Step 5: Run the spider2 + generic translator suites to confirm no regression**

Run: `uv run --frozen pytest tests/unit/test_translate_harbor_block.py tests/unit/test_translate_spider2_dbt.py -q`
Expected: PASS — the generic pass-through (non-family) and the spider2 branch are unchanged by the refactor. (If `test_translate_harbor_block` has a pre-existing dabstep network-only failure, confirm it fails identically on the base commit before this change; it is not a regression.)

- [ ] **Step 6: Commit**

```bash
git add tests/unit/test_translate_swe_bench_pro.py src/razorback/translate.py
git commit -m "feat(translate): materialize swe-bench-pro views via generic materializer in kind:harbor"
```

---

## Task 3: Minimal swe-bench-pro fixture source tree

**Files:**
- Create: `tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/` and `…/swe-bench-pro-fixture-002/`

**Interfaces:**
- Consumes: nothing at runtime — these are static fixture dirs returned by the monkeypatched resolver.
- Produces: two swe-bench-pro-shaped Harbor task dirs, each with `task.toml` (valid `HarborTaskConfig`), `instruction.md`, `environment/Dockerfile`, and a planted gold-patch-shaped file under a default-deny path so the materializer's leakage stripping is exercised.

**Why two instances:** AC-3's "one entry per fixture instance" and AC-1's "N materialized task-view dirs" need N>1; T4b's `exclude_tasks` needs a second task to keep after dropping one.

**Why the planted deny-path file:** to prove the generic materializer's default leakage stripping actually runs on swe-shaped trees (a `solution/` dir is covered by `DEFAULT_SOLUTION_DENY_GLOBS` `"solution/**"`, `leakage.py:8`). Note: swe-specific `*.patch`/`test_patch`/`gold` globs are NOT in the default set — hardening those is E2, out of scope. So plant a file that the DEFAULT set already denies (e.g. `solution/gold_patch.diff`), proving the mechanism without pre-empting E2.

- [ ] **Step 1: Create fixture instance 001**

```bash
mkdir -p tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/environment
mkdir -p tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/solution
```

Write `tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/task.toml`:

```toml
schema_version = "1.2"

[task]
name = "scale-ai/swe-bench-pro-fixture-001"
description = "Synthetic swe-bench-pro Harbor-shaped task fixture (repo + base commit)."

[environment]
docker_image = "swe-bench-pro-source:latest"
os = "linux"
cpus = 2
memory_mb = 4096
```

Write `tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/instruction.md`:

```markdown
Fix the failing tests in the checked-out repository at the given base commit.
```

Write `tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/environment/Dockerfile`:

```dockerfile
FROM python:3.12
```

Write `tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/solution/gold_patch.diff` (planted under a DEFAULT-deny path `solution/**`, so the materialized view must NOT contain it):

```diff
--- a/app/buggy.py
+++ b/app/buggy.py
@@ -1 +1 @@
-return None
+return 42
```

- [ ] **Step 2: Create fixture instance 002 by copy + rename**

```bash
cp -R tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001 \
      tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-002
```

Then edit `…/swe-bench-pro-fixture-002/task.toml` so the `[task] name` field reads `name = "scale-ai/swe-bench-pro-fixture-002"` (rename `001` → `002` in the `name` field only; leave everything else).

- [ ] **Step 3: Sanity-check both task.toml files validate as Harbor task configs**

Run:
```bash
uv run --frozen python -c "
from pathlib import Path
from harbor.models.task.config import TaskConfig
root = Path('tests/fixtures/swe_bench_pro/harbor_task_minimal')
for d in sorted(root.glob('swe-bench-pro-fixture-*')):
    cfg = TaskConfig.model_validate_toml((d / 'task.toml').read_text())
    print(d.name, '->', cfg.task.name)
"
```
Expected: prints both fixture names with no validation error.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/swe_bench_pro/harbor_task_minimal
git commit -m "test(swe-bench-pro): minimal harbor task fixture tree (two instances + planted deny-path file)"
```

---

## Task 4: Integration test — N task-view dirs, each with a swe-bench-pro manifest, leakage-clean (AC-1)

**Files:**
- Test: `tests/unit/test_translate_swe_bench_pro.py` (extend)

**Interfaces:**
- Consumes: the `_build_harbor` swe branch (T2); the two fixture instances (T3).
- Produces: proof of AC-1 — N emitted dirs, each with `task.toml` + `view_manifest.json` (`benchmark_kind == "swe-bench-pro"`), and the planted `solution/gold_patch.diff` excluded.

- [ ] **Step 1: Write the failing/guarding test**

```python
# tests/unit/test_translate_swe_bench_pro.py  (append)
def test_swe_resolves_n_views_with_manifest_leakage_clean(tmp_path, monkeypatch):
    sources = sorted(FIXTURE_ROOT.glob("swe-bench-pro-fixture-*"))
    assert len(sources) >= 2, "need >1 fixture instance to prove N task-view dirs"

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="scale-ai/swe-bench-pro@latest")
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) == len(sources)
    for task in job_config.tasks:
        view = task.path
        assert view.name.startswith("swe-bench-pro-")
        assert (view / "task.toml").is_file()
        manifest = json.loads((view / "view_manifest.json").read_text())
        assert manifest["benchmark_kind"] == "swe-bench-pro"
        assert manifest["benchmark_task_id"].startswith("swe-bench-pro-fixture-")
        # leakage-clean: the planted DEFAULT-deny file did not survive.
        assert not (view / "solution" / "gold_patch.diff").exists()
        assert not (view / "solution").exists()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run --frozen pytest tests/unit/test_translate_swe_bench_pro.py::test_swe_resolves_n_views_with_manifest_leakage_clean -v`
Expected: PASS — T2's branch materializes each source through `materialize_harbor_task_view`, which strips `solution/**` (`leakage.py:8` + `_reflect_allowed_files` `materialize.py:99-119`) and writes the manifest (`materialize.py:73-95`). If the `solution/` assertion FAILS, confirm `DEFAULT_SOLUTION_DENY_GLOBS` still contains `"solution/**"`.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_translate_swe_bench_pro.py
git commit -m "test(swe-bench-pro): N leakage-clean task-view dirs with benchmark_kind manifest (AC-1)"
```

---

## Task 4b: `exclude_tasks` binds to the source slug + NOT-the-pass-through guard (AC-1)

**Files:**
- Test: `tests/unit/test_translate_swe_bench_pro.py` (extend)

**Interfaces:**
- Consumes: the `_build_harbor` swe branch with filter-before-materialize (T2); the two fixture instances (T3).
- Produces: proof that (a) selectors bind to the Harbor source slug, not the `swe-bench-pro-<slug>` view name; (b) the swe ref takes the new branch, NOT the generic pass-through (AC-1's explicit "NOT the generic pass-through" clause).

- [ ] **Step 1: Write the failing/guarding test**

```python
# tests/unit/test_translate_swe_bench_pro.py  (append)
def test_exclude_tasks_drops_swe_source_slug(tmp_path, monkeypatch):
    sources = sorted(FIXTURE_ROOT.glob("swe-bench-pro-fixture-*"))
    assert len(sources) >= 2
    excluded_slug = sources[0].name  # SOURCE slug, e.g. "swe-bench-pro-fixture-001"

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )
    spec = _spec(
        HarborBenchmarkBlock(
            kind="harbor",
            dataset="scale-ai/swe-bench-pro@latest",
            exclude_tasks=[excluded_slug],
        )
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) == len(sources) - 1
    view_names = {t.path.name for t in job_config.tasks}
    # filter ran on the SOURCE slug, so neither the source slug nor its
    # `swe-bench-pro-<slug>` view appears in the emitted set
    assert excluded_slug not in view_names
    assert f"swe-bench-pro-{excluded_slug}" not in view_names
    # a surviving task IS the `swe-bench-pro-<slug>` view form
    kept_slug = sources[1].name
    assert f"swe-bench-pro-{kept_slug}" in view_names


def test_swe_ref_takes_materializer_branch_not_passthrough(tmp_path, monkeypatch):
    # AC-1: the swe ref must take the materializer branch. The generic
    # pass-through emits the RAW source dir (no manifest, name == source slug);
    # the materializer branch emits a `swe-bench-pro-<slug>` view WITH a
    # manifest. Assert the latter to prove the branch — not the pass-through.
    source = FIXTURE_ROOT / "swe-bench-pro-fixture-001"
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: [source],
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="scale-ai/swe-bench-pro@latest")
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    view = job_config.tasks[0].path
    assert view != source                       # NOT the raw source dir
    assert view.name == "swe-bench-pro-swe-bench-pro-fixture-001"
    assert (view / "view_manifest.json").is_file()  # only the materializer writes this
```

- [ ] **Step 2: Run test**

Run: `uv run --frozen pytest tests/unit/test_translate_swe_bench_pro.py -k "exclude_tasks_drops_swe or takes_materializer_branch" -v`
Expected: PASS (2 passed). `test_exclude_tasks_drops_swe_source_slug` is the regression pin for filter-before-materialize: if a refactor moves the selector filter after materialization, `excluded_slug` matches no view name, the excluded task survives, `len(job_config.tasks) == len(sources)` (not `-1`), and the test FAILS.

- [ ] **Step 3: (optional) Prove `n_tasks` also slices source-side**

```python
# tests/unit/test_translate_swe_bench_pro.py  (append)
def test_n_tasks_caps_swe_before_materialize(tmp_path, monkeypatch):
    sources = sorted(FIXTURE_ROOT.glob("swe-bench-pro-fixture-*"))
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )
    spec = _spec(
        HarborBenchmarkBlock(
            kind="harbor", dataset="scale-ai/swe-bench-pro@latest", n_tasks=1
        )
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) == 1
```

Run: `uv run --frozen pytest tests/unit/test_translate_swe_bench_pro.py -k "exclude_tasks_drops_swe or n_tasks_caps_swe" -v`
Expected: PASS (2 passed).

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_translate_swe_bench_pro.py
git commit -m "test(swe-bench-pro): exclude_tasks binds to source slug; ref takes materializer branch (AC-1)"
```

---

## Task 5: Each view carries the swe-bench-pro benchmark env (AC-2)

**Files:**
- Test: `tests/unit/test_translate_swe_bench_pro.py` (extend)

**Interfaces:**
- Consumes: the materialized view `task.toml` from T2; `harbor.models.task.config.TaskConfig.model_validate_toml` (the same parser the materializer uses at `materialize.py:129`).
- Produces: proof of AC-2 — the emitted view's `task.toml` carries both env keys (passed by the BRANCH as `environment_env`, MERGED by `materialize_harbor_task_view` via `_patch_task_toml`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_translate_swe_bench_pro.py  (append)
from harbor.models.task.config import TaskConfig as HarborTaskConfig


def test_materialized_view_carries_benchmark_env(tmp_path, monkeypatch):
    source = FIXTURE_ROOT / "swe-bench-pro-fixture-001"
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: [source],
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="scale-ai/swe-bench-pro@latest")
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    view_toml = job_config.tasks[0].path / "task.toml"
    cfg = HarborTaskConfig.model_validate_toml(view_toml.read_text())
    # env passed by the _build_harbor swe branch, MERGED into task.toml by
    # materialize_harbor_task_view (_patch_task_toml) — the materializer does
    # NOT synthesize these; the branch supplies them.
    assert cfg.environment.env["RAZORBACK_BENCHMARK_KIND"] == "swe-bench-pro"
    assert cfg.environment.env["RAZORBACK_BENCHMARK_TASK_ID"] == "swe-bench-pro-fixture-001"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run --frozen pytest tests/unit/test_translate_swe_bench_pro.py::test_materialized_view_carries_benchmark_env -v`
Expected: PASS — T2's branch passes `environment_env`; `_patch_task_toml` (`materialize.py:132-135`) merges it into the view `task.toml`; `benchmark_task_id=src.name` gives `RAZORBACK_BENCHMARK_TASK_ID == "swe-bench-pro-fixture-001"`.

(This passes immediately because T2 wires the env; it exists to *prove* AC-2 explicitly and to guard against a future refactor dropping `environment_env`.)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_translate_swe_bench_pro.py
git commit -m "test(swe-bench-pro): assert materialized view carries benchmark env (AC-2)"
```

---

## Task 6: Fixture frozen spec for `rk run --explain`

**Files:**
- Create: `tests/fixtures/swe_bench_pro/specs/swe-bench-pro-fixture.frozen.yaml`

**Interfaces:**
- Consumes: nothing new at runtime — the spec is parsed by `parse_spec_file` (`src/razorback/spec/parse.py`).
- Produces: a schema-valid frozen `kind: harbor` swe-bench-pro spec used by T7.

- [ ] **Step 1: Create the fixture frozen spec**

Write `tests/fixtures/swe_bench_pro/specs/swe-bench-pro-fixture.frozen.yaml`. Use a NOP agent so `--explain` needs no auth, and the fully-qualified dataset ref so the schema validator accepts it (mirrors `tests/fixtures/spider2_dbt/specs/spider2-dbt-fixture.frozen.yaml`):

```yaml
# ABOUTME: Fixture frozen spec — kind:harbor swe-bench-pro for rk run --explain (AC-3).
# ABOUTME: T7 resolves it offline by monkeypatching _resolve_harbor_dataset_tasks in-process.
version: 1
experiment: swe-bench-pro-fixture
agent:
  kind: nop
benchmark:
  kind: harbor
  dataset: scale-ai/swe-bench-pro@latest
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

Run:
```bash
uv run --frozen python -c "from razorback.spec.parse import parse_spec_file; from pathlib import Path; s = parse_spec_file(Path('tests/fixtures/swe_bench_pro/specs/swe-bench-pro-fixture.frozen.yaml')); print(s.benchmark.dataset)"
```
Expected: prints `scale-ai/swe-bench-pro@latest` with no validation error. A bare `dataset: swe-bench-pro@latest` here would instead raise the schema validator's "required shape is `<org>/<name>@<ref>`" error (`spec/schema.py:221-226`) — confirming the contract.

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/swe_bench_pro/specs/swe-bench-pro-fixture.frozen.yaml
git commit -m "test(swe-bench-pro): fixture frozen kind:harbor spec for rk run --explain (AC-3)"
```

---

## Task 7: `rk run --explain --explain-format json` lists resolved task views (AC-3) — in-process, no env seam

**Files:**
- Create: `tests/integration/test_rk_run_swe_bench_pro_explain.py`

**Interfaces:**
- Consumes: the fixture frozen spec (T6); `rk run ... --explain --explain-format json` via Typer `CliRunner` (`razorback.cli.app`); `razorback.translate._resolve_harbor_dataset_tasks` (monkeypatched).
- Produces: proof of AC-3 — exit 0 and `payload["prompt"]["task_paths"]` has one entry per fixture instance, each a `swe-bench-pro-<slug>` view.

**Why in-process + JSON (locked):** Running `rk run --explain` in-process via `CliRunner` lets a `monkeypatch.setattr("razorback.translate._resolve_harbor_dataset_tasks", ...)` reach the resolver, so the test is offline with zero production-code seam (mirrors `tests/integration/test_rk_run_spider2_dbt_explain.py`). The JSON format is the load-bearing surface: the default text `--explain` prints only a task count + one sample task (`cli/run_explain.py:281-309`), so the per-task list lives only in the JSON payload. `task_paths` nests under `prompt` (`run_explain.py:254` builds `"prompt": _prompt_plan(...)`, and `_prompt_plan` spreads `**_sample_task_prompt_inputs` which carries `task_paths` at `run_explain.py:52`).

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_rk_run_swe_bench_pro_explain.py
# ABOUTME: AC-3 — rk run --explain --explain-format json lists resolved swe-bench-pro task views.
# ABOUTME: In-process via CliRunner; resolver is monkeypatched (offline, no env seam).
import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "tests" / "fixtures" / "swe_bench_pro" / "specs" / "swe-bench-pro-fixture.frozen.yaml"
SOURCE_ROOT = REPO / "tests" / "fixtures" / "swe_bench_pro" / "harbor_task_minimal"


def test_rk_run_explain_lists_swe_task_views(tmp_path, monkeypatch):
    sources = sorted(SOURCE_ROOT.glob("swe-bench-pro-fixture-*"))
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
    # AC-3: one task entry per fixture instance, nested under "prompt".
    task_paths = payload["prompt"]["task_paths"]
    assert len(task_paths) == n_instances
    # emitted paths are materialized swe-bench-pro views, not raw source dirs
    assert all(Path(p).name.startswith("swe-bench-pro-") for p in task_paths)
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run --frozen pytest tests/integration/test_rk_run_swe_bench_pro_explain.py -v`
Expected: PASS — exit 0, `len(task_paths) == n_instances`, every path is a `swe-bench-pro-<slug>` view (proving materialization ran through the CLI path end-to-end). If `result.exit_code != 0`, print `result.stdout`/`result.stderr`; a `provenance`-related failure would mean the fixture spec accidentally carries a `provenance:` block (it must not).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_rk_run_swe_bench_pro_explain.py
git commit -m "test(swe-bench-pro): rk run --explain --explain-format json lists resolved views in-process (AC-3)"
```

---

## Task 8: Live smoke (non-gating) + hydration / fallback decision

**Files:**
- The live-smoke result + fallback decision are recorded by the **validation stage** in `docs/razorback-implementation/validation/swe-bench-pro-hydration-resolve-smoke.md`. This task documents exactly what that section must capture; it adds no gating test and no code commit.

**Interfaces:**
- Consumes: nothing in the harness — this exercises the live registry path the fixture seam deliberately bypasses.
- Produces: a recorded exit status + task-dir count, a re-check of the PKG-40-style `git checkout` blocker, and a named decision on the fallback.

- [ ] **Step 1: Confirm the CLI flag shape, then run the live smoke**

First confirm flags (do NOT assume): `uv run --frozen harbor download --help`. Confirmed at plan time (harbor 0.6.6): the positional `NAME` accepts `org/name@ref`; `--output-dir/-o PATH`; `--export` is the **default** mode (`<output-dir>/<dataset-name>/<task-name>/`); `--cache` is the alternative content-addressable mode; `--overwrite` overwrites existing tasks. There is no separate required `--export` value — it is a default flag, so passing it is valid but redundant.

Run:
```bash
uv run --frozen harbor download scale-ai/swe-bench-pro@<ref> \
  --output-dir runs/swe-bench-pro-wiring-smoke/download --overwrite
echo "exit=$?"
find runs/swe-bench-pro-wiring-smoke/download -maxdepth 3 -name task.toml | wc -l
```
Record the exact `<ref>` used (see Open Decision below), the exit status, and the `task.toml` count verbatim in the validation report.

- [ ] **Step 2: Re-check the PKG-40-style blocker and name the fallback decision**

swe-bench-pro is git-repo-based (clone repo at a base commit), so the spider2-dbt `git checkout exit-128` blocker (PKG-40, `docs/razorback-implementation/_archive/spider2-dbt-source-resolution-and-run-wiring.md:154`) is the #1 feasibility risk (design `:107-118`).

- **If the live download SUCCEEDS** (task-dir count > 0): note the blocker has cleared on this surface; the fixture-backed tests remain the gating path. Name (do not build) a future integration-marked test that resolves `scale-ai/swe-bench-pro@<ref>` live as out-of-scope follow-up.
- **If the live download STILL FAILS** (git-checkout/hydration blocker persists): record the exit status + stderr verbatim. Then name the fallback decision explicitly — per the entity Out of scope §, a benchmark-specific view transform / local generator is deferred unless a probe proves otherwise. The decision to surface to the captain is **defer vs. build a hydration workaround**; recommend **defer** (the fixture-backed tests already gate AC-1/AC-2/AC-3; hydration is a separate concern feeding the deferred full-dataset goal entity). Do **not** build a workaround inside this task.

- [ ] **Step 3: No code commit for this task**

The validation report lives on the validation stage, not the implementation worktree. The implementation worktree is complete after T7. This task is a checklist the validation worker executes.

---

## Self-Review

**1. Spec coverage:**
- AC-1 → T1 (detect) + T2 (family-dispatch generic-materializer branch) + T3 (fixture tree) + T4 (N views + `benchmark_kind` manifest + leakage-clean) + T4b (`exclude_tasks` on source slug + NOT-pass-through guard). ✓
- AC-2 → T5 (env keys on view `task.toml`, branch-passed + materializer-merged). ✓
- AC-3 → T6 (fixture spec) + T7 (in-process `CliRunner` `rk run --explain --explain-format json`, `payload["prompt"]["task_paths"]`). ✓
- Test plan's non-gating live `harbor download` smoke + PKG-40 re-check + fallback decision → T8. ✓
- Out of scope (swe deny-glob hardening = E2; example spec + strata = E3; full-dataset score = deferred goal; benchmark-specific view transform) → honored: T2/T3 use DEFAULT deny-globs only and the GENERIC materializer (no wrapper); T8 explicitly defers any hydration workaround. ✓

**2. Riskiest-contract-first ordering (per dispatch requirement 2):** T2 (the new `_build_harbor` swe branch + `materialize_harbor_task_view` wiring with `environment_env` + `benchmark_kind="swe-bench-pro"`) is implemented and proven (T4/T4b/T5) BEFORE the CLI explain test (T7) and BEFORE the non-gating live `harbor download` smoke (T8). ✓

**3. Precision points from the dispatch (hard-won in adversarial review):**
- Env vars passed BY THE BRANCH as `environment_env`, MERGED by the materializer — stated in Global Constraints, design decision 2, T2 Step 3 comment, T5 Step 1 comment. Never "the materializer synthesizes them." ✓
- Explain assertion is `payload["prompt"]["task_paths"]` (nested) — T7 Step 1 + the "Why in-process + JSON" note cite `run_explain.py:254` + `:52`. ✓
- Only spider2 has a `_build_harbor` branch today; ade uses the same materializer via its own helper; this plan ADDS the swe branch in `_build_harbor` — stated in Architecture, design decision 3, T2 design note. ✓

**4. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step shows actual code; every command shows expected output. The single deliberate cross-task note (T2 Step 1 fixture-ordering caveat) names the concrete resolution (create T3's fixture first), not a placeholder.

**5. Type consistency:** `_is_swe_bench_pro_dataset(dataset_ref: str) -> bool` defined T1, consumed T2. `materialize_harbor_task_view(*, source_task_dir, view_root, benchmark_kind, benchmark_task_id, transform_name, environment_env=..., view_mode=...)` used in T2 matches `materialize.py:26-41` exactly. `_apply_task_selectors(paths, *, exclude_tasks, n_tasks)` (existing, `translate.py:69`) and `_resolve_harbor_dataset_tasks(*, dataset_ref, tasks, cache_root)` (existing, `translate.py:516`) monkeypatched consistently across T2/T4/T4b/T5/T7. `view_mode: Literal["copy","link"]` map (`bind`→`link`) matches the spider2 branch (`translate.py:376-378`). Fixture path `tests/fixtures/swe_bench_pro/harbor_task_minimal/` consistent across T2/T3/T4/T4b/T5/T7.

**Plan-time verifications (run live against the repo this cycle, not assumed):**
- `PackageReference.parse("scale-ai/swe-bench-pro@latest")` → `short_name=="swe-bench-pro"`, `org=="scale-ai"`, `ref=="latest"`; `PackageReference.parse("swe-bench-pro@latest")` raises (ValidationError). Detection + fixture-spec ref design rely on this. ✓ (ran live)
- `harbor download --help` (harbor 0.6.6): positional `org/name@ref`; `--output-dir/-o`, `--overwrite`; `--export` is the DEFAULT mode, `--cache` the alternative. The dispatch's "do not assume `--export`" caution is resolved: `--export` exists and is the default; T8 omits it (redundant) and uses `--output-dir` + `--overwrite`. ✓ (ran live)
- `materialize_harbor_task_view` signature (`materialize.py:26-41`): `benchmark_kind`, `benchmark_task_id`, `transform_name` are required keyword args; `environment_env` optional; `exclude_globs` defaults to `DEFAULT_SOLUTION_DENY_GLOBS`; `view_mode` defaults to `"copy"`. T2's call passes the required four + `environment_env` + `view_mode`, omits `exclude_globs` (default). ✓ (read)
- `_build_harbor` today: spider2-only branch with early return at `translate.py:361-401`; generic pass-through at `:403-424`; `materialize_mode` already threaded in at `:307`/`:376`. The refactor generalizes the family check without touching the pass-through. ✓ (read)
- `_prompt_plan` returns `{**_sample_task_prompt_inputs(...), ...}` carrying `task_paths` (`run_explain.py:52`); `explain_run` nests it under `"prompt"` (`run_explain.py:254`). Extraction `payload["prompt"]["task_paths"]` confirmed. ✓ (read)
- `DEFAULT_SOLUTION_DENY_GLOBS` (`leakage.py:7-14`) contains `"solution/**"` — the planted `solution/gold_patch.diff` is stripped without adding swe-specific globs (E2). ✓ (read)
- Precedent `tests/integration/test_rk_run_spider2_dbt_explain.py` uses exactly the `CliRunner` + resolver-monkeypatch shape T7 reuses. ✓ (read)

**Open decision for the captain (flag in Stage Report):**
- **The exact `@<ref>` to pin** for `scale-ai/swe-bench-pro` in the live smoke (T8) and ultimately the example spec (E3). The fixture spec (T6) uses `@latest` as a placeholder — schema-valid and sufficient for the offline AC-3 gate (the resolver is monkeypatched, so the ref is never resolved). But the live smoke (T8) and the user-facing example spec (E3) need a real, reproducible ref. Recommend the captain pin a concrete published ref (or confirm `@latest` is acceptable for the smoke) before validation runs T8.
- **Fixture realism:** the minimal fixture (T3) is a `task.toml` + `instruction.md` + `environment/Dockerfile` + a planted `solution/` deny-path file — it does NOT carry a real git-repo checkout / gold patch / test patch / FAIL_TO_PASS, since those drive E2 (leakage hardening) and the hydration concern (T8/deferred goal), both out of scope here. This is sufficient to gate AC-1/AC-2/AC-3 (which only require `task.toml` + manifest + env + view listing). Flag for captain awareness in case a more repo-shaped fixture is wanted before E2.
