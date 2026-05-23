# Phase 6: Promote v2 Canonical Implementation Plan

> For implementation workers: use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to execute this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Promote the v2 solver route from the transitional `agent.kind: spacedock_solver_v2` to the canonical `agent.kind: spacedock_solver`, sideline the v1 solver and other non-survivor modules into `_legacy/`, and leave the post-Phase-6 canonical surface free of v1/discriminator leftovers. The implementation must be planned from clean `HEAD`; the local main worktree currently has unrelated dirty code, tests, and examples from aborted/direct attempts and other-agent ADE/Claude work.

**Gate note:** The backlog -> plan gate for this entity was auto-approved by the first officer under the captain's resumed auto-approval mode. Future gates should be recorded as auto-approved when applicable, not as human-blocking gates.

**Source of truth:**
- v2 spec: `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`, especially spec §3.2, §4, §4.5, §6.1, §6.2, §7, §8.1, §8.2, §8.3, §8.3a, §8.4.
- Reconciliation plan: `docs/superpowers/plans/2026-05-19-razorback-reconciliation-plan.md`, Phase 6 AC-6.1..AC-6.9 plus Phase 4b fallback note for `rk diff`.
- Module inventory: `docs/superpowers/plans/2026-05-19-razorback-inventory.md`, especially DROP/PORT-OUT rows for `agents/claude_cli.py`, `agents/registry.py`, `benchmarks/dab/`, `benchmarks/ade_bench/`, `compat/`, `observers/`, `run.py`, `runtime/`, and surviving v2 rows for `spec`, `cli`, `score`, `audit`, `runs`, `translate`, `agents/_runtime`, `agents/seal.py`, and `agents/auth.py`.
- Test inventory: `docs/superpowers/plans/2026-05-19-razorback-test-inventory.md`, used to decide re-author vs drop vs port-out tests.
- Existing Phase 3/4a/PKG-38 plans: v2 class and runtime adapter details remain valid; Phase 6 only promotes the route and sidelines leftovers.

**Current committed routing surface at `HEAD`:**
- `src/razorback/spec/schema.py` accepts v1 `SpacedockSolverAgentBlock.kind: "spacedock-solver"` and transitional v2 `SpacedockSolverV2AgentBlock.kind: "spacedock_solver_v2"`.
- `src/razorback/translate.py` has `SPACEDOCK_SOLVER_IMPORT_PATH = "razorback.agents.spacedock_solver:SpacedockSolverAgent"` and `SPACEDOCK_SOLVER_V2_IMPORT_PATH = "razorback.agents.spacedock_solver_v2:SpacedockSolverAgent"`.
- `src/razorback/agents/spacedock_solver.py` is the v1 standalone class; `src/razorback/agents/spacedock_solver_v2.py` is the v2 class.
- `src/razorback/agents/registry.py` is still a v1-style agent registry, despite the spec §4.5 import-path dispatch model.
- `examples/specs/` still includes transitional v2 examples and in-tree adapter examples; Phase 6 must flip examples to `agent.kind: spacedock_solver` plus `harbor_dab`.

## AC to Task Map

