# harbor-view task identity through scored runs (spider2-dbt + generic) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Harbor task-view materialize root and the solver/scoring discovery root agree so a spider2-dbt scored run carries `benchmark_kind` / `benchmark_task_id` end-to-end, without changing the generic `kind: harbor` identity behavior.

**Architecture:** A single producer materializes view manifests under `tasks_root` (`run_dir/tasks`), but two independent consumers — `SpacedockSolverAgent` freeze-identity discovery and the scoring aggregator — scan a divergent hardcoded root (`run_dir/_razorback/task_views`). Nothing writes that root, so the manifests are invisible. We reconcile by pointing **both consumers at the actual `tasks_root`** (direction (b)) via one shared resolver, leaving the producer and the run-orchestrator contract untouched.

**Tech Stack:** Python 3.12, pytest, pydantic (JobConfig/Spec), uv for env.

## Global Constraints

- Entity is `auto-approve: false` — touches the run-orchestrator path contract.
- Do NOT change the generic `kind: harbor` / `harbor-local` identity semantics (AC-3). The pure pass-through path does not materialize manifests; it must keep falling back to `stratum.json` sidecars / trial-name parsing.
- Producer `tasks_root` is set at `src/razorback/cli/run.py:311` as `run_dir / "tasks"` and threaded to `spec_to_job_config(..., tasks_root=...)`. Do not alter this.
- All commands run from repo root `/Users/kent/Dev/InfuseAI/GitHub/razorback` under the project venv: prefix with `uv run` (e.g. `uv run pytest ...`).
- Stay on `main` for this plan; implementation happens later in a worktree.

---

## Design decision: discovery-root reconciliation direction (the linchpin)

Three candidate directions were named in the entity Test plan. The single producer / dual consumer split is the root cause:

- **Producer** — `src/razorback/translate.py:369` sets `view_root = Path(tasks_root)` and materializes each spider2-dbt view there. `tasks_root` = `run_dir / "tasks"` (`src/razorback/cli/run.py:311`). Harbor also runs trials from these task dirs (`TaskConfig(path=...)`), so this is the run-orchestrator contract.
- **Consumer A** — `src/razorback/agents/spacedock_solver.py:340`: `views_root = run_dir / "_razorback" / "task_views"` (freeze-identity discovery).
- **Consumer B** — `src/razorback/runs/aggregate.py:131-132`: `run_dir = trial_dir.parent; views_root = run_dir / "_razorback" / "task_views"` (scoring stratum resolution, feeding `summary.json` / `per_trial_outcomes.json`).

| Direction | Change | Risk | Verdict |
|---|---|---|---|
| (a) Materialize into `_razorback/task_views` | Move producer's `view_root` off `tasks_root` | **High** — breaks the orchestrator contract: harbor's `TaskConfig(path=...)` points at `tasks_root`, so views must live there to be executed. Would force double-materialization or symlinking and a new path contract. | Rejected |
| (b) Point both consumers at `tasks_root` (`run_dir/tasks`) | Two consumer reads + one shared resolver | **Low** — producer + orchestrator already agree on `run_dir/tasks`; we align the two readers to where the manifests already are. Generic path unaffected (no manifest there either way). | **CHOSEN** |
| (c) Populate `trial_name_map` | Fill the empty map at `translate.py:388` | Wrong layer — `trial_name_map` feeds the aggregator's DAB *per-query* rewiring, not the `benchmark_kind`/`benchmark_task_id` manifest discovery. Does not satisfy AC-1/AC-2. | Rejected (orthogonal) |

**Chosen: (b).** Lowest-risk reconciliation that makes the materialize root and the discovery/scoring root agree. Trade-off recorded: we accept that the views root name becomes `tasks` (the same dir harbor runs from) rather than a dedicated `_razorback/task_views` sidecar; the manifests already co-locate with the task dirs, so co-locating discovery there is the natural alignment and removes a dead path. The `_razorback/task_views` literal is referenced only by the two consumers (plus their tests) — no producer relies on it.

