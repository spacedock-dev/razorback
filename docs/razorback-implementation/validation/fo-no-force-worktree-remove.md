# Validation Report — first-officer contract: no `--force` worktree remove without untracked-file audit

- Entity: `docs/razorback-implementation/fo-no-force-worktree-remove.md`
- Worktree (razorback): `.worktrees/spacedock-ensign-fo-no-force-worktree-remove`
- Branch (razorback): `spacedock-ensign/fo-no-force-worktree-remove`
- Cross-repo target: `/Users/clkao/git/spacedock/.worktrees/fo-no-force-worktree-remove` on branch `fo-no-force-worktree-remove`, HEAD `4b29a50ec348c6644904ee24d3402245e5d1ee88`
- Plugin mirror: `/Users/clkao/.claude/plugins/marketplaces/spacedock/skills/first-officer/references/first-officer-shared-core.md`
- Date: 2026-05-22
- Verdict: **PASSED**

## Headline

Cross-repo prose entity. Spacedock-side commit `4b29a50e` inserts the new `### Worktree removal safety` subsection into `first-officer-shared-core.md` inside `## Merge and Cleanup` immediately after step 9 (line 233) and before `## State Management` (line 256). Source-tree and installed-plugin copies are bit-identical. AC-3 (smoke test) deferred per the captain-approved plan; not a blocker.

## AC walk

### AC-1 — Contract addition in `first-officer-shared-core.md` (PASS)

**Location check.** In `/Users/clkao/git/spacedock/.worktrees/fo-no-force-worktree-remove/skills/first-officer/references/first-officer-shared-core.md`:

- `## Merge and Cleanup` is at line 215.
- Step 9 (the `git worktree remove {path}` step) is at line 233.
- `### Worktree removal safety` subsection runs lines 235–254.
- `## State Management` follows at line 256.

The subsection lives inside `## Merge and Cleanup`, immediately after step 9, before `## State Management` — matches the plan's targeted insertion site.

**Prose-verbatim check.** The inserted body (lines 235–254) matches the AC-1 spec prose in the entity (entity body lines 167–188) verbatim, including:

- Heading depth `### Worktree removal safety` (line 235).
- Opening paragraph "Use `git worktree remove {path}` (no `--force`). The default mode refuses to delete a worktree with untracked changes — that refusal is the safety net." (lines 237–239).
- Three numbered audit steps with parenthetical `git -C {path} status --short` example (lines 244–251).
- Closing paragraph "The `--force` flag is never default; it is an explicit captain-confirmed bypass." (lines 253–254).

No drift from the spec.

### AC-2 — Skill instructions reflect the contract (PASS, transitively)

The first-officer skill at `/Users/clkao/.claude/plugins/marketplaces/spacedock/skills/first-officer/SKILL.md` already includes `@references/first-officer-shared-core.md`. Per the plan's `### AC-2` discussion, AC-1's edit landing in that file auto-satisfies AC-2 — no separate edit needed. The new subsection loads as part of the shared-core include on next skill invoke.

### AC-3 — Smoke / contract test (SKIPPED, plan-approved deferral)

Plan stage explicitly deferred AC-3 (entity lines 217–233): the contract is prose discipline aimed at FO behavior; an FO simulator would either require heavy Claude Code/Codex sandbox infra (over the bug bar) or restate the prose (no added rigor). The spec itself flagged this AC as optional ("belt-and-braces"). Real acceptance signal comes from the Resume hook — the next FO cleanup session.

Marked **SKIPPED**, not FAILED. Not a gate blocker.

## Bit-identity check (source ↔ plugin mirror)

```
diff -q /Users/clkao/git/spacedock/.worktrees/fo-no-force-worktree-remove/skills/first-officer/references/first-officer-shared-core.md \
        /Users/clkao/.claude/plugins/marketplaces/spacedock/skills/first-officer/references/first-officer-shared-core.md
# exit=0, no output → files identical
```

Running FO sessions and the spacedock worktree branch will load the same prose.

## Code review (prose)

Reviewed lines 235–254 against the surrounding `## Merge and Cleanup` and `## State Management` sections for clarity, grammar, and consistency.

**Clarity:** the imperative voice ("Use", "the FO MUST", "ONLY after the audit pass") matches surrounding step prose (e.g. step 9 uses "Remove the worktree", step 1 uses "Check for registered merge hooks"). The three-step audit procedure is concrete and actionable: each step names a command or decision criterion. The closing reframe ("never default; explicit captain-confirmed bypass") makes the policy unambiguous.

**Grammar:** clean. Em-dash usage (`— that refusal is the safety net`, `— move to a persistent location` analog) matches surrounding shared-core style. No stray articles, agreement issues, or tense slips.

**Consistency with shared-core:**

- Section depth `###` matches the depth pattern used elsewhere for clarifying subsections (e.g. `### Worktree Ownership` at line 262, `### FO Write Scope` at line 268).
- Code-fence backtick usage for `git worktree remove {path}` and `git -C {path} status --short` matches the inline-command style used in steps 1–9 of the parent section.
- The placeholder `{path}` follows the same brace convention as `{slug}`, `{workflow_dir}`, `{branch}` elsewhere in the file.
- Numbered audit steps mirror the numbered cleanup steps (lines 219–233) — same visual rhythm.

**Findings:**

- Blocking: none.
- Non-blocking: none. Prose ships as-is.

## Gate decision

**APPROVE → `done`.**

- AC-1: PASS (subsection present at the correct location; prose verbatim).
- AC-2: PASS (transitively via existing `@references` include).
- AC-3: SKIPPED with captain-approved plan-stage rationale.
- Source ↔ plugin mirror: bit-identical.
- Code review: no blocking findings.

The razorback-side entity has no razorback code to test — its deliverable is the spacedock-side commit `4b29a50e` plus the plugin-mirror sync, both verified present and identical. Per the entity body, the upstream spacedock merge (`fo-no-force-worktree-remove` into spacedock main) is out-of-scope for this razorback entity; the captain can land it out-of-band.
