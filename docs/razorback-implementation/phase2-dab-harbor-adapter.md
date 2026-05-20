---
id: 51f3z613j7xns0r38nma537r
title: Phase 2 — DAB harbor adapter (sibling package)
status: validation
source: plan Phase 2 + spec §2 + §8.4 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T06:23:05Z
completed:
verdict:
score: 0.85
worktree: .worktrees/spacedock-ensign-phase2-dab-harbor-adapter
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

**AC-9 — Dataset hydration semantics named and honored.**
The DAB harbor adapter has an explicit answer for how the 12 DAB
datasets reach the per-task container at run time. v1's pattern
was a manual user prereq (`git lfs pull` in
`dataagentbench/data/` per `dataagentbench/benchmark/setup.sh:84`).
v2's adapter chooses between (a) auto-hydration triggered by the
adapter on first use, (b) enforced prereq with a clean
missing-dataset error message at adapter-install time, or (c) a
hybrid (cache check + lazy pull). The plan stage names the
choice; the implementation honors it; validation confirms by
deleting the cached dataset and observing the chosen behavior
(auto-pull, clean error, or hybrid).
Verified by: a fresh checkout (`git clone` + no `git lfs pull`)
followed by `uv run rk run examples/specs/bookreview-claude.frozen.yaml`
either (a) succeeds with adapter-triggered hydration, (b) fails
with the documented missing-dataset error message naming the fix,
or (c) caches per the hybrid policy. The validator runs whichever
of (a)/(b)/(c) the plan committed to.

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

## Stage Report: plan

- DONE: Plan covers all 9 ACs (including AC-9 dataset hydration semantics) with a clear path/file structure for the new sibling package packages/razorback-plugin-dab/, pyproject.toml shape, module layout, harbor adapter discovery via import_path.
  Plan at `docs/razorback-implementation/plans/phase2-dab-harbor-adapter.md` carries an AC-task map (9 rows), a `File structure` block laying out `packages/razorback-plugin-dab/` (pyproject.toml, src layout, tests), and an `Architecture` paragraph that names harbor's adapter-dispatch contract (filesystem task-tree consumed via `JobConfig.tasks[].path`, NOT `AgentConfig.import_path`) per the AC-0.2 probe at `docs/superpowers/plans/2026-05-19-harbor-entry-point-probe.md`. The `import_path` mechanism is still load-bearing for `SpacedockSolverAgent` in Phase 3; Phase 2's plugin does not register a harbor agent or environment via that mechanism.
- DONE: AC-9 hydration decision is made explicitly in the plan, auto-hydrate vs enforced prereq vs hybrid. Plan names the choice and its trade-offs; validation will confirm the chosen behavior works under the documented condition (missing-dataset scenario).
  Plan §`AC-9 hydration decision` selects **option (b) enforced prereq with a clean missing-dataset error message** with a 3-row trade-offs table. Task 6 implements the LFS-pointer check; Task 13 is the validator that deletes the cached dataset, observes the exact stderr message + exit-code 2, hydrates, and re-runs.
- DONE: Mechanism validation discipline, a per-task live-DB compose stack runs end-to-end against bookreview (smallest dataset) BEFORE the comparison runs across all 12 datasets. The expected-shift-band pre-registration (AC-6) is part of the plan, not a post-hoc commitment.
  `Riskiest contract first` section names two integration-level gates: Task 1 (plugin discoverability via harbor's filesystem task-tree contract) and Task 7 (bookreview live-DB compose end-to-end before porting the other 11 datasets). Task 12 commits the per-dataset expected-shift table to `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md` in a commit that precedes the Task 15 run-dir commit; the TDD checkpoint table makes the ordering an explicit acceptance check.

### Summary

Wrote a 15-task implementation plan covering all 9 ACs at
`docs/razorback-implementation/plans/phase2-dab-harbor-adapter.md`.
The riskiest contracts (harbor adapter consumption shape; live-DB
compose-stack reachability on bookreview) are gated by Tasks 1 and
7, ahead of the 12-dataset port. AC-9 is resolved by option (b)
enforced-prereq with a documented missing-dataset error; rationale
is recorded in the plan body and the validator is Task 13. AC-6's
pre-registration ordering is enforced by commit ordering (Task 12
precedes Task 15) so it cannot be retrofitted.
