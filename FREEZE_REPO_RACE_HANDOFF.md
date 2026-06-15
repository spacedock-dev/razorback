# Handoff: spacedock_solver freeze-repo concurrency race (blocks `trials > 1`)

> **RESOLVED 2026-06-15 (Fix A — per-cell freeze isolation).**
> `resolve_freeze_dir()` now returns `<cas-root>/<sealed_hash>/<cell_token>`,
> where `<cell_token>` = `sha256(trial_name or resolved logs_dir)[:16]`
> (`src/razorback/agents/spacedock_solver.py`, `resolve_freeze_dir` /
> `_cell_token` / `_trial_name`). Every concurrent cell commits to its OWN git
> repo, so concurrent stage commits never contend for one `HEAD` ref lock.
> Host-side-only change — the per-cell subdir lives under the bind-mounted
> freeze root, so the container surface is unaffected.
>
> **Trade-off taken (deliberate):** the sealed_hash-only shared CAS (AC-2:
> cross-worktree discovery + jobs-resume-by-regenerated-trial-name dedup) is
> dropped. Within-cell resume (same `logs_dir`) is preserved. Preserving
> cross-restart dedup too would need a stable per-attempt index that harbor's
> `generate_trial_name()` does not expose.
>
> Regression test: `tests/integration/test_freeze_concurrent_trials_isolated.py`.
> The three AC-2 tests were reframed to the per-cell contract
> (`test_spacedock_solver_freeze_dir_mechanism.py`,
> `test_spacedock_solver_lifecycle.py`, `test_freeze_cross_worktree_discovery.py`);
> `test_freeze_cas_resume_no_agent_invocation.py` still passes unchanged.

**Author:** ade-bench operator session, 2026-06-08
**Repo pin:** both clones (`~/razorback` and `~/autobench/razorback`) at `f5914db`
(`Merge pull request #7 … fix/dbt-hub-proxy-allowlist`); `seal.py` and
`spacedock_solver.py` byte-identical between them, so the file:line refs below are valid
in this offline clone.

---

## TL;DR / the ask

When a `spacedock_solver` run uses `concurrency.trials > 1`, trials abort almost
immediately with:

```
SpacedockSolverAgentError: freeze repo git failed at: git -C <freeze>/<sealed_hash> commit -q --allow-empty -m "stage: …"
(rc=128); stderr="fatal: cannot lock ref 'HEAD': is at <X> but expected <Y>"
```

**Root cause:** every cell of a run (all 48 tasks × all trials) computes the **same
`sealed_hash`**, so they all `git commit` into **one shared freeze repo**. Concurrent
commits race on the `HEAD` ref lock and the loser aborts.

The current spec dodges this by pinning `trials: 1`. That leaves a **single-trial variance
wall** (~±2 incidental flips/run on gpt-5.5@xhigh; paired 95% CI ≈ [−4, +4] tasks at n=48)
that is *wider than a real +1 lever's signal* — which is why the oracle-problem program
ended at +0 despite owning one genuine, artifact-proven fix (airbnb009) it could not bank.
**Making `trials > 1` safe is the highest-leverage unblock for the whole research loop.**

**Please fix the freeze-repo isolation so concurrent cells don't share one git repo.**
Details, exact mechanism, two candidate fixes, and a verification recipe below.

---

## Why this matters (1 paragraph, skip if you only want the bug)

At `trials: 1` we cannot average out gpt-5.5 run-to-run noise, and a do-no-harm tripwire
("paired CI must exclude a regression") is *structurally unsatisfiable* for a +1 lever — the
CI is wider than the signal. The fix turns single-trial roulette into a measurable paired
delta: it banks the existing airbnb009 fix (→ 32/48) and, more importantly, makes **every
future candidate** measurable above the noise floor. Full strategic context:
`~/autobench/ade-bench/hypotheses/_proposal/retrospective-2026-06-07.md` §2.1.

---

## The verified mechanism (with file:line)

All paths relative to `src/razorback/`.

1. **One freeze root per RUN, bind-mounted into every cell.**
   `translate.py:489` — `host_freeze_root = run_dir / "_razorback" / "freeze"`, created once
   and bind-mounted into each cell's container. So the freeze tree is shared at the run level
   by construction. (Confirmed on disk: every ade-bench run dir's `_razorback/` contains only
   `freeze`.)

2. **Within that root, the subdir is keyed ONLY by `sealed_hash`.**
   `agents/spacedock_solver.py:282` — `resolve_freeze_dir()` returns
   `resolve_default_freeze_dir() / self.sealed_hash`. No task component, no trial component in
   the path.

