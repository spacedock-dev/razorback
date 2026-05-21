# Goal 2: ade-bench Haiku baseline (haiku-4.5 × 44 tasks × N=1), Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to drive this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Entity:** `docs/razorback-implementation/goal2-ade-bench-haiku-baseline.md`
(id `jjv58hxgfknqwbsehkashqj8`).

**Goal.** Establish the Haiku-on-ade-bench baseline via the v2 surface
stack with PKG-19's bind-mount data path. Matrix shape: `claude-haiku-4-5`
× all ade-bench tasks under `~/git/ade-bench/tasks/` × N=1 trial per task.
Each cell runs `rk freeze` → `rk run --max-budget-usd-running budget.json`
→ `rk score` → `rk audit --policy strict`. The aggregate stratified pass@1
across the task set is the headline baseline number; it becomes the
`--against-constant` target for future Haiku improvement runs (AC-7).

## Captain directive (2026-05-20)

**Scope to N=1 to ship the number fast; raising N is a separate
follow-up entity.** This overrides the entity body's AC-4a.14 framing
of N≥3. Total trial count: ~44 (one trial per discovered ade-bench
task, not the literal "48" in the entity title — the entity body's
count is approximate; the generator enumerates the actual task set at
dispatch time and prints the count in `--dry-run`). Expected cost ~$0
via Claude subscription auth (`CLAUDE_CODE_OAUTH_TOKEN`); expected
wallclock 60-90 min.

**Honesty caveat carried into the result doc (T6).** At N=1 the per-task
Wilson 95% CI is degenerate: any single observation yields a CI of
either `[0, 0.975]` (pass=0, n=1) or `[0.025, 1]` (pass=1, n=1) — the
"CIs" are not interpretable as precision statements. The result doc
reports per-task pass@1 as a 0/1 point estimate, omits per-task CIs
(or renders them with an explicit "N=1 — degenerate" annotation), and
treats the aggregate stratified pass@1 over the task set as the
headline. AC-5's framing of "non-degenerate CI half-widths" does NOT
hold under this directive; this plan substitutes:

> AC-5 (revised under captain directive): `rk score` output is
> committed per cell + aggregated across the task set. Per-task CI
> half-widths are degenerate at N=1 by construction; the result doc
> names the degeneracy explicitly. The aggregate stratified pass@1
> across the task set is the registered baseline value.

**No `--against-constant`.** Goal 2 is an establishing measurement,
not a reproduction. `rk score` is invoked without `--against-constant`;
the output value becomes the baseline-of-record for future runs
(AC-7).

**Same stratum-collapse caveat as Goal 1.** `rk score`'s ML-reviewer F1
calculation collapses strata; the result doc cites the caveat verbatim
from Goal 1's result doc.

## Architecture

**Dispatch shape.** A bash matrix-driver at
`examples/drivers/ade-bench-haiku-matrix.sh` iterates the discovered
ade-bench task set, one cell per (model, task, trial-index) tuple
(trial-index is fixed at 1 under the captain directive). Each cell:

```
for task in ade_bench_tasks:
  rk freeze <spec>                          # → spec.frozen.yaml + provenance.yaml
  rk run --max-budget-usd-running budget.json <spec.frozen.yaml> \
      --runs-dir runs/goal2/<task>/
  rk score <run-dir> --format json > score.json
  rk audit --policy strict <run-dir> --format json > audit.json
```

Idempotence is provided by `rk run`'s content-hash determinism: if a
cell's run-dir already exists with a clean `result.json`, the driver
skips. Same mechanism as Goal 1's `dab-paper-matrix.sh`.

**Budget enforcement.** A single `budget.json` is threaded across all
cells via `--max-budget-usd-running`. The matrix spec declares
`experiment_meta.max_budget_usd: 50` (well above the ~$0 expectation,
chosen to catch unexpected API-billed regression without blocking the
intended subscription-billed run). Per spec exit code 22, any cell
that would push the running total over the cap refuses to dispatch
and the driver pauses.

**Data path.** Every task spec uses `AdeBenchLocalTaskEntry` (slug-
only) plus `benchmark.ade_bench_root: ~/git/ade-bench`. This is the
PKG-19 bind-mount path: no per-task `harbor-datasets` clone, view-dir
built from the local checkout, `seeds/solution__*.csv` filtered out of
the agent's view. See PKG-19's validation report at
`docs/razorback-implementation/validation/pkg19-ade-bench-data-bind-mount.md`.

**Probe phase 2-5 is the first task in this plan.** Single-task end-
to-end smoke (Haiku × airbnb001 × N=1 through the v2 surface stack +
PKG-19 bind-mount) gates the full matrix dispatch the same way Goal
1's T0 gates Goal 1's matrix. If the probe fails at any of phases
2-5, the matrix-dispatch task does not start.

## Source of truth

