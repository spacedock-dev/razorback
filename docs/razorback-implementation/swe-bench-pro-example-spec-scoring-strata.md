---
id: xrh8vh7pbdzt7h09sfkspwp2
title: swe-bench-pro — example spec + scoring strata confirmation
status: plan
source: docs/superpowers/specs/2026-06-24-swe-bench-pro-on-harbor-design.md (E3); spider2-dbt-example-spec + harbor-view-task-identity-scored-runs as reference; sibling shape dabstep-claude-harbor.yaml (spacedock_solver + solver_workflow)
started: 2026-06-24T08:19:00Z
completed:
verdict:
score:
worktree:
issue:
pr:
mod-block:
auto-approve: false
---

## Problem

No user-facing spec demonstrates running swe-bench-pro, and the scoring
path is **broken** for swe-bench-pro's project-prefixed task slugs. This
entity adds `examples/specs/swe-bench-pro-spacedock-codex.yaml` AND **fixes**
the view-manifest-driven aggregator
(`src/razorback/runs/aggregate.py:_resolve_stratum_from_task_view_manifest`)
so it stratifies swe-bench-pro slugs. A full live run is gated on the
hydration blocker (PKG-40-style), so AC-1/AC-2 verify what is checkable
offline (schema-valid + freezes) and AC-3 fixes-then-confirms the
stratification with a fixture-backed scoring run.

**Scope widened after the Cycle-1 plan-gate rejection (see `## Feedback
Cycles`).** A Codex antagonist review PROVED the aggregator CANNOT stratify
swe-bench-pro at all — every task collapses to `dataset="default"`. The
original premise ("confirm the aggregator stratifies") was false. Two bugs,
both reproduced live: (1) **`__` split mis-cut** — Harbor names trial dirs
`task_name[:32].rstrip("_-") + "__" + suffix`
(`harbor/models/trial/config.py:219` `generate_trial_name`), and swe-bench-pro
canonical slugs contain `__` (e.g. `astropy__astropy-7166`), so the
aggregator's `trial_dir.name.split("__",1)[0]` (`aggregate.py:137`) cuts the
trial prefix at the WRONG `__` and never matches the view key
`view_dir.name[:32].rstrip("_-")` → `default` collapse; (2) **`[:32]`
collision** — after the 14-char `swe-bench-pro-` prefix only 18 slug chars
survive, so `django__django-11099` and `django__django-11098` share the key
`swe-bench-pro-django__django-110` → distinct tasks merge into one cell,
first sorted manifest wins. The fix is now a **production-code change**, not
a doc-only confirmation.

The robust fix (spike-confirmed): each Harbor trial dir persists
`config.json` (`harbor/trial/trial.py:934`,
`harbor/models/trial/paths.py` `config_path = trial_dir/"config.json"`) =
the serialized `TrialConfig`, whose `task.path` is the FULL materialized
view-dir path razorback passed. The aggregator resolves the view manifest
DIRECTLY from `config.json["task"]["path"]` (re-anchored by view-dir name
under `run_dir/tasks`), eliminating BOTH the `__` split and the `[:32]`
collision because no trial-dir-name parsing is needed. The current
dir-name join stays as a fallback for trials without a usable `config.json`
task path (preserves dabstep/spider2/ade short-slug behavior).

The agent block MUST be `kind: spacedock_solver` / `runtime: codex` to use
a solver workflow: `CodexAgentBlock` (`src/razorback/spec/schema.py:49-89`)
has no `solver_workflow` or `max_turns` fields — those live only on
`SpacedockSolverAgentBlock` (`schema.py:92-119`). Mirror the dabstep smoke
spec (`examples/specs/dabstep-claude-harbor.yaml`), swapping `runtime:
codex` + the `codex-benchmark-solver` workflow.

Depends on `swe-bench-pro-hydration-resolve-smoke` (the materializer
wiring); overlaps the leakage entity. `auto-approve: false` — touches the
scoring surface and a user-facing example.

