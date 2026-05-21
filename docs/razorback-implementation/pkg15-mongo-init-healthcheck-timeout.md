---
id: mbvd6v5j5cscffzfryvr88qs
title: PKG-15 follow-up — mongo init healthcheck timeout (extend retries / startup wait)
status: backlog
source: PKG-15 follow-up — Goal 1 matrix 2026-05-20 (commits dae5d33 + 148c6af on archived branch spacedock-ensign/goal1-dab-paper-reproduction); direct-minimal/agnews failed Step main healthcheck after 12 consecutive retries
started:
completed:
verdict:
score: 0.85
worktree:
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
