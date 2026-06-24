# swe-bench-pro Scoring-Join Fix + Example Spec Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FIX the scoring aggregator so swe-bench-pro's canonical project-prefixed task slugs (which contain `__` and exceed the 32-char join window) stratify into distinct per-task query cells instead of collapsing to `dataset="default"`, and add a user-facing `examples/specs/swe-bench-pro-spacedock-codex.yaml` that freezes offline.

**Architecture:** This is a **production-code change** (the cycle-1 doc-only premise was disproven — see entity `## Feedback Cycles`). The aggregator's view-manifest join parses the trial dir NAME (`trial_dir.name.split("__")[0] == view_dir.name[:32].rstrip("_-")`), which is doubly broken for swe-bench-pro: the `__` split mis-cuts canonical slugs and the `[:32]` truncation collides distinct slugs. The robust fix resolves the view manifest DIRECTLY from each trial's persisted `config.json["task"]["path"]` (the full materialized view-dir path Harbor records), eliminating all dir-name parsing. The legacy dir-name join is retained as a fallback so dabstep/spider2/ade (short, `__`-free slugs, possibly older run dirs without a usable config) do not regress. Plus the unchanged AC-1/AC-2 example-spec authoring from cycle 1.

**Tech Stack:** Python 3, pytest, `uv run`, harbor 0.6.6 (`harbor.models.trial.config.TrialConfig`), Typer CLI (`rk`), pydantic spec schema, YAML.

## Global Constraints

- Spec source of truth: `docs/razorback-implementation/swe-bench-pro-example-spec-scoring-strata.md` (Problem § + 3 ACs revised for cycle 2). Design §: `docs/superpowers/specs/2026-06-24-swe-bench-pro-on-harbor-design.md` (E3, lines 133-148).
- AC-3 is now a FIX, not a confirmation. The fix lives in `src/razorback/runs/aggregate.py` `_resolve_stratum_from_task_view_manifest` (`:131-155`). It MUST handle canonical `__` slugs AND long-slug `[:32]` collisions.
- The fix MUST NOT regress dabstep/spider2/ade: `tests/unit/test_task_identity_scoring.py` and `tests/integration/test_spider2_dbt_scored_run_identity.py` (short, `__`-free slugs) must still pass.
- Agent block MUST be `kind: spacedock_solver` / `runtime: codex` (the only schema shape with `solver_workflow`/`max_turns`; `CodexAgentBlock` `schema.py:49-89` lacks them; `SpacedockSolverAgentBlock` `schema.py:92-119` has them).
- Dataset ref `scale-ai/swe-bench-pro@latest` (offline placeholder; see OPEN CAPTAIN DECISIONS). SWE-tuned budget above the 1200s codex default: `max_turns: 400`, `override_timeout_sec: 5400`, `max_timeout_sec: 7200` (`max_timeout_sec >= override_timeout_sec` enforced, `schema.py:122-132`).
- `./examples/solver_workflows/codex-benchmark-solver` exists (verified).
- Committed `*.frozen.yaml` + `provenance.yaml` under `examples/specs/` are gitignored (verified). AC-1 is verified by RUNNING `rk freeze --allow-missing`, NOT a committed frozen file. Do NOT `git add` them.
- Do NOT conflate scoring surfaces: `aggregate_summary` → `summary.json`; `rk score` (`cli/score.py:122-125`) → separate `score_version`/`strata`. AC-3 asserts ONLY `summary.json`.

---

## Plan-Time Live Verifications (recorded)

All reproduced/prototyped with `.venv/bin/python` before authoring:

