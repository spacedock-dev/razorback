---
id: f4vk47r17zgms9dgezgckmp9
title: PKG-2 — Aggregator trustworthiness (errored-vs-completed, trial_name pairing, sampling validation, partial-DAB labeling, n<5 guard, silent-drop guard)
status: backlog
source: ML review Rev 2 (2026-05-19): P0-1, P0-2, P1-1, P1-2, P1-3, P1-4
started:
completed:
verdict:
score: 1.0
worktree:
issue:
pr:
mod-block:
---

## Problem

Six methodology defects in the aggregator + diff stack. None
affect M1..M7 numbers as currently cited (the 0.6746 verifies by
hand), but each one would invalidate a paired comparison or
a published claim. Bundled as one package because they touch
overlapping files
(`src/razorback/benchmarks/{dab,ade_bench}/aggregate.py`,
`src/razorback/diff/`, `src/razorback/spec/schema.py`) and ship
as one coherent shipment.

The six defects, from the ML review:

1. **P0-1 errored vs completed collapsed.** `summary.json` reports
   `n_trials=1, n_correct=0, score=0.0` identically for "agent ran
   and got it wrong" vs "agent crashed at setup before any LLM call
   fired". The FU-1 ade-bench result shows exactly this: score=0.0
   because `claude --version exit=127`, not because claude tried
   and failed. `rk runs diff` will treat crash-trials as failed
   trials — false negatives that bias comparisons against any
   condition where the agent is brittle in setup.

2. **P0-2 sampling.seed accepted on claude-cli specs.** The spec
   parser has no cross-validation: `agent: {kind: claude-cli,
   sampling: {seed: 42, temperature: 0.0}}` parses cleanly and
   pins the seed into `spec.frozen.yaml` and (for spacedock-solver)
   into `sealed_hash`. A reader would assume seed-reproducibility;
   Anthropic ignores seed. Design §6.2 says the spec parser
   validates against the registered schema before `AgentConfig` is
   constructed — not enforced.

3. **P1-1 partial-DAB headline mislabeled.** `summary.json` field
   `stratified_pass_at_1` is over whatever datasets the spec lists.
   For the M5 6-of-12 subset, the field reads as "DAB stratified
   pass@1" with no marker that 6 datasets are missing. Cited
   externally without the caveat, it implies full-DAB.

4. **P1-2 n=1 trials makes per-query CIs useless.** Wilson CI at
   n=1 returns ~0.83-wide bands; exact-McNemar p collapses
   entirely. Design §6.5 names N=5 as the floor below which
   "signal tests miss". `rk runs diff` happily runs at n=1 today.

5. **P1-3 aggregator silently drops unmapped trials.**
   `aggregate.py:99-102, 128-133` `if key is None: continue` —
   any time `trial_name_map` and the actual trial names disagree
   (dataset rename, prefix-separator change), trials vanish from
   the aggregate without warning. No assertion that
   `len(per_query) == expected_n_queries`. Silent corruption.

6. **P1-4 diff pairs by `(dataset, query_id, trial_index)`, not
   `trial_name`.** Design §6.5 says pair by `trial_name`
   (deterministic under seeded JobConfig); razorback uses
   trial_index which is only stable while `n_concurrent_trials=1`
   (hardcoded today). One constant change breaks every paired
   comparison silently. The M6 plan named this as a deliberate
   divergence but the ML reviewer graded the rationalization
   faulty.

## Unlocks

- `experiments.analyze` produces statistically valid paired
  comparisons that survive retry-or-resume scenarios.
- `runs.reconciling` can count actual completes (vs crashes) and
  decide whether to dispatch make-up runs vs error out.
- Any externally-cited result from this pipeline carries honest
  labels (partial-DAB marked, n<5 caveats surfaced).

## Acceptance criteria

