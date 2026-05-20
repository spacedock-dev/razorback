# PKG-17 rk run writes run-dir artifacts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After harbor's subprocess exits, `rk run` walks the on-disk run-dir and writes the v2-canonical aggregator artifact set (`manifest.json`, `summary.json`, `events.jsonl`, `per_trial_outcomes.json`, `lock.json`) so `rk runs list/show/cost/diff` work against v2 run-dirs and Goal 1's cost ledger unblocks.

**Architecture:** A new module `src/razorback/runs/aggregate.py` is the single post-harbor aggregator. It reads harbor's job-level `result.json`, per-trial `result.json` files, per-trial events, and per-trial stratum sidecars from the run-dir, then writes the five canonical artifacts. `cli/run.py` calls it once after `_invoke_harbor()` returns (success OR non-zero), guarded by exception handling so an aggregator failure does not mask harbor's exit code. Harbor 0.6.6 already writes `lock.json` itself, so PKG-17 only adds a drift-warning read path in `rk runs show`, not a writer.

**Tech Stack:** Python 3.12, pydantic (existing spec schema), Typer (CLI), pytest, jsonschema (already a transitive dep via pydantic). No new runtime deps.

---

## AC ↔ Task Map

| AC | Tasks | Spec §-cites |
|----|-------|-------------|
| AC-1 manifest.json | T1 (schema + writer), T9 (wire post-harbor) | entity §AC-1 |
| AC-2 summary.json | T2 (aggregator core), T9 | entity §AC-2; `_legacy/run.py:140-153`; `benchmarks/dab/aggregate.py:83-125` |
| AC-3 events.jsonl | T3 (per-trial → top-level concatenator), T9 | entity §AC-3; `_legacy/observers/jsonl.py` |
| AC-4 per_trial_outcomes.json | T4 (sidecar writer reusing T2 input), T9 | entity §AC-4; `benchmarks/dab/aggregate.py:49,122`; `diff/pairing.py:8-16` |
| AC-5 lock.json + drift | T5 (read harbor's lock + drift check) | entity §AC-5; harbor `models/job/lock.py:28` |
| AC-6 rk runs cost honest | T10 (smoke matrix) | entity §AC-6; `runs/cost.py:83-129` |
| AC-7 8 integration tests un-break | T11 (per-test fixup pass) | entity §AC-7 |
| AC-8 no regression in rk score | T12 (rk score smoke against pre-PKG-17 dir + new dir) | entity §AC-8; `score/load.py:44-60` |

T6/T7/T8 are intermediate refactors and the smallest-end-to-end mechanism validation (per "Validating new mechanisms" rule: cheapest contract check first).

---

## File Structure

**New files:**
- `src/razorback/runs/aggregate.py` — post-harbor aggregator. Reads run-dir; writes `manifest.json`, `summary.json`, `events.jsonl`, `per_trial_outcomes.json`. One module, ~250 lines.
- `src/razorback/runs/manifest_schema.json` — JSON schema pin for the manifest envelope, per AC-1 verified-by.
- `src/razorback/runs/lock_drift.py` — `read_lock_with_drift(run_dir, provenance_path)` that returns `(lock_dict, drift_record | None)`. Used by `rk runs show` per AC-5.
- `tests/unit/test_runs_aggregate.py` — unit tests for the aggregator. Fixture run-dirs constructed by an extended `make_run_dir` helper.
- `tests/unit/test_runs_aggregate_events.py` — events.jsonl concatenation behavior (per-trial → top-level + line offsets).
- `tests/unit/test_lock_drift.py` — drift warning when lock fingerprint ≠ provenance fingerprint.
- `tests/fixtures/runs/post_harbor_skeleton/` — minimal on-disk run-dir skeleton fixture (harbor's job-level `result.json` + 2 trial dirs each with `result.json` + `agent/stratum.json` + per-trial `events.jsonl`).

**Modified files:**
- `src/razorback/cli/run.py:285-312` — add `_run_aggregator(run_dir, harbor_rc)` call after `_invoke_harbor()`; keep the existing `_write_provenance_artifacts` call.
- `src/razorback/cli/runs.py:48-58` — `rk runs show` shows the drift record from `read_lock_with_drift` (AC-5).
- `src/razorback/runs/__init__.py` — re-export `write_run_dir_artifacts` from `aggregate.py` for clean import from `cli/run.py`.
- `tests/unit/conftest.py:7-77` — extend `make_run_dir` defaults so the new tests can compose fixture run-dirs from minimal kwargs.
- `tests/integration/test_rk_run_nop.py` — assertions already match the PKG-17 contract; no edits expected (verify only).
- `tests/integration/test_rk_run_bookreview_nop.py` — assertions already match; verify only.
- `tests/integration/test_rk_run_v2_deterministic_smoke.py:60-67` — switch from asserting on harbor's job-level `result.json` to also asserting `summary.json` shape (the PKG-17-canonical path).
- `tests/integration/test_dab_dev_claude_full.py`, `test_dab_workflow_lifecycle.py`, `test_ade_bench_claude_smoke.py`, `test_rk_run_bookreview_claude.py` — gated by env vars (cost-bearing); validate test structure still asserts the PKG-17 artifact set; no behavioral edits expected.
- `tests/integration/test_no_auth_leak_in_run_dir.py`, `test_tools_denied_live.py` — depend on `events.jsonl` existence; validate they pass against PKG-17 writes.

The "8 broken integration tests" of AC-7 are: `test_rk_run_nop.py` (2 tests in file), `test_rk_run_bookreview_nop.py` (2 tests), `test_dab_dev_claude_full.py`, `test_dab_workflow_lifecycle.py`, `test_ade_bench_claude_smoke.py`, `test_rk_run_bookreview_claude.py`. T11 walks each and applies the minimal fix the v2 artifact set requires.

---

## Mechanism Validation First (Rule: "Validating new mechanisms")

**Riskiest contract:** the aggregator reads from the on-disk run-dir, not from `JobResult.trial_results`. The legacy aggregator (`_legacy/run.py:142-153`) consumed Python objects from `harbor.Job.run()`; v2 invokes harbor as a subprocess (`cli/run.py:62-66`) so the aggregator must reconstruct everything from filesystem state.

**Smallest end-to-end exercise:** **T6** — a 30-second pytest run that takes a fixture run-dir on disk (no docker, no harbor invocation), calls `aggregate_run_dir(run_dir)`, and asserts the four written files exist with the right top-level keys. This validates the read-side contract before T9 wires the aggregator into the live `rk run` path.

Only after T6 is green do we (a) wire into `cli/run.py` (T9), (b) run the integration tests (T11), (c) run the smoke matrix (T10).

---

## Tasks

### Task 1: Manifest schema + writer (AC-1)

**Files:**
- Create: `src/razorback/runs/manifest_schema.json`
- Create: `src/razorback/runs/aggregate.py` (skeleton + manifest writer only)
- Test: `tests/unit/test_runs_aggregate.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_runs_aggregate.py`:

```python
# ABOUTME: Unit tests for src/razorback/runs/aggregate.py (PKG-17).
# ABOUTME: AC-1: manifest.json schema; AC-2: summary aggregator; AC-3: events concat.

import json
from pathlib import Path

import pytest

from razorback.runs.aggregate import (
    MANIFEST_SCHEMA_VERSION,
    write_manifest,
)


def test_write_manifest_schema_fields_present(tmp_path: Path):
    run_dir = tmp_path / "exp" / "job_abc"
    run_dir.mkdir(parents=True)
    write_manifest(
        run_dir,
        spec_path=Path("examples/specs/pkg13-bookreview-claude-harbor-dab-n3.yaml"),
        frozen_spec_hash="deadbeef" * 8,
        provenance_hash="cafef00d" * 8,
        harbor_job_name="job_abc",
        n_trials_total=3,
        n_trials_completed=3,
        n_trials_errored=0,
        per_trial_paths=["bookreview-q1__a", "bookreview-q2__b", "bookreview-q3__c"],
        benchmark_kind="harbor_dab",
    )
    payload = json.loads((run_dir / "manifest.json").read_text())
    assert payload["run_dir_version"] == MANIFEST_SCHEMA_VERSION
    assert payload["experiment"] == "exp"
    assert payload["job_name"] == "job_abc"
    assert payload["spec_path"].endswith("pkg13-bookreview-claude-harbor-dab-n3.yaml")
    assert payload["frozen_spec_hash"] == "deadbeef" * 8
    assert payload["provenance_hash"] == "cafef00d" * 8
    assert payload["harbor_job_name"] == "job_abc"
    assert payload["n_trials_total"] == 3
    assert payload["n_trials_completed"] == 3
    assert payload["n_trials_errored"] == 0
    assert payload["per_trial_paths"] == [
        "bookreview-q1__a",
        "bookreview-q2__b",
        "bookreview-q3__c",
    ]
    assert payload["benchmark_kind"] == "harbor_dab"
    assert payload["created_at"].endswith("Z") or "+" in payload["created_at"]


def test_write_manifest_validates_against_schema(tmp_path: Path):
    """The written manifest validates against manifest_schema.json (AC-1 verified-by)."""
    import jsonschema

    schema_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "razorback"
        / "runs"
        / "manifest_schema.json"
    )
    schema = json.loads(schema_path.read_text())

    run_dir = tmp_path / "exp" / "job_abc"
    run_dir.mkdir(parents=True)
    write_manifest(
        run_dir,
        spec_path=Path("/spec.yaml"),
        frozen_spec_hash="a" * 64,
        provenance_hash="b" * 64,
        harbor_job_name="job_abc",
        n_trials_total=1,
        n_trials_completed=1,
        n_trials_errored=0,
        per_trial_paths=["t1"],
        benchmark_kind="nop",
    )
    payload = json.loads((run_dir / "manifest.json").read_text())
    jsonschema.validate(payload, schema)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_runs_aggregate.py -v`
Expected: `ModuleNotFoundError: No module named 'razorback.runs.aggregate'`.

- [ ] **Step 3: Write minimal implementation — manifest_schema.json**

Create `src/razorback/runs/manifest_schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "razorback run-dir manifest (PKG-17)",
  "type": "object",
  "additionalProperties": true,
  "required": [
    "run_dir_version",
    "experiment",
    "job_name",
    "created_at",
    "spec_path",
    "frozen_spec_hash",
    "provenance_hash",
    "harbor_job_name",
    "n_trials_total",
    "n_trials_completed",
    "n_trials_errored",
    "per_trial_paths"
  ],
  "properties": {
    "run_dir_version": {"const": 1},
    "experiment": {"type": "string"},
    "job_name": {"type": "string"},
    "created_at": {"type": "string"},
    "spec_path": {"type": "string"},
    "frozen_spec_hash": {"type": "string", "minLength": 64, "maxLength": 64},
    "provenance_hash": {"type": "string", "minLength": 64, "maxLength": 64},
    "harbor_job_name": {"type": "string"},
    "n_trials_total": {"type": "integer", "minimum": 0},
    "n_trials_completed": {"type": "integer", "minimum": 0},
    "n_trials_errored": {"type": "integer", "minimum": 0},
    "per_trial_paths": {"type": "array", "items": {"type": "string"}},
    "benchmark_kind": {"type": ["string", "null"]}
  }
}
```

- [ ] **Step 4: Write minimal implementation — aggregate.py skeleton + write_manifest**

Create `src/razorback/runs/aggregate.py`:

```python
# ABOUTME: PKG-17 post-harbor aggregator. Writes manifest/summary/events/per_trial_outcomes.
# ABOUTME: Reads run-dir filesystem state; no JobResult dependency (harbor runs as subprocess).

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

MANIFEST_SCHEMA_VERSION = 1


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_manifest(
    run_dir: Path,
    *,
    spec_path: Path,
    frozen_spec_hash: str,
    provenance_hash: str,
    harbor_job_name: str,
    n_trials_total: int,
    n_trials_completed: int,
    n_trials_errored: int,
    per_trial_paths: list[str],
    benchmark_kind: str | None,
) -> None:
    """AC-1: write <run_dir>/manifest.json.

    Carries enough to reconstruct provenance + per-trial discovery. The
    experiment / job_name fields are derived from the run-dir path so
    consumers don't need to re-parse the frozen spec to enumerate runs.
    """
    payload = {
        "run_dir_version": MANIFEST_SCHEMA_VERSION,
        "experiment": run_dir.parent.name,
        "job_name": run_dir.name,
        "created_at": _utcnow_iso(),
        "spec_path": str(spec_path),
        "frozen_spec_hash": frozen_spec_hash,
        "provenance_hash": provenance_hash,
        "harbor_job_name": harbor_job_name,
        "n_trials_total": n_trials_total,
        "n_trials_completed": n_trials_completed,
        "n_trials_errored": n_trials_errored,
        "per_trial_paths": per_trial_paths,
        "benchmark_kind": benchmark_kind,
    }
    (run_dir / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_runs_aggregate.py -v`
Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/razorback/runs/aggregate.py src/razorback/runs/manifest_schema.json tests/unit/test_runs_aggregate.py
git commit -m "PKG-17 T1: manifest.json schema + writer (AC-1)"
```

---

### Task 2: Summary aggregator core — per-trial rewards + stratified pass@1 (AC-2)

**Files:**
- Modify: `src/razorback/runs/aggregate.py` (add `aggregate_summary`)
- Create: `tests/fixtures/runs/post_harbor_skeleton/` (fixture skeleton)
- Test: `tests/unit/test_runs_aggregate.py` (append)

**Reference (per entity §test plan):**
- `_legacy/run.py:140-153` shows the in-process DAB/ade-bench branching.
- `benchmarks/dab/aggregate.py:83-125` is the in-process aggregator. We re-derive the same logic but read inputs from disk instead of `JobResult.trial_results`.
- `score/load.py:44-60` shows the right discriminator between "this is a trial dir" vs other top-level files.

- [ ] **Step 1: Build the fixture skeleton**

Run these commands:

```bash
mkdir -p tests/fixtures/runs/post_harbor_skeleton/{bookreview-q1__a,bookreview-q2__b,bookreview-q3__c}/agent
mkdir -p tests/fixtures/runs/post_harbor_skeleton/tasks/bookreview/{bookreview-q1,bookreview-q2,bookreview-q3}
```

Write `tests/fixtures/runs/post_harbor_skeleton/result.json`:

```json
{
  "id": "fixture-job",
  "started_at": "2026-05-20T10:00:00",
  "finished_at": "2026-05-20T10:05:00",
  "n_total_trials": 3,
  "stats": {
    "n_completed_trials": 2,
    "n_errored_trials": 1,
    "evals": {
      "claude-cli__claude-opus-4-5__adhoc": {
        "reward_stats": {"reward": {"1.0": ["bookreview-q1__a"], "0.0": ["bookreview-q2__b"]}},
        "exception_stats": {}
      }
    },
    "cost_usd": null
  }
}
```

Write each per-trial `result.json`. For `bookreview-q1__a/result.json`:

```json
{
  "trial_name": "bookreview-q1__a",
  "task_name": "razorback/bookreview-q1",
  "verifier_result": {"rewards": {"reward": 1.0}},
  "exception_info": null
}
```

For `bookreview-q2__b/result.json`:

```json
{
  "trial_name": "bookreview-q2__b",
  "task_name": "razorback/bookreview-q2",
  "verifier_result": {"rewards": {"reward": 0.0}},
  "exception_info": null
}
```

For `bookreview-q3__c/result.json` (errored):

```json
{
  "trial_name": "bookreview-q3__c",
  "task_name": "razorback/bookreview-q3",
  "verifier_result": null,
  "exception_info": {"exception_type": "AgentTimeoutError"}
}
```

Per-trial `agent/stratum.json` (one per trial):

`bookreview-q1__a/agent/stratum.json`:

```json
{"stratum": {"dataset": "bookreview", "query_id": 1}}
```

(repeat with `query_id: 2` / `3` for the other two trials).

- [ ] **Step 2: Write the failing test**

Append to `tests/unit/test_runs_aggregate.py`:

```python
from razorback.runs.aggregate import aggregate_summary

FIXTURE_RUN = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "runs"
    / "post_harbor_skeleton"
)


def test_aggregate_summary_per_trial_rewards_and_stratified(tmp_path: Path):
    work = tmp_path / "exp" / "job"
    work.mkdir(parents=True)
    # Copy fixture skeleton into work-dir.
    import shutil
    for child in FIXTURE_RUN.iterdir():
        if child.is_dir():
            shutil.copytree(child, work / child.name)
        else:
            shutil.copy(child, work / child.name)

    aggregate_summary(work)
    summary = json.loads((work / "summary.json").read_text())

    # AC-2 row shape: per-trial (trial_id, reward, cost_usd, wall_seconds, error_reason).
    trial_ids = {t["trial_id"] for t in summary["trials"]}
    assert trial_ids == {"bookreview-q1__a", "bookreview-q2__b", "bookreview-q3__c"}
    by_id = {t["trial_id"]: t for t in summary["trials"]}
    assert by_id["bookreview-q1__a"]["reward"] == 1.0
    assert by_id["bookreview-q2__b"]["reward"] == 0.0
    assert by_id["bookreview-q3__c"]["reward"] is None
    assert by_id["bookreview-q3__c"]["error_reason"] == "AgentTimeoutError"

    # AC-2 aggregate counts.
    assert summary["n_trials_total"] == 3
    assert summary["n_trials_completed"] == 2
    assert summary["n_trials_errored"] == 1

    # AC-2 per-stratum pass@1 (no Wilson CI — that's rk score's job).
    assert summary["datasets"]["bookreview"]["dataset_pass_at_1"] == 0.5  # 1 of 2 completed
    assert summary["stratified_pass_at_1"] == 0.5

    # AC-6 cost rollup: null per the fixture's subscription-auth shape.
    assert summary["cost_usd"] is None
    assert summary["summary_version"] == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_runs_aggregate.py::test_aggregate_summary_per_trial_rewards_and_stratified -v`
Expected: `ImportError: cannot import name 'aggregate_summary'`.

- [ ] **Step 4: Implement `aggregate_summary`**

Append to `src/razorback/runs/aggregate.py`:

```python
SUMMARY_VERSION = 1

_NON_TRIAL_TOP_LEVEL = {
    "manifest.json",
    "summary.json",
    "per_trial_outcomes.json",
    "events.jsonl",
    "result.json",
    "lock.json",
    "config.json",
    "job.log",
    "spec.frozen.yaml",
    "spec.frozen.prior.yaml",
    "provenance.yaml",
    "_job_config.yaml",
    "tasks",
    ".harbor-home",
    "crash.json",
}


def _iter_trial_dirs(run_dir: Path) -> list[Path]:
    """Trial dirs are sibling subdirs of run_dir, excluding scaffolding."""
    out: list[Path] = []
    for child in sorted(run_dir.iterdir()):
        if not child.is_dir() or child.name in _NON_TRIAL_TOP_LEVEL:
            continue
        if not (child / "result.json").exists():
            continue
        out.append(child)
    return out


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _resolve_stratum(trial_dir: Path) -> dict | None:
    """Reuse the same precedence rk score/load.py:110-146 walks."""
    candidates = [
        trial_dir / "agent" / "stratum.json",
        trial_dir / "logs" / "verifier" / "stratum.json",
    ]
    steps_root = trial_dir / "steps"
    if steps_root.is_dir():
        for step_dir in sorted(steps_root.iterdir()):
            candidates.append(step_dir / "verifier" / "stratum.json")
    for candidate in candidates:
        payload = _read_json(candidate)
        if payload is not None:
            return payload.get("stratum")
    return None


def _read_trial(trial_dir: Path) -> dict:
    """Extract one trial's row for summary.json + per_trial_outcomes.json."""
    result = _read_json(trial_dir / "result.json") or {}
    exception_info = result.get("exception_info")
    verifier = result.get("verifier_result")
    stratum = _resolve_stratum(trial_dir) or {}

    if exception_info is not None:
        return {
            "trial_id": trial_dir.name,
            "reward": None,
            "cost_usd": None,
            "wall_seconds": None,
            "error_reason": exception_info.get("exception_type"),
            "stratum": stratum,
        }

    reward = None
    if verifier is not None:
        rewards = verifier.get("rewards") or {}
        if "reward" in rewards:
            reward = float(rewards["reward"])
        elif rewards:
            reward = float(next(iter(rewards.values())))

    return {
        "trial_id": trial_dir.name,
        "reward": reward,
        "cost_usd": _trial_cost(trial_dir),
        "wall_seconds": None,
        "error_reason": None,
        "stratum": stratum,
    }


def _trial_cost(trial_dir: Path) -> float | None:
    """Sum per-step agent_result.cost_usd; mirror runs/cost.py:58-78."""
    result = _read_json(trial_dir / "result.json") or {}
    steps = result.get("step_results")
    if not isinstance(steps, list):
        return None
    costs: list[float] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        agent = step.get("agent_result")
        if not isinstance(agent, dict):
            continue
        value = agent.get("cost_usd")
        if value is not None:
            costs.append(float(value))
    return sum(costs) if costs else None


def _stratified_pass_at_1(trials: list[dict]) -> tuple[dict, float | None]:
    """Group completed trials by stratum.dataset; pass@1 = mean over datasets of dataset mean.

    Mirrors benchmarks/dab/aggregate.py:_build_summary. Returns
    (datasets_block, stratified_pass_at_1_or_None).
    """
    completed = [t for t in trials if t["error_reason"] is None and t["reward"] is not None]
    if not completed:
        return ({}, None)

    by_ds_q: dict[tuple[str, int | None], list[float]] = {}
    for t in completed:
        ds = (t["stratum"] or {}).get("dataset", "default")
        qid = (t["stratum"] or {}).get("query_id")
        by_ds_q.setdefault((str(ds), qid), []).append(float(t["reward"]))

    datasets: dict[str, dict] = {}
    for (ds, qid), rewards in by_ds_q.items():
        n = len(rewards)
        c = sum(1 for r in rewards if r >= 1.0)
        entry = datasets.setdefault(ds, {"dataset_pass_at_1": 0.0, "n_queries": 0, "queries": []})
        entry["queries"].append(
            {"query_id": qid, "n_trials": n, "n_correct": c, "pass_at_1": (c / n) if n else 0.0}
        )
    for ds, entry in datasets.items():
        entry["queries"].sort(key=lambda q: (q["query_id"] is None, q["query_id"]))
        entry["n_queries"] = len(entry["queries"])
        entry["dataset_pass_at_1"] = sum(q["pass_at_1"] for q in entry["queries"]) / entry["n_queries"]

    stratified = sum(d["dataset_pass_at_1"] for d in datasets.values()) / len(datasets)
    return (dict(sorted(datasets.items())), stratified)


def _job_cost_usd(run_dir: Path) -> float | None:
    """Harbor's job-level cost; falls back to per-trial sum."""
    result = _read_json(run_dir / "result.json") or {}
    stats = result.get("stats") or {}
    value = stats.get("cost_usd")
    if value is not None:
        return float(value)
    # Fall back: sum per-trial costs.
    totals: list[float] = []
    for child in _iter_trial_dirs(run_dir):
        c = _trial_cost(child)
        if c is not None:
            totals.append(c)
    return sum(totals) if totals else None


def aggregate_summary(run_dir: Path) -> None:
    """AC-2: write <run_dir>/summary.json with per-trial rows + stratified pass@1."""
    trials = [_read_trial(td) for td in _iter_trial_dirs(run_dir)]
    n_total = len(trials)
    n_errored = sum(1 for t in trials if t["error_reason"] is not None)
    n_completed = n_total - n_errored

    datasets, stratified = _stratified_pass_at_1(trials)

    summary = {
        "summary_version": SUMMARY_VERSION,
        "n_trials_total": n_total,
        "n_trials_completed": n_completed,
        "n_trials_errored": n_errored,
        "stratified_pass_at_1": stratified,
        "datasets": datasets,
        "trials": [
            {
                "trial_id": t["trial_id"],
                "reward": t["reward"],
                "cost_usd": t["cost_usd"],
                "wall_seconds": t["wall_seconds"],
                "error_reason": t["error_reason"],
            }
            for t in trials
        ],
        "cost_usd": _job_cost_usd(run_dir),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_runs_aggregate.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/razorback/runs/aggregate.py tests/fixtures/runs/post_harbor_skeleton/ tests/unit/test_runs_aggregate.py
git commit -m "PKG-17 T2: aggregate_summary core + post_harbor_skeleton fixture (AC-2)"
```

---

### Task 3: events.jsonl concatenation (AC-3)

**Files:**
- Modify: `src/razorback/runs/aggregate.py`
- Modify: `tests/fixtures/runs/post_harbor_skeleton/` (add per-trial events.jsonl)
- Test: `tests/unit/test_runs_aggregate_events.py`

- [ ] **Step 1: Add per-trial events.jsonl fixtures**

Write `tests/fixtures/runs/post_harbor_skeleton/bookreview-q1__a/events.jsonl`:

```
{"event": "start", "timestamp": "2026-05-20T10:00:00Z"}
{"event": "agent_start", "timestamp": "2026-05-20T10:00:01Z"}
{"event": "end", "timestamp": "2026-05-20T10:01:00Z"}
```

Write `tests/fixtures/runs/post_harbor_skeleton/bookreview-q2__b/events.jsonl`:

```
{"event": "start", "timestamp": "2026-05-20T10:01:01Z"}
{"event": "end", "timestamp": "2026-05-20T10:02:00Z"}
```

Skip writing one for `bookreview-q3__c` (the errored trial may legitimately have no events.jsonl; the aggregator must tolerate that).

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_runs_aggregate_events.py`:

```python
# ABOUTME: PKG-17 AC-3 — top-level events.jsonl is the per-trial concatenation
# ABOUTME: with each line carrying {trial_id, line_offset} for cross-trial correlation.

import json
import shutil
from pathlib import Path

from razorback.runs.aggregate import concatenate_events

FIXTURE_RUN = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "runs"
    / "post_harbor_skeleton"
)


def test_concatenate_events_writes_top_level_with_trial_prefix(tmp_path):
    work = tmp_path / "exp" / "job"
    work.mkdir(parents=True)
    for child in FIXTURE_RUN.iterdir():
        if child.is_dir():
            shutil.copytree(child, work / child.name)
        else:
            shutil.copy(child, work / child.name)

    concatenate_events(work)

    top = (work / "events.jsonl").read_text().splitlines()
    # Q1 has 3 events; Q2 has 2; Q3 has none. Order is by trial_id sort then per-trial line.
    assert len(top) == 5

    parsed = [json.loads(l) for l in top]
    # Each row carries the prefix keys.
    for row in parsed:
        assert "trial_id" in row
        assert "line_offset" in row

    # Q1's first row corresponds to its first per-trial line.
    q1_rows = [r for r in parsed if r["trial_id"] == "bookreview-q1__a"]
    assert q1_rows[0]["event"] == "start"
    assert q1_rows[0]["line_offset"] == 0
    assert q1_rows[2]["event"] == "end"
    assert q1_rows[2]["line_offset"] == 2


def test_concatenate_events_tolerates_missing_per_trial_file(tmp_path):
    work = tmp_path / "exp" / "job"
    work.mkdir(parents=True)
    for child in FIXTURE_RUN.iterdir():
        if child.is_dir():
            shutil.copytree(child, work / child.name)
        else:
            shutil.copy(child, work / child.name)

    concatenate_events(work)
    # Q3 has no per-trial events.jsonl; absence must not crash or contribute lines.
    parsed = [json.loads(l) for l in (work / "events.jsonl").read_text().splitlines()]
    assert not any(r["trial_id"] == "bookreview-q3__c" for r in parsed)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_runs_aggregate_events.py -v`
Expected: `ImportError: cannot import name 'concatenate_events'`.

- [ ] **Step 4: Implement `concatenate_events`**

Append to `src/razorback/runs/aggregate.py`:

```python
def concatenate_events(run_dir: Path) -> None:
    """AC-3: write <run_dir>/events.jsonl, the per-trial concatenation.

    Each line carries `{trial_id, line_offset}` so `rk audit` can correlate a
    finding back to the per-trial events.jsonl. Trials with no per-trial
    events.jsonl contribute nothing (errored-before-publisher trials are valid).
    """
    out_lines: list[str] = []
    for trial_dir in _iter_trial_dirs(run_dir):
        per_trial = trial_dir / "events.jsonl"
        if not per_trial.exists():
            continue
        try:
            text = per_trial.read_text(encoding="utf-8")
        except OSError:
            continue
        for offset, raw in enumerate(text.splitlines()):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                # Corrupt per-trial line — preserve as a raw record with the prefix.
                payload = {"raw": stripped}
            payload = {"trial_id": trial_dir.name, "line_offset": offset, **payload}
            out_lines.append(json.dumps(payload))
    (run_dir / "events.jsonl").write_text(
        ("\n".join(out_lines) + "\n") if out_lines else ""
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_runs_aggregate_events.py -v`
Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/razorback/runs/aggregate.py tests/fixtures/runs/post_harbor_skeleton/ tests/unit/test_runs_aggregate_events.py
git commit -m "PKG-17 T3: events.jsonl concatenation with trial prefix (AC-3)"
```

---

### Task 4: per_trial_outcomes.json writer (AC-4)

**Files:**
- Modify: `src/razorback/runs/aggregate.py`
- Test: `tests/unit/test_runs_aggregate.py` (append)

The diff-pairing consumer is `diff/pairing.py:8-16`, which expects:

```json
{"outcomes_version": 1, "trials": [{"dataset": str, "query_id": int, "trial_index": int, "reward": float}]}
```

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_runs_aggregate.py`:

```python
from razorback.runs.aggregate import write_per_trial_outcomes
from razorback.diff.pairing import load_run_outcomes


def test_write_per_trial_outcomes_matches_pairing_loader_contract(tmp_path: Path):
    import shutil
    work = tmp_path / "exp" / "job"
    work.mkdir(parents=True)
    for child in FIXTURE_RUN.iterdir():
        if child.is_dir():
            shutil.copytree(child, work / child.name)
        else:
            shutil.copy(child, work / child.name)

    write_per_trial_outcomes(work)

    # AC-4: diff/pairing.load_run_outcomes round-trips without raising.
    trials = load_run_outcomes(work)
    by_q = {(t["dataset"], t["query_id"]): t for t in trials}
    # Q1 (reward=1.0) + Q2 (reward=0.0) are completed; Q3 errored → reward=0.0 row.
    assert by_q[("bookreview", 1)]["reward"] == 1.0
    assert by_q[("bookreview", 2)]["reward"] == 0.0
    # Errored trials get reward=0.0 per legacy aggregate_job_result (legacy line 102-106).
    assert by_q[("bookreview", 3)]["reward"] == 0.0
    # trial_index defaults to 0 when only one trial per (dataset, query).
    assert all(t["trial_index"] == 0 for t in trials)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_runs_aggregate.py::test_write_per_trial_outcomes_matches_pairing_loader_contract -v`
Expected: `ImportError: cannot import name 'write_per_trial_outcomes'`.

- [ ] **Step 3: Implement `write_per_trial_outcomes`**

Append to `src/razorback/runs/aggregate.py`:

```python
OUTCOMES_VERSION = 1


def write_per_trial_outcomes(run_dir: Path) -> None:
    """AC-4: write <run_dir>/per_trial_outcomes.json for rk runs diff.

    Errored trials enter the outcomes table with reward=0.0 (parity with
    benchmarks/dab/aggregate.py:104 — `if verifier_result is None: reward = 0.0`).
    rk runs diff is a pairwise comparison and needs every key on both arms.
    """
    counter: dict[tuple[str, int | None], int] = {}
    rows: list[dict] = []
    for trial_dir in _iter_trial_dirs(run_dir):
        info = _read_trial(trial_dir)
        stratum = info.get("stratum") or {}
        dataset = str(stratum.get("dataset", "default"))
        query_id = stratum.get("query_id")
        key = (dataset, query_id)
        idx = counter.get(key, 0)
        counter[key] = idx + 1
        reward = info["reward"] if info["reward"] is not None else 0.0
        rows.append(
            {
                "dataset": dataset,
                "query_id": query_id,
                "trial_index": idx,
                "trial_name": trial_dir.name,
                "reward": float(reward),
            }
        )
    (run_dir / "per_trial_outcomes.json").write_text(
        json.dumps({"outcomes_version": OUTCOMES_VERSION, "trials": rows}, indent=2) + "\n"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_runs_aggregate.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/runs/aggregate.py tests/unit/test_runs_aggregate.py
git commit -m "PKG-17 T4: per_trial_outcomes.json writer (AC-4)"
```

---

### Task 5: lock.json drift surface for `rk runs show` (AC-5)

Harbor 0.6.6 writes `lock.json` itself at job start (verified in
`.venv/.../harbor/models/job/lock.py:28` + `harbor/job.py:562-578`), so PKG-17
does NOT write the file. AC-5's requirement is "lock.json's fingerprint
disagrees with provenance.yaml's → `rk runs show` flags the drift visibly."
Implement that drift READ path here.

**Files:**
- Create: `src/razorback/runs/lock_drift.py`
- Test: `tests/unit/test_lock_drift.py`
- Modify: `src/razorback/cli/runs.py:48-58` (use lock_drift in `show_command`)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_lock_drift.py`:

```python
# ABOUTME: PKG-17 AC-5 — lock.json drift surface for rk runs show.

import json
from pathlib import Path

from razorback.runs.lock_drift import compute_drift


def _write_lock(run_dir: Path, harbor_version: str) -> None:
    (run_dir / "lock.json").write_text(json.dumps({
        "schema_version": 1,
        "created_at": "2026-05-20T10:00:00Z",
        "harbor": {"version": harbor_version, "is_editable": False},
    }))


def _write_provenance(run_dir: Path, harbor_version: str) -> None:
    (run_dir / "provenance.yaml").write_text(
        f"harbor_version: {harbor_version}\nmodel_resolved_version: claude-opus-4-5-20250101\n"
    )


def test_compute_drift_returns_none_when_fingerprints_match(tmp_path: Path):
    run_dir = tmp_path / "exp" / "job"
    run_dir.mkdir(parents=True)
    _write_lock(run_dir, "0.6.6")
    _write_provenance(run_dir, "0.6.6")
    assert compute_drift(run_dir) is None


def test_compute_drift_returns_record_when_harbor_version_disagrees(tmp_path: Path):
    run_dir = tmp_path / "exp" / "job"
    run_dir.mkdir(parents=True)
    _write_lock(run_dir, "0.6.7")
    _write_provenance(run_dir, "0.6.6")
    drift = compute_drift(run_dir)
    assert drift is not None
    assert drift["field"] == "harbor_version"
    assert drift["provenance"] == "0.6.6"
    assert drift["lock"] == "0.6.7"


def test_compute_drift_tolerates_missing_lock_json(tmp_path: Path):
    """harbor>=0.7 may relocate lock.json; absent file → drift=None, not crash."""
    run_dir = tmp_path / "exp" / "job"
    run_dir.mkdir(parents=True)
    _write_provenance(run_dir, "0.6.6")
    assert compute_drift(run_dir) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_lock_drift.py -v`
Expected: `ModuleNotFoundError: No module named 'razorback.runs.lock_drift'`.

- [ ] **Step 3: Implement `lock_drift.py`**

Create `src/razorback/runs/lock_drift.py`:

```python
# ABOUTME: PKG-17 AC-5 — read harbor's lock.json + diff against provenance.yaml.
# ABOUTME: Surface drift records for rk runs show; harbor writes lock.json itself.

from __future__ import annotations

import json
from pathlib import Path

import yaml


def compute_drift(run_dir: Path) -> dict | None:
    """Return a drift record when the lock fingerprint disagrees with provenance.

    Today this checks `harbor.version` against `provenance.yaml::harbor_version`.
    Future fields (image_digest, agent_cli_hash, model_resolved_version) follow
    the same pattern; expand the comparison map below when freeze-time pinning
    lands runtime resolution.
    """
    lock_path = run_dir / "lock.json"
    prov_path = run_dir / "provenance.yaml"
    if not lock_path.exists() or not prov_path.exists():
        return None

    try:
        lock = json.loads(lock_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    try:
        prov = yaml.safe_load(prov_path.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return None

    lock_harbor = (lock.get("harbor") or {}).get("version")
    prov_harbor = prov.get("harbor_version")
    if prov_harbor is not None and lock_harbor is not None and prov_harbor != lock_harbor:
        return {
            "field": "harbor_version",
            "provenance": prov_harbor,
            "lock": lock_harbor,
        }
    return None
```

- [ ] **Step 4: Wire into `rk runs show`**

Modify `src/razorback/cli/runs.py:48-58` `show_command`. Replace the function body with:

```python
@runs_app.command("show")
def show_command(
    run_dir: Path = typer.Argument(...),
) -> None:
    """Show one run-dir's manifest envelope + summary + lock drift. §3.2."""
    try:
        payload = read_run_dir(run_dir)
    except FileNotFoundError as exc:
        typer.echo(f"run-dir missing required input: {exc}", err=True)
        raise typer.Exit(ExitCode.USAGE)
    from razorback.runs.lock_drift import compute_drift

    drift = compute_drift(run_dir)
    if drift is not None:
        payload["lock_drift"] = drift
    typer.echo(json.dumps(payload, indent=2))
```

- [ ] **Step 5: Add a `rk runs show` CLI test for the drift surface**

Append to `tests/unit/test_lock_drift.py`:

```python
def test_rk_runs_show_renders_drift_record(tmp_path: Path):
    """End-to-end: rk runs show <run-dir> emits lock_drift in JSON output."""
    from typer.testing import CliRunner
    from razorback.cli.runs import runs_app

    run_dir = tmp_path / "exp" / "job"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(json.dumps({
        "run_dir_version": 1,
        "experiment": "exp",
        "job_name": "job",
        "created_at": "2026-05-20T10:00:00Z",
    }))
    (run_dir / "summary.json").write_text(json.dumps({"summary_version": 1}))
    _write_lock(run_dir, "0.6.7")
    _write_provenance(run_dir, "0.6.6")

    result = CliRunner().invoke(runs_app, ["show", str(run_dir)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["lock_drift"]["field"] == "harbor_version"
```

- [ ] **Step 6: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_lock_drift.py -v`
Expected: 4 PASS.

- [ ] **Step 7: Commit**

```bash
git add src/razorback/runs/lock_drift.py src/razorback/cli/runs.py tests/unit/test_lock_drift.py
git commit -m "PKG-17 T5: lock.json drift surface for rk runs show (AC-5)"
```

---

### Task 6: Mechanism validation — aggregate end-to-end against fixture (riskiest contract check first)

**Files:**
- Modify: `tests/unit/test_runs_aggregate.py`

This is the smallest end-to-end exercise of the riskiest contract: the
aggregator reads the on-disk run-dir (not `JobResult.trial_results`) and
produces all four PKG-17 artifacts in one call. If this check fails, T9
(the wiring task) is invalidated; we want to know now.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_runs_aggregate.py`:

```python
from razorback.runs.aggregate import aggregate_run_dir


def test_aggregate_run_dir_writes_all_four_artifacts(tmp_path: Path):
    """One call after harbor exits → manifest + summary + events + per_trial_outcomes."""
    import shutil
    work = tmp_path / "exp" / "job"
    work.mkdir(parents=True)
    for child in FIXTURE_RUN.iterdir():
        if child.is_dir():
            shutil.copytree(child, work / child.name)
        else:
            shutil.copy(child, work / child.name)
    # Pretend cli/run.py already wrote spec.frozen.yaml + provenance.yaml.
    (work / "spec.frozen.yaml").write_text("version: 1\nexperiment: exp\n")
    (work / "provenance.yaml").write_text("harbor_version: 0.6.6\n")

    aggregate_run_dir(
        work,
        spec_path=Path("/fixtures/spec.yaml"),
        frozen_spec_hash="a" * 64,
        provenance_hash="b" * 64,
        harbor_job_name="job",
        benchmark_kind="dab",
    )

    for name in ("manifest.json", "summary.json", "events.jsonl", "per_trial_outcomes.json"):
        assert (work / name).is_file(), f"missing {name}"

    manifest = json.loads((work / "manifest.json").read_text())
    assert manifest["n_trials_total"] == 3
    assert manifest["n_trials_completed"] == 2
    assert manifest["n_trials_errored"] == 1
    assert manifest["per_trial_paths"] == sorted(manifest["per_trial_paths"])


def test_aggregate_run_dir_idempotent(tmp_path: Path):
    """Calling aggregate_run_dir twice yields byte-identical outputs except created_at."""
    import shutil
    work = tmp_path / "exp" / "job"
    work.mkdir(parents=True)
    for child in FIXTURE_RUN.iterdir():
        if child.is_dir():
            shutil.copytree(child, work / child.name)
        else:
            shutil.copy(child, work / child.name)
    (work / "spec.frozen.yaml").write_text("version: 1\nexperiment: exp\n")
    (work / "provenance.yaml").write_text("harbor_version: 0.6.6\n")

    aggregate_run_dir(work, spec_path=Path("/x"), frozen_spec_hash="a"*64,
                     provenance_hash="b"*64, harbor_job_name="job", benchmark_kind="dab")
    first_summary = (work / "summary.json").read_text()
    first_outcomes = (work / "per_trial_outcomes.json").read_text()
    first_events = (work / "events.jsonl").read_text()

    aggregate_run_dir(work, spec_path=Path("/x"), frozen_spec_hash="a"*64,
                     provenance_hash="b"*64, harbor_job_name="job", benchmark_kind="dab")
    assert (work / "summary.json").read_text() == first_summary
    assert (work / "per_trial_outcomes.json").read_text() == first_outcomes
    assert (work / "events.jsonl").read_text() == first_events
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_runs_aggregate.py -v`
Expected: `ImportError: cannot import name 'aggregate_run_dir'`.

- [ ] **Step 3: Implement `aggregate_run_dir`**

Append to `src/razorback/runs/aggregate.py`:

```python
def aggregate_run_dir(
    run_dir: Path,
    *,
    spec_path: Path,
    frozen_spec_hash: str,
    provenance_hash: str,
    harbor_job_name: str,
    benchmark_kind: str | None,
) -> None:
    """Single post-harbor entrypoint. Writes the four canonical PKG-17 artifacts.

    Idempotent for summary / events / per_trial_outcomes (deterministic inputs);
    manifest.created_at re-stamps on each call by design.
    """
    trial_dirs = _iter_trial_dirs(run_dir)
    n_total = len(trial_dirs)
    n_errored = 0
    for td in trial_dirs:
        result = _read_json(td / "result.json") or {}
        if result.get("exception_info") is not None or result.get("verifier_result") is None:
            n_errored += 1
    n_completed = n_total - n_errored

    write_manifest(
        run_dir,
        spec_path=spec_path,
        frozen_spec_hash=frozen_spec_hash,
        provenance_hash=provenance_hash,
        harbor_job_name=harbor_job_name,
        n_trials_total=n_total,
        n_trials_completed=n_completed,
        n_trials_errored=n_errored,
        per_trial_paths=sorted(td.name for td in trial_dirs),
        benchmark_kind=benchmark_kind,
    )
    aggregate_summary(run_dir)
    concatenate_events(run_dir)
    write_per_trial_outcomes(run_dir)
```

- [ ] **Step 4: Re-export for clean imports**

Modify `src/razorback/runs/__init__.py` (overwrite contents):

```python
# ABOUTME: razorback.runs package — read-side helpers + PKG-17 post-harbor aggregator.
# ABOUTME: Backs the rk runs list/show/cost/diff CLI subcommands.

from razorback.runs.aggregate import aggregate_run_dir

__all__ = ["aggregate_run_dir"]
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_runs_aggregate.py tests/unit/test_runs_aggregate_events.py -v`
Expected: 6 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/razorback/runs/aggregate.py src/razorback/runs/__init__.py tests/unit/test_runs_aggregate.py
git commit -m "PKG-17 T6: aggregate_run_dir top-level entrypoint (mechanism check)"
```

---

### Task 7: frozen_spec_hash + provenance_hash helpers

`aggregate_run_dir` needs both hashes from `cli/run.py`. The frozen-spec hash
is already computed there as `derive_job_name`; the provenance hash is not.
Add a small helper so `cli/run.py` can pass them in cleanly.

**Files:**
- Modify: `src/razorback/runs/aggregate.py`
- Test: `tests/unit/test_runs_aggregate.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_runs_aggregate.py`:

```python
from razorback.runs.aggregate import compute_provenance_hash


def test_compute_provenance_hash_is_stable_for_identical_input(tmp_path: Path):
    p = tmp_path / "provenance.yaml"
    p.write_text("harbor_version: 0.6.6\nmodel_resolved_version: claude-opus-4-5\n")
    h1 = compute_provenance_hash(p)
    h2 = compute_provenance_hash(p)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest


def test_compute_provenance_hash_changes_when_content_changes(tmp_path: Path):
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    a.write_text("harbor_version: 0.6.6\n")
    b.write_text("harbor_version: 0.6.7\n")
    assert compute_provenance_hash(a) != compute_provenance_hash(b)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_runs_aggregate.py::test_compute_provenance_hash_is_stable_for_identical_input -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement `compute_provenance_hash`**

Append to `src/razorback/runs/aggregate.py`:

```python
def compute_provenance_hash(provenance_path: Path) -> str:
    """sha256 hex digest of provenance.yaml bytes."""
    import hashlib

    return hashlib.sha256(provenance_path.read_bytes()).hexdigest()
```

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest tests/unit/test_runs_aggregate.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/runs/aggregate.py tests/unit/test_runs_aggregate.py
git commit -m "PKG-17 T7: compute_provenance_hash helper"
```

---

### Task 8: Aggregator failure path — never mask harbor's exit code

Per the entity "AC-1: After harbor's `harbor run` completes (success OR
failure), `cli/run.py` invokes an aggregator." If the aggregator itself
raises, the user's view of "did harbor succeed?" must not flip to a Python
traceback. Cover the failure path explicitly.

**Files:**
- Modify: `src/razorback/runs/aggregate.py`
- Test: `tests/unit/test_runs_aggregate.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_runs_aggregate.py`:

```python
from razorback.runs.aggregate import safe_aggregate_run_dir


def test_safe_aggregate_run_dir_returns_warnings_on_partial_input(tmp_path: Path, capsys):
    """An empty run-dir (harbor crashed before any trial dirs) still aggregates
    cleanly: manifest written with n_trials_total=0; no exception."""
    work = tmp_path / "exp" / "job"
    work.mkdir(parents=True)
    (work / "spec.frozen.yaml").write_text("version: 1\n")
    (work / "provenance.yaml").write_text("harbor_version: 0.6.6\n")

    warnings = safe_aggregate_run_dir(
        work,
        spec_path=Path("/x"),
        frozen_spec_hash="a" * 64,
        provenance_hash="b" * 64,
        harbor_job_name="job",
        benchmark_kind=None,
    )
    assert isinstance(warnings, list)
    manifest = json.loads((work / "manifest.json").read_text())
    assert manifest["n_trials_total"] == 0


def test_safe_aggregate_run_dir_catches_unexpected_failure(tmp_path: Path):
    """A non-existent run-dir → safe_aggregate emits a warning, does NOT raise."""
    warnings = safe_aggregate_run_dir(
        tmp_path / "nope" / "job",
        spec_path=Path("/x"),
        frozen_spec_hash="a" * 64,
        provenance_hash="b" * 64,
        harbor_job_name="job",
        benchmark_kind=None,
    )
    assert warnings
    assert any("aggregate" in w.lower() for w in warnings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_runs_aggregate.py -v -k safe_aggregate`
Expected: `ImportError`.

- [ ] **Step 3: Implement `safe_aggregate_run_dir`**

Append to `src/razorback/runs/aggregate.py`:

```python
def safe_aggregate_run_dir(
    run_dir: Path,
    *,
    spec_path: Path,
    frozen_spec_hash: str,
    provenance_hash: str,
    harbor_job_name: str,
    benchmark_kind: str | None,
) -> list[str]:
    """Run aggregate_run_dir; collect warnings instead of raising.

    Harbor's exit code is what the user gates on; the aggregator must not mask
    it with a Python traceback. Returns a list of human-readable warning strings;
    empty list = clean run.
    """
    warnings: list[str] = []
    try:
        aggregate_run_dir(
            run_dir,
            spec_path=spec_path,
            frozen_spec_hash=frozen_spec_hash,
            provenance_hash=provenance_hash,
            harbor_job_name=harbor_job_name,
            benchmark_kind=benchmark_kind,
        )
    except Exception as exc:
        warnings.append(f"aggregate_run_dir failed: {type(exc).__name__}: {exc}")
    return warnings
```

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest tests/unit/test_runs_aggregate.py -v`
Expected: 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/runs/aggregate.py tests/unit/test_runs_aggregate.py
git commit -m "PKG-17 T8: safe_aggregate_run_dir never masks harbor exit code"
```

---

### Task 9: Wire aggregator into `cli/run.py` after harbor exit (AC-1/2/3/4)

**Files:**
- Modify: `src/razorback/cli/run.py:285-312`
- Test: `tests/unit/test_cli_run_aggregator_wiring.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_cli_run_aggregator_wiring.py`:

```python
# ABOUTME: PKG-17 — cli/run.py invokes the aggregator after harbor exit.
# ABOUTME: Patches _invoke_harbor + the aggregator to assert call ordering.

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from razorback.cli import app


def _fake_spec_dir(tmp_path: Path) -> Path:
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "version: 1\n"
        "experiment: pkg17-wiring\n"
        "agent:\n  kind: nop\n"
        "benchmark:\n  kind: local\n"
    )
    return spec


def test_cli_run_invokes_aggregator_on_harbor_success(tmp_path: Path):
    spec = _fake_spec_dir(tmp_path)
    runs_dir = tmp_path / "_runs"

    captured = {}

    def fake_invoke_harbor(job_config_yaml, env):
        # Simulate harbor: write a job-level result.json and a single trial dir.
        run_dir = Path(job_config_yaml).parent
        (run_dir / "result.json").write_text(json.dumps({
            "n_total_trials": 0, "stats": {"n_completed_trials": 0, "n_errored_trials": 0, "evals": {}, "cost_usd": None}
        }))
        return 0

    def fake_aggregate(run_dir, *, spec_path, frozen_spec_hash, provenance_hash,
                      harbor_job_name, benchmark_kind):
        captured["run_dir"] = run_dir
        captured["frozen_spec_hash"] = frozen_spec_hash
        captured["benchmark_kind"] = benchmark_kind
        # Touch the four canonical artifacts so downstream assertions can verify.
        (run_dir / "manifest.json").write_text("{}")
        (run_dir / "summary.json").write_text("{}")
        (run_dir / "events.jsonl").write_text("")
        (run_dir / "per_trial_outcomes.json").write_text("{}")

    with patch("razorback.cli.run._invoke_harbor", side_effect=fake_invoke_harbor), \
         patch("razorback.cli.run._run_canary"), \
         patch("razorback.runs.aggregate.aggregate_run_dir", side_effect=fake_aggregate):
        result = CliRunner().invoke(app, ["run", str(spec), "--runs-dir", str(runs_dir)])
    assert result.exit_code == 0, result.output
    assert captured["benchmark_kind"] == "local"
    assert captured["run_dir"].name  # aggregator received the run-dir


def test_cli_run_invokes_aggregator_on_harbor_failure(tmp_path: Path):
    """AC-1: after harbor exits success OR failure, aggregator still runs."""
    spec = _fake_spec_dir(tmp_path)
    runs_dir = tmp_path / "_runs"

    called = []

    def fake_invoke_harbor(job_config_yaml, env):
        return 30  # harbor non-zero

    def fake_aggregate(run_dir, **kwargs):
        called.append(run_dir)
        (run_dir / "manifest.json").write_text("{}")

    with patch("razorback.cli.run._invoke_harbor", side_effect=fake_invoke_harbor), \
         patch("razorback.cli.run._run_canary"), \
         patch("razorback.runs.aggregate.aggregate_run_dir", side_effect=fake_aggregate):
        result = CliRunner().invoke(app, ["run", str(spec), "--runs-dir", str(runs_dir)])
    # Harbor's exit code wins.
    assert result.exit_code == 30
    # ...but the aggregator was still invoked.
    assert len(called) == 1


def test_cli_run_aggregator_failure_does_not_mask_harbor_exit(tmp_path: Path):
    """T8: when the aggregator raises, rk run still exits with harbor's code."""
    spec = _fake_spec_dir(tmp_path)
    runs_dir = tmp_path / "_runs"

    with patch("razorback.cli.run._invoke_harbor", return_value=0), \
         patch("razorback.cli.run._run_canary"), \
         patch(
             "razorback.runs.aggregate.aggregate_run_dir",
             side_effect=RuntimeError("synthetic"),
         ):
        result = CliRunner().invoke(app, ["run", str(spec), "--runs-dir", str(runs_dir)])
    # Exit 0 from harbor preserved; aggregator failure surfaces as a stderr warning.
    assert result.exit_code == 0
    assert "aggregate" in result.output.lower() or "synthetic" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cli_run_aggregator_wiring.py -v`
Expected: 3 FAIL (aggregator not yet wired into cli/run.py).

- [ ] **Step 3: Modify `src/razorback/cli/run.py`**

In `src/razorback/cli/run.py`, after the post-completion budget-stamp block ending at line 307 (the `stamp_completed(...)` call) and BEFORE the existing `_write_provenance_artifacts(...)` call at lines 309-312, add the aggregator invocation. Final block:

```python
    # PKG-17 §AC-1..AC-4: write canonical aggregator artifacts after harbor exit.
    # Provenance + spec must be on disk first (the aggregator hashes them and
    # records the spec_path); writing them before the aggregator call also
    # matches harbor's lock.json timing (created at job start).
    _write_provenance_artifacts(
        spec_bytes, spec, run_dir, plugin_drift_record=plugin_drift_record
    )

    from razorback.runs.aggregate import (
        compute_provenance_hash,
        safe_aggregate_run_dir,
    )

    provenance_path = run_dir / "provenance.yaml"
    if provenance_path.exists():
        provenance_hash = compute_provenance_hash(provenance_path)
    else:
        # m1-nop with no provenance block; hash an empty file marker so the
        # manifest field is type-stable.
        import hashlib
        provenance_hash = hashlib.sha256(b"").hexdigest()

    frozen_spec_hash = hashlib.sha256(spec_bytes).hexdigest() if isinstance(spec_bytes, bytes) else (
        __import__("hashlib").sha256(spec_bytes.encode("utf-8") if isinstance(spec_bytes, str) else b"").hexdigest()
    )
    # Note: `job_name` is already sha256(frozen)[:16] from derive_job_name; reuse the
    # full sha256 here for downstream pinning.
    benchmark_kind = getattr(spec.benchmark, "kind", None)
    warnings = safe_aggregate_run_dir(
        run_dir,
        spec_path=spec_path,
        frozen_spec_hash=frozen_spec_hash,
        provenance_hash=provenance_hash,
        harbor_job_name=job_name,
        benchmark_kind=benchmark_kind,
    )
    for w in warnings:
        typer.echo(f"warning: {w}", err=True)

    if rc != 0:
        raise typer.Exit(ExitCode.HARBOR_RUNTIME)
```

…and DELETE the existing block at the same location (lines 286-312) which used to:
1. Call `_invoke_harbor` (kept earlier)
2. Raise `typer.Exit(ExitCode.HARBOR_RUNTIME)` immediately on harbor failure (before aggregator)
3. Run the budget-stamp block (keep — happens before this block)
4. Call `_write_provenance_artifacts` (now moved BEFORE the aggregator)

The net change: harbor-failure exit happens AFTER the aggregator runs (AC-1
covers both success and failure). The budget stamp + provenance write
sequence is preserved.

To be precise, modify `src/razorback/cli/run.py` from line 285 to line 312 to read:

```python
    rc = _invoke_harbor(job_config_yaml, harbor_env)

    # Phase 4a: post-completion budget stamp. (unchanged — runs regardless of rc)
    if max_budget_usd_running is not None:
        from razorback.budget import (
            read_actual_cost_from_run_dir,
            stamp_completed,
        )

        actual_cost, cost_known = read_actual_cost_from_run_dir(run_dir)
        stamp_completed(
            path=max_budget_usd_running,
            run_dir=str(run_dir),
            actual_usd=actual_cost,
            cost_known=cost_known,
        )

    # AC-3 (provenance) — must happen BEFORE the aggregator so it can hash
    # provenance.yaml into manifest.json.
    _write_provenance_artifacts(
        spec_bytes, spec, run_dir, plugin_drift_record=plugin_drift_record
    )

    # PKG-17 §AC-1..AC-4: write the canonical aggregator artifacts.
    import hashlib

    from razorback.runs.aggregate import (
        compute_provenance_hash,
        safe_aggregate_run_dir,
    )

    provenance_path = run_dir / "provenance.yaml"
    provenance_hash = (
        compute_provenance_hash(provenance_path)
        if provenance_path.exists()
        else hashlib.sha256(b"").hexdigest()
    )
    frozen_spec_hash = hashlib.sha256(spec_bytes).hexdigest()
    benchmark_kind = getattr(spec.benchmark, "kind", None)
    warnings = safe_aggregate_run_dir(
        run_dir,
        spec_path=spec_path,
        frozen_spec_hash=frozen_spec_hash,
        provenance_hash=provenance_hash,
        harbor_job_name=job_name,
        benchmark_kind=benchmark_kind,
    )
    for w in warnings:
        typer.echo(f"warning: {w}", err=True)

    if rc != 0:
        typer.echo(f"harbor run failed (exit {rc}); surfacing as exit 30", err=True)
        raise typer.Exit(ExitCode.HARBOR_RUNTIME)
```

- [ ] **Step 4: Run wiring tests to verify pass**

Run: `uv run pytest tests/unit/test_cli_run_aggregator_wiring.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Run the full unit suite to check for regressions**

Run: `uv run pytest tests/unit/ -v -x`
Expected: all PASS (including phase 4a tests that touch `cli/run.py`).

- [ ] **Step 6: Commit**

```bash
git add src/razorback/cli/run.py tests/unit/test_cli_run_aggregator_wiring.py
git commit -m "PKG-17 T9: wire aggregator into cli/run.py post-harbor (AC-1..AC-4)"
```

---

### Task 10: smoke matrix — `rk runs cost` against PKG-17 run-dirs (AC-6)

**Files:**
- Test: `tests/integration/test_runs_cost_against_pkg17.py` (new)

This validates AC-6 via the existing `rk runs cost` consumer without
requiring a cost-bearing live run. We synthesize a small matrix of two
PKG-17-produced run-dirs by invoking `aggregate_run_dir` against fixture
skeletons and assert `rk runs cost --root <matrix>` sums them correctly.

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_runs_cost_against_pkg17.py`:

```python
# ABOUTME: PKG-17 AC-6 — rk runs cost walks PKG-17-produced run-dirs.

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from razorback.runs.aggregate import aggregate_run_dir

REPO = Path(__file__).resolve().parents[2]
FIXTURE_RUN = REPO / "tests" / "fixtures" / "runs" / "post_harbor_skeleton"


def _populate(run_dir: Path, *, cost_in_summary: float | None) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for child in FIXTURE_RUN.iterdir():
        target = run_dir / child.name
        if target.exists():
            continue
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy(child, target)
    (run_dir / "spec.frozen.yaml").write_text("version: 1\nexperiment: smoke\n")
    (run_dir / "provenance.yaml").write_text("harbor_version: 0.6.6\n")
    aggregate_run_dir(
        run_dir,
        spec_path=Path("/x"),
        frozen_spec_hash="a" * 64,
        provenance_hash="b" * 64,
        harbor_job_name=run_dir.name,
        benchmark_kind="dab",
    )
    if cost_in_summary is not None:
        summary = json.loads((run_dir / "summary.json").read_text())
        summary["cost_usd"] = cost_in_summary
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def test_rk_runs_cost_sums_pkg17_run_dirs(tmp_path: Path):
    matrix = tmp_path / "matrix"
    _populate(matrix / "bookreview" / "j1", cost_in_summary=1.23)
    _populate(matrix / "bookreview" / "j2", cost_in_summary=4.56)
    _populate(matrix / "crmarenapro" / "j3", cost_in_summary=7.89)

    result = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "runs", "cost", "--root", str(matrix)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    doc = json.loads(result.stdout)
    assert doc["n_known"] == 3
    assert doc["n_unknown"] == 0
    assert abs(doc["total_usd"] - (1.23 + 4.56 + 7.89)) < 1e-9
    # No "no manifest.json found, skipping" warnings.
    assert not doc["warnings"]
```

- [ ] **Step 2: Run test to verify it fails (or passes if T9 wired correctly)**

Run: `uv run pytest tests/integration/test_runs_cost_against_pkg17.py -v`
Expected: PASS (if T9 wiring is correct + summary.json carries the synthesized cost_usd).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_runs_cost_against_pkg17.py
git commit -m "PKG-17 T10: AC-6 smoke matrix — rk runs cost honest against PKG-17 dirs"
```

---

### Task 11: un-break the 8 integration tests (AC-7)

The 8 SWE-flagged tests are listed in the entity §AC-7. For each, decide:
keep as-is (test already matches PKG-17 contract) vs minimal fix.

**Files (decisions):**

| Test file | Status | Action |
|----|----|----|
| `tests/integration/test_rk_run_nop.py` (2 tests in file) | Already-aligned | Verify only; no edits expected |
| `tests/integration/test_rk_run_bookreview_nop.py` (2 tests) | Already-aligned | Verify only |
| `tests/integration/test_dab_dev_claude_full.py` | Already-aligned (cost-gated) | Verify only |
| `tests/integration/test_dab_workflow_lifecycle.py` | Already-aligned (docker-gated) | Verify only |
| `tests/integration/test_ade_bench_claude_smoke.py` | Already-aligned (docker-gated) | Verify only |
| `tests/integration/test_rk_run_bookreview_claude.py` | Already-aligned (docker-gated) | Verify only |
| `tests/integration/test_rk_run_v2_deterministic_smoke.py` | Test asserts on harbor's `result.json` directly (post-PKG-13 loader-fix world). PKG-17 adds `summary.json`; update test to also assert summary.json shape | Add summary.json assertion |
| `tests/integration/test_no_auth_leak_in_run_dir.py` | Asserts `config.json` exists; events.jsonl is required by spec but file's grep gate is artifact-agnostic | Verify only |

- [ ] **Step 1: Run the four free tests under the local-only path**

Run: `uv run pytest tests/integration/test_rk_run_nop.py tests/integration/test_rk_run_bookreview_nop.py tests/integration/test_rk_run_v2_deterministic_smoke.py tests/integration/test_no_auth_leak_in_run_dir.py -v -m "not skipif"`

Expected: most PASS after PKG-17 wiring. Note any FAIL or SKIP and capture in the stage report.

- [ ] **Step 2: Update `test_rk_run_v2_deterministic_smoke.py`**

Modify `tests/integration/test_rk_run_v2_deterministic_smoke.py`, append after line 83 (after the existing harbor `result.json` assertions):

```python

    # PKG-17 §AC-2: rk run writes summary.json post-harbor.
    summary_path = run_dir / "summary.json"
    assert summary_path.is_file(), (
        f"PKG-17 AC-2 violation: no summary.json under {run_dir}"
    )
    summary = json.loads(summary_path.read_text())
    assert summary["n_trials_completed"] == 3
    assert summary["n_trials_errored"] == 0
    # PKG-17 §AC-1: manifest.json carries per_trial_paths + counts.
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["n_trials_completed"] == 3
    assert len(manifest["per_trial_paths"]) == 3
    # PKG-17 §AC-3: events.jsonl present.
    assert (run_dir / "events.jsonl").is_file()
    # PKG-17 §AC-4: per_trial_outcomes.json present.
    assert (run_dir / "per_trial_outcomes.json").is_file()
```

- [ ] **Step 3: Run the deterministic smoke test if local docker is available**

Run: `RAZORBACK_RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_rk_run_v2_deterministic_smoke.py -v` (skip if docker not available; document in stage report).

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_rk_run_v2_deterministic_smoke.py
git commit -m "PKG-17 T11: deterministic-smoke integration asserts PKG-17 artifact set (AC-7)"
```

---

### Task 12: rk score no-regression check (AC-8)

**Files:**
- Test: `tests/unit/test_score_no_regression_pkg17.py` (new)

`rk score` reads per-trial `result.json` files via `score/load.py:44-60`, not
the new `summary.json`. PKG-17's additive writes must not change `rk score`'s
output. Validate against:
1. The fixture run-dir (`tests/fixtures/runs/post_harbor_skeleton/`).
2. The existing PKG-13 honest re-run dir (`.runs/baseline-rerun-20260520-bookreview/...`)
   — `rk score` against it produces 9/9 Wilson CI; running before & after PKG-17 wiring
   must yield byte-identical output.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_score_no_regression_pkg17.py`:

```python
# ABOUTME: PKG-17 AC-8 — rk score's output is unchanged after PKG-17 lands.
# ABOUTME: Walks per-trial result.json (score/load.py:44-60) — independent of new summary.json.

import json
import shutil
from pathlib import Path

from razorback.score.load import load_run_dir

FIXTURE_RUN = Path(__file__).resolve().parents[1] / "fixtures" / "runs" / "post_harbor_skeleton"


def test_rk_score_loader_unaffected_by_summary_json_presence(tmp_path: Path):
    """`load_run_dir` walks per-trial result.json, not summary.json. Adding
    summary.json (and friends) at run-dir top level must not change which
    trial records `load_run_dir` returns."""
    work = tmp_path / "exp" / "job"
    work.mkdir(parents=True)
    for child in FIXTURE_RUN.iterdir():
        if child.is_dir():
            shutil.copytree(child, work / child.name)
        else:
            shutil.copy(child, work / child.name)

    # Baseline: rk score against the run-dir before PKG-17 writes.
    before = load_run_dir(work)
    before_state = {(r.trial_name, r.state, r.reward) for r in before}

    # PKG-17 writes the four artifacts.
    from razorback.runs.aggregate import aggregate_run_dir

    (work / "spec.frozen.yaml").write_text("version: 1\n")
    (work / "provenance.yaml").write_text("harbor_version: 0.6.6\n")
    aggregate_run_dir(
        work,
        spec_path=Path("/x"),
        frozen_spec_hash="a" * 64,
        provenance_hash="b" * 64,
        harbor_job_name="job",
        benchmark_kind="dab",
    )

    after = load_run_dir(work)
    after_state = {(r.trial_name, r.state, r.reward) for r in after}

    assert before_state == after_state, (
        f"rk score loader regression: {before_state ^ after_state}"
    )
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_score_no_regression_pkg17.py -v`
Expected: PASS.

- [ ] **Step 3: Live `rk score` smoke (if PKG-13 dir available)**

Run: `uv run rk score .runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/` (note this dir already has summary.json + the other artifacts from a prior aggregator pass; PKG-17's writes are byte-compatible with that earlier output).

Expected: same 3/3 reward=1.0 Wilson CI output as recorded in PKG-13's stage
report. If the dir is missing locally, document the SKIP in the stage report.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_score_no_regression_pkg17.py
git commit -m "PKG-17 T12: AC-8 — rk score loader unaffected by PKG-17 writes"
```

---

### Task 13: Final sweep — full unit + non-cost-bearing integration

**Files:** none new.

- [ ] **Step 1: Run the full razorback unit suite**

Run: `uv run pytest tests/unit/ -v`
Expected: all PASS (no SKIPs introduced by PKG-17 beyond those pre-existing).

- [ ] **Step 2: Run the non-cost-bearing integration tests**

Run: `uv run pytest tests/integration/ -v -m "not slow"` (or whatever marker the project uses for cost-gated tests — read `pyproject.toml` if unsure).

Capture which tests PASS / FAIL / SKIP. Document in stage report.

- [ ] **Step 3: Run the plugin test suite (no regressions)**

Run: `uv run pytest packages/razorback-plugin-dab/tests/ -v` (paths from prior PKG-13 stage reports).
Expected: all PASS.

- [ ] **Step 4: Commit (only if any test fixups were needed)**

If any non-trivial test edits surfaced during the sweep:

```bash
git add <files>
git commit -m "PKG-17 T13: test fixups from full sweep"
```

Otherwise no commit.

---

## Self-Review

**Spec coverage:**
- AC-1 (manifest.json post-harbor) → T1 + T9.
- AC-2 (summary.json per-trial + stratified) → T2 + T9.
- AC-3 (events.jsonl concatenation) → T3 + T9.
- AC-4 (per_trial_outcomes.json) → T4 + T9.
- AC-5 (lock.json drift surface) → T5.
- AC-6 (rk runs cost honest against v2) → T10.
- AC-7 (8 integration tests un-break) → T11 (table of decisions per test).
- AC-8 (rk score no-regression) → T12.
- T6 + T7 + T8 are the mechanism-validation gate (smallest end-to-end + helpers + failure-safety).

**Placeholder scan:** No "TBD", "add appropriate error handling", or "similar to Task N". Every step has the actual content.

**Type consistency:** Method names align across tasks:
- `write_manifest`, `aggregate_summary`, `concatenate_events`, `write_per_trial_outcomes` (the four leaf writers, T1-T4).
- `aggregate_run_dir`, `safe_aggregate_run_dir` (the entry points, T6/T8).
- `compute_provenance_hash` (T7), `compute_drift` (T5).
- Constants: `MANIFEST_SCHEMA_VERSION = 1`, `SUMMARY_VERSION = 1`, `OUTCOMES_VERSION = 1` (matches existing `_legacy/manifest.py:8` and `benchmarks/dab/aggregate.py:8`).

**Risk callout:** The biggest assumption is that harbor 0.6.6's
filesystem layout (per-trial `result.json`, per-trial `events.jsonl`,
job-level `result.json`) is stable. T6's mechanism check exercises that
end-to-end against a fixture skeleton that mirrors the real `.runs/baseline-rerun-20260520-bookreview/...`
layout, so a future harbor upgrade that moves files will fail T6 first
(not in production).

## Execution Handoff

Plan complete. Two execution options:

1. **Subagent-Driven** (recommended) — dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch with checkpoints.