1. **Both bugs reproduced against live code.** Real `generate_trial_name` (`harbor/models/trial/config.py:219` = `task_name[:32].rstrip("_-") + "__" + ShortUUID().random(7)`) + the live `aggregate_summary`: canonical slugs `astropy__astropy-7166`, `django__django-11099`, `django__django-11098` → `summary.json` `datasets` = `['default']` with `n_queries=1` (two of three lost to the `[:32]` collision). Confirms the `default` collapse + collision.
2. **Spike: Harbor persists the task path per trial.** `harbor/trial/trial.py:934` writes `self._trial_paths.config_path.write_text(self.config.model_dump_json(indent=4))`. `harbor.models.trial.paths.TrialPaths.config_path = trial_dir / "config.json"`. The serialized `TrialConfig.task` (`TaskConfig`, `harbor/models/trial/config.py:129`) carries `path` = the view-dir path razorback passed (e.g. `tasks/swe-bench-pro-astropy__astropy-7166`) — FULL, untruncated. `TrialConfig(task=TaskConfig(path=...))` round-trips `task.path` verbatim in `model_dump_json`.
3. **Fix prototype is GREEN.** Resolving `config.json → task["path"] → <re-anchored view>/view_manifest.json` over the three canonical slugs yields query_ids `['astropy__astropy-7166','django__django-11098','django__django-11099']` — 3 distinct, all `dataset="swe-bench-pro"`, no `default`, no collision.
4. **Aggregator surfaces confirmed live:** `_read_json` helper (`aggregate.py:96`), `task_views_root` import already present (`aggregate.py:14`, = `run_dir/"tasks"`), manifest-stratum precedence (`aggregate.py:112-114`), `default` collapse (`aggregate.py:414-418`), `aggregate_summary` (`aggregate.py:526-563`). `_iter_trial_dirs` requires `result.json` to exist in a trial dir (`aggregate.py:90`).
5. **`SpacedockSolverAgentBlock` accepts `runtime: codex` + tuned budget** (constructed OK); `rk freeze --allow-missing` exits 0 offline writing `benchmark.dataset` verbatim; frozen/provenance gitignored. (Carried from cycle 1, re-confirmed.)

---

## AC ↔ Task Map

| AC | Requirement | Task(s) | TDD checkpoint |
|----|-------------|---------|----------------|
| AC-3 | FIX the join so canonical `__` swe-bench-pro slugs stratify into distinct cells (no `default`, no `[:32]` collision); no regression | Task 1 (load-bearing, riskiest-first) | RED-first test (canonical `__` slugs + real `generate_trial_name` + real `config.json`) FAILS on current aggregator, PASSES after the `config.json`-path resolution fix. Regression: existing identity + spider2 tests stay green. |
| AC-1 | Schema-valid `spacedock_solver`/`runtime: codex` spec, SWE-tuned budget, freezes via `rk freeze --allow-missing`; frozen dataset verbatim; grep agent shape + budget | Task 2 | `rk freeze … --allow-missing` exit 0 + frozen dataset assertion + grep. |
| AC-2 | ABOUTME header note names the hydration prerequisite | Task 2 (same file) | `grep -F 'scale-ai/swe-bench-pro' …` returns the ABOUTME line. |

Riskiest-first: **Task 1 (AC-3 fix) before Task 2 (AC-1/AC-2)** — the scoring-join fix is the load-bearing contract; the freeze/grep checks are cheap and already validated.

---

## File Structure

- **Modify** `src/razorback/runs/aggregate.py` — `_resolve_stratum_from_task_view_manifest` (`:131-155`): add a `config.json`-task-path resolution that runs FIRST, falling back to the existing dir-name join. New private helpers `_stratum_from_config_task_path(trial_dir)` and `_stratum_from_manifest_payload(payload)`. (Task 1)
- **Create** `tests/unit/test_swe_bench_pro_scoring_strata.py` — the AC-3 red-first test + collision case + regression assertions. (Task 1)
- **Create** `examples/specs/swe-bench-pro-spacedock-codex.yaml` — the AC-1/AC-2 example spec. (Task 2)

---

### Task 1: AC-3 — FIX the scoring join for canonical swe-bench-pro slugs (load-bearing, riskiest-first)

**Files:**
- Modify: `src/razorback/runs/aggregate.py:131-155` (`_resolve_stratum_from_task_view_manifest` + new helpers)
- Create: `tests/unit/test_swe_bench_pro_scoring_strata.py`
- Reference (read-only): `harbor/models/trial/config.py:208-221` (`generate_trial_name`, `TrialConfig`, `TaskConfig`), `harbor/trial/trial.py:934` (config.json write), existing `tests/unit/test_task_identity_scoring.py` + `tests/integration/test_spider2_dbt_scored_run_identity.py` (regression guards).

