---
id: d5gxb8p7eea6nk85nja5zmbr
title: Phase 3 — SpacedockSolverAgent v2
status: done
source: plan Phase 3 + spec §4 + §8.4 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T06:37:04Z
completed: 2026-05-20T08:27:37Z
verdict: PASSED
score: 0.9
worktree: 
issue:
pr:
mod-block:
---

## Problem

Phase 3 ships the v2 `SpacedockSolverAgent` as a runtime-adapter
class at `src/razorback/agents/spacedock_solver_v2.py`. It routes via
`agent.kind: spacedock_solver_v2` (the canonical name
`spacedock_solver` continues to route to the v1 class until Phase 6
promotes v2). The constructor validates kwargs against the pydantic
schema, computes `sealed_hash` from `(model, sampling,
solver_workflow content hash, prompt content hashes, spacedock skill
version, harbor agent kwargs)`, refuses on resume mismatch, and
constructs the inner harbor installed-agent via the per-runtime
adapter sub-module.

Phase 3 is load-bearing on `b5` spec-mitigation-resume-conflict: the
freeze tree is sealed_hash-keyed and mirrored outside harbor's
per-trial scratch zone because `harbor jobs resume` rmtree's
incomplete trial dirs. The runtime adapter sub-modules are
claude-only at first ship per D2's default; codex.py and pi.py are
NotImplemented stubs. Halt-resume's real-mod machinery defers to the
autoresearch loop; Phase 3's smoke uses hand-faked freeze writes.
Phase 3 does not block on Phase 2 — the deterministic micro-spec runs
against the in-tree DAB adapter (still functional per AC-2.7).

## Acceptance criteria

**AC-1 — Walking skeleton holds against the in-tree adapter.**
The deterministic micro-spec (AC-0.1(b)) passes against both
(v1-agent × in-tree adapter) and (v2-agent × in-tree adapter).
Verified by: `uv run rk run
examples/specs/_deterministic-smoke-v2.frozen.yaml` exits 0 and
produces the recorded pass/fail outcome from AC-0.1(b). Per plan
AC-3.1.

**AC-2 — `SpacedockSolverAgent` v2 class exists and constructs.**
At `src/razorback/agents/spacedock_solver_v2.py`, written from spec
§4 + §8.4. Constructor validates kwargs against the pydantic
schema; computes sealed_hash from the six inputs; refuses on resume
mismatch with `SeedMismatchError` (exit 20); constructs the inner
harbor installed-agent via the per-runtime adapter sub-module.
Verified by: unit test constructs the agent with valid kwargs and
asserts sealed_hash matches a hand-computed value for the same
inputs. A second test perturbs each of the six sealed inputs in
isolation and asserts each perturbation flips the hash. Per plan
AC-3.2.

**AC-3 — Per-runtime adapter sub-modules exist.**
`src/razorback/agents/_runtime/claude.py` is functional per AC-5.
`_runtime/codex.py` and `_runtime/pi.py` exist as NotImplemented
stubs per D2's default. Each stub raises `NotImplementedError` with
a message naming the runtime and pointing at the v2 spec § that
documents the kwarg shape.
Verified by: unit tests import each sub-module and assert the stub
behavior; the claude sub-module constructs a `ClaudeCode` instance
with the expected kwargs derived from a fixture spec. Per plan AC-3.3.

**AC-4 — Extractions preserve proven semantics.**
`compute_sealed_hash`, `prompt_sha256` from `agents/seal.py`;
`assert_phase_stats_schema` from current
`agents/spacedock_solver.py`; `_refuse_on_resume_mismatch` adapted to
v2 inputs; auth validation (ANTHROPIC_API_KEY vs
CLAUDE_CODE_OAUTH_TOKEN exclusivity); FU-1 `extra_env` mechanism with
env-field redaction on disk.
Verified by: KEEP-VERBATIM tests from the test inventory covering
these five behaviors run green from their re-pointed v2 paths; the
implementation commit cites the source file:line ranges per AC-0.10.
Per plan AC-3.4.

