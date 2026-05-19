---
id: erpsz704gkyytn8b8g86ysp8
title: M2 — DAB adapter for bookreview (one dataset)
status: implementation
source: design §8
started: 2026-05-19T07:42:22Z
completed:
verdict:
score: 0.9
worktree: .worktrees/spacedock-ensign-m2-dab-bookreview
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

## Stage Report: plan

- DONE: Plan steps map 1:1 to the 7 ACs in the M2 entity body, each with the design-doc §-cite that governs it (§6.5 DAB-as-harbor-adapter shape, §7 repository layout for benchmarks/dab/, §6.1 spec → JobConfig surface inherited from M1).
  AC↔task map table at the top of the plan; each AC names its governing §-cite and the tasks that implement and assert it.
- DONE: The riskiest contract for M2 — that aggregator output against a frozen synthetic input matches a golden — is a stand-alone unit test in plan Task 1, BEFORE wiring `prepare`/`verify` into harbor. The integration test against the real bookreview dataset (under /Users/clkao/git/dataagentbench/data/) comes AFTER the aggregator math is locked.
  Task 1 authors the golden fixture and Task 2 implements `aggregate.py` against it; the integration test (Task 11) runs only after Tasks 4–9 have wired prepare/verify/translator/orchestrator end-to-end.
- DONE: The plan is committed to docs/razorback-implementation/plans/m2-dab-bookreview.md on main as a single file, and cross-references M1's already-landed spec parser and JobConfig translator (the M2 entity inherits those surfaces; M2 does NOT redo them).
  Plan path: `docs/razorback-implementation/plans/m2-dab-bookreview.md` (single file on main). Plan header's "M1 inputs (do not duplicate)" block names the M1 modules (spec/schema.py, compat/harbor_0_6_6.py, run.py, manifest.py, observers/, errors.py) that M2 extends rather than reimplements. Task 14 adds a cross-reference line in the entity Test plan.

### Summary

Plan written via the superpowers:writing-plans skill, 15 tasks (0–14) ordered riskiest-contract-first. Task 1 authors a golden `summary.json` and synthetic `trial_results.json` fixture; Task 2 implements `aggregate.py` to produce byte-exact output. Tasks 3–9 build out the supporting surfaces (per_trial_state_reset declaration, prepare.py, verify.py, spec schema extension, translator with retry-zero and trial-name map, acceptance spec, orchestrator dispatch). Task 7 absorbs the prepare/verify rewrite needed once the bind-mount-vs-tests-dir choice was made; the simpler "copy validate.py into /tests/" shape avoids a host-path bind mount entirely and keeps AC-2 trivially provable. Task 11's end-to-end runs against the real bookreview dataset under `/Users/clkao/git/dataagentbench/data/query_bookreview/` and asserts `summary.json` contains a numeric `stratified_pass_at_1` plus three per-query `pass_at_1: 0.0` (nop agent always wrong). Task 12 encodes AC-5's grep gate as a permanent pytest. Plan stays on main; no worktree was created for the plan stage.
