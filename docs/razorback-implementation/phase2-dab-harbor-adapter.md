---
id: 51f3z613j7xns0r38nma537r
title: Phase 2 — DAB harbor adapter (sibling package)
status: backlog
source: plan Phase 2 + spec §2 + §8.4 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started:
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
mod-block:
---

## Problem

Phase 2 ships the DAB harbor adapter as a parallel sibling package
at `packages/razorback-plugin-dab/` per D5's default. It is a
cross-repo work stream this plan blocks on at Phase 2's acceptance;
razorback core does not change. The adapter ports the 12 DAB
datasets into harbor task definitions, brings the live-DB compose
stack (the surviving content of PKG-3) into per-task environment
config, plumbs the workspace-README variants from PKG-9's surviving
content, and emits stratum-tagged trial output the v2 `rk diff` /
`rk score` consume per D7's AC-2.8 split.

Phase 2 is on the critical path for goal 1: the in-tree adapter
would need the same live-DB work the harbor adapter needs, and
doing it twice is rejected. Phase 2's live-DB run replaces the v1
dump-file baseline as the canonical anchor from Phase 3 onward
(AC-0.9 policy). Before the comparison runs, per-dataset
expected-shift bands are pre-registered so the v1→v2 score
shift is interpretable rather than "eyeball within X%".

## Acceptance criteria

**AC-1 — Walking skeleton holds on both paths.**
The in-tree DAB adapter (Phase 1 path) still produces a run-dir;
the new harbor-DAB adapter via `rk run` also produces a run-dir.
Verified by: `uv run rk run examples/specs/bookreview-claude.frozen.yaml`
exits 0 against both `benchmark: in_tree_dab` and `benchmark:
harbor_dab` spec variants. Per plan AC-2.1.

**AC-2 — DAB harbor adapter package builds and publishes locally.**
Verified by: `uv build` inside `packages/razorback-plugin-dab/`
produces a wheel; installing the wheel into razorback's venv makes
the DAB adapter discoverable to `harbor run` via the package's
exposed module path (per AC-0.2's import_path dispatch model).
Per plan AC-2.2.

**AC-3 — All 12 DAB datasets are ported as harbor task definitions.**
Each dataset has prepare, verify, per-task environment (including
the live-DB compose stack), and per-task hook config (DISALLOWED_TOOLS
+ workspace-README variants) defined.
Verified by: `harbor adapter list` (or local-discovery equivalent)
enumerates 12 DAB tasks; each task's manifest passes harbor's
adapter schema validation. Per plan AC-2.3.

**AC-4 — Live-DB mode confirmed by trajectory evidence.**
Verified by: a bookreview run via the new harbor-DAB adapter
produces `events.jsonl` containing a `psql --host dab-postgres`
invocation or `dab-postgres:5432` connection string. The grep
output is captured in the validation report. Per plan AC-2.4.

**AC-5 — Live-DB baseline committed and promoted to canonical
anchor.**
Verified by: a full DAB-claude run via the new harbor-DAB adapter
appends headline score + per-dataset breakdown to
`docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`.
The v1 dump-file baseline (AC-0.1(a)) is retired in the same
file to "pre-correction reference" status with the methodological
taint explanation. Per plan AC-2.5.

**AC-6 — Per-dataset expected-shift bands pre-registered before
the comparison runs.**
For each of the 12 DAB datasets, the expected direction + rough
magnitude of the live-DB-vs-dump-file score shift is committed to
the baseline doc BEFORE the comparison run begins.
Verified by: the baseline doc's pre-registration table is committed
in a commit that precedes the run-dir commit; the comparison's
acceptance criterion is "observed shifts fall within pre-registered
direction; magnitudes within 2x of prediction", not "scores match".
A surprise reversal flags a real bug. Per plan AC-2.6.

**AC-7 — In-tree adapter still functional.**
`src/razorback/benchmarks/dab/` is unchanged from Phase 1; an
in-tree-adapter smoke run produces the v1-baseline-comparable result.
Verified by: regression test runs the bookreview smoke via the
in-tree adapter and asserts the result matches Phase 1's recorded
output. Per plan AC-2.7.

**AC-8 — Cross-dataset aggregation contract honored.**
The adapter tags each trial with its stratum metadata (dataset
name; query difficulty bucket if applicable). Razorback's `rk
score` / `rk diff` consume the tags and own the stratified math.
Verified by: a fixture run-dir from the harbor-DAB adapter carries
per-trial `stratum: {dataset: bookreview, ...}` records in
`summary.json`; `rk score` against the same run-dir computes a
per-stratum readout. Per plan AC-2.8 (D7 split).

## Test plan

- **Adapter unit tests:** per-task prepare + verify scripts run
  green against the live-DB compose stack on at least bookreview
  + agnews (the smallest two datasets). Workspace-README variants
  parse against harbor's adapter schema.
- **Integration test:** bookreview run via the new harbor-DAB
  adapter end-to-end; assert live-DB evidence in `events.jsonl`
  per AC-4; assert per-trial stratum tagging in `summary.json`
  per AC-8.
- **Comparison test:** v1-vs-v2 per-dataset shift table matches
  the pre-registered bands per AC-6.
- **Acceptance command:** `uv run rk run
  examples/specs/dab-claude-harbor-adapter.frozen.yaml` against
  the full 12-dataset matrix at N=1 exits 0; the run-dir's
  headline score + per-dataset breakdown commit to the baseline
  doc.

## Out of scope

- harbor-native ade-bench adapter port. Separate work stream;
  Phase 6 sidelines `src/razorback/benchmarks/ade_bench/` to
  `_legacy/` when that port lands.
- HAL / τ-bench / LogicStar / terminal-bench-2 adapters. Each is
  a separate harbor adapter port (the archived PKG-4/5/6/7).
- Razorback core changes. Phase 2 is sibling-package work; razorback
  core unchanged.
- Paired statistics on the v1-vs-v2 comparison. Phase 2 reports the
  per-dataset shift table against pre-registered bands; paired
  bootstrap CI ships with `rk diff` (Phase 4b).

## Depends on

- `b5` spec-mitigation-resume-conflict (architectural §4.4 +
  §7.1 — the freeze-tree location informs the adapter's
  per-trial scratch zone)
- `ra` spec-corrections-from-phase0-probes (benchmark-adapter
  framing as offline task generators per AC-2; the spec must
  reflect this before the adapter's contract is finalized)