**Interfaces:**
- Consumes: `from razorback.runs.aggregate import aggregate_summary`; `from harbor.models.trial.config import TrialConfig, TaskConfig` (test only, to generate REAL trial names + the REAL config.json). `aggregate_summary(run_dir) -> None`.
- The fix's resolution contract: for a trial dir, read `trial_dir/"config.json"` → `["task"]["path"]`; the view dir is located by re-anchoring `Path(task_path).name` under `task_views_root(run_dir)` (= `run_dir/"tasks"`), then read `<view>/view_manifest.json` for `benchmark_kind`/`benchmark_task_id`. Returns `{dataset, query_id, benchmark_kind, benchmark_task_id}` exactly as the existing path does (`aggregate.py:149-154`), or `None` to fall through to the dir-name join.
- Produces: no downstream consumers (`aggregate_summary` writes `summary.json` as a side effect).

- [ ] **Step 1: Write the failing test (RED-first, with real harbor naming + config.json)**

Create `tests/unit/test_swe_bench_pro_scoring_strata.py`:

```python
# ABOUTME: AC-3 — aggregate_summary stratifies CANONICAL swe-bench-pro task slugs
# ABOUTME: (containing __, exceeding the 32-char join window) into distinct per-task
# ABOUTME: query cells. RED on the dir-name join; GREEN via config.json task-path
# ABOUTME: resolution. Regression-guards short __-free slugs (dabstep/spider2/ade).
import json
import re
from pathlib import Path

from harbor.models.trial.config import TaskConfig, TrialConfig

from razorback.runs.aggregate import aggregate_summary


def _view_name(slug: str) -> str:
    # Mirrors harbor_tasks/materialize.py:_view_name (kind-task, sanitized, [:160]).
    raw = f"swe-bench-pro-{slug}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-._")[:160] or "task-view"


def _build_swe_run(tmp_path: Path, slugs_rewards: list[tuple[str, float]]) -> Path:
    """Synthetic run dir using REAL harbor trial naming + the REAL per-trial
    config.json harbor persists (trial.py:934). Each view dir carries a
    view_manifest.json sidecar; each trial dir carries result.json + config.json
    whose task.path points at its view dir."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for slug, reward in slugs_rewards:
        view = run_dir / "tasks" / _view_name(slug)
        view.mkdir(parents=True)
        (view / "view_manifest.json").write_text(
            json.dumps(
                {
                    "benchmark_kind": "swe-bench-pro",
                    "benchmark_task_id": slug,
                    "view_mode": "copy",
                }
            )
        )
        # REAL harbor TrialConfig: trial_name via generate_trial_name, task.path
        # = the view dir. This is exactly what harbor writes to config.json.
        tc = TrialConfig(task=TaskConfig(path=str(view)))
        trial = run_dir / tc.trial_name
        trial.mkdir()
        (trial / "result.json").write_text(
            json.dumps({"verifier_result": {"rewards": {"reward": reward}}})
        )
        (trial / "config.json").write_text(tc.model_dump_json(indent=4))
    return run_dir


def test_aggregator_stratifies_canonical_swe_bench_pro_slugs(tmp_path):
    """Canonical project-prefixed swe-bench-pro slugs (with __, > 18 task-id
    chars) land in DISTINCT swe-bench-pro query cells, never the `default`
    collapse, and -11099/-11098 do NOT collide. RED on the dir-name join."""
    run_dir = _build_swe_run(
        tmp_path,
        [
            ("astropy__astropy-7166", 1.0),
            ("django__django-11099", 0.0),
            ("django__django-11098", 1.0),
        ],
    )

    aggregate_summary(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text())
    datasets = summary["datasets"]

    assert "swe-bench-pro" in datasets, (
        f"expected swe-bench-pro stratum, got {sorted(datasets)}"
    )
    assert "default" not in datasets, (
        f"canonical __ slugs collapsed to default: {datasets.get('default')}"
    )
    cells = datasets["swe-bench-pro"]["queries"]
    assert datasets["swe-bench-pro"]["n_queries"] == 3, datasets["swe-bench-pro"]
    cell_ids = {c["query_id"] for c in cells}
    assert cell_ids == {
        "astropy__astropy-7166",
        "django__django-11099",
        "django__django-11098",
    }, f"collision/mis-cut: cells={cell_ids}"
    kinds = {t["stratum"].get("benchmark_kind") for t in summary["trials"]}
    assert kinds == {"swe-bench-pro"}, kinds


def test_short_dunderless_slugs_still_stratify_via_fallback(tmp_path):
    """Regression guard: short, __-free slugs that DON'T carry a config.json
    task path still resolve through the retained dir-name join (the
    dabstep/spider2/ade path). No config.json written here on purpose."""
    run_dir = tmp_path / "legacy"
    run_dir.mkdir()
    for view_name, slug, reward in [
        ("ade-bench-adebench-fixture-001", "adebench-fixture-001", 1.0),
        ("spider2-dbt-spider2-fixture-001", "spider2-fixture-001", 0.0),
    ]:
        view = run_dir / "tasks" / view_name
        view.mkdir(parents=True)
        kind = "ade-bench" if view_name.startswith("ade") else "spider2-dbt"
        (view / "view_manifest.json").write_text(
            json.dumps({"benchmark_kind": kind, "benchmark_task_id": slug})
        )
        trial_prefix = view_name[:32].rstrip("_-")
        trial = run_dir / f"{trial_prefix}__deadbee"
        trial.mkdir()
        (trial / "result.json").write_text(
            json.dumps({"verifier_result": {"rewards": {"reward": reward}}})
        )
    aggregate_summary(run_dir)
    datasets = json.loads((run_dir / "summary.json").read_text())["datasets"]
    assert set(datasets) == {"ade-bench", "spider2-dbt"}, sorted(datasets)
    assert "default" not in datasets
```

