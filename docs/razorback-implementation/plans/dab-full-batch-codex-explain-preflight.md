# DAB Full Batch Codex Explain Preflight Implementation Plan

**Entity:** `docs/razorback-implementation/dab-full-batch-codex-explain-preflight.md`

**Goal:** Produce explain-only evidence for the full DAB batch Codex launch shape before any scored run. The intended launch is the Goal 3 Codex DAB shape: `agent.kind: spacedock_solver`, `runtime: codex`, `model: gpt-5.5`, `reasoning_effort: xhigh`, DAB `workspace_variant: spacedock`, `query_mode: batch`, and N=1 over all 12 datasets from `dataset: dab@1.0`.

**Boundary:** This is a preflight/probe task. It may freeze a spec and run `rk run --explain --explain-format json`, which performs normal preflight and may materialize DAB task views. It must not invoke Harbor, must not write `_job_config.yaml`, must not run Codex, and must not run `rk score` or `rk audit`.

**Spec cites:** v2 spec §3.2 (`rk run` surface), §4.2-4.3 spacedock solver shape, §6.1 benchmark dataset definitions and DAB `dataset: dab@1.0`, §6.2 agent block, §6.3 validation, §7.1 run-dir artifacts, §8.1 `rk run` pass-through boundary, §8.2 freeze provenance, §8.4 runtime adaptation.

## AC to Task Map

| AC | Governing cites | Tasks | Evidence |
| --- | --- | --- | --- |
| AC-1 - The full DAB batch spec resolves through dataset definitions. | v2 spec §6.1, §6.3 | T0, T1, T3 | Dataset definition reports `dab@1.0`, 12 datasets, 54 query IDs; explain JSON has `benchmark.dataset: dab@1.0`, `query_mode: batch`, `prompt.task_count: 12`, and task paths for all definition datasets. |
| AC-2 - Batch mode and Codex solver settings are explicit. | v2 spec §4.2-4.3, §6.2, §8.4 | T1, T2, T3 | Explain JSON inspection proves solver variant `spacedock-workflow`, `agent.spec_kind: spacedock_solver`, `agent.runtime: codex`, `agent.model: gpt-5.5`, `harbor_agent_kwargs.reasoning_effort: xhigh`, and prompt mode `spacedock-codex-first-officer`. |
| AC-3 - Explain mode does not launch Harbor or the model. | v2 spec §3.2, §7.1, §8.1 | T3, T4 | Explain JSON has `explain_only: true`; filesystem inspection proves no `_job_config.yaml`, no `trials/`, no `result.json`, no `summary.json`, no `events.jsonl`, no `score.json`, and no `audit.json` under the explain run dir. |
| AC-4 - The next launch command and blockers are recorded. | v2 spec §3.2, §7.1 | T5 | Final report records the green full-run command or a blocker class with failing command and stderr/log path. |

## Target Spec

Use one run-local preflight spec instead of the existing Goal 1 per-cell specs. This proves the full DAB definition path in a single `rk run` translation: `benchmark.dataset: dab@1.0` with no `benchmark.datasets` subset means the DAB plugin definition supplies all 12 datasets.

Create this file during implementation at `_runs/dab-full-batch-codex-explain-preflight/specs/dab-full-batch-codex-spacedock.yaml`:

```yaml
version: 1
experiment: dab-full-batch-codex-gpt55-xhigh-spacedock
agent:
  kind: spacedock_solver
  runtime: codex
  model: gpt-5.5
  sampling:
    temperature: 0.0
    top_p: null
    seed: 1
  solver_workflow: ./examples/solver_workflows/codex-benchmark-solver
  spacedock_skill_version: "1.0.0"
  max_turns: 200
  tools_allowed: []
  tools_denied: []
  reasoning_effort: xhigh
benchmark:
  kind: harbor_dab
  dataset: dab@1.0
  workspace_variant: spacedock
  hints: true
  query_mode: batch
trials: 1
concurrency:
  trials: 1
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
```

If a reviewed canonical spec already exists by implementation time and matches this shape byte-for-byte in the fields above, use it instead and record its path. Do not use `benchmark.data_root` as the identity path; the data root is only a machine-local materialization input supplied through `DATAAGENTBENCH_DATA_ROOT`.

## Surface Map

