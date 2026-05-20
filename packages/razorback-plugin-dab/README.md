# razorback-plugin-dab

Harbor benchmark-adapter that emits one task directory per `(dataset, query_id)`
for the 12 upstream DAB datasets. Razorback's `rk run` invokes this plugin as a
subprocess when a spec declares `benchmark.kind: harbor_dab`.

## Install

```
uv sync           # via the razorback workspace root
```

The plugin is a uv-workspace member at `packages/razorback-plugin-dab/` and is
installed into the same venv as razorback.

## CLI

```
razorback-plugin-dab generate --datasets bookreview \
    --data-root /path/to/dataagentbench/data \
    --workspace-variant direct-minimal \
    --out /tmp/dab-tasks

razorback-plugin-dab list        # JSON catalog of 12 datasets
razorback-plugin-dab validate    # schema-check an emitted task tree
```

## Hydration prerequisite (AC-9)

The plugin enforces a clean missing-dataset error rather than auto-hydrating.
If `<data_root>/query_<name>/` contains LFS pointer files (130-150 byte stubs),
`generate` exits with code 2 and a stderr message of the form:

```
razorback-plugin-dab: dataset <name> not hydrated, found LFS pointer at <path>.
Hydrate with:
  cd <data_root> && git lfs pull
```

Run the hydrate command, then re-invoke `generate`.
