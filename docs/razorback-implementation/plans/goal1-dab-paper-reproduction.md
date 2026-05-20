# Goal 1: DAB paper reproduction (opus-4.7 + hints × 3 variants × 12 datasets × N=5), Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to drive this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Entity:** `docs/razorback-implementation/goal1-dab-paper-reproduction.md`
(id `ayf9mczntgnp808z8ggpjzf4`).

**Goal.** Reproduce the dataagentbench paper's headline pass@1 result via
the v2 surface stack. The matrix shape is opus-4.7 + hints ON × three
workspace-README variants (`direct-minimal`, `direct-structured`,
`spacedock`) × 12 DAB datasets × N=5 trials = **180 cells**. Each cell
runs `rk freeze` → `rk run --max-budget-usd-running budget.json` →
`rk score --against-constant` → `rk audit --policy strict`. The
spacedock variant's stratified pass@1 is the primary reproduction claim
(against the paper's 0.577); the direct-baseline variants compare
against 0.4376.

## Blocker (read before any implementation)

**PKG-13 — harbor-DAB compose generator workdir-path correctness.**
T14's "100% pass@1 on bookreview" result (committed to
`docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`) is a
**false positive**. Captain's review of `docker ps` post-run showed no
containers running. Investigation surfaced two coupled defects in
`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py`
(and the prepare-layout it pairs with):

1. The generated `docker-compose.yaml` mounts
   `./workdir/query_dataset/books_info.sql` into postgres's
   `/docker-entrypoint-initdb.d/`, but the actual workdir under
   harbor's per-trial layout lives at `steps/main/workdir/`, not
   `workdir/`. The bind-mount source resolves to a non-existent host
   path; postgres starts with an empty data directory.
2. The emitted `task.toml` has no real verifier command (or the
   verifier short-circuits when the query DB is empty), so the
   verifier defaults to `reward=1.0`. The agent never queried any
   real data; the score is fictitious.

**Until PKG-13 lands, Goal 1 cannot produce meaningful numbers.**
PKG-13 must:
- correct the compose generator's bind-mount source path to match
  harbor's actual per-trial workdir layout (`steps/main/workdir/...`
  or equivalent, verified by inspecting an in-flight container's
  mount table);
- ensure the verifier is a real verifier (it queries postgres /
  mongo and compares against the expected result), so an empty DB
  produces `reward=0.0` and not the silent `1.0` default;
- ship a smoke that fails closed on the broken-mount scenario
  (e.g., a unit test that asserts the generated compose's
  bind-mount source resolves to a path that exists after the
  prepare step writes the workdir tree);
- re-run the T14-shape end-to-end smoke (N=3 on bookreview) and
  confirm `docker ps` shows the dab-postgres container alive
  during agent execution AND the verifier scores against real
  query output, not the empty default.

**Implementation gate.** Tasks T1 through T7 in this plan **do not
start** until PKG-13 is shipped, validated by the smoke above, and
the corrected bookreview N=3 result is appended to
`docs/superpowers/plans/2026-05-19-reconciliation-baseline.md` (the
T14 section gets a strikethrough or supersession note pointing at
the corrected run). The matrix-dispatch design in this plan is
valid; only the burn is blocked.

**Captain has been informed; further investigation dispatched.**

## Architecture

**Dispatch shape.** A bash matrix-driver script at
`examples/drivers/dab-paper-matrix.sh` iterates the 180-cell
Cartesian product and dispatches each cell as a sequence of four
`rk` invocations. Per spec §3.2:

```
for spec in matrix:
  rk freeze <spec> --allow-plugin-drift=false
  rk run --max-budget-usd-running budget.json <spec>.frozen.yaml \
      --runs-dir runs/goal1/<variant>/<dataset>/
  rk score --against-constant <variant-target> <run-dir>
  rk audit --policy strict <run-dir>
```

