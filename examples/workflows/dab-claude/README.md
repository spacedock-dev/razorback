# dab-claude workflow

A spacedock-style experiment workflow that runs a single-shot Claude CLI agent
against the 12-dataset DAB benchmark and produces a verdict + promoted baseline.

## Lifecycle

The workflow stages follow design doc §4:

- **propose** — the operator authors a spec on a worktree branch and validates it
  (`rk validate`, `rk constraints check`, `rk spec freeze`).
- **smoke** — a one-dataset, one-trial override of the spec runs via a dispatched
  run-workflow entity; the operator reads `summary.json` and decides whether to
  advance or fall back.
- **full** — the full 12-dataset spec runs at the production trial count via the
  same run-workflow entity shape; the reconciling stage dispatches make-up `rk run`
  invocations to fill any shortfall against the target trial count.
- **analyze** — the operator resolves a baseline (`rk registry resolve`), then runs
  `rk runs diff` between the baseline and the new run-dir(s).
- **conclude** — if the captain approves promotion, the operator runs
  `rk baseline promote` and the entity archives.

## Files

- `README.md` — this file.
- `stages.md` — declarative stage definitions; each stage names its inputs, outputs,
  and the razorback subcommands it invokes.
- `run-workflow.md` — the inner run-workflow entity (one per smoke / full stage).
  Its `reconciling` stage drives `reconcile_run_workflow` (§2.1, §4).

## How to run

A spacedock first-officer agent reads `stages.md` and dispatches ensigns per stage.
The operator does not invoke this workflow manually; spacedock owns the dispatch
loop. For a one-off manual exercise, see `stages.md` § "Manual mode".

The headline acceptance spec is `examples/specs/dab-dev-claude.yaml` (M5).
