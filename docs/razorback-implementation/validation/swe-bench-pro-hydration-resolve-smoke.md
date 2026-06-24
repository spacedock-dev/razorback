# Validation Report — swe-bench-pro — hydration + task-view materializer wiring smoke

**Entity:** `docs/razorback-implementation/swe-bench-pro-hydration-resolve-smoke.md`
**Branch under test:** `swe-bench-pro-hydration-resolve-smoke`
**Worktree:** `/Users/kent/Dev/InfuseAI/GitHub/razorback/.worktrees/swe-bench-pro-hydration-resolve-smoke`
**Validator:** fresh independent VALIDATION-stage worker (reproduced everything from committed branch tip; did not trust implementer self-report)
**Date:** 2026-06-24

## GATE DECISION: APPROVE

All 3 ACs PASS with reproduced evidence. Full suite has 4 failures, all INDEPENDENTLY confirmed pre-existing on `main` (identical reproduction in a detached base worktree) — zero regressions. Code review found no Critical/Important issues (only cosmetic Minor nits, none blocking). The single documented deviation is sound and the load-bearing leakage assertion holds. T8 live smoke correctly deferred (non-gating, validation-owned, no network access attempted).

---

## 0. Branch state

```
$ git -C .worktrees/swe-bench-pro-hydration-resolve-smoke status
On branch swe-bench-pro-hydration-resolve-smoke
nothing to commit, working tree clean

$ git log --oneline main..HEAD
f838094 docs(swe-bench-pro): implementation stage report
ccc6092 style(swe-bench-pro): hoist test imports to module top (ruff E402)
626da25 test(swe-bench-pro): rk run --explain --explain-format json lists resolved views in-process (AC-3)
2f29933 test(swe-bench-pro): fixture frozen kind:harbor spec for rk run --explain (AC-3)
668ee35 test(swe-bench-pro): assert materialized view carries benchmark env (AC-2)
6438e66 test(swe-bench-pro): exclude_tasks binds to source slug; ref takes materializer branch (AC-1)
21ca379 test(swe-bench-pro): N leakage-clean task-view dirs with benchmark_kind manifest (AC-1)
425018d feat(translate): materialize swe-bench-pro views via generic materializer in kind:harbor
55de296 test(swe-bench-pro): minimal harbor task fixture tree (two instances + planted deny-path file)
0197354 feat(translate): detect swe-bench-pro dataset family by short name
```

Worktree is clean and at branch tip. The ACs do NOT depend on a dirty tree. Production diff is contained to `src/razorback/translate.py` (90 lines); rest is fixtures + tests + entity body (`git diff --stat main..HEAD`: 13 files, +414/-23).

---

## AC-1 — kind:harbor / scale-ai/swe-bench-pro@<ref> resolves to N materialized task-view dirs via the materializer branch (NOT pass-through). PASS

**Verified by (reproduced):**
```
$ uv run --frozen pytest tests/unit/test_translate_swe_bench_pro.py -v
...
tests/unit/test_translate_swe_bench_pro.py::test_swe_resolves_n_views_with_manifest_leakage_clean PASSED
tests/unit/test_translate_swe_bench_pro.py::test_swe_ref_takes_materializer_branch_not_passthrough PASSED
tests/unit/test_translate_swe_bench_pro.py::test_swe_dataset_materializes_views_with_manifest PASSED
tests/unit/test_translate_swe_bench_pro.py::test_exclude_tasks_drops_swe_source_slug PASSED
tests/unit/test_translate_swe_bench_pro.py::test_n_tasks_caps_swe_before_materialize PASSED
```
(10 unit tests + the AC-3 integration test = 11 passed in 1.22s.)

- `test_swe_resolves_n_views_with_manifest_leakage_clean` asserts N(=2) views, each with `task.toml` + `view_manifest.json` whose `benchmark_kind == "swe-bench-pro"`. PASS.
- `test_swe_ref_takes_materializer_branch_not_passthrough` proves the swe ref takes the materializer branch (emitted dir name `swe-bench-pro-swe-bench-pro-fixture-001`, `view_manifest.json` present), NOT the generic pass-through (which would emit the raw source dir with no manifest). PASS.
- `test_exclude_tasks_drops_swe_source_slug` proves selectors bind to the SOURCE slug before materialization. PASS.

**Result: PASS.** Pytest nodes above, all PASSED.

---

## AC-2 — Each materialized view's task.toml carries RAZORBACK_BENCHMARK_KIND + RAZORBACK_BENCHMARK_TASK_ID. PASS

