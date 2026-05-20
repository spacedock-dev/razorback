---
id: pj4nm6c2qhxv9k1z8gwrtb5y
title: PKG-17 — rk run writes summary/manifest/events/per_trial_outcomes/lock to v2 run-dir
status: backlog
source: Staff SWE review 2026-05-20 finding F2; captain decision "File as PKG-18, ship before Goal 1" (filed here as PKG-17 per ID sequencing); Goal 1 AC-7 cost-ledger blocker
started:
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
mod-block:
---

## Problem

The v2 `rk run` (`src/razorback/cli/run.py:139-312`) writes only three files into the run-dir: `spec.frozen.yaml`, `provenance.yaml`, `_job_config.yaml`. Every downstream v2 command expects the legacy aggregator's output set (`manifest.json`, `summary.json`, `events.jsonl`, `per_trial_outcomes.json`, `lock.json`) and crashes against v2 run-dirs:

- **`rk runs show`** raises `FileNotFoundError` ("summary.json not found in <run-dir>") for every v2 run-dir per `src/razorback/runs/inspect.py:64-67`.
- **`rk runs list`** filters out every v2 run-dir because `manifest.json` is missing per `src/razorback/runs/inspect.py:23-25`.
- **`rk runs cost`** reads from the absent aggregator outputs — Goal 1's AC-7 (matrix cost ledger via `rk runs cost --root runs/goal1/`) is structurally broken.
- **`rk runs diff`** reads `per_trial_outcomes.json` (`src/razorback/diff/pairing.py:10-11`); the sidecar is only produced by `src/razorback/benchmarks/dab/aggregate.py:49,122` invoked from `_legacy/run.py`.
- Eight integration tests under `tests/integration/` that assert on `summary.json` / `manifest.json` are silently broken against v2 (e.g., `tests/integration/test_rk_run_nop.py:44-86`, `tests/integration/test_rk_run_bookreview_nop.py:40-77`).

PKG-13 T11 added a partial loader workaround so `rk score` could read from harbor's `result.json` directly. That workaround does NOT cover the other 4 downstream commands. The PKG-13 9/9 number was extractable; Goal 1's cost ledger is not.

The legacy aggregator at `src/razorback/_legacy/run.py:91-162` produced the right artifact set (`manifest`, `summary` via `aggregate_job_result`, `events` via `EventChannel`); v2 dropped them with no replacement hooked into the post-harbor exit path.

## Acceptance criteria

**AC-1 — v2 `rk run` writes `manifest.json` post-harbor-exit.**
After harbor's `harbor run` completes (success OR failure), `cli/run.py` invokes an aggregator that walks the harbor-produced trial dirs and writes `<run-dir>/manifest.json` with: `run_id`, `spec_path`, `frozen_spec_hash`, `provenance_hash`, `harbor_job_name`, `created_at`, `n_trials_total`, `n_trials_completed`, `n_trials_errored`, per-trial paths.

Verified by: a fresh `uv run rk run examples/specs/pkg13-bookreview-claude-harbor-dab-n3.yaml` writes `manifest.json` whose fields parse against a JSON schema in `src/razorback/runs/manifest_schema.json` (new file). `rk runs list` finds the run-dir.

**AC-2 — `summary.json` written with per-trial rewards + cost + stratified pass@1.**
The aggregator writes `<run-dir>/summary.json` with: per-trial `(trial_id, reward, cost_usd, wall_seconds, error_reason)`, aggregate counts, per-stratum pass@1 (no Wilson CI; that's `rk score`'s job), and total cost. Schema: existing `src/razorback/benchmarks/dab/aggregate.py:122` produces this shape for legacy; lift the producer to a v2-canonical location (`src/razorback/runs/aggregate.py` new file) that reads harbor's `result.json` + per-trial dirs.

Verified by: a fresh run writes `summary.json`. `rk runs show <run-dir>` prints the per-trial table without crashing. The PKG-13 honest re-run's run-dir backfills against this aggregator and produces the same 9/9 reward=1.0 as the rk score loader-fix workaround already does.

**AC-3 — `events.jsonl` aggregated from per-trial trajectories.**
Per-trial `events.jsonl` (already produced by harbor / the agent) is concatenated into a top-level `<run-dir>/events.jsonl` with each line prefixed by `{trial_id, line_offset}` for cross-trial correlation. This is the artifact `rk audit` walks.

