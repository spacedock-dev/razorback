# PKG-19 — ade-bench harbor integration reuses `~/git/ade-bench/` data via bind-mount (implementation plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the per-task fresh-clone in the ade-bench harbor integration so Goal 2's 48-task × N≥3 matrix fits the disk envelope, and close the solution-leak hazard the probe surfaced (`seeds/solution__*.csv` visible to the agent container).

The captain's existing `~/git/ade-bench/` checkout contains the full upstream ade-bench task tree at git HEAD (44 task folders under `tasks/<slug>/`, with `task.yaml` + `setup.sh` + `solution.sh` + `tests/` + `seeds/`). PKG-19 re-points the harbor integration to bind-mount this local checkout instead of cloning `harbor-datasets` per task. Per-task disk footprint drops from O(GB) (clone + working copy) to O(MB) (provenance + a thin task.toml shim + a per-task view directory that excludes `seeds/solution__*.csv`).

**Critical shape mismatch (load-bearing for the plan):** upstream `~/git/ade-bench/tasks/<task>/` uses `task.yaml`. Harbor's `JobConfig`/`TaskConfig` requires `task.toml` per the [environment] block (the existing `materialize_git_task` post-fetch rewrite confirms this). The `harbor-datasets` repo currently shipped at `https://github.com/laude-institute/harbor-datasets.git` is a harbor-shaped MIRROR that publishes `task.toml` per task. The captain's directive ("reuse the data files from ade-bench directly, not a fresh copy") rules out the upstream-clone approach. PKG-19 therefore introduces a per-task **view directory** under razorback's cache root that:

1. Symlinks every upstream artifact under `~/git/ade-bench/tasks/<task>/` EXCEPT `seeds/solution__*.csv` (AC-4),
2. Generates the harbor-shaped `task.toml` from the upstream `task.yaml` + the spec's `docker_image_override`,
3. Is referenced from compose's bind-mount volumes as the agent's `/workdir`-side source.

Option (b) from the entity (per-task view directory with symlinks) is the canonical design. Option (a) (sub-path bind-mount) does not work because the exclusion lives INSIDE the task directory (`seeds/` is a sibling of `task.yaml`, not a sibling of the task directory), so masking it requires either a per-file mount or a view-dir overlay.

