---
id: 5f192b62951w0v5wx45fw8qm
title: retire v1 SpacedockSolverAgent + rename v2 to spacedock (clean cut, no rollback alias)
status: plan
source: 2026-05-23 session — captain decision after auditing v1 callers (zero production specs use kind `spacedock-solver`; all callers are test-only). The `_v2` suffix on the canonical agent leaks rewrite history into every spec. Captain directive: "i don't care about old runs, as long as new fresh run works." Supersedes `t1 phase6-promote-v2-canonical` and `sd phase7-delete-legacy` from the original reconciliation plan.
started: 2026-05-23T04:11:11Z
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
mod-block:
---

## Problem

The codebase carries two solver classes and a dual dispatch surface:

- `src/razorback/agents/spacedock_solver.py` (v1; the original) — has
  zero production callers. All references are in 8 tests + 4 fixture
  specs + `_legacy/` + the registry. The integration test for v1
  halt-resume (`test_rk_run_bookreview_spacedock_halt_resume.py`) is
  currently failing on main with `SpecError: spec must be frozen` —
  v1's spec shape diverged from the v2-era parser's requirements, and
  the AC-3.8 regression contract no longer holds.
- `src/razorback/agents/spacedock_solver_v2.py` (v2; the canonical
  agent every active research spec uses) — wired via `translate.py`'s
  hardcoded `SPACEDOCK_SOLVER_V2_IMPORT_PATH` constant, not through
  the `_REGISTRY` table that other kinds (`claude-cli`, `nop`, the v1
  `spacedock-solver`) use. The `_v2` suffix is everywhere — kind name
  in every goal1 spec, class file name, schema literal, pydantic
  block name.

The original reconciliation plan (`docs/superpowers/plans/2026-05-19-razorback-reconciliation-plan.md`)
sketched this cleanup as Phase 6 (promote v2 to canonical) + Phase 7
(delete `_legacy/`). Those entities (`t1 phase6-promote-v2-canonical`
and `sd phase7-delete-legacy`) carried the `_legacy` rollback alias
discipline — the kind name `spacedock_solver_legacy` was reserved
for emergency rollback. Captain decision 2026-05-23: skip the
rollback alias. This is a new repo; there are no old runs to migrate.
Clean cut.

Folding the two phases into one ship gives a single audit point and
avoids re-doing the rename twice. The target shape is:

- one solver class at `src/razorback/agents/spacedock.py` with class
  `SpacedockAgent`
- one kind name: `kind: spacedock` (no underscore-v2 suffix)
- one dispatch path: `_REGISTRY["spacedock"]` like every other kind
- no `_legacy/` holding tank
- no v1 tests
- no v1 fixture specs

## Acceptance criteria

**AC-1 — v1 SpacedockSolverAgent surface deleted.**
The following files are deleted via `git rm`:

- `src/razorback/agents/spacedock_solver.py`
- `tests/unit/test_v1_spacedock_solver_regression.py`
- `tests/unit/test_spacedock_registry.py`
- `tests/unit/test_translate_spacedock_solver_import_path.py`
- `tests/unit/test_spacedock_prompt_drift.py`
- `tests/unit/test_spacedock_tools_allowed.py`
- `tests/unit/test_spacedock_seed_mismatch.py`
- `tests/integration/test_spacedock_git_freeze.py`
- `tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py`
- `tests/fixtures/spacedock/seed-frozen-spec.yaml`
- `tests/fixtures/spacedock/resume-mismatch-frozen-spec.yaml`
- `examples/specs/bookreview-spacedock-seed.yaml`
- `examples/specs/bookreview-spacedock-resume.yaml`
- `src/razorback/_legacy/` (entire directory)

Verified by: `grep -rn 'kind: spacedock-solver\|from razorback.agents.spacedock_solver \|razorback._legacy' src/ tests/ examples/ packages/` returns zero hits outside this entity's body or its validation report.

**AC-2 — v2 renamed to spacedock.**
The following renames land:

