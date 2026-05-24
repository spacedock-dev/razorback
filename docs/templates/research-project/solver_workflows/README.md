# Solver workflows

Each subdirectory is one solver-workflow README the spacedock-solver
agent loads at trial start. `baseline/` is the scaffold-shipped
starting point. Hypothesis variants are git diffs over this prose.

## Authoring a hypothesis

```bash
$ cp -r solver_workflows/baseline solver_workflows/h0001-<slug>
$ ${EDITOR:-vi} solver_workflows/h0001-<slug>/README.md
$ cp specs/baseline.yaml specs/h0001.yaml
$ sed -i 's|solver_workflows/baseline|solver_workflows/h0001-<slug>|' specs/h0001.yaml
$ ${EDITOR:-vi} specs/h0001.yaml  # update experiment: name
$ rk freeze specs/h0001.yaml --out specs/h0001.frozen.yaml
$ rk run specs/h0001.frozen.yaml --runs-dir runs --max-budget-usd-running runs/_budget.json
$ rk audit runs/<experiment>/<job>/ --policy strict
$ rk diff runs/<baseline-job>/ runs/<h0001-job>/
```

The four required sections in each workflow README
(`## Stages`, `## Reset declaration`, `## External-oracle audit`,
optional `## ROLE prefix`) are load-bearing — the matrix driver's
smoke gates assume their presence. Strip them only if you understand
the downstream consequence.