Idempotence is provided by `rk run`'s content-hash determinism on
`(jobs_dir, job_name)`: re-running the same frozen spec against the
same runs-dir is a no-op if the run-dir already exists with a clean
result. The driver detects this by checking for the run-dir's
`result.json` before invoking `rk run`; if present and clean, skip.

**Budget enforcement.** A single `budget.json` file is threaded
across all 180 invocations of `rk run --max-budget-usd-running`.
Per spec exit code 22, any cell whose pre-launch estimate would
push the running total over `experiment.max_budget_usd` (declared
as $500 in the matrix specs) refuses to dispatch. The driver
surfaces the refusal and exits non-zero; the captain decides
whether to raise the cap or stop.

**Cost-shape assumption** (validated in T0 below). T14 on opus-4.5
delivered $0 for 9 trials via subscription auth
(`CLAUDE_CODE_OAUTH_TOKEN`). The same auth path on opus-4.7 is
**unverified**. The driver's pre-flight checks the auth mode and
either confirms subscription billing or refuses to start without
captain acknowledgment of the per-trial API-billed cost estimate
($1.50-$3.00 per trial × 180 trials = $270-$540).

**Workspace variants.** The plugin emits three variants per dataset
via the spec-level `workspace_variant:` field (parsed by
`HarborDabBenchmarkBlock`). The matrix expands this to 3 specs per
dataset; the driver iterates the 3-spec set per dataset and
accumulates the per-variant run-dir tree.

**Scoring contract.** `rk score --against-constant` is invoked per
variant with the variant-specific reproduction target:

| Variant            | `--against-constant` target            | Source       |
|--------------------|----------------------------------------|--------------|
| `spacedock`        | `spacedock=0.577`                      | DAB paper    |
| `direct-minimal`   | `direct_baseline=0.4376`               | DAB paper    |
| `direct-structured`| `direct_baseline=0.4376`               | DAB paper    |

The verdict (inside-CI / outside-CI) per stratum is recorded in
the per-variant `rk score` JSON output committed alongside the
run-dir set.

**Audit.** `rk audit --policy strict <run-dir>` runs after each
cell. Per spec §3.2 exit code 23, a non-`clean` trial in any cell
exits non-zero; the driver pauses and surfaces the cell.

## Source of truth

