---
id: zmnfnh9v2kn9v0anadpbqe1x
title: PKG-8 — Generic plugin/skill version pinning
status: backlog
source: CL 2026-05-19 — generalize "spacedock-version pin" question to all in-container agent skills/plugins
started:
completed:
verdict:
score: 0.5
worktree:
issue:
pr:
mod-block:
---

## Problem

The `SpacedockSolverAgent` halt-resume contract refuses to
resume when sealed-stage inputs (model, sampling, stages
config, prompts) differ between seed-time and resume-time.
But the seal does NOT cover everything that perturbs LLM
behavior. Specifically, **the in-container agent's skill set,
plugins, and MCP server configs are not pinned**. If the
operator's `~/.claude/skills/` changes between seed and
resume (skills evolve, mods get added, MCP servers swap), the
resumed agent has access to a different toolset than the seed
agent — but razorback considers the resume valid.

This was raised as "spacedock-version pinning" but the real
surface is broader: anything that changes the LLM's behavior
between seed and resume should be pinned. Per CL's
generalization: skill/plugin version pinning, not
spacedock-specific.

Concretely, what perturbs behavior:

- `claude` CLI binary (already pinned as `agent_cli_hash` in §6.4)
- claude-code skills directory (recursive hash) — biggest lever
- claude-code plugins directory (recursive hash) — mods, hooks
- MCP server configs (rendered settings.json hash)
- claude settings.json (already implicit via per-attempt write)

## Unlocks

- Halt-resume contracts that actually catch skill/plugin
  drift between seed and resume.
- Reproducibility claims for halt-resume runs become honest:
  "the resumed agent had access to the same skill set as the
  seed agent" is now verifiable.
- PKG-4 reliability experiments (consistency dimension across
  runs of the same task) can pin the agent environment so
  the K=5 runs are truly comparable.

## Acceptance criteria

**AC-1 — Provenance freeze adds `agent_environment_hash`.**
Verified by: a unit test against a fixture skills+plugins+MCP
config tree asserts the resolver produces a deterministic
hash. Two equivalent trees (same contents, different file
order) produce the same hash. A one-byte change in any input
file changes the hash.

**AC-2 — `provenance.yaml` carries `agent_environment_hash`
when `provenance.pin_agent_environment: true` is in the
spec.**
Verified by: a unit test runs freeze with the pin enabled
and asserts the hash is in `provenance.yaml`. With the pin
disabled (default for backward compat), the field is
absent.

**AC-3 — `rk run` re-resolves the hash at run start and
refuses with `EnvironmentDriftError` (new exit code 22 or
reuse `ProvenanceError` 11) when the resolved hash differs
from the frozen one — unless `--allow-environment-drift` is
passed.**
Verified by: a unit test mutates a skills file between
freeze and run; `rk run` exits with the drift error and
names which file changed. With the override flag, the run
proceeds but `provenance.yaml` records both hashes.

**AC-4 — SpacedockSolverAgent sealed_hash includes
`agent_environment_hash` for halt-resume sealing.**
Verified by: a unit test mutates a skills file between
seed and resume specs; the agent refuses to resume with
`SeedMismatchError` (exit 20) per the existing M4 contract.

**AC-5 — The hash resolver handles missing skills/plugins
gracefully (no error, hash reflects "absent").**
Verified by: a unit test against a fixture with no
`~/.claude/skills/` directory asserts the resolver produces
a hash (likely the empty-input hash) without raising.

**AC-6 — Carry-forward tests stay green.**
Verified by: `uv run pytest` exits 0; M4 halt-resume tests
still pass.

## Test plan

- **Unit tests:** hash determinism; sensitivity to one-byte
  changes; absence-handling; drift refusal at rk run;
  SeedMismatch on resume; --allow-environment-drift override.
- **Integration test:** none required — purely host-side
  hashing.
- **Acceptance command:** `uv run pytest` exits 0.

## Out of scope

- Per-skill version pinning (e.g., "spacedock@0.11.2
  specifically"). The recursive hash captures the directory
  state, which is finer-grained than version strings. If
  per-skill versioning becomes useful later, layer on top.
- Pinning environment beyond the agent surface (e.g., the
  container's apt package list). Defer; the design's
  `image_digest` already pins container content.
- Auto-cleanup of stale skill caches between seed and
  resume — separate concern.
