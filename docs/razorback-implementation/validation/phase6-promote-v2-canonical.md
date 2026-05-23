# Phase 6 Promote v2 Canonical Validation, Cycle 2

Validator: `spacedock-ensign`
Role asset read: `/home/exedev/.codex/plugins/cache/spacedock/spacedock/0.12.0/skills/ensign/SKILL.md`
Worktree: `/home/exedev/razorback/.worktrees/spacedock-ensign-phase6-promote-v2-canonical`
Branch: `spacedock-ensign/phase6-promote-v2-canonical`
Implementation range reviewed: `a08769c..c19e357`

Gate decision: **APPROVE to done for the core solver-retirement merge**.

This approval accepts the first-officer-scoped split: the Phase 6 core work
promotes canonical `agent.kind: spacedock_solver`, retires the active v2
discriminator, keeps the v1 solver legacy-only, provides the literal frozen
bookreview smoke target, renders workflow status, and passes full tests.
The broad AC-4 DAB/ADE/standalone-CLI/compat/observer retirements are not
complete in this branch. I classify those as **non-blocking only for this core
solver-retirement merge** because the first officer explicitly bounded that
scope; they must be filed and tracked as follow-up entities before claiming the
original broad Phase 6 retirement complete.

The backlog -> plan, plan -> implementation, and validation re-dispatch gates
were first-officer auto-approved, not human-gated.

## Commands

Focused canonical solver suite:

```text
$ uv run pytest tests/unit/test_spec_schema_spacedock_solver.py tests/unit/test_translate_spacedock_solver_import_path.py tests/unit/test_spacedock_solver_class.py tests/unit/test_spacedock_solver_lifecycle.py tests/unit/test_spacedock_solver_freeze_on_host.py tests/unit/test_runtime_adapters.py tests/unit/test_spec_freeze_cli_pkg8.py tests/unit/test_seal_v2_six_inputs.py tests/unit/test_tools_denied_parse.py tests/unit/test_spacedock_registry.py tests/unit/test_generate_matrix_specs.py tests/unit/test_generate_matrix_specs_per_variant_kind.py tests/unit/test_codex_benchmark_spec_generator.py tests/unit/test_claude_benchmark_spec_generator.py -q
90 passed in 3.68s
```

Stale discriminator inventory:

```text
$ rg -n "spacedock_solver_v2|spacedock-solver" src/razorback tests examples/specs examples/drivers packages
src/razorback/_legacy/run.py:44:    # (e.g. spacedock-solver `sealed_hash` and `prompt_contents` populated).
src/razorback/_legacy/run.py:120:    # AC-1: instantiate the spacedock-solver agent BEFORE harbor.Job.create so
src/razorback/_legacy/agents/spacedock_solver_legacy.py:171:        return "spacedock-solver"
src/razorback/_legacy/compat/harbor_0_6_6.py:51:    threads through to spacedock-solver agent kwargs for AC-1 sealed-hash refusal.
src/razorback/_legacy/compat/harbor_0_6_6.py:112:                "spacedock-solver agent requires project_root for .env auth discovery."
src/razorback/_legacy/compat/harbor_0_6_6.py:116:                "spacedock-solver spec must be frozen (agent.sealed_hash missing). "
src/razorback/_legacy/compat/harbor_0_6_6.py:121:                "spacedock-solver spec must be frozen (agent.prompt_contents missing)."
```

Benchmark-kind inventory:

```text
$ rg -n "kind: dab|kind: in_tree_dab" examples/specs examples/drivers tests/fixtures/specs
<no output, exit 1>
```

Example canonical-kind inventory:

```text
$ rg -n "spacedock_solver_v2" examples/specs examples/drivers
<no output, exit 1>

$ rg -n "spacedock_solver" examples/specs examples/drivers
examples/drivers/generate-codex-benchmark-specs.py:132:        "kind": "spacedock_solver",
examples/drivers/generate-dab-paper-matrix-specs.py:31:            "kind": "spacedock_solver",
examples/specs/bookreview-claude.yaml:4:  kind: spacedock_solver
examples/specs/bookreview-claude.frozen.yaml:4:  kind: spacedock_solver
examples/specs/bookreview-spacedock-seed.yaml:4:  kind: spacedock_solver
examples/specs/bookreview-spacedock-resume.yaml:4:  kind: spacedock_solver
examples/specs/goal1/spacedock/bookreview.yaml:6:  kind: spacedock_solver
```

Workflow status:

