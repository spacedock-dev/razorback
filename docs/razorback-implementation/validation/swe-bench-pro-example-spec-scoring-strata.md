# Validation Report — swe-bench-pro-example-spec-scoring-strata

**Entity:** E3 — swe-bench-pro example spec + scoring strata fix
**Branch:** `swe-bench-pro-example-spec-scoring-strata` @ `f5cf8d4` (3 commits over main `1444078`: 5ea4291, 37f32f2, f5cf8d4)
**Worktree:** `.worktrees/swe-bench-pro-example-spec-scoring-strata` — clean, at tip.
**Validator:** fresh independent verifier (did NOT trust implementer self-report).
**Date:** 2026-06-24

## GATE DECISION: APPROVE

All three ACs pass with live evidence. The RED-first test is honest. The shared-aggregator change is provably safe for all benchmarks (dabstep/spider2/ade unchanged in behavior; config-first is strictly more correct where it differs). Edge cases handled gracefully. Full-suite 4 failures confirmed pre-existing on main, not regressions. Independent code review verdict: Ready to merge (Yes), no Critical/Important issues.

---

## Worktree / branch state

```
$ git status        -> nothing to commit, working tree clean
$ git log --oneline main..HEAD
f5cf8d4 report: ... implementation stage
37f32f2 feat: add swe-bench-pro spacedock_solver/codex example spec
5ea4291 fix: resolve scoring strata from trial config.json task path
$ git rev-parse HEAD -> f5cf8d43952ebbae4c1743053d7cbf6572964a2b
```
PASS — clean, exactly the 3 expected commits.

---

## AC-3 RED-first honesty (CRITICAL) — PASS, HONEST

Method: reverted ONLY `src/razorback/runs/aggregate.py` to main (`git checkout main -- src/razorback/runs/aggregate.py`), kept the new test, re-ran.

**RED (no fix, test present):**
```
$ uv run pytest tests/unit/test_swe_bench_pro_scoring_strata.py -q
F.   1 failed, 1 passed
FAILED test_aggregator_stratifies_canonical_swe_bench_pro_slugs
  AssertionError: expected swe-bench-pro stratum, got ['default']
  datasets == {'default': {... 'n_queries': 1, 'queries':[{'query_id': None}]}}
```
The canonical `__`-slug test FAILS exactly as the bug predicts: all three slugs collapse to `dataset='default'`, n_queries=1. The regression-guard test (`test_short_dunderless_slugs_still_stratify_via_fallback`) passes on pre-fix code, confirming it exercises the genuinely-unchanged fallback path.

**Restore + GREEN:**
```
$ git checkout HEAD -- src/razorback/runs/aggregate.py
$ uv run pytest tests/unit/test_swe_bench_pro_scoring_strata.py -q  -> 2 passed
```
Verdict: the test is load-bearing and not dishonest. RED on current aggregator, GREEN after fix.

---

## AC-3 fix correctness — PASS (independent synthetic run dirs)

Read `_resolve_stratum_from_task_view_manifest`, `_stratum_from_config_task_path`, `_stratum_from_manifest_payload` (aggregate.py:131-206).

- (a) Config-first resolution reads `config.json["task"]["path"]`, takes **basename only** via `Path(str(raw_path)).name`, and re-anchors under `task_views_root(trial_dir.parent)`. It does **NOT** read `Path(raw_path)/manifest` directly — confirmed in source (comment at aggregate.py:169-177 and code: `views_root / view_dir_name / "view_manifest.json"`). My own TEST B proved this: a config.json whose `task.path` is a foreign absolute path (`/some/other/machine/...`) still resolved correctly via basename re-anchoring.
- (b) Built an independent run dir (scratchpad/probe.py TEST A) with real `harbor.models.trial.config.TrialConfig.generate_trial_name` + real serialized `config.json` for the three canonical slugs. The trial dir names produced confirm the bug source — both django dirs become `swe-bench-pro-django__django-110__<uuid>` (identical [:32] prefix). Result: 3 distinct `swe-bench-pro` cells, `n_queries=3`, NO `default` bucket, query_ids = {astropy__astropy-7166, django__django-11099, django__django-11098}.

PASS.

---

## REGRESSION — shared aggregator (MOST IMPORTANT) — PASS

Existing tests:
```
$ uv run pytest tests/unit/test_task_identity_scoring.py -q                 -> 2 passed
$ uv run pytest tests/integration/test_spider2_dbt_scored_run_identity.py -q -> 1 passed
```

Independent synthetic short-slug runs (scratchpad/probe.py):
- TEST C — short slug WITHOUT config.json: datasets == {dabstep, spider2-dbt}, no default. Fallback dir-name join still stratifies. PASS.
- TEST D — short slug WITH config.json: datasets == {dabstep, spider2-dbt}, no default. Config-first path resolves the SAME result. PASS.

