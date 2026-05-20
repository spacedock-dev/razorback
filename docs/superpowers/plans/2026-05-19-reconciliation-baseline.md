# Razorback v1 reconciliation baseline (pre-correction reference)

**Date:** 2026-05-20
**Razorback commit:** 2a2be8cc148ed049d3ba5febba7ff16cb16112dc
**Resolves:** AC-0.1(a) in 2026-05-19-razorback-reconciliation-plan.md
**Cost:** $0 spent (auth resolved via `CLAUDE_CODE_OAUTH_TOKEN`, subscription-billed)
**Status:** Pre-correction reference — for Phase 2 expected-shift-band documentation, NOT for Phase 1-3 walking-skeleton anchor (that role belongs to the deterministic smoke at `examples/specs/_deterministic-smoke.yaml`).

## Spec

- File: `examples/specs/bookreview-claude.yaml`
- Dataset: bookreview (3 query tasks: q1, q2, q3)
- N (trials per task): 1
- Agent: `claude-cli` (model `claude-opus-4-5`, version `2.1.142 (Claude Code)`)
- Sampling: `temperature: 0.0`
- Access mode: in-tree adapter, dump-file mode (v1)

## Headline

- Pass rate: **0.0%** (`stratified_pass_at_1 = 0.0`, `bookreview.dataset_pass_at_1 = 0.0`)
- Wilson CI: not computed; degenerate at c=0/n=3 (one-sided 95% upper bound ≈ 60.2% via Wilson). The CI is uninformative because the failure is structural, not statistical.
- Trials run: 3 total; 0 pass, 3 fail (all fail with `RewardFileNotFoundError`, not with a low-reward answer)
- Cost: **$0** (subscription auth path; `agent_result.cost_usd` is null in the harbor wrapper for every trial)
- Wall-clock: 5:02 (302s); per-trial agent execution durations 77s / 119s / 67s for q1 / q2 / q3

## Per-task breakdown

| Task          | N | Pass | Fail | Error | Pass rate | Failure mode             |
| ------------- | - | ---- | ---- | ----- | --------- | ------------------------ |
| bookreview-q1 | 1 | 0    | 1    | 0     | 0.0       | RewardFileNotFoundError  |
| bookreview-q2 | 1 | 0    | 1    | 0     | 0.0       | RewardFileNotFoundError  |
| bookreview-q3 | 1 | 0    | 1    | 0     | 0.0       | RewardFileNotFoundError  |

Trial-state taxonomy: harbor's job-level `stats.n_completed_trials = 3`, `n_errored_trials = 0` — every trial **completed** from harbor's perspective (the verifier ran, raised a typed error, and harbor recorded a reward of 0). None were `errored` in harbor's sense. The 3 "fail" rows above are razorback's interpretation: agent ran, verifier failed to produce a reward file, reward defaulted to 0.

## The degraded-path failure mode

Every trial fails with the same exception at the verifier step. From `bookreview-q1__GBudFby/result.json` (excerpt):

```
File ".venv/lib/python3.12/site-packages/harbor/trial/trial.py", line 602, in _verify_step
    step_result.verifier_result = await asyncio.wait_for(
File ".venv/lib/python3.12/site-packages/harbor/verifier/verifier.py", line 206, in verify
    raise RewardFileNotFoundError(
harbor.verifier.verifier.RewardFileNotFoundError: No reward file found at
  .../bookreview-q1__GBudFby/verifier/reward.txt or
  .../bookreview-q1__GBudFby/verifier/reward.json
```

What this tells Phase 2: v1's failure on this path is **verifier-broken**, not low-score. The agent runs (77-119s of real Claude invocation per trial), the agent execution returns, then harbor's verifier (`harbor/verifier/verifier.py` v0.6.6) calls `environment.exec(test_script)` and afterwards looks for the reward file on the host side and finds neither `verifier/reward.txt` nor `verifier/reward.json`. The trial's `steps/main/verifier/` directory is empty after the run; either `test.sh` didn't write the reward file inside the container or harbor didn't download it back.