- [ ] **Step 2: Run test to verify it FAILS (RED) on the current aggregator**

Run: `uv run pytest tests/unit/test_swe_bench_pro_scoring_strata.py::test_aggregator_stratifies_canonical_swe_bench_pro_slugs -v`
Expected: FAIL on `assert "swe-bench-pro" in datasets` / `assert "default" not in datasets` — the current dir-name join collapses all three canonical slugs to `default`. (The regression test `test_short_dunderless_slugs_still_stratify_via_fallback` should already PASS on current code — confirm with `uv run pytest tests/unit/test_swe_bench_pro_scoring_strata.py::test_short_dunderless_slugs_still_stratify_via_fallback -v`.)

- [ ] **Step 3: Implement the fix in `aggregate.py`**

The current function (`src/razorback/runs/aggregate.py:131-155`):

```python
def _resolve_stratum_from_task_view_manifest(trial_dir: Path) -> dict | None:
    run_dir = trial_dir.parent
    views_root = task_views_root(run_dir)
    if not views_root.is_dir():
        return None

    trial_prefix = trial_dir.name.split("__", 1)[0]
    for manifest_path in sorted(views_root.glob("*/view_manifest.json")):
        payload = _read_json(manifest_path)
        if payload is None:
            continue
        view_name = manifest_path.parent.name[:32].rstrip("_-")
        if trial_prefix != view_name:
            continue
        benchmark_kind = payload.get("benchmark_kind")
        benchmark_task_id = payload.get("benchmark_task_id")
        if not benchmark_kind or not benchmark_task_id:
            return None
        return {
            "dataset": str(benchmark_kind),
            "query_id": str(benchmark_task_id),
            "benchmark_kind": str(benchmark_kind),
            "benchmark_task_id": str(benchmark_task_id),
        }
    return None
```

Replace that entire block (`:131-155`) with the following — a shared payload shaper, the new config-path resolver run FIRST, and the dir-name join kept as a fallback:

