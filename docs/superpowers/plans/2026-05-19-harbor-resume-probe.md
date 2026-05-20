# Harbor jobs resume probe — AC-0.5

**Date:** 2026-05-20
**Resolves:** AC-0.5 in `2026-05-19-razorback-reconciliation-plan.md`

## Verdict

CONFLICT. `harbor jobs resume` rmtree's any trial directory that is
missing `result.json`, then re-runs the trial under a freshly randomised
`trial_name`. Razorback's `agent_freeze/` subtree, sealed inside the
trial dir, is destroyed on resume; the only state razorback may rely on
across a harbor resume is state belonging to trials that already wrote
`result.json` (i.e., trials harbor considers *complete*).

## Harbor's resume algorithm

The CLI surface is `harbor jobs resume -p <job-dir>`
(`harbor/cli/jobs.py:1361-1430`). `<job-dir>` is consulted only to load
`config.json` (jobs.py:1444-1477); the rest of the resume scans the
*config's* `jobs_dir / job_name` directory, **not** the path passed to
`-p`. (This bit me on the first attempt and is worth flagging.)

The resume CLI:

1. Optionally rmtree's trials whose `result.json` has an
   `exception_info.exception_type` in `--filter-error-type`
   (default: `CancelledError` only) — jobs.py:1452-1475.
2. Loads the same `JobConfig` and calls `await Job.create(config)`
   (jobs.py:1499).
3. `Job.__init__` calls `_maybe_init_existing_job`
   (`harbor/job.py:104, 192-228`), which is the resume entry point and
   does the work below.
4. Calls `await job.run()`, which executes only the trials produced by
   `_init_remaining_trial_configs` (job.py:107, 263-293).

`_maybe_init_existing_job` (job.py:192-228) does, for every subdir of
`self.job_dir`:

```python
trial_paths = TrialPaths(trial_dir)
if not trial_paths.result_path.exists():
    shutil.rmtree(trial_paths.trial_dir)      # job.py:220-221
else:
    self._existing_trial_configs.append(...)
    self._existing_trial_results.append(...)
```

That is: **any trial directory lacking `result.json` is recursively
deleted**, including `agent/agent_freeze/.git`, `agent/agent_freeze/
phase_stats.json`, and `agent/agent_freeze/sealed_hash.txt`.

Surviving trials (those with `result.json`) are kept verbatim; their
`TrialConfig` is read from disk and used by
`_init_remaining_trial_configs` to skip them in the next run.

Trials that need re-execution get a fresh `TrialConfig` whose
`trial_name` is regenerated via
`f"{task_name[:32]}__{ShortUUID().random(length=7)}"`
(`harbor/models/trial/config.py:213-222`). The new `trial_name` does
**not** match the rmtree'd one — `__qRkNdkY` becomes `__wMGYfz7` in our
probe — so even if razorback wrote `agent_freeze/` to a sibling
location keyed by `trial_name`, the re-execution would not find it.

## Fixture and execution

- Fixture run-dir: `/tmp/razorback-resume-probe/logs-fixture/resume-probe/`
- Construction method:
  1. Ran `harbor run -c spec.yaml` with `agents: [{name: nop}]` and the
     `examples/tasks/hello-world` task to produce a known-good
     baseline run-dir at `/tmp/razorback-resume-probe/logs/resume-probe/`.
     The trial errored with `RewardFileNotFoundError` (nop writes
     nothing), but harbor wrote `result.json`, so the trial is
     "complete" from harbor's point of view.
  2. `cp -r` the baseline into `logs-fixture/resume-probe/`.
  3. Rewrote `logs-fixture/resume-probe/config.json` to set
     `jobs_dir: /tmp/razorback-resume-probe/logs-fixture` so harbor's
     `self.job_dir` would resolve to the fixture path (without this,
     harbor scans the *baseline* dir and the probe is invalid — see
     "Caveat" below).
  4. Inside the trial dir `hello-world__qRkNdkY/`:
     - created `agent/agent_freeze/.git/HEAD` (placeholder),
     - wrote `agent/agent_freeze/sealed_hash.txt` with token
       `RAZORBACK_TOKEN_1779253546`,
     - wrote `agent/agent_freeze/phase_stats.json` with a fake stage
       record,
     - **deleted `result.json`** to mark the trial incomplete.
  5. Deleted the stale `lock.json` at the job root.

- Invocation:
  ```
  DOCKER_CONFIG=… DOCKER_HOST=… HOME=/tmp/razorback-resume-probe-home \
  uv run harbor jobs resume \
      -p /tmp/razorback-resume-probe/logs-fixture/resume-probe
  ```

- Observed behaviour: exit 0 after ~13 s. Stdout:
  ```
  1/1 Mean: 0.000 …
  adhoc • nop
  Trials │ Exceptions │ Mean
       0 │          1 │ 0.000
  Exception                │ Count
  RewardFileNotFoundError  │     1
  ```
  Stderr empty.

- Post-resume on-disk state:
  - `hello-world__qRkNdkY/` — **gone**.
  - `hello-world__wMGYfz7/` — new trial dir, populated with
    `config.json`, `result.json`, `trial.log`, `exception.txt`, empty
    `agent/`, empty `verifier/`, empty `artifacts/`.
  - `agent/agent_freeze/` — **not present** anywhere under the job
    dir. `sealed_hash.txt` token unrecoverable.
  - Job-level `result.json`, `job.log`, `lock.json` rewritten.

