---
id: z52n4f55c4be6sta05h1gmbn
title: first-officer contract — no `--force` worktree remove without untracked-file audit
status: backlog
source: goal1-resume-spacedock-first 2026-05-22 — FO ran `git worktree remove --force` at entity terminal cleanup; destroyed gitignored runs/ artifacts (per-cell validation.json, reward_per_query.json, session jsonl, freeze trees). The `--force` flag was needed because untracked files existed — that was a signal the FO ignored.
started:
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
mod-block:
---

## Problem

The first-officer contract at `.../first-officer-shared-core.md`
documents worktree cleanup at terminal:

> "Remove the worktree (`git worktree remove {path}`) and delete
> the local branch (`git branch -d {branch}`)."

In practice, the FO routinely needs `--force` because
worktree-relative gitignored content (notably `runs/`) leaves
untracked files. `git worktree remove` without `--force` refuses
to delete a worktree with untracked changes — that refusal IS
the safety net. Adding `--force` overrides the safety net.

For razorback specifically, the `runs/` content under the
worktree IS the experiment deliverable. Destroying it on FO
cleanup is the opposite of what the workflow should do.

This entity adds a contract clause that requires the FO to
audit untracked files before forcing a worktree removal.

## Acceptance criteria

**AC-1 — Contract addition in `first-officer-shared-core.md`.**
The `## Merge and Cleanup` section gets a new subsection:

> ### Worktree removal safety
>
> Use `git worktree remove {path}` (no `--force`). The default
> mode refuses to delete a worktree with untracked changes —
> that refusal is the safety net.
>
> If `git worktree remove` fails because untracked files
> exist, the FO MUST:
> 1. Audit those files (`git -C {path} status --short` from the
>    parent worktree).
> 2. Decide per file: commit to the worktree branch (if
>    audit-essential per repo's gitignore policy), move to a
>    persistent location (if experiment-output that belongs
>    outside the worktree), or explicitly confirm destruction
>    with the captain.
> 3. ONLY after the audit pass, `--force` is permitted.
>
> The `--force` flag is never default; it is an explicit
> captain-confirmed bypass.

Verified by: the section exists in the shared core; a code
review confirms the prose.

**AC-2 — Skill instructions reflect the contract.**
The `spacedock:first-officer` skill content (or the relevant
runtime adapter) references this section so the FO loads the
discipline at session start.
Verified by: the skill content has a reference to the new
subsection.

**AC-3 — Smoke / contract test (optional).**
A test fixture creates a worktree with untracked files, asserts
that `git worktree remove` (no `--force`) fails, then runs an
FO simulator that responds correctly per the new contract.
Verified by: test exists and passes. Optional because the
contract is prose discipline; the test is belt-and-braces.

## Test plan

- **Documentation review:** the contract addition is technically
  clear, grammatically clean, and consistent with surrounding
  shared-core prose.
- **Integration (optional):** the FO simulator test from AC-3.
- **Acceptance:** the next session that touches worktree cleanup
  follows the new discipline.

## Out of scope

- Auto-archival of audit-essential untracked files. The contract
  enforces discipline; mechanism for moving files is separate.
- Tooling to discover "audit-essential" gitignored files at the
  worktree (could be in razorback or spacedock; out of scope
  for THIS contract change).

## Depends on

- spacedock framework's first-officer-shared-core.md is owned
  by spacedock-dev; this entity may need a parallel PR to that
  repo OR a razorback-side override.

## Resume hook

After this entity merges, future FO sessions automatically use
the audit-before-force discipline. Combined with
`razorback-runs-outside-worktree` and
`commit-small-artifacts-by-default`, the experiment-destruction
failure mode is closed structurally.