| Path | Action |
| --- | --- |
| Python implementation modules | No changes. This task is evidence generation only. |
| `_runs/dab-full-batch-codex-explain-preflight/specs/` | Run-local preflight spec, frozen spec, and freeze sidecar. Gitignored scratch. |
| `_runs/dab-full-batch-codex-explain-preflight/runs/` | Run-local explain run dir containing materialized task views only. Gitignored scratch. |
| `docs/razorback-implementation/_evidence/dab-full-batch-codex-explain-preflight.json` | Commit if small enough for review; otherwise commit a normalized field-extraction JSON and cite the raw artifact path plus SHA256. |
| `docs/razorback-implementation/_evidence/dab-full-batch-codex-explain-preflight.md` | Commit the concise preflight report with command, field checks, no-Harbor/no-model checks, and next full-run command or blocker. |
| Entity body | Append the implementation stage report later. |

## Tasks

### T0 - Resolve Dataset Definition and Local Inputs

**Goal:** Prove the DAB full set comes from the plugin-shipped dataset definition, then resolve the machine-local data root without hard-coding it into Razorback code.

Run:

```bash
uv run python - <<'PY'
from razorback_plugin_dab.dataset_def import load_default_definition

d = load_default_definition()
query_count = sum(len(ds.query_ids) for ds in d.datasets)
print(f"ref={d.ref}")
print(f"dataset_count={len(d.datasets)}")
print(f"query_count={query_count}")
for ds in d.datasets:
    print(f"{ds.name}\t{len(ds.query_ids)}\t{','.join(map(str, ds.query_ids))}")
PY
```

Expected: `ref=dab@1.0`, `dataset_count=12`, `query_count=54`, with datasets `agnews`, `bookreview`, `crmarenapro`, `DEPS_DEV_V1`, `GITHUB_REPOS`, `googlelocal`, `music_brainz_20k`, `PANCANCER_ATLAS`, `PATENTS`, `stockindex`, `stockmarket`, and `yelp`.

Resolve `DATAAGENTBENCH_DATA_ROOT` as an operator input. Prefer an existing exported value. If unset, probe known local checkout conventions only as implementation evidence, not as spec identity:

```bash
: "${DATAAGENTBENCH_DATA_ROOT:=}"
if [ -z "$DATAAGENTBENCH_DATA_ROOT" ]; then
  for candidate in /home/exedev/dataagentbench/data "$HOME/git/dataagentbench/data" "$HOME/dataagentbench/data"; do
    if [ -d "$candidate" ]; then
      DATAAGENTBENCH_DATA_ROOT="$candidate"
      break
    fi
  done
fi
test -n "$DATAAGENTBENCH_DATA_ROOT"
test -d "$DATAAGENTBENCH_DATA_ROOT"
export DATAAGENTBENCH_DATA_ROOT
```

If no usable data root exists, stop with blocker `missing-dab-data-root`; record the failed probe commands and do not attempt a full run.

### T1 - Write and Freeze the Preflight Spec

**Goal:** Create the run-local spec from the target shape and freeze it so `spacedock_solver` has `sealed_hash` and `solver_workflow_content_hash` before `rk run --explain`.

Commands:

```bash
ROOT=_runs/dab-full-batch-codex-explain-preflight
SPEC="$ROOT/specs/dab-full-batch-codex-spacedock.yaml"
FROZEN="$ROOT/specs/dab-full-batch-codex-spacedock.frozen.yaml"
mkdir -p "$ROOT/specs"
# write SPEC from the Target Spec block above
uv run rk freeze "$SPEC" --allow-missing
test -f "$FROZEN"
```

Verification:

```bash
uv run python - <<'PY'
from pathlib import Path
import yaml

frozen = Path("_runs/dab-full-batch-codex-explain-preflight/specs/dab-full-batch-codex-spacedock.frozen.yaml")
spec = yaml.safe_load(frozen.read_text())
agent = spec["agent"]
bench = spec["benchmark"]
assert agent["kind"] == "spacedock_solver"
assert agent["runtime"] == "codex"
assert agent["model"] == "gpt-5.5"
assert agent["reasoning_effort"] == "xhigh"
assert agent["sealed_hash"]
assert agent["solver_workflow_content_hash"]
assert bench["kind"] == "harbor_dab"
assert bench["dataset"] == "dab@1.0"
assert "data_root" not in bench
assert bench["query_mode"] == "batch"
assert bench["workspace_variant"] == "spacedock"
PY
```