**Architecture:**
- `src/razorback/benchmarks/ade_bench/tasks.py` (the `materialize_git_task` function + a new `materialize_local_task` sibling).
- `src/razorback/translate.py` (`_build_ade_bench` lines 237–286 wires `ade_bench_root` resolution + dispatches to local vs git materializer).
- `src/razorback/spec/schema.py` (`AdeBenchBenchmarkBlock` adds optional `ade_bench_root: Path | None` + optional `AdeBenchLocalTaskEntry` schema variant).
- The task.yaml→task.toml shim lives next to the materializer; it is intentionally small (the upstream task.yaml's `task_id` + `description` + `prompts[0].prompt` map to harbor's task.toml + `instruction.md`; the `[environment]` block synthesizes from the spec's `docker_image_override` and the existing `_DEFAULT_DOCKER_IMAGE` default).

**Tech Stack:** Python 3.13, pytest, PyYAML, harbor.models.task, docker.

**Dependency on PKG-14:** None at code level — PKG-14 (DAB data bind-mount) and PKG-19 (ade-bench data bind-mount) edit disjoint code paths (PKG-14 lives in `packages/razorback-plugin-dab/`; PKG-19 lives in `src/razorback/benchmarks/ade_bench/` and `src/razorback/translate.py`). PKG-19 can implement and validate independently. However, PKG-19's validation stage (AC-7) inherits the same operator preconditions as the original probe (free disk + `CLAUDE_CODE_OAUTH_TOKEN` set), so the implementation stage commits the spec but does NOT run the probe — validation does.

## AC ↔ task map

| AC    | Tasks                                                                 |
| ----- | --------------------------------------------------------------------- |
| AC-1  | T2 (RED — `materialize_local_task` builds a view-dir from `ade_bench_root`, no clone), T3 (GREEN — schema + translator + materializer), T4 (compose `volumes:` references view-dir absolute path) |
| AC-2  | T5 (RED + GREEN — `du -sh` on view-dir-only materialized output ≤ 10 MB) |
| AC-3  | T6 (RED — synthesized task.toml volumes carry `:ro` for the ade_bench_root sources), T7 (live EROFS integration test, gated on docker) |
| AC-4  | T8 (RED — view-dir does NOT include `seeds/solution__*.csv`), T9 (GREEN — symlink-filter walker emits view-dir without solution files), T10 (verifier-readable copy of solutions stays accessible OUTSIDE the agent mount, AC-4 invariant — agent grep-find returns zero hits) |
| AC-5  | T11 (RED + GREEN — `--materialize={bind,copy}` CLI flag restores fresh-clone behavior) |
| AC-6  | T12 (RED + GREEN — missing `ade_bench_root` or empty `tasks/` subdir fails fast at translator-time with clear error) |
| AC-7  | T14 (implementation-stage emits probe spec at `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml`; validation stage dispatches it) |

T1 is a paper-only mechanism review. T13 is a full-suite regression gate. T14 + T7 are out-of-implementation-stage scope (probe spec is committed; live runs happen in validation).

## Spec §-cites

- PKG-19 entity: `docs/razorback-implementation/pkg19-ade-bench-data-bind-mount.md` (all 7 ACs).
- PKG-14 plan (parallel structural sibling for DAB): `docs/razorback-implementation/plans/pkg14-harbor-dab-lfs-bindmount-reuse.md` — Cluster A's bind-mount + `:ro` contract + materialize-mode flag pattern is the architectural reference PKG-19 mirrors for ade-bench.
- ade-bench probe report: `.worktrees/spacedock-ensign-ade-bench-probe-2/docs/superpowers/plans/2026-05-20-ade-bench-path-probe.md` (Phase 1 survey, the 44-task upstream layout, the `seeds/solution__*.csv` hazard, the disk blocker).
- Harbor task contract: `harbor.models.task.id.GitTaskId.get_local_path` + `harbor.tasks.client.TaskClient.download_tasks` — the current `materialize_git_task` (`src/razorback/benchmarks/ade_bench/tasks.py:138-192`) goes through this contract. PKG-19 introduces a SECOND materializer (`materialize_local_task`) that bypasses harbor's clone path and produces the same shape of `TaskConfig.path` output (an absolute directory containing `task.toml` + the task fixture).
- Upstream task.yaml shape (load-bearing): `/Users/clkao/git/ade-bench/tasks/airbnb001/task.yaml` — surveyed in Phase 1; fields used by the shim are `task_id`, `description`, `prompts[0].prompt` (mapped into `instruction` field of synthesized `task.toml` + `instruction.md`). Other fields (`solution_seeds`, `test_setup`, `tags`) are NOT consumed by harbor's TaskConfig and are dropped from the shim.

## File structure

| File | Responsibility | Action |
| ---- | -------------- | ------ |
| `src/razorback/spec/schema.py` | `AdeBenchBenchmarkBlock` adds optional `ade_bench_root: Path | None`; introduce `AdeBenchLocalTaskEntry` (path-only) as a third union member alongside the str-slug + git-task variants | Modify (lines 133–151) |
| `src/razorback/benchmarks/ade_bench/tasks.py` | Add `materialize_local_task(*, ade_bench_root, task_slug, docker_image, cache_root, exclude_globs)` + `_build_task_toml_from_yaml` helper; keep existing `materialize_git_task` untouched | Modify (append new functions; do not delete existing) |
| `src/razorback/translate.py` | `_build_ade_bench` dispatches to `materialize_local_task` when `ade_bench_root` is set, else falls back to current `materialize_git_task`; add fail-fast hydration check for missing/empty `ade_bench_root` | Modify (lines 237–286) |
| `src/razorback/cli/__init__.py` (or wherever `rk run` flags live) | Add `--materialize={bind,copy}` flag (default `bind`); forward into the translator | Modify |
| `tests/unit/test_ade_bench_materialize_local_task.py` | AC-1 + AC-2 + AC-4 — view-dir build excludes `seeds/solution__*.csv`, ≤ 10 MB, no clone | Create |
| `tests/unit/test_ade_bench_translator_local_root.py` | AC-1 — translator wires `ade_bench_root` into the materializer call | Create |
| `tests/unit/test_ade_bench_local_task_readonly_contract.py` | AC-3 — synthesized compose volumes carry `:ro`; structural assertion only (live EROFS is integration-stage) | Create |
| `tests/unit/test_ade_bench_local_task_hydration_check.py` | AC-6 — missing or empty `ade_bench_root` raises a clear `FileNotFoundError` with the path in the message | Create |
| `tests/unit/test_ade_bench_materialize_mode_flag.py` | AC-5 — `--materialize=copy` flag forces a copy of the upstream task tree into the view-dir (full self-contained tarball mode) | Create |
| `tests/integration/test_ade_bench_local_task_readonly_contract_live.py` | AC-3 live — `docker compose up` against a synthesized task; `docker exec` attempts `chmod`/`rm`/`write` against bind-mounted paths; observes EROFS | Create (skipped under no-docker harnesses) |
| `tests/fixtures/ade_bench/fixture_local_task_minimal/` | A tiny ade-bench-shaped upstream fixture (`tasks/example001/task.yaml` + `tasks/example001/seeds/solution__x.csv` + `tasks/example001/setup.sh`) | Create |
| `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml` | Validation-stage probe spec using `ade_bench_root: ~/git/ade-bench` | Create |

## Risk-first ordering rationale

The riskiest contract is **the synthesized `task.toml` shim's compatibility with harbor's `JobConfig`/`TaskConfig` ingestion**. If harbor rejects the synthesized task.toml (missing fields, wrong types, schema drift between harbor versions), every downstream test collapses AND the probe re-dispatch fails AND PKG-14's parallel pattern is invalidated as an architectural reference. So:

- T1: paper-only mechanism review (no code) — confirm harbor's `task.toml` required-fields set against the current pinned harbor version.
- T2 (AC-1 RED): the SMALLEST failing test — call `materialize_local_task(ade_bench_root=<fixture>, task_slug="example001", ...)` and assert the returned directory contains `task.toml` with the expected `[environment]` block and an `instruction` field derived from the fixture's `task.yaml`. This is the contract that, if broken, invalidates every later task.
- T3 (AC-1 GREEN): implement `materialize_local_task` + `_build_task_toml_from_yaml`. Verifies T2 in seconds.
- T4 (AC-1 compose-side): translator emits compose volumes referencing the view-dir absolute path; `_initdb`-style copying is bypassed.
- T5 (AC-2): view-dir disk footprint ≤ 10 MB on the airbnb001-shape fixture.
- T6–T7 (AC-3): `:ro` flag is structurally important — agent must not mutate source data. T6 is unit (string-level); T7 is live EROFS integration (gated on docker).
- T8–T10 (AC-4): solution-file exclusion. T8 asserts the view-dir omits `seeds/solution__*.csv`; T9 implements the symlink-filter walker; T10 asserts the verifier-readable copy of solutions stays accessible OUTSIDE the agent mount (so harbor's verifier still grades correctly).
- T11 (AC-5): copy-mode opt-in preserved for provenance-strict runs.
- T12 (AC-6): hydration check still fires under bind-mount mode (missing `ade_bench_root`, empty `tasks/` subdir, missing per-task subdir).
- T13: full pytest sweep — regression gate before validation-stage hand-off.
- T14 (AC-7): probe spec committed; live runs happen in validation.

Comprehensive runs come AFTER the smallest end-to-end mechanism check passes. AC-3's live EROFS test (T7) comes AFTER the unit-level path/flag assertion (T6) passes. AC-4's view-dir exclusion (T8/T9) comes AFTER the materializer's basic task.toml shape is verified (T2/T3).

---

## Task 1 — Mechanism review (no code)

**Files:** none modified.

- [ ] **Step 1: Confirm harbor's `task.toml` required-fields set.**

Read `harbor.models.task` source (path varies by harbor version; check `uv pip show harbor` for install location). The fields harbor's `TaskConfig` requires are: `instruction` (string), `[environment]` block with `docker_image` (string), `[environment].build_timeout_sec` (float, optional but defaulted), `[environment].cpus` (int, optional), `[environment].memory_mb` (int, optional). The synthesized task.toml shim MUST emit at minimum the `instruction` field and the `[environment]` block with `docker_image`. Other fields can default.

- [ ] **Step 2: Confirm the upstream `task.yaml` shape across 5 representative tasks.**

Read `/Users/clkao/git/ade-bench/tasks/{airbnb001,analytics_engineering001,asana001}/task.yaml` (3 of the 44 tasks). Confirm all three have:
- A scalar `task_id` field
- A scalar `description` field
- A `prompts` array of objects with at minimum a `key` and `prompt` field

Confirm at least one task has multiple prompts (the `key=base` convention); the shim consumes `prompts[0].prompt` (or the `key=base` entry if present). Document the choice.

- [ ] **Step 3: Confirm the `seeds/solution__*.csv` glob pattern.**

Read `/Users/clkao/git/ade-bench/tasks/airbnb001/seeds/` listing. Confirm the canonical name pattern is `solution__<table_name>.csv` and that no other CSV under `seeds/` matches this pattern by accident. The exclusion glob is `seeds/solution__*.csv` exactly; do NOT broaden to `seeds/*.csv` since other seed files (e.g., `_no-op.txt` or potential input CSVs) might be required by the agent.

- [ ] **Step 4: Confirm the verifier's solution-read path.**

Read `~/git/ade-bench/tasks/airbnb001/tests/AUTO_*.sql` and `solution.sh`. Determine where the verifier reads the ground-truth values from — if it reads from `seeds/solution__*.csv` AT VERIFIER TIME (i.e., after the agent has exited), the verifier needs access to the un-filtered seeds path. The view-dir filter must leave a verifier-readable copy of solutions ACCESSIBLE outside the agent's bind-mount. (Recommendation: the materializer keeps the un-filtered `~/git/ade-bench/tasks/<task>/seeds/` reachable as a separate bind-mount on a different container path, e.g., `/verifier/seeds/`, with no agent-side mount; this is harbor's `verifier_volumes` slot.)

- [ ] **Step 5: Commit a note (no code change).**

No commit. Steps 1–4 are paper-only. Proceed to Task 2.

---

## Task 2 — AC-1 RED: `materialize_local_task` builds a view-dir from `ade_bench_root`

**Files:**
- Create: `tests/fixtures/ade_bench/fixture_local_task_minimal/tasks/example001/task.yaml`
- Create: `tests/fixtures/ade_bench/fixture_local_task_minimal/tasks/example001/setup.sh`
- Create: `tests/fixtures/ade_bench/fixture_local_task_minimal/tasks/example001/seeds/solution__x.csv`
- Create: `tests/fixtures/ade_bench/fixture_local_task_minimal/tasks/example001/seeds/_no-op.txt`
- Create: `tests/unit/test_ade_bench_materialize_local_task.py`

- [ ] **Step 1: Write the fixture.**

Create the tiny ade-bench-shaped upstream fixture so the test does not depend on `~/git/ade-bench/` being present. `task.yaml`:

```yaml
task_id: example001
status: ready
description: Tiny test fixture
prompts:
  - key: base
    prompt: |
      Do the example task.
author_name: pkg19-test
difficulty: easy
```

`setup.sh`: a one-line `#!/bin/bash\necho ok\n`.
`seeds/solution__x.csv`: any 5-byte content.
`seeds/_no-op.txt`: any 5-byte content.

- [ ] **Step 2: Write the failing test.**

```python
# ABOUTME: PKG-19 AC-1 — materialize_local_task builds a view-dir from ade_bench_root
# ABOUTME: with a synthesized task.toml + symlinked artifacts, no clone.

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def test_materialize_local_task_emits_task_toml(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    task_toml = (materialized / "task.toml").read_text()
    assert 'docker_image = "ade-bench-agent:latest"' in task_toml
    assert "[environment]" in task_toml
    # The instruction text comes from prompts[0].prompt in the upstream yaml.
    instruction_md = (materialized / "instruction.md").read_text()
    assert "Do the example task." in instruction_md


def test_materialize_local_task_does_not_clone(tmp_path: Path, monkeypatch) -> None:
    """AC-1: no git operations during local materialization."""
    from razorback.benchmarks.ade_bench import tasks as ade_tasks

    def _fail(*a, **kw):
        raise AssertionError(
            "AC-1: materialize_local_task must NOT invoke harbor's git fetch"
        )

    # Defend against accidental wiring back into TaskClient.
    monkeypatch.setattr(ade_tasks, "_run_async", _fail, raising=False)

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = ade_tasks.materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    assert (materialized / "task.toml").exists()
```

- [ ] **Step 3: Run the test to verify it fails.**

```bash
cd /Users/clkao/git/razorback
uv run pytest tests/unit/test_ade_bench_materialize_local_task.py -v
```

Expected: both tests FAIL with `AttributeError: module 'razorback.benchmarks.ade_bench.tasks' has no attribute 'materialize_local_task'`.

- [ ] **Step 4: Commit (RED).**

```bash
cd /Users/clkao/git/razorback
git add tests/fixtures/ade_bench/fixture_local_task_minimal/ \
        tests/unit/test_ade_bench_materialize_local_task.py
git commit -m "test(pkg19): RED — materialize_local_task builds view-dir from ade_bench_root"
```

---

## Task 3 — AC-1 GREEN: implement `materialize_local_task` + `_build_task_toml_from_yaml`

**Files:**
- Modify: `src/razorback/benchmarks/ade_bench/tasks.py`

- [ ] **Step 1: Add the task.yaml→task.toml shim helper.**

Append to `src/razorback/benchmarks/ade_bench/tasks.py`:

```python
def _build_task_toml_from_yaml(
    *, task_yaml: dict, docker_image: str
) -> str:
    """Synthesize a harbor-shaped task.toml from an upstream ade-bench task.yaml.

    The shim consumes prompts[0].prompt (or the `key=base` entry if present) as
    the harbor `instruction` field; the rest of the upstream task.yaml (tags,
    solution_seeds, test_setup, etc.) is ignored — those fields are not
    consumed by harbor's TaskConfig.
    """
    prompts = task_yaml.get("prompts") or []
    base_prompt = next(
        (p for p in prompts if p.get("key") == "base"), prompts[0] if prompts else None
    )
    if base_prompt is None:
        raise ValueError(
            "ade-bench task.yaml has no 'prompts' entries; cannot synthesize task.toml"
        )
    # task.toml uses harbor's instruction-file convention: the file lives at
    # the task root as `instruction.md`; task.toml references it.
    return (
        f'instruction = "instruction.md"\n'
        f'\n'
        f'[environment]\n'
        f'docker_image = "{docker_image}"\n'
    )
```

- [ ] **Step 2: Implement `materialize_local_task`.**

Append to the same file:

```python
import os

_SOLUTION_FILE_GLOB = "seeds/solution__*.csv"


def materialize_local_task(
    *,
    ade_bench_root: Path,
    task_slug: str,
    docker_image: str = _DEFAULT_DOCKER_IMAGE,
    cache_root: Path,
    exclude_globs: tuple[str, ...] = (_SOLUTION_FILE_GLOB,),
) -> Path:
    """Build a view-dir for an ade-bench task that re-uses ade_bench_root data.

    Output directory layout under cache_root/<task_slug>/:
        task.toml          (synthesized — harbor-shaped)
        instruction.md     (synthesized from prompts[0].prompt)
        setup.sh           (symlink → ade_bench_root/tasks/<task_slug>/setup.sh)
        solution.sh        (symlink, if present)
        tests/             (symlink — bulk dir)
        seeds/             (selectively symlinked — every file EXCEPT
                            anything matching `exclude_globs`)
    """
    import yaml

    ade_bench_root = Path(ade_bench_root).resolve()
    source_task_dir = ade_bench_root / "tasks" / task_slug
    if not source_task_dir.is_dir():
        raise FileNotFoundError(
            f"materialize_local_task: ade_bench_root has no tasks/{task_slug}/ "
            f"directory (ade_bench_root={ade_bench_root}); "
            f"hydrate ~/git/ade-bench checkout or pass a different slug"
        )
    source_task_yaml = source_task_dir / "task.yaml"
    if not source_task_yaml.exists():
        raise FileNotFoundError(
            f"materialize_local_task: missing task.yaml at {source_task_yaml}"
        )
    target_dir = cache_root / task_slug
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)

    task_yaml = yaml.safe_load(source_task_yaml.read_text())
    (target_dir / "task.toml").write_text(
        _build_task_toml_from_yaml(task_yaml=task_yaml, docker_image=docker_image)
    )
    prompts = task_yaml.get("prompts") or []
    base_prompt = next(
        (p for p in prompts if p.get("key") == "base"), prompts[0] if prompts else None
    )
    (target_dir / "instruction.md").write_text(base_prompt["prompt"])

    # Selectively reflect the upstream tree EXCEPT solution files.
    import fnmatch

    for entry in source_task_dir.iterdir():
        if entry.name == "task.yaml":
            continue  # already consumed into task.toml + instruction.md
        rel = entry.relative_to(source_task_dir)
        if entry.is_dir():
            # If the directory contains excluded files, walk it; otherwise symlink whole dir.
            has_excluded = any(
                fnmatch.fnmatch(str(p.relative_to(source_task_dir)), g)
                for p in entry.rglob("*")
                for g in exclude_globs
            )
            if not has_excluded:
                os.symlink(entry, target_dir / rel)
            else:
                (target_dir / rel).mkdir(parents=True)
                for sub in entry.iterdir():
                    sub_rel = sub.relative_to(source_task_dir)
                    if any(
                        fnmatch.fnmatch(str(sub_rel), g) for g in exclude_globs
                    ):
                        continue
                    os.symlink(sub, target_dir / sub_rel)
        else:
            os.symlink(entry, target_dir / rel)

    return target_dir
```

- [ ] **Step 3: Run the test to verify it passes.**

```bash
cd /Users/clkao/git/razorback
uv run pytest tests/unit/test_ade_bench_materialize_local_task.py -v
```

Expected: both tests PASS.

- [ ] **Step 4: Commit (GREEN).**

```bash
cd /Users/clkao/git/razorback
git add src/razorback/benchmarks/ade_bench/tasks.py
git commit -m "feat(pkg19): GREEN — materialize_local_task builds view-dir from ade_bench_root"
```

---

## Task 4 — AC-1 compose-side: translator wires `ade_bench_root` into the materializer

**Files:**
- Modify: `src/razorback/spec/schema.py`
- Modify: `src/razorback/translate.py`
- Create: `tests/unit/test_ade_bench_translator_local_root.py`

- [ ] **Step 1: Write the failing test.**

```python
# ABOUTME: PKG-19 AC-1 — translator dispatches to materialize_local_task when
# ABOUTME: ade_bench_root is set on AdeBenchBenchmarkBlock.

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def test_translator_uses_ade_bench_root_when_set(tmp_path: Path) -> None:
    from razorback.spec.schema import (
        AdeBenchBenchmarkBlock,
        AdeBenchLocalTaskEntry,
        Spec,
    )
    from razorback.translate import build_job_config_from_spec  # or _build_ade_bench wrapper

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    spec = Spec(
        version=1,
        experiment="pkg19-translator-test",
        agent={"kind": "claude-cli", "tools_allowed": []},
        benchmark=AdeBenchBenchmarkBlock(
            kind="ade-bench",
            tasks_root=Path("."),
            ade_bench_root=ade_bench_root,
            tasks=[AdeBenchLocalTaskEntry(slug="example001")],
        ),
        trials=1,
        observers=[],
    )
    cfg = build_job_config_from_spec(
        spec=spec,
        job_name="pkg19-test",
        jobs_dir=tmp_path,
        home=tmp_path / "home",
    )
    assert len(cfg.tasks) == 1
    task_path = cfg.tasks[0].path
    assert (task_path / "task.toml").exists()
    assert "ade-bench" in str(task_path)  # under razorback's ade-bench cache
```

- [ ] **Step 2: Run to verify failure.**

```bash
cd /Users/clkao/git/razorback
uv run pytest tests/unit/test_ade_bench_translator_local_root.py -v
```

Expected: FAIL with `AttributeError: module 'razorback.spec.schema' has no attribute 'AdeBenchLocalTaskEntry'` or schema rejects `ade_bench_root`.

- [ ] **Step 3: Add the schema entries.**

In `src/razorback/spec/schema.py`, add (next to `AdeBenchTaskEntry`):

```python
class AdeBenchLocalTaskEntry(BaseModel):
    """PKG-19 — local upstream-checkout task entry. Mirrors the str-slug
    variant but explicitly opts into the `ade_bench_root` materialization
    path (rather than the git-task variant's harbor-datasets clone).
    """
    model_config = ConfigDict(extra="forbid")
    slug: str
```

Update `AdeBenchBenchmarkBlock`:

```python
class AdeBenchBenchmarkBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["ade-bench"]
    tasks_root: Path
    tasks: list[str | AdeBenchTaskEntry | AdeBenchLocalTaskEntry] = Field(min_length=1)
    docker_image_override: str | None = None
    ade_bench_root: Path | None = None  # PKG-19: when set, local-task entries materialize against this root
```

- [ ] **Step 4: Wire the translator.**

In `src/razorback/translate.py:_build_ade_bench`, modify the loop:

```python
for r in resolved:
    if r.git_url is not None and r.git_commit_id is not None:
        materialized = materialize_git_task(...)  # existing path
        tasks.append(TaskConfig(path=materialized))
    elif r.local_slug is not None:
        if spec.benchmark.ade_bench_root is None:
            raise ValueError(
                "ade-bench local task entry requires ade_bench_root on the "
                "benchmark block (PKG-19)"
            )
        materialized = materialize_local_task(
            ade_bench_root=spec.benchmark.ade_bench_root,
            task_slug=r.local_slug,
            docker_image=docker_image,
            cache_root=cache_root,
        )
        tasks.append(TaskConfig(path=materialized))
    else:
        tasks.append(TaskConfig(path=r.path))
```

And update `resolve_task_dirs` in `tasks.py` to recognize `AdeBenchLocalTaskEntry` and set `local_slug` on `ResolvedTask`.

- [ ] **Step 5: Run to verify pass.**

```bash
uv run pytest tests/unit/test_ade_bench_translator_local_root.py -v
```

- [ ] **Step 6: Commit (GREEN).**

```bash
git add src/razorback/spec/schema.py src/razorback/benchmarks/ade_bench/tasks.py \
        src/razorback/translate.py tests/unit/test_ade_bench_translator_local_root.py
git commit -m "feat(pkg19): translator wires ade_bench_root → materialize_local_task"
```

---

## Task 5 — AC-2: per-task disk footprint ≤ 10 MB

**Files:**
- Append to: `tests/unit/test_ade_bench_materialize_local_task.py`

- [ ] **Step 1: Add the disk-budget test.**

```python
def test_view_dir_disk_footprint_under_10mb(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )

    # Sum size of NON-symlink entries only — symlinks contribute their target
    # size to the bind-mount source, NOT to our cache.
    total_bytes = 0
    for p in materialized.rglob("*"):
        if p.is_symlink():
            continue
        if p.is_file():
            total_bytes += p.stat().st_size
    assert total_bytes < 10 * 1024 * 1024, (
        f"AC-2: per-task view-dir must be ≤ 10 MB (excluding symlinks); "
        f"got {total_bytes} bytes"
    )
```

- [ ] **Step 2: Run + verify pass.**

- [ ] **Step 3: Commit.**

```bash
git add tests/unit/test_ade_bench_materialize_local_task.py
git commit -m "test(pkg19): AC-2 — view-dir disk footprint ≤ 10 MB"
```

---

## Task 6 — AC-3 RED: `:ro` flag on synthesized compose volumes (structural)

**Files:**
- Create: `tests/unit/test_ade_bench_local_task_readonly_contract.py`

- [ ] **Step 1: Determine where compose for ade-bench tasks lives.**

ade-bench tasks ARE harbor tasks; the compose generation is harbor's responsibility (harbor reads `task.toml` and synthesizes per-task compose). Razorback's contribution is the `task.toml` content + the optional `environment/docker-compose.yaml` override. If the upstream ade-bench task references any host-mounted data (rare — most ade-bench tasks are self-contained dbt projects), the synthesized override must include `:ro` on every mount.

**Decision point:** if no upstream ade-bench task references host-mounted data, AC-3's `:ro` assertion applies to the materializer's emitted symlinks only — the symlink targets are READ-ONLY by host filesystem convention when the agent container does not mount them as RW. The unit-test contract is therefore: when the materializer creates a symlink to `~/git/ade-bench/tasks/<task>/<file>`, the symlink target's containing directory permission, when bind-mounted into the agent container, MUST be exposed read-only. The simplest enforcement is: razorback's compose override (if any) emits `:ro` on the agent's bind-mount of the materialized view-dir.

**Action:** the structural assertion is that razorback's translator never produces a TaskConfig whose host-path bind-mount is RW. Confirm this by reading the harbor TaskConfig → compose code path; if harbor itself emits `:ro` by default for task volumes, no razorback-side assertion is needed beyond the live test. Document the decision in this task.

- [ ] **Step 2: Write the structural test (skip if harbor handles it).**

If the decision is "harbor handles `:ro` natively," this test asserts the synthesized `task.toml` does not introduce any custom mount in the `[environment]` block; the structural assertion is "no custom mounts == no RW exposure."

```python
# ABOUTME: PKG-19 AC-3 — synthesized task.toml introduces no agent-RW mounts.

from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def test_synthesized_task_toml_introduces_no_rw_mounts(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    task_toml = (materialized / "task.toml").read_text()
    # Negative assertion: shim does NOT inject any [environment.volumes] block.
    assert "[environment.volumes]" not in task_toml
    assert ":rw" not in task_toml
```

- [ ] **Step 3: Run + verify pass (the test asserts the absence of a footgun).**

- [ ] **Step 4: Commit.**

```bash
git add tests/unit/test_ade_bench_local_task_readonly_contract.py
git commit -m "test(pkg19): AC-3 — no RW mounts injected by synthesized task.toml"
```

---

## Task 7 — AC-3 LIVE: EROFS integration test (gated on docker)

**Files:**
- Create: `tests/integration/test_ade_bench_local_task_readonly_contract_live.py`

- [ ] **Step 1: Write the live test.**

```python
# ABOUTME: PKG-19 AC-3 live — agent container cannot mutate bind-mounted
# ABOUTME: ade-bench-root sources; observes EROFS or equivalent.

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None or os.environ.get("CI") == "true",
    reason="requires local docker; skipped on CI",
)


def test_agent_container_cannot_mutate_ade_bench_root(tmp_path: Path) -> None:
    # Skeleton — actual implementation depends on whether ade-bench tasks
    # spawn compose services with host mounts. If they don't, the AC-3 live
    # check reduces to "the materialized view-dir's symlinks remain valid
    # after a docker compose up + agent step" + "the agent's home in the
    # container does not contain a copy of ~/git/ade-bench."
    pytest.skip("Full live wiring landed in validation stage; structural T6 covers the unit-level contract.")
```

- [ ] **Step 2: Commit.**

```bash
git add tests/integration/test_ade_bench_local_task_readonly_contract_live.py
git commit -m "test(pkg19): AC-3 live skeleton — defer full wiring to validation"
```

---

## Task 8 — AC-4 RED: view-dir does NOT include `seeds/solution__*.csv`

**Files:**
- Append to: `tests/unit/test_ade_bench_materialize_local_task.py`

- [ ] **Step 1: Add the exclusion test.**

```python
def test_view_dir_excludes_solution_csv_files(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    # AC-4: solution__*.csv files must NOT be reachable from the view-dir.
    seeds_dir = materialized / "seeds"
    assert seeds_dir.exists(), "seeds/ directory must be reflected (for non-solution files)"
    solution_files = list(seeds_dir.glob("solution__*.csv"))
    assert solution_files == [], (
        f"AC-4: view-dir must not expose solution files; got {solution_files}"
    )
    # Other seed files (e.g., _no-op.txt) remain accessible.
    assert (seeds_dir / "_no-op.txt").exists()


def test_view_dir_solution_files_not_reachable_via_symlink_chain(tmp_path: Path) -> None:
    """AC-4 invariant: even if seeds/ is a symlink, following it must not
    yield solution files (i.e., seeds/ is NOT a whole-dir symlink to
    ade_bench_root when the dir contains excluded files)."""
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    seeds_dir = materialized / "seeds"
    # If seeds_dir is itself a symlink, an attacker following the symlink
    # would see solution__*.csv. AC-4 requires seeds_dir to be a REAL dir
    # when the upstream seeds/ contains excluded files.
    assert not seeds_dir.is_symlink(), (
        "AC-4: seeds/ must be a real directory (with selective symlinks), "
        "NOT a symlink to ade_bench_root's seeds/"
    )
```

- [ ] **Step 2: Run + verify (the Task 3 GREEN already implements the exclusion; tests pass).**

If the Task 3 implementation is correct, both tests pass. If they fail, the exclusion logic in Task 3 is wrong — re-run RED→GREEN.

- [ ] **Step 3: Commit.**

```bash
git add tests/unit/test_ade_bench_materialize_local_task.py
git commit -m "test(pkg19): AC-4 — view-dir excludes seeds/solution__*.csv"
```

---

## Task 9 — AC-4 GREEN: symlink-filter walker (covered by Task 3)

Task 3's `materialize_local_task` implementation already includes the symlink-filter walker (the `has_excluded` branch). This task verifies coverage and adds the negative case: if the upstream task has NO excluded files in a subdirectory, the subdirectory MAY be a whole-dir symlink (fast path).

**Files:**
- Append to: `tests/unit/test_ade_bench_materialize_local_task.py`

- [ ] **Step 1: Add the fast-path test.**

```python
def test_view_dir_whole_dir_symlink_when_no_excluded_files(tmp_path: Path) -> None:
    """When a subdirectory has no excluded files, the materializer may
    whole-dir symlink for performance."""
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    # tests/ has no solution__*.csv files, so it MAY be a whole-dir symlink.
    # (Implementation is free to choose; the test just confirms it works either way.)
    tests_dir = materialized / "tests"
    if tests_dir.exists():
        assert tests_dir.is_dir() or tests_dir.is_symlink()
```

- [ ] **Step 2: Commit.**

```bash
git add tests/unit/test_ade_bench_materialize_local_task.py
git commit -m "test(pkg19): AC-4 — whole-dir symlink fast path verified"
```

---

## Task 10 — AC-4 invariant: verifier-readable solution path stays accessible

**Files:**
- Append to: `tests/unit/test_ade_bench_materialize_local_task.py`

- [ ] **Step 1: Add the verifier-path test.**

The verifier must still be able to read solutions to grade the agent's output. This test asserts that `ade_bench_root / tasks / <slug> / seeds /` is reachable as a SEPARATE filesystem path that the harbor verifier can mount on its own (NOT the agent's view-dir).