```python
def _stratum_from_manifest_payload(payload: dict | None) -> dict | None:
    """Shape a view_manifest.json payload into a stratum dict, or None when it
    lacks the required identity fields."""
    if payload is None:
        return None
    benchmark_kind = payload.get("benchmark_kind")
    benchmark_task_id = payload.get("benchmark_task_id")
    if not benchmark_kind or not benchmark_task_id:
        return None
    return {
        "dataset": str(benchmark_kind),
        "query_id": str(benchmark_task_id),
        "benchmark_kind": str(benchmark_kind),
        "benchmark_task_id": str(benchmark_task_id),
    }


def _stratum_from_config_task_path(trial_dir: Path) -> dict | None:
    """Resolve the view manifest from the trial's recorded task path.

    Harbor persists `<trial_dir>/config.json` (TrialConfig) carrying
    `task.path` = the full materialized view-dir path razorback passed
    (harbor/trial/trial.py writes config.json; TaskConfig.path round-trips
    verbatim). Reading the manifest from that path avoids ALL trial-dir-name
    parsing, so canonical swe-bench-pro slugs (which contain `__` and exceed
    the 32-char join window) resolve correctly — no `__` mis-cut, no `[:32]`
    collision. Returns None to fall back to the dir-name join when config.json
    is absent or carries no usable task path.
    """
    config = _read_json(trial_dir / "config.json")
    if not isinstance(config, dict):
        return None
    task = config.get("task")
    if not isinstance(task, dict):
        return None
    raw_path = task.get("path")
    if not raw_path:
        return None
    view_dir_name = Path(str(raw_path)).name
    # Re-anchor under this run's tasks_root: the recorded path may be absolute,
    # cwd-relative, or from another machine; the view-dir name is the stable
    # join key and the view always lives under run_dir/tasks.
    views_root = task_views_root(trial_dir.parent)
    for candidate in (Path(str(raw_path)), views_root / view_dir_name):
        manifest = candidate / "view_manifest.json"
        if manifest.is_file():
            stratum = _stratum_from_manifest_payload(_read_json(manifest))
            if stratum is not None:
                return stratum
    return None


def _resolve_stratum_from_task_view_manifest(trial_dir: Path) -> dict | None:
    # Preferred: resolve directly from the trial's recorded task path
    # (robust to canonical `__` slugs + long-slug [:32] collisions).
    via_config = _stratum_from_config_task_path(trial_dir)
    if via_config is not None:
        return via_config

    # Fallback: the legacy dir-name join. Keeps short, __-free slugs
    # (dabstep/spider2/ade) and config-less/legacy run dirs working.
    run_dir = trial_dir.parent
    views_root = task_views_root(run_dir)
    if not views_root.is_dir():
        return None

    trial_prefix = trial_dir.name.split("__", 1)[0]
    for manifest_path in sorted(views_root.glob("*/view_manifest.json")):
        view_name = manifest_path.parent.name[:32].rstrip("_-")
        if trial_prefix != view_name:
            continue
        return _stratum_from_manifest_payload(_read_json(manifest_path))
    return None
```

Note: `task_views_root` is already imported (`aggregate.py:14`) and `_read_json` already defined (`aggregate.py:96`) — no new imports. The refactor folds the shared payload-shaping into `_stratum_from_manifest_payload` (DRY). The one behavioral nuance: the old fallback `return None` immediately when a matched manifest lacked identity fields; the new fallback returns `None` from the helper and the loop then exhausts (no other view matches the same unique `trial_prefix`) and returns `None` — same net result.

- [ ] **Step 4: Run the test to verify it PASSES (GREEN)**

Run: `uv run pytest tests/unit/test_swe_bench_pro_scoring_strata.py -v`
Expected: BOTH tests PASS — canonical `__` slugs land in 3 distinct `swe-bench-pro` cells (no `default`, no collision) via config-path resolution; short `__`-free slugs still stratify via the fallback.

- [ ] **Step 5: Run the regression guard (dabstep/spider2/ade must not regress)**

Run: `uv run pytest tests/unit/test_task_identity_scoring.py tests/integration/test_spider2_dbt_scored_run_identity.py tests/unit/test_translate_swe_bench_pro.py -v`
Expected: ALL PASS. These use short, `__`-free slugs without a config.json task path, exercising the retained dir-name fallback unchanged.

- [ ] **Step 6: Run the broader scoring test surface for safety**

Run: `uv run pytest tests/unit/ -k "aggregate or scoring or identity or strat" -v`
Expected: PASS (no collateral breakage).

- [ ] **Step 7: Commit**

