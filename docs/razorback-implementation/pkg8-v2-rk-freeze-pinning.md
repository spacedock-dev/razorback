---
id: 72ej035903fc6wrsx0h9fb4g
title: PKG-8 v2 — plugin pinning in rk freeze
status: plan
source: spec §3.2 + §8.2 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T07:26:09Z
completed:
verdict:
score:
worktree:
issue:
pr:
mod-block:
---

## Problem

Original PKG-8's plugin-pinning concern folds into v2's `rk freeze`
as an extension. Spec §3.2 names `rk freeze` as the resolver for
every dynamic input including "spacedock skill version" and
"solver-workflow content hash"; §8.2 details the resolver's surface.
What v2 adds beyond the prior design is the harbor adapter shape:
when razorback installs a harbor agent plugin (DAB-adapter, future
benchmark adapters) and a harbor agent (claude_code, codex, pi),
their versions perturb LLM behavior between freeze and re-run.
`rk freeze` must capture the installed harbor adapter + agent
plugin shape so a re-run against the same frozen manifest is
reproducible. Alias-drift detection (spec §8.2's pre-run check that
re-resolves the model alias and refuses with `AliasDriftError`) is
unchanged.

## Acceptance criteria

**AC-1 — `provenance.yaml` carries a `plugins:` block listing each
installed harbor adapter + harbor agent plugin and its version.**
Verified by: unit test against a fixture environment with the DAB
adapter and the claude_code agent installed asserts
`provenance.yaml.plugins` contains both entries with the expected
distribution metadata (package name, installed version, content
hash where applicable). Each entry carries the entry-point group
that routed it.

**AC-2 — `rk freeze` content-hashes the `solver_workflow` directory
and pins under `provenance.yaml.solver_workflow_hash`.**
Verified by: unit test against a fixture solver-workflow dir
asserts the hash is deterministic, that the hash changes when any
file under the dir changes by one byte, and that two equivalent
trees (same contents, different mtime/order) hash identically.
Cite spec §8.2 in the implementation comment.

**AC-3 — `rk run` re-resolves the plugins block at run start and
refuses with `ProvenanceError` (exit 11) when an installed plugin
differs from the frozen manifest, unless `--allow-plugin-drift` is
passed.**
Verified by: unit test mutates one plugin's installed version
between freeze and run; the run refuses with exit 11 naming the
drifted plugin. With the override flag, the run proceeds and
`provenance.yaml` records both hashes.

**AC-4 — Alias-drift detection from `rk run` (spec §8.2) stays
intact alongside the new plugin-pinning behavior.**
Verified by: existing alias-drift tests stay green; a new test
asserts that both alias-drift and plugin-drift checks fire when
both inputs change, with the first-fired surfacing in the exit
code.

**AC-5 — A freeze + re-freeze cycle on the same spec produces an
identical `provenance.yaml` (spec §3.1's idempotency rule).**
Verified by: integration test runs `rk freeze` twice against the
same fixture spec and asserts the two `provenance.yaml` files are
byte-identical.

## Test plan

- **Unit tests:** plugins-block construction (DAB-only +
  claude_code-only + both); solver_workflow recursive hash
  (determinism + byte-sensitivity + order-insensitivity);
  plugin-drift refusal at `rk run` time (default + override);
  freeze idempotency.
- **Integration test:** `rk freeze` then `rk run` against a
  fixture spec with the override flag absent; mutate an installed
  plugin version; assert the second run refuses with exit 11.
- **Acceptance command:** `uv run rk freeze <fixture-spec>` writes
  a manifest with the plugins block; `uv run rk run
  <frozen-spec>.frozen.yaml` exits 11 after a forced plugin drift.

## Out of scope

- Per-skill version pinning (e.g., "spacedock@0.11.2"). The
  solver-workflow content hash captures the relevant surface;
  per-skill version strings layer on top if a consumer demands.
- Pinning beyond harbor's plugin surface (e.g., the container's
  apt package list). Spec §6.1's `provenance.pin_image_digest`
  already covers container content.
- Auto-cleanup of stale skill caches between seed and resume.
  Separate concern; the runtime owns cache invalidation.
- The hash resolver for SpacedockSolverAgent's halt-resume sealed
  hash (spec §4.3 names this as the class's job, not `rk freeze`'s).
