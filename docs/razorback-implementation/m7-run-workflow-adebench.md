---
id: 12pw03062wxqmjxh17qm51rp
title: M7 — Run-workflow integration + ade-bench (first ade-bench result)
status: validation
source: design §8
started: 2026-05-19T09:06:49Z
completed:
verdict:
score: 0.9
worktree: .worktrees/spacedock-ensign-m7-run-workflow-adebench
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

## Stage Report: plan

- DONE: Plan steps map 1:1 to the 6 ACs in the M7 entity body, each with the §-cite that governs it (§4 stage usage / §2.1 architecture for run-workflow; §6.5 per_trial_state_reset for ade-bench's compose-services declaration; §9.2 inherited-contamination surface; §3.2 cross-benchmark diff refusal).
  Plan lives at `docs/razorback-implementation/plans/m7-run-workflow-adebench.md`; the "AC ↔ task map" table cites §2.1 + §4 (AC-1); §4 + §2.1 (AC-2); §2.1 + §M7 (AC-3); §6.5 (AC-4); §9.2 (AC-5); §3.2 row 12 + §6.5 (AC-6). Each AC names the exact Task(s) implementing it (Tasks 1–11).
- DONE: The riskiest contract — that ade-bench's bundled harbor task manifests actually run via `rk run` with the current spec → JobConfig translator — is plan Task 1 as a single-trial smoke against one ade-bench task, BEFORE the run-workflow integration scaffolds.
  Task 1 lands the `AdeBenchBenchmarkBlock` schema, the translator's `_build_ade_bench` branch, and a hand-authored harbor-format fixture (`tests/fixtures/ade_bench/tasks/adebench-fixture-001/`) with explicit STOP-and-escalate language if ade-bench's harbor shape diverges in a load-bearing way.
- DONE: The plan extends M5 + M6's outputs.
  M5 Task 6 (`rk spec freeze`) + Task 11 (`examples/specs/dab-dev-claude.yaml`) are reused by `examples/workflows/dab-claude/stages.md` (M7 Task 10); M5's `summary_version: 1` field carries to ade-bench with a strictly smaller shape (Task 6). M6 Task 7 (`rk runs diff`) gains the cross-benchmark refusal pre-check (M7 Task 7); M6 Task 9 (`rk baseline promote`) is invoked by the conclude stage (M7 Task 10) and the AC-2 acceptance (M7 Task 11); M6 Task 10 (`rk registry resolve`) is invoked by the analyze stage (M7 Task 10).
- DONE: Plan written via superpowers:writing-plans.
  Plan header + bite-sized task structure follows the writing-plans skill format (per-task Steps, exact file paths, complete code in every step, exact commands with expected output, frequent commits, TDD-first ordering). The plan-document self-review checklist at the bottom of the plan confirms spec coverage, placeholder scan, and type consistency.
- DONE: Named divergences instead of guessing the ade-bench shape.
  Plan names five divergence calls verbatim: (1) §6.5 "postgres" example is illustrative, actual ade-bench compose uses snowflake/duckdb; (2) M7 ships a hand-authored harbor-format fixture for AC-3 wire-up, real harbor-datasets clone is post-M7; (3) only single-shot workflow ships in M7, halt-resume is post-M7; (4) M6's `(dataset, query_id, trial_index)` pairing is irrelevant to AC-6's pre-pairing refusal; (5) `rk validate` is brand-new in M7 (M1–M6 referenced but did not land it). Each call cites the §-anchor it is aligned with.

### Summary

The M7 plan lands a new benchmark adapter (`razorback.benchmarks.ade_bench` parallel to `dab`), a new `rk validate` CLI command (the §6.5 `per_trial_state_reset` + §9.2 `tools_allowed` warning surfaces), a cross-benchmark refusal in `rk runs diff` (via a `benchmark_kind` field added to `manifest.json`), and a `razorback.runtime.reconcile_run_workflow` driver that the spacedock run-workflow's `reconciling` stage invokes to dispatch make-up `rk run` calls. Two example deliverables ship under `examples/`: the spec `examples/specs/ade-bench-claude.yaml` for the AC-3 first-ade-bench-result acceptance, and the workflow markdown bundle under `examples/workflows/dab-claude/` for the AC-2 end-to-end DAB lifecycle. The riskiest contract (ade-bench harbor tasks actually running through `rk run`) is Task 1 with an explicit STOP-and-escalate clause if the on-disk shape requires invention rather than adaptation.
