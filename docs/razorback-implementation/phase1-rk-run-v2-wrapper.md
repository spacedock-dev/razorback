---
id: e34q91ykfa8g281cdf523b1v
title: Phase 1 — rk run v2 wrapper
status: implementation
source: plan Phase 1 + spec §3.2 + §8.1 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T06:23:05Z
completed:
verdict:
score: 0.9
worktree: .worktrees/spacedock-ensign-phase1-rk-run-v2-wrapper
issue:
pr:
mod-block:
---

## Problem

Phase 1 ships the v2 `rk run` as a pre-check wrapper around `harbor
run`. It reads the frozen spec, runs the alias-drift pre-check
against the resolved model version, delegates execution to harbor
through the import-path dispatch model the AC-0.2 probe verified
(`AgentConfig.import_path` per spec corrections), passes harbor's
exit code through (reserving exit 30 for harbor runtime failure),
and writes `spec.frozen.yaml` + `provenance.yaml` into the
harbor-produced run-dir. The current path's `src/razorback/run.py`
+ orchestration helpers sideline under `git mv` to
`src/razorback/_legacy/`. Phase 1 holds the walking-skeleton check
(in-tree DAB adapter still runs) and does not depend on Phase 2.

The spec→JobConfig translator built here is load-bearing for every
later phase; Phase 3's agent class is invoked through it, Phase 4a's
budget gate extends its flag set, and the matrix dispatcher loops
over its invocation. The dispatch route — direct via
`AgentConfig.import_path` or fallback via `rk run` spec
pre-translation — is finalized here per AC-0.2's outcome.

## Acceptance criteria

**AC-1 — Walking skeleton holds; `rk run` produces a run-dir against
the in-tree DAB adapter.**
Verified by: `uv run rk run examples/specs/bookreview-claude.frozen.yaml`
exits 0 and produces a run-dir whose `summary.json` parses against
the harbor schema. Per plan AC-1.1.

**AC-2 — `rk run` reads the frozen spec, runs the alias-drift
pre-check, delegates to harbor, and passes the exit code through.**
Verified by: unit test mocks the provider model-resolution call;
asserts `AliasDriftError` raised when the resolved version differs
from `provenance.yaml.model_resolved_version` and the
`--allow-alias-drift` flag suppresses the error. A second unit test
asserts exit code 30 surfaces when harbor's delegated invocation
exits non-zero. Per plan AC-1.2; spec §3.2 + §8.1 + §3.4 exit-code
table.

**AC-3 — `rk run` writes `spec.frozen.yaml` + `provenance.yaml` into
the harbor-produced run-dir.**
Verified by: integration test runs the deterministic micro-spec
(AC-0.1(b)); asserts both files are present in the run-dir and that
their content matches the input frozen spec byte-for-byte (no
re-freezing inside `rk run`). Per plan AC-1.2 + spec §7.1.

**AC-4 — Extracted behaviors preserve their proven semantics.**
Alias-drift detection (resolved-version comparison vs
`provenance.yaml.model_resolved_version`), auth handling (`.env`
via `dotenv_values` per FU-1 M3 AC-3), and run-dir creation helpers
move into the v2 path with attribution.
Verified by: tests classified KEEP-VERBATIM in the test inventory
(`docs/superpowers/plans/2026-05-19-razorback-test-inventory.md`)
that cover these three behaviors run green from their re-pointed v2
paths; the implementation commit cites the source file:line ranges
per AC-0.10. Per plan AC-1.3 + AC-1.5.

**AC-5 — Superseded `run.py` and helpers move to `_legacy/`.**
Verified by: `git log --diff-filter=R -- src/razorback/run.py` shows
the move into `src/razorback/_legacy/run.py`; the v1 path remains
importable from there for parity tests. Per plan AC-1.4.