```text
$ python /home/exedev/.codex/plugins/cache/spacedock/spacedock/0.12.0/skills/commission/bin/status --workflow-dir docs/razorback-implementation
...
t1     phase6-promote-v2-canonical    validation           Phase 6 -- promote v2 canonical, sideline v1 to _legacy/ 0.7      plan Phase 6 (v2 reconciliation plan at docs/superpowers/plans/2026-05-19-razorback-reconciliation-plan.md)
1e     goal1-resume-t0-cost-projection done                 T0 cost-shape verification -- Goal 1 RESUME (spacedock-first)          2026-05-21 cost-shape probe note
exit 0
```

Full suite:

```text
$ uv run pytest
574 passed, 12 skipped, 16 warnings in 33.99s
```

Frozen smoke target parse:

```text
$ uv run python - <<'PY'
from pathlib import Path
from razorback.spec.parse import parse_spec_file
p = Path('examples/specs/bookreview-claude.frozen.yaml')
spec = parse_spec_file(p)
print('exists:', p.exists())
print('agent.kind:', spec.agent.kind)
print('benchmark.kind:', spec.benchmark.kind)
print('sealed_hash:', spec.agent.sealed_hash)
print('solver_workflow_content_hash:', spec.agent.solver_workflow_content_hash)
print('data_root:', getattr(spec.benchmark, 'data_root', None))
PY
exists: True
agent.kind: spacedock_solver
benchmark.kind: harbor_dab
sealed_hash: 58a31226e065199ed4b86f73f638cf6a
solver_workflow_content_hash: sha256:a7dbdb88f0229b8b8f655283498d6d4cc603c03603505fb5e9fa5d0edaf559fd
data_root: /home/exedev/dataagentbench/data
```

Exact AC-1 command:

```text
$ uv run rk run examples/specs/bookreview-claude.frozen.yaml
Starting step 1/1: main
  3/3 Mean: 1.000
adhoc * spacedock_solver * claude-opus-4-5
Trials 3, Exceptions 0, Mean 1.000
Job Info
Total runtime: 8m 41s
Results written to /home/exedev/.local/share/razorback/runs/m3-bookreview-claude/1739dfdc7e8295ce/result.json
exit 0
```

Run-dir contract / `summary.json` check:

```text
$ uv run python - <<'PY'
import json
from pathlib import Path
run = Path('/home/exedev/.local/share/razorback/runs/m3-bookreview-claude/1739dfdc7e8295ce')
summary = json.loads((run / 'summary.json').read_text())
result = json.loads((run / 'result.json').read_text())
print('summary.exists:', (run / 'summary.json').exists())
print('result.exists:', (run / 'result.json').exists())
print('job_config.exists:', (run / '_job_config.yaml').exists())
print('n_trials_total:', summary['n_trials_total'])
print('n_trials_completed:', summary['n_trials_completed'])
print('n_trials_errored:', summary['n_trials_errored'])
print('stratified_pass_at_1:', summary['stratified_pass_at_1'])
print('datasets:', ','.join(summary['datasets'].keys()))
print('harbor_n_completed:', result['stats']['n_completed_trials'])
print('harbor_n_errors:', result['stats']['n_errored_trials'])
print('harbor_mean:', result['stats']['evals']['spacedock_solver__claude-opus-4-5__adhoc']['metrics'][0]['mean'])
PY
summary.exists: True
result.exists: True
job_config.exists: True
n_trials_total: 3
n_trials_completed: 3
n_trials_errored: 0
stratified_pass_at_1: 1.0
datasets: bookreview
harbor_n_completed: 3
harbor_n_errors: 0
harbor_mean: 1.0
```

Score and AC-7 fallback:

```text
$ uv run rk diff --help
No such command 'diff'.
exit 2

$ uv run rk score /home/exedev/.local/share/razorback/runs/m3-bookreview-claude/1739dfdc7e8295ce --format json --against-constant stratified_pass_at_1=0.577
"stratified_pass_at_1": 1.0
"stratified_n_completed": 3
"stratified_n_errored": 0
"against_constant": {"stratified": {"mean": 1.0, "verdict": "above"}, "per_stratum": {"bookreview": {"verdict": "matches", "ci": [0.43850296824495455, 1.0]}}}
```

Rename / sideline evidence:

```text
$ git log --diff-filter=R --summary --reverse a08769c..HEAD -- src/razorback/agents src/razorback/_legacy/agents
e761ef5 sideline: v1 SpacedockSolverAgent -> _legacy
rename src/razorback/{agents/spacedock_solver.py => _legacy/agents/spacedock_solver_legacy.py} (100%)

f5c956b phase6: promote v2 solver module to canonical path
rename src/razorback/agents/{spacedock_solver_v2.py => spacedock_solver.py} (99%)
```

## AC Results

**AC-1, Walking skeleton holds: PASS.**

The exact verified-by command exited 0. The run dir
`/home/exedev/.local/share/razorback/runs/m3-bookreview-claude/1739dfdc7e8295ce`
contains `summary.json`, `result.json`, and `_job_config.yaml`.
`summary.json` reports 3 total trials, 3 completed, 0 errored, and
`stratified_pass_at_1: 1.0`.

