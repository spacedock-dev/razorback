# M2 — DAB adapter for `bookreview` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `uv run rk run examples/specs/bookreview-nop.yaml` execute against the real `bookreview` dataset under `/Users/clkao/git/dataagentbench/data/`, through harbor's bundled nop agent, producing a run-dir whose `summary.json` carries the per-query / per-dataset / stratified pass@1 breakdown §6.5 requires.

**Architecture:** A `razorback.benchmarks.dab` package adds three modules — `prepare.py` (materializes a harbor task dir per `(dataset, query_id)` from a DAB dataset root; copies `query.json`, `db_config.yaml`, `db_description.txt`, `query_dataset/`; **never** copies `ground_truth.csv` or `validate.py`), `verify.py` (script invoked by `tests/test.sh` inside the container; reads `/work/answers.json`, imports the source dataset's `validate.py` under a bind-mount, writes `/logs/verifier/reward.json`), and `aggregate.py` (reads `JobResult.trial_results`, computes pass@1 per query, per-dataset means, stratified macro-average; writes `summary.json`). M1's spec parser and JobConfig translator extend just enough to accept `benchmark.kind=dab` with `data_root` and `datasets`; the run orchestrator dispatches the DAB aggregator when the spec's benchmark kind is `dab`.

**Tech Stack:** Python 3.12, `uv`, Pydantic 2.11, PyYAML 6, harbor 0.6.6 (already pinned in M1), pytest 8 with `pytest-asyncio` 0.24, docker via Colima.

**Source of truth:** the design doc at `/Users/clkao/git/dataagentbench/docs/superpowers/specs/2026-05-18-razorback-python-on-harbor.md`. Section anchors below cite it as `§N.N`. The seven ACs live in the M2 entity at `docs/razorback-implementation/m2-dab-bookreview.md`.

**M1 inputs (do not duplicate):**

- Spec parser + pydantic schema: `src/razorback/spec/{schema,parse,freeze}.py`. Extend the existing `BenchmarkBlock` and add an optional `DabBenchmarkBlock`; do not write a second parser.
- JobConfig translator: `src/razorback/compat/harbor_0_6_6.py::spec_to_job_config`. Extend; do not fork.
- Run orchestrator: `src/razorback/run.py::execute_run` / `_execute_run_async`. Hook a post-`Job.run()` aggregator dispatch on `spec.benchmark.kind`.
- Manifest writer (`run_dir_version: 1`), observers, channel drainer, `derive_job_name`, exit-code map — unchanged.

**AC ↔ task map (1:1):**

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-1 `aggregate.py` consumes synthetic input → golden `summary.json` | §6.5 stratified macro-average; harbor's `pass_at_k` formula in `dataagentbench/data/common_scaffold/validate/pass_k.py` | Tasks 1, 2 |
| AC-2 `prepare.py` excludes `ground_truth.csv` | §6.5 DAB-as-harbor-adapter shape; §7 layout | Task 4 |
| AC-3 `verify.py` emits harbor's reward shape against `answers.json` | §6.5; reward contract in `docs/pre-m1-findings.md` | Task 5 |
| AC-4 `JobConfig.retry.max_retries == 0` for DAB | §6.5 ("retry-after-failure that harbor marks as a passed trial would inflate pass@1") | Task 7 |
| AC-5 aggregator does NOT read `JobResult.stats.evals` | §6.5 ("`JobStats.evals` is per-dataset micro-average, not what DAB needs") | Task 2 (negative test); Task 12 (grep gate) |
| AC-6 declared `per_trial_state_reset` matches §6.5 | §6.5 reset declarations | Task 3 |
| AC-7 end-to-end `rk run examples/specs/bookreview-nop.yaml` → `summary.json` with stratified pass@1 | §6.5 stratified pass@1; §8.M2 acceptance | Tasks 6, 7, 8, 9, 10, 11 |

**Riskiest contract first.** Task 1 builds a hand-written `JobResult`-shaped fixture and asserts the aggregator produces the byte-exact golden `summary.json` **before** any harbor task wiring, prepare/verify scripts, or end-to-end run lands. Per CL's "Validating new mechanisms" rule and per AC-1's verbatim text ("Verified by: a unit test feeds a hand-written `JobResult` fixture covering bookreview's queries to `aggregate.py` and asserts the resulting `summary.json` matches a checked-in golden file"), the math must be locked first. If the formula or shape is wrong, every later task produces wrong scores; the integration test (Task 11) is then redundant.

**Working agreements pulled forward from M1's plan:**

- Repo layout follows §7 (`src/razorback/benchmarks/dab/` for M2).
- All Python source files start with the `ABOUTME:` two-line comment header (per CL's global rules). YAML/TOML/markdown data files do not.
- Pinned harbor is `harbor==0.6.6`; imports follow `docs/pre-m1-findings.md` "Harbor API map".
- macOS+Colima only mounts `/Users/<user>/` into the docker VM. The DAB data root, the generated harbor task dirs, and run-dirs must all live under `/Users/...`. The `bookreview-nop.yaml` spec's `data_root: /Users/clkao/git/dataagentbench/data` is absolute and already Colima-safe; tests reuse M1's `colima_safe_tmp_path` fixture.
- TDD: every behavior task writes the failing test first, runs it red, then makes it green, then commits.
- Commits: one focused commit per task. Format: `m2: <short summary>`.

---

## File structure

Files created or modified by this plan. Existing files (from M1, landed on branch `spacedock-ensign/m1-rk-run-nop`) marked `[existing]`.

```
examples/
└── specs/
    └── bookreview-nop.yaml                            [new] M2 acceptance spec
src/razorback/
├── spec/
│   └── schema.py                                      [existing — extend]
├── compat/
│   └── harbor_0_6_6.py                                [existing — extend]
├── run.py                                             [existing — extend post-run dispatch]
└── benchmarks/
    ├── __init__.py                                    [new]
    └── dab/
        ├── __init__.py                                [new] — re-export per_trial_state_reset
        ├── prepare.py                                 [new] — materialize harbor task dirs
        ├── verify.py                                  [new] — in-container reward emitter
        ├── aggregate.py                               [new] — JobResult → summary.json
        └── reset.py                                   [new] — per_trial_state_reset declaration
tests/
├── unit/
│   ├── test_dab_aggregate.py                          [new] AC-1, AC-5 negative
│   ├── test_dab_aggregate_grep.py                     [new] AC-5 grep gate
│   ├── test_dab_per_trial_state_reset.py              [new] AC-6
│   ├── test_dab_prepare.py                            [new] AC-2
│   ├── test_dab_verify.py                             [new] AC-3
│   ├── test_dab_spec_parse.py                         [new] DabBenchmarkBlock parser
│   └── test_dab_translator.py                         [new] AC-4 retry-zero + task fan-out
├── integration/
│   └── test_rk_run_bookreview_nop.py                  [new] AC-7 end-to-end
└── fixtures/
    └── dab/
        ├── synthetic_trial_results.json               [new] AC-1 input fixture
        └── golden_summary.json                        [new] AC-1 golden output
docs/razorback-implementation/
└── m2-dab-bookreview.md                               [existing — extend Test plan]
```

---

## Task 0: Pre-flight — confirm M1 surfaces and DAB data root

**Files:** none.

- [ ] **Step 1: Verify operator environment matches M1's expectations**

```bash
cd /Users/clkao/git/razorback
uv --version
docker info | head -3
.venv/bin/python -c "import harbor; print(harbor.__version__)"
ls /Users/clkao/git/dataagentbench/data/query_bookreview/
```

Expected:
- `uv` reports a version; `docker info` succeeds (Colima up); harbor reports `0.6.6`.
- `query_bookreview/` lists exactly four directories: `query1`, `query2`, `query3`, `query_dataset` (plus `db_config.yaml`, `db_description.txt`, `db_description_withhint.txt`, `__pycache__`).

If `query_bookreview/` is missing or has a different shape, **STOP and escalate via `SendMessage(to="team-lead", ...)`** — the design doc and the on-disk shape diverged; the plan cannot proceed without re-anchoring on the actual files.

- [ ] **Step 2: Confirm M1 ships on this branch**

```bash
git log --oneline -1 -- src/razorback/spec/schema.py
git log --oneline -1 -- src/razorback/compat/harbor_0_6_6.py
git log --oneline -1 -- src/razorback/run.py
```

Each must show an `m1: …` commit. If any prints nothing, M2 is being run before M1's worktree merged to main — escalate.

- [ ] **Step 3: No commit. This is a check, not a change.**

---

## Task 1: Author the golden synthetic fixture for the aggregator

**Why first:** AC-1 explicitly names a "hand-written `JobResult` fixture covering bookreview's queries" against a "checked-in golden file". The golden encodes the §6.5 formula; once it lands, Task 2's aggregator code is constrained to produce exactly that output. If the formula is wrong, no later task lands a correct score. Per CL's "Validating new mechanisms" rule, this contract goes first.

The synthetic fixture exercises the math, not harbor — it is JSON, not a real `JobResult`. Task 2's loader reads it as if it were `[TrialResult, ...]`. This keeps the contract test independent of harbor's serialization shape.

**Files:**
- Create: `tests/fixtures/dab/synthetic_trial_results.json`
- Create: `tests/fixtures/dab/golden_summary.json`

- [ ] **Step 1: Write the synthetic input fixture**

`tests/fixtures/dab/synthetic_trial_results.json`:

```json
[
  {"trial_name": "bookreview-q1__aaaa001", "task_name": "razorback/bookreview-q1", "dataset": "bookreview", "query_id": 1, "trial_index": 0, "rewards": {"reward": 1.0}},
  {"trial_name": "bookreview-q1__aaaa002", "task_name": "razorback/bookreview-q1", "dataset": "bookreview", "query_id": 1, "trial_index": 1, "rewards": {"reward": 1.0}},
  {"trial_name": "bookreview-q1__aaaa003", "task_name": "razorback/bookreview-q1", "dataset": "bookreview", "query_id": 1, "trial_index": 2, "rewards": {"reward": 0.0}},
  {"trial_name": "bookreview-q1__aaaa004", "task_name": "razorback/bookreview-q1", "dataset": "bookreview", "query_id": 1, "trial_index": 3, "rewards": {"reward": 0.0}},
  {"trial_name": "bookreview-q1__aaaa005", "task_name": "razorback/bookreview-q1", "dataset": "bookreview", "query_id": 1, "trial_index": 4, "rewards": {"reward": 1.0}},
  {"trial_name": "bookreview-q2__bbbb001", "task_name": "razorback/bookreview-q2", "dataset": "bookreview", "query_id": 2, "trial_index": 0, "rewards": {"reward": 0.0}},
  {"trial_name": "bookreview-q2__bbbb002", "task_name": "razorback/bookreview-q2", "dataset": "bookreview", "query_id": 2, "trial_index": 1, "rewards": {"reward": 0.0}},
  {"trial_name": "bookreview-q2__bbbb003", "task_name": "razorback/bookreview-q2", "dataset": "bookreview", "query_id": 2, "trial_index": 2, "rewards": {"reward": 0.0}},
  {"trial_name": "bookreview-q2__bbbb004", "task_name": "razorback/bookreview-q2", "dataset": "bookreview", "query_id": 2, "trial_index": 3, "rewards": {"reward": 0.0}},
  {"trial_name": "bookreview-q2__bbbb005", "task_name": "razorback/bookreview-q2", "dataset": "bookreview", "query_id": 2, "trial_index": 4, "rewards": {"reward": 0.0}},
  {"trial_name": "bookreview-q3__cccc001", "task_name": "razorback/bookreview-q3", "dataset": "bookreview", "query_id": 3, "trial_index": 0, "rewards": {"reward": 1.0}},
  {"trial_name": "bookreview-q3__cccc002", "task_name": "razorback/bookreview-q3", "dataset": "bookreview", "query_id": 3, "trial_index": 1, "rewards": {"reward": 1.0}},
  {"trial_name": "bookreview-q3__cccc003", "task_name": "razorback/bookreview-q3", "dataset": "bookreview", "query_id": 3, "trial_index": 2, "rewards": {"reward": 1.0}},
  {"trial_name": "bookreview-q3__cccc004", "task_name": "razorback/bookreview-q3", "dataset": "bookreview", "query_id": 3, "trial_index": 3, "rewards": {"reward": 1.0}},
  {"trial_name": "bookreview-q3__cccc005", "task_name": "razorback/bookreview-q3", "dataset": "bookreview", "query_id": 3, "trial_index": 4, "rewards": {"reward": 1.0}}
]
```

Per-query c (correct count) / n (trials): q1: 3/5 → pass@1 = 3/5 = 0.6; q2: 0/5 → pass@1 = 0.0; q3: 5/5 → pass@1 = 1.0. Per-dataset macro-average = (0.6 + 0.0 + 1.0) / 3 = 0.5333… (16/30). Stratified macro-average across datasets = 0.5333… (only one dataset).

The pass@1 derivation uses the `pass_at_k` formula in `/Users/clkao/git/dataagentbench/data/common_scaffold/validate/pass_k.py`:
- `c == 0` → 0.0
- `n - c < 1` → 1.0 (i.e. all correct → 1.0)
- otherwise `1 - C(n-c, 1) / C(n, 1) = 1 - (n-c)/n = c/n`

For k=1 the formula reduces to `c/n` (the conventional pass@1). The aggregator uses the verbatim formula so that future M5 work (pass@k, k>1) shares a single code path.

- [ ] **Step 2: Write the golden output fixture**

`tests/fixtures/dab/golden_summary.json`:

```json
{
  "summary_version": 1,
  "stratified_pass_at_1": 0.5333333333333333,
  "datasets": {
    "bookreview": {
      "dataset_pass_at_1": 0.5333333333333333,
      "n_queries": 3,
      "queries": [
        {"query_id": 1, "n_trials": 5, "n_correct": 3, "pass_at_1": 0.6},
        {"query_id": 2, "n_trials": 5, "n_correct": 0, "pass_at_1": 0.0},
        {"query_id": 3, "n_trials": 5, "n_correct": 5, "pass_at_1": 1.0}
      ]
    }
  }
}
```

The schema follows §6.5: "both the stratified score and the per-query, per-dataset breakdowns paired diff needs". `summary_version: 1` mirrors `run_dir_version: 1` — a stable contract per §3.3 (rolling fields up under semver).

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/dab/synthetic_trial_results.json tests/fixtures/dab/golden_summary.json
git commit -m "m2: golden fixture for DAB aggregator (AC-1)"
```

---

## Task 2: Implement `aggregate.py` against the golden

**Files:**
- Create: `src/razorback/benchmarks/__init__.py`
- Create: `src/razorback/benchmarks/dab/__init__.py`
- Create: `src/razorback/benchmarks/dab/aggregate.py`
- Create: `tests/unit/test_dab_aggregate.py`

The aggregator's I/O surface is small: it takes a sequence of typed records (`trial_name`, `task_name`, `rewards`, plus a `(dataset, query_id) → trial_name_prefix` mapping built at job-config time) and writes one JSON file. The mapping is necessary because §6.5 explicitly forbids reading `JobResult.stats.evals` (AC-5), and `trial_name` is the only stable per-trial identifier harbor exposes.

For Task 2 the aggregator reads the synthetic fixture directly (each fixture row already carries `dataset` and `query_id`). Task 7 wires the real translator-produced mapping in.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_dab_aggregate.py`:

```python
# ABOUTME: Unit tests for the DAB aggregator (§6.5).
# ABOUTME: Frozen synthetic input → byte-exact golden summary.json (AC-1).

import json
from pathlib import Path

from razorback.benchmarks.dab.aggregate import aggregate_synthetic

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dab"


def test_aggregator_matches_golden_summary(tmp_path):
    rows = json.loads((FIXTURES / "synthetic_trial_results.json").read_text())
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    got = json.loads(out.read_text())
    expected = json.loads((FIXTURES / "golden_summary.json").read_text())
    assert got == expected


def test_pass_at_1_uses_pass_k_formula_at_k_equals_1():
    """pass@1 at k=1 reduces to c/n. Anchored to harbor's golden math."""
    from razorback.benchmarks.dab.aggregate import pass_at_k

    assert pass_at_k(n=5, c=0, k=1) == 0.0
    assert pass_at_k(n=5, c=5, k=1) == 1.0
    assert pass_at_k(n=5, c=3, k=1) == 0.6
    assert pass_at_k(n=5, c=1, k=1) == 0.2
```

- [ ] **Step 2: Run tests, confirm red**

```bash
uv run pytest tests/unit/test_dab_aggregate.py -v
```

Expected: ImportError on `razorback.benchmarks.dab.aggregate`.

- [ ] **Step 3: Implement `aggregate.py`**

`src/razorback/benchmarks/__init__.py`:

```python
# ABOUTME: Razorback benchmark adapters root package.
# ABOUTME: Per-benchmark subpackages live here (dab/, …). Each declares per_trial_state_reset.
```

`src/razorback/benchmarks/dab/__init__.py`:

```python
# ABOUTME: DAB-as-harbor-adapter package (§6.5).
# ABOUTME: Re-exports per_trial_state_reset; prepare/verify/aggregate live in sibling modules.

from razorback.benchmarks.dab.reset import per_trial_state_reset

__all__ = ["per_trial_state_reset"]
```

`src/razorback/benchmarks/dab/aggregate.py`:

```python
# ABOUTME: DAB stratified pass@1 aggregator (§6.5).
# ABOUTME: Reads typed per-trial records; writes per-query / per-dataset / stratified summary.json.

import json
from math import comb
from pathlib import Path
from typing import Iterable

SUMMARY_VERSION = 1


def pass_at_k(*, n: int, c: int, k: int) -> float:
    """Verbatim DAB pass@k (see /Users/clkao/git/dataagentbench/data/common_scaffold/validate/pass_k.py).

    For k=1 this reduces to c/n; the general formula is kept so M5 can add pass@k>1
    without changing the code path.
    """
    if c == 0:
        return 0.0
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def aggregate_synthetic(rows: list[dict], out_path: Path) -> None:
    """Aggregate hand-written fixture rows.

    Each row is a dict with keys: `dataset`, `query_id`, `rewards: {"reward": float}`.
    Used by the AC-1 unit test before the harbor translator landing in Task 7.
    """
    per_query: dict[tuple[str, int], list[float]] = {}
    for row in rows:
        ds = row["dataset"]
        qid = int(row["query_id"])
        reward = float(row["rewards"]["reward"])
        per_query.setdefault((ds, qid), []).append(reward)

    summary = _build_summary(per_query)
    Path(out_path).write_text(json.dumps(summary, indent=2) + "\n")


def _build_summary(per_query: dict[tuple[str, int], list[float]]) -> dict:
    datasets: dict[str, dict] = {}
    for (ds, qid), rewards in per_query.items():
        n = len(rewards)
        c = sum(1 for r in rewards if r >= 1.0)  # DAB treats reward ∈ {0.0, 1.0}; pass = ≥1.0.
        entry = datasets.setdefault(ds, {"dataset_pass_at_1": 0.0, "n_queries": 0, "queries": []})
        entry["queries"].append({"query_id": qid, "n_trials": n, "n_correct": c, "pass_at_1": pass_at_k(n=n, c=c, k=1)})
    for ds, entry in datasets.items():
        entry["queries"].sort(key=lambda q: q["query_id"])
        entry["n_queries"] = len(entry["queries"])
        entry["dataset_pass_at_1"] = sum(q["pass_at_1"] for q in entry["queries"]) / entry["n_queries"]
    stratified = (
        sum(ds["dataset_pass_at_1"] for ds in datasets.values()) / len(datasets)
        if datasets
        else 0.0
    )
    return {
        "summary_version": SUMMARY_VERSION,
        "stratified_pass_at_1": stratified,
        "datasets": dict(sorted(datasets.items())),
    }


def aggregate_job_result(
    trial_results: Iterable,
    trial_name_map: dict[str, tuple[str, int]],
    out_path: Path,
) -> None:
    """Aggregate a real harbor JobResult.trial_results sequence.

    `trial_name_map` is built by the spec → JobConfig translator (Task 7).
    Each trial_result must expose `.trial_name: str` and `.verifier_result.rewards: dict | None`.

    Per §6.5 the aggregator never reads `JobResult.stats.evals` (AC-5). The mapping
    pairs each trial back to its (dataset, query_id) by exact `trial_name → key` lookup,
    matching by the `bookreview-q1__<uuid>` prefix harbor assigns at TrialConfig validation
    (see harbor.models.trial.config.TrialConfig.generate_trial_name).
    """
    per_query: dict[tuple[str, int], list[float]] = {}
    for tr in trial_results:
        # trial_name in harbor is "{task_name_last_segment[:32]}__{uuid7}"; we match the prefix.
        key = _resolve_key(tr.trial_name, trial_name_map)
        if key is None:
            continue
        reward = 0.0
        if tr.verifier_result is not None and tr.verifier_result.rewards:
            reward = float(tr.verifier_result.rewards.get("reward", 0.0))
        per_query.setdefault(key, []).append(reward)

    summary = _build_summary(per_query)
    Path(out_path).write_text(json.dumps(summary, indent=2) + "\n")


def _resolve_key(trial_name: str, trial_name_map: dict[str, tuple[str, int]]) -> tuple[str, int] | None:
    # trial_name = "<prefix>__<uuid7>"; split on the documented "__" separator.
    prefix = trial_name.split("__", 1)[0]
    return trial_name_map.get(prefix)
```

- [ ] **Step 4: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_dab_aggregate.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/benchmarks tests/unit/test_dab_aggregate.py
git commit -m "m2: DAB aggregator — stratified pass@1 against golden (AC-1)"
```

---

## Task 3: `per_trial_state_reset` declaration (AC-6)

**Files:**
- Create: `src/razorback/benchmarks/dab/reset.py`
- Create: `tests/unit/test_dab_per_trial_state_reset.py`

§6.5 names the exact triplet: `agent_container: True, compose_services: True, host_workspace: True`. The M2 entity body (AC-6) repeats it verbatim. Encoding the triplet as a module-level constant exposed via `razorback.benchmarks.dab.per_trial_state_reset` keeps the declaration auditable by `rk validate` and `rk runs show` (those are M5/M6 surfaces; M2 lands only the declaration plus the unit-test assertion).

- [ ] **Step 1: Write the failing test**

`tests/unit/test_dab_per_trial_state_reset.py`:

```python
# ABOUTME: Unit test asserting the DAB adapter's per_trial_state_reset declaration.
# ABOUTME: AC-6 — must match §6.5 verbatim: agent_container, compose_services, host_workspace all True.


def test_dab_declares_all_three_reset_surfaces_true():
    from razorback.benchmarks.dab import per_trial_state_reset

    assert per_trial_state_reset == {
        "agent_container": True,
        "compose_services": True,
        "host_workspace": True,
    }
```

- [ ] **Step 2: Run test, confirm red**

```bash
uv run pytest tests/unit/test_dab_per_trial_state_reset.py -v
```

Expected: ImportError on `razorback.benchmarks.dab.reset` (the `__init__.py` from Task 2 already imports it, so the failing path is the missing module).

- [ ] **Step 3: Implement `reset.py`**

```python
# ABOUTME: DAB benchmark's per_trial_state_reset declaration (§6.5, AC-6).
# ABOUTME: Read by rk validate and rk runs show in later milestones; declared at the adapter root.

per_trial_state_reset: dict[str, bool] = {
    "agent_container": True,
    "compose_services": True,
    "host_workspace": True,
}
```

- [ ] **Step 4: Run test, confirm green**

```bash
uv run pytest tests/unit/test_dab_per_trial_state_reset.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/benchmarks/dab/reset.py tests/unit/test_dab_per_trial_state_reset.py
git commit -m "m2: DAB per_trial_state_reset triplet declared (AC-6)"
```

---

## Task 4: `prepare.py` — materialize harbor task dirs, exclude `ground_truth.csv` (AC-2)

**Files:**
- Create: `src/razorback/benchmarks/dab/prepare.py`
- Create: `tests/unit/test_dab_prepare.py`

`prepare.py` consumes the DAB data root layout — for `bookreview` that root is `/Users/clkao/git/dataagentbench/data/query_bookreview/`. It contains:

- `db_config.yaml` — safe to copy (the agent reads it)
- `db_description.txt` — safe (the agent reads it)
- `db_description_withhint.txt` — safe (optional, for hint mode)
- `query_dataset/` — safe (the SQLite + postgres source files the agent queries)
- `query1/`, `query2/`, `query3/` — each contains:
  - `query.json` — safe (the agent reads the question)
  - `validate.py` — **NOT** copied to the task dir (the verifier runs it inside the container via a bind mount of the dataset root; the agent must not see it)
  - `ground_truth.csv` — **NOT** copied (AC-2)

The function produces one harbor task dir per `(dataset, query_id)` under a caller-supplied root. Each task dir has the harbor layout discovered in `docs/pre-m1-findings.md`'s "Harbor API map":

```
<tasks_root>/bookreview-q1/
├── task.toml             ← [task].name = "razorback/bookreview-q1"
├── instruction.md        ← contents of query.json + db_description.txt
├── environment/Dockerfile
├── tests/test.sh         ← invokes razorback's verify.py against the bind-mounted dataset
└── workdir/              ← safe files only (no ground_truth.csv, no validate.py)
    ├── db_config.yaml
    ├── db_description.txt
    ├── query.json
    └── query_dataset/    ← copied or symlinked from the dataset root
```

The `workdir/` materialization happens before the container starts; harbor's docker env copies it into `/work` inside the container (or uses a bind mount). For M2 we **copy** (not symlink) `query_dataset/` into each task dir to keep the contract simple — `query_dataset/` is the same across the 3 bookreview queries, so for production scale a symlink will replace this; that's an M5 perf concern, not an M2 correctness concern.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_dab_prepare.py`:

```python
# ABOUTME: Unit tests for the DAB prepare module (§6.5).
# ABOUTME: AC-2 — ground_truth.csv must NOT appear in the materialized task workdir.

from pathlib import Path

import pytest

from razorback.benchmarks.dab.prepare import prepare_dataset_tasks


def _make_fixture_dataset(root: Path) -> Path:
    """Build a minimal query_bookreview-shaped fixture under root."""
    ds = root / "query_bookreview"
    (ds / "query_dataset").mkdir(parents=True)
    (ds / "query_dataset" / "review_query.db").write_bytes(b"sqlite-stub")
    (ds / "db_config.yaml").write_text("db_clients: {}\n")
    (ds / "db_description.txt").write_text("two-databases description")
    for qid in (1, 2):
        q = ds / f"query{qid}"
        q.mkdir()
        (q / "query.json").write_text(f'"question {qid}?"')
        (q / "validate.py").write_text("def validate(s): return True, 'ok'\n")
        (q / "ground_truth.csv").write_text(f"answer-{qid}\n")
    return ds


def test_prepare_excludes_ground_truth_csv(tmp_path):
    data_root = tmp_path / "data"
    _make_fixture_dataset(data_root)
    tasks_root = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tasks_root,
    )
    assert len(manifest) == 2
    for entry in manifest:
        task_dir = entry["task_dir"]
        # AC-2: no ground_truth.csv anywhere in the task tree.
        assert not list(task_dir.rglob("ground_truth.csv"))


def test_prepare_excludes_validate_py(tmp_path):
    """Negative correlate of AC-2: validate.py is also off-limits to the agent's workdir."""
    data_root = tmp_path / "data"
    _make_fixture_dataset(data_root)
    tasks_root = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tasks_root,
    )
    for entry in manifest:
        workdir = entry["task_dir"] / "workdir"
        assert not list(workdir.rglob("validate.py")), f"validate.py leaked into {workdir}"


def test_prepare_copies_safe_inputs(tmp_path):
    data_root = tmp_path / "data"
    _make_fixture_dataset(data_root)
    tasks_root = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tasks_root,
    )
    q1 = next(e for e in manifest if e["query_id"] == 1)["task_dir"]
    assert (q1 / "workdir" / "query.json").read_text() == '"question 1?"'
    assert (q1 / "workdir" / "db_config.yaml").exists()
    assert (q1 / "workdir" / "db_description.txt").exists()
    assert (q1 / "workdir" / "query_dataset" / "review_query.db").exists()


def test_prepare_writes_task_toml_and_dockerfile(tmp_path):
    data_root = tmp_path / "data"
    _make_fixture_dataset(data_root)
    tasks_root = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tasks_root,
    )
    q1 = next(e for e in manifest if e["query_id"] == 1)["task_dir"]
    task_toml = (q1 / "task.toml").read_text()
    assert 'razorback/bookreview-q1' in task_toml
    assert (q1 / "environment" / "Dockerfile").exists()
    assert (q1 / "tests" / "test.sh").exists()
    # Executable bit on test.sh.
    assert (q1 / "tests" / "test.sh").stat().st_mode & 0o111


def test_prepare_returns_manifest_with_task_name(tmp_path):
    data_root = tmp_path / "data"
    _make_fixture_dataset(data_root)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
    )
    names = sorted(e["task_name"] for e in manifest)
    assert names == ["bookreview-q1", "bookreview-q2"]


def test_prepare_rejects_missing_dataset(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    with pytest.raises(FileNotFoundError):
        prepare_dataset_tasks(
            data_root=data_root,
            dataset="bookreview",
            tasks_root=tmp_path / "tasks",
        )
```

- [ ] **Step 2: Run tests, confirm red**

```bash
uv run pytest tests/unit/test_dab_prepare.py -v
```

Expected: ImportError on `razorback.benchmarks.dab.prepare`.

- [ ] **Step 3: Implement `prepare.py`**

```python
# ABOUTME: DAB prepare — materialize one harbor task dir per (dataset, query_id) under tasks_root.
# ABOUTME: AC-2: ground_truth.csv (and validate.py) are NEVER copied into the agent's workdir.

import shutil
import stat
from pathlib import Path
from typing import TypedDict


class TaskManifestEntry(TypedDict):
    dataset: str
    query_id: int
    task_name: str
    task_dir: Path


# Files inside a query dir that are SAFE to copy to the agent's workdir.
_QUERY_SAFE = ("query.json",)
# Files inside a query dir that must NEVER be copied to the agent's workdir.
_QUERY_FORBIDDEN = ("ground_truth.csv", "validate.py", "__pycache__")
# Top-level safe entries.
_DATASET_SAFE = ("db_config.yaml", "db_description.txt", "db_description_withhint.txt", "query_dataset")


def prepare_dataset_tasks(
    *,
    data_root: Path,
    dataset: str,
    tasks_root: Path,
) -> list[TaskManifestEntry]:
    """Materialize harbor task dirs for every query in `dataset`.

    data_root: the DAB data root (e.g. `/Users/clkao/git/dataagentbench/data`).
    dataset:   short name, e.g. "bookreview" (resolved as `data_root / f"query_{dataset}"`).
    tasks_root: razorback-owned dir (must live under /Users/... for Colima); deleted and re-created.

    Returns one entry per query directory found.
    """
    data_root = Path(data_root)
    dataset_dir = data_root / f"query_{dataset}"
    if not dataset_dir.exists():
        raise FileNotFoundError(f"DAB dataset dir not found: {dataset_dir}")

    tasks_root = Path(tasks_root)
    if tasks_root.exists():
        shutil.rmtree(tasks_root)
    tasks_root.mkdir(parents=True)

    manifest: list[TaskManifestEntry] = []
    for query_dir in sorted(p for p in dataset_dir.iterdir() if p.is_dir() and p.name.startswith("query") and p.name != "query_dataset"):
        try:
            query_id = int(query_dir.name.removeprefix("query"))
        except ValueError:
            continue
        task_name = f"{dataset}-q{query_id}"
        task_dir = tasks_root / task_name
        _materialize_task_dir(
            task_name=task_name,
            dataset_dir=dataset_dir,
            query_dir=query_dir,
            task_dir=task_dir,
        )
        manifest.append({
            "dataset": dataset,
            "query_id": query_id,
            "task_name": task_name,
            "task_dir": task_dir,
        })
    return manifest


def _materialize_task_dir(
    *,
    task_name: str,
    dataset_dir: Path,
    query_dir: Path,
    task_dir: Path,
) -> None:
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(_task_toml(task_name))

    instruction = _instruction(query_dir=query_dir, dataset_dir=dataset_dir)
    (task_dir / "instruction.md").write_text(instruction)

    env_dir = task_dir / "environment"
    env_dir.mkdir()
    (env_dir / "Dockerfile").write_text(_dockerfile())

    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    test_sh = tests_dir / "test.sh"
    test_sh.write_text(_test_sh())
    test_sh.chmod(test_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    workdir = task_dir / "workdir"
    workdir.mkdir()
    for name in _DATASET_SAFE:
        src = dataset_dir / name
        if not src.exists():
            continue
        dst = workdir / name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    for name in _QUERY_SAFE:
        src = query_dir / name
        if src.exists():
            shutil.copy2(src, workdir / name)

    # AC-2 belt-and-braces: any forbidden file that somehow landed under workdir is removed.
    for forbidden in _QUERY_FORBIDDEN:
        for stray in workdir.rglob(forbidden):
            if stray.is_dir():
                shutil.rmtree(stray)
            else:
                stray.unlink()


def _task_toml(task_name: str) -> str:
    return f"""\
schema_version = "1.2"

[task]
name = "razorback/{task_name}"
description = "DAB {task_name} as a harbor task."
"""


def _instruction(*, query_dir: Path, dataset_dir: Path) -> str:
    query_text = (query_dir / "query.json").read_text()
    db_description = (dataset_dir / "db_description.txt").read_text()
    return (
        "# Task\n\n"
        f"Answer the following query using the databases described below.\n\n"
        f"## Query\n\n{query_text}\n\n"
        f"## Databases\n\n{db_description}\n\n"
        "## Output contract\n\n"
        "Write your final answer to `/work/answers.json` as a JSON object of the form\n"
        '`{\"answer\": \"<your answer as a single string>\"}`. The verifier reads this file.\n'
    )


def _dockerfile() -> str:
    # Minimal image: bookreview tasks read SQLite directly; postgres is out of M2 scope
    # (the nop agent never queries it). Future milestones will swap in DAB's full image.
    return (
        "FROM python:3.12-slim\n"
        "RUN apt-get update && apt-get install -y --no-install-recommends sqlite3 && rm -rf /var/lib/apt/lists/*\n"
        "WORKDIR /work\n"
        "CMD [\"sleep\", \"infinity\"]\n"
    )


def _test_sh() -> str:
    # tests/test.sh runs as the verifier. It invokes razorback's verify.py against a bind mount
    # of the dataset root (passed in via $DAB_DATASET_ROOT, set by the spec → JobConfig translator
    # in Task 7). The verify.py module then imports the dataset's validate.py from outside the
    # workdir (so it stays invisible to the agent).
    return (
        '#!/bin/sh\n'
        'set -eu\n'
        'mkdir -p /logs/verifier\n'
        ': "${DAB_DATASET_ROOT:?DAB_DATASET_ROOT must be set}"\n'
        ': "${DAB_DATASET:?DAB_DATASET must be set}"\n'
        ': "${DAB_QUERY_ID:?DAB_QUERY_ID must be set}"\n'
        'python /opt/razorback/verify.py \\\n'
        '  --dataset-root "$DAB_DATASET_ROOT" \\\n'
        '  --dataset "$DAB_DATASET" \\\n'
        '  --query-id "$DAB_QUERY_ID" \\\n'
        '  --answers /work/answers.json \\\n'
        '  --reward-out /logs/verifier/reward.json\n'
    )
```

- [ ] **Step 4: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_dab_prepare.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/benchmarks/dab/prepare.py tests/unit/test_dab_prepare.py
git commit -m "m2: prepare.py — materialize harbor task dirs without ground_truth.csv (AC-2)"
```

---

## Task 5: `verify.py` — read `answers.json`, emit harbor reward shape (AC-3)

**Files:**
- Create: `src/razorback/benchmarks/dab/verify.py`
- Create: `tests/unit/test_dab_verify.py`

`verify.py` is the script `tests/test.sh` invokes inside the container. It:

1. Reads `--answers /work/answers.json` (the agent's output); if missing or unparseable, the answer is `""`.
2. Imports `<dataset-root>/query_<dataset>/query<query_id>/validate.py` dynamically (mirrors `common_scaffold/validate/validate.py`).
3. Calls `validate_mod.validate(llm_answer)` → `(is_valid: bool, reason: str)`.
4. Writes `--reward-out` as `{"reward": 1.0}` (pass) or `{"reward": 0.0, "reason": "..."}` (fail) — the harbor reward shape: a JSON object with at least a `reward` key (see `VerifierResult.rewards: dict[str, float | int] | None` at `harbor.models.verifier.result`).

Per `docs/pre-m1-findings.md`'s "Per-trial reward contract", harbor accepts either `reward.txt` (single value) or `reward.json` (dict). We use `reward.json` so that the failure reason rides through to `JobResult.trial_results[i].verifier_result.rewards` for debugging; harbor `0.6.6`'s `VerifierResult.rewards` is `dict[str, float | int] | None`, so non-`reward` keys must be numeric. The `reason` lives in stderr / `test-stdout.txt`, not `rewards`.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_dab_verify.py`:

```python
# ABOUTME: Unit tests for the DAB verify module (§6.5, AC-3).
# ABOUTME: Reads answers.json, imports dataset validate.py, writes /logs/verifier/reward.json.

import json
from pathlib import Path

from razorback.benchmarks.dab.verify import emit_reward


def _make_fixture_dataset(root: Path) -> Path:
    ds = root / "query_bookreview"
    q1 = ds / "query1"
    q1.mkdir(parents=True)
    (q1 / "validate.py").write_text(
        "def validate(s):\n"
        "    return ('2020' in s, 'present' if '2020' in s else 'missing')\n"
    )
    return root


def test_emit_reward_writes_1_0_on_pass(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"answer": "the answer is the 2020s decade"}))
    reward_out = tmp_path / "reward.json"

    emit_reward(
        dataset_root=data_root,
        dataset="bookreview",
        query_id=1,
        answers_path=answers,
        reward_out=reward_out,
    )
    payload = json.loads(reward_out.read_text())
    assert payload == {"reward": 1.0}


def test_emit_reward_writes_0_0_on_fail(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"answer": "wrong"}))
    reward_out = tmp_path / "reward.json"

    emit_reward(
        dataset_root=data_root,
        dataset="bookreview",
        query_id=1,
        answers_path=answers,
        reward_out=reward_out,
    )
    payload = json.loads(reward_out.read_text())
    assert payload["reward"] == 0.0
    # Reason stays out of rewards (harbor's VerifierResult.rewards is dict[str, number]).
    assert all(isinstance(v, (int, float)) for v in payload.values())


