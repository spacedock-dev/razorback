---
id: 7z4xe5883k8p181g176wq79q
title: PKG-22 — provenance writer extension for claude-cli agent kind
status: backlog
source: Goal 2 T0 retry 2026-05-20 (worker observation on .worktrees/spacedock-ensign-goal2-ade-bench-haiku-baseline) — provenance writer at src/razorback/provenance/freeze_cmd.py:97-107 omits solver_workflow_hash / spacedock_skill_version / harbor_agent_kwargs_hash / tools_denied when agent kind != spacedock_solver_v2
started:
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
mod-block:
---

## Problem

`src/razorback/provenance/freeze_cmd.py:97-107` writes the
provenance.yaml sealed-input set only for agent kind ==
`spacedock_solver` (historical spelling at observation time; canonical now
`spacedock_solver`). For agent kind == `claude-cli` (the kind
Goal 2's matrix uses; also the kind Goal 1 uses for two of its
three variants), the writer emits a smaller field set and omits:

- `solver_workflow_hash`
- `spacedock_skill_version`
- `harbor_agent_kwargs_hash`
- `tools_denied`

Goal 1's AC-2 and Goal 2's AC-2 both require these four fields to
be present in every cell's provenance.yaml. The Goal 2 implementation
ensign correctly flagged this as a contract mismatch on 2026-05-20.

The plan workers for both Goal 1 and Goal 2 copied the AC-2 field
list from the v2 spec's spacedock-shaped reference shape without
checking whether `claude-cli` kind populates them. The writer's
behavior is by construction (claude-cli has no spacedock workflow
to hash, no spacedock skill version to record, no agent_kwargs
shape, and no DAB DISALLOWED_TOOLS-equivalent for the non-DAB
adapters), so the AC-2 assertion is over-broad rather than the
writer being buggy.

PKG-22 resolves the mismatch by making the writer emit
agent-kind-appropriate values for these four fields under
`claude-cli` kind — populating them where a defensible
interpretation exists, marking them `null` where one does not, but
in either case ensuring the keys are present so downstream tooling
that asserts on the schema does not bomb.

## Acceptance criteria

**AC-1 — Provenance schema is stable across agent kinds.** Every
cell's provenance.yaml (under any supported agent kind:
`claude-cli`, `spacedock_solver`, future) contains exactly the
same top-level key set. Where a key is not applicable to the kind,
the value is `null` (not absent).
Verified by: a unit test enumerates the writer's output keys
across all three agent kinds and asserts they are identical sets;
a schema validator catches future kinds that diverge.

**AC-2 — `claude-cli` kind populates the four spacedock-specific
fields where defensible.** For `claude-cli` kind:
- `solver_workflow_hash`: `null` (no spacedock workflow in this
  agent kind).
- `spacedock_skill_version`: `null` (no spacedock skill in this
  agent kind).
- `harbor_agent_kwargs_hash`: SHA-256 over the
  `AgentConfig.kwargs` dict actually passed to the claude-cli
  adapter (this IS computable).
- `tools_denied`: the DISALLOWED_TOOLS list passed to the harbor
  adapter — empty list `[]` for adapters with no denial set;
  populated for harbor-DAB which carries DAB's denial list.
Verified by: unit test asserts each field's value for a
`claude-cli` claude-haiku spec against a fixture; round-trip
serialization preserves nulls.

**AC-3 — Existing `spacedock_solver` provenance unchanged.**
PKG-22 only adds output for `claude-cli` kind; the existing
spacedock_solver path emits the same field values as before.
Verified by: existing PKG-8 / PKG-15 provenance tests stay green.

**AC-4 — Goal 1 + Goal 2 result docs reference real values.**
After PKG-22 merges and the goal2 matrix re-dispatches, the result
summary at `docs/superpowers/plans/2026-05-19-goal2-haiku-baseline.md`
cites the actual `harbor_agent_kwargs_hash` + `tools_denied` values
from one sampled cell's provenance.yaml.
Verified by: result doc subsection cites a non-null
`harbor_agent_kwargs_hash` from a goal2 cell.

## Test plan

- **Unit:** `tests/unit/test_provenance_freeze_cmd.py` extends with
  cases for AC-1 (cross-kind key parity), AC-2 (claude-cli field
  values), AC-3 (spacedock regression).
- **Integration:** A new test materializes a `claude-cli` spec,
  invokes `rk freeze`, and parses the output provenance.yaml to
  assert the schema is complete.
- **Acceptance:** A live `rk run` of any claude-cli cell produces a
  provenance.yaml with the four fields populated per AC-2.

## Out of scope

- Adding new sealed-input fields beyond what currently exists.
  PKG-22 makes the EXISTING fields uniformly present across kinds;
  schema EXTENSION is separate.
- DAB-specific DISALLOWED_TOOLS enforcement at runtime — that's
  PKG-9 v2's territory.
- Goal 1 / Goal 2 retroactive provenance rewrite — the cells from
  prior dispatches keep their incomplete provenance; only cells
  dispatched after PKG-22 merges get the new field set.

## Depends on

- PKG-8 v2 — `rk freeze` extended (shipped)
- PKG-9 v2 — `tools_denied` field on AgentConfig (shipped)

## Resume hook

After PKG-22 merges, Goal 2's already-dispatched cells (if any)
keep their incomplete provenance — a re-dispatch is needed only if
the captain wants a clean N=1 baseline with the full field set
across all 48 cells. Otherwise, mark Goal 2's AC-2 PASSED with the
caveat that early cells used the old writer.
