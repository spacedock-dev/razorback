---
id: t1qhefvs93x72m9dbvzw11gn
title: Phase 6 — promote v2 canonical, sideline v1 to _legacy/
status: validation
source: plan Phase 6 (v2 reconciliation plan at docs/superpowers/plans/2026-05-19-razorback-reconciliation-plan.md)
started: 2026-05-23T03:52:58Z
completed:
verdict:
score: 0.7
worktree: .worktrees/spacedock-ensign-phase6-promote-v2-canonical
issue:
pr:
mod-block:
---

## Problem

Phase 6 promotes the v2 implementation to the canonical surface and
sidelines the v1 modules to `src/razorback/_legacy/` (the holding
tank created by AC-0.11). After Phase 4a's smoke succeeds and goals
1+2 ship from the `spacedock_solver_v2` discriminator, Phase 6
renames the discriminator to `spacedock_solver` and `git mv`s the
v1 modules into `_legacy/`. Each sideline is one commit per logical
group for bisect-clean history; the canonical surface progressively
shrinks while `_legacy/` remains importable for parity tests and
emergency rollback.

Phase 6 lands BEFORE Phase 5 in dispatch order (even though Phase 5
is numbered earlier) because Phase 5's templates reference the
canonical name. Phase 6's strongest check is AC-6.7's
same-canonical cross-history null diff: the rename + sideline must
not change v2 behavior.

## Acceptance criteria

**AC-1 — Walking skeleton holds.**
A DAB benchmark runs end-to-end via the canonical v2 path
(`agent.kind: spacedock_solver` routing to the v2 class) after the
rename + sideline.
Verified by: `uv run rk run examples/specs/bookreview-claude.frozen.yaml`
exits 0 and produces a non-degraded `summary.json`. Per plan AC-6.1.

**AC-2 — `spacedock_solver` routes to v2.**
`agent.kind: spacedock_solver` invokes the v2 runtime-adapter class.
`pyproject.toml`'s entry-point (or the `rk run` translation per D1)
is updated. The previous `spacedock_solver_v2` discriminator is
removed.
Verified by: unit test feeds a spec with `agent.kind:
spacedock_solver` and asserts the v2 class is constructed (via
instrumentation hook). A second test asserts `spacedock_solver_v2`
no longer routes (raises `SpecError` or equivalent). Per plan AC-6.2.

**AC-3 — V1 class sidelined as its own commit.**
The previous standalone `SpacedockSolverAgent` moves to
`src/razorback/_legacy/agents/spacedock_solver_legacy.py`.
Optionally accessible via `agent.kind: spacedock_solver_legacy` for
emergency rollback; carries a DeprecationWarning on instantiation.
Verified by: `git log --diff-filter=R --follow` shows the move in a
commit titled `sideline: v1 SpacedockSolverAgent → _legacy`; no
other edits in the same commit. Per plan AC-6.3.