**AC-2, `spacedock_solver` routes to v2: PASS.**

The focused canonical suite passed. The run artifact also shows
`agent.import_path` as `razorback.agents.spacedock_solver:SpacedockSolverAgent`
with `agent_info.name: spacedock_solver`. Stale `spacedock_solver_v2` and
hyphenated `spacedock-solver` references are legacy-only.

**AC-3, V1 class sidelined as its own commit: PASS.**

Commit `e761ef5` is titled `sideline: v1 SpacedockSolverAgent -> _legacy` and
renames `src/razorback/agents/spacedock_solver.py` to
`src/razorback/_legacy/agents/spacedock_solver_legacy.py`. The legacy class
emits `DeprecationWarning` on instantiation.

**AC-4, Non-survivor modules sidelined: DEFERRED / NON-BLOCKING FOR THIS GATE.**

The original AC's six broad sideline commits are not all present.
`src/razorback/agents/claude_cli.py`, `src/razorback/benchmarks/dab/`, and
`src/razorback/benchmarks/ade_bench/` remain active. The implementation
documents live imports at `src/razorback/agents/_runtime/claude.py:10` and
`src/razorback/translate.py:299-300`/ADE paths. I accept the first-officer
scope split as non-blocking for the core solver-retirement merge, but this is
still mandatory follow-up scope.

**AC-5, Trimmed canonical surface: PASS FOR CORE SOLVER SCOPE, BROAD RETIREMENTS DEFERRED.**

`src/razorback/agents/registry.py` contains only the canonical
`spacedock_solver` registry entry. `src/razorback/spec/schema.py` exposes only
`kind: Literal["spacedock_solver"]` for the solver block, and
`src/razorback/translate.py` routes that block to the canonical import path.
The active DAB/ADE/Claude CLI surfaces remain intentionally deferred with AC-4.

**AC-6, Examples reflect v2: PASS.**

`examples/specs/` and `examples/drivers/` have no `spacedock_solver_v2` hits,
and the active spacedock examples/generators use `spacedock_solver`. The stale
`kind: dab` and `kind: in_tree_dab` grep returned no output.

**AC-7, Same-canonical cross-history diff: PARTIAL PASS VIA FALLBACK.**

`rk diff` is unavailable, so the AC allows the fallback score path. The live
canonical run scored `stratified_pass_at_1: 1.0`; the
`--against-constant stratified_pass_at_1=0.577` check reports the bookreview CI
matches and the stratified verdict is above. This is acceptable fallback
evidence until Phase 4b ships `rk diff`.

**AC-8, workflow dispatch can resume: PASS.**

The packaged Spacedock status command renders the workflow and exits 0. The
previous malformed active entity `goal1-resume-t0-cost-projection.md` now
appears as `done`.

**AC-9, `uv run pytest` exits 0: PASS.**

Full pytest exits 0 with `574 passed, 12 skipped, 16 warnings in 33.99s`.

## Code Review

I applied the `superpowers:requesting-code-review` template to range
`a08769c..c19e357`. Codex does not expose a Task subagent tool in this session,
so the review was performed directly against the diff, requirements, and fresh
validation output.

Blocking findings: none for the core solver-retirement merge.

Non-blocking findings:

1. Broad AC-4 retirements are not complete.
   Files: `src/razorback/agents/_runtime/claude.py:10`,
   `src/razorback/translate.py:299`, `src/razorback/benchmarks/dab/`,
   `src/razorback/benchmarks/ade_bench/`.
   This is intentionally deferred by first-officer scope, but follow-up
   entities must retire or explicitly keep each surface.

2. Internal names still carry `V2` after canonical promotion.
   Files: `src/razorback/spec/schema.py:48`,
   `src/razorback/translate.py:28`.
   The external discriminator and import path are canonical, so this is not a
   behavior blocker. A later cleanup can rename internal symbols to reduce
   historical terminology.

3. `rk diff` is absent.
   Command: `uv run rk diff --help` exits 2 with `No such command 'diff'`.
   The fallback score path is acceptable for this phase, but AC-7 should be
   rerun with real cross-history diff once Phase 4b lands.

## Required Follow-ups

1. File follow-up entities for the deferred AC-4 broad retirements:
   standalone CLI agent, in-tree DAB adapter, ADE-Bench adapter, compat,
   observers, and remaining DROP/PORT-OUT sweep.
2. Once Phase 4b lands, rerun AC-7 with the real `rk diff` cross-history
   comparison instead of the score fallback.
3. Optionally rename internal `SpacedockSolverV2AgentBlock` references to
   canonical terminology after this merge.