```bash
git add src/razorback/runs/aggregate.py tests/unit/test_swe_bench_pro_scoring_strata.py
git commit -m "fix: resolve scoring strata from trial config.json task path

The view-manifest join parsed the trial dir NAME
(trial_dir.name.split('__')[0] == view_dir.name[:32].rstrip('_-')), which
collapsed every canonical swe-bench-pro slug to dataset=default: the __ split
mis-cut slugs like astropy__astropy-7166 and the [:32] truncation collided
django__django-11099/-11098. Resolve the view manifest directly from the
trial's persisted config.json[task][path] (the full view-dir path harbor
records), eliminating all dir-name parsing. Retain the dir-name join as a
fallback so dabstep/spider2/ade short __-free slugs do not regress.
Entity: swe-bench-pro-example-spec-scoring-strata (plan-gate cycle 2).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: AC-1 + AC-2 — User-facing example spec (freezes offline; hydration-prereq note)

(Unchanged from cycle 1 — the spec shape + offline freeze passed Codex review.)

**Files:**
- Create: `examples/specs/swe-bench-pro-spacedock-codex.yaml`
- Reference (read-only): `examples/specs/dabstep-claude-harbor.yaml` (spacedock_solver shape), `examples/specs/spider2-dbt-harbor-codex.yaml` (ABOUTME + qualified-ref + commented selector block).

**Interfaces:**
- Consumes: `src/razorback/spec/schema.py` (`SpacedockSolverAgentBlock`, `HarborBenchmarkBlock`) + `rk freeze`.
- Produces: a transient gitignored frozen spec whose `benchmark.dataset` equals `scale-ai/swe-bench-pro@latest` verbatim.

- [ ] **Step 1: Write the spec file**

Create `examples/specs/swe-bench-pro-spacedock-codex.yaml`:

```yaml
# ABOUTME: User-facing swe-bench-pro score spec — Harbor published dataset ref
# ABOUTME: scale-ai/swe-bench-pro@latest (kind: harbor, qualified-ref resolution path).
# ABOUTME: A live run requires the scale-ai/swe-bench-pro harbor-package to be
# ABOUTME: hydrated/checked-out first (the PKG-40-style git-checkout blocker); freeze +
# ABOUTME: schema-validate work offline without it via `rk freeze --allow-missing`.
version: 1
experiment: swe-bench-pro-spacedock-codex
agent:
  kind: spacedock_solver
  runtime: codex
  model: gpt-5.5
  sampling:
    temperature: 0.0
    top_p: null
    seed: null
  solver_workflow: ./examples/solver_workflows/codex-benchmark-solver
  # SWE-tuned budget — above the 1200s codex default: large repos + long
  # test suites need more turns and a longer per-attempt/overall timeout.
  max_turns: 400
  override_timeout_sec: 5400
  max_timeout_sec: 7200
  reasoning_effort: xhigh
benchmark:
  kind: harbor
  dataset: scale-ai/swe-bench-pro@latest
  # Smoke-test a subset (spec-side selectors; same semantics as harbor -l/-i/-x):
  #   n_tasks: 1                 # quickest: cap to the first N tasks (no names needed)
  #   tasks:                     # or run only specific project-prefixed slugs
  #     - astropy__astropy-7166
  #   exclude_tasks:             # or run everything except these
  #     - django__django-11099
  # All commented out: the default is a full dataset run.
trials: 1
concurrency:
  trials: 1
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
```

- [ ] **Step 2: Verify the spec freezes offline (AC-1 freeze check)**

Run: `uv run rk freeze examples/specs/swe-bench-pro-spacedock-codex.yaml --allow-missing --out /tmp/swe-bench-pro.frozen.yaml`
Expected: exit 0; stdout `wrote /tmp/swe-bench-pro.frozen.yaml` + `wrote examples/specs/provenance.yaml`.

Then: `grep -n 'dataset:' /tmp/swe-bench-pro.frozen.yaml`
Expected: `dataset: scale-ai/swe-bench-pro@latest`

- [ ] **Step 3: Verify the agent shape + tuned budget grep (AC-1 grep check)**

Run: `grep -E 'kind: spacedock_solver|runtime: codex|max_turns|override_timeout_sec' examples/specs/swe-bench-pro-spacedock-codex.yaml`
Expected: all four match — `kind: spacedock_solver`, `runtime: codex`, `max_turns: 400`, `override_timeout_sec: 5400`.

- [ ] **Step 4: Verify the hydration-prereq note (AC-2 grep check)**

Run: `grep -F 'scale-ai/swe-bench-pro' examples/specs/swe-bench-pro-spacedock-codex.yaml`
Expected: returns the ABOUTME header line(s) naming the `scale-ai/swe-bench-pro` harbor-package hydration step (the PKG-40-style blocker).

- [ ] **Step 5: Clean up gitignored freeze side effects**

Run: `git status --short examples/specs/`
Expected: shows ONLY `?? examples/specs/swe-bench-pro-spacedock-codex.yaml`. If `provenance.yaml` appears it is gitignored — do NOT `git add` it (`git checkout examples/specs/provenance.yaml` or leave untracked).

- [ ] **Step 6: Commit (spec only)**

```bash
git add examples/specs/swe-bench-pro-spacedock-codex.yaml
git commit -m "feat: add swe-bench-pro spacedock_solver/codex example spec