- v2 spec: `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
  §3.2 (CLI subcommands), §6.2 (agent block), §6.4 (benchmark block —
  ade-bench shape), §8.1 (budget gate), §9.4 (audit).
- Goal 2 entity: `docs/razorback-implementation/goal2-ade-bench-haiku-baseline.md`
  (7 ACs; this plan covers all 7 with AC-4a.14/AC-5 revised per
  captain directive above).
- PKG-19 validation report:
  `docs/razorback-implementation/validation/pkg19-ade-bench-data-bind-mount.md`
  (bind-mount data path, `AdeBenchLocalTaskEntry`, solution-file
  exclusion contract).
- PKG-17 archive:
  `docs/razorback-implementation/_archive/pkg17-rk-run-writes-rundir-artifacts.md`
  (run-dir artifact contract — `result.json`, `provenance.yaml`,
  trial subtree, manifest schema).
- Goal 1 plan as architectural template:
  `docs/razorback-implementation/plans/goal1-dab-paper-reproduction.md`
  (matrix-driver shape; idempotence; budget threading; aggregate
  scoring/audit). Adapt — don't re-derive.
- ade-bench task catalog: `~/git/ade-bench/tasks/<slug>/` (44 tasks at
  plan time per `ls /Users/clkao/git/ade-bench/tasks` 2026-05-20; the
  generator re-enumerates at dispatch time).

## AC-to-task map

| AC | Task |
|----|------|
| AC-1 (matrix dispatcher + dry-run + skip-completed) | T1 (generator) + T2 (driver) + T3 (idempotence) |
| AC-2 (provenance.yaml sealed inputs)               | T1 (`rk freeze` per spec) + T5 (provenance spot-check) |
| AC-3 (budget gate enforced)                         | T2 (`--max-budget-usd-running` threading) + T4 (budget fixture) |
| AC-4 (audit clean across all cells)                 | T4 (per-cell + aggregate audit) |
| AC-5 (rk score per-task + aggregate; revised)       | T4 (per-cell `rk score`) + T6 (aggregate + result doc) |
| AC-6 (result summary committed)                     | T6 (result doc) |
| AC-7 (registered baseline value)                    | T6 (result doc names the value) |

## Riskiest contract first

Before the matrix burn (cheap as it is at ~$0):

1. **T0 — probe phase 2-5.** Single-task Haiku × airbnb001 × N=1 end-
   to-end via the v2 surface stack with PKG-19's bind-mount. This is
   the riskiest unverified contract — PKG-19's AC-7 was SKIPPED in
   validation (env blocker), so this is the first live exercise of
   the bind-mount data path through `rk run` + harbor + claude-cli
   against a real ade-bench task. All four phases (rk run cleanly
   completes; rk score parses; rk audit clean; provenance.yaml carries
   the v2 sealed-input set) must be green before T1 dispatches the
   spec set or T2 dispatches the matrix.
2. T1-T6 dispatch only after T0 is green.

## Tasks

### T0: Probe phase 2-5 — single-task end-to-end smoke

**Files:**
- Use: `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml`
  (exists from PKG-19; needs the model swapped to Haiku).
- Create: `examples/specs/probe-ade-bench-airbnb001-haiku.yaml` (copy
  of the PKG-19 probe spec with `model: claude-haiku-4-5`).
- Outputs (transient): `runs/goal2-probe/airbnb001/<job-hash>/...`
- Validation artifact (committed): brief notes appended to the result
  doc T6 will write (see T6 step 1 below — T0 seeds the doc).

- [ ] **Step 1: Create the Haiku probe spec.** Copy
      `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml`
      to `examples/specs/probe-ade-bench-airbnb001-haiku.yaml`. Change
      `agent.model` from `claude-opus-4-5` to `claude-haiku-4-5`.
      Change `experiment` from `probe-ade-bench-airbnb001-claude-
      harbor-local` to `goal2-probe-ade-bench-airbnb001-haiku`. Leave
      the rest (tasks_root, ade_bench_root, slug, trials, budget)
      unchanged.

- [ ] **Step 2 (probe phase 2 — rk run): dispatch the single-task
      cell.** From the razorback repo root with `CLAUDE_CODE_OAUTH_TOKEN`
      exported:

```
uv run rk freeze examples/specs/probe-ade-bench-airbnb001-haiku.yaml
uv run rk run --max-budget-usd-running runs/goal2-probe/budget.json \
              examples/specs/probe-ade-bench-airbnb001-haiku.frozen.yaml \
              --runs-dir runs/goal2-probe/
