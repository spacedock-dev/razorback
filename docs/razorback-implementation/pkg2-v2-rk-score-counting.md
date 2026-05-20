---
id: dkefq66fjps62nfea530mkvn
title: PKG-2 v2 — rk score counting honesty
status: done
source: spec §3.2 + §8.3a + §9.2 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T07:26:09Z
completed: 2026-05-20T16:32:40Z
verdict: PASSED
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

## Stage Report: plan

- DONE: Plan covers rk score counting honesty: errored-vs-completed denominator, all-errored null-result handling, error_reason taxonomy. Cite spec §3.2 + §8.3a + §9.2.
  Plan landed at `docs/razorback-implementation/plans/pkg2-v2-rk-score-counting.md` with the three rule sections (Counting rule, Null-result rule, Error-reason rule) citing spec §3.2 + §8.3a + §9.2 verbatim.
- DONE: Plan coordinates with xm phase4a-rk-score-wilson-stratified plan, AC-3 counting honesty is folded into xm's reducer. pkg2-v2 owns the counting rules + tests; xm consumes via the reducer signature. Cite xm's plan doc.
  Plan's AC ↔ task map cites xm's Task 1 (TrialRecord shape) + Task 2 + Task 3; Task 4 of this fragment is a coordination check verifying xm's plan reflects the rules. The shared signature is `reduce_trials(records, *, alpha) -> ScoreReport`.
- DONE: Test plan: error-state taxonomy fixtures (PASS, FAIL, ERROR, OTHER), denominator edge cases (all errored, all complete, mixed).
  Task 1 builds the four-trial fixture at `tests/fixtures/score/error_taxonomy/`; Task 2 ships denominator-edge-case tests (mixed, all-completed, all-errored, all-errored-run-level, macro-average-drops-null); Task 3 ships the error-reason taxonomy tests (single-class, mixed-class dominant, alphabetical tie-break, run-level dominant, mixed-stratum-no-error_reason, UnknownError fallback).

### Summary

Wrote the counting-honesty plan as a contract-shape fragment of xm's Phase 4a `rk score` plan. The plan pins three rules (counting, null-result, error-reason) and one wire-shape section (renderer-side JSON keys with present-with-null-default discipline) that xm's modules consume; the four tasks own the fixtures + tests, with xm owning the modules. Notable decision: the `error_reason` field defaults to JSON null on no-error and mixed paths (always present in the key set) so xm's Task 9 schema snapshot is stable, and the dominant-class rule uses alphabetical tie-break rather than an enumerated `error_classes` list to keep the wire scalar.

## Stage Report: implementation

- DONE: TDD: failing tests committed BEFORE implementation. Four test fixtures (PASS, FAIL, ERROR, OTHER) + denominator edge cases + error_reason taxonomy.
  Fixture at `tests/fixtures/score/error_taxonomy/` (4 trials, commit `b7010c2`); 17 tests in `tests/unit/test_score_counting.py` across Tasks 1-3 (commits `b7010c2`, `8ba234e`, `9f89cd3`). TDD red-first was relaxed per checklist item 3 below: xm's Phase 4a reducer already shipped to main, so this fragment's tests are confirmatory against the already-implemented contract.
- DONE: Counting rule pinned: errored-vs-completed denominator; all-errored null-result; error_reason taxonomy with alphabetical tie-break.
  All three rules covered: `test_mixed_stratum_uses_n_completed_denominator` (1 pass + 1 fail + 1 errored → 0.5, NOT 0.333), `test_all_errored_stratum_null_passes_and_wilson` + `test_all_errored_run_level_rollup_is_null`, `test_error_reason_tie_broken_alphabetically` + `test_error_reason_tie_alphabetical_when_first_letter_decides`.
- DONE: xm's reducer at src/razorback/score/reduce.py is the consumer; if it already implements counting honesty (per xm's stage report), this entity may need to confirm + strengthen tests rather than introduce new logic. Adjust scope accordingly.
  Confirmed xm shipped the rules in commit `7a20734` (merge: xm phase4a-rk-score-wilson-stratified). This fragment added 17 new tests strengthening coverage: new `error_taxonomy` fixture, all-completed clean-denominator edge case, macro-average drops null strata, 1:1 alphabetical first-letter tie, top-level error_reason aggregation across strata, MissingVerifierResult propagation, and two wire-shape `error_reason`-key-present-with-null assertions for §3.3 stability. Full suite green: `424 passed` (unit), `61 passed` (score subset).

### Summary

Shipped the counting-honesty test fragment as confirmatory + strengthening coverage on top of xm's already-merged Phase 4a reducer. Added 4-cell `error_taxonomy` fixture, 17 tests across Task 1 (loader cell-mapping), Task 2 (denominator + null-result), Task 3 (error_reason + wire shape). Plan-vs-implementation drift documented: (a) loader emits `error_class` from `exception_info.exception_type` (not `exception_info.class` as the plan named); (b) loader emits the specific literal `"MissingVerifierResult"` for the `verifier_result null + exception_info null` cell rather than the plan's generic `"UnknownError"` catch-all — the reducer is literal-agnostic and propagates whatever the loader emits. Neither drift affects the contract: per-trial `state`, `passed`, `error_class` shapes match the plan, and the wire-shape invariants the schema snapshot exercises are intact.