| AC | Governing spec cites | Implementation tasks | Validation tasks |
| --- | --- | --- | --- |
| AC-1 Walking skeleton holds through canonical v2 path | spec §3.2, §4, §6.2, §7, §8.1 | T1, T2, T5, T8 | V6 smoke: `uv run rk run examples/specs/bookreview-claude.frozen.yaml --runs-dir <tmp>` then inspect `summary.json`; if live spend/env unavailable, run V6 fallback command set and document exact blocker |
| AC-2 `spacedock_solver` routes to v2 and `spacedock_solver_v2` is removed | spec §4.5, §6.2, §8.1, §8.4 | T1, T2, T4 | V1 focused routing/schema tests, V4 grep inventory |
| AC-3 v1 class sidelined as its own commit | spec §4.5, inventory `agents/spacedock_solver.py` ADAPT-EXTRACT | T3 | V3 `git log --diff-filter=R --follow` and focused legacy warning test if warning route is kept |
| AC-4 non-survivor modules sidelined, one logical group per commit | spec §1.3, §3.2, §4.5, §6.1, §8.1; inventory DROP/PORT-OUT rows | T6, T7, T9, T10, T11, T12 | V3 commit-order checks, V4 grep/import inventory, focused tests after each move |
| AC-5 trimmed canonical surface | spec §1.3, §3.2, §4, §6.2, §8 | T2, T4, T6-T12 | V4 canonical surface inventory report |
| AC-6 examples reflect v2 | spec §6.1, §6.2, §8.1 | T5 | V2 example tests, V4 grep no transitional kind |
| AC-7 same-canonical cross-history diff is statistically null | spec §8.3, §8.3a; reconciliation Phase 4b fallback | T8, V7 | V7 `rk diff` if available, otherwise `rk score --against-constant <pre-promotion-headline>` fallback |
| AC-8 workflow dispatch can resume | workflow README plan/implementation/validation stages; spec §5 | T13 | V8 dry workflow-status check and post-merge resume note |
| AC-9 full tests pass | all above | all tasks | V9 `uv run pytest` |

## Scope Boundaries

- **v1 solver retirement:** Move the previous standalone v1 `SpacedockSolverAgent` to `src/razorback/_legacy/agents/spacedock_solver_legacy.py` in its own rename-only commit. Add `DeprecationWarning` and any optional `agent.kind: spacedock_solver_legacy` rollback route in a separate follow-up commit so the AC-3 rename commit stays auditable.
- **Transitional v2 route retirement:** Remove `agent.kind: spacedock_solver_v2` as an accepted discriminator. The canonical target is `agent.kind: spacedock_solver`, routed to the v2 class.
- **Canonical module promotion:** After the v1 file is sidelined, move the v2 module to `src/razorback/agents/spacedock_solver.py` and update import paths/tests. This is separate from the v1 sideline commit so the v1 move remains clean.
- **Later `_legacy/` deletion:** Do not delete `_legacy/` in Phase 6. Phase 7 owns optional deletion after a release-cycle delay.
- **DAB/ADE adapter retirement:** Phase 6 mechanically sidelines the in-tree DAB and ADE benchmark adapter modules after active specs/routes use harbor adapters or task views. It does not port ADE to a new harbor adapter and does not redesign DAB, those are separate work streams.
- **Unrelated dirty work:** Ignore the current dirty main-worktree edits in examples, ADE/Claude runtime code, tests, and direct canonical-renaming attempts. Implementation workers should start from a clean Phase 6 worktree and commit only Phase 6 work.

## Risk-First Order

1. Lock the canonical routing contract with failing tests before moving files: `spacedock_solver` must construct the v2 class; `spacedock_solver_v2` must reject.
2. Temporarily route canonical `spacedock_solver` to the still-existing v2 module path while v1 remains at its old module path. This de-risks the discriminator before file moves.
3. Perform the v1 solver sideline as a pure rename commit once no active route imports the old v1 path.
4. Promote the v2 module file to the canonical path and remove transitional constants/tests.
5. Flip examples and run the smallest end-to-end mechanism smoke before broad sideline sweeps.
6. Sideline non-survivor modules one logical group per commit, running focused tests after each move.
7. Finish with grep/inventory checks, statistical fallback validation, workflow resume check, and `uv run pytest`.

## Task 0: Worktree and Baseline Inventory

**Spec cites:** workflow README `implementation` stage, spec §4.5, spec §8.1.

**Files:** none committed in this task except the implementation stage report later.

- [ ] Create a clean implementation worktree, for example `.worktrees/spacedock-ensign-phase6-promote-v2-canonical`, on a branch named for the entity.
- [ ] Run `git status --short --branch` in the worktree and confirm it is clean before editing.
- [ ] Record a `HEAD` inventory:
  - `git ls-tree -r --name-only HEAD src/razorback/agents src/razorback/benchmarks src/razorback/compat src/razorback/observers`
  - `rg -n "spacedock_solver_v2|spacedock-solver|spacedock_solver|harbor_dab|kind: dab" src tests examples/specs`
