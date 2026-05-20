---
id: d5gxb8p7eea6nk85nja5zmbr
title: Phase 3 — SpacedockSolverAgent v2
status: plan
source: plan Phase 3 + spec §4 + §8.4 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T06:37:04Z
completed:
verdict:
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