**Verified facts** (file:line, current tree):
- Producer writes to `tasks_root`: `translate.py:369` `view_root = Path(tasks_root)`; spider2 sets `trial_name_map = {}` at `translate.py:388`.
- Generic `kind: harbor` / `harbor-local` path emits `TaskConfig(path=source)` and does NOT materialize manifests (`translate.py:403-404`, and `tests/unit/test_translate_harbor_block.py:33-50` asserts `path == FIXTURE_ADE_TASKS / ...`). So neither consumer finds a manifest on that path regardless of root → AC-3 is structurally safe.
- Aggregator trials are direct children of `run_dir` (`aggregate.py:83-92`), so `trial_dir.parent == run_dir`.
- Solver backs out `run_dir` via `_resolve_run_dir_from_logs_dir` (`spacedock_solver.py:319-332`).
- Manifest keys present: `benchmark_kind`, `benchmark_task_id`, `child_task_ids`, `view_mode`, etc. (`src/razorback/harbor_tasks/manifest.py:43-62`).

---

## AC ↔ Task map

| AC | Requirement | Tasks |
|---|---|---|
| **AC-1** | Scored spider2-dbt run → `summary.json` / `per_trial_outcomes.json` carry `benchmark_kind=spider2-dbt` + per-task `benchmark_task_id` | Task 1 (shared resolver), Task 3 (aggregator reads `tasks_root`), Task 5 (integration: fixture spider2-dbt → scored artifacts) |
| **AC-2** | `SpacedockSolverAgent` `views_root` discovery resolves the materialized view manifests | Task 1 (shared resolver), Task 2 (solver discovery reads `tasks_root`) |
| **AC-3** | Generic `kind: harbor` identity unchanged; `test_translate_harbor_block` green + pinned regression | Task 4 (regression pin: non-spider2 path produces no manifest stratum, falls back unchanged) |

**Sequencing rationale (riskiest contract first):** Task 1 establishes the single shared root resolver (the contract). Tasks 2-3 migrate the two consumers onto it. **Task 5 (the smallest end-to-end scored-run exercise)** is the riskiest contract — the run-orchestrator `tasks_root` ↔ discovery-root agreement — and is written as an integration test driving a fixture spider2-dbt job to scored artifacts. Per the stage's "smallest end-to-end exercise of the riskiest contract first" rule, Task 5's integration assertion is the proof the whole reconciliation hinges on; Tasks 1-4 are the unit scaffolding that makes it pass. Task 4 pins AC-3 last as a guardrail.

---

## File Structure

- `src/razorback/harbor_tasks/manifest.py` — **add** a shared `task_views_root(run_dir: Path) -> Path` resolver (single source of truth for the materialize/discovery root). This module already owns manifest read/write, so the root literal belongs here.
- `src/razorback/agents/spacedock_solver.py` — **modify** `_discover_task_identity_from_manifest` (line 340) to call the shared resolver instead of the hardcoded `run_dir / "_razorback" / "task_views"`.
- `src/razorback/runs/aggregate.py` — **modify** `_resolve_stratum_from_task_view_manifest` (line 132) to call the shared resolver.
- `tests/unit/test_task_views_root.py` — **create** unit test for the resolver.
- `tests/unit/test_task_identity_scoring.py` — **modify** existing manifest fixtures to write under `tasks/` (the new root) and assert resolution.
- `tests/integration/test_spider2_dbt_scored_run_identity.py` — **create** the end-to-end fixture run → scored artifacts identity test (AC-1).
- `tests/unit/test_translate_harbor_block.py` — **modify**: add AC-3 regression pin that the generic path yields no manifest stratum.

---

### Task 1: Shared `task_views_root` resolver (the contract)

Establish one function that both consumers and (for tests) producers agree on. This is the path contract change in a single place.

**Files:**
- Modify: `src/razorback/harbor_tasks/manifest.py`
- Test: `tests/unit/test_task_views_root.py` (create)

**Interfaces:**
- Produces: `task_views_root(run_dir: Path) -> Path` returning `run_dir / "tasks"`. Both Task 2 and Task 3 consume this exact signature.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_task_views_root.py`:

```python
# ABOUTME: Pins the single shared task-views root used by producer + both consumers.
from pathlib import Path

from razorback.harbor_tasks.manifest import task_views_root


