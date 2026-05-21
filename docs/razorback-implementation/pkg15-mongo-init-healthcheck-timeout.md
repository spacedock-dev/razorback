---
id: mbvd6v5j5cscffzfryvr88qs
title: PKG-15 follow-up — mongo init healthcheck timeout (extend retries / startup wait)
status: validation
source: PKG-15 follow-up — Goal 1 matrix 2026-05-20 (commits dae5d33 + 148c6af on archived branch spacedock-ensign/goal1-dab-paper-reproduction); direct-minimal/agnews failed Step main healthcheck after 12 consecutive retries
started: 2026-05-21T06:11:54Z
completed:
verdict:
score: 0.85
worktree: .worktrees/spacedock-ensign-pkg15-mongo-init-healthcheck-timeout
issue:
pr:
mod-block:
---

## Problem

PKG-15 shipped the mongorestore `.sh` shim mechanism (mongo:8 only
auto-runs `.sh`/`.js` initdb scripts; PKG-15 generates one to
invoke `mongorestore` against the bind-mounted BSON dump). Live
testing under Goal 1's matrix surfaced a downstream gap: the
**healthcheck timeout is too short for large mongo datasets**.

Goal 1's direct-minimal/agnews cell failed with:
```
Step 'main' healthcheck failed: Healthcheck failed after 12
consecutive retries:
mongosh --quiet --host dab-mongo --eval
"db.getSiblingDB('articles_db').getCollection('articles').countDocuments() > 0"
| grep -q true
```

The cell repeated this failure 4 times before giving up (each
trial = 4 questions × ~12 retries × 5s = ~4 minutes of waiting per
trial, all returning reward 0). The dataset wasn't broken; mongo
just hadn't finished restoring the BSON when the healthcheck
exhausted its retries.

Likely root cause: agnews (and yelp) BSON dumps are large enough
that `mongorestore` takes >60 seconds inside the `dab-mongo`
container. The PKG-15 healthcheck has `retries: 12` and `interval:
5s` = 60-second max wait. The mongorestore wall time exceeds that
for the larger datasets.

## Acceptance criteria

**AC-1 — Healthcheck waits long enough for large mongo datasets.**
The mongo content-presence healthcheck (emitted by PKG-15 in the
generated compose) is configured so its `retries × interval`
product exceeds the worst-case mongorestore wall time for the
biggest ade-bench / DAB mongo dataset. Suggested defaults:
`retries: 60`, `interval: 5s` = 5 minutes max wait. The exact
numbers are configurable per dataset.
Verified by: a unit test asserts the compose emits the new
defaults; an integration test against a fixture mongo dataset
(or a deliberate slow-restore mock) asserts the healthcheck
eventually passes.

**AC-2 — Configurable per-dataset.**
The compose generator accepts a per-dataset healthcheck-retries
override (via `db_config` schema extension or a sensible default
keyed on dataset size). Datasets that auto-restore quickly
(small ones like bookreview) need not waste 5 minutes on
healthcheck wait; large datasets get the bigger budget.
Verified by: a unit test exercises the override path.

**AC-3 — Goal 1 agnews + yelp cells produce non-zero rewards on
resume.** After PKG-15-followup ships, the goal1-resume matrix's
agnews and yelp cells produce trial outcomes other than
mean-reward=0-from-mongo-timeout. (If they still fail, it's a
real query failure — not the init-time race.)
Verified by: a live `rk run` against agnews × claude-opus-4-7
produces a result.json with at least one query attempt's reward
computed by the verifier (not by mongo-not-ready short-circuit).

**AC-4 — DAB regression.**
PKG-15's existing fixture tests + the bookreview / postgres path
tests stay green.
Verified by: `uv run pytest
packages/razorback-plugin-dab/tests/unit/` passes.

## Test plan

- **Unit:** extends PKG-15's existing `test_compose_mongo.py` with
  cases for AC-1 (new healthcheck defaults), AC-2 (per-dataset
  override).
- **Integration:** synthetic mongo dataset with deliberate slow
  init asserts the healthcheck eventually passes.
- **Acceptance:** Goal 1's agnews + yelp cells produce real
  verifier output on resume.

## Out of scope

- Speeding mongorestore itself (BSON dumps are pre-built; would
  require dataset-side changes).
- Healthchecks for other services (postgres, redis if added).

## Depends on

- PKG-15 (shipped) — this entity tightens the healthcheck timing

## Resume hook

After PKG-15-followup merges, goal1-resume-spacedock-first
implementation re-runs the matrix; agnews and yelp cells in the
direct-minimal and spacedock variants should produce real verifier
outcomes.

## Plan

