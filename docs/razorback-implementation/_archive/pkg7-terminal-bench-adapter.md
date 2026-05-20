---
id: 0dymhh6cmhhyfe375yqgzk1v
title: PKG-7 — terminal-bench-2 adapter
status: backlog
source: CL 2026-05-19 — non-data benchmark candidate for custom spacedock solver
started:
completed:
verdict:
score: 0.6
worktree:
issue:
pr:
mod-block:
---

## Problem

terminal-bench-2 (89 tasks, harbor's registry, source
`github.com/laude-institute/terminal-bench-2`) is the pure
non-data benchmark — shell-scripted tasks where the agent
operates a terminal to solve concrete goals (compile X, debug
Y, restore Z). It's the cleanest fit for a custom spacedock
solver: the staged
`understand_task / make_plan / execute / verify` pattern maps
directly onto the agent's natural workflow on terminal tasks.

terminal-bench-2 is already in harbor's bundled registry; just
needs the razorback adapter shape (similar to ade-bench's
git-task fetch path that FU-1 added).

## Unlocks

- Non-data benchmark target for the custom spacedock solver
  (M4 agent).
- A second comparison axis alongside DAB (data-y) and ade-bench
  (data engineering): pure shell-task agentic work.

## Acceptance criteria

**AC-1 — `TerminalBenchBenchmarkBlock` parses specs.**
Verified by: a unit test feeds a spec with
`benchmark.kind: terminal-bench, tasks: [<task-ids>]` and
asserts it parses; unknown keys reject; extra='forbid' holds.

**AC-2 — Razorback's translator fetches terminal-bench-2 tasks
from harbor's registry.**
Verified by: a unit test against a fixture asserts the
translator constructs harbor `TaskConfig` entries with the
correct git_url + git_commit_id from harbor's registry shape
(verified against harbor's bundled terminal-bench dataset
metadata).

**AC-3 — terminal-bench's task.toml has a `docker_image`
that may or may not include claude on PATH. Razorback's
adapter applies the FU-2 image-override pattern by default
(`dab-agent:latest`).**
Verified by: a unit test asserts the image-override applies
unless the spec specifies `benchmark.docker_image_override`
to opt out.

**AC-4 — terminal-bench reward shape passes through to
`summary.json` correctly.**
Verified by: a unit test against a fixture terminal-bench
trial's `result.json` asserts the aggregator emits
`benchmark_kind: terminal-bench, score: <numeric>,
n_trials: <int>, n_completed: <int>, n_errored: <int>` per
PKG-2's errored-vs-completed contract.

**AC-5 — Live `rk run examples/specs/terminal-bench-claude.yaml`
against 1-2 terminal-bench tasks exits 0 with numeric score
+ no token leak in run-dir.**
Verified by: live invocation; `grep -r "$ANTHROPIC_API_KEY"
<run-dir>` returns no matches (PKG-2 AC-1 grep-gate carried
forward); `jq .score <run-dir>/summary.json` returns a
number.

**AC-6 — Carry-forward tests stay green.**
Verified by: `uv run pytest` exits 0.

## Test plan

- **Unit tests:** spec block parsing; registry fetch path;
  image-override applies unless opted out; aggregator shape.
- **Integration test:** 1-2 terminal-bench tasks end-to-end
  through Claude.
- **Acceptance command:** `uv run rk run examples/specs/
  terminal-bench-claude.yaml` exits 0; summary.json has
  numeric score, run-dir grep-clean.

## Out of scope

- Custom spacedock-solver against terminal-bench (separate
  experiment workflow entity, not a harness task).
- Adversarial terminal-bench variants — defer.
