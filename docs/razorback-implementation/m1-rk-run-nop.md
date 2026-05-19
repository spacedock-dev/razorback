---
id: zknb9f32jpzgtg83k9q7wm9d
title: M1 — rk run against nop agent
status: plan
source: design §8
started: 2026-05-19T07:16:21Z
completed:
verdict:
score: 1.0
worktree:
issue:
pr:
mod-block:
---

## Problem

First runnable slice. `rk run` translates a frozen spec into a
`harbor.JobConfig`, calls `Job.create(JobConfig)` and `Job.run()`
against harbor's bundled `nop` agent, and writes a run-dir that
matches the public contract in §6.3. Proves the spec → harbor →
run-dir lifecycle end-to-end before any DAB or claude work happens.
See §8.M1 and §6.1 of the design doc.

The pre-M1 harbor smoke (`scripts/smoke_nop.py`, committed on `main`)
already confirmed that `Job.create + Job.run` work against the nop
agent and that the per-trial layout matches §6.3. M1's job is to put
the rest of the lifecycle (spec parser, frozen-spec writer, manifest
writer, observers, CLI entry point) around that working core.

## Acceptance criteria

Each AC names a property of the finished milestone (an artifact or a
run-dir invariant) and how it is verified.

**AC-1 — `rk run examples/specs/nop.yaml` exits 0.**
Verified by: `uv run rk run examples/specs/nop.yaml` from a clean
checkout of the milestone branch produces exit code 0 and writes a
run-dir under `_runs/<experiment>/<job_name>/`.

**AC-2 — Run-dir layout matches §6.3.**
Verified by: the run-dir contains, at the top level, all of
`spec.frozen.yaml`, `manifest.json`, `events.jsonl`,
`summary.json`, plus harbor's `lock.json`. Each `trials/<task>-NNNN/`
subdir contains harbor's `config.json`, `result.json`, `agent/`,
`verifier/`, and `artifacts/` per §6.3.

**AC-3 — `spec.frozen.yaml` is a faithful echo of the input spec.**
Verified by: `diff` between the input spec and
`spec.frozen.yaml` shows only the additions razorback writes
(M1 defers full provenance resolution to M5; the M1 freeze writer
echoes the input plus razorback's `version: 1` envelope and any
defaults it materializes).

**AC-4 — `manifest.json` carries `run_dir_version: 1` and a
`created_at` ISO 8601 timestamp.**
Verified by: `jq '.run_dir_version, .created_at'` returns `1` and
a valid ISO 8601 string per §6.7.

**AC-5 — `events.jsonl` contains one JSON object per fired
`TrialEvent`, in fire order, written by a single drainer
coroutine.**
Verified by: `wc -l` matches the count of `TrialEvent` hooks that
fired during the run; each line is a valid JSON object;
`jq .event` lists at least `start`, `environment_start`,
`agent_start`, `end` in chronological order (verifier_start fires
when verification runs; cancel fires only on explicit cancellation).

**AC-6 — `job_name` is the SHA-256 of the frozen spec, truncated
to 16 hex chars.**
Verified by: `sha256sum spec.frozen.yaml | cut -c1-16` matches the
`job_name` segment of the run-dir path, per §6.7.

**AC-7 — Spec validation rejects unknown top-level keys with a
typed `SpecError` and exit code 10.**
Verified by: a unit test feeds a spec with `unknown_key: foo` to
the parser and asserts a `SpecError` is raised; the CLI exits with
code 10 when fed the same spec.

**AC-8 — The stdout observer prints a single human-readable line
per `TrialEvent` while the jsonl observer fills `events.jsonl`,
both reading from the same single-writer asyncio channel (§6.6).**
Verified by: `uv run rk run examples/specs/nop.yaml` stdout has
one line per fired event in fire order; the corresponding
`events.jsonl` rows line-match the stdout summary.

## Test plan

- **Unit tests:** spec parser (valid spec, unknown key rejected,
  missing required key rejected); job_name derivation
  (sha256[:16]); manifest writer (`run_dir_version: 1`,
  `created_at` is ISO 8601 with timezone); events drainer
  (concurrent hook callbacks serialize through the channel without
  interleaved partial writes).
- **Integration test:** `rk run` against
  `examples/specs/nop.yaml` from a `tmp_path`-style fixture rooted
  under `/Users/clkao/...` (so harbor's bind mount works on
  Colima). Asserts AC-1 through AC-8 end-to-end. Uses
  `VerifierConfig(disable=True)` initially; flips to a live
  verifier once the hello-world task has a working `tests/test.sh`
  (see `docs/pre-m1-findings.md`).
- **Acceptance command:** `uv run rk run examples/specs/nop.yaml`
  is the §8.M1 acceptance command the validator reruns.
- **Implementation plan:** `docs/razorback-implementation/plans/m1-rk-run-nop.md`.

## Out of scope

- Full provenance resolution (model versions, image digests, CLI
  hashes, git SHAs) — that is §M5.
- DAB adapter, scoring, paired diff — §M2, §M5, §M6.
- Custom `BaseAgent` subclasses (`ClaudeCliAgent`,
  `CodexCliAgent`, `SpacedockSolverAgent`) — §M3, §M4.
- `constraints check`, `baseline promote/verify`, `runs diff`,
  `registry` subcommands — §M6.