- v2 spec: `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
  §3.2 (CLI subcommands), §6.2 (agent block), §6.4 (benchmark block),
  §8.1 (budget gate), §9.4 (audit). 
- Goal 1 entity: `docs/razorback-implementation/goal1-dab-paper-reproduction.md`
  (7 ACs; this plan covers all 7).
- Reconciliation plan AC-4a.12: `docs/superpowers/plans/2026-05-19-razorback-reconciliation-plan.md`
  (matrix-driver requirement).
- Pre-registered shift bands + T14 (now-known-false-positive) result:
  `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`.
- Phase 2 archive: `docs/razorback-implementation/_archive/phase2-dab-harbor-adapter.md`
  (3 variants × 12 datasets ported; matrix spec at
  `examples/specs/dab-claude-harbor-adapter.yaml`).

## AC-to-task map

| AC | Task |
|----|------|
| AC-1 | T2 (dispatcher script + dry-run) + T3 (idempotence) |
| AC-2 | T1 (matrix-spec generator emits frozen-spec set) + T6 (provenance.yaml sample check) |
| AC-3 | T4 (budget gate threading) |
| AC-4 | T5 (audit aggregation) |
| AC-5 | T5 (scoring step per variant) |
| AC-6 | T7 (result summary doc) |
| AC-7 | T4 (budget gate final check) |

## Riskiest contract first

Before the $300-$500 burn:

1. **PKG-13 ships** (external dependency; not in this plan's scope but
   blocks T1+).
2. **T0** (cost-shape verification) confirms opus-4.7 + subscription
   delivers $0 or the captain acknowledges API billing.
3. **AC-4a.13 mechanism smoke** (already required by Phase 4a) is
   re-run against the PKG-13-corrected bookreview adapter end-to-end:
   `rk freeze` + `rk run --max-budget-usd-running` +
   `rk score --against-constant` + `rk audit --policy strict` clean
   on a single (variant, dataset) cell at N=3.
4. The 180-cell matrix dispatches **only after** steps 1-3 are
   green.

## Tasks

### T0: Cost-shape verification (opus-4.7 subscription vs API)

Riskiest contract for the burn itself: confirm whether T14's $0
result on opus-4.5 generalizes to opus-4.7. Goal: avoid burning
$300-$500 of API budget on an unverified assumption.

- [ ] **Probe step 1: subscription tier coverage.** Check whether
      `CLAUDE_CODE_OAUTH_TOKEN`'s subscription tier covers opus-4.7
      (Claude Code subscription docs / account billing page; if
      ambiguous, run a single-trial smoke and inspect
      `agent_result.cost_usd`).
- [ ] **Probe step 2: 3-trial smoke on bookreview, opus-4.7.**
      Spec: `examples/specs/bookreview-claude-harbor-dab-n3.yaml`
      with `model: claude-opus-4-7`. Run on the PKG-13-corrected
      adapter. Inspect `result.json` `cost_usd` per trial.
- [ ] **Branch A (subscription covers opus-4.7).** Recorded as
      "$0/trial for the 180-cell matrix" in the budget ledger.
      Proceed to T1 without further captain gate.
- [ ] **Branch B (subscription does NOT cover opus-4.7).** Use the
      probe step 2's measured `cost_usd` × 180 to project the
      matrix cost. Set `experiment.max_budget_usd: 600` (20%
      headroom above the $500 estimate) in the matrix specs and
      surface to captain for explicit approval BEFORE T2 runs.
- [ ] **Capture the verification result** in
      `docs/superpowers/plans/2026-05-19-goal1-paper-reproduction.md`
      (the result-summary doc T7 will write; T0's section seeds
      that doc).

**Acceptance:** the cost-shape question is answered with measured
per-trial `cost_usd` before T2 dispatches anything beyond the smoke.

### T1: Matrix-spec generator

Emit the 36 frozen specs (3 variants × 12 datasets) the driver
iterates. Each spec carries opus-4.7 + hints ON + N=5 + the
$500 (or T0-Branch-B-determined) experiment cap.

- [ ] Write
      `examples/drivers/generate-dab-paper-matrix-specs.py`.
      Input: the 12-dataset catalog from
      `packages/razorback-plugin-dab/src/razorback_plugin_dab/datasets.py`;
      the 3 variants from `workspace_readme.py::WORKSPACE_VARIANTS`.
      Output: 36 specs at
      `examples/specs/goal1/{variant}/{dataset}.yaml`, each shaped
      like `examples/specs/dab-claude-harbor-adapter.yaml` but
      narrowed to one dataset + one variant + `model:
      claude-opus-4-7` + `hints: true` + `trials: 5` +
      `experiment.max_budget_usd: 500`.
- [ ] Run `uv run rk freeze` against each emitted spec; the
      generator commits the 36 `*.frozen.yaml` + `provenance.yaml`
      pairs under `examples/specs/goal1/` so the driver doesn't
      need to freeze at dispatch time. Per AC-2: each
      `provenance.yaml` includes `solver_workflow_hash`,
      `spacedock_skill_version`, `harbor_agent_kwargs_hash`,
      resolved model, image digest, agent CLI binary hash, prompt
      content hashes, harbor version, `tools_denied` populated with
      DAB's full DISALLOWED_TOOLS list.
- [ ] Unit test: generator emits exactly 36 specs; each parses
      against `HarborDabBenchmarkBlock`; each `provenance.yaml`
      carries the 9 fields named in AC-2.

### T2: Matrix-driver script — dry-run + dispatch loop

`examples/drivers/dab-paper-matrix.sh`. Bash, idiomatic, exits
non-zero on the first cell failure unless `--continue-on-fail` is
passed.

- [ ] **Flags.** `--budget <usd>` (default 500),
      `--output-dir <path>` (default `runs/goal1/`),
      `--dry-run` (print the 180-cell plan without dispatching),
      `--continue-on-fail` (skip past failed cells, accumulate
      failures for end-of-run report).
- [ ] **Dispatch loop.** Iterate the 36 frozen specs × 5 trials
      (the 5-trial replication is via the spec's `trials: 5`
      field, so the loop is 36 specs not 180; each `rk run`
      handles its own N=5). For each spec:
      `rk run --max-budget-usd-running <budget.json>
      <spec.frozen.yaml> --runs-dir <output-dir>/<variant>/<dataset>/`.
- [ ] **Per-cell post-run.** Immediately after `rk run` returns
      success, dispatch `rk audit --policy strict <run-dir>`. On
      audit failure (exit 23), pause with a captain-prompt and
      record the tainted finding to a failure ledger.
- [ ] **Dry-run output.** A 36-line table listing
      `(variant, dataset, frozen_spec_path, projected_runs_dir)`
      ordered by variant then dataset. Total trial count
      `36 × 5 = 180` printed at the bottom.
- [ ] **Per-AC-1 acceptance test.** Bash-level test (or shellcheck
      + `--dry-run` snapshot) asserts the dry-run output is
      deterministic and lists all 36 cells.

### T3: Idempotence + partial-resume

The driver re-runs cleanly after a partial failure. Each cell's
"already done" check is a filesystem read on the expected
run-dir's `result.json`.

- [ ] Before each `rk run` invocation, check whether
      `<runs-dir>/<job-name>/<content-hash>/result.json` exists
      AND `result.json::stats.n_completed_trials >= 5` AND
      `result.json::stats.n_errored_trials == 0`. If so, skip.
- [ ] If the run-dir exists but `n_completed_trials < 5` (partial
      run from a prior interrupted attempt), let `rk run` resume
      it; razorback's harbor-pass-through handles the trial-count
      reconciliation (per spec §5.2's run-workflow contract,
      mirrored here at the driver level).
- [ ] **Idempotence acceptance test.** Dispatch with `--dry-run`,
      manually drop one cell's run-dir to look "completed" (touch
      a stub `result.json` with `n_completed_trials: 5,
      n_errored_trials: 0`), re-dispatch, confirm that cell is
      skipped and the final state is the same as a fresh
      dispatch.

### T4: Budget gate threading

The single `budget.json` file is the matrix's running cost ledger.
`rk run --max-budget-usd-running` reads and writes it atomically;
the driver passes the same path on every invocation.

- [ ] Driver initializes `budget.json` to `{"total_usd": 0.0,
      "spent_usd": 0.0, "max_usd": <budget>}` if absent.
- [ ] Driver passes `--max-budget-usd-running budget.json` to every
      `rk run`. The flag's pre-launch estimate + write-on-completion
      semantics are razorback-shipped per
      `docs/razorback-implementation/_archive/phase4a-rk-run-budget-gate.md`.
- [ ] **Budget acceptance test (AC-3, AC-7).** Fixture test
      simulates a matrix-level budget overage mid-dispatch (set
      `max_usd` to a value the third cell would exceed; assert
      that the third `rk run` invocation refuses with exit 22 and
      the driver surfaces the refusal + pauses).

### T5: Per-cell + aggregate scoring + audit

Two per-cell artifacts and two aggregate artifacts.

- [ ] **Per-cell scoring.** After each cell completes, the driver
      dispatches `rk score --against-constant <target>
      <run-dir> --format json > <run-dir>/score.json` where
      `<target>` is `spacedock=0.577` for the spacedock variant
      and `direct_baseline=0.4376` for the two direct variants.
- [ ] **Per-cell audit.** `rk audit --policy strict
      <run-dir> --format json > <run-dir>/audit.json`. The
      driver collects audit.json files into an aggregate
      `audit-aggregate.json` (sum of `n_tainted` across all
      cells; AC-4 requires 0).
- [ ] **Aggregate per-variant scoring.** A wrapper script
      `examples/drivers/aggregate-goal1-scores.py` reads the 12
      per-cell `score.json` files per variant and computes the
      stratified-mean pass@1 across the 12 strata (each dataset
      is one stratum). Output:
      `runs/goal1/<variant>/aggregate-score.json` with the
      stratified mean + Wilson 95% CI + per-stratum verdicts
      (inside-CI / outside-CI vs the variant's target).
- [ ] **Aggregate audit.** A wrapper reads all 180 cells'
      `audit.json` and emits
      `runs/goal1/audit-aggregate.json` with `n_tainted` summed
      across the matrix.

### T6: Provenance spot-check (AC-2)

- [ ] Driver writes a `validation/goal1-provenance-sample.json` at
      end-of-matrix that loads one randomly-sampled cell's
      `provenance.yaml` and asserts it carries the 9 fields named
      in AC-2 (`solver_workflow_hash`, `spacedock_skill_version`,
      `harbor_agent_kwargs_hash`, resolved model alias, image
      digest, agent CLI binary hash, prompt content hashes,
      harbor version, `tools_denied`).
- [ ] If any field is missing/null, the validation file flags it
      and the driver exits non-zero before the result summary is
      written.

### T7: Result summary doc

`docs/superpowers/plans/2026-05-19-goal1-paper-reproduction.md`.
The post-burn artifact; AC-6 deliverable.

- [ ] **Sections.**
  1. Cost-shape verification (T0's output: subscription tier or
     API-cost projection).
  2. Headline (per-variant stratified pass@1 + Wilson 95% CI +
     `--against-constant` verdict for the primary
     reproduction claim).
  3. Per-variant × per-dataset table (36 rows: variant ×
     dataset → pass@1 + CI + `--against-constant` verdict
     where applicable).
  4. Audit (per-cell pass/fail + aggregate `n_tainted`).
  5. Cost ledger (final `budget.json` total + per-variant
     subtotal if available from `rk runs cost
     --root runs/goal1/<variant>/`).
  6. Run-dir paths (one row per variant; each row cites the
     run-dir for the 12 datasets in that variant).
- [ ] **Reproduction verdict.** A 1-sentence headline in section 2:
      "DAB paper headline (spacedock variant, opus-4.7 + hints
      ON, N=5 × 12 datasets): observed stratified pass@1 = <X>;
      paper's published = 0.577; verdict: <reproduced |
      not-reproduced | partially-reproduced>." Same shape for
      the direct-baseline variants against 0.4376.
- [ ] **Each subsection cites the underlying run-dir paths** (per
      AC-6: "each subsection cites the underlying run-dir paths").

## Test plan

- **PKG-13 smoke (external blocker).** Bookreview N=3 end-to-end
  via the PKG-13-corrected adapter; `docker ps` confirms
  dab-postgres alive; verifier scores against real query output;
  `rk score` reports a believable (NOT 100%) number on
  bookreview-q1/q2/q3 with subscription-billed cost telemetry
  inspected.
- **T0 cost-shape probe.** Opus-4.7 single-trial smoke result is
  $0 (subscription) or a measured `cost_usd` is recorded and
  multiplied through to project the matrix cost.
- **AC-4a.13 mechanism smoke.** `rk freeze` → `rk run
  --max-budget-usd-running` → `rk score --against-constant` → `rk
  audit --policy strict` chain runs clean on a single
  (variant, dataset) cell at N=3 BEFORE the 180-cell burn.
- **Dry-run test.** `bash examples/drivers/dab-paper-matrix.sh
  --dry-run` prints the 36-cell × 5-trial plan without invoking
  `rk run`.
- **Idempotency test.** Partial dispatch → interrupt → re-dispatch
  produces the same final state as a single fresh dispatch.
- **Budget-gate fixture test.** Simulated mid-dispatch overage:
  `rk run` exits 22 on the third cell; driver surfaces the
  refusal and pauses (AC-3, AC-7).
- **Aggregate audit test.** `rk audit --policy strict` across all
  180 cells reports `n_tainted: 0` (AC-4).
- **Acceptance command.** `bash
  examples/drivers/dab-paper-matrix.sh --budget 500
  --output-dir runs/goal1/` exits 0 after dispatching all 180
  cells; the result summary doc lands at
  `docs/superpowers/plans/2026-05-19-goal1-paper-reproduction.md`
  with all 6 sections populated.

## File structure

New files (under razorback root):

```
examples/drivers/
  dab-paper-matrix.sh                    (T2/T3/T4/T5 dispatcher)
  generate-dab-paper-matrix-specs.py     (T1 spec generator)
  aggregate-goal1-scores.py              (T5 aggregate scoring)