- File: `src/razorback/agents/spacedock_solver_v2.py` → `src/razorback/agents/spacedock.py`
- Class: `SpacedockSolverAgent` (the v2 one) → `SpacedockAgent`
- Kind name: `spacedock_solver_v2` → `spacedock` (everywhere — schema literal, all goal1 specs at `examples/specs/goal1/spacedock/*.yaml`, deterministic smoke at `examples/specs/_deterministic-smoke-v2.frozen.yaml`, all v2 tests' fixture YAMLs, all docs that cite the kind name)
- Schema pydantic block: `SpacedockSolverV2AgentBlock` → `SpacedockAgentBlock`
- Schema literal: `Literal["spacedock_solver_v2"]` → `Literal["spacedock"]`
- Runtime adapter sub-modules at `src/razorback/agents/_runtime/{claude,codex,pi}.py` stay (their docstrings reference "v2" — update those references too).

Verified by: `grep -rn 'spacedock_solver_v2\|SpacedockSolverV2\|SpacedockSolverAgent' src/ tests/ examples/ packages/ --include='*.py' --include='*.yaml' --include='*.yml' --include='*.md'` returns zero hits in production code (test fixtures whose only purpose is the v2 contract are renamed accordingly; this entity's body + validation report may still cite the old names as historical reference).

**AC-3 — Dual dispatch eliminated.**
`_REGISTRY` in `src/razorback/agents/registry.py` carries the new
`spacedock` entry pointing at `razorback.agents.spacedock:SpacedockAgent`.
The hardcoded constants `SPACEDOCK_SOLVER_IMPORT_PATH` and
`SPACEDOCK_SOLVER_V2_IMPORT_PATH` in `src/razorback/translate.py`
are deleted; translate.py routes `spec.agent.kind` through
`resolve_agent_kind()` exactly like it routes `claude-cli` today.
Verified by: `grep -n 'SPACEDOCK_SOLVER' src/razorback/translate.py`
returns zero hits, AND `grep -n '"spacedock"' src/razorback/agents/registry.py`
returns the new `_REGISTRY` entry.

**AC-4 — Green main.**
`uv run pytest -m 'not integration' --timeout=60 -q` exits 0. The
two pre-existing failures (`test_rk_run_bookreview_spacedock_halt_resume`,
`test_rk_run_nop`) disappear with v1's deletion in AC-1; no new
regressions are introduced. Verified by: paste exit code + N/N pass count.

## Test plan

- **Mechanical:** rename + delete pass; `git mv` for file moves so
  history follows the rename.
- **Spec freeze pass:** after the kind-name rename in
  `examples/specs/goal1/spacedock/*.yaml`, re-freeze each spec
  (`rk freeze <spec>`) so the frozen kind name and the schema
  literal agree. This is essential — sealed_hash includes the spec
  content; the rename invalidates the prior frozen specs by design.
- **Unit / integration:** the existing v2 test bundle continues to
  pass under the renamed kind. Specifically:
  - `tests/unit/test_runs_dir_default.py`
  - `tests/unit/test_freeze_dir_default.py`
  - `tests/unit/test_cli_run_default_runs_dir.py`
  - `tests/unit/test_dab_paper_matrix_driver_shape.py`
  - `tests/unit/test_spacedock_solver_v2_lifecycle.py` (renamed to
    `test_spacedock_lifecycle.py`)
  - `tests/unit/test_spacedock_solver_v2_freeze_on_host.py` (renamed)
  - `tests/unit/test_spacedock_solver_v2_class.py` (renamed)
  - `tests/unit/test_spec_schema_spacedock_solver_v2.py` (renamed)
  - `tests/integration/test_v2_freeze_dir_mechanism.py` (rename
    `test_v2_*` → `test_freeze_dir_mechanism.py` etc.)
  - `tests/integration/test_freeze_cross_worktree_discovery.py`
  - `tests/integration/test_freeze_cas_resume_no_agent_invocation.py`
  - `tests/integration/test_v2_deterministic_smoke.py` (rename)
- **Acceptance:** `uv run pytest` full-suite green; main is clean
  for the first time in a while.

## Out of scope

- Backward-compat kind aliases. Captain's directive ("don't care about
  old runs") removes the need for a `spacedock_solver_legacy` rollback
  name or a `spacedock_solver_v2` deprecation shim. The cut is
  immediate.
- Migrating any prior frozen `spec.frozen.yaml` files at runs that
  used `kind: spacedock_solver_v2`. They will no longer parse against
  the new schema; if anyone wants to reproduce a prior run, they
  re-freeze the source spec under the new kind name and re-run.
  Captain confirmed this is acceptable.
- Tightening `runtime: codex|pi` schema validation. Those stubs still
  exist and still raise `NotImplementedError` at setup. Filed as
  follow-up if anyone cares.
- Cross-repo changes (the entity edits razorback only; no spacedock
  marketplace edits needed).

## Depends on

- **`merge-origin-main-after-ergonomics-sprint` (E2)** — origin/main's
  pkg40 work touches `spacedock_solver_v2.py` and the v2 lifecycle
  tests. Dispatch E3 only after E2 merges, so the rename pass operates
  on the unified file content.

## Supersedes

- `t1 phase6-promote-v2-canonical` (active in backlog) — moved to
  `_archive/` with a "Superseded by retire-v1-rename-v2-to-spacedock"
  note as part of this entity's implementation stage.
- `sd phase7-delete-legacy` (active in backlog) — same treatment.

## Resume hook

After this entity merges, the codebase has one solver kind named
`spacedock`, one dispatch surface, one agent class, and a green test
suite. Goal 1 specs all carry `kind: spacedock`; the re-run dispatches
against the clean shape. Future spec writers never see the `_v2`
suffix and never wonder which solver to use.
