---
id: xmnmxmphkmvdysatn39awsyp
title: Phase 4a — rk score Wilson CIs + stratified mean + against-constant
status: plan
source: plan Phase 4a + spec §3.2 + §8.3a (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T07:12:27Z
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
mod-block:
---

## Problem

Phase 4a ships the single-run statistical readout `rk score` per
spec §3.2 + §8.3a. Given one harbor run-dir, it emits JSON carrying:
per-stratum (typically per-dataset) pass@1 with Wilson 95% CI
(confidence level via `--alpha`); overall stratified pass@1 per the
adapter's stratum tagging; per-stratum trial counts with
errored-vs-completed distinction; when invoked with
`--against-constant <name=value>`, a "matches" / "outside-CI" line
per stratum. `--format markdown` produces a human-readable
equivalent.

This is the operational shape goal 1's analyze step uses to answer
"did we reproduce" via `rk score <run-dir> --against-constant
stratified_pass_at_1=0.577`. The counting-honesty discipline from
`dk` pkg2-v2-rk-score-counting is folded in (errored trials not
counted as fails; silent-drop guard flags missing trials). Paired
statistics defer to `rk diff` (Phase 4b).

## Acceptance criteria

**AC-1 — `rk score <run-dir>` reports per-stratum Wilson 95% CI and
overall stratified pass@1.**
Verified by: unit test against a fixture run-dir with three strata
asserts per-stratum CIs match hand-computed Wilson intervals at
α=0.05 and that the stratified mean matches the macro-average of
per-stratum pass@1. A second test with `--alpha 0.10` asserts the
CI half-width shrinks accordingly. Per plan AC-4a.2; folds `dk`
pkg2-v2-rk-score-counting AC-1.

**AC-2 — Fixture-driven Wilson CI correctness.**
Hand-computed Wilson interval values for synthetic single-run
pass@1 data match `rk score`'s output within tolerance.
Verified by: unit test compares output CIs against literature
reference values (e.g., for n=20, k=10, Wilson 95% CI = [0.299,
0.701]). Per plan AC-4a.3.

**AC-3 — Counting honesty: errored trials are not silently counted
as fails.**
The JSON output carries per-stratum `n_completed`, `n_errored`,
`n_total`. The score denominator is `n_completed`.
Verified by: unit test against a fixture trial set containing one
completed-success, one completed-failure, and one errored trial
(non-zero exit, no verifier output); asserts the JSON carries the
three counts and that the score denominator equals `n_completed`
not `n_total`. A second test with all-errored trials asserts
`score` is null and an `error_reason` field names the dominant
exception class. Per plan AC-4a.2; folds `dk`
pkg2-v2-rk-score-counting AC-2.

**AC-4 — `--against-constant <name=value>` emits inside-CI /
outside-CI line per stratum.**
Verified by: unit test with a fixture run-dir whose bookreview
stratum has a Wilson CI of [0.50, 0.65] asserts that
`--against-constant paper=0.577` reports inside-CI for that
stratum and `--against-constant paper=0.70` reports outside-CI.
The line includes the stratum label, the constant value, the CI,
and the verdict. Per plan AC-4a.3 + AC-4a.6.

**AC-5 — Paper-reproduction readout shape works on a real run-dir.**
`rk score <real-run-dir>
--against-constant stratified_pass_at_1=0.577` against a Phase 4a
harbor-DAB smoke run-dir returns "inside-CI" or "outside-CI" with
the Wilson CI bounds on the run's stratified pass@1.
Verified by: integration test runs the command against the AC-4a.13
smoke run-dir from `phase3-spacedock-solver-v2` + harbor-DAB and
asserts the output shape is consistent with the unit-test-verified
JSON schema. Per plan AC-4a.6.

**AC-6 — Adapter stratum tagging is honored without hard-coding.**
A DAB-tagged run-dir's strata are dataset slugs; an ade-bench-tagged
run-dir's strata are ade-bench's tag scheme. The stratified mean
reducer is benchmark-agnostic.
Verified by: separate unit tests against DAB + ade-bench fixtures
assert correct stratum extraction. Per plan AC-4a.2 + D7 (AC-2.8).

**AC-7 — `--format markdown` produces human-readable equivalent.**
Verified by: unit test asserts the markdown output carries one row
per stratum with `(stratum, n_completed, n_errored, pass@1, CI,
[verdict])` and a final stratified-mean row. Per plan AC-4a.2.

**AC-8 — JSON output stable under spec §3.3's semver promise.**
Verified by: snapshot test pins the output JSON schema; CI fails
on key rename or removal within the major version. Per spec §3.3.

**AC-9 — `uv run pytest` exits 0.**

## Test plan

- **Unit tests:** Wilson CI math at α=0.05 and α=0.10;
  stratified-mean reducer against fixture strata; errored-vs-completed
  counting (all-completed + all-errored + mixed);
  `--against-constant` inside-CI / outside-CI verdicts; adapter
  stratum-tag passthrough (DAB + ade-bench fixtures); markdown
  formatting; JSON-key snapshot.
- **Integration test:** end-to-end `rk score <fixture-run-dir>` for
  one DAB-tagged run; assert exit 0 and that the rendered output
  matches the unit-test-verified shape. `rk score
  <ac-4a.13-smoke-run-dir> --against-constant
  stratified_pass_at_1=0.577` returns the expected verdict.
- **Acceptance command:** `uv run rk score <fixture-run-dir>
  --against-constant paper=0.577 --alpha 0.05` exits 0 and emits
  the expected JSON.

## Out of scope

- Paired-comparison statistics (per-query exact-McNemar,
  Holm-Bonferroni family-wise correction, paired bootstrap CI).
  Spec §8.3 names these as `rk diff`'s responsibility; ships in
  Phase 4b per `phase4b-rk-diff-paired-stats`.
- TOST equivalence testing. Per the v2 design call: advanced stats
  in code is overkill; analyze-stage agents interpret.
- Per-trial cost/latency accounting. Spec §3.2 names `rk runs cost`
  as the cost-summary surface.

## Depends on

- `phase3-spacedock-solver-v2` (sealed-state contract — `rk score`
  reads the run-dir's `summary.json` whose shape the v2 agent
  produces)
- `dk` pkg2-v2-rk-score-counting (counting-honesty integration —
  the spec §9.2 counting-honesty discipline lands here in `rk
  score`'s implementation)