**AC-6 — Dispatch route reflects AC-0.2 outcome.**
Per the harbor-entry-point probe: `AgentConfig.import_path:
"razorback.agents.spacedock_solver:SpacedockSolverAgent"` is the
dispatch shape harbor accepts. `rk run`'s translation logic emits
the spec with `import_path` populated; the entry-point group
language from older spec wording does not appear in code or tests.
Verified by: unit test feeds a spec with `agent.kind:
spacedock_solver` and asserts the post-translation `AgentConfig`
carries the correct `import_path`. Depends on `ra`
spec-corrections-from-phase0-probes landing first.

**AC-7 — `uv run pytest` exits 0.**
Verified by: pytest exits 0 from a clean checkout of the worktree
branch tip. Per plan AC-1.6.

**AC-8 — Runs-dir mount-visibility canary at start of run.**
Before any agent invocation, `rk run` verifies the resolved
`--runs-dir` is visible to the harbor-orchestrated docker
containers. v1's `tests/conftest.py:12-23` `colima_safe_tmp_path`
fixture encodes this discipline for tests; v2's `rk run` lifts it
to the CLI boundary via a runtime probe (write a canary file under
the resolved runs-dir, exec `ls <canary>` inside the planned
container environment, abort with `ExitCode.CONFIG_INVALID` and a
clean diagnostic if the canary is missing). The check is robust to
non-`/Users/` virtiofs mounts (configurable via `colima.yaml`) —
it probes actual visibility, not a hardcoded path prefix. On
non-macOS systems the canary still runs and succeeds in the
normal case; the same error class fires if `runs-dir` is on a
filesystem the container can't see (NFS-restricted mount,
unmounted volume).
Verified by: a synthetic test invokes `rk run --runs-dir /tmp/...`
on a macOS+Colima environment and asserts (a) the run aborts with
`ExitCode.CONFIG_INVALID` before any agent step; (b) the error
message names the runs-dir, its resolved path, and the fix (e.g.,
"use --runs-dir under /Users/... or a virtiofs-mounted volume").
A positive test under `/Users/.../.runs/...` confirms the canary
passes and the run proceeds normally. Reference investigation:
`docs/superpowers/plans/2026-05-20-v1-bookreview-regression-investigation.md`.

## Test plan

- **Unit tests:** alias-drift pre-check (mocked provider API);
  harbor-passthrough exit-code surfacing (mocked harbor invocation);
  spec→JobConfig `import_path` translation; auth handling via
  `dotenv_values`. KEEP-VERBATIM tests from the test inventory cover
  alias-drift logic and auth; RE-AUTHOR tests cover the new
  harbor-delegation path.
- **Integration test:** `rk run` against the deterministic
  micro-spec produces a run-dir whose `summary.json` parses and
  whose `provenance.yaml` matches the input frozen spec.
- **Acceptance command:** `uv run rk run
  examples/specs/_deterministic-smoke.frozen.yaml` exits 0 with the
  expected pass/fail outcome recorded in AC-0.1(b).

## Out of scope

- Per-experiment budget gate (`--max-budget-usd-running <file>`).
  Phase 4a ships this; see `phase4a-rk-run-budget-gate`.
- `rk freeze` extensions (solver_workflow_hash,
  spacedock_skill_version, harbor_agent_kwargs_hash). Phase 4a per
  `72` pkg8-v2-rk-freeze-pinning extends these alongside the budget
  gate.
- `SpacedockSolverAgent` v2 class. Phase 3 per
  `phase3-spacedock-solver-v2`; the spec→JobConfig translator
  built here invokes it through `import_path` but does not
  implement it.
- DAB harbor adapter. Phase 2 per `phase2-dab-harbor-adapter`;
  Phase 1's walking-skeleton check uses the in-tree DAB adapter.

## Depends on

