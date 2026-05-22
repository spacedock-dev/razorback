---
id: jpfj5pv1d00zpgtem00q949b
title: commit small experiment artifacts by default (split bulky vs scoring-essential)
status: backlog
source: goal1-resume-spacedock-first 2026-05-22 — `.gitignore: runs/` blanket-ignored per-cell scoring artifacts (KB-scale validation.json, reward_per_query.json, summary.json, provenance.yaml) alongside bulky stuff (dataset tasks/ copies). Worktree teardown destroyed both, leaving nothing committable.
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

Razorback's `.gitignore` blanket-excludes `runs/`, `_runs/`,
`.runs/`. This was reasonable when most run-dir content was
bulky (per-cell task copies, postgres pgdata, agent caches).
After PKG-21's clonefile materialization + PKG-14's bind-mount
discipline, the per-cell scoring artifacts are KB-scale:

- `result.json` (harbor trial outcome — KB)
- `summary.json` (per-trial summary — KB)
- `score.json` (rk score output — KB)
- `reward_per_query.json` (verify_batch.py per-query map — KB)
- `validation.json` (paper-shaped per-query pass map — KB)
- `provenance.yaml` (sealed inputs — KB)
- `audit.json` (rk audit per-cell verdict — KB)
- `manifest.json`, `lock.json`, `per_trial_outcomes.json`,
  `events.jsonl`, `spec.frozen.yaml` (all KB-scale)

12 cells × ~100KB = 1.2 MB. The repo can absorb that. Bulky
artifacts that SHOULD stay gitignored:

- `tasks/` subdirs (per-cell dataset clonefile copies — even
  zero physical bytes via clonefile, the inode/extent metadata
  pollutes git)
- `.harbor-home/`, `.cache_home/` (per-cell HOME overrides)
- Session jsonl traces (per-turn agent capture — can be MB-scale)
- `audit/` raw scan output if voluminous

This entity sharpens the gitignore split so the audit-essential
KB-scale set is committable while bulky stays excluded.

## Acceptance criteria

**AC-1 — Per-cell scoring artifacts are NOT gitignored.**
The following globs are explicitly allowed by `.gitignore`:
- `runs/**/result.json`
- `runs/**/summary.json`
- `runs/**/score.json`
- `runs/**/reward_per_query.json`
- `runs/**/validation.json`
- `runs/**/provenance.yaml`
- `runs/**/audit.json`
- `runs/**/manifest.json`
- `runs/**/lock.json`
- `runs/**/per_trial_outcomes.json`
- `runs/**/spec.frozen.yaml`

Verified by: a unit test runs `git check-ignore -v` against a
fixture path of each shape; none are ignored.

**AC-2 — Bulky artifacts stay gitignored.**
The following globs remain gitignored:
- `runs/**/tasks/`
- `runs/**/.harbor-home/`
- `runs/**/.cache_home/`
- `runs/**/events.jsonl` (per-turn — large)
- `runs/**/agent/sessions/projects/**/*.jsonl` (session captures)

Verified by: same test exercises these and asserts they ARE
ignored.

**AC-3 — Worktree teardown smoke.**
After razorback-runs-outside-worktree ships AND this entity
ships, the smoke test (create worktree → run cell → remove
worktree → re-score from committed artifacts) succeeds at the
RE-SCORE step. Without this entity, the committed artifacts may
still be missing.
Verified by: smoke test from
`razorback-runs-outside-worktree`'s AC-4 with an additional
assertion that the audit-essential file set is present.

**AC-4 — Repo size budget honored.**
The repo's size delta from this change stays under 5 MB per
sprint of typical use (12 cells × 100KB × 4 sprints ≈ 5MB
budget). A CI check warns if a single commit adds >2 MB of
runs/ data.
Verified by: CI workflow runs `git diff --stat` against
runs/ paths and asserts the size delta.

## Test plan

- **Unit:** gitignore behavior per AC-1/AC-2 (using
  `git check-ignore -v`).
- **Integration:** combined smoke test with
  `razorback-runs-outside-worktree`.
- **Acceptance:** a runs/ tree from one Goal 1 cell is
  committable in its scoring subset and pre-existing
  test runs still skip bulky.

## Out of scope

- LFS for session jsonl traces or other large artifacts.
  Separate decision if bulky data becomes load-bearing.
- Retention/rotation policy for runs/. Future entity.
- Per-experiment partitioning under runs/. Future entity.

## Depends on

- `razorback-runs-outside-worktree` (this entity becomes
  meaningful when runs/ lives in user-data; before that, the
  worktree-relative path still gets nuked even if files were
  committable)
- PKG-21 (shipped) — clonefile materialization is what made the
  per-cell tasks/ a "bulky" rather than "irreducible" artifact

## Resume hook

After this entity merges, goal1 re-dispatches will commit their
audit-essential outputs alongside the worktree branch. Worktree
teardown no longer destroys the scoring set.
