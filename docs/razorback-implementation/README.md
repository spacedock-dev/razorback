---
commissioned-by: spacedock@0.11.2
entity-type: task
entity-label: task
entity-label-plural: tasks
id-style: sd-b32
stages:
  defaults:
    worktree: false
    concurrency: 2
  states:
    - name: backlog
      initial: true
      gate: true
    - name: plan
      gate: true
    - name: implementation
      worktree: true
    - name: validation
      worktree: true
      fresh: true
      feedback-to: implementation
      gate: true
    - name: done
      terminal: true
---

# Razorback implementation arc

Razorback is the Python CLI built on `harbor==0.6.6` that makes
agentic-benchmark research scriptable. This workflow ships razorback
through its seven design-doc tasks (M1..M7) — from a `rk run`
smoke against harbor's bundled `nop` agent all the way to a first DAB
result and a first ade-bench result.

Each task is one entity in this workflow. The entity carries the
acceptance criteria from §8 of the design doc, moves through plan →
implementation → validation in its own worktree, and lands on `main`
via PR review managed by the `pr-merge` mod. The single design doc at
`/Users/clkao/git/dataagentbench/docs/superpowers/specs/2026-05-18-razorback-python-on-harbor.md`
is the source of truth — task bodies cite it rather than redefine
it.

## File Naming

Each task lives as either:

- a flat markdown file `{slug}.md` (default), or
- a folder `{slug}/` containing `index.md` when the task needs
  sibling artifacts (plan documents, validation reports, code-review
  transcripts) that belong alongside the tracker.

Slugs are lowercase, hyphens, no spaces. Example:
`m1-rk-run-nop.md` or `m1-rk-run-nop/index.md`.

## Schema

Every task file has YAML frontmatter. Fields are documented
below; see **Task Template** for a copy-paste starter.

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | 24-character SD-B32 stored ID minted by `status --next-id --id-seed <slug>` |
| `title` | string | Human-readable task name (e.g., "M1 — rk run against nop") |
| `status` | enum | One of: backlog, plan, implementation, validation, done |
| `source` | string | "design §8" for the seeded tasks; otherwise where the task came from |
| `started` | ISO 8601 | When active work began (set at first dispatch off backlog) |
| `completed` | ISO 8601 | When the task reached `done` |
| `verdict` | enum | PASSED or REJECTED — set at validation |
| `score` | number | Priority score, 0.0–1.0 (optional) |
| `worktree` | string | Worktree path while implementation or validation is active, empty otherwise. Sticky across the worktree stages, cleared at terminal merge. |
| `issue` | string | GitHub issue reference (optional cross-reference) |
| `pr` | string | GitHub PR reference (set when a PR is opened for the task branch) |
| `mod-block` | string | Pending mod-declared blocking action, format `{lifecycle_point}:{mod_name}` |

### ID Style

`id-style: sd-b32` — the workflow expects multiple task branches
to be active in parallel (M1's PR review can overlap with M2's
planning). SD-B32 stored IDs reconcile without coordination across
worktrees. Display prefixes start at 2 chars and lengthen if a
collision arises.

## Stages

### `backlog`

A task enters `backlog` when it is first seeded from §8 of the
design doc. The captain decides when to greenlight it for planning;
this is a captain-gated holding stage.

- **Inputs:** The task's acceptance criteria from design §8
- **Outputs:** A seed task file with title, source (`design §8`),
  one-paragraph problem statement, and the acceptance criteria copied
  verbatim from §8 under `## Acceptance criteria`
- **Good:** AC items name end-state artifacts (`spec.frozen.yaml`,
  `summary.json`) rather than stage actions; the body is short enough
  for the captain to triage on sight
- **Bad:** Restating the entire design doc, hand-waving the AC,
  starting design work before the captain greenlights

### `plan`

A task moves to `plan` when the captain approves it for design
work. The work here is to produce a written implementation plan
against the design doc. The plan stays on `main` (no worktree yet) so
it is reviewable independently of the worktree branch.

- **Inputs:** The task body's AC; the design doc; the previous
  task's worktree and validation report if relevant
