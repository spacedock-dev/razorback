---
id: z52n4f55c4be6sta05h1gmbn
title: first-officer contract — no `--force` worktree remove without untracked-file audit
status: plan
source: goal1-resume-spacedock-first 2026-05-22 — FO ran `git worktree remove --force` at entity terminal cleanup; destroyed gitignored runs/ artifacts (per-cell validation.json, reward_per_query.json, session jsonl, freeze trees). The `--force` flag was needed because untracked files existed — that was a signal the FO ignored.
started: 2026-05-22T23:11:16Z
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

## Implementation plan (inline, tiny task)

3 ACs, mostly prose. Per `docs/razorback-implementation/README.md`
plan-size rule, this is inline; no separate `plans/{slug}.md`.

### Decision: cross-repo edit vs razorback-side override

**Recommendation: cross-repo edit to spacedock's
`first-officer-shared-core.md` (path B), not a razorback-side
override (path A).**

Tradeoffs:

- **Path A — razorback-side override** (new
  `/Users/clkao/git/razorback/CLAUDE.md` or `.claude/`
  augmentation that the FO loads after the spacedock skill).
  - Pros: ships entirely in this repo; no second-repo PR.
  - Cons: (1) razorback has no such surface today
    (no `CLAUDE.md`, no `.claude/`) — adding one introduces a
    new load-order contract that the FO doesn't actually
    follow today; (2) the spec for FO behavior would split
    across two repos, so the *next* FO contract change has
    to remember to check razorback-side overrides too;
    (3) the failure mode (force-remove destroys runs/) is
    not razorback-specific — any workflow with gitignored
    deliverables hits it. Fix belongs in the shared core.
- **Path B — direct edit to spacedock's shared-core**
  (`/Users/clkao/git/spacedock/skills/first-officer/references/first-officer-shared-core.md`,
  plus the mirrored copy at
  `/Users/clkao/.claude/plugins/marketplaces/spacedock/skills/first-officer/references/first-officer-shared-core.md`).
  - Pros: one canonical location; loaded by every FO via the
    existing `@references/first-officer-shared-core.md` line
    in `skills/first-officer/SKILL.md`; AC-2 is auto-satisfied
    (the skill already `@`-includes the file we're editing);
    fix is general, not workflow-specific.
  - Cons: spacedock is a separate git repo. Captain has
    authority to merge locally this sprint, which makes the
    cross-repo edit shippable in-session; an upstream PR
    follows out-of-band.

Choose **path B**. The implementation stage commits the edit
to spacedock's repo on a feature branch (FO/captain's normal
worktree flow there), then mirrors to the installed-plugin
copy so the running session also sees the new prose without
a plugin reinstall.

### AC-1 — exact prose to add to `first-officer-shared-core.md`

**Target location:** insert a new `### Worktree removal safety`
subsection inside `## Merge and Cleanup`, immediately after
step 9 (line 233 in current shared-core), before
`## State Management` (line 235). The subsection precedes
nothing structural — it is a clarification of step 9.

**Exact prose to insert** (copy from AC-1 in the spec, verbatim,
with the section header at the same `###` depth):

```markdown
### Worktree removal safety

Use `git worktree remove {path}` (no `--force`). The default
mode refuses to delete a worktree with untracked changes —
that refusal is the safety net.

If `git worktree remove` fails because untracked files
exist, the FO MUST:

1. Audit those files (`git -C {path} status --short` from
   the parent worktree).
2. Decide per file: commit to the worktree branch (if
   audit-essential per repo's gitignore policy), move to a
   persistent location (if experiment-output that belongs
   outside the worktree), or explicitly confirm destruction
   with the captain.
3. ONLY after the audit pass, `--force` is permitted.

The `--force` flag is never default; it is an explicit
captain-confirmed bypass.
```

**Why this position:** step 9 of `## Merge and Cleanup` is the
exact step that runs `git worktree remove`. The safety
subsection sits adjacent so the FO reading the procedure
hits the warning at the same moment they're about to run the
command.

### AC-2 — skill-content reference attachment

`spacedock:first-officer`'s SKILL.md already includes
`@references/first-officer-shared-core.md` (line 18). The
new subsection is loaded automatically by that include — no
additional reference is required.