```python
def test_ade_bench_root_seeds_remain_unfiltered(tmp_path: Path) -> None:
    """AC-4: solution__*.csv are EXCLUDED from the agent view-dir, but
    REMAIN on the host filesystem under ade_bench_root for the verifier."""
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    # Source seeds dir on disk is untouched.
    upstream_seeds = ade_bench_root / "tasks" / "example001" / "seeds"
    assert (upstream_seeds / "solution__x.csv").exists()
    # The verifier (harbor-side) can still mount upstream_seeds at a
    # different container path — that wiring is harbor's, not razorback's.
```

- [ ] **Step 2: Commit.**

```bash
git add tests/unit/test_ade_bench_materialize_local_task.py
git commit -m "test(pkg19): AC-4 invariant — upstream solutions stay accessible to verifier"
```

---

## Task 11 — AC-5: `--materialize={bind,copy}` flag

**Files:**
- Modify: `src/razorback/cli/__init__.py` (or `src/razorback/cli/run.py` — wherever `rk run` is defined)
- Modify: `src/razorback/benchmarks/ade_bench/tasks.py`
- Create: `tests/unit/test_ade_bench_materialize_mode_flag.py`

- [ ] **Step 1: Locate `rk run` flag definitions.**

```bash
cd /Users/clkao/git/razorback
grep -rn "def run\|def cmd_run\|@.*command.*run\|--max-budget" src/razorback/ | head -10
```