def test_task_views_root_is_tasks_subdir_of_run_dir():
    run_dir = Path("/runs/job-123")
    # The producer materializes views under run_dir/"tasks" (tasks_root);
    # discovery + scoring must resolve the same root.
    assert task_views_root(run_dir) == run_dir / "tasks"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_task_views_root.py -v`
Expected: FAIL with `ImportError: cannot import name 'task_views_root'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/razorback/harbor_tasks/manifest.py` (near the top-level helpers):

```python
def task_views_root(run_dir: Path) -> Path:
    """The single root where Harbor task-view manifests live.

    The run orchestrator materializes views under tasks_root = run_dir/"tasks"
    (cli/run.py threads it into spec_to_job_config; translate.py materializes
    there). Solver freeze-identity discovery and the scoring aggregator MUST
    resolve this same root so a spider2-dbt run's benchmark identity propagates
    end-to-end. See plan: harbor-view-task-identity-scored-runs (direction b).
    """
    return run_dir / "tasks"
```

Ensure `from pathlib import Path` is imported in the module (it is used by existing manifest code; add if absent).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_task_views_root.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/razorback/harbor_tasks/manifest.py tests/unit/test_task_views_root.py
git commit -m "feat(harbor): add shared task_views_root resolver (run_dir/tasks)"
```

---

### Task 2: Solver freeze-identity discovery reads `tasks_root` (AC-2)

Point `SpacedockSolverAgent._discover_task_identity_from_manifest` at the shared root.

**Files:**
- Modify: `src/razorback/agents/spacedock_solver.py:340`
- Test: `tests/integration/test_spacedock_solver_freeze_dir_mechanism.py` (extend) — OR add a focused unit if the integration harness is heavy; see Step 1.

**Interfaces:**
- Consumes: `task_views_root(run_dir)` from Task 1.

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/test_spacedock_solver_freeze_dir_mechanism.py` (or create `tests/unit/test_spacedock_solver_identity_discovery.py` if the integration file's fixtures are too heavy — prefer reusing its `run_dir`/`logs_dir` builders). The test writes a manifest under `run_dir/tasks/<view>/view_manifest.json` and asserts discovery resolves it:

```python
def test_discovery_reads_manifest_under_tasks_root(tmp_path):
    import json
    from razorback.agents.spacedock_solver import SpacedockSolverAgent  # adjust import to match file

    run_dir = tmp_path / "job-abc"
    # harbor lays trials as direct children of run_dir; logs_dir nests under a trial
    trial_name = "spider2-dbt-bq001"
    logs_dir = run_dir / trial_name / "logs"
    logs_dir.mkdir(parents=True)
    (run_dir / "_job_config.yaml").write_text("{}")  # run-dir sentinel for _resolve_run_dir_from_logs_dir

    view_dir = run_dir / "tasks" / "spider2-dbt-bq001"
    view_dir.mkdir(parents=True)
    (view_dir / "view_manifest.json").write_text(json.dumps({
        "benchmark_kind": "spider2-dbt",
        "benchmark_task_id": "bq001",
        "child_task_ids": [],
    }))

    agent = SpacedockSolverAgent.__new__(SpacedockSolverAgent)  # bypass heavy __init__
    agent.logs_dir = str(logs_dir)
    identity = agent._discover_task_identity_from_manifest()
    assert identity["benchmark_kind"] == "spider2-dbt"
    assert identity["benchmark_task_id"] == "bq001"
```

Note for implementer: confirm the constructor-bypass / `logs_dir` attribute access matches the real class; if `_trial_name`/`_resolve_run_dir_from_logs_dir` need more attributes, set them on the bare instance. If bypass is impractical, build a minimal real instance using the integration file's existing fixture factory.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_spacedock_solver_freeze_dir_mechanism.py -k discovery_reads_manifest_under_tasks_root -v`
Expected: FAIL — current code scans `run_dir/_razorback/task_views`, finds nothing, returns `{}`, so `identity["benchmark_kind"]` raises `KeyError`.

- [ ] **Step 3: Write minimal implementation**

In `src/razorback/agents/spacedock_solver.py`, replace the hardcoded root at line 340. Add the import near the other razorback imports:

```python
from razorback.harbor_tasks.manifest import task_views_root
```

Then change `_discover_task_identity_from_manifest`:

```python
        run_dir = self._resolve_run_dir_from_logs_dir(Path(self.logs_dir))
        trial_prefix = trial_name.split("__", 1)[0]
        views_root = task_views_root(run_dir)
        if not views_root.is_dir():
            return {}
```