3. **`sealed_hash` collapses to one value for the whole ade-bench run.**
   - `agents/seal.py:18-32` — `compute_sealed_hash(...)` params include `benchmark_task_id`
     but **no trial index**.
   - `agents/seal.py:68-82` — `task_identity` (which carries `benchmark_task_id`) is added to
     the hashed payload **only if** `benchmark_kind / benchmark_task_id / batch_mode /
     child_task_ids_hash` is non-None.
   - `agents/spacedock_solver.py:192-214` — the agent tries to fill `benchmark_task_id` from
     `_discover_task_identity_from_manifest()` and feeds it to `compute_sealed_hash`.
   - `agents/spacedock_solver.py:299-330` — that discovery reads
     `run_dir/_razorback/task_views/*/view_manifest.json`. **It returns `{}` whenever that
     dir is absent** (`spacedock_solver.py:313`).
   - **EVIDENCE (decisive): `task_views` is never written on the ade-bench path.** All 50
     ade-bench run dirs under `~/autobench/ade-bench/runs/` have `_razorback/freeze` and **no
     `_razorback/task_views`**. So discovery always returns `{}` → `benchmark_task_id` is
     always None → `task_identity` is always omitted → **all cells hash identically.**

4. **The race site.** Each pipeline stage checkpoints by committing to that one repo:
   `agents/spacedock_solver.py:348-356` (`_commit_stage` → `_host_git("commit", …)`), and
   `_host_git` raises `SpacedockSolverAgentError` on non-zero rc
   (`spacedock_solver.py:332-346`). Git's `HEAD` update is a compare-and-swap; two concurrent
   commits to the same repo → one sees `HEAD` moved → `cannot lock ref 'HEAD'` → that cell
   dies before/while the agent runs. `trials > 1` simply multiplies the number of cells
   contending for the one repo, which is why turning trials up surfaces it.

> Note I did **not** fully trace harbor's host-vs-container freeze resolution (the freeze tree
> is bind-mounted into the container at `SPACEDOCK_SOLVER_CONTAINER_FREEZE_ROOT`, while
> `_host_git` runs host-side via `resolve_default_freeze_dir()`), nor harbor's exact cell
> concurrency loop. The collision is reproducible regardless; those details only matter for
> choosing *where* to inject the per-cell discriminator (see fixes).

---

## The crucial nuance: per-task is necessary but NOT sufficient

The older note in MEMORY framed the fix as "make the freeze repo per-task (pass
`benchmark_task_id` into `compute_sealed_hash`)." That is correct for **separating tasks**,
but it does **not** make `trials > 1` safe on its own:

- `sealed_hash` has **no trial identifier** (`seal.py:18-32`), and `resolve_freeze_dir`
  appends no trial component (`spacedock_solver.py:282`).
- So even with per-task identity working, **two trials of the *same* task still compute the
  same `sealed_hash` → same freeze repo → still race.**

**To make `trials > 1` safe you need per-(task, trial) freeze isolation, not just per-task.**
This is the key thing to get right.

---

## Reproduce

1. Take any `spacedock_solver` spec (e.g. `~/autobench/ade-bench/specs/baseline.yaml`), set
   `concurrency.trials: 2` (or higher), freeze it.
2. Run it (it does not need all 48 tasks — 2–3 tasks at trials:2 with images pre-built is
   enough; pre-building makes cells hit the same checkpoint in lockstep and reliably exposes
   the race).
3. Observe trials aborting ~0.06s into `agent_execution` with `cannot lock ref 'HEAD'`.
4. Confirm shared repo: during the run, `ls <run>/_razorback/freeze/` shows **one**
   `<sealed_hash>` dir, and `git -C <that dir> log --oneline` shows commits from **multiple
   tasks/trials interleaved**.

---

## Candidate fixes (ranked)

### Fix A — per-cell freeze dir in `resolve_freeze_dir` (smallest, most robust)
Append a per-cell discriminator to the freeze path so isolation never depends on the seal:

- In `agents/spacedock_solver.py:270-282`, change `resolve_freeze_dir()` to return
  `resolve_default_freeze_dir() / self.sealed_hash / <cell_token>`, where `<cell_token>` is a
  stable function of this cell's identity. The agent already derives `trial_name` from
  `self.logs_dir` at `spacedock_solver.py:307-311` (logs_dir is unique per trial) — reuse
  that (e.g. a short sha256 of the resolved `logs_dir` or `trial_name`).
- **Pro:** ~3 lines; guarantees per-cell isolation independent of whether `task_views` is
  ever written; fixes both the task-collision and the trial-collision at once.
