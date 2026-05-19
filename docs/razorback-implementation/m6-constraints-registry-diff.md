---
id: 9ekr46rwhh2hs1zsemvgzqv8
title: M6 — Constraints, registry, baselines, runs diff
status: plan
source: design §8
started: 2026-05-19T08:51:27Z
completed:
verdict:
score: 0.6
worktree:
issue:
pr:
mod-block:
---

## Problem

The analysis subcommand surface: `rk constraints check`, `rk
baseline promote`, `rk baseline verify`, `rk registry {list,
resolve, add, remove}`, and `rk runs diff` with the paired
statistics from §6.5. This is the milestone that lets workflow
markdown reason about runs (compare to baseline, promote a
verdict, register a baseline). See §3.2 and §6.5 (the diff math).

## Acceptance criteria

**AC-1 — `rk runs diff` emits per-arm Wilson 95% CI on pass@1,
per-query exact-McNemar p, paired bootstrap CI on the
stratified delta, and a power-at-fixed-N line.**
Verified by: a unit test feeds two fixture run-dirs (one
baseline, one hypothesis) with hand-computed expected values
and asserts each statistic in the JSON output matches the
expected value (within numerical tolerance for the bootstrap).
The cites for the math are §6.5.

**AC-2 — `--alpha` sets the confidence level; `--bootstrap-
iters` sets B (default 10000).**
Verified by: unit tests assert both flags flow through to the
statistics module.

**AC-3 — `runs diff` refuses (`AssertionError` or typed error)
when only one run has `agent.seed.default` set.**
Verified by: a unit test feeds a baseline with no seed and a
hypothesis with `seed.default: 42`; the command exits non-zero
with the §6.5 refusal text.

**AC-4 — `rk constraints check` enforces pinned fields and
mutation-surface coverage from a constraints file.**
Verified by: a unit test feeds a constraints file with a pinned
`model_resolved_version` and a spec whose value differs; the
command exits with `ConstraintViolation` (exit code 12).

**AC-5 — `rk baseline promote` copies the run's frozen spec,
summary, per-dataset scores, and provenance into a baseline
directory and verifies constraints at promotion.**
Verified by: an integration test promotes a finished run-dir
and asserts the target baseline directory contains all four
artifacts, and that a subsequent `rk baseline verify` against
the same constraints exits 0.

**AC-6 — `rk registry resolve` resolves a `@name` to the
registered path.**
Verified by: a unit test registers `@codex-direct-baseline →
/some/path` via `rk registry add` then asserts `rk registry
resolve baseline @codex-direct-baseline` prints that path.

**AC-7 — Power-at-fixed-N line names a minimum detectable
effect at α and 80% power.**
Verified by: a unit test feeds a known fixture and asserts the
MDE matches the hand-computed value for the given trials ×
queries.

## Test plan

- **Unit tests:** Wilson CI, exact-McNemar, paired bootstrap,
  power calculation; constraints check pinning + mutation-
  surface coverage; baseline promote + verify roundtrip;
  registry add/resolve/remove.
- **Integration test:** end-to-end propose → smoke → analyze
  → promote cycle against bookreview (one dataset is enough for
  the integration shape; the math tests live in unit tests).
- **Acceptance command:** `uv run pytest src/razorback/diff/`
  plus a small integration script that promotes a finished
  bookreview run and verifies the resulting baseline.

## Out of scope

- The run-workflow integration — §M7.
- ade-bench or other harbor-shipped benchmarks — §M7.
- Markdown rendering for `--format markdown` — design lists it;
  the JSON path is the canonical output and markdown is a thin
  pretty-printer that can ship in a follow-up.

## Stage Report: plan

- DONE: Plan steps map 1:1 to the 7 ACs in the M6 entity body, each with the §-cite that governs it (§3.2 subcommand surface: constraints check, baseline promote/verify, runs diff, registry; §6.5 paired statistics: per-arm Wilson CI, exact-McNemar, paired bootstrap, power-at-fixed-N; §3.2 exit code 12 = ConstraintViolation, exit code 20 = SeedMismatchError for halt-resume diff refusal).
  AC↔task map in `plans/m6-constraints-registry-diff.md` covers all 7 ACs with §-cites; Task 8 lands ConstraintViolation (exit 12), Task 6 lands SeedMismatchError (exit 20).
- DONE: The riskiest contract for M6 — that the paired-bootstrap CI on the stratified delta produces numerically-stable output for the DAB N=5 case where exact-McNemar p clusters near 1.0 — is plan Task 1 as a unit test against hand-computed expected values, BEFORE wiring runs diff CLI surface.
  Plan Task 1 lands `paired_bootstrap_ci` against a hand-authored 2×2×5 fixture with fixed numpy seed (B=1000); Task 7 (CLI) comes after Tasks 1-6 lock the math + pairing.
- DONE: The plan extends M2/M5's aggregator + summary.json shape (per-query pass@1, per-dataset means, stratified macro-average) for the diff's paired pairing logic (by trial_name when JobConfig is deterministic, per §6.5). Cite which M5 plan tasks produce the inputs M6 reads.
  Task 2 adds the additive `per_trial_outcomes.json` sidecar to `aggregate.py` (summary.json contract unchanged); M5 reuse table names M2 Task 2 (`_build_summary`), M5 Task 6 (`rk spec freeze` for AC-3 input), M5 Task 11 (`examples/specs/dab-dev-claude.yaml`), M2 Task 7 (translator `trial_name_map`). Plan names a §6.5-aligned divergence: pairing by `(dataset, query_id, trial_index)` instead of literal `trial_name` because harbor's `trial_name` is `<task_name>__<uuid7>` and uuid7 differs across runs.

### Summary

Plan landed at `docs/razorback-implementation/plans/m6-constraints-registry-diff.md` (commit 5be2dc6). 12 tasks, math-first ordering: Task 1 locks the paired-bootstrap CI against a hand-authored fixture before any CLI work; Tasks 2-6 land the sidecar + pairing + other three stats + composer + seed-refusal; Task 7 ships `rk runs diff`; Tasks 8-10 ship constraints / baseline / registry; Task 11 is acceptance; Task 12 cross-links the plan from the entity body. Notable divergence calls (named in the plan): pairing key is `(dataset, query_id, trial_index)` because harbor's `trial_name` is uuid7-suffixed and unstable across runs; exact-McNemar uses `scipy.stats.binomtest` (stable API across scipy 1.x) instead of `scipy.stats.contingency.mcnemar`; power-MDE uses the closed-form normal-approximation with N = trials × queries, reported as a conservative upper bound alongside the bootstrap CI.

