# swe-bench-pro Example Spec + Scoring-Strata Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-facing `examples/specs/swe-bench-pro-spacedock-codex.yaml` (schema-valid `spacedock_solver`/`runtime: codex` agent, SWE-tuned budget, hydration-prereq header note, freezes offline) and prove the view-manifest-driven aggregator stratifies real long swe-bench-pro task slugs into distinct per-task query cells.

**Architecture:** Two surfaces, no production-code change. (1) A new example spec YAML mirroring `examples/specs/dabstep-claude-harbor.yaml`'s `spacedock_solver` shape, swapped to `runtime: codex` + the existing `codex-benchmark-solver` workflow, with a swe-tuned turn/timeout budget and an ABOUTME hydration-prereq note. (2) A fixture-backed unit test that builds a synthetic run dir with `view_manifest.json` sidecars and realistic LONG swe-bench-pro trial-dir names, runs `aggregate_summary`, and asserts `summary.json`'s `swe-bench-pro` stratum carries one query cell per task slug — exercising the real `trial_dir.name.split("__")[0] == view_dir.name[:32].rstrip("_-")` join key so long/`__`-bearing slugs do NOT collapse to `dataset="default"`.

**Tech Stack:** Python 3, pytest, `uv run`, Typer CLI (`rk`), pydantic spec schema, YAML.

## Global Constraints

- Spec source of truth: `docs/razorback-implementation/swe-bench-pro-example-spec-scoring-strata.md` (3 ACs, each with a `Verified by:` clause). Design §: `docs/superpowers/specs/2026-06-24-swe-bench-pro-on-harbor-design.md` (E3, lines 133-148).
- The agent block MUST be `kind: spacedock_solver` / `runtime: codex`. `CodexAgentBlock` (`src/razorback/spec/schema.py:49-89`) has NO `solver_workflow`/`max_turns`; those live only on `SpacedockSolverAgentBlock` (`schema.py:92-119`).
- Dataset ref form is `scale-ai/swe-bench-pro@<ref>`. Offline placeholder `@latest` (see OPEN CAPTAIN DECISIONS); `PackageReference.parse` validates the `<org>/<name>@<ref>` form (design doc lines 33-37).
- SWE-tuned budget MUST sit ABOVE the 1200s codex default (`spider2-dbt-harbor-codex.yaml` uses `override_timeout_sec: 1200`). Plan values: `max_turns: 400`, `override_timeout_sec: 5400`, `max_timeout_sec: 7200`. `max_timeout_sec >= override_timeout_sec` is schema-enforced (`schema.py:122-132`).
- The solver workflow dir `./examples/solver_workflows/codex-benchmark-solver` MUST exist (verified live at plan time — it does).
- Committed `*.frozen.yaml` and `provenance.yaml` under `examples/specs/` are gitignored (verified live: `git check-ignore` matches both). AC-1 is verified by RUNNING `rk freeze --allow-missing`, NOT by a committed frozen file. Do NOT `git add` the frozen/provenance artifacts.
- Do NOT write production code. The aggregator (`aggregate.py`) is already correct; AC-3 only adds a TEST that pins its behavior on long slugs.
- Do NOT conflate the two scoring surfaces: `aggregate_summary` writes `summary.json`; `rk score` (`cli/score.py:122-125`) echoes a SEPARATE `score_version`/`strata` JSON. AC-3 asserts ONLY `summary.json`.

---

## Plan-Time Live Verifications (recorded)

All three confirmed before authoring (riskiest-first; recorded so the implementer trusts the surfaces):