```

      **Expected:** `rk run` exits 0. `runs/goal2-probe/<job-hash>/`
      exists with `result.json` + at least one trial subdir +
      `provenance.yaml`. Per PKG-17's run-dir artifact contract.

- [ ] **Step 3 (probe phase 3 — rk score): score the single-task
      cell.**

```
uv run rk score runs/goal2-probe/<job-hash>/ --format json
```

      **Expected:** exits 0. JSON parses. Includes `stratified_pass_at_1`
      and a per-stratum entry for `airbnb001`. The score value may be 0
      or 1 — that is NOT the gate. The gate is "rk score reads the
      run-dir without error and produces a parseable artifact." Capture
      the score value for T6's seed entry.

- [ ] **Step 4 (probe phase 4 — rk audit): audit the single-task
      cell.**

```
uv run rk audit --policy strict runs/goal2-probe/<job-hash>/
```

      **Expected:** exits 0 (n_tainted == 0). ade-bench's task surface
      should not trigger DAB-specific tool denials, but the heredoc /
      `python -c` / web-search guards still apply — confirm clean.

- [ ] **Step 5 (probe phase 5 — provenance.yaml sealed inputs).**
      Inspect `runs/goal2-probe/<job-hash>/provenance.yaml`. Confirm
      the v2 sealed-input set is populated:

```
uv run python -c "
import yaml
from pathlib import Path
prov = yaml.safe_load(Path('runs/goal2-probe/<job-hash>/provenance.yaml').read_text())
required = ['solver_workflow_hash', 'spacedock_skill_version',
            'harbor_agent_kwargs_hash', 'agent', 'tools_denied']
for k in required:
    assert k in prov, f'missing: {k}'
print('OK:', sorted(prov.keys()))
"
```

      **Expected:** prints OK with the populated key list. Per AC-2 +
      the entity's verbatim sealed-input field list:
      `solver_workflow_hash`, `spacedock_skill_version`,
      `harbor_agent_kwargs_hash`, resolved model alias, image digest,
      agent CLI binary hash, prompt content hashes, harbor version,
      `tools_denied`.

- [ ] **Step 6: T0 verdict.** If steps 2-5 all exit 0 and provenance
      is populated, T0 is PASS — proceed to T1. If any step fails,
      STOP and surface to captain with the failing step's output;
      DO NOT dispatch T1+.

- [ ] **Step 7: Commit the probe spec.**

```
git add examples/specs/probe-ade-bench-airbnb001-haiku.yaml \
        examples/specs/probe-ade-bench-airbnb001-haiku.frozen.yaml \
        examples/specs/probe-ade-bench-airbnb001-haiku.frozen.provenance.yaml
git commit -m "goal2-t0: ade-bench Haiku probe spec + frozen pair"
```

      Do NOT commit `runs/goal2-probe/` (gitignored; the probe's
      run-dir is transient).

**Acceptance (T0):** all four probe phases (rk run completes, rk
score parses, rk audit clean, provenance v2 sealed-input set
populated) are green on the airbnb001 single-task smoke. T0's verdict
+ score value + run-dir path get seeded into T6's result doc.

### T1: Matrix-spec generator

Emit one frozen spec per discovered ade-bench task. Each spec carries
`claude-haiku-4-5` + `trials: 1` + `ade_bench_root: ~/git/ade-bench` +
`AdeBenchLocalTaskEntry` per task slug.

**Files:**
- Create: `examples/drivers/generate-ade-bench-haiku-matrix-specs.py`
- Output dir: `examples/specs/goal2/<task-slug>.yaml` + `.frozen.yaml`
  + `.frozen.provenance.yaml` per task.

- [ ] **Step 1: Write the generator.** Bash-friendly Python; mirrors
      the shape of Goal 1's `generate-dab-paper-matrix-specs.py` (per
      the Goal 1 plan §T1). Input: list directory entries of
      `~/git/ade-bench/tasks/` (expanded via `Path.expanduser()`),
      excluding non-directories and dotfiles. Output template per task:

```yaml
version: 1
experiment: goal2-ade-bench-haiku-<task-slug>
agent:
  kind: claude-cli
  model: claude-haiku-4-5
  sampling:
    temperature: 0.0
  tools_allowed:
    - Bash
    - Read
    - Write
    - Edit
    - Glob
    - Grep
benchmark:
  kind: ade-bench
  tasks_root: .
  ade_bench_root: ~/git/ade-bench
  tasks:
    - slug: <task-slug>
trials: 1
experiment_meta:
  max_budget_usd: 50.0
  estimated_cost_usd: 0.0
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
```

      The generator writes one file per task slug under
      `examples/specs/goal2/`. Print the total count at the end (the
      "44" number from this plan is a snapshot; the generator emits
      whatever the directory currently holds).

- [ ] **Step 2: Run the generator.**

```
uv run python examples/drivers/generate-ade-bench-haiku-matrix-specs.py \
  --ade-bench-root ~/git/ade-bench \
  --output-dir examples/specs/goal2/
