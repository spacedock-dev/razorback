---
id: 3sdsaz943qg5mxhb6g598nvf
title: PKG-5 — τ-bench adapter
status: backlog
source: HAL pivot (2026-05-19) — τ-bench is HAL's second canonical benchmark alongside GAIA
started:
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
mod-block:
---

## Problem

HAL's reliability dashboard runs against two benchmarks: GAIA and
τ-bench (airline domain, both `clean` and `original` variants).
GAIA is in harbor's registry today (165 tasks); τ-bench is not.
To produce HAL-comparable reliability scores, razorback needs a
τ-bench adapter that fetches tasks from
`sierra-research/tau-bench` (or wherever HAL's preferred source
lives — check `github.com/steverab/hal-harness` for the canonical
clone).

τ-bench's shape: multi-turn customer-service tool-use scenarios.
The agent talks to a simulated user; success = completing the
customer's task + respecting domain rules. Unlike DAB (one-shot
SQL) or ade-bench (single-task code edits), τ-bench is the
multi-turn-conversation shape — agent harness must handle
back-and-forth.

## Unlocks

- HAL reliability experiments against the second canonical HAL
  benchmark.
- A multi-turn-conversation benchmark target for razorback's
  agent harness (currently DAB/ade-bench are both single-turn-
  ish).

## Acceptance criteria

**AC-1 — `TaubenchBenchmarkBlock` parses τ-bench specs.**
Verified by: a unit test feeds a spec with `benchmark.kind:
taubench, domain: airline, variant: clean, tasks: [<task-ids>]`
and asserts it parses. Variants `clean` and `original` are
both accepted; unknown variant rejects.

**AC-2 — Razorback's translator fetches τ-bench tasks from the
canonical git source (sierra-research/tau-bench or harbor's
registry if HAL has uploaded a derived dataset).**
Verified by: a unit test against a fixture git source (pinned
commit) asserts the translator constructs harbor `TaskConfig`
entries with `git_url` + `git_commit_id` per FU-1's path. The
test does NOT actually clone (uses a local mock); a separate
integration test does the real clone.

**AC-3 — Multi-turn conversation harness: the agent receives the
simulated-user response between turns and writes one
`agent/conversation.jsonl` per trial.**
Verified by: a unit test against a fixture τ-bench task asserts
`agent/conversation.jsonl` contains alternating
{role: "user", role: "assistant"} entries, in execution order,
matching the actual turn structure. (This may already be
supported by harbor's `BaseAgent.run` shape — if so, AC-3 is
a documentation task, not a code task.)

**AC-4 — τ-bench verifier composes the per-domain rules into the
reward.**
Verified by: a unit test against a fixture trial where the
agent broke a domain rule asserts the reward reflects the
violation (likely 0); a second test with a clean trial
asserts a non-zero reward.

**AC-5 — Live `rk run examples/specs/taubench-airline-claude.yaml`
against one real τ-bench task exits 0 with a numeric score in
`summary.json`.**
Verified by: live invocation (cost-bearing, ~$1-2). The
trial reaches `agent.run()`, the conversation flows, the
verifier scores. `n_completed_trials: 1`, score field is
numeric (per PKG-2 AC-1 errored-vs-completed distinction).

**AC-6 — Carry-forward tests stay green.**
Verified by: `uv run pytest` exits 0.

## Test plan

- **Unit tests:** spec block parsing; git-fetch translator;
  conversation.jsonl shape; verifier reward composition.
- **Integration test:** one live τ-bench-airline task end-to-end
  through Claude.
- **Acceptance command:** `uv run rk run examples/specs/
  taubench-airline-claude.yaml` exits 0 with numeric score.

## Out of scope

- The `original` variant if it requires materially different
  prepare/verify shape; ship `clean` first and revisit.
- Full τ-bench reliability run via PKG-4's perturbation
  variants — separate downstream task once PKG-4 + PKG-5 both
  land.
- Cross-domain extension to retail/healthcare/etc. — defer
  until airline reliability score is in hand.
