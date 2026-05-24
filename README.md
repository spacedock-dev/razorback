# Razorback

Razorback is a Python CLI for reproducible agentic benchmark research
on top of Harbor. It turns benchmark runs into defensible numbers:
freeze the spec, run the job, score the result, audit for leakage, and
inspect run-dir artifacts.

## What Is Here

- `rk freeze` pins runtime inputs into a frozen spec and provenance.
- `rk run` translates a frozen Razorback spec into a Harbor job and
  writes canonical run-dir artifacts.
- `rk score` computes pass@1, Wilson intervals, and stratified
  summaries.
- `rk audit` scans traces for forbidden data acquisition and coverage
  gaps.
- `razorback-plugin-dab` emits Harbor task directories for
  DataAgentBench.
- `spacedock_solver` is the sealed Spacedock first-officer solver wrapper
  for runtime adapters such as Claude and Codex.

## Layout

```text
src/razorback/                 core CLI, agents, provenance, scoring, audit
packages/razorback-plugin-dab/ DAB task generator plugin
examples/specs/                example and matrix specs
examples/drivers/              matrix dispatch and aggregation scripts
examples/solver_workflows/     solver workflow READMEs
docs/razorback-implementation/ active Spacedock implementation workflow
tests/                         unit and integration tests
```

## Setup

```bash
uv sync
uv run pytest
```

DAB data is external to this repo. Point specs at the local
DataAgentBench data checkout for the machine running the benchmark.

## Common Commands

```bash
uv run rk freeze examples/specs/bookreview-claude-harbor-dab.yaml
uv run rk run examples/specs/bookreview-claude-harbor-dab.frozen.yaml --explain
uv run rk run examples/specs/bookreview-claude-harbor-dab.frozen.yaml --runs-dir runs/smoke
uv run rk score <run-dir> --format json
uv run rk audit <run-dir> --policy strict --format json
```

## Where do runs go?

`rk run` writes one run-dir per `(spec, job)` under a base "runs-dir":

- **Default**: `$RAZORBACK_RUNS_DIR` if set; else `$XDG_DATA_HOME/razorback/runs`
  if set; else `~/.local/share/razorback/runs`.
- **Override**: pass `--runs-dir <path>` to `rk run`.

The default lives OUTSIDE your git worktree on purpose: `git worktree remove
--force` cannot destroy experiment outputs written there. If you pin a
worktree-relative path (`--runs-dir _runs`, `--runs-dir runs/`) the outputs
share the worktree's fate.

## Current Direction

The active goal is to produce N=1 full-dataset benchmark numbers for
DAB and ade-bench using Codex. The first dependency is implementing
the Codex runtime adapter for `spacedock_solver`; DAB and
ade-bench score matrices build on that surface.