- The hello-world verifier `reward.txt` mystery surfaced in pre-M1
  is **in scope** here as part of AC-1's end-to-end run: the M1
  plan must produce a `tests/test.sh` for the nop spec's
  hello-world task that actually drops a reward file, and the
  run-dir must show `n_errored_trials: 0`.

## Stage Report: plan

- DONE: Plan steps map 1:1 to the 8 AC items in the M1 body, each with the design-doc §-cite that governs it (§6.1 harbor integration, §6.3 run-dir layout, §6.6 async observers, §6.7 job_name from sha256[:16], §3.2 exit codes).
  AC↔task map table is at the top of the plan; each AC names its governing §-cite and the tasks that implement and assert it.
- DONE: The riskiest contract — harbor's verifier reward.txt under Colima bind-mounts (see docs/pre-m1-findings.md) — is the FIRST integration step in the plan, not the last. Scaffolding (CLI, parser modules) follows after the live nop+hello-world+verifier round-trip is proven on the operator's machine.
  Task 1 ("Mechanism validation — live nop+hello-world+verifier round-trip") precedes every scaffolding task; tasks 2–6 (errors, spec, freeze, job_name, manifest, CLI plumbing) come after.
- DONE: The plan is committed to docs/razorback-implementation/plans/m1-rk-run-nop.md on main as a single file (entity stays a flat .md, not folder form), and the M1 entity body's Test plan section is extended with a one-line cross-reference to the plan path.
  Plan path: `docs/razorback-implementation/plans/m1-rk-run-nop.md` (single file on main). Entity Test plan now ends with the cross-reference line.

### Summary

Plan written via the superpowers:writing-plans skill, 15 tasks ordered riskiest-contract-first. Task 1 runs the live nop+hello-world+verifier round-trip before any razorback code lands, so if `reward.txt` doesn't survive Colima bind-mounts we know on day one and escalate before scaffolding. Each AC maps to at least one TDD-shaped task with failing-test → green-test → commit cadence; the §8.M1 acceptance command appears as Task 14's interactive validation alongside the subprocess-driven integration test in Tasks 11–12.

## Stage Report: implementation

- DONE: Plan Task 1 (live nop+hello-world+verifier round-trip) is exercised on the operator's machine BEFORE any razorback scaffolding code is written. The mechanism check must pass — a real run-dir with reward.txt actually deposited on the host — before tasks 2+ start. If it fails on the bind-mount/Colima path, STOP and escalate to the FO instead of working around.
  Mechanism smoke ran first (commit 29eb878). First execution surfaced the real Colima risk: `bash` not in `alpine:3.20` PATH → harbor's `bash -c` exec returns OCI 127 → nothing lands in the verifier bind mount. Fixed at the task-manifest layer (`RUN apk add --no-cache bash` in `examples/tasks/hello-world/environment/Dockerfile`) — within the plan's Step 4 option (a). After fix: events fired = `[start, environment_start, agent_start, verification_start, end]`, `n_completed=1`, `n_errored=0`, `reward.txt` (3B `'1.0'`) and `test-stdout.txt` (17B) visible on host.
- DONE: Each AC-N in the M1 entity body has at least one passing test that proves its `Verified by:` clause from a clean checkout of the worktree branch — confirmed by `uv run pytest` exiting 0 and the §8.M1 acceptance command `uv run rk run examples/specs/nop.yaml` exiting 0 with a run-dir whose `_runs/<experiment>/<job_name>/` contains spec.frozen.yaml, manifest.json, events.jsonl, summary.json, and harbor's lock.json + per-trial subtree.
  17/17 pytest passed (15 unit + 2 integration). `uv run rk run examples/specs/nop.yaml` exits 0 with `_runs/m1-nop/2ad8314cc61b194f/` containing spec.frozen.yaml, manifest.json, events.jsonl (5 rows), summary.json (`n_errored_trials: 0`), lock.json, and `hello-world__62AYkys/{config.json, result.json, agent/, verifier/, artifacts/}`.
- DONE: Commits follow the plan's `m1: <short summary>` format, one focused commit per plan task, with the failing test landing before the implementation that makes it green. The worktree branch tip is ready for fresh-agent validation review without follow-up cleanup.
  13 atomic commits on `spacedock-ensign/m1-rk-run-nop` (29eb878..2063869), each `m1: <summary>` and one-per-plan-task. Tasks 14 (interactive acceptance) and Task 15 (cross-reference already landed in the plan-stage commit) deliberately produce no commit per the plan. Worktree is clean.

### Summary

M1 lands `rk run` against harbor's nop agent end-to-end. The pre-M1 verifier-on-Colima risk surfaced exactly where it was predicted (Task 1, mechanism-first): alpine's missing bash broke every `bash -c` exec harbor issues. Fix was a single-line `apk add bash` in the task Dockerfile, not a design change. Every AC has a green test from a clean branch checkout, with the §8.M1 command exiting 0 and writing the §6.3 layout.

One scoped plan deviation: Task 1's smoke writes under `<repo>/.smoke-tmp/` rather than `~/.cache/razorback-smoke/` — the harness sandbox denies `~/.cache` writes, but both paths are equally Colima-mountable under `/Users/clkao/`. `.smoke-tmp/` is gitignored and the cwd is still under `/Users/clkao/`, so harbor's bind mount works as the plan intended.