def test_emit_reward_treats_missing_answers_as_empty(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    reward_out = tmp_path / "reward.json"

    emit_reward(
        dataset_root=data_root,
        dataset="bookreview",
        query_id=1,
        answers_path=tmp_path / "nope.json",
        reward_out=reward_out,
    )
    assert json.loads(reward_out.read_text())["reward"] == 0.0


def test_emit_reward_treats_malformed_answers_as_empty(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    answers = tmp_path / "answers.json"
    answers.write_text("not json")
    reward_out = tmp_path / "reward.json"

    emit_reward(
        dataset_root=data_root,
        dataset="bookreview",
        query_id=1,
        answers_path=answers,
        reward_out=reward_out,
    )
    assert json.loads(reward_out.read_text())["reward"] == 0.0
```

- [ ] **Step 2: Run tests, confirm red**

```bash
uv run pytest tests/unit/test_dab_verify.py -v
```

Expected: ImportError on `razorback.benchmarks.dab.verify`.

- [ ] **Step 3: Implement `verify.py`**

```python
# ABOUTME: DAB verifier — reads /work/answers.json, calls validate.py, writes reward.json.
# ABOUTME: §6.5 — emits harbor's per-task reward shape (dict at /logs/verifier/reward.json).

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def emit_reward(
    *,
    dataset_root: Path,
    dataset: str,
    query_id: int,
    answers_path: Path,
    reward_out: Path,
) -> None:
    """Compute and write the harbor-shaped reward file.

    The reward payload is `{"reward": 1.0}` on pass, `{"reward": 0.0}` on fail.
    Harbor's VerifierResult.rewards is `dict[str, float | int] | None`; the failure
    reason rides through stderr (so it lands in test-stdout.txt), not into rewards.
    """
    llm_answer = _read_answer(Path(answers_path))
    validate_fn = _load_validate(Path(dataset_root), dataset, query_id)

    is_valid, reason = validate_fn(llm_answer) if llm_answer else (False, "empty answer")
    payload = {"reward": 1.0 if is_valid else 0.0}
    Path(reward_out).parent.mkdir(parents=True, exist_ok=True)
    Path(reward_out).write_text(json.dumps(payload) + "\n")
    if not is_valid:
        sys.stderr.write(f"DAB verify: {dataset}/query{query_id} failed: {reason}\n")


def _read_answer(answers_path: Path) -> str:
    if not answers_path.exists():
        return ""
    try:
        raw = json.loads(answers_path.read_text())
    except json.JSONDecodeError:
        return ""
    if isinstance(raw, dict) and "answer" in raw:
        return str(raw["answer"])
    if isinstance(raw, str):
        return raw
    return ""


def _load_validate(dataset_root: Path, dataset: str, query_id: int):
    validate_py = dataset_root / f"query_{dataset}" / f"query{query_id}" / "validate.py"
    if not validate_py.exists():
        raise FileNotFoundError(f"validate.py not found: {validate_py}")
    spec = importlib.util.spec_from_file_location(
        f"_dab_validate_{dataset}_q{query_id}", str(validate_py)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--query-id", type=int, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--reward-out", type=Path, required=True)
    args = parser.parse_args()
    emit_reward(
        dataset_root=args.dataset_root,
        dataset=args.dataset,
        query_id=args.query_id,
        answers_path=args.answers,
        reward_out=args.reward_out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_dab_verify.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/benchmarks/dab/verify.py tests/unit/test_dab_verify.py
git commit -m "m2: verify.py — emit harbor reward shape against answers.json (AC-3)"
```

---

## Task 6: Spec schema extension — `DabBenchmarkBlock`

**Files:**
- Modify: `src/razorback/spec/schema.py` (extend `BenchmarkBlock` / add `DabBenchmarkBlock`)
- Create: `tests/unit/test_dab_spec_parse.py`

M1's `BenchmarkBlock` is permissive on `kind` (declared as `str`). M2 adds the `dab` kind with two extra required fields — `data_root: Path` and `datasets: list[str]` — and forbids `task_paths` (which is meaningful only for `kind: local`). The simplest way is a discriminated union: a `LocalBenchmarkBlock` + `DabBenchmarkBlock` with `kind` as a `Literal` discriminator, surfaced through a tagged union.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_dab_spec_parse.py`:

```python
# ABOUTME: Unit tests for the DAB extension of the spec schema.
# ABOUTME: AC-7 input shape: kind: dab, data_root: Path, datasets: list[str].

import pytest

from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text


VALID_DAB_SPEC = """\
version: 1
experiment: m2-bookreview-nop
agent:
  kind: nop
benchmark:
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets:
    - bookreview
trials: 1
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
"""


def test_parses_dab_benchmark_block():
    spec = parse_spec_text(VALID_DAB_SPEC)
    assert spec.benchmark.kind == "dab"
    assert str(spec.benchmark.data_root) == "/Users/clkao/git/dataagentbench/data"
    assert spec.benchmark.datasets == ["bookreview"]


def test_dab_rejects_unknown_subkey():
    bad = VALID_DAB_SPEC + "  task_paths: [a]\n"
    with pytest.raises(SpecError):
        parse_spec_text(bad)


def test_dab_requires_datasets():
    bad = VALID_DAB_SPEC.replace("  datasets:\n    - bookreview\n", "")
    with pytest.raises(SpecError):
        parse_spec_text(bad)


def test_local_benchmark_still_parses():
    """Negative correlate: M1 specs (kind: local) keep parsing unchanged."""
    spec = parse_spec_text(
        "version: 1\n"
        "experiment: m1\n"
        "agent:\n  kind: nop\n"
        "benchmark:\n  kind: local\n  task_paths: [examples/tasks/hello-world]\n"
    )
    assert spec.benchmark.kind == "local"
    assert [str(p) for p in spec.benchmark.task_paths] == ["examples/tasks/hello-world"]
```

- [ ] **Step 2: Run tests, confirm red**

```bash
uv run pytest tests/unit/test_dab_spec_parse.py -v
```

Expected: at least one assertion fails or pydantic accepts the unknown `task_paths`/missing `datasets` because M1's `BenchmarkBlock` is permissive.

- [ ] **Step 3: Extend `spec/schema.py`**

Replace the body of `src/razorback/spec/schema.py` with:

```python
# ABOUTME: Pydantic schema for the razorback spec.
# ABOUTME: Top-level forbids unknown keys; benchmark is a discriminated union (local | dab).

from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class AgentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str


class LocalBenchmarkBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["local"] = "local"
    task_paths: list[Path] = Field(default_factory=list)


class DabBenchmarkBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["dab"]
    data_root: Path
    datasets: list[str] = Field(min_length=1)


BenchmarkBlock = Annotated[
    Union[LocalBenchmarkBlock, DabBenchmarkBlock],
    Field(discriminator="kind"),
]


class ObserverBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["jsonl", "stdout"]
    path: str | None = None


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    experiment: str
    agent: AgentBlock
    benchmark: BenchmarkBlock
    trials: int = 1
    observers: list[ObserverBlock] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_dab_spec_parse.py tests/unit/test_spec_parse.py -v
```

Expected: 4 + 3 = 7 passed. The M1 tests still pass because `LocalBenchmarkBlock` keeps the same field shape.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/spec/schema.py tests/unit/test_dab_spec_parse.py
git commit -m "m2: spec schema — discriminated benchmark block (local | dab)"
```

---

## Task 7: Extend the harbor 0.6.6 translator — DAB fan-out, retry-zero, env bind (AC-4)

**Files:**
- Modify: `src/razorback/compat/harbor_0_6_6.py`
- Create: `tests/unit/test_dab_translator.py`

The translator now does three things for `benchmark.kind == "dab"`:

1. Call `prepare_dataset_tasks` for each named dataset, producing a list of harbor task dirs under a translator-supplied `tasks_root` (passed in by the run orchestrator; typically `run_dir / "tasks"`).
2. Build the `trial_name → (dataset, query_id)` map the aggregator needs (the prefix is `f"{dataset}-q{query_id}"`).
3. Construct a `JobConfig` with `retry=RetryConfig(max_retries=0)` (**AC-4**), `n_attempts=spec.trials`, one `TaskConfig` per generated task dir, and `verifier.env` carrying `DAB_DATASET_ROOT`, `DAB_DATASET`, `DAB_QUERY_ID`, plus a bind mount for the dataset root so `verify.py` can read the dataset's `validate.py`.

The `verifier.env` per-task differs by `(dataset, query_id)`. Harbor's `TaskConfig.verifier.env` is per-task; the translator stamps it accordingly.

The bind-mount approach for the verifier reading the harness `verify.py`: harbor's docker env doesn't auto-mount arbitrary host paths into the container. The simplest workaround that fits inside M2's "one dataset, real bookreview run" scope is to **copy** `verify.py` and a copy of the dataset's `validate.py` directories into the task dir under a path the verifier can reach (`/tests/verify.py`, `/tests/validate.py`), then have `tests/test.sh` invoke that. The dataset root bind mount is deferred to M5 (when 12 datasets justify the bind mount instead of 36 file copies).

For M2 the simpler shape — copy `verify.py` and per-query `validate.py` into the task's `tests/` dir, where harbor already auto-copies tests into `/tests/` — is what we ship. `validate.py` in `tests/` is invisible to the agent (which only sees `/work`), so AC-2's "the agent doesn't see validate.py" still holds.

Revisit Task 4's `prepare.py`: place a copy of the dataset's per-query `validate.py` into `<task_dir>/tests/validate.py`, AND copy `src/razorback/benchmarks/dab/verify.py` into `<task_dir>/tests/verify.py`. Then `tests/test.sh` becomes:

```sh
#!/bin/sh
set -eu
mkdir -p /logs/verifier
python /tests/verify.py \
  --validate-py /tests/validate.py \
  --answers /work/answers.json \
  --reward-out /logs/verifier/reward.json
```

This avoids the bind-mount question entirely for M2. Verifier args drop from `(--dataset-root, --dataset, --query-id)` to `--validate-py` (a direct file path) — simpler and self-contained. We rewrite Task 4's `prepare.py` and Task 5's `verify.py` here, behind a failing translator test.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_dab_translator.py`:

```python
# ABOUTME: Unit tests for the DAB extensions of the harbor 0.6.6 translator.
# ABOUTME: AC-4 retry-zero; task fan-out; trial_name_map shape.

from pathlib import Path

import pytest
from harbor.models.job.config import JobConfig

from razorback.compat.harbor_0_6_6 import spec_to_job_config
from razorback.spec.parse import parse_spec_text


def _make_fixture_dataset(root: Path) -> Path:
    ds = root / "query_bookreview"
    (ds / "query_dataset").mkdir(parents=True)
    (ds / "query_dataset" / "review_query.db").write_bytes(b"sqlite-stub")
    (ds / "db_config.yaml").write_text("db_clients: {}\n")
    (ds / "db_description.txt").write_text("desc")
    for qid in (1, 2, 3):
        q = ds / f"query{qid}"
        q.mkdir()
        (q / "query.json").write_text(f'"Q{qid}?"')
        (q / "validate.py").write_text(f"def validate(s): return ('{qid}' in s, 'ok')\n")
        (q / "ground_truth.csv").write_text(f"{qid}\n")
    return root


DAB_SPEC_TEMPLATE = """\
version: 1
experiment: m2-bookreview-nop
agent:
  kind: nop
benchmark:
  kind: dab
  data_root: {data_root}
  datasets:
    - bookreview
trials: 5
"""


def test_translator_sets_retry_max_retries_zero(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    spec = parse_spec_text(DAB_SPEC_TEMPLATE.format(data_root=data_root))
    cfg, _trial_map = spec_to_job_config(
        spec,
        job_name="abc1234567890def",
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
    )
    # AC-4: retry-zero so first-attempt failures don't get re-counted as passes.
    assert cfg.retry.max_retries == 0


def test_translator_fans_out_one_task_per_query(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    spec = parse_spec_text(DAB_SPEC_TEMPLATE.format(data_root=data_root))
    cfg, _ = spec_to_job_config(
        spec,
        job_name="abc1234567890def",
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
    )
    task_names = sorted(Path(tc.path).name for tc in cfg.tasks)
    assert task_names == ["bookreview-q1", "bookreview-q2", "bookreview-q3"]
    assert isinstance(cfg, JobConfig)


def test_translator_returns_trial_name_map(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    spec = parse_spec_text(DAB_SPEC_TEMPLATE.format(data_root=data_root))
    _cfg, trial_name_map = spec_to_job_config(
        spec,
        job_name="abc1234567890def",
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
    )
    assert trial_name_map == {
        "bookreview-q1": ("bookreview", 1),
        "bookreview-q2": ("bookreview", 2),
        "bookreview-q3": ("bookreview", 3),
    }


def test_translator_keeps_n_attempts_equal_to_trials(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    spec = parse_spec_text(DAB_SPEC_TEMPLATE.format(data_root=data_root))
    cfg, _ = spec_to_job_config(
        spec,
        job_name="abc1234567890def",
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
    )
    assert cfg.n_attempts == 5
    assert cfg.agents[0].name == "nop"


def test_translator_still_accepts_local_benchmark(tmp_path):
    """The M1 path must keep working."""
    spec = parse_spec_text(
        "version: 1\nexperiment: x\nagent:\n  kind: nop\n"
        "benchmark:\n  kind: local\n  task_paths: [examples/tasks/hello-world]\n"
        "trials: 1\n"
    )
    cfg, trial_map = spec_to_job_config(
        spec, job_name="x" * 16, jobs_dir=tmp_path / "jobs", tasks_root=tmp_path / "tasks"
    )
    assert trial_map == {}
    assert len(cfg.tasks) == 1
```

- [ ] **Step 2: Run tests, confirm red**

```bash
uv run pytest tests/unit/test_dab_translator.py -v
```

Expected: TypeError on `spec_to_job_config()` (no `tasks_root` kwarg) or it returns a `JobConfig` rather than a tuple.

- [ ] **Step 3: Extend the translator**

Replace the body of `src/razorback/compat/harbor_0_6_6.py` with:

```python
# ABOUTME: Spec → harbor 0.6.6 JobConfig translator (§6.1).
# ABOUTME: Supports agent.kind=nop and benchmark.kind ∈ {local, dab}.

from pathlib import Path

from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig, RetryConfig
from harbor.models.trial.config import AgentConfig, TaskConfig, VerifierConfig

from razorback.benchmarks.dab.prepare import prepare_dataset_tasks
from razorback.errors import SpecError
from razorback.spec.schema import DabBenchmarkBlock, LocalBenchmarkBlock, Spec


def spec_to_job_config(
    spec: Spec,
    *,
    job_name: str,
    jobs_dir: Path,
    tasks_root: Path | None = None,
) -> tuple[JobConfig, dict[str, tuple[str, int]]]:
    """Translate a parsed spec into a harbor JobConfig and a trial_name_map.

    Returns a 2-tuple: (JobConfig, trial_name_map). The map keys are the trial_name
    prefixes harbor will assign (`<task_name>__<uuid7>`); values are (dataset, query_id).
    For non-DAB benchmarks the map is empty.

    `tasks_root` is required for DAB specs (where prepared task dirs land). The run
    orchestrator passes `run_dir / "tasks"`. M1 callers omit it; the local path uses
    only `spec.benchmark.task_paths`.
    """
    if spec.agent.kind != "nop":
        raise SpecError(f"agent.kind=nop only (got {spec.agent.kind!r}); ClaudeCliAgent lands in M3.")

    if isinstance(spec.benchmark, LocalBenchmarkBlock):
        return _build_local(spec=spec, job_name=job_name, jobs_dir=jobs_dir), {}

    if isinstance(spec.benchmark, DabBenchmarkBlock):
        if tasks_root is None:
            raise SpecError("DAB specs require tasks_root (the run orchestrator passes it).")
        return _build_dab(
            spec=spec,
            job_name=job_name,
            jobs_dir=jobs_dir,
            tasks_root=Path(tasks_root),
        )

    raise SpecError(f"unsupported benchmark block: {type(spec.benchmark).__name__}")


def _build_local(*, spec: Spec, job_name: str, jobs_dir: Path) -> JobConfig:
    assert isinstance(spec.benchmark, LocalBenchmarkBlock)
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[AgentConfig(name=AgentName.NOP.value)],
        tasks=[TaskConfig(path=Path(p).resolve()) for p in spec.benchmark.task_paths],
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
    )


def _build_dab(
    *,
    spec: Spec,
    job_name: str,
    jobs_dir: Path,
    tasks_root: Path,
) -> tuple[JobConfig, dict[str, tuple[str, int]]]:
    assert isinstance(spec.benchmark, DabBenchmarkBlock)
    manifest_all: list[dict] = []
    for dataset in spec.benchmark.datasets:
        manifest_all.extend(
            prepare_dataset_tasks(
                data_root=Path(spec.benchmark.data_root),
                dataset=dataset,
                tasks_root=tasks_root / dataset,
            )
        )
    tasks = [TaskConfig(path=entry["task_dir"]) for entry in manifest_all]
    trial_name_map = {
        entry["task_name"]: (entry["dataset"], entry["query_id"]) for entry in manifest_all
    }
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[AgentConfig(name=AgentName.NOP.value)],
        tasks=tasks,
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
    ), trial_name_map
```

- [ ] **Step 4: Rewrite `prepare.py`'s test.sh emission and add `validate.py`/`verify.py` copies**

Replace `_test_sh()` in `src/razorback/benchmarks/dab/prepare.py` with:

```python
def _test_sh() -> str:
    # The verifier reads /work/answers.json, calls /tests/verify.py with the per-query validate.py
    # already copied alongside it. No env vars, no bind mounts — everything the verifier needs is
    # in /tests/ (where harbor auto-copies the task's tests/ dir).
    return (
        '#!/bin/sh\n'
        'set -eu\n'
        'mkdir -p /logs/verifier\n'
        'python /tests/verify.py \\\n'
        '  --validate-py /tests/validate.py \\\n'
        '  --answers /work/answers.json \\\n'
        '  --reward-out /logs/verifier/reward.json\n'
    )
```

Then extend `_materialize_task_dir` to also copy `validate.py` and `verify.py` into `tests/`:

```python
def _materialize_task_dir(
    *,
    task_name: str,
    dataset_dir: Path,
    query_dir: Path,
    task_dir: Path,
) -> None:
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(_task_toml(task_name))

    instruction = _instruction(query_dir=query_dir, dataset_dir=dataset_dir)
    (task_dir / "instruction.md").write_text(instruction)

    env_dir = task_dir / "environment"
    env_dir.mkdir()
    (env_dir / "Dockerfile").write_text(_dockerfile())

    tests_dir = task_dir / "tests"
    tests_dir.mkdir()

    # The verifier and the dataset's validate.py live in /tests/ inside the container.
    # /tests/ is NOT visible to the agent (it only sees /work/), so this preserves AC-2.
    import razorback.benchmarks.dab.verify as verify_module
    shutil.copy2(Path(verify_module.__file__), tests_dir / "verify.py")
    shutil.copy2(query_dir / "validate.py", tests_dir / "validate.py")

    test_sh = tests_dir / "test.sh"
    test_sh.write_text(_test_sh())
    test_sh.chmod(test_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    workdir = task_dir / "workdir"
    workdir.mkdir()
    for name in _DATASET_SAFE:
        src = dataset_dir / name
        if not src.exists():
            continue
        dst = workdir / name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    for name in _QUERY_SAFE:
        src = query_dir / name
        if src.exists():
            shutil.copy2(src, workdir / name)

    for forbidden in _QUERY_FORBIDDEN:
        for stray in workdir.rglob(forbidden):
            if stray.is_dir():
                shutil.rmtree(stray)
            else:
                stray.unlink()
```

- [ ] **Step 5: Rewrite `verify.py` to accept `--validate-py`**

Replace the body of `src/razorback/benchmarks/dab/verify.py` with:

```python
# ABOUTME: DAB verifier — reads /work/answers.json, calls a per-query validate.py, writes reward.json.
# ABOUTME: §6.5 — emits harbor's per-task reward shape (dict at /logs/verifier/reward.json).

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def emit_reward(
    *,
    validate_py: Path,
    answers_path: Path,
    reward_out: Path,
) -> None:
    """Compute and write the harbor-shaped reward file.

    `validate_py` points at the dataset's per-query validate.py. The dataset's
    ground_truth lives inside that module's source (the DAB datasets ship validate.py
    with the ground truth inlined as a Python literal; ground_truth.csv is only used
    by the displayed-on-failure reason and is never read by the validator itself).
    """
    llm_answer = _read_answer(Path(answers_path))
    validate_fn = _load_validate(Path(validate_py))

    is_valid, reason = validate_fn(llm_answer) if llm_answer else (False, "empty answer")
    payload = {"reward": 1.0 if is_valid else 0.0}
    Path(reward_out).parent.mkdir(parents=True, exist_ok=True)
    Path(reward_out).write_text(json.dumps(payload) + "\n")
    if not is_valid:
        sys.stderr.write(f"DAB verify ({validate_py}): {reason}\n")


def _read_answer(answers_path: Path) -> str:
    if not answers_path.exists():
        return ""
    try:
        raw = json.loads(answers_path.read_text())
    except json.JSONDecodeError:
        return ""
    if isinstance(raw, dict) and "answer" in raw:
        return str(raw["answer"])
    if isinstance(raw, str):
        return raw
    return ""


def _load_validate(validate_py: Path):
    if not validate_py.exists():
        raise FileNotFoundError(f"validate.py not found: {validate_py}")
    spec = importlib.util.spec_from_file_location("_dab_validate", str(validate_py))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-py", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--reward-out", type=Path, required=True)
    args = parser.parse_args()
    emit_reward(
        validate_py=args.validate_py,
        answers_path=args.answers,
        reward_out=args.reward_out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Update Task 5's tests to the new signature**

Replace the contents of `tests/unit/test_dab_verify.py`:

```python
# ABOUTME: Unit tests for the DAB verify module (§6.5, AC-3).
# ABOUTME: Reads answers.json, imports per-query validate.py, writes /logs/verifier/reward.json.

import json
from pathlib import Path

from razorback.benchmarks.dab.verify import emit_reward


def _validate_py(root: Path) -> Path:
    p = root / "validate.py"
    p.write_text(
        "def validate(s):\n"
        "    return ('2020' in s, 'present' if '2020' in s else 'missing')\n"
    )
    return p


def test_emit_reward_writes_1_0_on_pass(tmp_path):
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"answer": "the answer is the 2020s decade"}))
    reward_out = tmp_path / "reward.json"
    emit_reward(validate_py=_validate_py(tmp_path), answers_path=answers, reward_out=reward_out)
    assert json.loads(reward_out.read_text()) == {"reward": 1.0}