**AC-1 — `summary.json` distinguishes errored from completed
trials.**
Verified by: a unit test feeds a `JobResult` with one
successful trial (score=1) + one errored trial (exception_info
set, no verifier_result) to the aggregator; the resulting
`summary.json` has `n_completed_trials: 1, n_errored_trials: 1,
score: 1.0` (one over one completed — NOT 0.5). When
`n_completed_trials == 0`, `score` is `null` and
`error_reason` carries the most common exception class name.

**AC-2 — Spec parser rejects sampling keys outside the agent's
`supported_sampling()`.**
Verified by: a unit test feeds a spec with `agent: {kind:
claude-cli, sampling: {seed: 42}}` and asserts `SpecError`
(exit 10) with message naming "seed not in supported_sampling
for claude-cli". Same for `top_p`. The check fires before
`AgentConfig` construction.

**AC-3 — `summary.json` carries `datasets_covered: [<slugs>]`
and `n_datasets_covered: N` whenever benchmark.kind == dab.**
Verified by: a unit test runs the DAB aggregator on a 6-of-12
input and asserts both fields are present and accurate. A
warning is emitted at `rk run` time when the spec's
`benchmark.datasets` is a strict subset of the 12 canonical DAB
datasets. The warning text names the missing datasets.

**AC-4 — `rk runs diff` refuses (exit 12 ConstraintViolation)
when median per-query `n_trials` < 5, unless `--allow-low-n` is
passed.**
Verified by: a unit test against a fixture run-dir with all
queries at n_trials=1 asserts exit 12 with a message naming
"median n_trials=1 < 5; pass --allow-low-n to override". A
second test with `--allow-low-n` asserts exit 0 plus a warning
in stderr.

**AC-5 — Aggregator hard-errors on unmapped `trial_name`.**
Verified by: a unit test feeds a `JobResult` with a
`trial_name` whose prefix is NOT in `trial_name_map` and
asserts the aggregator raises a typed `AggregatorError`
naming the unmapped name. `summary.json` is NOT written.
Negative case: a unit test with all trial_names mapped
succeeds and writes summary.json as before.

**AC-6 — `rk runs diff` pairs by `trial_name`, not by index.**
Verified by: a unit test feeds two run-dirs where the trial
ordering inside one query differs (run A: [trial_001, trial_002];
run B: [trial_002, trial_001]) and asserts the paired
comparison matches trial_001 ↔ trial_001 across runs, not by
position. Cite §6.5 verbatim in the implementation comment.

**AC-7 — M1..M7 + FU-1/FU-2 carry-forward tests stay green.**
Verified by: `uv run pytest` from a clean checkout of the
PKG-2 worktree branch tip exits 0 with the prior ~250+
tests passing alongside the new PKG-2 tests.

## Test plan

- **Unit tests:** errored-vs-completed shape (3 variants:
  all-errored, all-completed, mixed); sampling rejection
  (seed + top_p + valid); datasets_covered (full + subset);
  rk runs diff n<5 refusal (default + --allow-low-n);
  aggregator hard-error on unmapped trial_name; trial_name
  pairing (matched ordering + mismatched ordering).
- **Integration test:** rk run examples/specs/bookreview-nop.yaml
  with one query intentionally crashing (mocked via a
  TaskConfig that fails setup), assert summary.json carries
  n_completed=2, n_errored=1, score reflects 2 completes.
- **Acceptance command:** `uv run pytest` exits 0 from clean
  checkout.

## Out of scope

- Per-trial cost/latency accounting (separate concern; ships
  with PKG-4 HAL stack for the resource-consistency metric).
- Confidence elicitation (separate concern; HAL predictability
  dimension; deferred).
- `rk runs diff --format markdown` (M6 explicitly out-of-scopes;
  separate polish task).
- The four non-blocking M5 N-findings (404 diagnostic precision,
  HarborDriftError exit code, data_root portability, claude
  CLI bin hardcode) — none affect result trustworthiness; track-
  forward as housekeeping.