1. **`SpacedockSolverAgentBlock` accepts `runtime: codex` + tuned budget.** Constructed `SpacedockSolverAgentBlock(kind="spacedock_solver", runtime="codex", model="gpt-5.5", solver_workflow="./examples/solver_workflows/codex-benchmark-solver", max_turns=400, override_timeout_sec=5400, max_timeout_sec=7200, reasoning_effort="xhigh")` → OK. Fields present and typed as expected (`schema.py:100-119`).
2. **`rk freeze --allow-missing` exits 0 offline and writes `benchmark.dataset` verbatim.** Ran `uv run rk freeze examples/specs/spider2-dbt-harbor-codex.yaml --allow-missing --out <scratch>` → exit 0, frozen body line `dataset: spider2-dbt/spider2-dbt@1.0` (verbatim, no download). Side effect: also writes `examples/specs/provenance.yaml` (gitignored).
3. **The aggregator join key is `trial_dir.name.split("__",1)[0] == manifest.parent.name[:32].rstrip("_-")`** (`aggregate.py:137-143`), manifest stratum has precedence over name-parse (`aggregate.py:112-114`), and the `default` collapse is at `aggregate.py:414-418`. View dir names are built by `_view_name(kind, task_id) = f"{kind}-{task_id}"` sanitized + truncated to **160** chars (`materialize.py:149-152`) — so the 32-char join truncation, not the 160-char view truncation, is what governs matching. Computed real swe-bench-pro slugs (e.g. `astropy__astropy-7166`) → view `swe-bench-pro-astropy__astropy-7166`, 32-char key `swe-bench-pro-astropy__astropy-7`. The `swe-bench-pro-` prefix is 14 chars, leaving only 18 task-id chars in the join key — the truncation/collision surface AC-3 must exercise.

---

## AC ↔ Task Map

| AC | Requirement | Task(s) | TDD checkpoint |
|----|-------------|---------|----------------|
| AC-3 | Aggregator stratifies swe-bench-pro slugs into per-task query cells via the real long-slug join key | Task 1 (load-bearing, riskiest-first) | New fixture-backed test: synthetic run dir + long-slug view manifests + long trial names → `aggregate_summary` → assert distinct `swe-bench-pro` query cells, NOT `default` collapse. Red→green by construction (aggregator already correct). |
| AC-1 | Schema-valid `spacedock_solver`/`runtime: codex` spec with SWE-tuned budget, freezes via `rk freeze --allow-missing`; frozen `benchmark.dataset == "scale-ai/swe-bench-pro@<ref>"`; grep confirms agent shape + tuned budget | Task 2 | `uv run rk freeze … --allow-missing` exits 0 + frozen dataset assertion + grep for `kind: spacedock_solver|runtime: codex|max_turns|override_timeout_sec`. |
| AC-2 | ABOUTME header note names the harbor-package hydration prerequisite for a live run | Task 2 (same file; folded in) | `grep -F 'scale-ai/swe-bench-pro' …` returns the ABOUTME hydration-prereq line. |

Riskiest-first ordering: **Task 1 (AC-3) before Task 2 (AC-1/AC-2)** — the scoring-strata test against the real long-slug join key is the load-bearing contract; the freeze/grep checks are cheap.

---

## File Structure

- **Create** `tests/unit/test_swe_bench_pro_scoring_strata.py` — the AC-3 fixture-backed test (Task 1). Sibling to `tests/unit/test_task_identity_scoring.py`, which it mirrors but with LONG swe-bench-pro slugs and the explicit anti-`default` assertion.
- **Create** `examples/specs/swe-bench-pro-spacedock-codex.yaml` — the AC-1/AC-2 user-facing spec (Task 2). Mirrors `examples/specs/dabstep-claude-harbor.yaml` (agent shape) + `examples/specs/spider2-dbt-harbor-codex.yaml` (ABOUTME header + qualified-ref + commented task-selector block).
- **No production files modified.**

---

### Task 1: AC-3 — Aggregator stratifies long swe-bench-pro slugs (load-bearing, riskiest-first)

**Files:**
- Create: `tests/unit/test_swe_bench_pro_scoring_strata.py`
- Reference (read-only, do NOT modify): `src/razorback/runs/aggregate.py:131-155` (join), `:414-418` (default collapse), `:526-563` (`aggregate_summary`); `tests/unit/test_task_identity_scoring.py` (pattern to mirror); `src/razorback/harbor_tasks/manifest.py:15-24` (`task_views_root` = `run_dir/"tasks"`).

**Interfaces:**
- Consumes: `from razorback.runs.aggregate import aggregate_summary`. `aggregate_summary(run_dir: Path) -> None` (writes `run_dir/summary.json` as a side effect).
- Join contract being exercised: a trial dir `<run_dir>/<prefix>__<suffix>/result.json` matches the view `<run_dir>/tasks/<view_name>/view_manifest.json` iff `prefix == view_name[:32].rstrip("_-")`. Manifest must carry non-empty `benchmark_kind` AND `benchmark_task_id` or the join returns `None` (`aggregate.py:147-148`). Trial reward read from `result.json` → `verifier_result.rewards.reward` (`aggregate.py:259-266`).
- Produces: nothing consumed downstream (leaf test).