Verified by: `rk audit --policy strict <run-dir>` reads the top-level events.jsonl AND each per-trial events.jsonl; both code paths return identical taint findings.

**AC-4 — `per_trial_outcomes.json` written for paired-stat use.**
The aggregator writes `<run-dir>/per_trial_outcomes.json` with one row per `(stratum, trial_id, reward, status)`. This is the artifact `rk runs diff` walks.

Verified by: a fresh run produces `per_trial_outcomes.json`. `rk runs diff <run-dir-A> <run-dir-B>` runs against two PKG-17-produced run-dirs without crashing.

**AC-5 — `lock.json` written with environment fingerprint at run time.**
`lock.json` records the run-time state of the things the freeze pipeline captured at freeze time (image digest, agent CLI hash, harbor version, plugin shape, model alias resolved). If lock.json's fingerprint disagrees with provenance.yaml's, `rk runs show` flags the drift visibly. This is the runtime-side companion to PKG-8's freeze-time pinning.

Verified by: a fresh run produces `lock.json`. An artificially modified provenance.yaml (test fixture) causes `rk runs show` to print a drift warning.

**AC-6 — `rk runs cost` against v2 run-dirs returns honest numbers.**
Goal 1's AC-7 (matrix cost ledger via `rk runs cost --root runs/goal1/`) functions: walks PKG-17-produced run-dirs and sums `summary.json::trials[].cost_usd`. No more "no manifest.json found, skipping" warnings on v2 run-dirs.

Verified by: a fresh smoke matrix (3 cells of bookreview + 3 cells of crmarenapro) produces a `rk runs cost --root <smoke-runs>` output that sums the per-cell `cost_usd` correctly.

**AC-7 — Eight integration tests under `tests/integration/` un-break against v2.**
The integration tests at:
- `tests/integration/test_rk_run_nop.py:44-86`
- `tests/integration/test_rk_run_bookreview_nop.py:40-77`
- (and the other 6 that the SWE review flagged)

…run green against v2 instead of silently asserting on absent files. If any of those tests are themselves outdated, they get updated in this PR to match the v2 artifact set; document each change in the stage report.

Verified by: `uv run pytest tests/integration/` exits 0 with no SKIPPED markers that weren't there before (i.e., the conftest's collect_ignore_glob list does not grow for these tests).

**AC-8 — PKG-13 result.json + harbor result.json still readable (no regression in `rk score`).**
The aggregator's output is additive; harbor's per-trial `result.json` files are not modified. `rk score` continues to read from the same source it did pre-PKG-17 (whatever the loader-fix path resolved to).

Verified by: `uv run rk score <pkg13-honest-rundir>` produces the same 9/9 Wilson CI output as it did pre-PKG-17.

## Test plan

- **Plan stage** reviews `_legacy/run.py:91-162` + `benchmarks/dab/aggregate.py:49,122` and identifies which legacy code is liftable into `src/razorback/runs/aggregate.py` without re-importing legacy.
- **Implementation stage** applies the lift TDD-first: write the AC-1+AC-2 schema-validation tests first, then implement. Each AC's verified-by is exercised before moving to the next.
- **Validation stage** runs the full 270+ test suite, the 8 integration tests, and a fresh `rk run` smoke against bookreview to confirm the artifact set emerges.

## Out of scope

- Backwards-compat with `_legacy/run.py` artifact paths. PKG-17 produces canonical v2 paths only; if anything still depends on legacy paths, it should be migrated separately.
- Re-running PKG-13's honest re-run with PKG-17's aggregator — the existing PKG-13 run-dir backfills (AC-2) which is enough.
- The `rk score` loader-fix from PKG-13 T11 — that loader stays; PKG-17 ADDS the summary.json path, doesn't replace the harbor result.json path.
- Cost ledger schema design beyond Goal 1's needs (e.g., per-token breakdown). Goal 1 needs `total_usd` per run-dir summed; that's it.

## Depends on

- e3 phase1-rk-run-v2-wrapper (DONE) — the v2 `rk run` body PKG-17 modifies.
- ta phase4a-rk-runs-cost (DONE) — the consumer of the cost ledger PKG-17 produces.
- PKG-13 (DONE) — its `rk score` loader-fix is the reference for "what reads from where today".

## Blocks

- Goal 1 — AC-7 (matrix cost ledger) is blocked without this. Captain authorized 2026-05-20 with "File as PKG-18, ship before Goal 1."
- `rk runs list / show / cost / diff` are broadly broken against v2 run-dirs until this lands.
