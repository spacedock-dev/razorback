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

## Where do runs go?

This plugin is invoked by `rk run` as a subprocess; it does not write run-dirs
itself. The run-dir location is controlled by `rk run`'s `--runs-dir` flag.
When omitted, `rk run` defaults to `$RAZORBACK_RUNS_DIR` / `$XDG_DATA_HOME/razorback/runs`
/ `~/.local/share/razorback/runs` — outside any git worktree. See the top-level
razorback README for details.