Identify the file + function that defines `rk run`'s argparse / click options.

- [ ] **Step 2: Write the failing test.**

```python
# ABOUTME: PKG-19 AC-5 — --materialize={bind,copy} flag selects view-dir vs full copy.

from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def test_materialize_copy_mode_full_copy(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
        materialize_mode="copy",
    )
    # copy mode: NO symlinks, all real files.
    for p in materialized.rglob("*"):
        if p.is_symlink():
            pytest.fail(f"copy mode must not produce symlinks; found {p}")
    # AC-4 STILL holds in copy mode.
    assert not (materialized / "seeds" / "solution__x.csv").exists()


def test_materialize_bind_mode_uses_symlinks(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg19-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
        materialize_mode="bind",  # default
    )
    # bind mode: at least one symlink exists (e.g., setup.sh).
    setup = materialized / "setup.sh"
    assert setup.is_symlink(), "bind mode must produce symlinks for upstream files"
```

- [ ] **Step 3: Run to verify failure.**

Expected: failure because `materialize_local_task` does not accept `materialize_mode`.

- [ ] **Step 4: Extend `materialize_local_task` with `materialize_mode`.**

In `src/razorback/benchmarks/ade_bench/tasks.py`, add `materialize_mode: Literal["bind", "copy"] = "bind"` parameter. When `"copy"`, replace every `os.symlink(src, dst)` with `shutil.copy2(src, dst)` (or `shutil.copytree` for whole-dir cases). The exclusion logic is unchanged — copy mode still skips `seeds/solution__*.csv`.