**AC-4 — Non-survivor modules sidelined, one commit per logical
group, in this order:**
1. `src/razorback/agents/{claude_cli,codex_cli}.py` →
   `_legacy/agents/` (harbor's installed agents replace)
2. `src/razorback/benchmarks/dab/` → `_legacy/benchmarks/dab/`
   (harbor-DAB adapter replaces)
3. `src/razorback/benchmarks/ade_bench/` →
   `_legacy/benchmarks/ade_bench/` (future harbor-ade-bench adapter
   replaces)
4. `src/razorback/compat/` → `_legacy/compat/` (per-runtime adapter
   sub-modules replace)
5. `src/razorback/observers/` → `_legacy/observers/` (harbor's hook
   system replaces)
6. Remaining DROP/PORT-OUT modules from Phase 0 inventory not
   already sidelined → `_legacy/` (sweep)
Verified by: `git log --oneline` shows six commits in the listed
order; each commit is bisect-clean (tests pass between commits);
no commit combines a sideline with an unrelated edit; no commit
combines two unrelated sidelines. Per plan AC-6.4.

**AC-5 — Trimmed canonical surface.**
`src/razorback/{spec,agents,cli}` contain only v2-spec-named
artifacts. Removed pieces are in `_legacy/`. `agents/registry.py`
holds the spacedock_solver pydantic schema only.
Verified by: a manual inventory walk of the canonical surface
matches the v2-spec-named artifact list; the validation report
cites file paths. Per plan AC-6.5.

**AC-6 — Examples reflect v2.**
`examples/specs/` flips to v2-canonical agent kinds and the
harbor-DAB adapter reference.
Verified by: `grep -r "spacedock_solver_v2" examples/specs/`
returns no hits; `grep -r "agent.kind: spacedock_solver"
examples/specs/` returns the expected hits. Per plan AC-6.6.

**AC-7 — Same-canonical cross-history diff is statistically null.**
A full DAB benchmark via the post-Phase-6 canonical path produces
a `rk diff` against a pre-Phase-6 v2-class-on-harbor-adapter run
(Phase 3's smoke result) whose stratified-delta paired bootstrap
CI includes zero.
Verified by: integration test runs the diff; asserts CI contains
zero. **Only runs if `rk diff` is available** (Phase 4b); if Phase
4b has not yet shipped at this phase's run time, the gate falls
back to `rk score --against-constant <pre-promotion-headline>`
returning inside-CI per stratum. Per plan AC-6.7.

**AC-8 — razorback-implementation workflow dispatch can resume.**
The Phase 0 pause is lifted; new v2-shaped backlog entities can
flow through the dispatch path.
Verified by: a backlog entity (this one, perhaps) dispatches off
backlog through plan → implementation → validation → done after
Phase 6's PR merges. Per plan AC-6.8.

**AC-9 — `uv run pytest` exits 0.**
Per plan AC-6.9.

## Test plan

- **Bisect-clean verification:** `git bisect run uv run pytest`
  across the six sideline commits + the rename commit exits 0 at
  every step.
- **Routing tests:** post-rename `spacedock_solver` → v2; v1
  accessible only via `spacedock_solver_legacy`.
- **Inventory walk:** canonical surface matches the v2 module list.
- **Cross-history diff (AC-7):** `rk diff` or `rk score
  --against-constant` against Phase 3's pre-promotion baseline
  passes the null check.
- **Acceptance command:** `uv run rk run
  examples/specs/bookreview-claude.frozen.yaml` exits 0 with
  v2-canonical routing.

## Out of scope

- Deleting `_legacy/`. Phase 7 per `phase7-delete-legacy` (optional,
  one-release-cycle delay per D6 default).
- Workflow templates referencing the canonical name. Phase 5 per
  `phase5-workflow-templates` lands after this entity.
- harbor-native ade-bench adapter port. Sidelining
  `benchmarks/ade_bench/` per AC-4 commit 3 is mechanical; the
  port itself is a separate work stream.

## Depends on

- `phase4a-rk-audit-taint-port` (first-cut surface stable)
- `phase4a-rk-runs-cost` (first-cut surface stable)
- `phase4a-rk-run-budget-gate` (first-cut surface stable)
- `phase4a-rk-score-wilson-stratified` (first-cut surface stable;
  AC-7's fallback gate uses this)
- `phase3-spacedock-solver-v2` (the v2 class being promoted; AC-7's
  pre-promotion baseline is the Phase 3 smoke result)
- `phase2-dab-harbor-adapter` (provides the harbor-DAB adapter the
  canonical surface references)
- `phase1-rk-run-v2-wrapper` (provides the rk run base)

## Stage Report: plan

- DONE: DONE if the plan maps every Phase 6 AC (AC-1..AC-9) to concrete implementation and validation tasks, including the current canonical target `agent.kind: spacedock_solver` and retired `spacedock_solver_v2` route.
  Evidence: `docs/razorback-implementation/plans/phase6-promote-v2-canonical.md` has an AC-to-task map and Tasks 1-13 covering canonical `spacedock_solver` routing plus `spacedock_solver_v2` rejection.
- DONE: DONE if the plan identifies the live routing/code surfaces to touch and explicitly separates v1 solver retirement from later optional `_legacy/` deletion, ADE/DAB adapter retirement, and unrelated dirty work currently in the main worktree.
  Evidence: the plan's Current committed routing surface and Scope Boundaries sections name `schema.py`, `translate.py`, solver modules, registry, examples, DAB/ADE adapter retirement, Phase 7 `_legacy/` deletion, and dirty-work exclusion.
- DONE: DONE if the plan gives a diligent validation path: focused TDD tests first, grep/inventory checks, then the feasible smoke/score fallback for AC-1/AC-7/AC-9, with clear commit boundaries.
  Evidence: Risk-First Order, Tasks 1-13, Commit Boundary Summary, and Final Validation Checklist define focused tests, grep/inventory, AC-1 smoke fallback, AC-7 `rk diff`/`rk score` fallback, and `uv run pytest`.

### Summary

Wrote the standard separate Phase 6 plan at `docs/razorback-implementation/plans/phase6-promote-v2-canonical.md` because the entity has nine ACs and spans multiple subsystems. The plan is based on committed `HEAD` context, treats the current dirty main-worktree edits as contamination, and records the backlog -> plan gate as auto-approved rather than human-gated.

## Stage Report: implementation

- DONE: DONE if canonical `agent.kind: spacedock_solver` routes to the v2 runtime-adapter solver, `spacedock_solver_v2` no longer parses/routes, v1 solver code is sidelined or explicitly legacy-only, and focused route/schema/freeze/runtime tests pass.
  Evidence: commits `f99876a`, `e761ef5`, `f5c956b`, `ab708ea`, `9792294`; `uv run pytest tests/unit/test_spec_schema_spacedock_solver.py tests/unit/test_translate_spacedock_solver_import_path.py tests/unit/test_spacedock_solver_class.py tests/unit/test_spacedock_solver_lifecycle.py tests/unit/test_spacedock_solver_freeze_on_host.py tests/unit/test_runtime_adapters.py tests/unit/test_spec_freeze_cli_pkg8.py tests/unit/test_seal_v2_six_inputs.py tests/unit/test_tools_denied_parse.py tests/unit/test_spacedock_registry.py tests/unit/test_generate_matrix_specs.py tests/unit/test_generate_matrix_specs_per_variant_kind.py tests/unit/test_codex_benchmark_spec_generator.py tests/unit/test_claude_benchmark_spec_generator.py -q` -> 90 passed.
- DONE: DONE if active examples/generators use canonical `spacedock_solver`, stale registry/v1 tests are removed or rehomed, and grep/inventory checks show no active `spacedock_solver_v2`/`spacedock-solver` references outside legacy or historical docs.
  Evidence: commits `25f46ba`, `099c348`, `d9362cd`, `6403daf`; `rg -n "spacedock_solver_v2|spacedock-solver" src/razorback tests examples/specs examples/drivers packages` returns only `_legacy/` hits; `rg -n "kind: dab|kind: in_tree_dab" examples/specs examples/drivers tests/fixtures/specs` returns no hits.
- DONE: DONE if implementation follows the approved plan's commit boundaries as far as safely possible, documents any blocked AC-4 broad adapter sideline (DAB/ADE/standalone CLI/compat/observers) with evidence rather than forcing it, and commits a stage report with exact tests run.
  Evidence: commit order is `f99876a`, `e761ef5`, `f5c956b`, `ab708ea`, `25f46ba`, `099c348`, `9792294`, `d9362cd`, `6403daf`; broad AC-4 adapter sidelines were stopped per FO route update and blocker evidence below.
- SKIPPED: AC-4 standalone CLI agent sideline.
  Rationale: `src/razorback/agents/_runtime/claude.py` actively imports `razorback.agents.claude_cli.ClaudeCliAgent`, and `tests/unit/test_runtime_adapters.py` asserts the Claude runtime adapter uses it for cost/audit/tool policy.
- SKIPPED: AC-4 in-tree DAB and ADE-Bench adapter sidelines.
  Rationale: `src/razorback/translate.py` still imports `razorback.benchmarks.dab.prepare` and `razorback.benchmarks.ade_bench.*`; ADE/DAB task-view tests still exercise those modules, so moving them now would block active adapter work.
- SKIPPED: AC-4 compat and observer sidelines.
  Rationale: compat/observer refs remain in ignored legacy/drop tests and `_legacy/`; FO explicitly instructed to defer broad DAB/ADE/standalone-CLI/compat/observer sidelines for this implementation pass.
- SKIPPED: AC-1 live `rk run`, AC-7 statistical cross-history diff, and AC-9 full pytest completion.
  Rationale: live run/diff need DAB data/API/baseline availability and full pytest was stopped after FO route update; structural fallback already wrote `/tmp/bookreview-spacedock.phase6.frozen.yaml` with `agent.kind: spacedock_solver`, `benchmark.kind: harbor_dab`, solver hash, and sealed hash, and `uv run rk score tests/fixtures/score/baseline_rerun_bookreview --format json` returned 3/3 completed with `stratified_pass_at_1: 1.0`.
- FAILED: AC-8 workflow status check.
  Details: `python /home/exedev/.codex/skills/commission/bin/status --workflow-dir docs/razorback-implementation` fails before rendering because unrelated active entity `goal1-resume-t0-cost-projection.md` is missing required `id`.

### Summary

Promoted the v2 runtime-adapter solver to canonical `agent.kind: spacedock_solver`, moved the old v1 solver to `_legacy/agents/spacedock_solver_legacy.py` with a deprecation warning, updated active examples/generators, trimmed the active registry, and removed stale v1/transitional tests. The backlog -> plan and plan -> implementation gates were auto-approved by the first officer, not human-gated; broad AC-4 adapter sidelines are intentionally deferred with active-import evidence instead of forced in this pass.

## Stage Report: validation

- DONE: DONE if validation independently reruns focused route/schema/freeze/runtime tests and grep/inventory checks for canonical `spacedock_solver`, rejected `spacedock_solver_v2`, and legacy-only v1 solver references.
  Evidence: focused route/schema/freeze/runtime/generator suite returned `90 passed in 3.67s`; grep found `spacedock_solver_v2|spacedock-solver` only under `_legacy/`, no active example/generator `spacedock_solver_v2`, and no active `kind: dab|kind: in_tree_dab`.
- DONE: DONE if validation reviews the implementation commits and AC evidence with explicit PASS/FAIL/SKIPPED for AC-1..AC-9, especially the broad AC-4 deferrals, AC-8 workflow-status failure, AC-1 smoke fallback, AC-7 fallback, and AC-9 full-test status.
  Evidence: validation report `docs/razorback-implementation/validation/phase6-promote-v2-canonical.md` records AC-1 FAIL, AC-2 PASS, AC-3 PASS, AC-4 FAIL, AC-5 FAIL, AC-6 PASS, AC-7 SKIPPED/partial fallback, AC-8 FAIL, AC-9 FAIL; full pytest was `19 failed, 572 passed, 5 skipped`.
- DONE: DONE if validation writes `docs/razorback-implementation/validation/phase6-promote-v2-canonical.md`, appends a stage report to the entity, commits only validation artifacts, and gives a clear gate decision: APPROVE to done or REJECT back to implementation with concrete fixes.
  Evidence: validation artifacts are this entity body update plus the validation report; gate decision is REJECT back to implementation with required fixes for AC-1, AC-4, AC-8, and AC-9.

### Summary

Validation rejected the branch. The canonical `spacedock_solver` route itself is green in focused tests, but the exact AC-1 run target is missing, broad AC-4 sidelines were deferred, workflow status fails on an unrelated malformed active entity, and `uv run pytest` exits non-zero. The plan and implementation gates were first-officer auto-approved, not human-gated.