- [ ] If `src/razorback/agents/codex_cli.py` is absent at `HEAD`, record that absence in validation rather than inventing a file move for AC-4 item 1.

**Commit:** none.

## Task 1: Canonical Route Tests First (AC-2)

**Spec cites:** spec §4.5 import-path dispatch, §6.2 agent block, §8.1 `rk run` translation, §8.4 runtime adapter shape.

**Files:**
- Modify/create focused tests near `tests/unit/test_spec_schema_spacedock_solver_v2.py`, `tests/unit/test_translate_spacedock_solver_import_path.py`, and `tests/unit/test_spacedock_solver_v2_class.py`.

- [ ] Add a schema test proving a v2-shaped agent block parses with `kind: spacedock_solver` and the same required fields currently used by `spacedock_solver_v2`.
- [ ] Add a routing test proving translated canonical specs emit `AgentConfig.import_path` for the v2 class and pass v2 kwargs (`runtime`, `solver_workflow`, `solver_workflow_content_hash`, `harbor_agent_kwargs`, `tools_denied`).
- [ ] Add a negative test proving `kind: spacedock_solver_v2` no longer parses/routes and raises `SpecError` or pydantic validation failure through the existing CLI error path.
- [ ] Add a regression assertion that v1-only `kind: spacedock-solver` is not the canonical spelling. If a temporary compatibility path is kept during the migration, it must be marked legacy and removed by Task 4.
- [ ] Run the focused tests and confirm they fail for the expected reason before implementation.

**Commit after Task 2:** route tests and route implementation land together once green.

## Task 2: Route `agent.kind: spacedock_solver` to the v2 Class (AC-2, AC-5)

**Spec cites:** spec §4.5, §6.2, §8.1, §8.4.

**Files:**
- Modify `src/razorback/spec/schema.py`.
- Modify `src/razorback/translate.py`.
- Modify `src/razorback/spec/freeze.py` and `src/razorback/provenance/freeze_cmd.py` where they check `spacedock_solver_v2`.
- Modify `src/razorback/spec/agent_kwargs.py` only if the frozen sealed-hash/runtime kwargs are currently inconsistent with translation.
- Modify focused tests from T1.

- [ ] Change `SpacedockSolverV2AgentBlock.kind` to `Literal["spacedock_solver"]`.
- [ ] Update translation so canonical `spacedock_solver` currently points at the v2 module import path. At this point the module may still be `razorback.agents.spacedock_solver_v2:SpacedockSolverAgent`; the route, not the filename, is the first risk to validate.
- [ ] Remove or ignore the v1 `SpacedockSolverAgentBlock` route for active parsing. If a legacy block remains for rollback, rename it to an explicit legacy spelling and keep it out of canonical examples.
- [ ] Update freeze/provenance sealed-field stamping guards from `spacedock_solver_v2` to `spacedock_solver`.
- [ ] Keep sealed-hash inputs byte-stable for unchanged v2 specs except for the intended discriminator rename. Add/adjust a focused test to compare frozen sealed fields from a canonical spec.
- [ ] Run:
  - `uv run pytest tests/unit/test_spec_schema_spacedock_solver_v2.py tests/unit/test_translate_spacedock_solver_import_path.py tests/unit/test_spacedock_solver_v2_class.py -q`
  - `uv run pytest tests/unit/test_spec_freeze_cli_pkg8.py tests/unit/test_seal_v2_six_inputs.py -q`

**Commit:** `phase6: route spacedock_solver to v2 and retire v2 discriminator`

## Task 3: Sideline v1 Solver as a Rename-Only Commit (AC-3)