def test_emit_reward_writes_0_0_on_fail(tmp_path):
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"answer": "wrong"}))
    reward_out = tmp_path / "reward.json"
    emit_reward(validate_py=_validate_py(tmp_path), answers_path=answers, reward_out=reward_out)
    payload = json.loads(reward_out.read_text())
    assert payload["reward"] == 0.0
    assert all(isinstance(v, (int, float)) for v in payload.values())


def test_emit_reward_treats_missing_answers_as_empty(tmp_path):
    reward_out = tmp_path / "reward.json"
    emit_reward(
        validate_py=_validate_py(tmp_path),
        answers_path=tmp_path / "nope.json",
        reward_out=reward_out,
    )
    assert json.loads(reward_out.read_text())["reward"] == 0.0


def test_emit_reward_treats_malformed_answers_as_empty(tmp_path):
    answers = tmp_path / "answers.json"
    answers.write_text("not json")
    reward_out = tmp_path / "reward.json"
    emit_reward(validate_py=_validate_py(tmp_path), answers_path=answers, reward_out=reward_out)
    assert json.loads(reward_out.read_text())["reward"] == 0.0
```

- [ ] **Step 7: Update the M1 translator caller in `run.py` to unpack the tuple**

In `src/razorback/run.py`, locate the line:

```python
job_config = spec_to_job_config(spec, job_name=job_name, jobs_dir=run_dir.parent)
```

Replace with:

```python
tasks_root = run_dir / "tasks"
job_config, trial_name_map = spec_to_job_config(
    spec, job_name=job_name, jobs_dir=run_dir.parent, tasks_root=tasks_root
)
```

(`trial_name_map` is used by Task 9; for M1's local path it is `{}` and falls through harmlessly.)

- [ ] **Step 8: Run the full unit suite, confirm green**

```bash
uv run pytest tests/unit -v
```

Expected: every previous unit test plus the new DAB tests pass. The new prepare tests need to be updated to expect `tests/validate.py` and `tests/verify.py` in the task dir — go back to `tests/unit/test_dab_prepare.py` and add one more assertion at the end of `test_prepare_writes_task_toml_and_dockerfile`:

```python
    # New: validate.py and verify.py are placed in /tests/ (invisible to the agent under /work).
    assert (q1 / "tests" / "validate.py").exists()
    assert (q1 / "tests" / "verify.py").exists()