**Verified by (reproduced):**
```
$ uv run --frozen pytest tests/unit/test_translate_swe_bench_pro.py::test_materialized_view_carries_benchmark_env -v
tests/unit/test_translate_swe_bench_pro.py::test_materialized_view_carries_benchmark_env PASSED
```
The test parses the emitted view `task.toml` with `HarborTaskConfig.model_validate_toml` and asserts:
- `cfg.environment.env["RAZORBACK_BENCHMARK_KIND"] == "swe-bench-pro"`
- `cfg.environment.env["RAZORBACK_BENCHMARK_TASK_ID"] == "swe-bench-pro-fixture-001"`

Confirmed the env is passed BY THE BRANCH as `environment_env` (`translate.py` swe branch) and MERGED by `materialize_harbor_task_view` (`_patch_task_toml`), not synthesized by the materializer.

**Result: PASS.** Node `test_materialized_view_carries_benchmark_env` PASSED.

---

## AC-3 — rk run <fixture-spec>.frozen.yaml --explain --explain-format json lists resolved task views. PASS

**Verified by (reproduced):** in-process `CliRunner` test.
```
$ uv run --frozen pytest tests/integration/test_rk_run_swe_bench_pro_explain.py -v
tests/integration/test_rk_run_swe_bench_pro_explain.py::test_rk_run_explain_lists_swe_task_views PASSED
```

I independently reproduced the underlying command behavior via an in-process CliRunner invocation of `rk run <spec>.frozen.yaml --explain --explain-format json`:
```
exit_code = 0
payload["prompt"]["task_paths"] = [
  ".../tasks/swe-bench-pro-swe-bench-pro-fixture-001",
  ".../tasks/swe-bench-pro-swe-bench-pro-fixture-002"
]
```
Exit 0, `payload["prompt"]["task_paths"]` has one entry per fixture instance (2), each a `swe-bench-pro-<slug>` materialized view.

**Confirmed the test patches BOTH seams** (`tests/integration/test_rk_run_swe_bench_pro_explain.py`):
- line 22-25: `monkeypatch.setattr("razorback.translate._resolve_harbor_dataset_tasks", ...)`
- line 31: `monkeypatch.setattr("razorback.cli.run._run_canary", lambda *a, **k: None)`

The `_run_canary` patch makes the test genuinely offline (the canary shells out to `docker run` before the `--explain` branch). This is an improvement over the spider2 precedent, which omits the canary patch and silently depends on a live Docker daemon.

**Result: PASS.** Node `test_rk_run_explain_lists_swe_task_views` PASSED.

---

## Full suite

```
$ uv run --frozen pytest tests/ -q
...
FAILED tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::test_codex_runtime_dispatch_constructs_inner_agent
FAILED tests/integration/test_worktree_teardown_preserves_runs.py::test_worktree_remove_force_does_not_destroy_runs
FAILED tests/unit/test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch
FAILED tests/unit/test_rk_research_new.py::test_rk_research_new_creates_scaffold_tree
4 failed, 845 passed, 12 skipped, 96 warnings in 43.02s
```

### Regression-vs-preexisting classification (INDEPENDENTLY verified)

I created a detached base worktree at `main` (HEAD `ccc2f3a`) and ran the 4 failing tests there:
```
$ git worktree add --detach <scratch>/e1-base main   # HEAD ccc2f3a
$ cd <scratch>/e1-base && uv run --frozen pytest \
    tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::test_codex_runtime_dispatch_constructs_inner_agent \
    tests/integration/test_worktree_teardown_preserves_runs.py::test_worktree_remove_force_does_not_destroy_runs \
    tests/unit/test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch \
    tests/unit/test_rk_research_new.py::test_rk_research_new_creates_scaffold_tree -q
4 failed in 19.44s
```

All 4 reproduce IDENTICALLY on `main`. They are **PRE-EXISTING, not regressions** caused by this branch. Corroborating evidence: the 4 failing test files have an empty diff `main..HEAD` (untouched by this branch), and they exercise codex runtime / worktree teardown / matrix specs / research scaffold — surfaces unrelated to harbor translation. The implementer's claim of 4 pre-existing failures is INDEPENDENTLY CONFIRMED.

### Pass-through + spider2 path unchanged
```
$ uv run --frozen pytest tests/unit/test_translate_harbor_block.py tests/unit/test_translate_spider2_dbt.py -q
21 passed, 4 warnings in 11.34s
```
The generic non-family harbor pass-through and the spider2-dbt branch are behaviorally unchanged (green). The spider2 branch still calls `materialize_spider2_harbor_task_view` with identical args; the generic pass-through block is byte-for-byte the original.

---

## Documented deviation (plan T4 leakage assertion relaxation) — SOUND