- **Con / watch:** the freeze CAS is intentionally keyed by `sealed_hash` so that re-running
  the *same* spec resumes from an existing freeze (`spacedock_solver.py:270-282` docstring,
  AC-5; resume validates `sealed_hash.txt` at `setup()`, `spacedock_solver.py:443-463`).
  Per-cell subdirs preserve **within-trial** resume (the trial finds its own subdir) but drop
  **cross-run CAS dedup**. For the benchmark loop that dedup isn't needed; just confirm no
  resume/halt-resume test asserts the cross-run behavior before committing.

### Fix B — feed real task + trial identity into the seal (matches original design intent)
Make the data the code already expects actually exist, and add the missing trial axis:

1. **Task axis:** ensure `benchmark_task_id` reaches the agent on the ade-bench path —
   either (i) write `run_dir/_razorback/task_views/<prefix>/view_manifest.json` carrying
   `benchmark_task_id` (the consumer at `runs/aggregate.py:130-137` already expects this
   manifest, so wiring its *producer* on the ade-bench path is consistent with the design),
   or (ii) pass `benchmark_task_id` explicitly into the `SpacedockSolverAgent` constructor
   from the harbor task (most robust — no manifest-discovery dependency).
2. **Trial axis:** add a trial identifier to `compute_sealed_hash` (`seal.py:18-93`) — or to
   the freeze path — so two trials of one task don't collide. Without this, Fix B still races
   at `trials > 1` (see "crucial nuance" above).
- **Pro:** keeps the CAS/resume design semantically meaningful (freeze keyed by genuine
  sealed inputs); fixes `_discover_task_identity_from_manifest` being silently inert.
- **Con:** larger surface (producer wiring + seal-shape change + frozen-spec compatibility:
  changing the seal payload changes `sealed_hash`, so check `spec/freeze.py:54` and
  `provenance/freeze_cmd.py:175` and any pinned `sealed_hash` in frozen specs / golden tests).

### Stopgap — no code change (already usable today)
Concurrent commits are the problem, so avoid concurrency: run a **lever-alone** spec
**sequentially** several times (each `trials: 1`, back-to-back) and compute the paired delta
across runs. Sequential runs never commit to the freeze repo at the same instant, so they
dodge the race entirely. Slower, and doesn't help genuinely-parallel runs, but it banks a +1
without touching razorback.

---

## How to verify a fix

1. With the fix applied, run a spec at `trials: 2` over a handful of tasks (images
   pre-built). **Expect zero `cannot lock ref 'HEAD'` errors.**
2. During/after the run, confirm isolation: `<run>/_razorback/freeze/` should now contain a
   **distinct freeze dir per cell** (per-task and per-trial), and each `git log` should show
   commits from **only one** task/trial.
3. Confirm resume still works: re-run the same spec; cells should resume from their own freeze
   (no `SeedMismatchError`, no re-invocation of the agent for already-completed stages).
4. Then the research payoff: a multi-trial paired re-confirm of E2/airbnb009 alone (vs
   @baseline `runs/ade-bench-baseline/622bdedac572b479`) should separate its +1 from noise.

---

## File map (quick reference)

| Concern | Location |
|---|---|
| Per-run freeze root + bind mount | `src/razorback/translate.py:478-502` (`host_freeze_root`, line 489) |
| Freeze dir resolution (no task/trial component) | `src/razorback/agents/spacedock_solver.py:270-282` |
| Freeze-dir env precedence | `src/razorback/freeze_dir_default.py` (`$RAZORBACK_FREEZE_DIR` > `$XDG_DATA_HOME/...` > `~/.local/share/...`) |
| sealed_hash computation (no trial axis) | `src/razorback/agents/seal.py:18-93` |
| task_identity gating in the seal | `src/razorback/agents/seal.py:68-82` |
| Task-identity discovery (inert on ade-bench) | `src/razorback/agents/spacedock_solver.py:192-214, 299-330` |
| Stage commit (race site) + host git wrapper | `src/razorback/agents/spacedock_solver.py:332-356` |
| Setup / resume / sealed_hash.txt validation | `src/razorback/agents/spacedock_solver.py:436-463` |
| view_manifest consumer (producer is the gap) | `src/razorback/runs/aggregate.py:130-137`; `src/razorback/harbor_tasks/manifest.py` |

**Evidence artifacts:** `~/autobench/ade-bench/runs/*/_razorback/` (50 dirs, all `freeze`-only,
no `task_views`). Strategic context: `~/autobench/ade-bench/hypotheses/_proposal/retrospective-2026-06-07.md`.