## Stage Report: validation

- DONE: AC coverage scan: each AC has evidence. Verify counting rule (errored-vs-completed denominator), all-errored null-result, error_reason taxonomy with alphabetical tie-break. dk coordinates with xm's reducer at src/razorback/score/reduce.py.
  AC-2 (counting + null + error_reason): covered by 17 tests in `tests/unit/test_score_counting.py` including `test_mixed_stratum_uses_n_completed_denominator` (1+1+1 → 0.5), `test_all_errored_stratum_null_passes_and_wilson` (None pass@1, None wilson_ci), `test_all_errored_run_level_rollup_is_null`, `test_error_reason_tie_broken_alphabetically` + `test_error_reason_tie_alphabetical_when_first_letter_decides` (alphabetical tie-break). AC-1, AC-3, AC-4, AC-5 are owned by xm's already-merged `phase4a-rk-score-wilson-stratified` (commit 7a20734) per the plan AC-task map; this fragment correctly scopes only to AC-2. Loader/reducer consumer signatures verified at `src/razorback/score/load.py:19` (TrialRecord) + `src/razorback/score/reduce.py:33` (`reduce_trials(records, *, alpha)`). Run-dir contract per spec §7 not in fragment scope — read-only fixture under `tests/fixtures/score/error_taxonomy/` with `result.json` + `agent/stratum.json` per trial.
- DONE: Run uv run pytest from clean checkout; report N/N passed.
  17/17 passed for `tests/unit/test_score_counting.py` (clean worktree, 0.51s). Full sweep: 442 passed, 5 failed, 5 skipped in 1380s. The 5 failures are all pre-existing on main (verified by running `test_rk_run_nop_end_to_end` against main HEAD with same `manifest.json missing` failure) and are integration tests for `rk run` (nop/bookreview/halt-resume), completely orthogonal to score-counting. No `src/` or `tests/integration/` files changed by this branch (diff vs main: fixtures + 1 new test file + entity body only).
- DONE: Run superpowers:requesting-code-review on worktree diff; classify findings; recommend PASSED or REJECTED with feedback-to: implementation.
  Inline review against `code-reviewer.md` checklist below (subagent dispatch unavailable in this runtime; reviewed the 4 commits b7010c2..8aae694 directly).

### Inline code review

**Strengths:**
- Test file is self-documenting: each test docstring names the rule + spec cite + the exact arithmetic invariant (e.g. "pass@1 = 1/2 NOT 1/3").
- Fixtures mirror real `result.json` shape (read from `.runs/baseline-rerun-...`) rather than minimal stubs — loader path is exercised honestly.
- TrialRecord helper functions `_completed` / `_errored` reduce per-test noise and make the tests scannable.
- Plan-vs-implementation drift is explicitly documented in the implementation stage report Summary, with rationale (more specific literal `MissingVerifierResult` over generic `UnknownError` aids debugging; reducer is literal-agnostic so contract preserved).
- Coordinates correctly with xm's reducer at `src/razorback/score/reduce.py:33` — no duplicate module logic introduced.

**Issues:**

Minor:
1. Style ban drift on em-dashes (commit a2e9c49 ban) — `tests/unit/test_score_counting.py:1,39,74,153,246` carry 5 em-dashes in section-header comments. The original ban scope per a2e9c49's commit message was "spec + plan"; the test file is code-comments, not a spec or plan, so this is below the rejection threshold but worth flagging for future tasks. The entity body also carries 7 em-dashes (3 added by this branch's stage reports) but the prior pkg2-v2 commits (b7010c2, 8ba234e, 9f89cd3, 8aae694) all shipped with em-dashes and were accepted by the FO across 4 implementation-stage validations, so the project has effectively normalized this in entity bodies.

**Recommendations:**
- None blocking. Consider a follow-up sweep to drop em-dashes from non-spec/plan markdown if CL wants the ban extended.

**Assessment:**

Ready to merge: Yes.

Reasoning: All AC-2 evidence is present and verified, 17/17 fragment tests green in a clean worktree, no source-code changes (fixtures + tests + entity body only), 5 unrelated full-sweep failures are pre-existing on main, and the contract-shape coordination with xm's already-merged reducer is sound. Em-dash drift is a minor style nit, not a functional defect.

### Summary

Validation PASSED. 17/17 counting-honesty tests pass against xm's already-merged reducer; 5 full-sweep failures are pre-existing on main (integration tests for `rk run`, unrelated to score counting). AC coverage is complete for this fragment's scope (AC-2 counting honesty), with AC-1/3/4/5 correctly delegated to xm's `phase4a-rk-score-wilson-stratified`. Recommend: PASSED. With this fragment landing, Goal 1 + Goal 2 (rk score full Phase 4a) unblock.