**Plan T4** specified `assert not (view/"solution").exists()`. The implementation relaxed this (`tests/unit/test_translate_swe_bench_pro.py:118-120`) to:
```python
assert not (view / "solution" / "gold_patch.diff").exists()
if (view / "solution").exists():
    assert not any(p.is_file() for p in (view / "solution").rglob("*"))
```
Rationale (in test comment): the materializer's `solution/**` glob strips files UNDER `solution/` but may leave an empty `solution/` dir node.

**Verified TRUE on disk** (reproduced by materializing fixture-001 directly):
```
SOURCE solution/ contents: ['solution/gold_patch.diff']
VIEW solution/ exists: True
VIEW solution/ is dir: True
VIEW solution/ all rglob entries: []
VIEW solution/ FILES: []
gold_patch.diff present in view: False
```
- The empty `solution/` dir genuinely remains and contains NO files and NO symlinks (rglob returns `[]`).
- The load-bearing leakage assertion holds: `gold_patch.diff` is ABSENT from the view.

**Judgment:** Sound, NOT a leakage concern. An empty directory node carries zero answer content; the materializer's own `assert_no_denied_paths` only inspects files/symlinks. The real leakage contract — "no answer content survives" — is satisfied. The empty-dir-node behavior is materializer-owned and out of scope here (deny-glob hardening is entity E2). The relaxation is a correct reflection of actual materializer behavior, not a weakening of the gate.

---

## Code review (base `main`)

Ran `superpowers:requesting-code-review` (general-purpose reviewer subagent, read-only, base `main`).

**Findings classification:**
- Critical (blocking): NONE
- Important (blocking): NONE — reviewer verified spider2 + generic pass-through paths are provably unchanged.
- Minor (non-blocking):
  1. Import ordering: `materialize_harbor_task_view` import (`translate.py:20`) not alphabetical; flagged only by `ruff check --select I` (isort), which is NOT in the project's active rule set. **Validator confirmed:** plain `uv run ruff check src/razorback/translate.py` → `All checks passed!`. Cosmetic only.
  2. Fixture naming yields a doubled prefix (`swe-bench-pro-swe-bench-pro-fixture-001`) because fixture slugs are literally `swe-bench-pro-fixture-*`; a fixture artifact, not a production defect (real task IDs won't carry the prefix).
  3. `transform_name`/`benchmark_kind` inline string literals vs the `SWE_BENCH_PRO_SHORT_NAME` constant — consistency nit.

**Reviewer verdict:** Ready to merge with (trivial) fixes; the only finding is a cosmetic import-order nit not flagged by active ruff. All Minor — NONE blocking.

---

## T8 — Live `harbor download` smoke (non-gating) — DEFERRED

T8 was correctly NOT run by the implementation stage (it is non-gating and validation-owned). Per dispatch instructions, this validator did NOT attempt live network access. **Recorded as a deferred, documented non-gating follow-up:**

- A future `integration`-marked test that resolves `scale-ai/swe-bench-pro@<ref>` live (out of scope of this entity's gate).
- The PKG-40-style `git checkout exit-128` hydration blocker (the #1 feasibility risk) is re-checked by this live smoke; its status remains UNVERIFIED here (no network run).
- Open decision for the captain (carried from plan): pin a concrete `@<ref>` for `scale-ai/swe-bench-pro` before any live smoke / E3 example spec; the fixture spec uses `@latest`, which is sufficient for the offline-gated ACs (resolver monkeypatched) but not for live reproduction.

This does NOT block the gate — all 3 ACs gate on the deterministic fixture and are PASS.

---

## Summary table

| Item | Result | Evidence |
| --- | --- | --- |
| AC-1 | PASS | `test_swe_resolves_n_views_with_manifest_leakage_clean`, `test_swe_ref_takes_materializer_branch_not_passthrough` + 3 more, all PASSED |
| AC-2 | PASS | `test_materialized_view_carries_benchmark_env` PASSED; env merged into task.toml |
| AC-3 | PASS | `test_rk_run_explain_lists_swe_task_views` PASSED; reproduced `exit 0` + 2 `task_paths` under `prompt`; patches both seams |
| Full suite | 845 passed / 4 failed / 12 skipped | 4 failures pre-existing (reproduced on `main` HEAD ccc2f3a), zero regressions |
| Pass-through + spider2 | 21 passed | unchanged |
| Deviation | SOUND | empty `solution/` dir, no files survive; `gold_patch.diff` absent |
| Code review | No Critical/Important; 3 Minor (non-blocking) | active ruff `All checks passed!` |
| T8 live smoke | DEFERRED (non-gating) | no network access attempted |

**GATE: APPROVE.**