**Spec cites:** spec §4.5, reconciliation AC-6.3, inventory `src/razorback/agents/spacedock_solver.py` ADAPT-EXTRACT.

**Files:**
- Move `src/razorback/agents/spacedock_solver.py` -> `src/razorback/_legacy/agents/spacedock_solver_legacy.py`.

- [ ] Ensure Task 2 already removed active imports of the v1 module path.
- [ ] Create `src/razorback/_legacy/agents/` if it does not exist using `git mv`/normal tracked directory semantics.
- [ ] Use `git mv` for the v1 file only. Do not edit the moved file in this commit.
- [ ] Run the smallest route-focused suite from Task 2. If a pure move breaks tests because a direct v1 import remains, fix that import in a predecessor commit, not in the rename-only commit.

**Commit:** `sideline: v1 SpacedockSolverAgent -> _legacy`

## Task 4: Promote the v2 Module Filename to Canonical (AC-2, AC-5)

**Spec cites:** spec §4, §4.5, §8.4.

**Files:**
- Move `src/razorback/agents/spacedock_solver_v2.py` -> `src/razorback/agents/spacedock_solver.py`.
- Update `src/razorback/translate.py`, tests, docs comments, and import strings.

- [ ] `git mv` the v2 module to the canonical filename.
- [ ] Update `SPACEDOCK_SOLVER_IMPORT_PATH` to `razorback.agents.spacedock_solver:SpacedockSolverAgent`.
- [ ] Delete `SPACEDOCK_SOLVER_V2_IMPORT_PATH` and any route-time references.
- [ ] Update tests whose purpose survives so their names/assertions refer to canonical `spacedock_solver` even if the test filenames remain transitional for one commit. Rename test files only if it reduces confusion and does not blur the commit.
- [ ] Add the `DeprecationWarning` to the moved legacy v1 class in a separate commit after the pure move. If an emergency rollback route is kept, use explicit `spacedock_solver_legacy`, not the old canonical name.
- [ ] Run the focused route/freeze/runtime suite.

**Commit:** `phase6: promote v2 solver module to canonical path`

**Optional rollback commit:** `phase6: expose deprecated spacedock_solver_legacy route`

## Task 5: Flip Examples to Canonical v2 + Harbor DAB (AC-1, AC-6)

**Spec cites:** spec §6.1 benchmark translation, §6.2 agent block, §8.1 run wrapper.

**Files:**
- Modify `examples/specs/**/*.yaml` as needed.
- Modify example generators under `examples/drivers/` only if they emit stale agent kinds or in-tree adapter blocks.
- Modify focused generator tests if present.

- [ ] Replace `agent.kind: spacedock_solver_v2` with `agent.kind: spacedock_solver`.
- [ ] Replace active DAB examples that still use the in-tree `kind: dab` path with `benchmark.kind: harbor_dab` where those examples are Phase 6/goal examples. Keep old examples only if moved under `_legacy` or explicitly marked as legacy fixtures.
- [ ] Ensure `examples/specs/bookreview-claude.frozen.yaml` exists and represents the canonical v2 + harbor-DAB path required by AC-1. If it must be generated from `bookreview-claude.yaml`, commit the frozen artifact with the example change.
- [ ] Update generator tests so matrix generation emits `spacedock_solver`, not `spacedock_solver_v2`.
- [ ] Run:
  - `uv run pytest tests/unit/test_generate_matrix_specs.py tests/unit/test_generate_matrix_specs_per_variant_kind.py tests/unit/test_codex_benchmark_spec_generator.py tests/unit/test_claude_benchmark_spec_generator.py -q` as applicable to existing files.
  - `rg -n "spacedock_solver_v2" examples/specs examples/drivers` and expect no active hits.
  - `rg -n "kind: spacedock_solver" examples/specs` and verify expected examples.

**Commit:** `phase6: update examples for canonical spacedock_solver`

## Task 6: Retire Active Registry Surface (AC-2, AC-5)

**Spec cites:** spec §4.5 import-path dispatch, §6.2 schema validation.