```

      **Expected:** prints `Emitted N specs to examples/specs/goal2/`
      where N matches `ls -d ~/git/ade-bench/tasks/*/ | wc -l`.

- [ ] **Step 3: Freeze every spec.** Loop:

```
for f in examples/specs/goal2/*.yaml; do
  [[ "$f" == *.frozen.yaml ]] && continue
  uv run rk freeze "$f"
done
```

      Each freeze produces a sibling `<spec>.frozen.yaml` plus a
      `<spec>.frozen.provenance.yaml`. Per AC-2 the provenance carries
      the v2 sealed-input set.

- [ ] **Step 4: Provenance smoke at generator-emit time.** Sample one
      generated `*.frozen.provenance.yaml`; assert the 9 v2 sealed-
      input fields named in AC-2 are present (same assertion as T0
      step 5 above; promote to a one-line script). Required fields:
      `solver_workflow_hash`, `spacedock_skill_version`,
      `harbor_agent_kwargs_hash`, resolved model alias (from `agent`),
      image digest (from benchmark resolution), agent CLI binary hash,
      prompt content hashes, harbor version, `tools_denied`.

- [ ] **Step 5: Commit the spec set.**

```
git add examples/drivers/generate-ade-bench-haiku-matrix-specs.py \
        examples/specs/goal2/
git commit -m "goal2-t1: ade-bench Haiku matrix spec generator + N specs"
```

**Acceptance (T1):** the generator emits one spec per discovered task
in `~/git/ade-bench/tasks/`; every spec parses against
`AdeBenchBenchmarkBlock`; every frozen spec's provenance carries the
9 v2 sealed-input fields (AC-2).

### T2: Matrix-driver script — dry-run + dispatch loop

`examples/drivers/ade-bench-haiku-matrix.sh`. Bash, idiomatic, exits
non-zero on the first cell failure unless `--continue-on-fail`. Mirror
Goal 1's `dab-paper-matrix.sh` (per the Goal 1 plan §T2) — adapt
flags and paths; don't re-derive shape.

**Files:**
- Create: `examples/drivers/ade-bench-haiku-matrix.sh`

- [ ] **Step 1: Flags.**
  - `--budget <usd>` (default `50`)
  - `--output-dir <path>` (default `runs/goal2/`)
  - `--specs-dir <path>` (default `examples/specs/goal2/`)
  - `--dry-run` (print the N-cell plan, exit 0 without dispatching)
  - `--continue-on-fail` (skip past failed cells, accumulate to
    `<output-dir>/failures.txt`, exit non-zero at end if any failed)

- [ ] **Step 2: Dispatch loop.** Iterate `<specs-dir>/*.frozen.yaml`.
      For each:

```bash
task_slug=$(basename "$spec" .frozen.yaml)
run_dir="${output_dir}/${task_slug}/"
uv run rk run --max-budget-usd-running "${output_dir}/budget.json" \
    "$spec" --runs-dir "$run_dir"
```

      The dispatch is one `rk run` per task (trials=1 lives inside the
      spec). On non-zero exit: per `--continue-on-fail`, either bail
      now or record + continue.

- [ ] **Step 3: Per-cell score + audit (interleaved with dispatch).**
      Immediately after each `rk run` succeeds, locate the cell's
      run-dir (newest `<run_dir>/<job-hash>/` containing `result.json`)
      and:

```bash
uv run rk score "$cell_run_dir" --format json > "$cell_run_dir/score.json"
uv run rk audit --policy strict "$cell_run_dir" --format json \
    > "$cell_run_dir/audit.json" || \
  echo "AUDIT_TAINTED $task_slug $cell_run_dir" >> "$output_dir/audit-failures.txt"
```

      Audit exit 23 records the taint, does NOT bail (matches Goal
      1's audit-aggregation-at-end pattern; tainted cells surface in
      T6's result doc).

- [ ] **Step 4: Dry-run output.** With `--dry-run`, iterate the spec
      set and print a deterministic table:

```
task_slug                  spec_path                                 projected_run_dir
airbnb001                  examples/specs/goal2/airbnb001.frozen.yaml runs/goal2/airbnb001/
airbnb002                  ...
...
TOTAL: <N> cells (N=1 per cell)
```

      Sort by task slug for determinism. Print the total count at the
      bottom.

- [ ] **Step 5: Acceptance test for dry-run.** Bash-level snapshot:

```
bash examples/drivers/ade-bench-haiku-matrix.sh --dry-run | head -3
bash examples/drivers/ade-bench-haiku-matrix.sh --dry-run | tail -1
```

      First should be the header + first two rows; last should match
      `TOTAL: <N> cells (N=1 per cell)` with N equal to the spec
      count.

- [ ] **Step 6: Commit.**

```
git add examples/drivers/ade-bench-haiku-matrix.sh
git commit -m "goal2-t2: ade-bench Haiku matrix driver + dry-run"
```

**Acceptance (T2):** `--dry-run` prints the N-cell plan
deterministically; live dispatch (deferred to T3 acceptance) drives
`rk run` + `rk score` + `rk audit` per cell.

### T3: Idempotence + partial-resume + matrix dispatch

The driver re-runs cleanly after a partial failure. Each cell's
"already done" check is a filesystem read on the expected run-dir's
`result.json`.

**Files:**
- Modify: `examples/drivers/ade-bench-haiku-matrix.sh` (skip-completed
  pre-check before `rk run`).

- [ ] **Step 1: Skip-completed check.** Before each `rk run`:

```bash
existing_result=$(find "$run_dir" -maxdepth 2 -name result.json 2>/dev/null | head -1)
if [[ -n "$existing_result" ]]; then
  n_completed=$(uv run python -c "
import json,sys; r=json.load(open('$existing_result'))
print(r.get('stats',{}).get('n_completed_trials',0))
")
  n_errored=$(uv run python -c "
import json,sys; r=json.load(open('$existing_result'))
print(r.get('stats',{}).get('n_errored_trials',0))
")
  if [[ "$n_completed" -ge 1 && "$n_errored" -eq 0 ]]; then
    echo "SKIP $task_slug (already complete: n_completed=$n_completed)"
    continue
  fi
fi
```

      Mirrors Goal 1's idempotence pattern, but for N=1: the threshold
      is `n_completed >= 1` not `>= 5`.

- [ ] **Step 2: Idempotence acceptance test.** Three-step manual
      smoke:

```
# Fresh dispatch — runs all cells:
bash examples/drivers/ade-bench-haiku-matrix.sh --output-dir runs/goal2/

# Re-dispatch — every cell should print SKIP:
bash examples/drivers/ade-bench-haiku-matrix.sh --output-dir runs/goal2/ \
  | tee /tmp/goal2-redispatch.log
grep -c "^SKIP " /tmp/goal2-redispatch.log
# Expected: N (matching the cell count)
```

      Deferred to live dispatch (Step 4 below); the bash-level
      assertion runs against the post-dispatch state.

- [ ] **Step 3: Live matrix dispatch.** With `CLAUDE_CODE_OAUTH_TOKEN`
      exported and T0 PASS confirmed:

```
bash examples/drivers/ade-bench-haiku-matrix.sh \
  --budget 50 --output-dir runs/goal2/
```

      Wallclock budget: 60-90 min (per captain directive). The driver
      runs in foreground; if the captain wants background dispatch,
      use `nohup` or a tmux session — out of plan scope.

- [ ] **Step 4: Verify idempotence post-dispatch.** Re-run the same
      command; expected output: `SKIP <slug>` for every task. Zero
      `rk run` invocations.

- [ ] **Step 5: Commit the idempotence wiring + dispatch log.**

```
git add examples/drivers/ade-bench-haiku-matrix.sh
git commit -m "goal2-t3: ade-bench Haiku matrix idempotence + skip-completed"
```

      Do NOT commit `runs/goal2/`. The run-dir set is gitignored;
      paths get cited in T6's result doc instead.

**Acceptance (T3, AC-1):** matrix dispatch completes; re-dispatch is a
no-op (all cells SKIP); the run-dir tree exists at
`runs/goal2/<task-slug>/<job-hash>/`.

### T4: Budget gate + per-cell + aggregate audit

Two artifacts: per-cell audit + aggregate audit + budget verification.

**Files:**
- Create: `examples/drivers/aggregate-goal2-audit.py`
- Read: `runs/goal2/<task>/<job-hash>/audit.json` (one per cell, from
  T2 step 3).
- Read: `runs/goal2/budget.json` (the threaded budget ledger).
- Output: `runs/goal2/audit-aggregate.json`.

- [ ] **Step 1: Budget gate verification (AC-3 + AC-7).** Read
      `runs/goal2/budget.json` after T3 dispatch completes. Assert:

```python
import json
b = json.load(open('runs/goal2/budget.json'))
assert b['spent_usd'] <= b['max_usd'], (
    f"budget exceeded: spent={b['spent_usd']} max={b['max_usd']}")
print(f"AC-3 PASS: spent_usd={b['spent_usd']} max_usd={b['max_usd']}")
```

      Per captain directive, expected `spent_usd` is ~0 (subscription
      auth). If non-zero by surprise, surface to captain before T6.

- [ ] **Step 2: Aggregate audit.** Write the aggregator:

```python
# examples/drivers/aggregate-goal2-audit.py
import json, sys
from pathlib import Path
def main(runs_dir):
    audit_files = list(Path(runs_dir).rglob('audit.json'))
    n_tainted = 0
    per_cell = []
    for f in audit_files:
        a = json.loads(f.read_text())
        n = a.get('n_tainted', 0)
        n_tainted += n
        per_cell.append({'cell': str(f.parent), 'n_tainted': n,
                         'policy': a.get('policy')})
    out = {'n_audit_files': len(audit_files),
           'n_tainted_total': n_tainted,
           'per_cell': per_cell}
    Path(runs_dir, 'audit-aggregate.json').write_text(
        json.dumps(out, indent=2, sort_keys=True))
    print(f"AC-4: n_audit_files={len(audit_files)} n_tainted={n_tainted}")
    return 0 if n_tainted == 0 else 23
if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
```

      Run:

```
uv run python examples/drivers/aggregate-goal2-audit.py runs/goal2/
```

      **Expected (AC-4 PASS):** `n_tainted=0`; the script exits 0 and
      writes `runs/goal2/audit-aggregate.json`.

- [ ] **Step 3: Commit the aggregator.** The aggregate JSON itself is
      under `runs/` (gitignored); only the script is committed.

```
git add examples/drivers/aggregate-goal2-audit.py
git commit -m "goal2-t4: ade-bench Haiku audit aggregator"
```

**Acceptance (T4, AC-3 + AC-4 + AC-7):** budget gate verified (spent
≤ max); aggregate audit reports `n_tainted: 0` across all cells.

### T5: Provenance spot-check + per-task score aggregation

Provenance sample for AC-2; per-task score loader for T6.

**Files:**
- Create: `examples/drivers/aggregate-goal2-scores.py`
- Create: `validation/goal2-provenance-sample.json` (committed
  evidence; mirrors Goal 1's `validation/goal1-provenance-sample.json`
  pattern).

- [ ] **Step 1: Provenance spot-check (AC-2).** Randomly sample one
      cell's `provenance.yaml`; assert the 9 v2 sealed-input fields
      present (same assertion shape as T0 step 5, T1 step 4).

```python
import json, random, yaml
from pathlib import Path
cells = sorted(Path('runs/goal2/').glob('*/*/provenance.yaml'))
sample = random.choice(cells)
prov = yaml.safe_load(sample.read_text())
required = ['solver_workflow_hash', 'spacedock_skill_version',
            'harbor_agent_kwargs_hash', 'agent', 'tools_denied']