## Acceptance criteria

**AC-1 — A `kind: harbor` swe-bench-pro example spec exists, is schema-valid with a `spacedock_solver`/`runtime: codex` agent and SWE-tuned budget, and freezes cleanly.**
Verified by: `uv run rk freeze examples/specs/swe-bench-pro-spacedock-codex.yaml --allow-missing`
exits 0 and the frozen `benchmark.dataset == "scale-ai/swe-bench-pro@<ref>"`;
`grep -E 'kind: spacedock_solver|runtime: codex|max_turns|override_timeout_sec'`
over the spec confirms the valid agent shape and a `max_turns` /
`override_timeout_sec` above the 1200s codex default.

**AC-2 — The example records the swe-bench-pro hydration prerequisite for a full run.**
Verified by: `grep -F 'scale-ai/swe-bench-pro' examples/specs/swe-bench-pro-spacedock-codex.yaml`
returns the `# ABOUTME:` header note naming the harbor-package hydration
step (the PKG-40-style blocker) a live run requires.

**AC-3 — The aggregator is FIXED to stratify swe-bench-pro task slugs (canonical `__` slugs, no `[:32]` collision) into per-task query cells.**
Verified by: a fixture-backed test that builds a synthetic run dir with
per-task `view_manifest.json` sidecars
(`benchmark_kind=swe-bench-pro`, distinct CANONICAL `benchmark_task_id`
slugs: `astropy__astropy-7166`, `django__django-11099`,
`django__django-11098`), **real Harbor trial-dir naming** (via
`harbor.models.trial.config.TrialConfig.generate_trial_name`,
`task_name[:32].rstrip("_-") + "__" + suffix` — NOT a hand-faked key) AND
the **real per-trial `config.json`** that Harbor persists
(`config.json["task"]["path"]` = the view-dir path), with non-null
`rewards["reward"]`, runs `aggregate_summary`
(`src/razorback/runs/aggregate.py:526-563`). The test is **RED-first**: it
FAILS on the current aggregator (reproducing the real `default` collapse +
the `-11099`/`-11098` collision), then PASSES after the fix — asserting
`summary.json`'s `swe-bench-pro` dataset stratum carries one query cell per
canonical slug, NO `default` bucket, and NO collision (all three distinct).
The fix resolves the view manifest from the trial's recorded
`config.json["task"]["path"]` in
`_resolve_stratum_from_task_view_manifest` (`aggregate.py:~131-155`),
eliminating both the `trial_dir.name.split("__")[0]` mis-cut
(`aggregate.py:137`) and the `view_dir.name[:32].rstrip("_-")` collision
(`aggregate.py:142`) that caused the `dataset="default"` collapse
(`aggregate.py:414-418`). A **regression guard** keeps the existing
`tests/unit/test_task_identity_scoring.py` +
`tests/integration/test_spider2_dbt_scored_run_identity.py` (short,
`__`-free slugs) passing — the dir-name join is retained as a fallback so
dabstep/spider2/ade do not regress. `rk score`'s separate
`score_version`/`strata` JSON surface (`cli/score.py:122-125`) is NOT
conflated with `summary.json`.

## Test plan

Offline freeze check (AC-1/AC-2; the live run stays blocked by hydration),
plus a fixture-backed `aggregate_summary` test over a synthetic
swe-bench-pro run dir with view-manifest sidecars (AC-3), reusing the
task-identity scoring surface from `harbor-view-task-identity-scored-runs`.
Acceptance command for validation:
`uv run rk freeze examples/specs/swe-bench-pro-spacedock-codex.yaml --allow-missing`
+ the aggregator test.

## Out of scope

Unblocking the swe-bench-pro harbor-package hydration (externally owned,
re-checked non-gating in `swe-bench-pro-hydration-resolve-smoke`). The
leakage/deny-glob hardening (its own entity). The full-dataset N=1 score
(deferred goal entity). Authoring a swe-tuned solver workflow — the
existing `codex-benchmark-solver` is the starting point; deferred unless it
underperforms on a live task.

