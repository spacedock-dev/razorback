---
id: xrh8vh7pbdzt7h09sfkspwp2
title: swe-bench-pro — example spec + scoring strata confirmation
status: backlog
source: docs/superpowers/specs/2026-06-24-swe-bench-pro-on-harbor-design.md (E3); spider2-dbt-example-spec + harbor-view-task-identity-scored-runs as reference; sibling shape dabstep-claude-harbor.yaml (spacedock_solver + solver_workflow)
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
slugs. This entity adds
`examples/specs/swe-bench-pro-spacedock-codex.yaml` and confirms the
view-manifest-driven aggregator
(`src/razorback/runs/aggregate.py:_resolve_stratum_from_task_view_manifest`)
stratifies the swe-bench-pro slugs. A full live run is gated on the
hydration blocker (PKG-40-style), so AC-1/AC-2 verify what is checkable
offline (schema-valid + freezes) and AC-3 uses a fixture-backed scoring
run.

The agent block MUST be `kind: spacedock_solver` / `runtime: codex` to use
a solver workflow: `CodexAgentBlock` (`src/razorback/spec/schema.py:49-89`)
has no `solver_workflow` or `max_turns` fields — those live only on
`SpacedockSolverAgentBlock` (`schema.py:92-119`). Mirror the dabstep smoke
spec (`examples/specs/dabstep-claude-harbor.yaml`), swapping `runtime:
codex` + the `codex-benchmark-solver` workflow.

Depends on `swe-bench-pro-hydration-resolve-smoke` (the materializer
wiring); overlaps the leakage entity. `auto-approve: false` — touches the
scoring surface and a user-facing example.

## Acceptance criteria

**AC-1 — A `kind: harbor` swe-bench-pro example spec exists, is schema-valid with a `spacedock_solver`/`runtime: codex` agent and SWE-tuned budget, and freezes cleanly.**
Verified by: `uv run rk freeze examples/specs/swe-bench-pro-spacedock-codex.yaml --allow-missing`
exits 0 and the frozen `benchmark.dataset == "scale-ai/swe-bench-pro@<ref>"`;
`grep -E 'kind: spacedock_solver|runtime: codex|max_turns|override_timeout_sec'`
over the spec confirms the valid agent shape and a `max_turns` /
`override_timeout_sec` above the 1200s codex default.

**AC-2 — The example records the swe-bench-pro hydration prerequisite for a full run.**
Verified by: `grep -F 'scale-ai/swe-bench-pro' examples/specs/swe-bench-pro-spacedock-codex.yaml`
returns the `# ABOUTME:` header note naming the harbor-package hydration
step (the PKG-40-style blocker) a live run requires.

**AC-3 — The aggregator stratifies swe-bench-pro task slugs into per-task query cells.**
Verified by: a fixture-backed test that builds a synthetic run dir with
per-task `view_manifest.json` sidecars
(`benchmark_kind=swe-bench-pro`, distinct `benchmark_task_id` slugs),
**realistic long swe-bench-pro trial-dir names**, and non-null
`rewards["reward"]`, runs `aggregate_summary`
(`src/razorback/runs/aggregate.py:526-563`), and asserts `summary.json`'s
`swe-bench-pro` dataset stratum carries one query cell per task slug. The
test MUST exercise the real manifest-join key — the aggregator matches a
trial to its view by `trial_dir.name.split("__")[0] ==
view_dir_name[:32].rstrip("_-")` (`aggregate.py:_resolve_stratum_from_task_view_manifest`,
~:131-153), so long slugs that collide or truncate at 32 chars must still
land in distinct cells, not the `dataset="default"` collapse at
`aggregate.py:414-418`. `rk score`'s separate `score_version`/`strata`
JSON surface (`cli/score.py:122-125`) is NOT conflated with `summary.json`.

## Test plan

Offline freeze check (AC-1/AC-2; the live run stays blocked by hydration),
plus a fixture-backed `aggregate_summary` test over a synthetic
swe-bench-pro run dir with view-manifest sidecars (AC-3), reusing the
task-identity scoring surface from `harbor-view-task-identity-scored-runs`.
Acceptance command for validation:
`uv run rk freeze examples/specs/swe-bench-pro-spacedock-codex.yaml --allow-missing`
+ the aggregator test.

## Out of scope

Unblocking the swe-bench-pro harbor-package hydration (externally owned,
re-checked non-gating in `swe-bench-pro-hydration-resolve-smoke`). The
leakage/deny-glob hardening (its own entity). The full-dataset N=1 score
(deferred goal entity). Authoring a swe-tuned solver workflow — the
existing `codex-benchmark-solver` is the starting point; deferred unless it
underperforms on a live task.
