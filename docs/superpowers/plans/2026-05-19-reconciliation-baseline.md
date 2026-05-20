# Razorback v1 reconciliation baseline

**Date:** 2026-05-20 (corrected rerun)
**Razorback commit:** 5e5123a (investigation HEAD; razorback/dab code paths unchanged from 2a2be8c original-run HEAD — intervening commits only add backlog entity files)
**Resolves:** AC-0.1(a) in 2026-05-19-razorback-reconciliation-plan.md
**Cost:** $0 spent (subscription-billed via `CLAUDE_CODE_OAUTH_TOKEN`)
**Status:** Corrected baseline — this is the Phase 2 expected-shift-band reference. The original 2026-05-20 baseline at this AC produced a 0/3 result that was diagnosed as a Colima bind-mount artifact (see "Colima `/tmp` path gotcha" subsection below) and superseded by this rerun.

## Spec

- File: `examples/specs/bookreview-claude.yaml`
- Dataset: bookreview (3 query tasks: q1, q2, q3)
- N (trials per task): 1
- Agent: `claude-cli` (model `claude-opus-4-5`, version `2.1.142 (Claude Code)`)
- Sampling: `temperature: 0.0`
- Access mode: in-tree adapter, dump-file mode (v1)
- Runs-dir: `/Users/clkao/git/razorback/.runs/baseline-rerun-20260520-bookreview/` (Colima-visible per `tests/conftest.py:14`)

## Headline

- Pass rate: **100.0%** (`stratified_pass_at_1 = 1.0`, `bookreview.dataset_pass_at_1 = 1.0`)
- Trials run: 3 total; 3 pass, 0 fail, 0 errored
- Cost: **$0** (subscription auth; `agent_result.cost_usd` is null per trial — same telemetry gap as before; reward file is independent of cost metering)
- Wall-clock: 6:56 (job total); per-trial agent execution durations 153s / 112s / 110s for q1 / q2 / q3
- Determinism: matches M5 (commit `f3f8c0e`) 3/3 = 1.000 on the same `dab-agent:latest` image (sha256 `018978c879d5...`)

## Per-task breakdown

| Task          | N | Pass | Fail | Error | Pass rate |
| ------------- | - | ---- | ---- | ----- | --------- |
| bookreview-q1 | 1 | 1    | 0    | 0     | 1.0       |
| bookreview-q2 | 1 | 1    | 0    | 0     | 1.0       |
| bookreview-q3 | 1 | 1    | 0    | 0     | 1.0       |

Trial-state taxonomy: `stats.n_completed_trials = 3`, `n_errored_trials = 0`. Per-trial reward 1.0 across all three.

## What Phase 2 measures against

V1 on bookreview at HEAD `5e5123a` (and equivalently at `2a2be8c`) is **fully functional** when run with a Colima-visible `--runs-dir`. Pass rate is 100% on the bookreview dataset (q1-q3). Phase 2's expected-shift-band documentation should reflect this: v2's bookreview score must be near-100% to be non-regressive; any drop below this baseline on the same dataset constitutes a regression to be triaged.

The "v1 is broken-broken" framing in the original (superseded) baseline doc was wrong — it described a run-environment defect, not a code-path defect.

## Run-dir reference

- Location: `/Users/clkao/git/razorback/.runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/`
- Key files inspected:
  - `summary.json` — DAB-shaped pass@1 aggregation (per §6.5)
  - `per_trial_outcomes.json` — 3 outcomes, all reward 1.0
  - `result.json` — harbor JobResult, `stats.n_completed_trials = 3`, `cost_usd: null`
  - `bookreview-q1__xgRg3Eo/result.json` — per-trial harbor TrialResult, no exception
  - `bookreview-q1__xgRg3Eo/steps/main/verifier/reward.json` — `{"reward": 1.0}` (present on host, confirming bind-mount worked)
  - `events.jsonl` — 15 hook events (start/environment_start/agent_start/verification_start/end × 3 trials)
  - `spec.frozen.yaml`, `provenance.yaml`, `lock.json` — captured at freeze
- Run-dir NOT committed (per brief). This document cites it as a reference path.

## Smoke run (AC-0.1(b)) — captured on the same v1 commit

- Spec: `examples/specs/_deterministic-smoke.yaml`
- Result: `stratified_pass_at_1 = 1.0`, 3/3 pass (`bookreview.dataset_pass_at_1 = 1.0`)
- Per-trial reward: q1=1.0, q2=1.0, q3=1.0
- Wall-clock: 6:30 (job total); per-trial agent execution durations 128s / 88s / 133s
- Run-dir: `/Users/clkao/git/razorback/.runs/baseline-rerun-20260520-smoke/_deterministic-smoke/bc7421b6432e225a/`
- This outcome is recorded in the smoke spec itself per AC-0.1(b) procedure.