missing = [k for k in required if k not in prov]
result = {'sampled_cell': str(sample.parent),
          'required_fields': required,
          'missing': missing,
          'verdict': 'PASS' if not missing else 'FAIL'}
Path('validation/goal2-provenance-sample.json').write_text(
    json.dumps(result, indent=2, sort_keys=True))
print(result)
assert not missing, f"AC-2 FAIL: missing fields {missing}"
```

      **Expected:** verdict=PASS; the JSON commits as evidence.

- [ ] **Step 2: Per-task score aggregator.** Write the aggregator:

```python
# examples/drivers/aggregate-goal2-scores.py
import json, sys
from pathlib import Path
def main(runs_dir):
    score_files = sorted(Path(runs_dir).rglob('score.json'))
    per_task = []
    n_pass = 0
    for f in score_files:
        s = json.loads(f.read_text())
        task_slug = f.parent.parent.name  # runs/goal2/<task>/<hash>/score.json
        pass_at_1 = s.get('stratified_pass_at_1')
        per_task.append({'task': task_slug,
                         'pass_at_1_n1': pass_at_1,
                         'score_json': str(f)})
        if pass_at_1 is not None and pass_at_1 > 0:
            n_pass += 1
    n_tasks = len(score_files)
    aggregate = n_pass / n_tasks if n_tasks else None
    out = {'n_tasks': n_tasks,
           'n_pass': n_pass,
           'aggregate_pass_at_1_n1': aggregate,
           'n_per_task': 1,
           'wilson_ci_note':
               'N=1 per task — per-task Wilson CIs degenerate by'
               ' construction (captain directive 2026-05-20);'
               ' aggregate is a point estimate, not a CI-bracketed'
               ' interval. Raising N is a separate follow-up entity.',
           'per_task': per_task}
    Path(runs_dir, 'score-aggregate.json').write_text(
        json.dumps(out, indent=2, sort_keys=True))
    print(f"AC-5 (revised): n_tasks={n_tasks} n_pass={n_pass}"
          f" aggregate_pass_at_1={aggregate}")
    return 0