**Files:**
- `src/razorback/agents/registry.py`.
- Tests currently covering registry behavior.

- [ ] Decide from the live tests whether `agents/registry.py` should become a minimal schema-only helper or move to `_legacy`. The entity text says "`agents/registry.py` holds the spacedock_solver pydantic schema only"; if current architecture validates through `spec/schema.py` instead, prefer moving registry to `_legacy` and updating validation to cite the actual schema path.
- [ ] Write/update tests first:
  - canonical `spacedock_solver` schema validates v2 block fields;
  - stale `spacedock_solver_v2`, `spacedock-solver`, `claude-cli` registry routes do not appear in the active canonical registry.
- [ ] Implement the smallest active surface consistent with those tests.
- [ ] Run registry/schema/translate focused tests.

**Commit:** `phase6: trim active agent registry surface`

## Task 7: Sideline Standalone CLI Agents (AC-4.1, AC-5)

**Spec cites:** spec §1.3 "exactly one custom harbor agent", §4, §8.4 runtime adapters.

**Files:**
- Move `src/razorback/agents/claude_cli.py` -> `src/razorback/_legacy/agents/claude_cli.py`.
- Move `src/razorback/agents/codex_cli.py` -> `src/razorback/_legacy/agents/codex_cli.py` only if present at `HEAD`.
- Keep `src/razorback/agents/_runtime/{claude,codex,pi}.py`, `auth.py`, `proxy.py`, `claude_invoke.py`, `seal.py`, and canonical `spacedock_solver.py`.

- [ ] Write/update tests proving live Claude/Codex runtime routing goes through `_runtime` Harbor-backed adapters and not standalone wrappers.
- [ ] Remove active imports of `claude_cli.py`; legacy `agent.kind: claude-cli` compatibility should be removed or routed through Harbor-backed runtime before the move.
- [ ] Perform the move as one logical sideline commit for standalone CLI agents.
- [ ] Run runtime adapter and translation tests.

**Commit:** `sideline: standalone CLI agents -> _legacy`

## Task 8: Smallest End-to-End Canonical Smoke (AC-1)

**Spec cites:** spec §3.2, §6.1, §6.2, §7, §8.1.

**Files:** no production changes unless the smoke exposes a direct Phase 6 routing bug.

- [ ] Run the smallest feasible canonical route smoke before broad module moves:
  - `uv run rk run examples/specs/bookreview-claude.frozen.yaml --runs-dir .runs/phase6-canonical-smoke`
- [ ] Confirm command exit 0 and inspect `.runs/phase6-canonical-smoke/**/summary.json` for non-degraded score shape. "Non-degraded" means the summary exists, has completed trial counts, and does not lose the Phase 3/4a fields needed by `rk score`.
- [ ] If live API, Docker, DAB data, or budget prevents this run, do not silently substitute. Run the cheap structural fallback:
  - `uv run rk freeze examples/specs/bookreview-claude.yaml --out /tmp/bookreview-claude.phase6.frozen.yaml`
  - `uv run rk score tests/fixtures/score/baseline_rerun_bookreview --format json`
  - focused translate test proving canonical import path
  Record the exact blocker and the fallback output in validation.

**Commit:** none unless fixing a bug exposed by the smoke.

## Task 9: Sideline In-Tree DAB Adapter (AC-4.2, AC-6)

**Spec cites:** spec §1.3 "Razorback ships no benchmark adapters", §6.1 harbor adapter/task generator contract.

**Files:**
- Move `src/razorback/benchmarks/dab/` -> `src/razorback/_legacy/benchmarks/dab/`.
- Keep `packages/razorback-plugin-dab/` active.
- Update `translate.py`, specs, tests that still import in-tree DAB.