**Why long slugs matter (design doc lines 141-147 + AC-3):** `_view_name` truncates to 160 but the JOIN truncates to 32. With the 14-char `swe-bench-pro-` prefix, only 18 task-id chars survive the join key. The existing `test_task_identity_scoring.py` uses SHORT names (`ade-bench-adebench-fixture-001`, < 32 chars) so `[:32]` is a no-op there and never exercises truncation. This test MUST use realistic long, project-prefixed swe-bench-pro slugs so a trial lands in its OWN cell and never in the `dataset="default"` bucket.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_swe_bench_pro_scoring_strata.py`:

```python
# ABOUTME: AC-3 — aggregate_summary stratifies long swe-bench-pro task slugs into
# ABOUTME: distinct per-task query cells via the real 32-char manifest-join key.
import json
from pathlib import Path

from razorback.runs.aggregate import aggregate_summary


def _write_manifest(run_dir: Path, view_name: str, task_id: str) -> None:
    # Views live under tasks_root = run_dir/"tasks" (harbor_tasks/manifest.py:15-24);
    # the aggregator resolves identity from this same root.
    view = run_dir / "tasks" / view_name
    view.mkdir(parents=True)
    (view / "view_manifest.json").write_text(
        json.dumps(
            {
                "benchmark_kind": "swe-bench-pro",
                "benchmark_task_id": task_id,
                "view_mode": "copy",
            }
        )
    )


def _write_trial(run_dir: Path, trial_name: str, reward: float) -> None:
    trial = run_dir / trial_name
    trial.mkdir(parents=True)
    (trial / "result.json").write_text(
        json.dumps({"verifier_result": {"rewards": {"reward": reward}}})
    )