if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
```

      Run:

```
uv run python examples/drivers/aggregate-goal2-scores.py runs/goal2/
```

      **Expected:** prints `n_tasks=<N> n_pass=<K> aggregate_pass_at_1=
      <K/N>`. The aggregate is the headline baseline number.

- [ ] **Step 3: Commit.**

```
git add examples/drivers/aggregate-goal2-scores.py \
        validation/goal2-provenance-sample.json
git commit -m "goal2-t5: provenance spot-check + score aggregator"
```

**Acceptance (T5, AC-2 + AC-5 revised):** sampled provenance carries
the 9 v2 sealed-input fields; per-task score aggregator emits
`runs/goal2/score-aggregate.json` with N=1 honesty caveat baked in.

### T6: Result summary doc

`docs/superpowers/plans/2026-05-19-goal2-haiku-baseline.md` (per AC-6;
date in filename matches the entity's commissioning date 2026-05-19,
same as Goal 1's result doc — NOT 2026-05-20).

**Files:**
- Create: `docs/superpowers/plans/2026-05-19-goal2-haiku-baseline.md`

- [ ] **Step 1: Section 1 — Scope + captain directive.** Document the
      N=1 directive verbatim:

> Captain directive 2026-05-20: scope to N=1 to ship the number fast;
> raising N is a separate follow-up entity.

      Then the AC-5 revision (per-task CIs degenerate at N=1; aggregate
      stratified pass@1 is the headline). And the no-`--against-constant`
      framing (establishing measurement, not reproduction).

- [ ] **Step 2: Section 2 — Probe phase 2-5 outcome (from T0).** Seed
      from T0 step 6:
  - airbnb001 single-task smoke: rk run / rk score / rk audit /
    provenance verdicts.
  - run-dir path cited.
  - Date + git SHA of the probe spec commit (T0 step 7).

- [ ] **Step 3: Section 3 — Headline baseline.** From T5's
      `score-aggregate.json`:

> Goal 2 baseline (claude-haiku-4-5, N=1 per task, full ade-bench task
> set): observed aggregate pass@1 = <K/N> across <N> tasks. Per-task
> CIs not reported (N=1 — degenerate by construction; see Scope
> section). This value registers as the Haiku-on-ade-bench baseline
> for AC-7's future `--against-constant haiku_ade_bench_baseline=<K/N>`
> comparisons.

- [ ] **Step 4: Section 4 — Per-task table.** N rows, sorted by task
      slug. Columns: `task | pass_at_1_n1 (0 or 1) | run_dir_path |
      score.json | audit.json | n_tainted`. Cite every path so AC-6's
      "each subsection cites the underlying run-dir paths" holds.

- [ ] **Step 5: Section 5 — Audit aggregate (AC-4).** From T4 step 2:
      `n_audit_files=<N>; n_tainted_total=<X>` (expected X=0).

- [ ] **Step 6: Section 6 — Cost ledger (AC-3, AC-7).** From the
      budget gate check in T4 step 1: `spent_usd=<...> max_usd=<50.0>`.
      Note captain expectation of ~$0 via subscription; if non-zero,
      itemize the surprise.

- [ ] **Step 7: Section 7 — Honesty caveats.** Two:
  1. **N=1 per-task CIs degenerate** (carry-forward from Section 1).
     Per-task Wilson CIs are not interpretable at N=1; the per-task
     column is a 0/1 point estimate.
  2. **`rk score` stratum-collapse for ML-reviewer F1** (same caveat
     as Goal 1's result doc). The ML-reviewer F1 implementation in
     `rk score` collapses strata; cite Goal 1's caveat language
     verbatim once Goal 1 ships its result doc.

- [ ] **Step 8: Section 8 — Registered baseline (AC-7).** Name the
      headline value + the commit SHA + the run-dir set's root path,
      so future `--against-constant` invocations can name this value
      and trace its provenance.

- [ ] **Step 9: Commit.**

```
git add docs/superpowers/plans/2026-05-19-goal2-haiku-baseline.md
git commit -m "goal2-t6: ade-bench Haiku baseline result summary"
```

**Acceptance (T6, AC-6 + AC-7):** the result doc exists with 8
sections, each citing underlying run-dir paths; the headline baseline
value is named in section 3 and section 8 as the registered baseline.

## Test plan

- **T0 probe phase 2-5 smoke (HARD GATE).** Single-task Haiku ×
  airbnb001 × N=1 via the v2 surface stack + PKG-19 bind-mount. All
  four phases (rk run completes, rk score parses, rk audit clean,
  provenance v2 sealed-input set populated) green BEFORE T1
  dispatches anything. Per the "riskiest contract first" section
  above.
- **T1 generator test.** Generator emits one spec per discovered
  task; every spec parses against `AdeBenchBenchmarkBlock`; every
  frozen provenance carries the 9 v2 sealed-input fields.
- **T2 dry-run test.** `bash examples/drivers/ade-bench-haiku-
  matrix.sh --dry-run` prints the N-cell plan deterministically.
- **T3 idempotence test.** Fresh dispatch → all cells complete;
  re-dispatch → all cells SKIP; no `rk run` invocations on the
  re-dispatch.
- **T4 budget verification.** Final `budget.json::spent_usd ≤
  max_usd`.
- **T4 aggregate audit test.** `aggregate-goal2-audit.py` reports
  `n_tainted_total: 0` across all cells (AC-4).
- **T5 provenance spot-check.** Sampled cell's `provenance.yaml`
  carries the 9 v2 sealed-input fields (AC-2).
- **T5 score aggregator.** `aggregate-goal2-scores.py` emits
  `score-aggregate.json` with `aggregate_pass_at_1_n1` populated and
  the N=1 honesty caveat in the JSON body.
- **Acceptance command.** `bash examples/drivers/ade-bench-haiku-
  matrix.sh --budget 50 --output-dir runs/goal2/` exits 0 after
  dispatching all discovered ade-bench tasks; the result summary at
  `docs/superpowers/plans/2026-05-19-goal2-haiku-baseline.md` lands
  with all 8 sections populated and the registered baseline named.

## File structure

New files (under razorback root):

```
examples/drivers/
  ade-bench-haiku-matrix.sh                   (T2/T3 dispatcher)
  generate-ade-bench-haiku-matrix-specs.py    (T1 spec generator)
  aggregate-goal2-audit.py                    (T4 aggregator)
  aggregate-goal2-scores.py                   (T5 aggregator)