Leave the rest of the method (the `glob("*/view_manifest.json")` loop and key extraction) unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_spacedock_solver_freeze_dir_mechanism.py -k discovery_reads_manifest_under_tasks_root -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/razorback/agents/spacedock_solver.py tests/integration/test_spacedock_solver_freeze_dir_mechanism.py
git commit -m "fix(solver): freeze-identity discovery reads tasks_root manifests (AC-2)"
```

---

### Task 3: Scoring aggregator reads `tasks_root` (AC-1 plumbing)

Point `_resolve_stratum_from_task_view_manifest` at the shared root and update the existing identity-scoring unit fixtures.

**Files:**
- Modify: `src/razorback/runs/aggregate.py:130-154`
- Test: `tests/unit/test_task_identity_scoring.py` (modify fixtures + assertions)

**Interfaces:**
- Consumes: `task_views_root(run_dir)` from Task 1.

- [ ] **Step 1: Update the failing test fixtures**

In `tests/unit/test_task_identity_scoring.py`, change the manifest-writing helper (`_write_manifest`, ~lines 16-27) so it writes under `run_dir / "tasks" / <view_name> / view_manifest.json` instead of `run_dir / "_razorback" / "task_views" / ...`. Keep the manifest payload (`benchmark_kind`, `benchmark_task_id`, `view_mode`) identical. The assertions in `test_aggregator_resolves_task_identity_from_view_manifest` and `test_task_identity_outputs_are_invariant_to_dispatch_order` stay the same (they assert stratum carries `benchmark_task_id`).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_task_identity_scoring.py -v`
Expected: FAIL — fixtures now write under `tasks/` but production still scans `_razorback/task_views`, so stratum falls back and loses the manifest identity.

- [ ] **Step 3: Write minimal implementation**

In `src/razorback/runs/aggregate.py`, add the import:

```python
from razorback.harbor_tasks.manifest import task_views_root
```

Change `_resolve_stratum_from_task_view_manifest`:

```python
def _resolve_stratum_from_task_view_manifest(trial_dir: Path) -> dict | None:
    run_dir = trial_dir.parent
    views_root = task_views_root(run_dir)
    if not views_root.is_dir():
        return None
```

Leave the `glob("*/view_manifest.json")` loop, prefix match, and return dict unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_task_identity_scoring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/razorback/runs/aggregate.py tests/unit/test_task_identity_scoring.py
git commit -m "fix(scoring): aggregator stratum resolves tasks_root manifests (AC-1)"
```

---

### Task 4: Pin generic `kind: harbor` identity is unchanged (AC-3)

Guardrail: prove the non-spider2 path produces no manifest and the consumers fall back exactly as before.

**Files:**
- Test: `tests/unit/test_translate_harbor_block.py` (add one regression test)

**Interfaces:**
- Consumes: nothing new (read-only assertion against `spec_to_job_config` + aggregator fallback).

- [ ] **Step 1: Run the existing suite to confirm baseline green**

Run: `uv run pytest tests/unit/test_translate_harbor_block.py -v`
Expected: PASS (all existing generic/harbor-local translation tests). This is the AC-3 "stays green" anchor.

- [ ] **Step 2: Write the regression pin (failing only if a future change leaks a manifest into the generic path)**

Add to `tests/unit/test_translate_harbor_block.py`:

```python
def test_harbor_local_path_writes_no_view_manifest(tmp_path):
    """AC-3: the generic harbor-local path emits TaskConfig(path=source) and
    materializes NO view_manifest under tasks_root. Identity on this path must
    keep coming from stratum.json / trial-name parsing, not manifest discovery.
    """
    spec = _make_spec(
        benchmark=HarborLocalBenchmarkBlock(
            kind="harbor-local",
            tasks_root=FIXTURE_ADE_TASKS,
            tasks=["adebench-fixture-001"],
        ),
    )
    run_dir = tmp_path / "testjob"
    job_config, trial_name_map = spec_to_job_config(
        spec, job_name="testjob", jobs_dir=tmp_path
    )
    # task path points at the source dir, not a materialized view under run_dir/tasks
    assert job_config.tasks[0].path == FIXTURE_ADE_TASKS / "adebench-fixture-001"
    # no manifests materialized under the shared task-views root
    assert not list((run_dir / "tasks").glob("*/view_manifest.json")) if (run_dir / "tasks").is_dir() else True
    assert trial_name_map == {}
```

- [ ] **Step 3: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_translate_harbor_block.py -k harbor_local_path_writes_no_view_manifest -v`
Expected: PASS (generic path never materializes; `run_dir/tasks` either absent or has no manifests).

