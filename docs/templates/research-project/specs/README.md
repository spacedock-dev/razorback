# Specs

Each spec is one experiment identity. Edit `baseline.yaml` to change
the benchmark, agent, or budget; `rk freeze` resolves model alias +
solver-workflow content hash and writes `baseline.frozen.yaml` +
`provenance.yaml` alongside.

## Authoring hypothesis variants

Copy `baseline.yaml` to `h<NNNN>-<slug>.yaml`, update `experiment:`,
and repoint `solver_workflow:` at the matching
`../solver_workflows/h<NNNN>-<slug>/` directory. Freeze the variant
and run it; `rk diff` against the baseline run-dir gives the paired
delta.