`agent_result.cost_usd` and the five token fields are all `null` on every step result — harbor's `claude-cli` agent wrapper in this access mode doesn't report token accounting (subscription auth path, no per-call metering). Phase 4a (`rk runs cost`) will need a different telemetry source for this access mode.

Phase 2 will measure v2's bookreview score and compare against this 0% reference; the expected shift is "v2 passes some trials" (any positive pass rate), because v1 is broken-broken on this triangle, not merely low-scoring. The shift band reflects this discontinuity.

## Run-dir reference

- Location: `/tmp/razorback-baseline-20260520/m3-bookreview-claude/b62c780119d24d68/`
- Key files inspected:
  - `summary.json` — DAB-shaped pass@1 aggregation (per §6.5)
  - `per_trial_outcomes.json` — 3 outcomes, all reward 0.0
  - `result.json` — harbor JobResult, `stats.n_completed_trials = 3`, `cost_usd: null`
  - `bookreview-q1__GBudFby/result.json` — per-trial harbor TrialResult with the typed exception_info above
  - `events.jsonl` — 15 hook events (start/environment_start/agent_start/verification_start/end × 3 trials)
  - `spec.frozen.yaml`, `provenance.yaml` — captured at freeze
- Run-dir NOT committed (per brief). This document cites it as a reference path.

## Phase 0 side findings (surfaced for Phase 1)

A. **Integration test contradicts HEAD.** `tests/integration/test_rk_run_bookreview_claude.py` asserts `bookreview.dataset_pass_at_1 > 0.0` after `uv run rk run examples/specs/bookreview-claude.yaml`. On commit 2a2be8c the value is 0.0; the test would fail if its skipif gate (which requires DAB data + `claude` CLI + auth + `dab-agent:latest` image — all present in this environment) passes. The test inventory at `docs/superpowers/plans/2026-05-19-razorback-test-inventory.md` classifies this file as RE-AUTHOR for v2; Phase 1 plan stage should cross-check whether the v1 contract this test was written against is the contract this baseline run executed, or whether HEAD regressed the path the test claims to cover.

B. **Smoke spec runs 3 tasks, not 1.** `examples/specs/_deterministic-smoke.yaml` declares `datasets: [bookreview]`, and the DAB adapter (`razorback.benchmarks.dab.prepare.prepare_dataset_tasks`) expands a dataset name to every `query*/` subdir under `query_<dataset>/`. There is no per-query selector in the current spec schema, so AC-0.1(b)'s "one task" intent is not realized today. The smoke ran 3 trials, all 0/3, deterministically. This is a follow-up for Phase 1 scoping (whether to add a `query_ids: [1]`-style selector to the spec schema or to ship a single-query bookreview-q1 dataset shape) — do NOT add a selector now.

C. **Subscription-auth cost telemetry gap.** With `CLAUDE_CODE_OAUTH_TOKEN` (Claude Code subscription) the per-trial `agent_result.cost_usd` is `null` and the five token fields are all `null` on every step result. Phase 4a's `rk runs cost` work will need a different telemetry source on this access mode (or to mark "subscription-billed; per-call cost not retrievable"). The §7.2 `phase_stats.json` schema mandates the five token fields as required; the v1 claude-cli access path cannot populate them under OAuth subscription auth.

## Smoke run (AC-0.1(b)) — captured on the same v1 commit

- Spec: `examples/specs/_deterministic-smoke.yaml`
- Result: `stratified_pass_at_1 = 0.0`, same failure mode (3/3 RewardFileNotFoundError)
- Wall-clock: 5:04 (304s)
- Run-dir: `/tmp/razorback-baseline-20260520-smoke/_deterministic-smoke/bc7421b6432e225a/`
- This outcome is recorded in the smoke spec itself per AC-0.1(b) procedure.
