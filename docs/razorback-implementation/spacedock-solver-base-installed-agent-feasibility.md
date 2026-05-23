---
id: m2a2q7hrmvzg9ypvc9q6nt2b
title: SpacedockSolverAgent — assess feasibility of extending BaseInstalledAgent (option 2 from ne cycle 3)
status: backlog
source: 2026-05-23 ne cycle-2 finding — harbor's trial runner gates `populate_context_post_run` on `isinstance(self._agent, BaseInstalledAgent)` at `harbor/trial/trial.py:466-471`. `SpacedockSolverAgent` extends `BaseAgent` so harbor only invokes `setup` + `run` + `to_agent_info`; `cleanup()` and `populate_context_post_run()` are both dead code on the outer agent. Captain accepted option 1 (write inside run()) for ne cycle 3 to ship the smoke-gate now, and asked for a follow-up entity to assess whether moving to BaseInstalledAgent is feasible + worth doing.
score: 0.7
auto-approve: false
worktree:
issue:
pr:
mod-block:
started:
completed:
verdict:
---

## Problem

`SpacedockSolverAgent` (the spacedock variant entry point) currently extends harbor's `BaseAgent`. Harbor's trial runner treats `BaseAgent` and `BaseInstalledAgent` differently: only `BaseInstalledAgent` subclasses receive lifecycle hooks like `populate_context_post_run`, `cleanup`, and (likely) others. By extending `BaseAgent`, `SpacedockSolverAgent` participates in a narrower lifecycle than the harbor-installed agents (claude_code, codex, pi, ~20 others) get.

`ne` cycle 2 discovered this when the post-run manifest writer failed to fire from `populate_context_post_run` (cycle-1 reviewer's diagnosis was based on `BaseInstalledAgent` lifecycle, not `BaseAgent`'s narrower one). `ne` cycle 3 shipped option 1 (write the manifest from inside `run()` after the inner-agent call returns) — that works but it's a workaround, not the canonical hook pattern.

This entity asks: would extending `BaseInstalledAgent` give us the canonical lifecycle? What's the surface cost?

## Acceptance criteria

**AC-1 — Surface inventory of `BaseInstalledAgent` vs `BaseAgent`.**
A short report at `docs/razorback-implementation/_evidence/spacedock-solver-base-installed-agent-feasibility-report.md` enumerates: (a) every method/attribute `BaseInstalledAgent` declares beyond `BaseAgent`, (b) every method/attribute `BaseInstalledAgent` makes ABSTRACT vs CONCRETE (so we know what we'd be forced to implement), (c) every lifecycle hook harbor invokes on `BaseInstalledAgent` but NOT on `BaseAgent` (cite `harbor/trial/trial.py` line numbers), (d) the lifecycle ordering across `setup` → `run` → `populate_context_post_run` → `cleanup` → `to_agent_info` calls.
Verified by: report exists; every cited line resolves against pinned `harbor==0.6.6`.

**AC-2 — Concrete migration assessment.**
The report names (a) which `BaseInstalledAgent` abstract methods `SpacedockSolverAgent` would need to implement; (b) which existing `SpacedockSolverAgent` methods would need rewriting; (c) whether harbor's existing `ClaudeCode` / `Codex` `BaseInstalledAgent` subclasses give us a usable shape to mirror; (d) the captain-facing API change footprint (does the spec block's `agent.kind: spacedock_solver` mean anything different? does the `import_path: razorback.agents.spacedock_solver:SpacedockSolverAgent` need to change?).
Verified by: report has a `## Migration cost` section enumerating concrete file diffs (or "no change required") for each item above.

**AC-3 — Recommendation.**
The report ends with a one-line recommendation: (a) yes, migrate to `BaseInstalledAgent` — cost is X, benefit is Y; (b) no, keep `BaseAgent` + option-1 workaround — cost of migration outweighs the canonical-hook benefit; (c) partial — migrate only when X precondition lands. Captain-decision-ready format.
Verified by: report has `## Recommendation` section with a YES/NO/PARTIAL verdict + the load-bearing trade-off cited.

**AC-4 — No code changes.**
This entity is investigation-only. No production source edits. If the recommendation is YES, the actual migration is a sibling entity the captain greenlights based on this report.
Verified by: `git diff main..HEAD -- src/` is empty.

## Test plan

- **Read harbor source:** `harbor/agents/base.py` (find `BaseAgent` + `BaseInstalledAgent`), `harbor/trial/trial.py:400-500` (lifecycle ordering + gating), `harbor/agents/installed/claude_code.py` + `harbor/agents/installed/codex.py` (reference implementations).
- **Read razorback source:** `src/razorback/agents/spacedock_solver.py` (current `BaseAgent` shape), `src/razorback/agents/_runtime/claude.py` `RazorbackClaudeCode` (already a `BaseInstalledAgent` subclass — could be a reference shape, or its inheritance might give us the lifecycle hooks for free if we delegated more).
- **Static comparison:** diff the abstract-method sets via `inspect.getmembers` Python probe.
- **No pytest required** — investigation-only doc entity (legitimate per the workflow README rule for research-spike-shaped work; this is the narrow exception case).

## Out of scope

- **Actually migrating to BaseInstalledAgent.** Sibling entity if the recommendation is YES.
- **Removing the option-1 workaround from `SpacedockSolverAgent.run()`.** Stays until migration ships (if it does).
- **Codex + Pi runtime adapters.** Razorback's codex/pi agents have their own inheritance trees — this entity scopes to the claude runtime.
- **Harbor-side changes.** Razorback can't change harbor's gating; if `BaseInstalledAgent` lifecycle is the constraint we need to migrate to, this entity assesses the cost on the razorback side only.

## Depends on

- **`ne` shipped via option 1** (cycle 3 in flight). Once `ne` lands with the option-1 workaround, this entity assesses whether option 2 is worth the migration.

## Resume hook

When this lands, the captain has a concrete decision: keep the `BaseAgent` + run()-internal-write pattern, or invest in migrating `SpacedockSolverAgent` to `BaseInstalledAgent` for canonical lifecycle hooks. If migration is recommended, file the sibling implementation entity; if not, the option-1 workaround stays as the canonical pattern and the rationale is documented for future maintainers.
