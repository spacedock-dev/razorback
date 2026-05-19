---
id: vmxa9q2xsvawzmcqe2na6zt5
title: PKG-4 — HAL reliability stack (trajectory + cost + perturbation + safety judge + 12-metric aggregator)
status: backlog
source: Princeton HAL Reliability Dashboard (https://hal.cs.princeton.edu/reliability/methodology/); CL pivot 2026-05-19
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

Razorback today produces accuracy-shaped scores (M5 stratified
pass@1). Princeton's HAL Reliability framework argues "rising
accuracy obscures unreliability" and evaluates agents on four
additional dimensions — Consistency, Predictability, Robustness,
Safety — across 12 metrics. The HAL paper benchmarks 14 agents
across GAIA + τ-bench and finds recent capability gains have
yielded only small improvements in reliability.

Razorback currently produces 2 of HAL's 12 metrics (outcome and
resource consistency, once we raise default trials). The other
10 require new instrumentation on the agent + aggregator surface.

This package lands the four reliability dimensions (minus
confidence-based predictability, deferred for cost reasons —
needs an extra LLM call per trial that we don't have a budget
for yet).

The five sub-deliverables, ordered by dependency:

1. **Per-trial trajectory capture** for ClaudeCliAgent and
   SpacedockSolverAgent (write action list to
   `agent/trajectory.jsonl`). Foundational — both
   trajectory-distribution (Jensen-Shannon) and trajectory-
   sequence (normalized Levenshtein) consistency metrics need it.

2. **Per-trial cost+latency accounting** in `result.json`. Harbor
   already exposes `TrialResult.compute_token_cost_totals()` —
   wire it through into our `result.json` per-trial, not just
   aggregate. Unlocks resource-consistency CV.

3. **Perturbation-variant specs** (baseline / fault-injection /
   structural / prompt-rephrase). The spec gains a
   `perturbations:` block; razorback's translator fans out one
   `rk run` per variant; an aggregator joins per-variant scores
   into HAL's three robustness ratios.

4. **Safety LLM-judge verifier** over `events.jsonl` post-run.
   HAL ships four default constraints: no PII exposure, no
   destructive operations, rate-limit respect, data
   minimization. The judge emits compliance + max-severity per
   trial; aggregator composes into HAL's compliance + conditional-
   severity metrics.

5. **HAL 12-metric aggregator** composes (1)-(4) into the 4
   dimension scores plus overall reliability R = mean of
   Consistency + Predictability + Robustness. Safety is reported
   separately per HAL methodology.

## Unlocks

- `experiments.full` for reliability-focused hypotheses can
  produce all 12 HAL metrics in a single run.
- HAL leaderboard reproducibility: razorback's `summary.json`
  shape becomes a superset of HAL's reporting schema.
- Reliability experiments (consistency variance, robustness
  ratios, safety constraint violations) become a first-class
  research target alongside accuracy experiments.

## Acceptance criteria

**AC-1 — Per-trial trajectory captured as `agent/trajectory.jsonl`
for both ClaudeCliAgent and SpacedockSolverAgent.**
Verified by: a unit test against a fixture claude run asserts
`agent/trajectory.jsonl` exists, each line is a valid JSON
object with `step_index`, `tool_name`, `tool_args` (truncated
or sanitized), `tool_result_summary`. Order matches actual
agent execution order. SpacedockSolverAgent captures
per-stage trajectories.

**AC-2 — Outcome consistency, trajectory-distribution
consistency, trajectory-sequence consistency, and resource
consistency are computed and emitted in `summary.json`.**
Verified by: a unit test feeds a fixture run-dir with K=5
trials of the same query (varying outcomes + trajectories);
the aggregator emits `consistency: {outcome: <float>,
trajectory_dist: <float>, trajectory_seq: <float>, resource:
<float>}` each in [0, 1]. Match HAL methodology page formulas
(Jensen-Shannon for dist, normalized Levenshtein for seq,
Bernoulli-variance ratio for outcome, exp(-CV) for resource).

**AC-3 — Per-trial cost+latency in `result.json`.**
Verified by: a unit test against a fixture trial asserts
`result.json` carries `tokens_in`, `tokens_out`, `cost_usd`,
`wallclock_s`, `n_api_calls`. The aggregator's
resource_consistency reads these.

**AC-4 — Perturbation-variant specs: spec gains a
`perturbations:` block; translator dispatches one harbor Job
per variant; cross-variant aggregator produces fault,
structural, prompt robustness ratios.**
Verified by: a unit test feeds a spec with three perturbation
variants and asserts the translator emits four harbor Jobs
(baseline + three perturbations). A second test feeds fixture
per-variant scores and asserts the cross-variant aggregator
produces `robustness: {fault: <ratio>, structural: <ratio>,
prompt: <ratio>}` each in [0, 1] per HAL's clamp.

**AC-5 — Safety LLM-judge verifier emits compliance + severity
per trial.**
Verified by: a unit test feeds a fixture `events.jsonl`
containing both a no-PII trial and a PII-leak trial (synthetic
violation); the judge marks the leak trial with
`violations: ["pii_exposure"], max_severity: "high"`. A second
test asserts the aggregator composes per-trial judgments into
`safety: {compliance: <float>, conditional_severity: <float>,
overall: <float>}` per HAL's formulas.

**AC-6 — HAL 12-metric aggregator composes (1)-(5) into the
overall R + per-dimension scores.**
Verified by: a unit test feeds a synthetic run-dir tree with
known per-metric inputs and asserts the resulting
`summary.json` has `hal: {reliability: <R>, consistency:
<R_Con>, predictability: <R_Pred>, robustness: <R_Rob>,
safety: <R_Saf>, metrics: {...all 12...}}`. Match HAL
methodology weightings (Con: 1/3 outcome + 1/3 trajectory-mean
+ 1/3 resource; Pred: Brier; Rob: 1/3 each; Saf separate).

**AC-7 — Carry-forward tests stay green.**
Verified by: `uv run pytest` exits 0 with prior ~250+ tests
passing alongside new PKG-4 tests.

## Test plan

- **Unit tests:** trajectory.jsonl shape per agent; consistency
  metric math (each of the four); per-trial cost extraction;
  perturbation spec parsing + translator fan-out; safety judge
  fixture (compliant + non-compliant); HAL 12-metric aggregator
  composition.
- **Integration test:** one perturbation-variant run end-to-end
  against bookreview with the nop agent (cost-free); assert
  per-variant scores land + cross-variant ratios computed +
  HAL aggregator emits the full shape.
- **Acceptance command:** `uv run pytest` exits 0; sample HAL
  summary.json from a fixture run-dir matches the HAL
  methodology's expected shape.

## Out of scope

- **Predictability dimension (Brier, calibration, AUROC,
  risk-coverage).** Requires per-trial self-reported confidence,
  which needs an extra LLM call per trial. Defer until cost
  budget makes sense.
- **Live reliability runs against GAIA or τ-bench.** PKG-4 builds
  the instrumentation; running a real reliability experiment is
  a downstream task (uses experiments workflow once it's
  commissioned).
- **HAL's confidence-consistency sub-metric.** Computed but not
  in HAL's R_Con aggregate per their methodology; skip until
  predictability lands.
