# run-workflow — dispatched per smoke / full stage (§2.1)

A run-workflow entity has the inner-loop stages from §2.1:

`pending → reconciling → completed | failed`

## Frontmatter shape

```yaml
---
status: pending           # or: reconciling | completed | failed
spec_path: <abs-path>     # the frozen spec to run
target_trials: <int>      # the make-up reconciliation target (§4)
runs_dir: <abs-path>      # the runs base directory
runs: []                  # filled in by the reconciling stage
---
```

## pending

The entity body is empty. The first-officer dispatches an ensign to the
reconciling stage.

## reconciling

The ensign invokes razorback's `reconcile_run_workflow` driver, which dispatches
make-up `rk run` calls until accumulated trials >= target_trials (or the iteration
cap is hit). Each new run-dir is appended to the entity's `## Runs` section.

```
uv run python -c "
from pathlib import Path
from razorback.runtime.reconcile import reconcile_run_workflow
result = reconcile_run_workflow(
    entity_path=Path('${ENTITY}'),
    target_trials=${TARGET},
    spec_path=Path('${SPEC}'),
    runs_dir=Path('${RUNS_DIR}'),
    max_iterations=5,
)
print(result)
"
```

When `result['target_met']` is true the entity advances to `completed`. Otherwise
it advances to `failed` and the outer experiment workflow decides whether to
back off or escalate.

## completed

Terminal stage. The entity body's `## Runs` section is the authoritative list of
run-dirs the outer workflow's analyze stage consumes.

## failed

Terminal stage. The body carries the exception text (the `RuntimeError` from
`reconcile_run_workflow`).