examples/specs/goal1/
  spacedock/{12 datasets}.yaml + .frozen.yaml + provenance.yaml
  direct-minimal/{12 datasets}.yaml + .frozen.yaml + provenance.yaml
  direct-structured/{12 datasets}.yaml + .frozen.yaml + provenance.yaml
docs/superpowers/plans/
  2026-05-19-goal1-paper-reproduction.md (T7 result summary)
runs/goal1/                              (matrix output; gitignored)
  budget.json
  audit-aggregate.json
  spacedock/<dataset>/<job-hash>/...
  direct-minimal/<dataset>/<job-hash>/...
  direct-structured/<dataset>/<job-hash>/...
validation/
  goal1-provenance-sample.json           (T6 sampled provenance check)
```

Modified files: none in razorback core; the matrix runs against
existing v2 surfaces (`rk freeze`, `rk run`, `rk score`,
`rk audit`, `rk runs cost`) without further code changes.

## Out of scope

Carried from the entity body:

- Goal 2 (ade-bench Haiku baseline).
- Paper publication / write-up beyond the result summary doc.
- Cross-model comparison (sonnet, haiku).
- N>5 trials.
- Failure-mode analysis of failed trials (deferred to
  `pkg11-failure-mode-analysis-workflow`).
- PKG-13 itself (the harbor-DAB compose generator bind-mount fix).
  This plan blocks on PKG-13; the fix is a separate work stream.

## Depends on (verbatim from entity body)

- `phase4a-rk-score-wilson-stratified` (analyze command — `rk
  score --against-constant`) — SHIPPED on main.
- `phase4a-rk-audit-taint-port` (`rk audit --policy strict`) —
  SHIPPED on main.
- `phase4a-rk-run-budget-gate` (`--max-budget-usd-running`) —
  SHIPPED on main.
- `phase4a-rk-runs-cost` (cost ledger) — SHIPPED on main.
- `72` pkg8-v2-rk-freeze-pinning (extended `rk freeze` per AC-2's
  sealed-input set) — SHIPPED on main.
- `v4` pkg9-v2-tools-denied-field (PreToolUse hook installation;
  DAB DISALLOWED_TOOLS list) — SHIPPED on main.
- `phase3-spacedock-solver-v2` (v2 agent class + per-runtime
  adapter for claude) — SHIPPED on main.
- `phase2-dab-harbor-adapter` (harbor-DAB adapter the matrix runs
  against) — SHIPPED on main; **but see PKG-13 blocker above**.
- `phase1-rk-run-v2-wrapper` (`rk run` base) — SHIPPED on main.
- AC-4a.13 mechanism-validation smoke clean (every surface
  exercised at N=3 bookreview before the $300-500 burn) —
  **BLOCKED on PKG-13**.
- **PKG-13 — harbor-DAB compose generator workdir-path correctness**
  (NEW; see Blocker section). Goal 1 implementation cannot begin
  until PKG-13 ships and the corrected bookreview smoke result
  supersedes T14's false-positive entry in the baseline doc.
