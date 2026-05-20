---
id: dkefq66fjps62nfea530mkvn
title: PKG-2 v2 — rk score counting honesty
status: plan
source: spec §3.2 + §8.3a + §9.2 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T07:26:09Z
completed:
verdict:
score:
worktree:
issue:
pr:
mod-block:
---

## Problem

Aggregator-trustworthiness concerns from original PKG-2 fold into
v2's Phase 4a `rk score`. The shipping-first single-run statistical
readout (spec §3.2 + §8.3a) replaces the older diff-only aggregator,
and the counting-honesty risks from spec §9.2 set its correctness
bar: errored trials must not be silently double-counted as failed
passes, Wilson 95% CIs must be reported per stratum, the stratified
mean must aggregate honestly across the adapter's stratum tagging,
and the `--against-constant` paper-reproduction readout must render
the comparison without hand-waving. Paired statistics ship later
under `rk diff` (Phase 4b), so PKG-2 v2's scope is the single-run
read.

## Acceptance criteria

**AC-1 — `rk score` reports Wilson 95% CI per stratum and an overall
stratified mean, with confidence level configurable via `--alpha`.**
Verified by: unit test against a fixture run-dir with three strata
asserts the per-stratum CIs match a hand-computed Wilson interval at
α=0.05 and that the stratified mean matches the macro-average of
per-stratum pass@1. A second test with `--alpha 0.10` asserts the CI
half-width shrinks accordingly.

**AC-2 — Trial-state taxonomy is exposed in the output; errored
trials are not silently counted as failed passes.**
Verified by: unit test against a fixture trial set containing one
completed-success trial, one completed-failure trial, and one
errored trial (exit code non-zero with no verifier output) asserts
the JSON output carries per-stratum `n_completed`, `n_errored`,
`n_total`, and that the score denominator is `n_completed`. A
second test with all-errored trials asserts `score` is null and an
`error_reason` field names the dominant exception class. Cite spec
§3.2's exit-code table and §9.2 in the implementation comment.

**AC-3 — `rk score --against-constant <name=value>` emits an
inside-CI / outside-CI line per stratum.**
Verified by: unit test with a fixture run-dir whose `bookreview`
stratum has a Wilson CI of `[0.50, 0.65]` asserts that
`--against-constant paper=0.577` reports inside-CI for that stratum
and `--against-constant paper=0.70` reports outside-CI. The line
includes the stratum label, the constant value, the CI, and the
verdict.

**AC-4 — `rk score` honors the adapter's stratum tagging without
hard-coding benchmark-specific aggregation rules.**
Verified by: unit test against a DAB-tagged run-dir asserts strata
are dataset slugs; a separate unit test against an ade-bench-tagged
run-dir asserts strata are ade-bench's tag scheme. The stratified
mean reducer is benchmark-agnostic.

**AC-5 — JSON output stable under spec §3.3's semver promise.**
Verified by: snapshot test pins the output JSON schema; CI fails on
key rename or removal within the major version.

## Test plan

- **Unit tests:** Wilson CI math against hand-computed intervals at
  α=0.05 and α=0.10; stratified-mean reducer against fixture strata;
  errored-vs-completed counting (all-completed + all-errored + mixed);
  `--against-constant` inside-CI / outside-CI verdicts; adapter
  stratum-tag passthrough (DAB + ade-bench fixtures); JSON-key
  snapshot.
- **Integration test:** end-to-end `rk score <fixture-run-dir>` for
  one DAB-tagged run; assert exit 0 and that the rendered output
  matches the unit-test-verified shape.
- **Acceptance command:** `uv run rk score <fixture-run-dir>
  --against-constant paper=0.577 --alpha 0.05` exits 0 and emits the
  expected JSON.

## Out of scope

- Paired-comparison statistics (per-query exact-McNemar,
  Holm-Bonferroni family-wise correction, paired bootstrap CI). Spec
  §8.3 names these as `rk diff`'s responsibility, shipping in Phase
  4b when the autoresearch loop needs them.
- TOST equivalence testing. Per the v2 design call: advanced stats
  in code is overkill; the analyze-stage agent interprets `rk
  score`'s numbers.
- Markdown formatting. Spec §3.1 names JSON as the default;
  `--format markdown` is a polish flag, defer until consumer demand.
- Per-trial cost/latency accounting. Spec §3.2 names `rk runs cost`
  as the cost-summary surface; PKG-2 v2 stays in the score domain.