- `b5` spec-mitigation-resume-conflict (architectural §4.4 +
  §7.1 — sealed_hash-keyed external freeze location informs
  `rk run`'s emit canonicalization rule per AC-3)
- `ra` spec-corrections-from-phase0-probes (spec wording fixes —
  import_path terminology, n_attempts field name, §7.1 path
  literal — that Phase 1's plan stage cites in its AC list)

## Stage Report: plan

- DONE: Plan covers all 8 ACs (including AC-8 runs-dir mount-visibility canary added during Phase 0) with file:line modules-to-touch named — src/razorback/cli/run.py + benchmarks/dab/prepare.py + new emit logic for spec→JobConfig translation.
  Plan at `docs/razorback-implementation/plans/phase1-rk-run-v2-wrapper.md` enumerates 10 tasks across 8 ACs with explicit AC↔task map. File:line anchors named per `docs/superpowers/plans/2026-05-19-razorback-inventory.md`: `errors.py:7-16` (Task 1), `agents/auth.py:13-67` (Task 2), `provenance/drift.py:11-35` (Task 3), `compat/harbor_0_6_6.py:96-157` (Task 5 lifts the import_path emit contract), `cli/run.py:22-34` (Task 7 keeps the error→exit-code mapping). Spec→JobConfig translator emit logic lives in NEW module `src/razorback/translate.py` (replaces v1 `compat/harbor_0_6_6.py` per inventory `compat/` DROP classification — v2 ships one harbor minor per §9.1 + Phase 0 D5). DAB walking-skeleton consumes existing in-tree `src/razorback/benchmarks/dab/prepare.py` (Phase 2 ports out).
- DONE: Plan acknowledges b5's shipped freeze-tree design (_razorback/freeze/<sealed_hash>/, jobs_dir canonicalization in §3.1+§8.1) and ra's in-flight import_path / n_attempts / observers wording fixes — cites section identities, NOT exact wording, so ra's concurrent implementation doesn't invalidate the plan.
  Plan header's "Spec source of truth" + "Concurrent dependency status" paragraphs name both dependencies. b5's contract is consumed by Task 7 (jobs_dir canonicalization via §3.1's path-canonicalization rule, runs-dir resolved absolute before `harbor run`) and is explicitly out-of-scope-but-coordinated for Task 5 (Phase 3 owns the freeze tree path; Phase 1's translator must not emit any conflicting path). ra is gated for implementation stage; plan-stage shipping does not block on ra per the "Execution Handoff" section.
- DONE: TDD checkpoints land per AC; integration-level mechanism validation (smallest end-to-end exercise — the deterministic-smoke spec at examples/specs/_deterministic-smoke.yaml) comes before comprehensive bookreview-claude runs.
  Tasks 1, 5, 6, 7, 8 each follow Write-failing-test → verify-fail → minimal-impl → verify-pass → commit. Task 9 is the integration walking-skeleton against `examples/specs/_deterministic-smoke.yaml` (baseline 3/3 pass at commit e014dbf per `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`). Task 5 (translator + import_path emit) and Task 6 (runs-dir canary) land BEFORE Task 7's harbor-delegation body — riskiest-contract-first per CL's "Validating new mechanisms" rule. Self-Review section §2 in the plan calls this out explicitly.

### Summary

Wrote separate-doc plan to `docs/razorback-implementation/plans/phase1-rk-run-v2-wrapper.md` per README flex rule (8 ACs > 3 threshold). Plan structures 10 TDD tasks across 6 small modules (`errors.py`, `translate.py` NEW, `runs_dir_canary.py` NEW, `cli/run.py`, plus verifications of `agents/auth.py` and `provenance/drift.py`) plus one mechanical `git mv` to `_legacy/`. Riskiest-contract-first ordering lands the spec→`AgentConfig.import_path` translator + the runs-dir mount-visibility canary BEFORE the harbor-delegation body, and the deterministic-smoke walking-skeleton (1 dataset, N=1, 6:30 baseline) before any comprehensive bookreview-claude run. Plan cites spec sections by identity (§3.1, §6.1, §6.2, §7.1, §8.1) not wording, so ra's concurrent §4.5/§6.1/§6.3/§9.2 edits do not invalidate the plan; b5's shipped sealed_hash-keyed external freeze design informs Task 7's jobs_dir canonicalization without Phase 1 implementing Phase 3's class.
