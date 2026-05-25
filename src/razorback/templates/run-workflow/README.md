---
commissioned-by: spacedock@0.12.1
entity-type: run
entity-label: run
entity-label-plural: runs
id-style: sd-b32
stages:
  defaults:
    worktree: false
    concurrency: 4
  states:
    - name: pending
      initial: true
    - name: reconciling
    - name: completed
      terminal: true
    - name: failed
      terminal: true
---

# Run workflow template

Copy this template into a research repo (e.g. `<research>/runs/`) to
track individual `rk run` invocations. Each run is one entity moving
through `pending → reconciling → completed | failed`. The
experiment-workflow's smoke / full stages dispatch runs against this
template.

No stage-completion-signal mods ship from razorback in the first cut
(spec §5.2): halt-resume's real-mod machinery defers per AC-3.6's
hand-fake note. The reconciling stage is driven by the captain or an
operator-ensign reading `audit.json` + `score.json` directly.

## Stage: pending

A run enters `pending` when `rk run` is invoked. The entity body
carries the resolved spec snapshot (frozen spec + plugin-resolved
args from `rk run --explain`), the target cell (task-id / dataset
slice), and the budget allocated to this run.

- **Inputs:** the frozen spec from the parent hypothesis;
  the task-id or dataset slice; the running budget
- **Outputs:** the run's `runs/<id>/spec.frozen.yaml` snapshot;
  the entity body's `## Plan` block citing the `rk run --explain`
  plan
- **Good:** the run's spec snapshot byte-equal to the parent
  hypothesis's frozen spec; the explain plan resolves cleanly
- **Bad:** dispatching a run whose explain plan disagrees with the
  parent hypothesis's frozen spec; skipping the explain pre-flight

## Stage: reconciling

The run has finished its harbor invocation; the run-dir at
`runs/<id>/` carries the agent's trace, the workspace, and the
verifier output. Reconciling rolls those raw artifacts into the
canonical `audit.json` + `score.json` outputs the parent
experiment's analyze stage consumes.

- **Inputs:** the run-dir's raw artifacts (`events.jsonl`, agent
  sessions, workspace files, verifier output)
- **Outputs:** `runs/<id>/audit.json` (from
  `rk audit --policy strict`) + `runs/<id>/score.json` (from
  `rk score`)
- **Good:** both artifacts produced from a clean checkout of the
  run-dir; the audit verdict surfaces any external-oracle calls
  the agent made; the score reports the canonical lens
- **Bad:** skipping `rk audit --policy strict`; trusting the
  agent's self-report instead of the verifier output

## Stage: completed

Terminal. The run produced `audit.json` + `score.json` cleanly. The
parent experiment's analyze stage reads these files directly. The
entity's `verdict` field is `PASSED`; `completed` is the ISO 8601
timestamp at which reconciling produced both artifacts.

- **Inputs:** `audit.json` + `score.json`
- **Outputs:** `verdict: PASSED`, `completed: <ISO 8601>`
- **Good:** reached `completed` via a real reconciling step;
  parent experiment can promote its full stage on the back of
  this run's outputs
- **Bad:** marking completed before reconciling produced both
  artifacts

## Stage: failed

Terminal. The run failed during harbor invocation, audit, or
score. The entity's `verdict` is `REJECTED`; the entity body's
`## Failure` block names the failure mode:

- **harbor-invocation failure:** container didn't start, agent
  CLI errored, workspace setup failed
- **audit failure:** `rk audit --policy strict` rejected the
  run (external-oracle call, forbidden tool use)
- **score failure:** verifier output malformed; `rk score`
  could not compute a pass rate
- **budget overrun:** `--max-budget-usd-running` cap triggered
  during the run

- **Inputs:** the partial run-dir; the failure event
- **Outputs:** `verdict: REJECTED`, `completed: <ISO 8601>`,
  `## Failure` block in the entity body
- **Good:** the failure mode is named precisely enough for the
  parent experiment's analyze stage to decide whether to retry,
  redesign, or abandon
- **Bad:** marking failed without surfacing the failure mode in
  the entity body
