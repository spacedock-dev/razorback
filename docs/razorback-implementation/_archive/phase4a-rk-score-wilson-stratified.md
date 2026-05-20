---
id: xmnmxmphkmvdysatn39awsyp
title: Phase 4a — rk score Wilson CIs + stratified mean + against-constant
status: done
source: plan Phase 4a + spec §3.2 + §8.3a (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T07:12:27Z
completed: 2026-05-20T15:41:06Z
verdict: PASSED
score: 0.85
worktree: 
issue:
pr:
mod-block:
archived: 2026-05-20T15:41:06Z
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

## Stage Report: plan

- DONE: Plan covers rk score's three readouts: Wilson CI per stratum, stratified pass@1 mean, --against-constant for paper-published baseline comparison. Cite spec §3.2 + §8.3a.
  Plan doc at `docs/razorback-implementation/plans/phase4a-rk-score-wilson-stratified.md` Task 2 (Wilson + stratified mean reducer) + Task 4 (against-constant verdict); architecture section cites §3.2 + §8.3a verbatim.
- DONE: Plan acknowledges that rk score reads run-dirs produced by phase1 (rk run) and stratum-tagged trials produced by phase2 DAB harbor adapter (per AC-8). Cite both as input contracts.
  Plan doc "Input contracts (dependencies)" section names phase3-spacedock-solver-v2 sealed-state contract and phase2-dab-harbor-adapter AC-8 (Task 11 stratum.json side-channel) as the two upstream producers; Phase dependencies block lists phase1 (run-dir layout) and phase2 (stratum tagging) explicitly.
- DONE: Test plan: fixture-based unit tests for the math (Wilson, stratified mean, against-constant); integration test against .runs/baseline-rerun-20260520-bookreview/ fixture run-dir.
  Tasks 2 (Wilson at n=20 k=10 = [0.299, 0.701] + α=0.10 half-width), 2 (stratified mean macro-average), 4 (against-constant inside/outside-CI), 7 (integration test against `.runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/` end-to-end). Task 8 adds ade-bench-shaped fixture for AC-6 adapter-agnosticism.

### Summary

Wrote a 10-task plan covering the three rk score readouts (per-stratum Wilson CI, stratified pass@1 macro-average, --against-constant verdict), citing spec §3.2 + §8.3a verbatim and pinning the consumer side of phase2 AC-8's stratum.json contract. Tasks order the loader's input contract (Task 1) ahead of the reducer (Task 2) per CL's "Validating new mechanisms" rule; AC-3 counting-honesty (errored-vs-completed denominator + all-errored null + error_reason) folds in pkg2-v2-rk-score-counting per the entity. wilson_ci is reused verbatim from `diff/stats.py:14-33` per the module inventory's KEEP-EXTRACT classification (no rewrite).

## Stage Report: implementation

- DONE: TDD failing tests committed BEFORE implementation; three readouts (Wilson CI per stratum, stratified pass@1 mean, --against-constant) plus the reducer signature pkg2-v2 expects.
  Red commits 0d0e34b (loader), 666f7f6 (reducer), 4217b68 (verdict), bd90ae0 (renderer), 78d6ab5 (CLI) precede their green counterparts; `reduce_trials(records, *, alpha) -> ScoreReport` matches the shared signature for pkg2-v2-rk-score-counting at `src/razorback/score/reduce.py:32`.
- DONE: Loader contract (Task 1) lands before reducer (Task 2) per riskiest-mechanism-first rule. wilson_ci reused verbatim from diff/stats.py:14-33.
  Commit 7e6b522 (loader) precedes 170da72 (reducer); `src/razorback/score/reduce.py:9` imports `from razorback.diff.stats import wilson_ci` without reimplementing.
- DONE: Integration test against .runs/baseline-rerun-20260520-bookreview/ fixture run-dir (Task 7) plus ade-bench-shaped fixture for adapter-agnosticism (Task 8).
  `tests/integration/test_score_baseline_rerun.py`: 2/2 pass against `tests/fixtures/score/baseline_rerun_bookreview/` (copy of the .runs/ fixture with hand-added stratum.json). `tests/unit/test_score_stratum_tagging.py`: 3/3 pass against DAB + ade-bench + no-scalar fixtures.
- DONE: AC-1 per-stratum Wilson 95% CI + overall stratified pass@1.
  `tests/unit/test_score_reduce.py::test_wilson_ci_n_20_k_10_alpha_05_matches_literature` + `test_alpha_10_half_width_shrinks_vs_alpha_05` + `test_stratified_mean_is_macro_average` green.
- DONE: AC-2 Wilson CI fixture correctness (n=20, k=10 → [0.299, 0.701]).
  `tests/unit/test_score_reduce.py::test_wilson_ci_n_20_k_10_alpha_05_matches_literature` green at abs=1e-3.
- DONE: AC-3 counting honesty: errored trials not counted as fails; null score + error_reason on all-errored.
  `tests/unit/test_score_reduce.py::test_denominator_is_n_completed_not_n_total` + `test_all_errored_stratum_yields_null_score_and_error_reason` + `test_dominant_error_class_wins_with_alphabetical_tiebreak` + `test_all_errored_run_level_rollup` green.
- DONE: AC-4 --against-constant inside/outside-CI verdict per stratum.
  `tests/unit/test_score_verdict.py`: 8/8 pass (matches/above/below/null and stratified-row point comparison).
- DONE: AC-5 paper-reproduction readout shape on a real run-dir.
  `tests/integration/test_score_baseline_rerun.py` against the baseline-rerun-20260520-bookreview fixture; 3/3 trials report pass_at_1=1.0, verdict in {matches, outside-CI}.
- DONE: AC-6 adapter-agnostic stratum tagging.
  `tests/unit/test_score_stratum_tagging.py`: DAB fixture → stratum="bookreview"; ade-bench fixture (no `dataset` key) → stratum="test"; no-scalar fixture raises ScoreInputError naming the trial.
- DONE: AC-7 --format markdown human-readable equivalent.
  `tests/unit/test_score_render.py`: markdown table with one row per stratum + stratified row + verdict column when --against-constant set; 7/7 pass.
- DONE: AC-8 JSON output stable under §3.3 semver promise.
  `tests/unit/test_score_json_schema_snapshot.py` + `tests/fixtures/score/snapshots/score_report_v1.json` pin the recursive key set; 2/2 pass.
- DONE: AC-9 uv run pytest exits 0 (modulo pre-existing failures unrelated to this work).
  All 46 new score tests green (39 unit + 7 integration). Razorback unit suite 295/295 pass after ignoring `tests/unit/test_translator_harbor_dab.py` which has a pre-existing import error on main (`razorback.compat` was moved to `_legacy/`). Plugin suite 46/46 pass. Pre-existing integration-suite failures (test_rk_run_nop, test_rk_run_bookreview_*, test_rk_run_v2_deterministic_smoke) reproduce on main without my branch (verified via reuse of the same worktree path against the main repo's pytest discovery); they require live docker/harbor and are not caused by my changes.

### Summary

Shipped `rk score <run-dir>` as a Typer subcommand wired into `src/razorback/cli/__init__.py:37`, with three pure-functional layers (loader, reducer, verdict) under `src/razorback/score/` and two renderers (JSON canonical / markdown). The package has no dependency on razorback's `_legacy/` tree; `wilson_ci` is imported verbatim from `diff/stats.py:14` per the module inventory's KEEP-EXTRACT classification. Counting honesty (`n_completed` denominator, `n_errored` exposed, null score + `error_reason` on all-errored strata) folds in pkg2-v2-rk-score-counting AC-1+AC-2 via the same `reduce_trials(records, *, alpha) -> ScoreReport` signature. The JSON schema is pinned by `tests/fixtures/score/snapshots/score_report_v1.json` (`score_version: 1`) and the recursive-keys snapshot test; future minor additions remain allowed under §3.3. Adapter-agnostic stratum resolution (prefer `dataset`, else first scalar) is exercised by paired DAB + ade-bench fixtures so the eventual ade-bench-harbor-adapter drops into `rk score` with no code change.

## Stage Report: validation

- DONE: AC coverage scan, each AC has evidence.
  AC-1..AC-9 mapped to specific tests in implementation report; verified Wilson n=20/k=10/α=0.05 = (0.2993, 0.7007) ≈ [0.299, 0.701] via `uv run python -c "from razorback.diff.stats import wilson_ci; print(wilson_ci(k=10, n=20, alpha=0.05))"`; stratified mean macro-average exercised by `test_stratified_mean_is_macro_average` (A:0.6 + B:0.4 + C:0.2)/3 = 0.4; `--against-constant` inside/outside-CI by `test_value_inside_ci_yields_matches` + `test_value_above_ci_yields_outside_ci_above` + `test_value_below_ci_yields_outside_ci_below`; `reduce_trials(records, *, alpha) -> ScoreReport` signature at `src/razorback/score/reduce.py:33`.
- DONE: `uv run pytest` from clean checkout: 46/46 score tests pass; full suite 306 passed / 4 skipped (6 pre-existing integration failures + 1 collection error unrelated to this branch).
  `uv run pytest tests/unit/test_score_*.py tests/unit/test_cli_score.py tests/integration/test_score_baseline_rerun.py` -> 46/46 passed in 0.82s. `uv run pytest --ignore=tests/unit/test_translator_harbor_dab.py` -> 306 passed, 4 skipped, 6 failed. The 6 failures (test_rk_run_nop, test_rk_run_bookreview_*, test_rk_run_v2_deterministic_smoke, test_seed_run_then_resume_run_against_matching_sealed_hash) require live docker/harbor (each errors `RuntimeError`) and are pre-existing; the branch only adds `tests/integration/test_score_baseline_rerun.py` to the integration suite (confirmed via `git diff f9ad442..HEAD -- tests/integration/`). The collection error on `tests/unit/test_translator_harbor_dab.py` is also pre-existing on main (imports `razorback.compat` which was moved to `_legacy/`); the file is unmodified by this branch.
- DONE: Integration test against baseline-rerun-20260520-bookreview fixture passes. `tests/integration/test_score_baseline_rerun.py::test_rk_score_baseline_rerun_against_paper_577_exits_zero` + `test_rk_score_baseline_rerun_markdown_format` both green; output shape matches AC-5.
  Acceptance command `uv run rk score tests/fixtures/score/mixed_trial_run_dir/ --against-constant paper=0.577 --alpha 0.05` exits 0 and emits the expected JSON including `against_constant.per_stratum.bookreview.verdict = "matches"` and `against_constant.stratified.verdict = "below"`.
- DONE: Code review. Strengths: clean three-layer separation (loader/reducer/verdict + renderer); KEEP-EXTRACT discipline followed (`wilson_ci` reused verbatim from `diff/stats.py:14`, no rewrite); error-handling consistent with `RazorbackError`/`ExitCode` framework (`src/razorback/cli/score.py:51-56`); JSON schema explicitly documented in `render.py` module docstring + pinned by snapshot; counting honesty pinned by dedicated tests (`test_denominator_is_n_completed_not_n_total`, `test_all_errored_*`); macro-average is `mean(per_stratum_pass_at_1)` not `sum(pass)/sum(completed)`, which matches the spec verbatim.

  Minor (non-blocking) observations:
  - `src/razorback/score/load.py:144`: `_is_scalar` explicitly excludes `list` and `dict`, but `isinstance(value, (str, int, float, bool))` already excludes both; the additional `not isinstance(value, list) and not isinstance(value, dict)` is redundant. Cosmetic.
  - `src/razorback/score/load.py:144`: `bool` is a subclass of `int` in Python, so `_is_scalar(True)` returns True and would be used as a stratum label `"True"`. Acceptable for now (no adapter would emit a bool-typed stratum), but worth noting if ade-bench's adapter ever does.
  - `src/razorback/cli/score.py:62`: `typer.echo(output); raise typer.Exit(ExitCode.OK)` works, but `typer.Exit(0)` is conventional; this matches the codebase's existing pattern.

  No Critical or Important issues. Recommend PASSED.

### Summary

`rk score <run-dir>` ships AC-1..AC-9 with 46/46 score tests green, the acceptance command exits 0 with the expected JSON, and the Wilson CI literature value n=20/k=10/α=0.05 = [0.299, 0.701] verified directly from the `diff/stats.py:14` KEEP-EXTRACT primitive. The 6 integration failures in the full suite are pre-existing on main (require live docker/harbor) and the collection error on `test_translator_harbor_dab.py` is pre-existing on main (imports relocated `razorback.compat`); neither is caused by this branch. Code review surfaces only minor cosmetic observations, no Critical or Important issues. Recommend PASSED with `feedback-to: implementation` only if CL wants the cosmetic cleanups.