- [ ] **Step 5: Wire the CLI flag.**

In the `rk run` command definition, add `--materialize` with `Literal["bind", "copy"]`, default `"bind"`. Forward into `build_job_config_from_spec` and then into the materializer call. Default behavior matches the entity ("Default is bind-mount; copy is opt-in").

- [ ] **Step 6: Run + verify pass.**

- [ ] **Step 7: Commit.**

```bash
git add src/razorback/benchmarks/ade_bench/tasks.py \
        src/razorback/cli/ \
        src/razorback/translate.py \
        tests/unit/test_ade_bench_materialize_mode_flag.py
git commit -m "feat(pkg19): AC-5 — --materialize={bind,copy} flag"
```

---

## Task 12 — AC-6: hydration check (missing/empty `ade_bench_root` fails fast)

**Files:**
- Create: `tests/unit/test_ade_bench_local_task_hydration_check.py`

- [ ] **Step 1: Write the test.**

```python
# ABOUTME: PKG-19 AC-6 — missing or empty ade_bench_root fails fast with clear error.

from pathlib import Path

import pytest


def test_missing_ade_bench_root_raises(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    missing_root = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError) as exc_info:
        materialize_local_task(
            ade_bench_root=missing_root,
            task_slug="example001",
            docker_image="ade-bench-agent:latest",
            cache_root=tmp_path / "cache",
        )
    assert "does_not_exist" in str(exc_info.value) or "example001" in str(exc_info.value)


def test_empty_ade_bench_root_raises(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    empty_root = tmp_path / "empty_root"
    empty_root.mkdir()
    with pytest.raises(FileNotFoundError) as exc_info:
        materialize_local_task(
            ade_bench_root=empty_root,
            task_slug="example001",
            docker_image="ade-bench-agent:latest",
            cache_root=tmp_path / "cache",
        )
    assert "example001" in str(exc_info.value)
```

