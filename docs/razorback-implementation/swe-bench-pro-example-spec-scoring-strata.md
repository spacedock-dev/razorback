---
id: xrh8vh7pbdzt7h09sfkspwp2
title: swe-bench-pro — example spec + scoring strata confirmation
status: backlog
source: docs/superpowers/specs/2026-06-24-swe-bench-pro-on-harbor-design.md (E3); spider2-dbt-example-spec + harbor-view-task-identity-scored-runs as reference; sibling shape ade-bench-harbor-dataset-codex.yaml
started:
completed:
verdict:
score:
worktree:
issue:
pr:
mod-block:
auto-approve: false
---

## Problem

No user-facing spec demonstrates running swe-bench-pro, and the scoring
path has not been confirmed against swe-bench-pro's project-prefixed task
slugs. This entity adds `examples/specs/swe-bench-pro-codex.yaml`
(`kind: harbor`, `dataset: scale-ai/swe-bench-pro@<ref>`, `kind: codex`
gpt-5.5, SWE-tuned timeout/turn budget, hydration-prereq header note),
mirroring the sibling `ade-bench-harbor-dataset-codex.yaml`, and confirms
`rk score` stratifies the swe-bench-pro slugs sensibly. A full live run is
gated on the hydration blocker (PKG-40-style), so the AC verifies what is
checkable offline (schema-valid + freezes) plus a fixture-backed scoring
test.

Depends on `swe-bench-pro-hydration-resolve-smoke` (the generic resolve
path); overlaps the leakage-audit entity. `auto-approve: false` — touches
the scoring surface and a user-facing example.

## Acceptance criteria

**AC-1 — A `kind: harbor` swe-bench-pro example spec exists and freezes cleanly with a SWE-tuned resource budget.**
Verified by: `uv run rk freeze examples/specs/swe-bench-pro-codex.yaml --allow-missing`
exits 0 and the frozen `benchmark.dataset == "scale-ai/swe-bench-pro@<ref>"`;
the spec sets `override_timeout_sec` / `max_timeout_sec` / `max_turns`
above the 1200s codex default (a `grep` over the spec confirms the tuned
values are present).

**AC-2 — The example records the swe-bench-pro hydration prerequisite for a full run.**
Verified by: `grep -F 'scale-ai/swe-bench-pro' examples/specs/swe-bench-pro-codex.yaml`
returns the `# ABOUTME:` header note naming the harbor-package hydration
step (the PKG-40-style blocker) a live run requires.

**AC-3 — `rk score` stratifies swe-bench-pro's project-prefixed slugs into per-task strata.**
Verified by: a fixture-backed test that runs `rk score` over a synthetic
swe-bench-pro run dir (project-prefixed slugs) and asserts `summary.json`
carries one stratum per task slug with a `stratified_pass_at_1` value —
byte-equal to the `rk score` JSON output.

## Test plan

Offline freeze check (AC-1/AC-2; the live run stays blocked by hydration),
plus a fixture-backed `rk score` test over a synthetic swe-bench-pro run
dir (AC-3) reusing the task-identity scoring surface from
`harbor-view-task-identity-scored-runs`. Acceptance command for
validation: `uv run rk freeze examples/specs/swe-bench-pro-codex.yaml --allow-missing`
+ the scoring test.

## Out of scope

Unblocking the swe-bench-pro harbor-package hydration (externally owned,
re-checked non-gating in `swe-bench-pro-hydration-resolve-smoke`). The
leakage/deny-glob hardening (its own entity). The full-dataset N=1 score
(deferred goal entity). Authoring a swe-tuned solver workflow — deferred
unless the generic `codex-benchmark-solver` underperforms on a live task.