If freeze is blocked by missing Codex auth or model-version resolution, classify the blocker by exact exception. `--allow-missing` should tolerate unresolved provenance fields; `spacedock_solver` still requires a frozen sealed hash.

### T2 - Run the Explain Probe Only

**Goal:** Generate the JSON artifact that proves the run shape without launching Harbor or Codex.

Command:

```bash
ROOT=_runs/dab-full-batch-codex-explain-preflight
FROZEN="$ROOT/specs/dab-full-batch-codex-spacedock.frozen.yaml"
RUNS_DIR="$ROOT/runs"
EVIDENCE=docs/razorback-implementation/_evidence/dab-full-batch-codex-explain-preflight.json
STDERR=docs/razorback-implementation/_evidence/dab-full-batch-codex-explain-preflight.stderr.txt
mkdir -p "$RUNS_DIR" docs/razorback-implementation/_evidence
DATAAGENTBENCH_DATA_ROOT="$DATAAGENTBENCH_DATA_ROOT" \
  uv run rk run "$FROZEN" \
    --runs-dir "$RUNS_DIR" \
    --explain --explain-format json \
    > "$EVIDENCE" 2> "$STDERR"
```

This command is the riskiest-contract check. It exercises the same spec parse, runs-dir canary, auth discovery, DAB plugin materialization, JobConfig translation, solver/runtime kwargs, and prompt composition that a full run would use, then exits before Harbor.

If this command exits non-zero, do not retry with a full run. Record blocker class:

| Failure signal | Blocker class |
| --- | --- |
| `AuthDiscoveryError: no codex credentials found` | `missing-codex-auth` |
| `ConfigInvalidError: runs-dir not visible` | `runs-dir-container-visibility` |
| `razorback-plugin-dab generate failed` | `dab-materialization` |
| missing `DATAAGENTBENCH_DATA_ROOT` or LFS pointer diagnostics | `missing-or-unhydrated-dab-data` |

### T3 - Inspect Explain JSON for AC-1 and AC-2

**Goal:** Convert the explain JSON into exact evidence for dataset resolution, batch mode, solver variant, model, effort, and prompt mode.

Run:

```bash
uv run python - <<'PY'
import json
from pathlib import Path

from razorback_plugin_dab.dataset_def import load_default_definition

evidence = Path("docs/razorback-implementation/_evidence/dab-full-batch-codex-explain-preflight.json")
plan = json.loads(evidence.read_text())
definition = load_default_definition()
expected = {ds.name for ds in definition.datasets}
actual = {Path(p).name for p in plan["prompt"]["task_paths"]}

assert plan["schema_version"] == "rk-run-explain-v1"
assert plan["explain_only"] is True
assert plan["benchmark"]["kind"] == "harbor_dab"
assert plan["benchmark"]["dataset"] == definition.ref
assert plan["benchmark"].get("datasets", []) == []
assert plan["benchmark"]["query_mode"] == "batch"
assert plan["benchmark"]["workspace_variant"] == "spacedock"
assert plan["prompt"]["task_count"] == len(expected) == 12
assert actual == expected, sorted(actual ^ expected)

agent = plan["agent"]
assert agent["spec_kind"] == "spacedock_solver"
assert agent["runtime"] == "codex"
assert agent["model"] == "gpt-5.5"
assert agent["kwargs"]["runtime"] == "codex"
assert agent["kwargs"]["harbor_agent_kwargs"]["reasoning_effort"] == "xhigh"
assert plan["prompt"]["mode"] == "spacedock-codex-first-officer"

print("dataset_ref", plan["benchmark"]["dataset"])
print("task_count", plan["prompt"]["task_count"])
print("solver_variant", "spacedock-workflow")
print("agent", agent["spec_kind"], agent["runtime"], agent["model"])
print("reasoning_effort", agent["kwargs"]["harbor_agent_kwargs"]["reasoning_effort"])
print("prompt_mode", plan["prompt"]["mode"])
PY
```

Expected printed evidence:

```text
dataset_ref dab@1.0
task_count 12
solver_variant spacedock-workflow
agent spacedock_solver codex gpt-5.5
reasoning_effort xhigh
prompt_mode spacedock-codex-first-officer
```

### T4 - Prove the No-Harbor and No-Model Boundary

