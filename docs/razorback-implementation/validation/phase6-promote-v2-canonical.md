# Phase 6 Promote v2 Canonical Validation

Validator: `spacedock-ensign`
Worktree: `/home/exedev/razorback/.worktrees/spacedock-ensign-phase6-promote-v2-canonical`
Branch: `spacedock-ensign/phase6-promote-v2-canonical`
Implementation range reviewed: `a08769c..23a604c`

Gate decision: **REJECT back to implementation**.

The canonical routing work is partially correct, but the branch does not satisfy the entity ACs. The exact AC-1 acceptance artifact is missing, AC-4's required sideline commits were intentionally deferred, AC-8 workflow status fails, and AC-9 full pytest fails.

## Commands

Focused canonical suite:

```text
$ uv run pytest tests/unit/test_spec_schema_spacedock_solver.py tests/unit/test_translate_spacedock_solver_import_path.py tests/unit/test_spacedock_solver_class.py tests/unit/test_spacedock_solver_lifecycle.py tests/unit/test_spacedock_solver_freeze_on_host.py tests/unit/test_runtime_adapters.py tests/unit/test_spec_freeze_cli_pkg8.py tests/unit/test_seal_v2_six_inputs.py tests/unit/test_tools_denied_parse.py tests/unit/test_spacedock_registry.py tests/unit/test_generate_matrix_specs.py tests/unit/test_generate_matrix_specs_per_variant_kind.py tests/unit/test_codex_benchmark_spec_generator.py tests/unit/test_claude_benchmark_spec_generator.py -q
90 passed in 3.67s
```

Exact AC-1 acceptance command:

```text
$ uv run rk run examples/specs/bookreview-claude.frozen.yaml --runs-dir .runs/phase6-validation-ac1
Invalid value for 'SPEC_PATH': File 'examples/specs/bookreview-claude.frozen.yaml' does not exist.
exit 2
```

Structural fallback:

```text
$ uv run rk freeze examples/specs/bookreview-spacedock-seed.yaml --out /tmp/bookreview-spacedock.phase6-validation.frozen.yaml
ProvenanceError: unresolved provenance fields: model_resolved_version. Pass --allow-missing to write anyway
exit 11

$ uv run rk freeze examples/specs/bookreview-spacedock-seed.yaml --out /tmp/bookreview-spacedock.phase6-validation.frozen.yaml --allow-missing
wrote /tmp/bookreview-spacedock.phase6-validation.frozen.yaml
wrote examples/specs/provenance.yaml

$ sed -n '1,45p' /tmp/bookreview-spacedock.phase6-validation.frozen.yaml
version: 1
experiment: m4-bookreview-spacedock
agent:
  kind: spacedock_solver
  runtime: claude
  model: claude-opus-4-5
  sampling:
    temperature: 0.0
    top_p: null
    seed: 42
  solver_workflow: examples/solver_workflows/claude-benchmark-solver
  solver_workflow_content_hash: sha256:a7dbdb88f0229b8b8f655283498d6d4cc603c03603505fb5e9fa5d0edaf559fd
  max_turns: 200
  max_budget_usd: null
  tools_allowed:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  tools_denied: []
  append_system_prompt: null
  reasoning_effort: null
  reasoning_summary: null
  resume_from_freeze: null
  sealed_hash: 58a31226e065199ed4b86f73f638cf6a
  spacedock_skill_version: 1.0.0
  prompt_content_hashes: {}
benchmark:
  kind: harbor_dab
```

Score / AC-7 fallback:

```text
$ uv run rk diff --help
No such command 'diff'.
exit 2

$ uv run rk score tests/fixtures/score/baseline_rerun_bookreview --format json --against-constant stratified_pass_at_1=0.577
bookreview: n_completed=3, n_pass=3, pass_at_1=1.0, wilson_ci=[0.43850296824495455, 1.0]
against_constant.bookreview.verdict=matches
against_constant.stratified.mean=1.0
against_constant.stratified.verdict=above
```

Workflow status:

```text
$ python /home/exedev/.codex/skills/commission/bin/status --workflow-dir docs/razorback-implementation
Error: missing required id: workflow=docs/razorback-implementation scope=active slug=goal1-resume-t0-cost-projection id= path=docs/razorback-implementation/goal1-resume-t0-cost-projection.md
exit 1
```

Full suite:

```text
$ uv run pytest
19 failed, 572 passed, 5 skipped, 16 warnings in 186.42s
```

Representative full-suite failures:

```text
tests/integration/test_budget_gate_two_invocations.py::test_two_sequential_invocations_second_refuses
tests/integration/test_rk_run_bookreview_claude.py::test_rk_run_bookreview_claude_produces_nonzero_score
tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py::test_seed_run_then_resume_run_against_matching_sealed_hash
tests/integration/test_rk_run_v2_deterministic_smoke.py::test_deterministic_smoke_runs_end_to_end
tests/integration/test_spacedock_git_freeze.py::test_run_creates_agent_freeze_git_repo_with_stage_commits
tests/unit/test_spacedock_prompt_drift.py::test_run_refuses_when_prompt_contents_hash_does_not_match_pinned_hash
tests/unit/test_spacedock_tools_allowed.py::test_setup_env_carries_only_proxy_auth_and_home
```

## AC Results

**AC-1 - Walking skeleton holds: FAIL.**

The exact verified-by command cannot run because `examples/specs/bookreview-claude.frozen.yaml` is absent. The fallback freeze proves a different spec, `examples/specs/bookreview-spacedock-seed.yaml`, can structurally freeze as canonical `spacedock_solver` only with `--allow-missing`. It does not produce a run dir or `summary.json`, so the run-dir artifact contract in spec §7 is unverified.