## Colima `/tmp` path gotcha (superseded original run, preserved)

The original AC-0.1(a) run on 2026-05-20 (commit `e9d7c43`) produced a 0/3 result. Root cause was diagnosed in `docs/superpowers/plans/2026-05-20-v1-bookreview-regression-investigation.md` (commit `5e5123a`):

- Original `--runs-dir` was `/tmp/razorback-baseline-20260520`, which on macOS resolves to `/private/tmp/...`.
- Colima's VM bind-mounts ONLY `/Users/clkao` (verified via `colima ssh -- mount` → `mount0 on /Users/clkao type virtiofs`). Host paths under `/private/tmp/` are invisible inside the Colima VM.
- Docker-compose's bind mount of the trial verifier dir (`harbor/environments/docker/docker-compose-base.yaml:3-9`, source = `trial_paths.verifier_dir.resolve().absolute()` from `harbor/environments/docker/docker.py:193-195`) therefore resolved to a VM-side tmpfs path the container backed up with empty storage, not the host directory harbor's verifier later checks (`harbor/verifier/verifier.py:201-210`).
- The container's `test.sh` wrote `/logs/verifier/reward.json` successfully inside the VM, but the write never reached the host. Harbor then raised `RewardFileNotFoundError` on every trial.
- M5 (commit `f3f8c0e`) succeeded on the same image+code at 3/3 = 1.000 because its driver `tests/integration/test_rk_run_bookreview_claude.py:46` routes `--runs-dir` through the `colima_safe_tmp_path` fixture (`tests/conftest.py:12-23`), whose docstring at `tests/conftest.py:14` explicitly states "A tmp dir under /Users/... that Colima mounts into the docker VM."

Original (superseded) result for reference:

- Pass rate: 0.0% (3/3 `RewardFileNotFoundError`)
- Run-dir: `/tmp/razorback-baseline-20260520/m3-bookreview-claude/b62c780119d24d68/`
- Wall-clock: 5:02; per-trial agent durations 77s / 119s / 67s
- Per-trial agent execution succeeded (real Claude calls 67-119s each); failure was strictly at the verifier-side host-path read.

The constraint exists in the codebase but is enforced ONLY via the test fixture; the CLI `rk run --runs-dir <path>` currently accepts any path and silently produces 100% failures when the path is outside Colima's mount scope. Candidate remediations (terse, for FO decision):

1. Add a CLI guard in `src/razorback/cli/run.py` that refuses to start if `runs_dir.resolve()` is not visible to the docker VM on macOS+Colima (e.g. probe via a canary file or check against discovered virtiofs mounts).
2. Document the constraint in the workflow README and adopt a `.runs/` directory convention rooted at the repo (already done in this rerun; `.runs/` is the existing gitignore-aware pattern via `_runs/`-style suffix — recommend adding `.runs/` to `.gitignore` to lock the convention).
3. Promote a start-of-trial mount-canary probe into harbor (out-of-tree change). Catches the failure class across all macOS-Colima users.

## Phase 0 side findings (surfaced for Phase 1)

A. **Integration test consistent with corrected baseline.** `tests/integration/test_rk_run_bookreview_claude.py` asserts `bookreview.dataset_pass_at_1 > 0.0` after `uv run rk run examples/specs/bookreview-claude.yaml`. The test passes against this corrected baseline (and against M5). The original baseline doc claimed the test "contradicts HEAD" — that claim was wrong; the test's `colima_safe_tmp_path` fixture is exactly the discipline this rerun applies. The contradiction was the run invocation, not the code under test.

B. **Smoke spec runs 3 tasks, not 1.** `examples/specs/_deterministic-smoke.yaml` declares `datasets: [bookreview]`, and the DAB adapter (`razorback.benchmarks.dab.prepare.prepare_dataset_tasks`) expands a dataset name to every `query*/` subdir under `query_<dataset>/`. There is no per-query selector in the current spec schema, so AC-0.1(b)'s "one task" intent is not realized today. The smoke runs 3 trials, all pass deterministically. This remains a follow-up for Phase 1 scoping (whether to add a `query_ids: [1]`-style selector to the spec schema or to ship a single-query bookreview-q1 dataset shape) — do NOT add a selector now.

