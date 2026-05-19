---
id: 9ekr46rwhh2hs1zsemvgzqv8
title: M6 — Constraints, registry, baselines, runs diff
status: backlog
source: design §8
started:
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