**Goal:** Make the boundary explicit enough that this preflight cannot be mistaken for a scored run.

Run:

```bash
uv run python - <<'PY'
import json
from pathlib import Path

plan = json.loads(Path("docs/razorback-implementation/_evidence/dab-full-batch-codex-explain-preflight.json").read_text())
run_dir = Path(plan["run_dir"])
for expected in (
    "does not write _job_config.yaml",
    "does not invoke Harbor",
    "does not run the model",
):
    assert expected in plan["explain_side_effects"]

assert run_dir.exists()
assert not (run_dir / "_job_config.yaml").exists()
assert not (run_dir / "trials").exists()
for pattern in ("result.json", "summary.json", "events.jsonl", "score.json", "audit.json"):
    matches = list(run_dir.rglob(pattern))
    assert not matches, (pattern, [str(p) for p in matches[:5]])

print("run_dir", run_dir)
print("no_job_config", True)
print("no_harbor_trials", True)
print("no_model_or_score_artifacts", True)
PY
```

The run dir may contain `tasks/` because explain materializes task views to report exact task paths. That is acceptable and should be named in the report.

### T5 - Report Green Launch Command or Blocker

**Goal:** Commit a concise preflight report and name the exact next action.

Write `docs/razorback-implementation/_evidence/dab-full-batch-codex-explain-preflight.md` with:

- the exact `rk run --explain --explain-format json` command;
- data-root discovery result, dataset definition ref, dataset count, and query count;
- JSON field inspection results from T3;
- boundary results from T4;
- raw JSON artifact path and SHA256;
- green launch recommendation or blocker.

If T2-T4 are green, record this as the next full-run command but do not run it:

```bash
DATAAGENTBENCH_DATA_ROOT="$DATAAGENTBENCH_DATA_ROOT" \
  uv run rk run \
    _runs/dab-full-batch-codex-explain-preflight/specs/dab-full-batch-codex-spacedock.frozen.yaml \
    --runs-dir _runs/dab-full-batch-codex-gpt55-xhigh-spacedock
```

If blocked, record:

- blocker class from T2;
- failing command;
- stderr/log path;
- whether any run-dir artifacts were created;
- the next repair action required before re-running explain.

## TDD and Mechanism Checkpoints

There is no production code in this task, so there is no red/green unit-test pair. The verification discipline is:

1. T0 proves the dataset definition before writing or running a spec.
2. T1 freezes the exact target spec and asserts the frozen solver fields.
3. T2 is the smallest end-to-end mechanism check of the riskiest contract: full DAB definition plus batch materialization plus Codex spacedock prompt shape, stopping before Harbor.
4. T3 and T4 are executable assertions over the JSON artifact and run-dir filesystem.
5. T5 records the full-run command only after explain evidence passes.

## Risks and Guardrails

| Risk | Guardrail |
| --- | --- |
| Explain still requires Codex auth discovery. | Treat missing auth as `missing-codex-auth`; do not bypass with fake credentials unless the captain explicitly authorizes a non-auth translation fixture. |
| Local DAB data is absent or contains LFS pointers. | Treat as `missing-or-unhydrated-dab-data`; record the path and plugin stderr. |
| `rk run --explain` materializes task views. | Allow `tasks/` under the explain run dir, but require no `_job_config.yaml`, no `trials/`, and no result/summary/event/score/audit artifacts. |
| A per-dataset Goal 1 spec is accidentally used. | T3 requires `benchmark.datasets == []` and `prompt.task_count == 12`; a single-cell spec fails. |
| Direct Codex minimal/structured shape is confused with the Goal 3 target. | T3 requires `agent.spec_kind: spacedock_solver`, `runtime: codex`, and prompt mode `spacedock-codex-first-officer`, then labels solver variant `spacedock-workflow`. |

## Definition of Done

- The explain artifact or normalized extraction is committed under `docs/razorback-implementation/_evidence/` or the raw JSON path and SHA256 are cited in the committed report.
- The report proves `dab@1.0`, 12 batch tasks, Codex `gpt-5.5`, `xhigh`, solver variant `spacedock-workflow`, and prompt mode `spacedock-codex-first-officer`.
- The report proves no `_job_config.yaml`, Harbor trials, model events, score, audit, summary, or result artifacts were produced by the explain invocation.
- The report ends with the exact full-run command to execute next, or a blocker with failing command and stderr/log path.