examples/specs/
  probe-ade-bench-airbnb001-haiku.yaml        (T0 probe spec)
  probe-ade-bench-airbnb001-haiku.frozen.yaml (T0 frozen probe spec)
examples/specs/goal2/
  <task-slug>.yaml + .frozen.yaml + .frozen.provenance.yaml per task
docs/superpowers/plans/
  2026-05-19-goal2-haiku-baseline.md          (T6 result summary)
validation/
  goal2-provenance-sample.json                (T5 sampled provenance check)
runs/goal2/                                   (matrix output; gitignored)
  budget.json
  audit-aggregate.json
  score-aggregate.json
  <task-slug>/<job-hash>/result.json + trial subdirs + provenance.yaml
                       + score.json + audit.json
runs/goal2-probe/                             (T0 transient; gitignored)
```

Modified files: none in razorback core. The matrix runs against
existing v2 surfaces (`rk freeze`, `rk run`, `rk score`, `rk audit`)
+ PKG-19's already-merged bind-mount path; no further code changes.

## Out of scope

Carried from the entity body + extended by captain directive:

- N>1 trials. Captain directive 2026-05-20 scopes Goal 2 to N=1; a
  Goal-2-followup entity for N≥3 (with non-degenerate per-task CIs)
  is a separate piece of work.
- Comparison against other models (opus, sonnet) — Goal 2 is Haiku
  baseline only.
- `--against-constant` paper-reproduction framing — Goal 2 is an
  establishing measurement.
- Paired comparison against any other baseline — paired comparisons
  ship via `rk diff` (Phase 4b) when needed.
- Goal 1 (DAB paper reproduction). Separate entity:
  `goal1-dab-paper-reproduction`. Goal 2 plans on `main`, no
  worktree; Goal 1 plans in its own worktree at
  `.worktrees/spacedock-ensign-goal1-dab-paper-reproduction`.
- ade-bench task set extensions / modifications — Goal 2 runs against
  whatever is currently checked out at `~/git/ade-bench/tasks/`.
- harbor-native ade-bench adapter port — Goal 2 runs against the
  in-tree adapter + PKG-19 bind-mount path; a harbor-ade-bench port
  is a separate research question.
- ML-reviewer F1 stratum-collapse fix in `rk score` — known caveat
  carried into the result doc; the fix is a separate phase 4b
  follow-up.

## Depends on

- `phase4a-rk-score-wilson-stratified` — SHIPPED on main (`rk score`
  per-task Wilson CIs + stratified pass@1). Note: per-task CIs are
  degenerate at N=1 by construction; this plan's directive scopes
  the captain to that reality.
- `phase4a-rk-audit-taint-port` — SHIPPED on main (`rk audit
  --policy strict`).
- `phase4a-rk-run-budget-gate` — SHIPPED on main
  (`--max-budget-usd-running`).
- `phase4a-rk-runs-cost` — SHIPPED on main (cost ledger).
- `pkg8-v2-rk-freeze-pinning` — SHIPPED on main (extended `rk freeze`
  per AC-2's sealed-input set).
- `phase3-spacedock-solver-v2` — SHIPPED on main (v2 agent class +
  claude runtime; Haiku is a claude model).
- `phase1-rk-run-v2-wrapper` — SHIPPED on main (`rk run` base).
- `pkg17-rk-run-writes-rundir-artifacts` — SHIPPED on main (run-dir
  artifact contract).
- `pkg19-ade-bench-data-bind-mount` — SHIPPED on main
  (`AdeBenchLocalTaskEntry` + `ade_bench_root` bind-mount). Note:
  PKG-19's AC-7 (live ade-bench probe) was SKIPPED in validation due
  to sandbox blockers; T0 of this plan is the first live exercise of
  the bind-mount path through `rk run` against a real ade-bench task,
  and gates T1+ accordingly.
