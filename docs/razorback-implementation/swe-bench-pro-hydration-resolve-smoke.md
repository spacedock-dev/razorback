---
id: jryf2ezvxa5s7zpayf9568zz
title: swe-bench-pro — hydration + generic-pass-through resolve smoke
status: backlog
source: docs/superpowers/specs/2026-06-24-swe-bench-pro-on-harbor-design.md (E1); generic-harbor-benchmark-surface-design + spider2-dbt-source-resolution-and-run-wiring as reference; captain directive "use harbor's scale-ai/swe-bench-pro"
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

razorback's generic `kind: harbor` block resolves any published harbor
dataset through `PackageDatasetClient` with no per-benchmark code when
`plugin:` is unset (the dabstep pass-through path, distinct from the
spider2-dbt / ade-bench view-materializer paths). `scale-ai/swe-bench-pro`
should ride that generic path. This entity proves it: a `kind: harbor`
spec with `dataset: scale-ai/swe-bench-pro@<ref>` resolves through
`_build_harbor` (no plugin, no family branch) to one `TaskConfig` per
task, and `rk run --explain` lists them. The fully-qualified
`<org>/<name>@<ref>` form is mandatory — `HarborBenchmarkBlock` rejects a
bare ref at parse time when `plugin is None` (`spec/schema.py:197-249`).

swe-bench-pro is git-repo-based (clone repo at a base commit), so harbor
package hydration is the top feasibility risk: spider2-dbt hit a
`git checkout exit-128` blocker (PKG-40) on the same surface. The live
`harbor download` smoke re-checks that blocker but is **non-gating** —
the ACs gate on a deterministic local fixture so the suite stays
network-free.

`auto-approve: false` — touches the spec/translate surface.

## Acceptance criteria

**AC-1 — A `kind: harbor` / `dataset: scale-ai/swe-bench-pro@<ref>` spec resolves to N task dirs via the generic pass-through (no plugin, no family branch).**
Verified by: an integration test that runs the resolver against a local
`tests/fixtures/swe_bench_pro/` source tree (resolver monkeypatched for
determinism) and asserts each emitted `TaskConfig.path` contains
`task.toml`, and that the swe-bench-pro ref takes the generic
`_build_harbor` branch — NOT any spider2/ade family branch.

**AC-2 — `rk run --explain` on a fixture swe-bench-pro spec lists the resolved tasks.**
Verified by: an in-process `CliRunner` invocation of
`uv run rk run <fixture-spec>.frozen.yaml --explain` (resolver
monkeypatched) exits 0 and prints one task line per fixture instance.

**AC-3 — The qualified-ref contract is enforced; a bare ref is rejected at parse time.**
Verified by: a test asserting `PackageReference`-backed schema validation
accepts `scale-ai/swe-bench-pro@latest` and rejects bare `swe-bench-pro`
when `plugin is None` (`spec/schema.py` qualified-ref validator).

## Test plan

Unit + integration around the generic resolver path, fixture-backed and
network-free (reuse the spider2 resolver-monkeypatch + `CliRunner` seams).
A documented **non-gating** live smoke runs
`uv run harbor download scale-ai/swe-bench-pro@<ref> --export` and records
exit status + task-dir count + the PKG-40-style `git checkout` blocker
status in the validation report. Acceptance command for validation:
`uv run rk run <fixture-spec>.frozen.yaml --explain`.

## Out of scope

Leakage/deny-glob hardening (`swe-bench-pro-leakage-audit-deny-globs`),
the example spec + scoring strata
(`swe-bench-pro-example-spec-scoring-strata`), and the full-dataset score
(deferred goal entity). Whether swe-bench-pro needs a view materializer —
that escalation is owned by the leakage-audit entity, not this one.