**AC-2 - `spacedock_solver` routes to v2: PASS.**

The focused suite passed. `rg -n "spacedock_solver_v2|spacedock-solver" src/razorback tests examples/specs examples/drivers packages` returns only `_legacy/` hits:

```text
src/razorback/_legacy/run.py
src/razorback/_legacy/compat/harbor_0_6_6.py
src/razorback/_legacy/agents/spacedock_solver_legacy.py
```

**AC-3 - V1 class sidelined as own commit: PASS.**

`git log --diff-filter=R --summary --reverse a08769c..23a604c -- src/razorback/agents src/razorback/_legacy/agents` shows:

```text
e761ef5 sideline: v1 SpacedockSolverAgent -> _legacy
rename src/razorback/{agents/spacedock_solver.py => _legacy/agents/spacedock_solver_legacy.py} (100%)

f5c956b phase6: promote v2 solver module to canonical path
rename src/razorback/agents/{spacedock_solver_v2.py => spacedock_solver.py} (99%)
```

**AC-4 - Non-survivor modules sidelined: FAIL.**

The required six sideline commits are not present. `src/razorback/agents/claude_cli.py`, `src/razorback/benchmarks/dab/`, and `src/razorback/benchmarks/ade_bench/` remain active. `src/razorback/compat/` and `src/razorback/observers/` are already absent from canonical and present under `_legacy/`, but this branch does not satisfy the AC's required ordered sideline sequence. The implementation report says the broad DAB/ADE/standalone-CLI/compat/observer sidelines were intentionally deferred; that is a blocking AC deviation.

**AC-5 - Trimmed canonical surface: FAIL.**

The canonical solver route and registry are trimmed, but the active surface still includes non-survivors required by AC-4 to move: `src/razorback/agents/claude_cli.py`, `src/razorback/benchmarks/dab/*`, and `src/razorback/benchmarks/ade_bench/*`. `src/razorback/agents/registry.py` contains only the `spacedock_solver` pydantic helper.

**AC-6 - Examples reflect v2: PASS.**

`rg -n "spacedock_solver_v2" examples/specs examples/drivers` returns no hits. `rg -n "kind: spacedock_solver|spacedock_solver" examples/specs examples/drivers` shows canonical spacedock examples and generators. `rg -n "kind: dab|kind: in_tree_dab" examples/specs examples/drivers tests/fixtures/specs` returns no hits.

**AC-7 - Same-canonical cross-history diff: SKIPPED / fallback partial.**

`rk diff` is unavailable. The fallback score command ran and the bookreview fixture's CI includes the target constant, but this is fixture scoring, not a full post-Phase-6 canonical benchmark against a pre-promotion v2 run dir. It is acceptable as only partial evidence, not as a full AC pass.

**AC-8 - workflow dispatch can resume: FAIL.**

The documented workflow status command fails before rendering because `docs/razorback-implementation/goal1-resume-t0-cost-projection.md` is missing required `id`. The plan and implementation gates were first-officer auto-approved, not human-gated; this validation records that accurately, but the resume/status check still fails.

**AC-9 - `uv run pytest` exits 0: FAIL.**

Full pytest exits 1 with `19 failed, 572 passed, 5 skipped`. Several remaining tests directly construct the canonical `SpacedockSolverAgent` with the retired v1/Phase-3 constructor shape, and several integration smokes fail.

## Code Review

Applied the `superpowers:requesting-code-review` template to implementation range `a08769c..23a604c`. Codex did not expose a separate Task subagent tool in this session, so the review was performed directly against the diff, ACs, and validation output.

Blocking findings:

1. Missing AC-1 acceptance artifact.
   File: `examples/specs/bookreview-claude.yaml:3`
   The exact required frozen file is absent, and the remaining `bookreview-claude.yaml` is `agent.kind: claude-cli`, not canonical `spacedock_solver`. Add/commit the expected frozen canonical v2 Harbor-DAB spec or update the entity AC if a different smoke spec is intended.

2. AC-4 sideline work is incomplete.
   Files: `src/razorback/agents/_runtime/claude.py:10`, `src/razorback/benchmarks/dab/prepare.py`, `src/razorback/benchmarks/ade_bench/harbor_view.py`
   The implementation leaves active imports and modules that the AC explicitly requires to be moved. Either complete the ordered sideline commits with tests green between commits, or revise/split the AC before approval.

3. Full suite is not green.
   Files: `tests/integration/test_spacedock_git_freeze.py:67`, `tests/unit/test_spacedock_prompt_drift.py:27`, `tests/unit/test_spacedock_tools_allowed.py:78`
   Multiple surviving tests still use the old constructor/API shape and now fail. Port, rehome, or delete those tests according to the test inventory and ensure `uv run pytest` exits 0.

Non-blocking findings:

1. Compatibility/observer sideline evidence is historical, not Phase-6-local.
   `src/razorback/compat` and `src/razorback/observers` are already gone from canonical and present under `_legacy/`, but validation should cite the prior commit if the AC is narrowed to "currently sidelined" rather than "six Phase 6 commits".

## Required Fixes

1. Provide the literal AC-1 command target or update the AC: `uv run rk run examples/specs/bookreview-claude.frozen.yaml --runs-dir <dir>` must either run and produce a non-degraded `summary.json`, or the entity must name the actual canonical smoke artifact.
2. Resolve AC-4 explicitly: complete the standalone CLI, DAB, ADE, compat, observer, and sweep sideline sequence, or send the task back to planning to split broad active-import retirements into separate entities.
3. Port/rehome/delete the remaining stale v1/Phase-3 tests and make `uv run pytest` exit 0.
4. Fix or archive the malformed active workflow entity `goal1-resume-t0-cost-projection.md` so workflow status can render.