**Surface correction:** the dispatch named
`packages/razorback-plugin-dab/.../generate/compose.py` as the
single-file change. The 12-retries × 5s healthcheck cited in the
failure log is in fact emitted by
`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py`
`_task_toml()` lines 339–361 (the `[steps.healthcheck]` block in
the per-task `task.toml`). `compose.py`'s container-level mongo
healthcheck already has `retries: 20`, not 12, and lives at a
different layer (docker-compose `services.dab-mongo.healthcheck`).
The plan targets `prepare.py` because that's where the failing
healthcheck is generated; `compose.py` is unchanged.

**TDD-ordered changes (single file:
`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py`):**

1. **RED for AC-1 (new defaults).** Extend
   `packages/razorback-plugin-dab/tests/unit/test_compose_mongo.py`
   (or a sibling `test_prepare_mongo_healthcheck.py` if isolation
   reads cleaner — implementer's call at TDD time) with a unit
   test that drives `_task_toml(mongo_probes=[("articles_db",
   "articles")])` and asserts the emitted toml contains
   `retries = 60` and `start_period_sec = 60`, `interval_sec = 5`
   (so retries × interval = 5 minutes, well above the worst-case
   mongorestore wall time for agnews / yelp). Run, confirm RED.

2. **GREEN AC-1.** Bump the literals in `prepare.py` `_task_toml`
   `elif mongo_probes:` branch: `retries = 12` → `retries = 60`.
   Leave `interval_sec = 5`, `timeout_sec = 10`, and
   `start_period_sec = 60` as-is (start_period is mongo-container
   startup budget, separate from the mongorestore-wait budget).
   Re-run, confirm GREEN.

3. **RED for AC-2 (per-dataset override).** Add a unit test that
   passes a `db_config` whose mongo client carries an optional
   `healthcheck_retries` field (e.g. `{"db_type": "mongo",
   "db_name": "articles_db", "dump_folder": "...",
   "healthcheck_retries": 120}`) and asserts the emitted task.toml
   contains `retries = 120`. Add a second test asserting that
   omitting the field falls back to the AC-1 default (60). Run,
   confirm RED.

4. **GREEN AC-2.** Thread an override through the existing call
   chain. Two minimal edits:
   - `_mongo_probe_targets` (or a sibling helper) is the natural
     place to extract `healthcheck_retries` from the mongo client
     `db_config` entry alongside `(db_name, collection)`. Extend
     its return shape to carry the optional override (or add a
     parallel `mongo_healthcheck_retries: int | None` argument
     thread).
   - `_task_toml` accepts `mongo_healthcheck_retries: int | None
     = None` and uses the override when present, defaulting to
     `60`.
   - `_materialize_task_dir` (`prepare.py` lines 159–168) passes
     the override from `db_config` through to `_task_toml`.
   No schema-validation framework lives in this package for
   `db_config`; the field is just a dict-key read with a
   `.get("healthcheck_retries")` and an `isinstance(int)` guard.
   Run, confirm GREEN.

5. **AC-3 (live smoke) — deferred to resume hook, NOT this
   plan's implementation stage.** AC-3 requires a live `rk run`
   against agnews × claude-opus-4-7, which costs API budget and
   wall time and must happen on the goal1-resume re-run rather
   than inside the implement stage. The resume hook at the end
   of this entity file already captures the dependency; the
   implementation stage MUST NOT block on AC-3.

6. **AC-4 (regression).** Run `uv run pytest
   packages/razorback-plugin-dab/tests/unit/ -q` after each
   green step; the whole suite must stay green at implement-
   stage completion.

**Effort estimate:** small. One file change in `prepare.py`
(roughly 8–15 lines: 1 default bump + ~10 lines of override
plumbing), plus 2–3 new unit tests. No compose.py change. No
new dependencies.

**Risks / unknowns:**
- The override field name `healthcheck_retries` is invented in
  this plan; if `db_config` schemas live in an upstream catalog
  module the implementer should grep for an existing convention
  first (`grep -rn "db_clients" packages/razorback-plugin-dab/
  --include=*.py`) and prefer the existing naming style. The
  exact name is not load-bearing — what matters is that exactly
  one well-named override key exists.
- AC-1's `retries = 60` (5-minute budget) is a guess sized for
  agnews / yelp; if implement-stage discovers a DAB mongo dataset
  with an even longer mongorestore wall time, the per-dataset
  override (AC-2) handles it without re-shipping defaults.

## Stage Report: plan

- DONE: Plan is INLINE (4 ACs, single-file change in packages/razorback-plugin-dab/.../generate/compose.py mongo healthcheck section). Stage report on entity body, no separate plan doc.
  Plan written inline under `## Plan` above; no separate plan doc created.
- DONE: Plan names the exact change: bump healthcheck `retries` from 12 to 60 (or sensible larger value); make it configurable per-dataset via db_config schema extension. Reference existing PKG-15 fixture test_compose_mongo.py as test surface.
  Step 2 bumps `retries = 12` → `retries = 60` at `prepare.py` `_task_toml` line 360; step 4 adds `healthcheck_retries` override via `db_config["db_clients"][...]`; test surface is `test_compose_mongo.py` (or sibling `test_prepare_mongo_healthcheck.py`).
- DONE: Plan TDD-orders: RED unit test for AC-1 (new defaults) first, then impl, then AC-2 per-dataset override test, then AC-3 deferred live-run smoke (captured in resume hook).
  Steps 1→2→3→4 are RED-GREEN pairs; AC-3 explicitly deferred to resume hook in step 5; AC-4 regression run in step 6.

### Summary

Plan corrects the dispatch's file-location (the failing
healthcheck lives in `prepare.py` `_task_toml`, not `compose.py`)
and lays out a TDD-ordered, single-file change: bump default
mongo content-presence healthcheck retries from 12 to 60 (AC-1),
thread a `healthcheck_retries` override through `db_config →
_materialize_task_dir → _task_toml` (AC-2), defer the live agnews
smoke to the goal1-resume hook (AC-3), and gate completion on the
existing dab unit-test suite (AC-4). Effort is small (~one file,
two helpers, two-to-three new unit tests, no new deps).