def test_aggregator_stratifies_long_swe_bench_pro_slugs(tmp_path):
    """Realistic project-prefixed swe-bench-pro slugs land in DISTINCT query
    cells under the `swe-bench-pro` dataset stratum, never the `default`
    collapse. Exercises the real join key:
    trial_dir.name.split('__',1)[0] == view_dir.name[:32].rstrip('_-')
    (aggregate.py:137-143)."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    # Realistic long swe-bench-pro task slugs (project-prefixed, > 18 chars
    # so the 32-char join truncation is genuinely exercised). _view_name
    # builds f"swe-bench-pro-{task_id}" (materialize.py:149-152).
    task_slugs = [
        "astropy-astropy-7166",
        "django-django-11099",
        "matplotlib-matplotlib-26020",
    ]

    for slug, reward in zip(task_slugs, (1.0, 0.0, 1.0)):
        view_name = f"swe-bench-pro-{slug}"
        _write_manifest(run_dir, view_name, slug)
        # The orchestrator names a trial after the view's 32-char join key
        # (see tests/integration/test_spider2_dbt_scored_run_identity.py).
        trial_prefix = view_name[:32].rstrip("_-")
        _write_trial(run_dir, f"{trial_prefix}__deadbee", reward)

    aggregate_summary(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text())

    datasets = summary["datasets"]
    # The swe-bench-pro stratum exists and carries one cell per task slug.
    assert "swe-bench-pro" in datasets, (
        f"expected swe-bench-pro stratum, got {sorted(datasets)}"
    )
    # CRITICAL: nothing collapsed into the `default` bucket
    # (aggregate.py:414-418). A truncation/join mismatch would land trials
    # in `default` and silently pass a weaker assertion.
    assert "default" not in datasets, (
        f"long slugs collapsed to default: {datasets.get('default')}"
    )
    cells = datasets["swe-bench-pro"]["queries"]
    assert datasets["swe-bench-pro"]["n_queries"] == len(task_slugs)
    cell_ids = {c["query_id"] for c in cells}
    assert cell_ids == set(task_slugs), (
        f"query cells {cell_ids} != task slugs {set(task_slugs)}"
    )
    # Every per-trial row also carries the resolved swe-bench-pro identity.
    kinds = {t["stratum"].get("benchmark_kind") for t in summary["trials"]}
    assert kinds == {"swe-bench-pro"}, kinds
```

- [ ] **Step 2: Run test to verify it passes (green-by-construction)**

Run: `uv run pytest tests/unit/test_swe_bench_pro_scoring_strata.py -v`
Expected: PASS. The aggregator is already correct (verified at plan time); this test PINS that long slugs join correctly. If it FAILS with the `default`-collapse assertion, the trial-name/view-name join math in the test does not mirror the real key — re-derive `trial_prefix = view_name[:32].rstrip("_-")` and fix the test, NOT the aggregator.

- [ ] **Step 3: Prove the test is load-bearing (mutation check, do not commit the mutation)**

Temporarily edit the test's `trial_prefix` to a deliberately wrong value (e.g. `view_name[:20]`) and re-run:
Run: `uv run pytest tests/unit/test_swe_bench_pro_scoring_strata.py -v`
Expected: FAIL on `assert "default" not in datasets` (the mismatch routes trials to `default`). This confirms the test actually catches the truncation/collapse failure mode. Then REVERT to `view_name[:32].rstrip("_-")` and re-run → PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_swe_bench_pro_scoring_strata.py
git commit -m "test: AC-3 aggregate_summary stratifies long swe-bench-pro slugs

Pins that realistic project-prefixed swe-bench-pro task slugs land in
distinct per-task query cells via the 32-char manifest-join key, not the
dataset=default collapse. Entity: swe-bench-pro-example-spec-scoring-strata.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: AC-1 + AC-2 — User-facing example spec (freezes offline; hydration-prereq note)

**Files:**
- Create: `examples/specs/swe-bench-pro-spacedock-codex.yaml`
- Reference (read-only): `examples/specs/dabstep-claude-harbor.yaml` (spacedock_solver agent shape), `examples/specs/spider2-dbt-harbor-codex.yaml` (ABOUTME header + qualified-ref + commented task-selector block).

**Interfaces:**
- Consumes: the schema in `src/razorback/spec/schema.py` (`SpacedockSolverAgentBlock`, `HarborBenchmarkBlock`) and `rk freeze` (`src/razorback/provenance/freeze_cmd.py`).
- Produces: a frozen spec (transient, gitignored) whose `benchmark.dataset` equals the spec's verbatim `scale-ai/swe-bench-pro@latest`.

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

Note: keep `sampling.seed: null` — `SpacedockSolverAgentBlock` does not reject sampling controls the way `CodexAgentBlock` does, but `null` is the safe default mirrored from `spider2-dbt-harbor-codex.yaml`. Verify the `tasks:` example slugs (`astropy__astropy-7166`) against the real dataset form — see OPEN CAPTAIN DECISIONS on the `__` separator; if the real benchmark_task_id uses no `__`, update the comment slugs (comment-only, non-load-bearing for freeze/grep).

- [ ] **Step 2: Verify the spec freezes offline (AC-1 freeze check)**

Run: `uv run rk freeze examples/specs/swe-bench-pro-spacedock-codex.yaml --allow-missing --out /tmp/swe-bench-pro.frozen.yaml`
Expected: exit 0; stdout `wrote /tmp/swe-bench-pro.frozen.yaml` + `wrote examples/specs/provenance.yaml`.

Then assert the frozen dataset is verbatim:
Run: `grep -n 'dataset:' /tmp/swe-bench-pro.frozen.yaml`
Expected: `dataset: scale-ai/swe-bench-pro@latest`

- [ ] **Step 3: Verify the agent shape + tuned budget grep (AC-1 grep check)**

Run: `grep -E 'kind: spacedock_solver|runtime: codex|max_turns|override_timeout_sec' examples/specs/swe-bench-pro-spacedock-codex.yaml`
Expected: matches all four — `kind: spacedock_solver`, `runtime: codex`, `max_turns: 400`, `override_timeout_sec: 5400` (the latter two confirm a budget above the 1200s codex default).

- [ ] **Step 4: Verify the hydration-prereq note (AC-2 grep check)**

Run: `grep -F 'scale-ai/swe-bench-pro' examples/specs/swe-bench-pro-spacedock-codex.yaml`
Expected: returns the ABOUTME header line(s) naming the `scale-ai/swe-bench-pro` harbor-package hydration step (the PKG-40-style blocker) a live run requires.

- [ ] **Step 5: Clean up the gitignored freeze side effects**

The freeze wrote `examples/specs/provenance.yaml` (gitignored) and `/tmp/swe-bench-pro.frozen.yaml` (outside the repo). Confirm they are NOT staged:
Run: `git status --short examples/specs/`
Expected: shows ONLY `?? examples/specs/swe-bench-pro-spacedock-codex.yaml` (the spec). If `provenance.yaml` appears, it is gitignored and must NOT be added; `git checkout examples/specs/provenance.yaml` or leave it untracked.

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

- [ ] **AC-3:** `uv run pytest tests/unit/test_swe_bench_pro_scoring_strata.py -v` → PASS.
- [ ] **AC-1:** `uv run rk freeze examples/specs/swe-bench-pro-spacedock-codex.yaml --allow-missing --out /tmp/swe.frozen.yaml` → exit 0; `grep 'dataset:' /tmp/swe.frozen.yaml` → `scale-ai/swe-bench-pro@latest`; `grep -E 'kind: spacedock_solver|runtime: codex|max_turns|override_timeout_sec' examples/specs/swe-bench-pro-spacedock-codex.yaml` → all four match.
- [ ] **AC-2:** `grep -F 'scale-ai/swe-bench-pro' examples/specs/swe-bench-pro-spacedock-codex.yaml` → ABOUTME hydration note.
- [ ] **No regressions / no stray adds:** `git status --short` shows only the two intended new files committed; no `.frozen.yaml` / `provenance.yaml` staged.

---

## OPEN CAPTAIN DECISIONS

1. **The `@<ref>` pin.** AC-1 verifies `benchmark.dataset == "scale-ai/swe-bench-pro@<ref>"`. The plan uses `@latest` as the offline placeholder (mirrors `dabstep@latest`; `spider2-dbt` pinned `@1.0`). DECISION: keep `@latest`, or pin a concrete published ref (e.g. `@1.0`) if the captain knows one is published? `@latest` is safe offline since `rk freeze --allow-missing` writes the ref verbatim without resolving it.

2. **The `__` separator in real swe-bench-pro slugs / `[:32]` truncation risk.** Real SWE-bench instance_ids canonically contain `__` (e.g. `astropy__astropy-7166`). The aggregator join is asymmetric: the trial dir does `split("__",1)[0]` but the view join-key does `view_name[:32].rstrip("_-")` (no split). If the materialized `benchmark_task_id` contains `__`, the view name `swe-bench-pro-astropy__astropy-7166` truncates to `swe-bench-pro-astropy__astropy-7` while a trial named off `split("__")` would yield `swe-bench-pro-astropy` — a MISMATCH that collapses to `default`. The plan's Task 1 sidesteps this by deriving the trial prefix from the SAME `view_name[:32].rstrip("_-")` the orchestrator uses (mirroring `test_spider2_dbt_scored_run_identity.py`), and by using `-`-separated slugs in the test. DECISIONS for the captain: (a) does the swe-bench-pro materializer emit `benchmark_task_id` WITH `__` (E1's output — worth confirming against E1's fixture/live), and if so (b) is the 32-char truncation/`__`-asymmetry a real production risk worth a dedicated additional test case (two slugs sharing the first 18 task-id chars → forced collision), or is it out of scope for this mechanism-smoke entity (the aggregator code is owned upstream; E3 only confirms stratification)? The plan currently treats it as a flagged risk, not a code fix.

---

## Self-Review

- **Spec coverage:** AC-1 → Task 2 (freeze + grep). AC-2 → Task 2 (ABOUTME note). AC-3 → Task 1 (fixture test, riskiest-first). Test plan's "reuse the task-identity scoring surface" → Task 1 mirrors `test_task_identity_scoring.py`. Out-of-scope items (hydration unblock, leakage hardening, full-dataset score, swe-tuned solver authoring) are NOT tasks. No gaps.
- **Placeholder scan:** No TBD/TODO. All test/spec code is complete and literal. Commands have expected output. No "similar to Task N" references.
- **Type/name consistency:** `aggregate_summary(run_dir)` signature matches `aggregate.py:526`. View root `run_dir/"tasks"` matches `manifest.py:24`. Join key `view_name[:32].rstrip("_-")` matches `aggregate.py:142`. Reward path `verifier_result.rewards.reward` matches `aggregate.py:261-263`. Budget fields (`max_turns`, `override_timeout_sec`, `max_timeout_sec`) match `schema.py:106-110` and were live-validated. `datasets[...]["queries"]`/`n_queries`/`query_id` match the `_render_legacy_datasets` shape (`aggregate.py:493-508`).