C. **Subscription-auth cost telemetry gap.** With `CLAUDE_CODE_OAUTH_TOKEN` (Claude Code subscription) the per-trial `agent_result.cost_usd` is `null` and the five token fields are all `null` on every step result. Phase 4a's `rk runs cost` work will need a different telemetry source on this access mode (or to mark "subscription-billed; per-call cost not retrievable"). The §7.2 `phase_stats.json` schema mandates the five token fields as required; the v1 claude-cli access path cannot populate them under OAuth subscription auth.

## Phase 2 AC-6 pre-registered expected-shift bands (committed BEFORE the comparison run)

This section is the AC-6 commitment: every per-dataset live-DB-vs-dump-file
shift band is recorded HERE in a commit that precedes the Phase 2 12-dataset
matrix run-dir commit (Task 15 of `docs/razorback-implementation/plans/phase2-dab-harbor-adapter.md`).
A surprise reversal in any row flags a real bug (mechanism failure, not
statistical noise).

The v1 dump-file column reflects M5's per-dataset pass-rate where measured;
"n/a" marks datasets v1 never ran end-to-end (those were only exercised
piecewise during M3 prototyping). Direction notation: `↓` = live-DB is
expected to score lower than dump-file; `↑` = higher; `≈` = within noise.

| Dataset | v1 dump-file score (pre-correction) | Expected direction (live-DB vs dump-file) | Expected magnitude | Reasoning |
|---|---|---|---|---|
| bookreview | 1.000 (3/3, this doc's headline) | ↓ | -0.10 to -0.30 | bookreview's 1.000 v1 run almost certainly grepped books_info.sql per archived PKG-3; agent must learn live SQL now. |
| agnews | n/a (M3 only) | ↓ | -0.05 to -0.20 | mongo + sqlite backend mix; dump-file mode let the agent read the mongo dump folder as text — live mongo forces real queries. |
| crmarenapro | n/a | ↓ | -0.10 to -0.25 | duckdb + postgres + sqlite triple is the most complex mix; live-DB removes file-grep shortcuts on all three. |
| DEPS_DEV_V1 | n/a | ≈ to ↓ | -0.05 to -0.15 | duckdb + sqlite; duckdb files are already query-mediated even in dump-file mode, so smaller shift expected. |
| GITHUB_REPOS | n/a | ≈ to ↓ | -0.05 to -0.15 | Same reasoning as DEPS_DEV_V1; duckdb + sqlite. |
| googlelocal | n/a | ↓ | -0.10 to -0.25 | postgres + sqlite; postgres dump-file is the canonical grep target. |
| music_brainz_20k | n/a | ≈ to ↓ | -0.05 to -0.15 | duckdb + sqlite. |
| PANCANCER_ATLAS | n/a | ↓ | -0.10 to -0.25 | duckdb + postgres; live postgres forces SQL on the dominant backend. |
| PATENTS | n/a | ↓ | -0.10 to -0.25 | postgres + sqlite. |
| stockindex | n/a | ≈ to ↓ | -0.05 to -0.15 | duckdb + sqlite. |
| stockmarket | n/a | ≈ to ↓ | -0.05 to -0.15 | duckdb + sqlite. |
| yelp | n/a | ↓ | -0.10 to -0.25 | duckdb + mongo; mongo live-mode is the larger shift driver. |

**AC-6 acceptance criterion.** Observed shifts must fall within the
pre-registered direction; magnitudes must fall within 2× of the predicted
band. A reversed direction (live-DB scores higher than dump-file on any
postgres-or-mongo-backed dataset) flags a real bug — mechanism failure
in either the dump-file v1 path (false-positive grep matches that
artificially inflated v1) or the live-DB v2 path (compose stack not
actually being queried). Per-trial stratification with Wilson 95% CI
from `rk score` is the readout shape (spec §3.2, §8.3a).

**Methodology note.** Only bookreview has a v1 end-to-end number in
this doc. For the eleven `n/a` rows the pre-registration is direction
+ magnitude only; AC-6 enforcement compares observed live-DB scores
against the direction prediction. The magnitude bands are calibrated
to bookreview's expected drop (postgres-heavy, the strongest
file-grep shortcut). Datasets with smaller expected shifts
(duckdb-heavy) get tighter bands; datasets with stronger shifts
(postgres + mongo) get wider bands.

**Where the run-dir commit lands.** Per Task 15 of the Phase 2 plan,
the comparison run-dir commit appends a reconciliation table below
this section AFTER the live-DB matrix completes. That commit MUST
postdate the commit that lands this pre-registration table — git log
ordering enforces AC-6 methodology.