kind: harbor + scale-ai/swe-bench-pro@latest, spacedock_solver/runtime:codex
with codex-benchmark-solver workflow and SWE-tuned budget (max_turns 400,
override_timeout_sec 5400, max_timeout_sec 7200). ABOUTME header records the
harbor-package hydration prerequisite a live run requires. Freezes offline via
rk freeze --allow-missing. Entity: swe-bench-pro-example-spec-scoring-strata.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final Verification (all ACs, run together)

- [ ] **AC-3:** `uv run pytest tests/unit/test_swe_bench_pro_scoring_strata.py tests/unit/test_task_identity_scoring.py tests/integration/test_spider2_dbt_scored_run_identity.py -v` → ALL PASS (fix works on canonical `__` slugs; no regression).
- [ ] **AC-1:** `uv run rk freeze examples/specs/swe-bench-pro-spacedock-codex.yaml --allow-missing --out /tmp/swe.frozen.yaml` → exit 0; `grep 'dataset:' /tmp/swe.frozen.yaml` → `scale-ai/swe-bench-pro@latest`; `grep -E 'kind: spacedock_solver|runtime: codex|max_turns|override_timeout_sec' examples/specs/swe-bench-pro-spacedock-codex.yaml` → all four.
- [ ] **AC-2:** `grep -F 'scale-ai/swe-bench-pro' examples/specs/swe-bench-pro-spacedock-codex.yaml` → ABOUTME note.
- [ ] **No stray adds:** `git status --short` → only the three intended files committed (`aggregate.py`, the new test, the spec); no `.frozen.yaml`/`provenance.yaml` staged.

---

## OPEN CAPTAIN DECISIONS

1. **The `@<ref>` pin.** Plan uses `@latest` offline placeholder (mirrors `dabstep@latest`; `spider2-dbt` pinned `@1.0`). Keep `@latest`, or pin a concrete published ref? Safe offline either way (`rk freeze --allow-missing` writes verbatim).
2. **Residual fallback exposure (LOW).** The fix prefers `config.json` task-path resolution; the dir-name join survives only as a fallback. If a real swe-bench-pro run dir ever lacked a usable `config.json` task path (it should not — harbor always writes it, `trial.py:934`), the fallback's `__`/`[:32]` bugs would re-appear for that trial. The spike confirms harbor always persists it, so this is not expected in practice; flagged for captain awareness. Optionally, a future hardening could DROP the dir-name fallback for swe-bench-pro once E1's live hydration smoke confirms real run dirs carry config.json — out of scope for this mechanism-smoke entity.

---

## Self-Review

- **Spec coverage:** AC-3 (fix) → Task 1 (red-first test + production fix + regression guard). AC-1 → Task 2 (freeze + grep). AC-2 → Task 2 (ABOUTME). Entity Problem § fix-mechanism (config.json task path) → Task 1 Step 3. Regression requirement → Task 1 Steps 5-6. No gaps.
- **Placeholder scan:** No TBD/TODO. All test + fix + spec code is complete and literal. Commands carry expected output.
- **Type/name consistency:** Fix helper names `_stratum_from_config_task_path`, `_stratum_from_manifest_payload` used consistently in Step 3. `aggregate_summary(run_dir)` matches `aggregate.py:526`. `task_views_root` already imported (`aggregate.py:14`), `_read_json` already defined (`aggregate.py:96`) — no new `aggregate.py` imports. Test imports `TrialConfig, TaskConfig` from `harbor.models.trial.config` (verified path). View-name builder mirrors `materialize.py:_view_name`. Stratum dict shape matches the existing return (`aggregate.py:149-154`). `datasets[...]["queries"]`/`n_queries`/`query_id` match `_render_legacy_datasets` (`aggregate.py:493-508`).