- [ ] Write/update tests proving active DAB examples use `harbor_dab` and translation shells to the plugin/task-view path, not `razorback.benchmarks.dab`.
- [ ] Remove active imports such as `_DEFAULT_DOCKER_IMAGE` from in-tree DAB. Replace with local constants in the surviving module only if needed for non-DAB paths.
- [ ] Move the in-tree DAB package to `_legacy`.
- [ ] Run:
  - `uv run pytest packages/razorback-plugin-dab/tests/ tests/unit/test_spec_harbor_dab_block.py tests/unit/test_translator_harbor_dab.py -q`
  - focused example/generator tests from T5.

**Commit:** `sideline: in-tree DAB adapter -> _legacy`

## Task 10: Sideline In-Tree ADE-Bench Adapter (AC-4.3)

**Spec cites:** spec §1.3 benchmark adapters live outside razorback, §6.1 task/dataset pass-through.

**Files:**
- Move `src/razorback/benchmarks/ade_bench/` -> `src/razorback/_legacy/benchmarks/ade_bench/`.
- Do not port ADE to a new adapter here.

- [ ] Inventory current ADE imports from `translate.py`, examples, and tests.
- [ ] If active ADE task-view code still depends on `src/razorback/benchmarks/ade_bench/harbor_view.py`, split this task into:
  - a predecessor commit that moves only reusable task-view materializer code to a v2-named non-adapter location, with tests;
  - the pure sideline commit for the old adapter package.
- [ ] Move the old ADE adapter package after active imports are gone.
- [ ] Run ADE-focused tests that remain in razorback. Port-out tests should be moved or deleted according to the test inventory, not left importing `_legacy`.

**Commit:** `sideline: in-tree ADE-Bench adapter -> _legacy`

## Task 11: Sideline Compat Translator Package (AC-4.4)

**Spec cites:** spec §8.1 says `rk run` is pass-through/wrapper and does not own v1 harbor 0.6.6 JobConfig construction.

**Files:**
- Move `src/razorback/compat/` -> `src/razorback/_legacy/compat/` if not already fully moved in the branch.
- Update/delete DROP tests from test inventory.

- [ ] Confirm `src/razorback/translate.py` is the only active translation surface.
- [ ] Remove active imports of `razorback.compat.*`.
- [ ] Move the package as one logical commit.
- [ ] Run all translate/freeze/run focused tests.

**Commit:** `sideline: v1 compat translator -> _legacy`

## Task 12: Sideline Observers and Remaining DROP/PORT-OUT Sweep (AC-4.5, AC-4.6, AC-5)

**Spec cites:** spec §7 run-dir contract, §8.1 `rk run` writes only razorback sidecars around harbor output.

**Files:**
- Move `src/razorback/observers/` -> `src/razorback/_legacy/observers/`.
- Sweep other DROP/PORT-OUT modules from the Phase 0 inventory that are not already sidelined, for example v1 `run.py`, `runtime/`, or v1-only CLI files if still active.

- [ ] Write/update inventory tests or grep checks proving active run-dir behavior uses harbor outputs plus `spec.frozen.yaml`/`provenance.yaml`, not observer fan-out.
- [ ] Move `observers/` in its own commit.
- [ ] For the remaining sweep, prepare a table before editing: module, inventory label, active replacement, planned move/delete, focused test command.
- [ ] Do not sweep newly added modules that are not classified by the Phase 0 inventory unless the Phase 6 AC explicitly names them.
- [ ] Run `uv run pytest tests/unit/test_cli_run_aggregator_wiring.py tests/unit/test_rk_run_v2_provenance_artifacts.py tests/unit/test_runs_aggregate.py -q` plus any focused tests that cover the moved modules.

**Commit:** `sideline: v1 observers -> _legacy`

**Commit:** `sideline: remaining v1 drop surfaces -> _legacy`

## Task 13: Canonical Inventory, Dispatch Resume, and Statistical Validation (AC-5, AC-7, AC-8, AC-9)

**Spec cites:** spec §3.2, §5, §7, §8.3, §8.3a.

**Files:**
- Validation report only.

