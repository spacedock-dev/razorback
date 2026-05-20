---
id: gny26mygz099s6bfz22pp9s2
title: Phase 4b — rk diff (cluster bootstrap + McNemar + MDE)
status: backlog
source: plan Phase 4b + spec §3.2 + §8.3 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started:
completed:
verdict:
score: 0.65
worktree:
issue:
pr:
mod-block:
---

## Problem

Phase 4b ships `rk diff` — the paired hypothesis-testing surface for
two harbor run-dirs paired by `(task, query, trial_index)`. Output
JSON carries: per-arm per-query Wilson 95% CI on pass@1; per-query
exact-McNemar p with exact-binomial fallback for small discordant
counts AND family-wise-adjusted p-values via Holm-Bonferroni;
paired bootstrap CI on the stratified delta resampling at the
cluster level (default `query`); MDE at fixed N;
achieved-power-at-observed-effect. The command refuses on
seed-asymmetry.

**Phase 4b is explicitly deferred.** Goal 1 (paper reproduction)
uses `rk score --against-constant` against published constants —
a one-sided test. Goal 2 (ade-bench Haiku baseline) is an
establishing measurement, no paired comparison. Paired-comparison
machinery lands when the autoresearch loop's analyze stage needs
to make a "hypothesis X beats baseline" claim with paired-statistics
defensibility. This entity is filed for visibility; it is not on
the v2 first-cut critical path.

## Acceptance criteria

**AC-1 — Walking skeleton holds.**
All first-ship surfaces still work; `rk diff` ships additively
without changing them. Per plan AC-4b.1.

**AC-2 — `rk diff <run-a> <run-b>` produces spec §8.3 statistics.**
Output JSON carries: per-arm per-query Wilson 95% CI on pass@1;
per-query exact-McNemar p with exact-binomial fallback for small
discordant counts; Holm-Bonferroni family-wise-adjusted p-values;
paired bootstrap CI on the stratified delta resampling at the
cluster level (default `query`); MDE at fixed N;
achieved-power-at-observed-effect. Refuses on seed-asymmetry.
Verified by: integration test against two fixture run-dirs paired
by `(task, query, trial_index)` asserts each named statistic appears
in the output. Per plan AC-4b.2; spec §8.3.

**AC-3 — Fixture-driven correctness, cluster bootstrap critical.**
Hand-computed expected values match within tolerance. Cluster
bootstrap fixture: synthetic dataset where intra-query trials are
perfectly correlated shows the trial-level bootstrap CI as
anti-conservatively narrow versus the query-cluster bootstrap CI;
test asserts the latter is wider. Family-wise fixture: 12-dataset
synthetic with no real effect produces ~46% uncorrected family-wise
error; Holm-Bonferroni brings it to nominal α.
Verified by: unit tests assert both fixtures. Per plan AC-4b.3.

**AC-4 — Same-spec self-diff is statistically null.**
Two back-to-back runs of the same frozen spec produce paired
bootstrap CI including zero at N=5.
Verified by: integration test runs the deterministic micro-spec
twice and asserts the diff CI contains zero. Per plan AC-4b.4.

**AC-5 — Same-adapter cross-class diff is statistically null (if v1
class still exists at this phase's ship time).**
Confirms v2 agent class does not change benchmark semantics versus
v1. Lands as a regression gate, not as a feature.
Verified by: integration test runs the same adapter with v1 + v2
agent classes and asserts the diff CI contains zero. Skipped if v1
class has been deleted by Phase 7. Per plan AC-4b.5.

**AC-6 — `uv run pytest` exits 0.** Per plan AC-4b.6.

## Test plan

- **Unit tests:** Wilson CI per arm; exact-McNemar with
  exact-binomial fallback; Holm-Bonferroni family-wise adjustment;
  paired bootstrap with cluster-level resampling; MDE computation;
  achieved-power computation; seed-asymmetry refusal.
- **Integration tests:** same-spec self-diff null; cross-class
  same-adapter null (if v1 class extant).
- **Acceptance command:** `uv run rk diff <run-a> <run-b>` exits 0
  with the expected JSON shape against fixture run-dirs.

## Out of scope

- **Deferred until autoresearch consumer materializes.** The
  trigger for activation per plan Phase 4b's status note: when the
  autoresearch experiment workflow's analyze stage needs to make a
  "hypothesis X beats baseline" claim with paired-statistics
  defensibility. Until then, `rk score --against-constant` against
  the registered baseline run-dir (treating the baseline's headline
  as the constant) is the operational shape.
- TOST equivalence testing. Per v2 design call: not in code; the
  analyze-stage agent (or captain) interprets.
- Multi-arm diff (more than two run-dirs). Pairwise comparison is
  the first-ship shape; multi-arm extends later if a consumer
  surfaces.
- Cross-benchmark stratification. Per "Package H" deferred-review
  finding: lands when a second benchmark's `rk diff` consumer
  surfaces a stratification difference.

## Depends on

- `phase4a-rk-score-wilson-stratified` (Wilson CI math + stratified
  mean reducer extend into the per-arm reporting in `rk diff`)
- `phase3-spacedock-solver-v2` (sealed-state contract — `rk diff`
  refuses on seed-asymmetry, which requires the v2 agent's
  sealed_hash discipline)