**Verification:** grep
`/Users/clkao/git/spacedock/skills/first-officer/SKILL.md`
for the `@references/first-officer-shared-core.md` line.
AC-2 is satisfied transitively by AC-1's edit landing in
that file.

No edit to `SKILL.md`, `agents/first-officer.md`, or the
runtime adapters is needed. (If validation insists on an
explicit cross-link, the minimal add is a `(see "Worktree
removal safety" below)` parenthetical after step 9's
sentence — but the inline subsection is the more discoverable
location.)

### AC-3 — smoke test in/out call

**Defer (mark out of scope for this entity).**

Reason: the contract is prose discipline aimed at the FO
agent's behavior, not at executable code. An "FO simulator"
test would require either (a) standing up a Claude
Code/Codex sandbox that loads the skill and exercises the
cleanup path — heavy infrastructure for one-time validation
— or (b) writing a placeholder script that re-asserts what
the prose already says, which adds maintenance burden
without raising the bug bar. The spec itself flags this AC
as optional ("belt-and-braces").

The next session that touches worktree cleanup (per the
Resume hook above) provides the real acceptance signal: did
the FO read the new subsection and follow it? That is the
correct integration test, run for free by normal usage.

### Stage-by-stage path

1. **plan** (this stage): produce this inline plan, commit
   to main on razorback. No worktree.
2. **implementation**: dispatch to the spacedock repo
   (`/Users/clkao/git/spacedock`). Worker creates a worktree
   under spacedock's git, edits
   `skills/first-officer/references/first-officer-shared-core.md`,
   commits, and mirrors the change to
   `/Users/clkao/.claude/plugins/marketplaces/spacedock/skills/first-officer/references/first-officer-shared-core.md`
   so the running session loads the updated prose on next
   skill invoke. Worktree on spacedock; razorback main stays
   clean.
3. **validation**: docs review — confirm the subsection is
   technically clear, grammatically clean, and consistent
   with surrounding shared-core prose. No code-level tests
   (per AC-3 defer above).
4. **terminal**: captain merges spacedock-side change (no-ff
   per sprint authority); razorback entity moves to
   `_archive/` with `verdict=PASSED`. Upstream spacedock PR
   filed out-of-band if desired.

### Riskiest contract (validate first)

The risky bit is **which `first-officer-shared-core.md` the
running FO actually loads**. Spacedock keeps two copies:
the source tree at `/Users/clkao/git/spacedock/...` and the
installed-plugin copy at
`/Users/clkao/.claude/plugins/marketplaces/spacedock/...`.
The implementation stage MUST update both (or confirm one is
a symlink to the other; quick `ls -la` check at the start of
the implementation stage settles it). This is the smallest
end-to-end mechanism check — pay that bill first, then write
the prose.

## Stage Report: plan

- DONE: Decide and document: cross-repo edit to spacedock's first-officer-shared-core.md vs razorback-side override (entity body flags this as open). Recommend the path and cite tradeoffs.
  Path B (cross-repo edit) recommended; razorback has no override surface and the fix is not workflow-specific. See "Decision" subsection.
- DONE: Inline plan in entity body specifies the exact prose for AC-1 (the new ### Worktree removal safety subsection) and where AC-2's skill-content reference attaches.
  AC-1 prose copied verbatim with insertion target named (after step 9 of `## Merge and Cleanup`, before `## State Management`). AC-2 attachment is the existing `@references/first-officer-shared-core.md` line in `skills/first-officer/SKILL.md` — auto-satisfied by AC-1.
- DONE: AC-3 in/out call: include the optional FO-simulator smoke test or defer. Name reason.
  Deferred. Contract is prose discipline; an FO simulator either requires heavy sandbox infra or restates the prose. Real acceptance signal comes from the next FO session per the Resume hook.

### Summary

Inline plan recommends a cross-repo edit to spacedock's `first-officer-shared-core.md` (path B) over a razorback-side override (path A): razorback has no override surface and the failure mode is not razorback-specific. AC-1's exact prose and insertion target are pinned (new `### Worktree removal safety` subsection inside `## Merge and Cleanup`, after step 9). AC-2 is auto-satisfied by the existing `@references/first-officer-shared-core.md` include in the first-officer skill. AC-3 (FO simulator smoke test) is deferred — the Resume hook's next-session check is the right acceptance signal. Implementation stage's riskiest-first task: update both the spacedock source tree and the installed-plugin mirror so the running session loads the new prose.
