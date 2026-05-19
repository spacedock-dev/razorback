# dab-claude experiment workflow — stages

Each section below is one stage definition. The operator (an LLM workflow agent)
reads its inputs, runs the named commands, and writes the named outputs.

## propose

**Inputs:** a hypothesis description from the captain.
**Outputs:** a worktree branch with `spec.yaml` + `spec.frozen.yaml` + `provenance.yaml`.

```
uv run rk validate spec.yaml
uv run rk constraints check spec.yaml --constraints @dab-direct
uv run rk spec freeze spec.yaml
```

## smoke

**Inputs:** the frozen spec from propose.
**Outputs:** a smoke run-dir under `_runs/<exp>/<job_name>/`. The operator reads
`summary.json` and gates on a workflow-local tripwire (e.g., stratified_pass_at_1
above 0.1).

The smoke stage dispatches a `run-workflow.md` entity with:

- `spec_path = <propose-output-frozen-spec>`
- `target_trials = 1`
- `datasets_override = [bookreview]` (one-dataset override at this stage)

## full

**Inputs:** the frozen spec from propose.
**Outputs:** one or more full run-dirs (the run-workflow tracks them as a list per §4).

The full stage dispatches a `run-workflow.md` entity with:

- `spec_path = examples/specs/dab-dev-claude.yaml`
- `target_trials = 5` (the DAB N=5 dev-tier default)

## analyze

**Inputs:** the full-stage run-dirs.
**Outputs:** a diff payload + verdict written into the entity body.

```
uv run rk registry resolve baseline @dab-claude-baseline
uv run rk runs diff <baseline-path> <full-run-dir>
```

The operator embeds the diff JSON (or markdown when M6 lands the markdown format)
into the entity body and writes a verdict. AC-6 of M7 ensures this `runs diff`
refuses if the operator accidentally pairs against an ade-bench run-dir.

## conclude

**Inputs:** the entity body's verdict; the captain's promotion mark.
**Outputs:** a promoted baseline directory.

```
uv run rk baseline promote <full-run-dir> --to <baseline-path> --constraints @dab-direct
```

The entity archives.

## Manual mode

To exercise the lifecycle manually (no spacedock first-officer dispatch):

```
# propose
uv run rk validate examples/specs/dab-dev-claude.yaml
uv run rk spec freeze examples/specs/dab-dev-claude.yaml

# smoke (one dataset, one trial)
uv run rk run examples/specs/dab-dev-claude.frozen.yaml --runs-dir _runs

# full (full dev-tier; subject to cost)
uv run rk run examples/specs/dab-dev-claude.frozen.yaml --runs-dir _runs

# analyze
uv run rk registry resolve baseline @dab-claude-baseline
uv run rk runs diff <baseline> <run-dir>

# conclude
uv run rk baseline promote <run-dir> --to <baseline> --constraints @dab-direct
```
