---
id: 12pw03062wxqmjxh17qm51rp
title: M7 — Run-workflow integration + ade-bench (first ade-bench result)
status: backlog
source: design §8
started:
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
mod-block:
---

## Problem

The "first ade-bench result" milestone CL named explicitly. Two
threads converge: the spacedock run-workflow's `reconciling`
stage invokes `rk run` directly per §4 / §2.1, and ade-bench is
wired in as the first harbor-shipped benchmark whose isolation
audit lands (§9.2 names it as the second-supported adapter after
DAB). End-to-end hypothesis lifecycle runs against DAB and against
ade-bench, both through the same spec → `rk run` →
run-dir → analyze path.

## Acceptance criteria

**AC-1 — Run-workflow's `reconciling` stage invokes `rk run`
directly and reconciles the target trial count.**
Verified by: an integration test in `examples/workflows/` runs
a spacedock run-workflow entity through reconciling with a
target trial count higher than one `rk run` produces; the
workflow dispatches a make-up `rk run` and the resulting
entity tracks both run-dirs as a list.

**AC-2 — End-to-end hypothesis lifecycle against DAB runs
through the example workflow.**
Verified by: a smoke run of the example workflow under
`examples/workflows/dab-claude/` exercises propose → smoke →
full → analyze → conclude and produces a final entity with a
verdict and a promoted baseline.

**AC-3 — ade-bench adapter wires through `rk run` and produces
a per-trial reward.**
Verified by: `uv run rk run examples/specs/ade-bench-
claude.yaml` exits 0 against ade-bench's bundled environment
through harbor and the run-dir's `summary.json` contains a
score (non-zero is the expected case; the AC is "score field
is present and numeric", not "matches a baseline").

**AC-4 — ade-bench's `per_trial_state_reset` declaration
accurately reflects the adapter's reset capability.**
Verified by: `rk validate` against an ade-bench spec warns
when `compose_services: False` is declared and the spec
depends on a service that leaks state across trials (per §6.5
example: "postgres state leaks across trials"). The warning
text is asserted in a unit test.

**AC-5 — Razorback's `tools_allowed` declaration is documented
as not enforced for ade-bench's agent path (the §9.2
constraint).**
Verified by: a unit test asserts that the `validate` command
emits a warning when an ade-bench spec includes
`tools_allowed: [...]` — naming §9.2 in the warning text.

**AC-6 — A combined paired-diff between DAB and ade-bench is
NOT produced (they are different benchmarks; cross-benchmark
diff is nonsense).**
Verified by: a unit test feeds two run-dirs with different
`benchmark.kind` to `rk runs diff` and asserts the command
refuses with a typed error.

## Test plan

- **Unit tests:** run-workflow dispatch shape; ade-bench
  adapter wiring; `per_trial_state_reset` warning logic;
  cross-benchmark diff refusal.
- **Integration tests:** end-to-end DAB workflow run; one ade-
  bench `rk run` (cost-bounded).
- **Acceptance command:** `uv run rk run examples/specs/ade-
  bench-claude.yaml` plus a workflow-level smoke under
  `examples/workflows/dab-claude/`.

## Out of scope

- Any harbor benchmark beyond ade-bench — they ship after their
  own isolation audits per §9.2.
- MLflow logger or any external logger integration — §1.3
  excludes native MLflow in v1.
- Markdown rendering of `runs diff` — §M6 covered the JSON path;
  markdown is a follow-up.
- Remote executors (modal, daytona) — §1.3 excludes them.