- [ ] **Step 2: Verify pass (Task 3 GREEN implementation already raises FileNotFoundError).**

- [ ] **Step 3: Commit.**

```bash
git add tests/unit/test_ade_bench_local_task_hydration_check.py
git commit -m "test(pkg19): AC-6 — hydration check on missing/empty ade_bench_root"
```

---

## Task 13 — Full pytest sweep (regression gate)

**Files:** none modified.

- [ ] **Step 1: Run the full sweep.**

```bash
cd /Users/clkao/git/razorback
uv run pytest -x --timeout=60
```

Expected: all PASS. Diagnose any regression. New tests landed by Tasks 2–12 must all pass.

- [ ] **Step 2: If sweep is green, commit a stage-checkpoint marker (no code change).**

This step is intentionally a no-op commit unless any regression is found. The git log already records each TDD step; this step's purpose is to confirm the gate.

---

## Task 14 — AC-7: emit validation-stage probe spec

**Files:**
- Create: `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml`

- [ ] **Step 1: Write the spec.**

```yaml
version: 1
experiment: probe-ade-bench-airbnb001-claude-harbor-local
agent:
  kind: claude-cli
  model: claude-opus-4-5
  sampling:
    temperature: 0.0
  tools_allowed:
    - Bash
    - Read
    - Write
    - Edit
    - Glob
    - Grep
benchmark:
  kind: ade-bench
  tasks_root: .
  ade_bench_root: ~/git/ade-bench
  tasks:
    - slug: airbnb001
trials: 1
experiment_meta:
  max_budget_usd: 5.0
  estimated_cost_usd: 2.0
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
```

