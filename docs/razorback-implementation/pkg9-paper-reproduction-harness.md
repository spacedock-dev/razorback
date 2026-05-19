---
id: 4tgrp3eberfywrq3bzn2wkn5
title: PKG-9 — Paper-reproduction harness (hints-ON, three workspace-README variants, hardened PreToolUse hook blocking)
status: backlog
source: CL 2026-05-19 — handoff names paper reproduction (opus-4.7 + hints ON × direct-minimal/direct-structured/spacedock × 12 DAB × N=5) as deliverable 1
score: 1.0
started:
completed:
verdict:
worktree:
issue:
pr:
mod-block:
---

## Problem

Razorback today cannot reproduce the dataagentbench paper's published
numbers (spacedock = 0.577, direct-published-baseline = 0.4376;
stratified pass@1 over 12 datasets, hints OFF in the paper but the
deliverable extends to hints ON per CL 2026-05-19). Three pieces of
agent-setup are missing from razorback's DAB adapter:

1. **hints-ON mode.** The paper's setup runs each task twice (hints
   OFF + hints ON) using DAB's `hints/` directory of human-written
   guidance per dataset. Razorback's spec format and prepare path
   have no toggle for this; the agent today never sees the hints.
2. **Three workspace-README variants.** Paper §3 ("Experimental
   Setup") defines `direct-minimal` (terse task statement only),
   `direct-structured` (task + canonical workspace layout
   description), and `spacedock` (task + workspace + the spacedock
   solver's framing prose). Razorback today materializes a single
   README shape that does not correspond exactly to any of the three.
3. **Hardened PreToolUse hook blocking.** dataagentbench's
   `benchmark/run_experiment.py:1531-1549` declares a DISALLOWED_TOOLS
   list (`Bash(pip install datasets*)`, `Bash(pip install
   dataagentbench*)`, `Bash(huggingface-cli login*)`, etc.) that
   prevents agents from short-circuiting the benchmark by downloading
   the reference dataset or the eval tool itself. Razorback's adapter
   does not configure a PreToolUse hook, so an agent can in principle
   `pip install datasets` and bypass the workspace entirely. Without
   this hook, reproducing the paper's numbers is methodologically
   compromised even if everything else matches.

Without all three, the eventual cost-bearing run (~$300-500 Opus
across 12 datasets × 3 variants × N=5) cannot be cited as a paper
reproduction. PKG-9 builds the harness; the run itself stays
out-of-scope (separate captain-gated experiment after PKG-9 +
PKG-2 + PKG-3 all merge).

## Unlocks

- The cost-bearing paper-reproduction run becomes runnable and
  methodologically defensible.
- Provides the apples-to-apples comparison number for razorback's
  spacedock solver vs the published baseline.
- Hardened PreToolUse hook blocking is reusable by every future
  benchmark adapter (not DAB-specific) — ade-bench, HAL, τ-bench
  all benefit.
- hints-ON / three-variant plumbing generalizes to any benchmark
  whose paper exposes a hints corpus or multiple prompt scaffolds.

## Depends on

- **PKG-3** (DAB live DB services + preflight) — required for the
  RUN. Reproduction against degraded-mode dump files is not the
  paper's setup. PKG-9 plan + implementation can begin earlier;
  the actual run waits for PKG-3 merge.
- **PKG-2** (aggregator trustworthiness) — required for the RUN.
  N=5 demands honest errored-vs-completed counting and trial_name
  pairing under retries; PKG-2's silent-drop guard catches the
  failure mode where some trials are quietly dropped from the
  denominator.
- **Reference reading**: `/Users/clkao/git/dataagentbench/docs/paper/
  paper.md` §3, `paper-outline.md`, and `benchmark/run_experiment.py`
  lines 1531-1549 (DISALLOWED_TOOLS) and 1440-2046 (auth +
  variant-selection paths).

## Acceptance criteria

**AC-1 — Razorback spec format carries a `hints: ON|OFF` field
(default OFF) and the prepare path injects DAB's per-task
`hints/{task}.md` into the agent's workspace when `hints: ON`.**
Verified by: a unit test feeds a spec with `hints: ON` for a
bookreview task; the generated workspace includes `hints.md` (or
the paper's exact filename) whose content matches the upstream
`hints/bookreview.md`. A second test with `hints: OFF` asserts the
file is absent.

**AC-2 — Razorback spec format carries a `workspace_variant:
direct-minimal|direct-structured|spacedock` field and the prepare
path materializes the matching README shape.**
Verified by: three unit tests (one per variant) feed the same
bookreview task spec with different `workspace_variant` values
and assert the generated `README.md` content matches the paper's
prescribed structure for that variant. The content cites paper
§3 verbatim where the variant text comes from the paper.

**AC-3 — Razorback's DAB adapter installs a PreToolUse hook config
that denies the dataagentbench DISALLOWED_TOOLS list verbatim from
`benchmark/run_experiment.py:1531-1549`.**
Verified by: a unit test inspects the generated agent settings.json
and asserts the PreToolUse permissions section contains the
DISALLOWED_TOOLS entries (`Bash(pip install datasets*)`,
`Bash(pip install dataagentbench*)`, `Bash(huggingface-cli
login*)`, plus the full upstream list). A second test fires a
mock agent invocation against `pip install datasets` and asserts
the hook denies it.

**AC-4 — Smoke run: a single bookreview task runs end-to-end in
each of the three variants with hints ON, producing a non-degraded
score and a `events.jsonl` whose first agent turn references the
correct README variant.**
Verified by: live invocation
`uv run rk run examples/specs/bookreview-claude-{variant}.yaml
--hints` for each variant (3 runs total; ~$1-3 each at Claude
rates). The run-dir's `events.jsonl` carries an agent message that
quotes a variant-specific README phrase. `summary.json` carries a
real score (not 0.0, not degraded-mode marker).

**AC-5 — Hook-block live probe: the PreToolUse hook actually fires
against a forbidden command during a smoke run.**
Verified by: a smoke run where the agent is prompted (via a fixture
spec) to attempt `pip install datasets`; the `events.jsonl` carries
a `PreToolUse` denial event citing the hook rule. The agent
continues without the dataset — no silent bypass.

**AC-6 — Spec for the full reproduction run exists, parameterized.**
Verified by: a YAML at `examples/specs/paper-reproduction.yaml` (or
sibling) declares the 12 datasets × 3 variants × N=5 grid as a
parameter sweep readable by `rk run`. The spec itself is not
executed under PKG-9 (cost-bearing, separate experiment); only
its parse + validation is exercised under unit test.

**AC-7 — Carry-forward tests stay green.**
Verified by: `uv run pytest` from a clean checkout exits 0 with
all prior tests passing alongside new PKG-9 tests.

## Test plan

- **Unit tests:** hints-ON file injection (with/without); three
  workspace-README variants; PreToolUse hook config generation
  (asserts the verbatim DISALLOWED_TOOLS list); spec parser
  rejects invalid `workspace_variant` values; reproduction-grid
  spec parses and validates.
- **Integration test:** three smoke runs (one per variant) against
  one bookreview task with hints ON. Cost: ~$3-9 total.
- **Hook-block live probe:** one smoke run with a deliberately
  forbidden command in the agent's prompt; assert denial event.
- **Acceptance command:** the three `uv run rk run examples/specs/
  bookreview-claude-{variant}.yaml --hints` invocations from AC-4.

## Out of scope

- **The full 12-dataset × 3-variant × N=5 paper-reproduction run
  itself.** That's a separate captain-gated experiment that lands
  after PKG-9 + PKG-2 + PKG-3 all merge. Cost: ~$300-500 Opus.
- Reproducing the paper's hints-OFF baseline numbers exactly (the
  paper's seeds + model versions may not be perfectly replicable;
  PKG-9 produces a comparable number, not an identical one).
- Extending hints/variant plumbing to non-DAB benchmarks. Different
  adapters; one-at-a-time.
- Pinning the agent's model version for full determinism. PKG-8
  handles plugin pinning more generally.
- Tweaking the workspace-README variants beyond direct quotation
  from paper §3. If the paper text needs cleanup, that's a paper
  PR, not a razorback PR.