- **Outputs:** An implementation plan written via the
  `superpowers:writing-plans` skill, committed to `docs/razorback-
  implementation/plans/{slug}.md` on `main` (or as a sibling in the
  entity's folder form). The plan enumerates the modules to touch, the
  TDD checkpoints, and which §-cites govern each step.
- **Good:** Plan steps map 1:1 to AC items; failing tests are written
  first; integration-level mechanism validation comes before
  comprehensive runs (smallest end-to-end exercise of the riskiest
  contract first)
- **Bad:** Re-deriving the design, planning by feature-name instead of
  AC-by-AC, deferring the riskiest contract (e.g., harbor's verifier
  bind-mount) to the end of the plan
- **Plan output scope (flex by AC count):**
  - ≤3 ACs / single-file change → **inline plan**. Plan-stage worker writes
    a short stage report on the entity body itself (no separate
    `plans/{slug}.md` doc). Validation reads the AC list directly.
  - 4+ ACs / multi-subsystem change → **separate plan doc** at
    `docs/razorback-implementation/plans/{slug}.md` per the standard
    flow. AC↔task map table at the top; design-doc §-cites per task.
  - The FO names the size at dispatch time ("tiny task — inline" vs
    "standard — separate doc").

### `implementation`

A task moves to `implementation` once its plan is approved. The
work happens in a dedicated worktree on a feature branch named
`m<N>-<slug>`, driven by the `superpowers:subagent-driven-
development` skill so the implementation does not consume the first-
officer context.

- **Inputs:** The approved plan; the worktree branch
- **Outputs:** The task's deliverable committed to the worktree
  branch — TDD-first (failing test → smallest implementation →
  passing test → refactor), with small atomic commits. A short stage
  report under `## Implementation summary` in the entity body names
  the modules added, the harbor surfaces touched, and any deviations
  from the plan with the design-doc cite that justifies them.
- **Good:** Tests are written before code; small atomic commits;
  deviations from the design are raised with the captain before being
  implemented; the worktree never includes unrelated refactors
- **Bad:** Skipping tests because "it's obvious", batching many
  unrelated changes into one commit, silently redesigning when the
  design seems wrong, leaving the deliverable incomplete for
  validation to finish

### `validation`

A task moves to `validation` after implementation is complete. A
**fresh** agent independently runs the task's acceptance command
from §8, verifies the expected artifacts match the run-dir layout in
§6.3, and runs `superpowers:requesting-code-review` against the
worktree branch. The validator does not write production code — it
checks what was produced.

- **Inputs:** The implementation's stage report; the task's AC;
  the worktree branch
- **Outputs:** A validation report at `docs/razorback-
  implementation/validation/{slug}.md` (or as a sibling in the
  folder-form entity) covering: PASS/FAIL per AC with the exact
  command and output that proves each clause; the code review's
  findings classified as blocking / non-blocking; a gate decision
  (approve to `done` or reject back to `implementation` with concrete
  fixes)
- **Good:** Reproduces each AC's `Verified by:` clause verbatim;
  reports actual command output, not assertions about what should
  happen; runs `uv run pytest` and the acceptance command from a
  clean checkout of the worktree branch
- **Bad:** Trusting the implementation's self-report, skipping AC
  clauses, approving with non-blocking findings unaddressed,
  approving without rerunning the acceptance command

### `done`

Terminal. The task's PR is merged into `main` and the entity is
archived. The `pr-merge` mod watches for the merge and advances the
entity here automatically.

- **Inputs:** A merged PR (tracked via the `pr` field; the `pr-merge`
  mod's startup/idle hooks detect the merge)
- **Outputs:** `completed` set, `verdict: PASSED`, the worktree torn
  down by the mod's terminal-merge step, the entity archived
- **Good:** Reached `done` via a real merge, not a manual flag flip;
  the next task in §8 ordering can start without waiting on
  cleanup
- **Bad:** Marking done before the PR merged; leaving the worktree
  attached after merge

## Acceptance discipline

Each task's body carries a `## Acceptance criteria` section with
the AC clauses transcribed from §8 of the design. The validation
stage's gate decision is bound to those clauses:

- AC items name end-state artifacts (`spec.frozen.yaml`,
  `summary.json`, `events.jsonl`) and the run-dir layout invariants
  from §6.3 — not stage actions
- Each AC carries a `Verified by:` line naming the exact command,
  file path, or test the validator runs to confirm the clause
- `verdict: PASSED` is set only when every AC passes its `Verified
  by:` check

## Workflow State

View the workflow overview:

```bash
/Users/clkao/git/spacedock/skills/commission/bin/status --workflow-dir /Users/clkao/git/razorback/docs/razorback-implementation
```

Find tasks ready for their next stage:

```bash
/Users/clkao/git/spacedock/skills/commission/bin/status --workflow-dir /Users/clkao/git/razorback/docs/razorback-implementation --next
```

## Task Template

```yaml
---
id:
title: M<N> — <short task name>
status: backlog
source: design §8
started:
completed:
verdict:
score:
worktree:
issue:
pr:
mod-block:
---

## Problem

What this task delivers and why it sits where it does in the §8
ordering. One short paragraph — cite the design rather than restate it.

## Acceptance criteria

Each AC names an end-state property of the finished task (an
artifact, a run-dir invariant, an exit code) and how it is verified.

**AC-1 — <End-state property cited from §8>.**
Verified by: <exact command, file path, or test name a validator can
reproduce>.

## Test plan

What tests cover the AC (unit + integration), and which acceptance
command from §8 the validator runs end-to-end.

## Out of scope

What this task deliberately defers to a later task in §8.
```

## Commit Discipline

- Commit status changes at dispatch and stage-merge boundaries
- Commit task body updates when substantive (plan link,
  implementation summary, validation report link)
- Implementation commits land on the worktree branch; merge to `main`
  happens via the `pr-merge` mod after PR review
