---
id: zkn663pcbvd5sbaaxwx5f1z5
title: swe-bench-pro — leakage audit + deny-globs (gold/test patch isolation)
status: backlog
source: docs/superpowers/specs/2026-06-24-swe-bench-pro-on-harbor-design.md (E2); spider2-dbt-source-resolution-and-run-wiring deny-glob precedent (SPIDER2_DBT_DENY_GLOBS)
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

SWE-bench tasks ship the **gold patch and the test patch** alongside the
repo checkout. If a resolved swe-bench-pro task workspace exposes either
pre-solve, the agent can read the answer — a leakage hole that invalidates
the score. This entity probes what a resolved swe-bench-pro workspace
actually exposes, then closes any hole: swe-specific deny-globs plus a
negative leakage test, mirroring the `SPIDER2_DBT_DENY_GLOBS` work where a
planted forbidden file proved a real top-level-dir glob hole.

Escalation hook: if deny-globs cannot strip the gold/test patch (e.g. it
lives inline in `task.toml` or the verifier metadata rather than as a
sibling file), this entity surfaces "swe-bench-pro needs a view
materializer" (the spider2/ade family pattern) as a **captain decision** —
it does not silently redesign.

Depends on `swe-bench-pro-hydration-resolve-smoke` (needs a resolved
workspace shape to probe). `auto-approve: false` — touches the
leakage/audit security surface.

## Acceptance criteria

**AC-1 — The resolved swe-bench-pro workspace exposes no gold-patch / test-patch / FAIL_TO_PASS answer content to the agent.**
Verified by: a test that materializes/resolves the fixture swe-bench-pro
task and asserts `rg -l 'gold|golden|test_patch|FAIL_TO_PASS|PASS_TO_PASS'`
over the agent-visible workspace returns no answer-bearing matches
(provenance/manifest files that merely record checksums are excluded by
path, as in the spider2 precedent).

**AC-2 — A negative leakage test fails when the deny set is reverted.**
Verified by: a test that plants gold-patch-shaped files
(`gold.patch`, `test_patch.diff`, an `expected/` dir) in a fixture task
and asserts they are excluded from the agent-visible workspace; reverting
the swe-bench-pro deny-globs makes the test FAIL (load-bearing proof).

**AC-3 — `rk audit` flags swe-bench-pro gold-patch leakage if it reaches a trace.**
Verified by: `uv run rk audit <fixture-run-dir> --policy strict --format json`
reports a finding when a trace references planted gold-patch content, and
clean otherwise. (If `rk audit` already covers this generically, the test
asserts that and no new signature is added — confirm, don't duplicate.)

## Test plan

Probe-then-harden: a probe test/script records the real workspace shape
(committed as evidence), then unit tests around the deny-globs and a
negative leakage test (plant → assert excluded → revert → assert leaks).
An `rk audit` test confirms the strict policy catches planted gold-patch
content. All fixture-backed and network-free. Acceptance command for
validation: `uv run pytest tests/ -k swe_bench_pro_leak` (or the suite the
plan names) + the `rk audit` command above.

## Out of scope

The example spec + scoring strata
(`swe-bench-pro-example-spec-scoring-strata`) and the full-dataset score.
Building the view materializer itself — if the probe shows one is needed,
this entity surfaces the captain decision and a follow-up entity owns the
build; this entity does not build it unless the captain greenlights the
scope widen.