- Caveat from the first (invalid) attempt: on the initial probe I
  passed `-p logs-fixture/…` but left `jobs_dir: /tmp/razorback-resume-
  probe/logs` inside the config. Harbor read the config from
  `logs-fixture/` but resolved `job_dir` from the config to
  `logs/resume-probe/` (the pristine baseline, which still had its
  `result.json`), so harbor declared the trial complete and did
  nothing to `logs-fixture/`. This made the agent_freeze tree appear
  to survive when it had simply never been scanned. The corrected
  fixture (config jobs_dir aligned with the on-disk location) shows
  the rmtree.

## Conflict analysis vs spec §4.4

Spec §4.4 (`docs/superpowers/specs/2026-05-19-razorback-on-harbor.md:
373-396`) makes the trial's `logs_dir/agent_freeze/` the
contractual on-disk surface between `SpacedockSolverAgent` and the
workflow mods. It contains:

- `.git/`, the private workspace history per stage,
- `phase_stats.json`, per-stage tokens / cost / wallclock,
- `sealed_hash.txt`, the sealed-input hash.

Section §4 also specifies the resume entry point (spec lines 363-366):
"If `resume_from_freeze` is set, read the prior run's freeze … restore
the trial workspace from the freeze's embedded git before invoking the
inner runtime so the runtime sees mid-workflow state and resumes."

Conflicts between this contract and harbor's resume:

1. **In-place resume of a halted trial is impossible.** If
   `SpacedockSolverAgent` halts mid-trial (process killed, container
   evicted, `harbor run` Ctrl-C'd) and the trial's `result.json` has
   not yet been written, harbor's resume rmtree's the entire trial
   dir, taking `agent_freeze/.git`, `phase_stats.json`, and
   `sealed_hash.txt` with it. The sealed-hash invariant is gone (no
   on-disk record of the sealed inputs the prior run committed to),
   and the per-stage workspace snapshots are gone.
2. **Stable `trial_name` cannot be relied on.** A re-executed trial
   gets a new random suffix (`__wMGYfz7` in our probe). Any razorback
   logic that keys off the prior trial directory's name — for example
   "look in `<prior-job-dir>/trials/<task>-<N>/agent/agent_freeze/`
   for resume material" — must be told the new name, not just the
   old one.
3. **`resume_from_freeze` (spec §4 line 363) is incompatible with
   `harbor jobs resume`.** Spec §4's resume is *cross-job*: take a
   freeze from job A and feed it as `resume_from_freeze: <path>` into
   job B. Harbor's resume is *intra-job*: continue job A in place.
   These are not the same mechanism. Cross-job resume sidesteps the
   rmtree (it reads from a separate path the operator points
   razorback at). Intra-job resume after a halt does not work under
   harbor's contract.
4. **No partial-credit recovery.** Even completed *stages* of an
   incomplete trial are wiped. Razorback's "per-stage cost
   attribution" downstream consumers (spec §4 line 389-391) cannot
   recover stage data from an incomplete trial after a resume — the
   `phase_stats.json` is gone.

These are CONFLICTS, not mere semantic mismatches. Razorback's
documented `agent_freeze/` survival assumption is empirically false
under `harbor jobs resume`.

## Recommendation

Razorback's runtime adapter MUST treat harbor's resume as a
**re-execution**, not a continuation, for any incomplete trial. To
preserve halt-resume semantics across a harbor resume, the freeze
subtree has to live **outside** harbor's per-trial scratch zone.

Three workable strategies, ordered by simplicity:

1. **Mirror `agent_freeze/` to a razorback-owned path at every stage
   commit.** When `SpacedockSolverAgent` writes
   `self.logs_dir / "agent_freeze/"`, also write (or `git push`) the
   same content to
   `<spec.frozen.yaml dir>/freezes/<sealed_hash>/<trial_name>/`.
   The sealed-hash component lets a cross-job resume locate the
   freeze by the spec's sealed identity even after `trial_name`
   changes. This is the most aligned with spec §7 (run-dir contract
   already owns the spec.frozen.yaml dir).

2. **Treat harbor's intra-job resume as out-of-scope.** Document
   that `rk run` does not survive `harbor jobs resume` for in-flight
   trials, and that operators must use razorback's cross-job
   `resume_from_freeze` mechanism (point a new `rk run` at the prior
   job's freeze dir at `<spec.frozen.yaml dir>/freezes/…`). This
   requires (1) as a precondition anyway.

3. **Replace `harbor jobs resume` with an `rk resume` wrapper that
   re-stages freezes from the razorback-owned mirror before invoking
   `harbor jobs resume`.** Cosmetic on top of (1); useful for UX
   parity with harbor.

Spec change recommended: edit §4.4 to add a "harbor-resume
interaction" paragraph naming the rmtree behaviour and pointing at
the freeze-mirror solution. Plan AC-0.5 was the right place to find
this; the spec should now be made truthful before §4.4 is shipped to
implementation.

Also recommended (independent): document the `-p` vs config
`jobs_dir` mismatch in razorback's CLI docs. `rk run` should ideally
keep these aligned by always writing the config's `jobs_dir` to the
same place the run-dir physically lives, so an operator running
`harbor jobs resume -p <razorback-emitted-dir>` does not silently
target a different dir.