- [ ] Run canonical grep checks:
  - `rg -n "spacedock_solver_v2|spacedock-solver" src/razorback tests examples/specs examples/drivers`
  - expected: no active hits outside `_legacy`, historical docs, or deliberately renamed transitional test files queued for cleanup.
  - `rg -n "agent.kind: spacedock_solver|kind: spacedock_solver" examples/specs`
  - expected: all active spacedock examples use canonical spelling.
- [ ] Run canonical surface inventory:
  - `find src/razorback/spec src/razorback/agents src/razorback/cli -maxdepth 3 -type f | sort`
  - cite which files are active and why they are v2-named.
- [ ] Verify commit order:
  - `git log --oneline --name-status -- src/razorback/_legacy src/razorback/agents src/razorback/benchmarks src/razorback/compat src/razorback/observers`
  - confirm AC-3 and AC-4 sideline order and no unrelated edits in sideline commits.
- [ ] AC-7 path:
  - If `uv run rk diff --help` succeeds and baseline run dirs are available, run `uv run rk diff <pre-phase6-v2-run-dir> <post-phase6-canonical-run-dir> --format json` and assert paired bootstrap CI includes zero.
  - If `rk diff` is not available, use the entity fallback: `uv run rk score <post-phase6-run-dir> --against-constant <pre-promotion-headline> --format json` and confirm the headline is inside CI per stratum. The pre-promotion headline must come from the Phase 3/4a smoke or the committed validation/baseline doc; cite the exact file or run-dir.
- [ ] AC-8 path:
  - Run the Spacedock status tool against `docs/razorback-implementation`.
  - Confirm this entity can move from implementation -> validation -> done after merge and that new v2-shaped backlog items are not blocked by the retired discriminator.
- [ ] AC-9 path:
  - `uv run pytest`
  - If full tests hit live API/Docker/budget gates, rerun the ungated focused suites plus document the exact skipped/blocking tests and environment reason.

**Commit:** validation report commit in validation stage, not implementation.

## Commit Boundary Summary

1. `phase6: route spacedock_solver to v2 and retire v2 discriminator`
2. `sideline: v1 SpacedockSolverAgent -> _legacy`
3. `phase6: promote v2 solver module to canonical path`
4. Optional: `phase6: expose deprecated spacedock_solver_legacy route`
5. `phase6: update examples for canonical spacedock_solver`
6. `phase6: trim active agent registry surface`
7. `sideline: standalone CLI agents -> _legacy`
8. `sideline: in-tree DAB adapter -> _legacy`
9. `sideline: in-tree ADE-Bench adapter -> _legacy`
10. `sideline: v1 compat translator -> _legacy`
11. `sideline: v1 observers -> _legacy`
12. `sideline: remaining v1 drop surfaces -> _legacy`

Each sideline commit must be bisect-clean. If a pure move breaks tests, create a predecessor commit that removes the active dependency, then keep the sideline commit itself move-only.

## Final Validation Checklist

- [ ] Focused TDD route/schema/freeze/runtime tests pass before broad edits.
- [ ] `spacedock_solver` is canonical and constructs the v2 class.
- [ ] `spacedock_solver_v2` no longer routes.
- [ ] v1 solver is under `_legacy/agents/spacedock_solver_legacy.py`, with deprecation warning added outside the pure rename commit.
- [ ] DAB/ADE/compat/observer sideline commits appear in AC order and are logically isolated.
- [ ] Active examples use canonical `spacedock_solver` and harbor-DAB.
- [ ] Canonical inventory cites active `src/razorback/{spec,agents,cli}` files and excludes v1/v2-transitional artifacts from active surfaces.
- [ ] AC-1 smoke succeeds or the documented fallback proves the route and explains the live-run blocker.
- [ ] AC-7 `rk diff` or `rk score --against-constant` fallback is run against cited pre/post artifacts.
- [ ] Workflow status confirms dispatch can resume.
- [ ] `uv run pytest` exits 0, or validation documents exact gated tests and focused pass set.