**Key regression-risk answer (does config-first change existing benchmarks that write config.json?):**
Traced `translate.py:284,319,447,456,479` — for materialized harbor runs razorback sets `TaskConfig(path=<view dir under run_dir/tasks>)`, so the config.json task.path BASENAME equals the view dir name. Config-first therefore targets the SAME manifest the old dir-name join did. They can only diverge where the old `[:32]`/`__` join was LOSSY (collision/mis-cut) — and there config-first is strictly MORE correct. Proved by TEST (adversarial): two dabstep views sharing a `[:32]` prefix that the OLD path would have MERGED into one cell are correctly disambiguated by config-first into 2 distinct cells. Config-first cannot resolve to a different/WRONG view because the basename IS the exact view dir name. Net effect for dabstep/spider2/ade: identical results on the happy path, latent collisions eliminated — improvement, not regression. Fallback code path logic unchanged (only refactored to share `_stratum_from_manifest_payload`, semantically identical).

---

## Edge cases — PASS (scratchpad/probe.py)

- TEST E — multi-attempt (2 trial dirs same task, distinct uuid suffixes): both resolve to ONE cell, n_queries=1, query n_trials=2. PASS.
- TEST F — malformed config.json (`{ this is not valid json`): no crash, graceful fallback to dir-name join -> {dabstep}. PASS.
- TEST G — config task.path basename with no matching view dir: config-first returns None, falls back to dir-name join -> {dabstep}, no crash. PASS.
- TEST H — missing config.json entirely: covered by TEST C. PASS.

---

## AC-1 — example spec freezes + correct shape — PASS

```
$ uv run rk freeze examples/specs/swe-bench-pro-spacedock-codex.yaml --allow-missing
wrote examples/specs/swe-bench-pro-spacedock-codex.frozen.yaml
wrote examples/specs/provenance.yaml      EXIT=0
```
Frozen spec: `dataset: scale-ai/swe-bench-pro@latest`; agent `kind: spacedock_solver`, `runtime: codex`, `max_turns: 400`, `override_timeout_sec: 5400.0`, `max_timeout_sec: 7200.0` (all above the 1200s codex default). Frozen artifacts (`*.frozen.yaml`, `provenance.yaml`) correctly gitignored (`git check-ignore` confirms). PASS.

## AC-2 — hydration prerequisite recorded — PASS

```
$ grep -F 'scale-ai/swe-bench-pro' examples/specs/swe-bench-pro-spacedock-codex.yaml
# ABOUTME: scale-ai/swe-bench-pro@latest (kind: harbor, qualified-ref resolution path).
# ABOUTME: A live run requires the scale-ai/swe-bench-pro harbor-package to be
  dataset: scale-ai/swe-bench-pro@latest
```
ABOUTME header names the harbor-package hydration step (PKG-40-style blocker) a live run requires. PASS.

---

## Full suite + regression classification — PASS

```
$ uv run pytest tests/ -q   -> 4 failed, 862 passed, 12 skipped
FAILED tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::test_codex_runtime_dispatch_constructs_inner_agent
FAILED tests/integration/test_worktree_teardown_preserves_runs.py::test_worktree_remove_force_does_not_destroy_runs
FAILED tests/unit/test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch
FAILED tests/unit/test_rk_research_new.py::test_rk_research_new_creates_scaffold_tree
```
Confirmed pre-existing on main via throwaway detached worktree at `1444078`: the SAME 4 tests fail (`4 failed`). NOT regressions from this branch. PASS.

---

## Code review (superpowers:requesting-code-review, base main) — Ready to merge: Yes

Independent reviewer (general-purpose) traced task.path provenance through translate.py and reached the same conclusion as the probes. No Critical, no Important issues. Two Minor (non-blocking):
- [MINOR/pre-existing] `_stratum_from_manifest_payload` calls `.get()` on `_read_json` output typed `dict | None` but a malformed top-level JSON array would raise AttributeError. Identical pattern existed in old inline code; manifests are always objects. Optional `isinstance(payload, dict)` guard.
- [MINOR] No test asserts config-first is *preferred* when a valid config.json AND a colliding dir-name match both exist. Logic is simple; validator's adversarial probe covers the disambiguation behaviorally.

Reviewer also flagged `uv.lock` churn from running the AC-1 freeze command — this is a side effect of the acceptance command itself; the committed tree is clean and validator restored `uv.lock` (`git checkout -- uv.lock`).

---

## Findings classification

- No [P1] / Critical findings.
- No [P2] / Important findings.
- [MINOR] `_read_json` non-dict robustness (pre-existing, latent).
- [MINOR] config-first-precedence test coverage gap (behaviorally proven by validator probes).

## Decision: APPROVE → done.