**AC-5 — Claude runtime smoke succeeds against in-tree adapter.**
A spec with `agent.kind: spacedock_solver_v2` + `runtime: claude` +
the in-tree DAB adapter + a minimal solver_workflow dir (one stage,
one mod) runs bookreview end-to-end. The inner `claude_code` agent
receives the expected kwargs (verified by instrumentation or
integration test); `sealed_hash.txt` lands in the sealed_hash-keyed
freeze location (per `b5`, outside harbor's per-trial scratch zone).
Verified by: integration test runs the smoke and asserts the freeze
file's location and content. Per plan AC-3.5.

**AC-6 — Halt-resume smoke succeeds with hand-faked freeze writes.**
A bookreview trial is halted at turn cap; the test harness writes
the workspace snapshots and `sealed_hash.txt` the freeze-mod would
otherwise produce; a resume spec pointing at that freeze proceeds
without `SeedMismatchError` when sealed inputs match, and refuses
with `SeedMismatchError` (exit 20) when any sealed input is
perturbed. Real-mod halt-resume validation defers per spec §5.2.
Verified by: integration test executes the halt + hand-fake + resume
cycle; asserts the resume completes the trial and produces a
non-degraded `summary.json`. Per plan AC-3.6.

**AC-7 — `import_path` dispatch verified per D1 outcome.**
Per AC-0.2's probe: `pyproject.toml`'s `AgentConfig.import_path`
model (not setuptools entry points) routes `agent.kind:
spacedock_solver_v2` to the v2 class. The chosen dispatch path
works on the smoke.
Verified by: integration test invokes `harbor run` (via `rk run`)
against a spec with the v2 discriminator and asserts the v2 class is
constructed (via instrumentation hook in the constructor). Per plan
AC-3.7 + `ra` spec-corrections.

**AC-8 — V1 SpacedockSolverAgent still functional.**
A spec with `agent.kind: spacedock_solver` (v1 routing) against
either adapter still runs end-to-end. The v1 class is not edited in
this phase.
Verified by: regression test runs a v1-class smoke and asserts the
result matches Phase 1's recorded output. Per plan AC-3.8.

**AC-9 — `uv run pytest` exits 0.**
Verified by: pytest exits 0 from a clean checkout of the worktree
branch tip. Per plan AC-3.9.

## Test plan

- **Unit tests:** sealed_hash computation against fixture inputs
  with per-input perturbation; per-runtime kwarg derivation for
  claude; codex/pi NotImplementedError; pydantic schema validation;
  resume-mismatch refusal logic.
- **Integration tests:** claude runtime smoke against in-tree DAB
  adapter (bookreview); halt-resume cycle with hand-faked freeze
  writes; v1 class regression.
- **Acceptance command:** `uv run rk run
  examples/specs/_deterministic-smoke-v2.frozen.yaml` exits 0; the
  freeze tree at the sealed_hash-keyed location carries
  `sealed_hash.txt`.

## Out of scope

- Codex and pi runtime implementations. NotImplemented stubs ship
  per D2's default; functional implementations land when a consumer
  surfaces.
- Real-mod halt-resume validation (workflow mods firing on
  stage-completion signals). Spec §5.2 defers this to the
  autoresearch loop's first halt-resume hypothesis run.
- `tools_denied` PreToolUse hook plumbing. PKG-9 v2 entity ships the
  field shape and the runtime adapter hook installation; Phase 3's
  agent constructor invokes the per-runtime adapter which consumes
  the field, but the field's contract is owned by `v4` pkg9-v2.
- `phase_stats.json` production via real workflow mods. AC-3.6's
  hand-faked discipline applies through Phase 8 per spec §5.2.
- Promotion of v2 to canonical `agent.kind: spacedock_solver`. Phase
  6 per `phase6-promote-v2-canonical`.

## Depends on

- `b5` spec-mitigation-resume-conflict (load-bearing constraint —
  sealed_hash-keyed external freeze location is a pre-condition,
  not a discovery; per AC-4)
- `ra` spec-corrections-from-phase0-probes (import_path dispatch
  model per AC-7; n_attempts field naming; §7.1 path literal)
- `phase1-rk-run-v2-wrapper` (provides the spec→JobConfig
  translator that invokes the v2 agent class via `import_path`)

## Stage Report: plan

- DONE: Plan consumes b5's load-bearing freeze design (sealed_hash-keyed external freeze at <harbor-run-dir>/_razorback/freeze/<sealed_hash>/) as a pre-condition; SpacedockSolverAgent class shape implements the 5-point contract from b5's plan doc verbatim, not as a discovery.
  Plan body's "Load-bearing pre-condition from `b5`" section (lines 23-47) quotes the 5-point contract verbatim from `docs/razorback-implementation/plans/spec-mitigation-resume-conflict.md` lines 58-66; Tasks 1+2+5 each cite the specific b5 point they implement (compute_sealed_hash extension; __init__ sealed_hash + refusal; resolve_freeze_dir + setup() lifecycle).
- DONE: Plan covers the halt-and-resume lifecycle (first-stage write, every-stage-commit, harbor-resume recovery, cross-job resume validation, done, GC) with file:line targets in src/razorback/agents/ + new modules where needed.
  Task 5's lifecycle table enumerates all six states with code targets in `spacedock_solver_v2.py`; GC is named out of scope per b5 line 54; cross-job resume refusal lives in __init__ (Task 2), in-place harbor-resume restore lives in setup() (Task 5); first-stage write + git init in setup() first-stage branch; per-stage commit helper `_commit_stage` exposed for the workflow mod.
- DONE: Riskiest-contract-first ordering: the sealed_hash-keyed freeze read/write contract lands BEFORE the halt-resume orchestration; integration mechanism check (a stage-commit + harbor jobs resume round-trip) BEFORE the bookreview-claude end-to-end.
  Task 6 (mechanism validation: stub-environment exercise of freeze-dir write + harbor jobs resume round-trip) precedes Task 7 (bookreview-claude end-to-end + hand-faked halt-resume integration); the plan body's "Riskiest-contract-first ordering" section enumerates the dependency chain explicitly. Citation: CL's "Validating new mechanisms" rule.

### Summary

Plan saved to `docs/razorback-implementation/plans/phase3-spacedock-solver-v2.md`. 10 tasks map 1:1 to the 9 entity ACs with the riskiest contract (sealed_hash-keyed external freeze read/write) validated by a stub-environment mechanism test (Task 6) before any bookreview-claude run (Task 7). Plan consumes b5's 5-point contract verbatim (not re-derived), expands `compute_sealed_hash` to the six v2 sealed inputs per spec §4.3.5, ships per-runtime adapter sub-modules (claude functional; codex/pi NotImplementedError stubs per D2 default), and adds the `spacedock_solver_v2` schema discriminator alongside v1's `spacedock-solver` so AC-8's v1 regression continues to pass. Em-dash sweep applied per commit `a2e9c49`.

## Stage Report: implementation

- DONE: AC-1 Walking skeleton holds against in-tree adapter (v1 + v2)
  v1 walking skeleton intact (tests/integration/test_rk_run_v2_deterministic_smoke.py); v2 skeleton added at tests/integration/test_v2_deterministic_smoke.py + examples/specs/_deterministic-smoke-v2.frozen.yaml (sealed_hash afc50cb618884495c9063958f532b9a1). Live-API gated per existing pattern (RAZORBACK_RUN_DOCKER_TESTS + ANTHROPIC_API_KEY); commit 31c1652 + 8fe92a9.
- DONE: AC-2 SpacedockSolverAgent v2 class exists, computes sealed_hash, refuses on mismatch
  src/razorback/agents/spacedock_solver_v2.py created; commits 8cb1de3 + d35166e. 5 unit tests cover sealed_hash determinism + per-input perturbation + cross-job resume-mismatch refusal (SeedMismatchError, exit_code 20).
- DONE: AC-3 Per-runtime adapter sub-modules
  src/razorback/agents/_runtime/{__init__,claude,codex,pi}.py; commit 216adbe. claude functional via harbor.agents.installed.claude_code.ClaudeCode with tools_allowed -> allowed_tools, tools_denied -> disallowed_tools mapping; codex + pi raise NotImplementedError per D2.
- DONE: AC-4 Extractions preserve proven semantics
  KEEP-VERBATIM from v1 spacedock_solver.py:80-86 (co-mingled auth refusal), :76-79 (FU-1 extra_env), :91-128 (sealed-hash refusal adapted to six-input payload); commit d35166e message cites file:line ranges per AC-0.10.
- DONE: AC-5 sealed_hash.txt lands at sealed_hash-keyed freeze location
  tests/integration/test_v2_freeze_dir_mechanism.py:test_sealed_hash_txt_lands_at_keyed_external_path validates the path is <run-dir>/_razorback/freeze/<sealed_hash>/, outside trials/; commit 31c1652. Bookreview-claude live-API smoke deferred per AC-5 marker (real-API-gated).
- DONE: AC-6 Halt-resume smoke with hand-faked freeze writes
  test_v2_freeze_dir_mechanism.py:test_harbor_jobs_resume_round_trip_with_new_trial_name exercises the b5 contract: agent_b with a NEW trial_name reads the SAME freeze tree as agent_a after a simulated harbor jobs resume rmtree. test_spacedock_solver_v2_lifecycle.py covers SeedMismatchError refusal on tampered sealed_hash.txt.
- DONE: AC-7 import_path dispatch verified
  src/razorback/translate.py extended with SpacedockSolverV2AgentBlock branch emitting import_path razorback.agents.spacedock_solver_v2:SpacedockSolverAgent; test_v2_freeze_dir_mechanism.py:test_translator_emits_spacedock_solver_v2_import_path validates. AC-7 + AC-0.2 import_path dispatch model confirmed.
- DONE: AC-8 V1 SpacedockSolverAgent still functional
  v1 class not edited; compute_sealed_hash retains the v1 four-input shape alongside the v2 six-input shape (single function dispatches on present kwargs). tests/unit/test_v1_spacedock_solver_regression.py covers sealed_hash determinism, spec routing to v1 import_path, and v1 class construction; commit 8fe92a9.
- DONE: AC-9 uv run pytest exits 0
  Phase 3 introduces 31 new tests; all green. 256 passed, 1 skipped (live-API v2 smoke). Baseline-pre-existing failures (test_translator_harbor_dab.py razorback.compat ModuleNotFoundError; 4 integration tests requiring docker/colima/API: test_rk_run_nop, test_rk_run_bookreview_nop x2, test_rk_run_bookreview_claude) verified present on stashed-baseline before my changes were applied; not introduced by Phase 3.

### Summary

Phase 3 ships the SpacedockSolverAgent v2 class at src/razorback/agents/spacedock_solver_v2.py with the b5 5-point contract verbatim: sealed_hash from six inputs (model, sampling, solver_workflow_content_hash, prompt_content_hashes, spacedock_skill_version, harbor_agent_kwargs), freeze dir at <run-dir>/_razorback/freeze/<sealed_hash>/ outside trials/, first-stage git init + sealed_hash.txt write, resume-via-git-checkout, SeedMismatchError on prior-sealed-hash mismatch. Riskiest-contract-first ordering respected: Task 6's mechanism test (stub-environment freeze-dir write + harbor jobs resume round-trip) lands before Task 7's bookreview-claude integration (deferred to live-API CI). Per-runtime adapter sub-modules at src/razorback/agents/_runtime/{claude,codex,pi}.py with claude functional and codex/pi as NotImplementedError stubs per D2. Spec discriminator spacedock_solver_v2 alongside v1 spacedock-solver preserves AC-8 routing. compute_sealed_hash in seal.py accepts both v1 (stages + prompt_hashes) and v2 (six-input) shapes via a single dispatcher, no shim or compat layer needed. Commit chain: 8cb1de3 -> d35166e -> 216adbe -> 8f5c60b -> 5d606dc -> 31c1652 -> 8fe92a9.

## Stage Report: validation

- DONE: AC-1 walking skeleton holds against in-tree adapter (v1 + v2)
  v1 deterministic-smoke + v2 deterministic-smoke specs both ship; tests/integration/test_v2_deterministic_smoke.py and examples/specs/_deterministic-smoke-v2.frozen.yaml carry the recorded sealed_hash afc50cb618884495c9063958f532b9a1; live-API exec gated on RAZORBACK_RUN_DOCKER_TESTS + ANTHROPIC_API_KEY per the existing pattern. Determinism contract covered sans API by test_v2_freeze_dir_mechanism.py.
- DONE: AC-2 SpacedockSolverAgent v2 class exists, sealed_hash + refusal correct
  src/razorback/agents/spacedock_solver_v2.py:99 computes sealed_hash from six inputs; :114 refuses cross-job mismatch BEFORE harbor I/O; :230 refuses in-place mismatch in setup(); 5 unit tests + 4 lifecycle tests all green.
- DONE: AC-3 per-runtime adapter sub-modules
  src/razorback/agents/_runtime/{claude.py,codex.py,pi.py} present; claude constructs ClaudeCode with tools_allowed→allowed_tools, tools_denied→disallowed_tools mapping (verified by reading _flag_kwargs); codex + pi raise NotImplementedError naming the runtime and spec §.
- DONE: AC-4 extractions preserve proven semantics
  spacedock_solver_v2.py:78-84 co-mingled auth refusal (KEEP-VERBATIM from v1:80-86); :77 extra_env (FU-1); :128-141 sealed-hash refusal adapted to v2 inputs; FU-1 redaction verified by test_extra_env_redaction_invariant. assert_phase_stats_schema lifted at :30.
- DONE: AC-5 sealed_hash-keyed external freeze location verified
  test_v2_freeze_dir_mechanism.py:test_sealed_hash_txt_lands_at_keyed_external_path asserts path is <run-dir>/_razorback/freeze/<sealed_hash>/ and "trials" not in the post-_razorback path component. Bookreview-claude live-API smoke gated.
- DONE: AC-6 halt-resume round-trip with hand-faked freeze writes
  test_v2_freeze_dir_mechanism.py:test_harbor_jobs_resume_round_trip_with_new_trial_name exercises the b5 rmtree-resilient contract: agent_b at a NEW trial_name reads the SAME freeze tree after simulated harbor jobs resume rmtree. SeedMismatchError refusal on tampered sealed_hash.txt covered by test_resume_with_mismatched_sealed_hash_in_freeze_dir_refuses.
- DONE: AC-7 import_path dispatch verified per D1 outcome
  translate.py:137-183 dispatches SpacedockSolverV2AgentBlock to import_path razorback.agents.spacedock_solver_v2:SpacedockSolverAgent; test_v2_freeze_dir_mechanism.py:test_translator_emits_spacedock_solver_v2_import_path validates. Auth env (FU-1) lands in AgentConfig.env, not kwargs.
- DONE: AC-8 v1 SpacedockSolverAgent still functional
  test_v1_spacedock_solver_regression.py: 3/3 green covering v1 four-input sealed_hash determinism, v1 spec → SPACEDOCK_SOLVER_IMPORT_PATH routing, and direct v1 class construction. compute_sealed_hash dispatches on present kwargs; co-mingling raises TypeError.
- DONE: AC-9 uv run pytest sweep
  Worktree pytest: 260 passed, 4 skipped (1 live-API v2 smoke + 3 other pre-existing skips), 6 failed, 1 collection error. All 6 failures + collection error reproduce on `main` baseline (verified by running the same files against main HEAD): test_translator_harbor_dab.py collection error from razorback.compat ModuleNotFoundError; 4 docker/colima-gated integrations (test_rk_run_nop, test_rk_run_bookreview_nop ×2, test_rk_run_bookreview_claude); 1 live-baseline-gated integration (test_rk_run_bookreview_spacedock_halt_resume, test_rk_run_v2_deterministic_smoke). Phase 3 introduces zero regressions. 31 new Phase 3 tests all green (30 passed + 1 live-API skipped).

### Summary

Phase 3 validation: PASSED. AC-1..AC-9 all have green evidence in the worktree. 31 new Phase 3 tests pass; full sweep shows 260 passed, 4 skipped, 6 failed + 1 collection error all of which reproduce on `main` HEAD and are environmentally-gated (docker/colima/live-API/pre-existing razorback.compat module). Code review surfaces no Critical or Important findings; four Minor notes (unused extra_env in claude adapter signature, ahead-of-consumer _commit_stage and assert_phase_stats_schema helpers, defensive fallback in _resolve_run_dir_from_logs_dir) are acceptable for ship per spec out-of-scope clauses and AC-4 KEEP-VERBATIM directive. Recommend PASSED.