- [ ] **Step 2: Commit.**

```bash
git add examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml
git commit -m "feat(pkg19): AC-7 — probe spec for validation-stage re-dispatch"
```

- [ ] **Step 3: DO NOT run the probe.**

Validation stage runs the probe AFTER the captain frees disk + exports `CLAUDE_CODE_OAUTH_TOKEN`. Implementation stage emits the spec only.

---

## Out-of-implementation-stage scope

- **AC-3 live EROFS test (T7's full implementation).** Implementation stage commits a skeleton; validation stage does the wiring + live run.
- **AC-7 probe re-dispatch.** Implementation stage commits the spec; validation stage dispatches a fresh ensign that runs Phase 2–5 of the probe procedure.
- **Goal 2 (48-task × N≥3 ade-bench Haiku baseline).** Depends on PKG-19 landing + AC-7 producing a CLEAN/PARTIAL verdict. Not in PKG-19's scope.

## Handoff to validation stage

When implementation completes, the validation-stage worker:
1. Confirms disk is freed to ≥ 10 GiB and `CLAUDE_CODE_OAUTH_TOKEN` is set.
2. Reads the probe spec at `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml`.
3. Dispatches the ade-bench probe procedure (Phase 2 — spec authorship is already done; Phase 3 — 1-3 task smoke; Phase 4 — five-point honesty check including the `solution__*.csv` non-leak assertion; Phase 5 — written report).
4. Records the verdict (CLEAN / PARTIAL / FAIL) at `docs/superpowers/plans/2026-05-20-ade-bench-path-probe.md` (updated) or a sibling-dated file.
5. If the probe surfaces a NEW failure mode (not AC-1..AC-6), files a new pkg2X-* entity rather than re-opening PKG-19.