- [ ] **Step 4: Confirm consumers fall back unchanged on this path**

Run: `uv run pytest tests/unit/test_task_identity_scoring.py tests/unit/test_translate_harbor_block.py -v`
Expected: PASS — manifest path is empty for generic, so `_resolve_stratum` falls through to `stratum.json` / `_parse_stratum_from_trial_name` as before.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_translate_harbor_block.py
git commit -m "test(harbor): pin generic kind:harbor identity unchanged (AC-3)"
```

---

### Task 5: End-to-end scored spider2-dbt run preserves identity (AC-1, riskiest contract)

The smallest end-to-end exercise of the run-orchestrator `tasks_root` ↔ discovery-root agreement: drive a fixture spider2-dbt job to scored artifacts and assert identity propagates.

**Files:**
- Test: `tests/integration/test_spider2_dbt_scored_run_identity.py` (create)

**Interfaces:**
- Consumes: `spec_to_job_config` (producer, materializes under `tasks_root`), the scoring aggregator (`aggregate_summary` / `write_per_trial_outcomes` from `src/razorback/runs/aggregate.py`), and the resolver from Task 1.

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/test_spider2_dbt_scored_run_identity.py`. This drives the producer to materialize spider2-dbt views under `tasks_root`, fabricates a completed trial dir keyed to the view, runs scoring, and asserts artifacts carry identity. Reuse the spider2 fixture wiring from `tests/unit/test_translate_spider2_dbt.py` (its `test_spider2_dataset_materializes_views` shows how to call `spec_to_job_config(..., tasks_root=tmp_path / "tasks")` and the monkeypatch needed to avoid network resolve).

```python
# ABOUTME: AC-1 end-to-end — spider2-dbt scored run preserves benchmark identity
# ABOUTME: through summary.json / per_trial_outcomes.json via the tasks_root manifest.
import json
from pathlib import Path

import pytest

# Reuse the fixture/monkeypatch pattern from tests/unit/test_translate_spider2_dbt.py
# (see test_spider2_dataset_materializes_views for the source-resolution stub).

from razorback.translate import spec_to_job_config
from razorback.runs.aggregate import aggregate_summary, write_per_trial_outcomes  # confirmed: aggregate.py:525, :603 (both -> None, write to run_dir)


@pytest.mark.integration
def test_spider2_dbt_scored_run_carries_benchmark_identity(tmp_path, monkeypatch):
    run_dir = tmp_path / "spider2job"
    tasks_root = run_dir / "tasks"

    # 1. Producer: materialize spider2-dbt views under tasks_root.
    #    (Build `spec` exactly as test_translate_spider2_dbt does; stub the
    #    source resolver so no network fetch occurs.)
    spec = _make_spider2_spec()  # copy helper from test_translate_spider2_dbt
    _stub_spider2_source_resolution(monkeypatch)  # copy stub from that test
    job_config, _ = spec_to_job_config(
        spec, job_name="spider2job", jobs_dir=tmp_path, tasks_root=tasks_root
    )

    # Verify the producer wrote a manifest under tasks_root (precondition).
    manifests = list(tasks_root.glob("*/view_manifest.json"))
    assert manifests, "producer must materialize at least one view manifest under tasks_root"
    manifest = json.loads(manifests[0].read_text())
    view_name = manifests[0].parent.name
    assert manifest["benchmark_kind"] == "spider2-dbt"
    task_id = manifest["benchmark_task_id"]

    # 2. Fabricate a completed trial dir keyed to the view prefix.
    #    Aggregator matches trial_prefix = trial_dir.name.split("__",1)[0]
    #    against manifest dir name[:32].rstrip("_-").
    trial_prefix = view_name[:32].rstrip("_-")
    trial_dir = run_dir / f"{trial_prefix}__a"
    trial_dir.mkdir(parents=True)
    (trial_dir / "result.json").write_text(json.dumps({"reward": 1.0}))  # minimal scored trial

    # 3. Run scoring. Both writers take run_dir and write the artifact as a
    #    side effect (return None) — confirmed at aggregate.py:525 and :603.
    aggregate_summary(run_dir)          # writes run_dir/summary.json
    write_per_trial_outcomes(run_dir)   # writes run_dir/per_trial_outcomes.json

    # 4. Assert identity propagated (AC-1). Mirror the assertion shape already
    #    used in tests/unit/test_task_identity_scoring.py — read the artifacts
    #    from disk and match its row/stratum key layout exactly.
    summary_obj = json.loads((run_dir / "summary.json").read_text())
    trial_row = summary_obj["trials"][0]
    assert trial_row["stratum"]["benchmark_kind"] == "spider2-dbt"
    assert trial_row["stratum"]["benchmark_task_id"] == task_id

    outcomes_obj = json.loads((run_dir / "per_trial_outcomes.json").read_text())
    row = outcomes_obj[0] if isinstance(outcomes_obj, list) else outcomes_obj["trials"][0]
    assert row["benchmark_kind"] == "spider2-dbt"
    assert row["benchmark_task_id"] == task_id
```