```

Re-run, expected: every test passes.

- [ ] **Step 9: Commit**

```bash
git add src/razorback/compat/harbor_0_6_6.py src/razorback/benchmarks/dab/prepare.py src/razorback/benchmarks/dab/verify.py src/razorback/run.py tests/unit/test_dab_translator.py tests/unit/test_dab_verify.py tests/unit/test_dab_prepare.py
git commit -m "m2: translator extends to DAB — retry-zero, task fan-out, trial map (AC-4)"
```

---

## Task 8: Author `examples/specs/bookreview-nop.yaml`

**Files:**
- Create: `examples/specs/bookreview-nop.yaml`

- [ ] **Step 1: Write the M2 acceptance spec**

```yaml
version: 1
experiment: m2-bookreview-nop
agent:
  kind: nop
benchmark:
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets:
    - bookreview
trials: 1
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
```

`trials: 1` keeps the CI/integration cost bounded; the aggregator math (AC-1) is already proven for n>1 by Task 2.

- [ ] **Step 2: Smoke-parse**

```bash
uv run python -c "from razorback.spec.parse import parse_spec_file; print(parse_spec_file('examples/specs/bookreview-nop.yaml'))"
```

Expected: prints a populated `Spec(...)` repr without raising.

- [ ] **Step 3: Commit**

```bash
git add examples/specs/bookreview-nop.yaml
git commit -m "m2: examples/specs/bookreview-nop.yaml — acceptance input"
```

---

## Task 9: Wire the run orchestrator to call the aggregator post-run

**Files:**
- Modify: `src/razorback/run.py`

When the spec's benchmark is DAB, after harbor returns the `JobResult` we call `aggregate_job_result(result.trial_results, trial_name_map, run_dir / "summary.json")` instead of the M1 stub summary. The M1 local path keeps writing the M1 summary.

- [ ] **Step 1: Modify `_execute_run_async`**

In `src/razorback/run.py`, locate the block that writes `summary.json` (the last few lines of `_execute_run_async`). Replace with:

```python
    from razorback.spec.schema import DabBenchmarkBlock
    if isinstance(spec.benchmark, DabBenchmarkBlock):
        from razorback.benchmarks.dab.aggregate import aggregate_job_result
        aggregate_job_result(
            trial_results=result.trial_results,
            trial_name_map=trial_name_map,
            out_path=run_dir / "summary.json",
        )
    else:
        summary = {
            "experiment": spec.experiment,
            "job_name": job_name,
            "n_total_trials": result.n_total_trials,
            "n_completed_trials": result.stats.n_completed_trials,
            "n_errored_trials": result.stats.n_errored_trials,
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
```

- [ ] **Step 2: Sanity-import**

```bash
uv run python -c "from razorback.run import execute_run; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/razorback/run.py
git commit -m "m2: orchestrator dispatches DAB aggregator when benchmark.kind == dab"
```

---

## Task 10: Cross-test the aggregator against a real (mocked) JobResult

**Files:**
- Modify: `tests/unit/test_dab_aggregate.py` (append)

Task 2 hit the aggregator's `aggregate_synthetic` path. The real path (`aggregate_job_result`) takes a sequence of `TrialResult`-shaped objects and a `trial_name_map`. We assert it produces the same golden as Task 2 when fed equivalent records.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_dab_aggregate.py`:

```python
class _StubVerifier:
    def __init__(self, reward: float) -> None:
        self.rewards = {"reward": reward}


class _StubTrial:
    def __init__(self, trial_name: str, reward: float) -> None:
        self.trial_name = trial_name
        self.verifier_result = _StubVerifier(reward)


def test_aggregate_job_result_uses_trial_name_map_to_pair(tmp_path):
    from razorback.benchmarks.dab.aggregate import aggregate_job_result

    trial_name_map = {
        "bookreview-q1": ("bookreview", 1),
        "bookreview-q2": ("bookreview", 2),
        "bookreview-q3": ("bookreview", 3),
    }
    trials = []
    rows = json.loads((FIXTURES / "synthetic_trial_results.json").read_text())
    for row in rows:
        trials.append(_StubTrial(row["trial_name"], row["rewards"]["reward"]))

    out = tmp_path / "summary.json"
    aggregate_job_result(trial_results=trials, trial_name_map=trial_name_map, out_path=out)
    got = json.loads(out.read_text())
    expected = json.loads((FIXTURES / "golden_summary.json").read_text())
    assert got == expected


def test_aggregate_job_result_handles_missing_verifier_result(tmp_path):
    """A trial that errored before verifier emission counts as 0 reward."""
    from razorback.benchmarks.dab.aggregate import aggregate_job_result

    class _ErroredTrial:
        trial_name = "bookreview-q1__zzzz001"
        verifier_result = None

    out = tmp_path / "summary.json"
    aggregate_job_result(
        trial_results=[_ErroredTrial()],
        trial_name_map={"bookreview-q1": ("bookreview", 1)},
        out_path=out,
    )
    got = json.loads(out.read_text())
    assert got["datasets"]["bookreview"]["queries"][0]["n_correct"] == 0
```

- [ ] **Step 2: Run, confirm pass**

```bash
uv run pytest tests/unit/test_dab_aggregate.py -v
```

Expected: 4 passed (2 from Task 2 + 2 new).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_dab_aggregate.py
git commit -m "m2: aggregate_job_result cross-test against synthetic + missing-verifier"
```

---

## Task 11: Integration test — `rk run examples/specs/bookreview-nop.yaml` end-to-end (AC-7)

**Files:**
- Create: `tests/integration/test_rk_run_bookreview_nop.py`

This is the AC-7 harness. The nop agent never writes `/work/answers.json`, so the verifier reads an empty answer and emits `{"reward": 0.0}` for every trial. The aggregator then writes a `summary.json` whose `stratified_pass_at_1: 0.0` and whose per-query pass@1 values are all `0.0`. AC-7 asserts the field **exists and is numeric**, not its score.

The test takes ~3 minutes (3 queries × 1 trial × 1 dockerized verifier each). Mark it with the existing `pytest` integration discipline (no extra marker — `tests/integration/` is collected separately by `testpaths` semantics).

- [ ] **Step 1: Write the failing integration test**

```python
# ABOUTME: End-to-end test for `rk run examples/specs/bookreview-nop.yaml`.
# ABOUTME: AC-7: summary.json carries stratified pass@1 (numeric) against the real bookreview dataset.

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "examples" / "specs" / "bookreview-nop.yaml"
DAB_DATA = Path("/Users/clkao/git/dataagentbench/data/query_bookreview")


@pytest.fixture
def runs_root(colima_safe_tmp_path):
    return colima_safe_tmp_path / "_runs"


@pytest.mark.skipif(not DAB_DATA.exists(), reason="DAB bookreview dataset not present")
def test_rk_run_bookreview_nop_writes_stratified_summary(runs_root):
    env = {**os.environ}
    result = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(SPEC), "--runs-dir", str(runs_root)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"

    experiment_dir = runs_root / "m2-bookreview-nop"
    run_dirs = list(experiment_dir.iterdir())
    assert len(run_dirs) == 1, run_dirs
    run_dir = run_dirs[0]

    summary_path = run_dir / "summary.json"
    assert summary_path.is_file(), f"missing summary.json in {run_dir}"
    summary = json.loads(summary_path.read_text())

    # AC-7: stratified pass@1 line exists and is numeric.
    assert "stratified_pass_at_1" in summary
    assert isinstance(summary["stratified_pass_at_1"], (int, float))

    # The nop agent always answers wrong, so every query's pass@1 is 0.0.
    book = summary["datasets"]["bookreview"]
    assert book["n_queries"] == 3
    for q in book["queries"]:
        assert q["pass_at_1"] == 0.0


@pytest.mark.skipif(not DAB_DATA.exists(), reason="DAB bookreview dataset not present")
def test_rk_run_bookreview_nop_preserves_run_dir_layout(runs_root):
    env = {**os.environ}
    result = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(SPEC), "--runs-dir", str(runs_root)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    run_dir = next((runs_root / "m2-bookreview-nop").iterdir())

    # M1's run-dir layout still holds.
    for name in ("spec.frozen.yaml", "manifest.json", "events.jsonl", "summary.json", "lock.json"):
        assert (run_dir / name).is_file(), f"missing {name}"
    # M2-specific: the materialized tasks_root.
    assert (run_dir / "tasks" / "bookreview" / "bookreview-q1" / "task.toml").is_file()
    assert not list((run_dir / "tasks").rglob("ground_truth.csv")), "ground_truth.csv leaked into task dirs"
```

- [ ] **Step 2: Run test**

```bash
uv run pytest tests/integration/test_rk_run_bookreview_nop.py -v -s
```

Expected on first run: PASS (verifier emits 0 for the empty answer; aggregator writes a numeric summary). If it fails, the failure is a real M2 bug — fix the right module, not the test.

Known issues to watch for:
- `RewardFileNotFoundError` from harbor: `tests/test.sh` didn't drop `reward.json`. Check `chmod +x` on `tests/test.sh` (Task 4 / Task 7).
- Verifier crash: usually means `python /tests/verify.py` exited non-zero. Re-run with `-s`, read `run_dir / "<trial>" / "verifier" / "test-stdout.txt"`.
- Summary missing `stratified_pass_at_1`: `aggregate_job_result` wasn't reached. Check `run.py`'s `isinstance(spec.benchmark, DabBenchmarkBlock)` branch.
- Task name parsing wrong: harbor's task_name comes from `[task].name` in task.toml after the `/`. Confirm `prepare.py`'s `_task_toml` emits `razorback/bookreview-q1`, and `harbor.models.trial.config.TrialConfig.generate_trial_name` truncates at 32 chars (our prefixes are 14 chars, safe).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_rk_run_bookreview_nop.py
git commit -m "m2: integration test — rk run bookreview-nop end-to-end (AC-7)"
```

---

## Task 12: AC-5 grep gate — `aggregate.py` does not read `stats.evals`

**Files:**
- Create: `tests/unit/test_dab_aggregate_grep.py`

The M2 entity body's AC-5 names a literal code-level check (`grep -n 'stats\.evals' src/razorback/benchmarks/dab/aggregate.py` must return no matches). Encoding it as a pytest test keeps the assertion permanent — a regression would surface in CI rather than someone running grep.

- [ ] **Step 1: Write the test**

`tests/unit/test_dab_aggregate_grep.py`:

```python
# ABOUTME: AC-5 grep gate — aggregate.py never reads JobResult.stats.evals.
# ABOUTME: §6.5: harbor's JobStats.evals is a per-dataset micro-average, not what DAB needs.

import re
from pathlib import Path

import razorback.benchmarks.dab.aggregate as aggregate_module


def test_aggregate_does_not_reference_stats_evals():
    src = Path(aggregate_module.__file__).read_text()
    # No occurrence of `stats.evals` anywhere in the module source.
    assert not re.search(r"stats\.evals", src), "aggregate.py must not read JobStats.evals (AC-5)"
    # Defensive: the literal string `evals` should also not appear (no near-misses).
    assert "evals" not in src
```

- [ ] **Step 2: Run, confirm pass**

```bash
uv run pytest tests/unit/test_dab_aggregate_grep.py -v
```

Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_dab_aggregate_grep.py
git commit -m "m2: AC-5 grep gate — aggregator stays off JobStats.evals"
```

---

## Task 13: Final acceptance — run the §8.M2 command from a clean tree

**Files:** none.

- [ ] **Step 1: Run the acceptance command**

```bash
uv run rk run examples/specs/bookreview-nop.yaml
```

Expected:
- Exit code 0 (`echo $?` confirms).
- Stdout contains one bracketed line per fired event in fire order (across 3 tasks).
- `_runs/m2-bookreview-nop/<job_name>/summary.json` exists.
- `jq '.stratified_pass_at_1, .datasets.bookreview.queries[].pass_at_1' summary.json` returns four `0.0` values (one stratified + one per query).
- `jq '.datasets.bookreview.n_queries' summary.json` returns `3`.

- [ ] **Step 2: Run the full test suite**

```bash
uv run pytest -v
```

Expected: every test from M1 and M2 green. Pristine output — no `pydantic` deprecation warnings (the schema rewrite is plain pydantic 2), no "coroutine was never awaited" lines. Per CL's rules, "test output MUST BE PRISTINE TO PASS".

- [ ] **Step 3: No commit (acceptance run only)**

---

## Task 14: Cross-reference plan from the M2 entity body

**Files:**
- Modify: `docs/razorback-implementation/m2-dab-bookreview.md` — Test plan section only

- [ ] **Step 1: Append a single cross-reference line to the Test plan section**

Locate the `## Test plan` section in `docs/razorback-implementation/m2-dab-bookreview.md`. After the `Acceptance command` bullet, append exactly:

```
- **Implementation plan:** `docs/razorback-implementation/plans/m2-dab-bookreview.md`.
```

Do not change the frontmatter; do not rewrite the Test plan section; do not paraphrase the existing bullets.

- [ ] **Step 2: Commit**

```bash
git add docs/razorback-implementation/m2-dab-bookreview.md
git commit -m "m2: cross-reference implementation plan from entity Test plan"
```

---

## Self-review notes

- **Spec coverage:** AC-1 (Tasks 1, 2), AC-2 (Task 4, re-asserted after Task 7's prepare rewrite), AC-3 (Tasks 5, 7), AC-4 (Task 7), AC-5 (Tasks 2, 12), AC-6 (Task 3), AC-7 (Tasks 6, 7, 8, 9, 11). Every AC is implemented by at least one task and asserted by at least one test.
- **Riskiest contract first:** Task 1 — the aggregator's golden math — precedes every wiring task. If `pass@1` math is wrong, no later task lands.
- **No placeholders:** every step shows file contents, exact commands, and the expected outcome. The single `... existing content ...`-style elision is the `_materialize_task_dir` rewrite in Task 7 Step 4, which gives the full function body to copy.
- **Type consistency:** `aggregate_synthetic(rows, out_path)`, `aggregate_job_result(trial_results, trial_name_map, out_path)`, `prepare_dataset_tasks(*, data_root, dataset, tasks_root)`, `emit_reward(*, validate_py, answers_path, reward_out)`, `spec_to_job_config(spec, *, job_name, jobs_dir, tasks_root) → (JobConfig, dict)`, `per_trial_state_reset: dict[str, bool]` are used consistently across tasks 1–14. The translator's return signature changes from M1's `JobConfig` to M2's `(JobConfig, dict)` — Task 7 Step 7 updates the M1 caller in `run.py`.
- **TDD discipline:** every behavior task (1+2, 3, 4, 5, 6, 7, 10, 11, 12) writes a failing test, runs it red, then makes it green. Tasks 8, 9, 13, 14 are scaffolding/wiring/docs and don't require their own dedicated unit test (each is exercised by tests in sibling tasks).
- **Commit cadence:** one focused commit per task, format `m2: <summary>`.
- **DAB on-disk reality check:** the plan reads from `/Users/clkao/git/dataagentbench/data/query_bookreview/{query1,query2,query3,query_dataset}/` — confirmed by `ls` during pre-flight (Task 0). The §6.5 design wording ("ground_truth.csv excluded") matches the on-disk file `ground_truth.csv` in each `queryN/` subdir. The §6.5 aggregator wording ("reads `JobResult.trial_results`") matches harbor 0.6.6's `JobResult.trial_results: list[TrialResult]` (confirmed via `harbor.models.trial.result.TrialResult`). No divergence requiring escalation.
