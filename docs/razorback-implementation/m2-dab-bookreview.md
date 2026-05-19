---
id: erpsz704gkyytn8b8g86ysp8
title: M2 — DAB adapter for bookreview (one dataset)
status: plan
source: design §8
started: 2026-05-19T07:42:22Z
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
mod-block:
---

## Problem

Stand up the DAB-as-harbor-adapter shape for a single dataset
(`bookreview`): a harbor task manifest, a `prepare.py` that
materializes the dataset's safe files into harbor's workspace
(excluding `ground_truth.csv`), a `verify.py` that runs the
dataset's `validate.py` against `answers.json` and emits harbor's
per-task reward shape, and an `aggregate.py` that reads
`JobResult.trial_results` and writes `summary.json` with the
`PerQueryStats` records the §6.5 stratified average needs. See
§6.5 and §8.M2.

The DAB ground-truth and dataset files live in the consuming repo
(`/Users/clkao/git/dataagentbench/data/`, per §7). M2 wires
razorback against that path through the spec's
`benchmark.data_root`.

## Acceptance criteria

**AC-1 — `aggregate.py` consumes a frozen synthetic input and
produces the expected `summary.json`.**
Verified by: a unit test feeds a hand-written `JobResult` fixture
covering bookreview's queries to `aggregate.py` and asserts the
resulting `summary.json` matches a checked-in golden file (per-
query pass@1, per-dataset mean, stratified macro-average all
present and numerically correct).

**AC-2 — `prepare.py` excludes `ground_truth.csv` from the
materialized workspace.**
Verified by: a unit test invokes `prepare.py` against a fixture
dataset dir containing `ground_truth.csv` and asserts the file is
absent from the target workspace.

**AC-3 — `verify.py` emits harbor's reward shape against
bookreview's `answers.json`.**
Verified by: a unit test feeds a fixture `answers.json` (correct
and incorrect cases) and asserts `verify.py` writes
`/logs/verifier/reward.json` (or `reward.txt`) in the contract
documented in `docs/pre-m1-findings.md` and that the value
matches the expected reward for each fixture.

**AC-4 — `JobConfig.retry.max_retries == 0` for DAB runs.**
Verified by: a unit test inspecting the spec → JobConfig
translator's output for a DAB spec asserts `retry.max_retries ==
0`. The cite is §6.5: "A retry-after-failure that harbor marks as
a passed trial would inflate pass@1".

**AC-5 — `aggregate.py` does NOT read `JobResult.stats.evals`.**
Verified by: a code-level check (`grep -n 'stats\\.evals'
src/razorback/benchmarks/dab/aggregate.py` returns no matches).
The cite is §6.5: harbor's `JobStats.evals` is per-dataset
micro-average, not what DAB needs.

**AC-6 — `per_trial_state_reset` declared on the DAB adapter
matches §6.5.**
Verified by: a unit test imports the DAB adapter's
`per_trial_state_reset` attribute and asserts
`{"agent_container": True, "compose_services": True,
"host_workspace": True}` per §6.5.

**AC-7 — End-to-end smoke against bookreview through the nop
agent runs and writes a `summary.json` with stratified pass@1.**
Verified by: `uv run rk run examples/specs/bookreview-nop.yaml`
exits 0 and the run-dir's `summary.json` contains a stratified
pass@1 line for bookreview. (Nop agent always answers wrong, so
pass@1 = 0.0 is the expected value; the test asserts the field
exists and is numeric, not its score.)

## Test plan

- **Unit tests:** aggregator with frozen synthetic input;
  prepare's ground-truth exclusion; verify's reward emission;
  translator's retry-zero assertion; declared
  `per_trial_state_reset` shape.
- **Integration test:** `rk run examples/specs/bookreview-
  nop.yaml` end-to-end against the real bookreview dataset under
  `/Users/clkao/git/dataagentbench/data/`. Uses nop agent so the
  test cost is bounded.
- **Acceptance command:** `uv run rk run examples/specs/
  bookreview-nop.yaml` plus the aggregator unit test.

## Out of scope

- The other 11 DAB datasets — §M5.
- Real agent (Claude / Codex) integration — §M3.
- Halt-resume, prompt content hashing — §M4.
- Provenance resolution — §M5.
- `runs diff`, paired statistics — §M6.