## Stage Report: plan

**[SUPERSEDED by cycle 2 — this cycle-1 report describes a doc-only confirming
test and "no production-code change". That premise was DISPROVEN: the
aggregator genuinely cannot stratify swe-bench-pro (`__` split + `[:32]`
collision). Cycle 2 re-planned E3 as a production fix. Read "## Stage Report:
plan (cycle 2)" + "## Feedback Cycles" below for the authoritative plan.]**

- DONE: Write the implementation plan (STANDARD — separate plan doc)
  `docs/razorback-implementation/plans/swe-bench-pro-example-spec-scoring-strata.md`: header, Global Constraints, AC↔task map, 2 tasks (riskiest-first), final verification, open decisions, self-review.
- DONE: AC↔task map with 1:1 TDD checkpoints
  AC-3→Task 1 (load-bearing test, first); AC-1→Task 2 (freeze+grep); AC-2→Task 2 (ABOUTME note). Map table in plan.
- DONE: Per-step spec/design §-cite + live code-surface cites
  Join `aggregate.py:137-143`; default collapse `:414-418`; `aggregate_summary` `:526-563`; `_view_name` `materialize.py:149-152`; `task_views_root` `manifest.py:15-24`; schema `:92-119`; freeze `freeze_cmd.py`.
- DONE: Plan-time live verifications recorded
  (1) `SpacedockSolverAgentBlock(runtime=codex, max_turns=400, override_timeout_sec=5400, max_timeout_sec=7200)` constructs OK. (2) `rk freeze --allow-missing` on spider2 spec → exit 0, dataset written verbatim offline. (3) Join math computed for real long slugs; `[:32]` w/ 14-char `swe-bench-pro-` prefix leaves 18 task-id chars. `*.frozen.yaml`+`provenance.yaml` confirmed gitignored.
- DONE: Self-review for placeholders/contradictions
  Spec coverage complete, no placeholders, type/name consistency checked against cited line numbers.
- DONE: Flag open captain decisions
  (1) `@<ref>` pin (`@latest` offline placeholder vs concrete published ref). (2) Real `__` separator in swe-bench-pro slugs + `[:32]` truncation/collision — whether a dedicated forced-collision test case is in scope or upstream-owned.

### Summary

Authored a STANDARD plan doc producing two artifacts with no production-code change: a fixture-backed AC-3 test (`tests/unit/test_swe_bench_pro_scoring_strata.py`) proving long project-prefixed swe-bench-pro slugs land in distinct `swe-bench-pro` query cells (not the `dataset="default"` collapse) via the real `trial_dir.name.split("__")[0] == view_dir.name[:32].rstrip("_-")` join key — with a mutation step to prove the test is load-bearing — and a user-facing `examples/specs/swe-bench-pro-spacedock-codex.yaml` (`spacedock_solver`/`runtime: codex`/gpt-5.5 + `codex-benchmark-solver`, SWE-tuned budget, ABOUTME hydration-prereq note) that freezes offline via `rk freeze --allow-missing`. Ordered riskiest-first (AC-3 before the cheap freeze/grep checks). Two open captain decisions flagged: the `@<ref>` pin and the `__`/`[:32]` truncation-collision scope.

## Feedback Cycles

### Cycle 1 — plan gate REJECTED (2026-06-24)

A Codex antagonist review of the cycle-1 plan PROVED (against the real
`harbor.models.trial.config.TrialConfig.generate_trial_name` and the live
`aggregate.py`) that razorback CANNOT stratify swe-bench-pro at all — every
canonical slug collapses to `dataset="default"`. The cycle-1 premise
("confirm the aggregator stratifies; the aggregator is already correct")
was FALSE; the cycle-1 plan's AC-3 test used `-`-separated slugs and a
hand-derived trial prefix, so it would have passed green while real
matching fell to `default`.

Two bugs, both reproduced live (`.venv/bin/python`):
- **`__` split mis-cut** — `generate_trial_name` =
  `task_name[:32].rstrip("_-") + "__" + suffix`
  (`harbor/models/trial/config.py:219`). Canonical slug
  `astropy__astropy-7166` → view `swe-bench-pro-astropy__astropy-7166`,
  trial dir `swe-bench-pro-astropy__astropy-7__<uuid>`. Aggregator
  `split("__",1)[0]` (`aggregate.py:137`) → `swe-bench-pro-astropy` ≠ view
  key `swe-bench-pro-astropy__astropy-7` (`aggregate.py:142`) → no match →
  `default` (`aggregate.py:414-418`).
- **`[:32]` collision** — `django__django-11099` and `django__django-11098`
  both → key `swe-bench-pro-django__django-110` → one cell, first manifest
  wins.

Captain decision: WIDEN E3 to FIX the join (production-code change, no
longer doc-only). Spike found each Harbor trial dir persists `config.json`
(`harbor/trial/trial.py:934`) carrying `task.path` = the full view-dir
path; the fix resolves the manifest directly from that recorded path,
killing both bugs without dir-name parsing. Entity Problem § + AC-3 revised
above; plan rewritten with a red-first test + regression guard. Verdict:
REJECTED → re-planned cycle 2.

## Stage Report: plan (cycle 2)

- DONE: Reproduce both proven bugs live before planning
  `.venv/bin/python` repro: canonical `__` slugs collapse to `default` (n_queries=1, two of three lost to collision) under the current aggregator.
- DONE: Spike — what Harbor records per trial
  Each trial dir persists `config.json` (`harbor/trial/trial.py:934`; `paths.py` `config_path = trial_dir/"config.json"`) = serialized `TrialConfig` with `task.path` = full view-dir path (`swe-bench-pro-astropy__astropy-7166`, untruncated). GREEN preview: resolving `config.json → task.path → view_manifest.json` yields 3 distinct swe-bench-pro cells, no default, no collision.
- DONE: Design the production fix
  `_resolve_stratum_from_task_view_manifest` reads `trial_dir/config.json` → `task.path`, re-anchors by view-dir name under `run_dir/tasks`, reads `<view>/view_manifest.json`. Retains the dir-name join as a fallback. Plan Task 1.
- DONE: Rewrite AC-3 red-first + load-bearing
  Canonical `__` slugs + real `generate_trial_name` + real `config.json`; RED on current code, GREEN after fix; asserts 3 distinct cells, no `default`, no collision. Plan Task 1.
- DONE: Regression guard
  Plan Task 1 re-runs `test_task_identity_scoring.py` + `test_spider2_dbt_scored_run_identity.py` (short `__`-free slugs) — must stay green via the fallback.
- DONE: Keep AC-1/AC-2 example-spec tasks as planned
  Plan Task 2 unchanged (spec shape validated, freeze offline OK — passed Codex review).
- DONE: Re-verify all join claims live + self-review
  Bugs reproduced, fix prototyped green, harbor surfaces cited with confirmed line numbers; plan self-reviewed.
- DONE: Update entity (Problem § + AC-3 + Feedback Cycles)
  This file; `status` unchanged per dispatch.

### Summary (cycle 2)

Re-planned after the cycle-1 plan-gate rejection: E3 is widened from
doc-only confirmation to a production fix of the scoring join. Reproduced
both proven bugs live, ran the spike (Harbor persists `config.json` with
the full task path per trial), and designed a robust fix that resolves the
view manifest directly from `config.json["task"]["path"]` — eliminating the
`__` split mis-cut and the `[:32]` collision at once, with the dir-name
join kept as a non-regressing fallback. AC-3 is rewritten red-first with
canonical `__` slugs and real Harbor trial naming + `config.json`, plus a
regression guard for dabstep/spider2/ade. AC-1/AC-2 example-spec tasks
carry over unchanged. Plan doc rewritten; entity Problem/AC-3/Feedback
Cycles updated; `status` untouched.