## Stage Report: implementation

- DONE: AC-1 — Healthcheck waits long enough for large mongo datasets. Default `retries` bumped 12 → 60 in `prepare.py` `_task_toml` (5min × 5s budget).
  test_prepare_mongo_healthcheck.py::test_mongo_healthcheck_default_retries_is_60 asserts emitted toml has retries=60, interval_sec=5, start_period_sec=60; previously RED (12 != 60), now GREEN.
- DONE: AC-2 — Configurable per-dataset via `db_config[<client>].healthcheck_retries` int override; helper `_mongo_healthcheck_retries(db_config)` threaded through `_materialize_task_dir` → `_task_toml(mongo_healthcheck_retries=...)`. Fallback to default 60 when absent.
  test_prepare_mongo_healthcheck.py::test_mongo_healthcheck_retries_override_honored (retries=120) + test_mongo_healthcheck_retries_override_absent_falls_back_to_default (retries=60) GREEN.
- SKIPPED: AC-3 — Goal 1 agnews + yelp live `rk run` non-zero rewards. Deferred to goal1-resume per plan step 5; live API cost belongs in validation/resume, not implementation.
  Plan step 5 explicitly defers this AC to the resume hook; entity body resume hook records the dependency.
- DONE: AC-4 — DAB regression. `uv run pytest packages/razorback-plugin-dab/tests/unit/ -q` → 123 passed, 1 skipped.
  All pre-existing PKG-13/14/15/16/21/25 unit tests stay green, including test_mongo_reachability_gate (asserts `retries >= 3`, satisfied by 60).

### Summary

Single-file change in `prepare.py` plus one new test module. AC-1 + AC-2 + AC-4 closed under TDD with RED→GREEN evidence; AC-3 explicitly deferred to goal1-resume per plan. No darwin live run executed (plan + stage discipline forbid it inside implementation). The new `healthcheck_retries` override is an opt-in dict key on mongo `db_config` entries; absent fields keep the default 60 retries × 5s = 5-minute budget, covering agnews/yelp worst-case mongorestore wall time.

## Stage Report: validation

- DONE: Re-run unit tests `uv run pytest packages/razorback-plugin-dab/tests/unit/` — confirm PKG-15 followup healthcheck-retries test GREEN + no regression in PKG-15/16/21/25 darwin tests.
  Full suite: 123 passed, 1 skipped (1.92s). New module test_prepare_mongo_healthcheck.py: 3/3 PASS (default=60, override=120 honored, absent→60 fallback).
- DONE: Docstring/comment honesty spot-check on prepare.py `_task_toml` per-dataset override mechanism.
  Comment block at L347-352 honestly states the 5-min budget AND the `db_config[<client>].healthcheck_retries` override path; `_mongo_healthcheck_retries` docstring (L501-507) describes widen/narrow semantics and None-fallback contract. No temporal/refactoring markers.
- DONE: Code review via superpowers:requesting-code-review.
  In-session review (no subagent dispatch — small focused diff, contained worktree). Verdict PASSED: tests green, naming honest, bool guard correct (`not isinstance(override, bool)` after isinstance(int)), kwarg default None preserves backwards compat, no drive-by refactors. Callers grep-verified: only `_materialize_task_dir` constructs `_task_toml`; all sites pass the new threading consistently.

### Summary

PKG-15 follow-up validation PASSED. All 4 ACs accounted for: AC-1 (defaults retries=60) + AC-2 (per-dataset override) + AC-4 (regression) verified GREEN; AC-3 (live agnews rk run) intentionally deferred to goal1-resume per plan step 5. The implementation diff is tight (38 lines in prepare.py, 89 lines of new tests), test coverage exercises real prepare_dataset_tasks end-to-end (no internal mocks), and the override mechanism is opt-in and backwards-compatible.