Implementer notes:
- Aggregator entry points are confirmed: `aggregate_summary(run_dir: Path) -> None` (`aggregate.py:525`, writes `run_dir/summary.json`) and `write_per_trial_outcomes(run_dir: Path) -> None` (`aggregate.py:603`, writes `run_dir/per_trial_outcomes.json`). `tests/unit/test_task_identity_scoring.py` already calls both — copy its read/assert shape.
- Copy `_make_spider2_spec` and the source-resolution stub verbatim from `tests/unit/test_translate_spider2_dbt.py` so no network fetch occurs; this keeps the test hermetic (no hidden machine dependency).
- If a real result/score reducer needs more trial scaffolding than `result.json` (e.g. `reward.json`), mirror exactly what `test_task_identity_scoring.py` writes for its trials.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_spider2_dbt_scored_run_identity.py -v`
Expected: BEFORE Tasks 1+3 land, FAIL because scoring scans `_razorback/task_views` and misses the manifest under `tasks/`. With Tasks 1+3 applied first (per sequence), this is the proof they integrate — it should PASS.

- [ ] **Step 3: Make it pass**

No new production code beyond Tasks 1+3. If the test fails after those tasks, debug the trial-prefix/view-name matching (`aggregate.py:141` `manifest_path.parent.name[:32].rstrip("_-")` vs `trial_dir.name.split("__",1)[0]`) — adjust the fabricated `trial_dir` name in the test to satisfy the existing matcher; do NOT loosen the production matcher.

- [ ] **Step 4: Run the full identity surface**

Run: `uv run pytest tests/integration/test_spider2_dbt_scored_run_identity.py tests/unit/test_task_identity_scoring.py tests/unit/test_translate_spider2_dbt.py tests/unit/test_translate_harbor_block.py tests/unit/test_task_views_root.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_spider2_dbt_scored_run_identity.py
git commit -m "test(integration): spider2-dbt scored run preserves benchmark identity (AC-1)"
```

---

## Self-Review

**Spec coverage:**
- AC-1 → Task 3 (aggregator) + Task 5 (end-to-end). Covered.
- AC-2 → Task 2 (solver discovery). Covered.
- AC-3 → Task 4 (regression pin) + Task 1's structural argument (generic path materializes no manifest). Covered.
- Design linchpin (direction a/b/c) → recorded with trade-off table; chose (b). Covered.
- Riskiest-contract-first sequencing → Task 5 named as the smallest end-to-end exercise; Tasks 1-3 are its scaffolding, Task 4 is the AC-3 guardrail. Covered.

**Placeholder scan:** No TBD/TODO. The two implementer-judgment points (solver test instance construction in Task 2; exact aggregator entry-point names in Task 5) are flagged with the concrete files to copy from (`test_task_identity_scoring.py`, `test_translate_spider2_dbt.py`) rather than left vague — these are existing tests that already exercise the same functions.

**Type consistency:** `task_views_root(run_dir: Path) -> Path` defined in Task 1, consumed by Tasks 2 and 3 with identical signature. Manifest keys (`benchmark_kind`, `benchmark_task_id`, `child_task_ids`) consistent across producer, manifest module, and both consumers.

**Confirmed during planning:** `aggregate_summary(run_dir: Path) -> None` (`aggregate.py:525`) and `write_per_trial_outcomes(run_dir: Path) -> None` (`aggregate.py:603`) both take `run_dir` and write the artifact as a side effect. The ADE fixture `tests/fixtures/ade_bench/tasks/adebench-fixture-001` used by Task 4 exists. `tests/unit/test_task_identity_scoring.py` helpers are `_write_trial` and `_write_manifest` (Task 3 modifies `_write_manifest`'s output dir).
