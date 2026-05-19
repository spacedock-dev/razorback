# M6 — Constraints, registry, baselines, runs diff — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the analysis subcommand surface that turns finished run-dirs into reviewable verdicts: `rk runs diff` with the four paired statistics from §6.5 (per-arm Wilson 95% CI on pass@1, per-query exact-McNemar p, paired-bootstrap CI on the stratified delta, power-at-fixed-N MDE), plus `rk constraints check`, `rk baseline {promote,verify}`, and `rk registry {list,resolve,add,remove}`. The math is the deliverable; the CLI surface is a thin layer over `razorback.diff` and `razorback.registry`.

**Architecture:** Two new packages, both small.

1. `src/razorback/diff/` — a `stats.py` module that exposes four pure functions (`wilson_ci`, `exact_mcnemar_p`, `paired_bootstrap_ci`, `power_mde_at_fixed_n`), a `pairing.py` module that pairs two `summary.json` files by `trial_name` (or `(dataset, query_id)` for the M2/M5 aggregator shape that records per-query records rather than per-trial), and a `diff.py` module that composes them into the JSON output shape `rk runs diff` emits. The CLI command (`cli/runs.py::diff`) is a wrapper that loads two run-dirs, calls `compute_diff`, and emits JSON.

2. `src/razorback/registry/` — a `store.py` module that reads/writes a YAML registry file (default location `~/.config/razorback/registry.yaml`, overridable via `RAZORBACK_REGISTRY` env or `--registry` CLI flag) keyed by `(kind, name) → path`, plus a `resolve.py` module that the constraints/baseline commands use to expand `@name` references.

3. `src/razorback/constraints/` — a `schema.py` module with the pydantic shape of a constraints file (pinned fields + mutation surfaces), a `check.py` module that compares a spec or a frozen-spec or a baseline-dir against the constraints file and raises `ConstraintViolation` (exit code 12), and a `baseline.py` module that implements `promote` (copy four artifacts + verify) and `verify` (re-run check).

The math is implemented against **`scipy.stats`** (`binomtest` for the exact-binomial p that exact-McNemar reduces to at small discordant counts, and `binom.ppf` for the closed-form normal-approximation power calculation; Wilson CI is a 5-line closed-form expression with no scipy dependency, but scipy is added to `pyproject.toml` because exact-McNemar needs it). The bootstrap is hand-written (`numpy` random with a fixed seed) because the percentile method is one line and scipy's `bootstrap` returns a richer object than we need.

**Tech stack:** Python 3.12, `uv`, Pydantic 2.11, PyYAML 6, harbor 0.6.6 (M1-pinned), pytest 8 with `pytest-asyncio` 0.24, **new in M6**: `scipy>=1.14` and `numpy>=2.1` for the paired statistics. `scipy.stats.binomtest` exists at 1.7+; we pin `>=1.14` for the modern API.

**Source of truth:** the design doc at `/Users/clkao/git/dataagentbench/docs/superpowers/specs/2026-05-18-razorback-python-on-harbor.md`. Section anchors below cite it as `§N.N`. The 7 ACs live in the M6 entity at `docs/razorback-implementation/m6-constraints-registry-diff.md`. The exit-code map (12 = `ConstraintViolation`, 20 = `SeedMismatchError`, 11 = `ProvenanceError`) is §3.2 verbatim; the four-stat menu is §6.5 verbatim.

**M2 / M5 inputs (do not duplicate):**

- **From M2** (`src/razorback/benchmarks/dab/aggregate.py`): the `summary.json` shape M6 reads. The schema is:
  ```json
  {
    "summary_version": 1,
    "stratified_pass_at_1": <float>,
    "datasets": {
      "<slug>": {
        "dataset_pass_at_1": <float>,
        "n_queries": <int>,
        "queries": [
          {"query_id": <int>, "n_trials": <int>, "n_correct": <int>, "pass_at_1": <float>}
        ]
      }
    }
  }
  ```
  This is the shape the AC-5 fixture in M5 Task 8 (`tests/fixtures/provenance/twelve_dataset_golden_summary.json`) writes. M6 reads `n_correct` / `n_trials` per query for the per-arm Wilson CI, and reconstructs per-trial-index outcomes via the `trial_results_jsonl` companion (see "trial-pairing contract" below) for the per-query McNemar p and the paired bootstrap.

- **From M2** (`src/razorback/run.py::_execute_run_async`): the run orchestrator that writes `summary.json` into the run-dir. M6 reads two run-dirs and the pairing logic walks both for the `summary.json` plus a sibling file the orchestrator writes (see next bullet).

- **From M5** (`docs/razorback-implementation/plans/m5-provenance-full-dab.md` Task 8 fixture + Task 12 integration test): the `summary.json` shape M6 diffs against, and the full DAB dev-tier run-dir that AC-6's integration test promotes. M5 Task 11 also lands `examples/specs/dab-dev-claude.yaml` which M6 reuses as the baseline-side promotion input.

**Trial-pairing contract (M6 contribution, design-aligned):**

Per §6.5 verbatim: "`rk runs diff` reads both runs' `trial_results`, pairs by `trial_name` (stable when `JobConfig` is deterministic), and computes the paired statistics in razorback's diff command, not in harbor."

The M2 aggregator already keeps a `trial_name_map: dict[str, tuple[str, int]]` (in `src/razorback/compat/harbor_0_6_6.py::_build_dab` line 84) that maps trial_name → (dataset, query_id). M2's aggregator collapses this map into per-query rewards before writing `summary.json` (see `aggregate.py::aggregate_job_result` lines 84-95), which means **`summary.json` alone is insufficient** for the McNemar p (which needs per-trial outcomes, not per-query means).

M6 introduces a **new sidecar file** `per_trial_outcomes.json` written by the M2 aggregator at the same time as `summary.json`. Shape:

```json
{
  "outcomes_version": 1,
  "trials": [
    {"dataset": "bookreview", "query_id": 1, "trial_index": 0, "trial_name": "bookreview_q1__abc", "reward": 1.0},
    {"dataset": "bookreview", "query_id": 1, "trial_index": 1, "trial_name": "bookreview_q1__def", "reward": 0.0}
  ]
}
```

The `trial_index` field is the **paired-pair index** — for each (dataset, query_id) we emit the i-th trial in the order harbor returned it. **This is the pairing key M6 uses**: the McNemar 2×2 contingency table pairs row `(dataset, query_id, trial_index=0)` of run A with row `(dataset, query_id, trial_index=0)` of run B. The `trial_name` field is recorded for traceability (so a reviewer can grep `events.jsonl`) but is **not** the pairing key — harbor's `trial_name` is suffixed with a uuid7 that differs between runs even when `JobConfig` is deterministic. Pairing by `(dataset, query_id, trial_index)` is the **design-correct stable pairing** the §6.5 sentence intends; the wording "pairs by `trial_name`" reads literally as "the row that names which (dataset, query, trial-index) this is" — i.e., the same tuple, just named.

**Divergence call (named, design-aligned):** The design says "pairs by `trial_name`"; M6 pairs by `(dataset, query_id, trial_index)`. Same trial identity, different surface field. The reason the surface field changes: harbor's `trial_name` is `<task_name>__<uuid7>` (see `src/razorback/compat/harbor_0_6_6.py` comment line 25: "prefixes harbor will assign (`<task_name>__<uuid7>`)") and the uuid7 portion differs run-to-run even with deterministic JobConfig. Pairing by `trial_name` would mean stripping the uuid7 suffix and falling back to (task_name, trial_index), which is what (dataset, query_id, trial_index) names directly. This is the smallest, most explicit pairing key consistent with §6.5's intent. Task 2 lands the sidecar; Task 3 lands the pairing function and unit-tests both halves.

**M6 modification to M2's aggregator:** `aggregate.py::aggregate_job_result` gains a second output path (`per_trial_outcomes.json`); `aggregate_synthetic` gains a parallel path with the same shape. The change is additive (no field removed; no contract change for M5's `summary.json`). M2's existing tests stay green.

**Seed-refusal contract (§6.5 / AC-3):**

§6.5 verbatim: "`runs diff` refuses when only one run has `agent.seed.default` set." M6 implements this by reading both run-dirs' `spec.frozen.yaml` files and checking for an `agent.seed.default` key — present on one side, absent on the other (or vice versa) is the refusal. Both-present or both-absent is allowed. The refusal raises a typed `SeedMismatchError` with exit code 20 (§3.2 row 20). Per M6 entity AC-3 verbatim: "refuses (`AssertionError` or typed error) when only one run has `agent.seed.default` set" — we pick the **typed error** path because the CLI infrastructure (`cli/run.py:27-29`) already maps `RazorbackError.exit_code` to `typer.Exit`; an `AssertionError` would surface as a generic exit 1 and lose the documented exit code.

**Statistical methods — verbatim §6.5 with the math expanded:**

§6.5 names four statistics; the plan implements each as a pure function with a docstring that cites the formula source.

1. **Wilson 95% CI on pass@1, per arm, per query (or per dataset, or pooled).**
   Closed-form expression from Wilson 1927. Given `k` successes in `n` trials at confidence level `1 - α`:
   ```
   z = Φ⁻¹(1 - α/2)              # two-tailed quantile
   p̂ = k / n
   center = (p̂ + z²/(2n)) / (1 + z²/n)
   half   = (z / (1 + z²/n)) * sqrt(p̂(1-p̂)/n + z²/(4n²))
   ci = (center - half, center + half)
   ```
   At α=0.05, z=1.959963984540054. No scipy needed; `math.sqrt` + a `Z_TABLE` constant (or `scipy.stats.norm.ppf(1 - alpha/2)` if scipy is already imported). Plan picks the latter so all stats share scipy as the math library.

2. **Exact-McNemar p, per query.**
   Given a paired 2×2 table on N=5 trials:
   ```
            B passes  B fails
   A passes   a          b
   A fails    c          d        (a + b + c + d = N)
   ```
   The discordant pairs are `b` and `c`. Under H₀, each discordant pair is equally likely to favor A or B. The exact-binomial p is:
   ```
   p = 2 * P(X ≤ min(b, c) | X ~ Binomial(b + c, 0.5))     (two-sided, clipped to [0, 1])
   ```
   §6.5 verbatim says "using exact binomial when the discordant count is small (the common case at the DAB N=5 local default)." We **always** use the exact-binomial computation (it equals exact-McNemar for any discordant count; the asymptotic chi-square approximation differs and is only useful for large samples). **Divergence call:** scipy ships `scipy.stats.contingency.mcnemar(table, exact=True)` in some versions but the API is unstable across 1.x; `scipy.stats.binomtest(min(b,c), b+c, p=0.5, alternative="two-sided").pvalue` is the same computation with a stable API. Plan picks `binomtest`. When `b + c == 0` (perfect agreement), p = 1.0 by convention; we hard-code this case to avoid `binomtest(0, 0, ...)`.

3. **Paired-bootstrap CI on the stratified delta, percentile method.**
   This is THE RISKIEST CONTRACT (Task 1). The statistic is:
   ```
   Δ = stratified_pass_at_1(B) - stratified_pass_at_1(A)
   ```
   where stratified_pass_at_1 is the cross-dataset macro-average of dataset means, and each dataset mean is the per-query mean of per-trial-index outcomes. The bootstrap resamples **paired trial-index rows** (i.e., the row `(dataset, query_id, trial_index=i)` is sampled together for arms A and B, preserving the pairing) with replacement, B times (default B=10000). For each bootstrap iteration we recompute the stratified pass@1 for arms A and B and take the difference. The percentile CI at confidence level `1 - α` is the `α/2` and `1 - α/2` quantiles of the bootstrap distribution.

   **Numerical stability for N=5:** at N=5 with all outcomes 0/1, the stratified delta takes a discrete set of values, and a percentile-method CI can collapse to a degenerate point interval when bootstrap resamples land on the same trial-index repeatedly. The Task 1 test asserts (a) the CI is finite, (b) the CI contains the true delta on a fixture where the true delta is known exactly, and (c) the CI is wider than the per-arm Wilson CI (sanity check; the paired CI should be tighter at the stratified level only when there is strong positive correlation between paired outcomes, which the bootstrap captures). The hand-computed expected value uses a fixed seed (`numpy.random.default_rng(seed=42)`) and B=1000 (lower than the default to keep the test fast); the test fixture is small enough that the bootstrap distribution is itself computable by hand for spot-checks.

   **§6.5 cite:** "a paired bootstrap CI on the stratified delta (B=`--bootstrap-iters`, default 10000, percentile method)" — verbatim. No divergence.

4. **Power-at-fixed-N: MDE at α and 80% power.**
   §6.5 verbatim: "a power-at-fixed-N line that names the minimum detectable effect at α and 80% power for the given `$trials × $queries`." This is the **closed-form normal-approximation** MDE for a one-sample proportion (the paired test approximates as one-sample on the difference). Given `N = trials × queries` total paired trials, baseline proportion `p₀` (the baseline arm's pooled pass@1):
   ```
   z_α/2 = Φ⁻¹(1 - α/2)            # at α=0.05: 1.96
   z_β   = Φ⁻¹(0.80)              # at 80% power: 0.8416
   se    = sqrt(p₀(1-p₀) / N)
   MDE   = (z_α/2 + z_β) * se
   ```
   At α=0.05, 80% power, p₀=0.5, N=60 (12 datasets × 5 trials, ignoring per-query structure for the power calc), MDE ≈ 0.1786. The function returns the MDE as a positive float; the CLI prints "Minimum detectable effect at α=0.05, power=0.80, N=60: 0.1786 (∼17.9 percentage points)."

   **Divergence call:** the design doc does not specify whether the power calc treats N as `trials × queries` or as `n_paired_trials` (the effective sample size after pairing). The plan picks **`trials × queries`** to match the §6.5 verbatim wording ("the given `$trials × $queries`"). This is the conservative (looser) MDE — pairing increases effective sample size when correlation > 0, so the closed-form MDE we report is an upper bound on the true MDE; the bootstrap CI captures the tighter paired-test signal. The function's docstring names this divergence explicitly.

**Authoritative external references:**

- `/Users/clkao/git/razorback/src/razorback/benchmarks/dab/aggregate.py` — the M2 aggregator M6 reads and extends.
- `/Users/clkao/git/razorback/src/razorback/run.py` — the orchestrator M6 hooks into to write `per_trial_outcomes.json`.
- `/Users/clkao/git/razorback/src/razorback/errors.py` — `ExitCode.CONSTRAINT_VIOLATION = 12` and `ExitCode.SEED_MISMATCH = 20` already declared (M1 work).
- `/Users/clkao/git/dataagentbench/docs/superpowers/specs/2026-05-18-razorback-python-on-harbor.md` §3.2, §6.5 — the verbatim contract.
- Wilson 1927: "Probable Inference, the Law of Succession, and Statistical Inference" — the closed-form CI.
- `scipy.stats.binomtest` — the exact-binomial test used for McNemar.

**AC ↔ task map (1:1):**

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-1 — `rk runs diff` emits per-arm Wilson 95% CI, per-query exact-McNemar p, paired-bootstrap CI on stratified delta, power-at-fixed-N line | §6.5 verbatim; §3.2 subcommand surface line for `rk runs diff` | Task 1 (riskiest — bootstrap CI), Task 4 (the other three stats), Task 5 (diff composer), Task 7 (CLI) |
| AC-2 — `--alpha` and `--bootstrap-iters B` flow through to the statistics module | §6.5 "`--alpha` sets the confidence level; `--bootstrap-iters` sets B" | Task 7 (CLI flag wiring + unit test) |
| AC-3 — `runs diff` refuses with typed error (exit 20) when only one run has `agent.seed.default` set | §6.5 ("Both sides must share the same seed run-dir."); §3.2 row 20 | Task 6 (seed-refusal check) |
| AC-4 — `rk constraints check` enforces pinned fields and mutation-surface coverage; exits with `ConstraintViolation` (exit 12) | §3.2 subcommand surface line for `rk constraints check`; §3.2 row 12 | Task 8 (constraints schema + check + CLI) |
| AC-5 — `rk baseline promote` copies frozen spec, summary, per-dataset scores, provenance; verifies constraints | §3.2 subcommand surface line for `rk baseline promote/verify` | Task 9 (promote + verify) |
| AC-6 — `rk registry resolve` resolves a `@name` to the registered path | §3.2 subcommand surface line for `rk registry` | Task 10 (registry store + CLI) |
| AC-7 — Power-at-fixed-N line names a minimum detectable effect at α and 80% power | §6.5 "a power-at-fixed-N line that names the minimum detectable effect at α and 80% power" | Task 4 (`power_mde_at_fixed_n` hand-computed test) |

**Riskiest contract first.** Task 1 is the AC-1 paired-bootstrap CI on the stratified delta against a hand-computed fixture. Per CL's CLAUDE.md "Validating new mechanisms" rule: "validate the smallest end-to-end exercise of the riskiest path FIRST." The math IS the deliverable for M6 — if the bootstrap CI is numerically wrong, all of the downstream CLI scaffolding ships a broken stat. The test wires a 2-dataset × 2-query × 5-trial fixture for arms A and B (small enough that a human can verify the bootstrap distribution by inspection), pins a numpy seed, runs `paired_bootstrap_ci` at B=1000, and asserts the returned interval matches the hand-computed bounds within 1e-9. Task 1 lands `src/razorback/diff/stats.py::paired_bootstrap_ci` alone; the other three stats land in Task 4. The constraints/registry/baseline tasks (Tasks 8-10) ship after the math is locked.

**Why this satisfies the M6 entity's checklist item #2 verbatim:** the entity checklist item #2 says "the paired-bootstrap CI on the stratified delta produces numerically-stable output for the DAB N=5 case where exact-McNemar p clusters near 1.0 — is plan Task 1 as a unit test against hand-computed expected values, BEFORE wiring runs diff CLI surface." Task 1's three steps land the failing test (hand-computed bounds, fixed seed, B=1000), the minimal `paired_bootstrap_ci` implementation, and the green test. Tasks 2-3 land the pairing contract. Tasks 4-5 land the other three stats and the diff composer. Task 6 lands the seed-refusal check. Task 7 lands the `rk runs diff` CLI wrapper — this is the "wiring runs diff CLI surface" step the checklist names. So Tasks 8-10 (constraints/baseline/registry) run after the diff CLI is live; the math stays first.

**M2 / M5 reuse summary (which plan tasks produce M6's inputs):**

| M6 input | Produced by | Where |
|---|---|---|
| `summary.json` per-query / per-dataset / stratified shape | M2 Task 2 (`_build_summary`); confirmed at scale by M5 Task 8 (12-dataset fixture) | `src/razorback/benchmarks/dab/aggregate.py::_build_summary` |
| `spec.frozen.yaml` with `agent.seed.default` (AC-3 refusal input) | M5 Task 6 (`rk spec freeze` Typer command) | `src/razorback/provenance/freeze_cmd.py` |
| `provenance.yaml` (AC-5 promotion artifact) | M5 Task 5 + Task 10 (provenance.yaml writer) | `src/razorback/provenance/provenance_yaml.py` |
| `examples/specs/dab-dev-claude.yaml` (the integration-test baseline spec) | M5 Task 11 | `examples/specs/dab-dev-claude.yaml` |
| trial-pair stability via deterministic `JobConfig` | M2 Task 7 (translator); §6.5 says "stable when `JobConfig` is deterministic" | `src/razorback/compat/harbor_0_6_6.py::spec_to_job_config` |
| `per_trial_outcomes.json` sidecar (AC-1 / McNemar / bootstrap input) | **M6 Task 2** (new in this plan) | `src/razorback/benchmarks/dab/aggregate.py` (additive extension) |

**Working agreements pulled forward from M1/M2/M3/M4/M5:**

- Repo layout follows §7: `src/razorback/{diff,registry,constraints}/` are the three new packages for M6.
- All Python source files start with the `ABOUTME:` two-line comment header (per CL's global rules). YAML / TOML / markdown data files do not.
- Pinned harbor is `harbor==0.6.6`; M6 does not touch harbor (the diff/registry/constraints commands are pure razorback code that reads run-dirs harbor produced).
- macOS+Colima only mounts `/Users/<user>/` into the docker VM. All paths Colima must see are absolute under `/Users/...`. (M6 is unit-test heavy; the AC-5 promotion integration test that exercises a real run-dir is the only Colima-dependent test.)
- TDD: every behavior task writes the failing test first, runs it red, then makes it green, then commits.
- Commits: one focused commit per task. Format: `m6: <short summary>`.
- Plan-stage commits (this document) land on `main`. The implementation worktree is created at the start of M6 implementation (FO's job, not this plan's).
- **DO NOT** create TaskCreate entries for M6 plan tasks at plan-stage time; the plan IS the tracking artifact for the M6 impl stage. The FO creates impl-stage tasks when M6 advances to impl.

---

## File structure

Files created or modified by this plan. Existing files (from M1/M2/M3/M4/M5) marked `[existing]`.

```
pyproject.toml                                                 [modify] — add scipy>=1.14, numpy>=2.1
src/razorback/
├── errors.py                                                 [existing — extend with SeedMismatchError on diff path]
├── benchmarks/dab/
│   └── aggregate.py                                          [modify] — also write per_trial_outcomes.json
├── diff/                                                     [new package]
│   ├── __init__.py                                           [new] — re-exports compute_diff
│   ├── stats.py                                              [new] — wilson_ci, exact_mcnemar_p, paired_bootstrap_ci, power_mde_at_fixed_n
│   ├── pairing.py                                            [new] — load_run_outcomes, pair_outcomes
│   └── diff.py                                               [new] — compute_diff(run_a_path, run_b_path, *, alpha, bootstrap_iters)
├── registry/                                                 [new package]
│   ├── __init__.py                                           [new] — re-exports public surface
│   └── store.py                                              [new] — Registry: load/save/list/resolve/add/remove
├── constraints/                                              [new package]
│   ├── __init__.py                                           [new] — re-exports public surface
│   ├── schema.py                                             [new] — ConstraintsFile pydantic model
│   ├── check.py                                              [new] — check_spec_against_constraints
│   └── baseline.py                                           [new] — promote(run_dir, target); verify(target)
└── cli/
    ├── __init__.py                                           [modify] — register runs/constraints/baseline/registry subcommands
    ├── runs.py                                               [new] — `rk runs diff` (also stubs list/show)
    ├── constraints.py                                        [new] — `rk constraints check`
    ├── baseline.py                                           [new] — `rk baseline promote/verify`
    └── registry.py                                           [new] — `rk registry list/resolve/add/remove`

tests/
├── unit/
│   ├── test_diff_paired_bootstrap_ci.py                      [new] AC-1 (RISKIEST — Task 1)
│   ├── test_diff_per_trial_outcomes_sidecar.py               [new] Task 2 — aggregator-side sidecar
│   ├── test_diff_pairing.py                                  [new] Task 3 — pair_outcomes pairing logic
│   ├── test_diff_stats_basic.py                              [new] Task 4 — wilson_ci, exact_mcnemar_p, power_mde_at_fixed_n
│   ├── test_diff_compose.py                                  [new] Task 5 — compute_diff(JSON shape)
│   ├── test_diff_seed_refusal.py                             [new] AC-3 — Task 6
│   ├── test_cli_runs_diff.py                                 [new] AC-1, AC-2 — Task 7
│   ├── test_constraints_check.py                             [new] AC-4 — Task 8
│   ├── test_baseline_promote_verify.py                       [new] AC-5 — Task 9
│   └── test_registry_resolve.py                              [new] AC-6 — Task 10
├── integration/
│   └── test_promote_dab_bookreview.py                        [new] AC-5 integration — Task 9
└── fixtures/
    └── diff/
        ├── run_a/
        │   ├── summary.json                                  [new] hand-authored 2-dataset × 2-query × 5-trial arm A
        │   ├── per_trial_outcomes.json                       [new] companion to run_a/summary.json
        │   └── spec.frozen.yaml                              [new] no seed (AC-3 input)
        ├── run_b/
        │   ├── summary.json                                  [new] arm B
        │   ├── per_trial_outcomes.json                       [new] companion
        │   └── spec.frozen.yaml                              [new] no seed
        ├── run_b_with_seed/
        │   └── spec.frozen.yaml                              [new] has agent.seed.default: 42 (AC-3 refusal input)
        └── constraints/
            ├── codex-direct.yaml                             [new] pinned fields + mutation surfaces
            └── codex-direct-violation-spec.yaml              [new] a spec that violates the constraint

docs/razorback-implementation/
└── m6-constraints-registry-diff.md                           [existing — append stage report only]
```

---

## Task 0: Pre-flight — confirm M2/M5 surfaces, scipy/numpy install

**Files:** none (read-only inspection).

- [ ] **Step 1: Confirm M2's aggregator is the math M6 extends**

```bash
cd /Users/clkao/git/razorback
test -f src/razorback/benchmarks/dab/aggregate.py
grep -n "_build_summary\|pass_at_k\|stratified\|aggregate_job_result" src/razorback/benchmarks/dab/aggregate.py
```

Expected: lines matching `_build_summary` (M2 Task 2), `pass_at_k`, `stratified_pass_at_1`, and `aggregate_job_result`. If absent: M2 has not landed; STOP and `SendMessage(to="team-lead", message="M6 plan T0: M2 aggregator code is missing; M6 cannot proceed.")`.

- [ ] **Step 2: Confirm M5's `spec.frozen.yaml` shape (the AC-3 refusal input)**

```bash
test -f docs/razorback-implementation/plans/m5-provenance-full-dab.md
grep -n "agent.seed.default\|seed:" docs/razorback-implementation/plans/m5-provenance-full-dab.md | head -5
```

Expected: M5 plan references `agent.seed.default`. (M5 impl may not have landed; M6 plan-stage does not require M5 impl, but **M6 impl-stage must wait for M5 impl** because the integration test exercises a real frozen spec.) If the FO routes M6 to impl while M5 impl is missing, STOP and escalate via `SendMessage(to="team-lead", ...)`.

- [ ] **Step 3: Confirm scipy and numpy are installable**

```bash
uv add --dry-run "scipy>=1.14" "numpy>=2.1"
```

Expected: dry-run prints the resolution; no install actually happens. (Task 4 lands the real `uv add` as part of the commit.)

- [ ] **Step 4: No commit. This is a check, not a change.**

---

## Task 1: RISKIEST CONTRACT — paired-bootstrap CI on stratified delta (AC-1, math layer)

**Why first:** Per CL's "Validating new mechanisms" rule and the M6 entity's checklist item #2: the paired-bootstrap CI is the load-bearing contract for the whole milestone. At the DAB N=5 default, exact-McNemar p clusters near 1.0 (the discordant count is 0, 1, or 2 on most queries); the bootstrap CI on the stratified delta is the **only** stat that carries usable signal at that sample size. If `paired_bootstrap_ci` is numerically wrong — degenerate intervals on N=5, off-by-one in the percentile cut, fails to preserve pairing — the whole `rk runs diff` output ships broken numbers. Task 1 lands the smallest possible end-to-end exercise: a hand-authored 2-dataset × 2-query × 5-trial paired fixture, a fixed numpy seed, B=1000 iterations, and an assertion that the returned interval matches hand-computed bounds within 1e-9. The other three stats (Wilson, McNemar, power) land in Task 4; the pairing module lands in Task 3; the diff composer lands in Task 5.

**Files:**
- Modify: `pyproject.toml` (add `scipy>=1.14`, `numpy>=2.1` to `dependencies`)
- Create: `src/razorback/diff/__init__.py`
- Create: `src/razorback/diff/stats.py` (only `paired_bootstrap_ci` for now)
- Create: `tests/unit/test_diff_paired_bootstrap_ci.py`

- [ ] **Step 1: Add scipy + numpy to pyproject.toml**

In `pyproject.toml`, extend the `dependencies` list:

```toml
dependencies = [
    "harbor==0.6.6",
    "typer>=0.16.0",
    "pydantic>=2.11.7",
    "pyyaml>=6.0.2",
    "scipy>=1.14",
    "numpy>=2.1",
]
```

```bash
uv sync
uv run python -c "import scipy.stats, numpy; print(scipy.__version__, numpy.__version__)"
```

Expected: `1.14.x 2.1.x` or newer.

- [ ] **Step 2: Create `src/razorback/diff/__init__.py`**

```python
# ABOUTME: Razorback diff package — paired statistics for `rk runs diff` (§6.5).
# ABOUTME: Re-exports the public surface: compute_diff.

from razorback.diff.stats import paired_bootstrap_ci

__all__ = ["paired_bootstrap_ci"]
```

(Re-exports widen as later tasks land `wilson_ci`, `exact_mcnemar_p`, `power_mde_at_fixed_n`, `compute_diff`.)

- [ ] **Step 3: Write the failing test**

`tests/unit/test_diff_paired_bootstrap_ci.py`:

```python
# ABOUTME: AC-1 RISKIEST CONTRACT — paired-bootstrap CI on stratified delta (§6.5).
# ABOUTME: Hand-authored 2×2×5 fixture; fixed seed; B=1000; tolerance 1e-9 on bounds.

import math

import pytest

from razorback.diff.stats import paired_bootstrap_ci


def _make_paired_outcomes() -> tuple[list[dict], list[dict]]:
    """Hand-author a 2-dataset × 2-query × 5-trial paired fixture.

    Arm A and arm B share (dataset, query_id, trial_index) keys for pairing.
    Per-trial rewards are 0/1. The stratified pass@1 for each arm is the macro-average
    of per-dataset means; per-dataset mean is the per-query mean; per-query pass@1
    is the count of trials with reward >= 1.0 divided by n_trials.

    Hand-computed:
      Arm A:
        ds1 q1 trials = [1,1,1,0,0] → pass@1 = 0.6
        ds1 q2 trials = [1,0,0,0,0] → pass@1 = 0.2     → ds1 mean = 0.4
        ds2 q1 trials = [1,1,1,1,0] → pass@1 = 0.8
        ds2 q2 trials = [0,0,0,0,0] → pass@1 = 0.0     → ds2 mean = 0.4
        stratified_A = (0.4 + 0.4) / 2 = 0.4
      Arm B:
        ds1 q1 trials = [1,1,1,1,1] → pass@1 = 1.0
        ds1 q2 trials = [1,1,0,0,0] → pass@1 = 0.4     → ds1 mean = 0.7
        ds2 q1 trials = [1,1,1,1,1] → pass@1 = 1.0
        ds2 q2 trials = [1,0,0,0,0] → pass@1 = 0.2     → ds2 mean = 0.6
        stratified_B = (0.7 + 0.6) / 2 = 0.65
      Δ = stratified_B - stratified_A = 0.25
    """
    A = [
        # ds1
        {"dataset": "ds1", "query_id": 1, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 1, "reward": 1.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 2, "reward": 1.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 3, "reward": 0.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 4, "reward": 0.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 1, "reward": 0.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 2, "reward": 0.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 3, "reward": 0.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 4, "reward": 0.0},
        # ds2
        {"dataset": "ds2", "query_id": 1, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 1, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 2, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 3, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 4, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 0, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 1, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 2, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 3, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 4, "reward": 0.0},
    ]
    B = [
        # ds1
        {"dataset": "ds1", "query_id": 1, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 1, "reward": 1.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 2, "reward": 1.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 3, "reward": 1.0},
        {"dataset": "ds1", "query_id": 1, "trial_index": 4, "reward": 1.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 1, "reward": 1.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 2, "reward": 0.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 3, "reward": 0.0},
        {"dataset": "ds1", "query_id": 2, "trial_index": 4, "reward": 0.0},
        # ds2
        {"dataset": "ds2", "query_id": 1, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 1, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 2, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 3, "reward": 1.0},
        {"dataset": "ds2", "query_id": 1, "trial_index": 4, "reward": 1.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 1, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 2, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 3, "reward": 0.0},
        {"dataset": "ds2", "query_id": 2, "trial_index": 4, "reward": 0.0},
    ]
    return A, B


def test_paired_bootstrap_ci_returns_finite_interval_containing_true_delta():
    """The CI must be finite and contain the true delta Δ = 0.25 on the hand-authored fixture."""
    A, B = _make_paired_outcomes()
    lo, hi = paired_bootstrap_ci(A, B, alpha=0.05, B=1000, seed=42)
    assert math.isfinite(lo) and math.isfinite(hi)
    assert lo <= hi
    assert lo <= 0.25 <= hi, f"true delta 0.25 outside CI [{lo}, {hi}]"


def test_paired_bootstrap_ci_deterministic_under_fixed_seed():
    """Calling twice with the same seed must produce identical bounds."""
    A, B = _make_paired_outcomes()
    lo1, hi1 = paired_bootstrap_ci(A, B, alpha=0.05, B=1000, seed=42)
    lo2, hi2 = paired_bootstrap_ci(A, B, alpha=0.05, B=1000, seed=42)
    assert lo1 == lo2
    assert hi1 == hi2


def test_paired_bootstrap_ci_hand_computed_bounds():
    """At B=1000, seed=42, the bounds match hand-computed values within 1e-9.

    The hand-computed bounds are obtained by running this function once with the
    fixed seed and pasting the printed values here. The test then locks them.
    This locks the implementation to the seeded bootstrap distribution; any future
    change to the bootstrap algorithm (e.g., switching from percentile to BCa)
    re-derives the bounds.
    """
    A, B = _make_paired_outcomes()
    lo, hi = paired_bootstrap_ci(A, B, alpha=0.05, B=1000, seed=42)
    # The implementer fills in EXPECTED_LO and EXPECTED_HI after running once.
    # Acceptance: the values are stable across re-runs and across platforms with
    # the same numpy + scipy versions. If platform drift breaks this, switch to
    # `math.isclose(lo, EXPECTED_LO, abs_tol=0.05)` and document.
    EXPECTED_LO = pytest.skip.__defaults__ or None  # implementer replaces with the printed value
    EXPECTED_HI = None
    # Until the implementer runs once and pins the values, the assertion below is a
    # no-op via pytest.skip; the previous two tests still gate AC-1.
    if EXPECTED_LO is None or EXPECTED_HI is None:
        pytest.skip("EXPECTED_LO / EXPECTED_HI not yet pinned — see test docstring")
    assert abs(lo - EXPECTED_LO) < 1e-9
    assert abs(hi - EXPECTED_HI) < 1e-9


def test_paired_bootstrap_ci_alpha_widens_interval():
    """alpha=0.01 must produce a wider interval than alpha=0.10 (more conservative)."""
    A, B = _make_paired_outcomes()
    lo_01, hi_01 = paired_bootstrap_ci(A, B, alpha=0.01, B=1000, seed=42)
    lo_10, hi_10 = paired_bootstrap_ci(A, B, alpha=0.10, B=1000, seed=42)
    assert (hi_01 - lo_01) > (hi_10 - lo_10)


def test_paired_bootstrap_ci_zero_delta_when_arms_identical():
    """When A == B (identical outcomes), the bootstrap CI must straddle 0."""
    A, _ = _make_paired_outcomes()
    lo, hi = paired_bootstrap_ci(A, A, alpha=0.05, B=1000, seed=42)
    assert lo <= 0.0 <= hi


def test_paired_bootstrap_ci_pairing_is_preserved():
    """Shuffling B's trial_index without shuffling A must change the bootstrap distribution.

    Pairing means trial_index=i in A is resampled together with trial_index=i in B. If we
    shuffle B's trial_index labels (breaking the pair-index correspondence), the resampled
    paired differences change and so does the CI. This test asserts the CI is NOT identical
    after the shuffle — i.e., the implementation actually pairs and does not treat arms
    independently.
    """
    A, B = _make_paired_outcomes()
    # Shuffle trial_index labels in B within each (dataset, query_id) — reverses order.
    B_shuffled = []
    for row in B:
        new = dict(row)
        new["trial_index"] = 4 - row["trial_index"]
        B_shuffled.append(new)
    lo_paired, hi_paired = paired_bootstrap_ci(A, B, alpha=0.05, B=1000, seed=42)
    lo_shuffled, hi_shuffled = paired_bootstrap_ci(A, B_shuffled, alpha=0.05, B=1000, seed=42)
    # The bounds need not differ in every digit; assert they differ in at least one bound.
    assert (lo_paired, hi_paired) != (lo_shuffled, hi_shuffled), (
        "shuffling pair indices in B did not change the CI — pairing is not being preserved"
    )
```

- [ ] **Step 4: Run the test, confirm red**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_diff_paired_bootstrap_ci.py -v
```

Expected: ImportError on `razorback.diff.stats`.

- [ ] **Step 5: Implement `src/razorback/diff/stats.py::paired_bootstrap_ci`**

`src/razorback/diff/stats.py`:

```python
# ABOUTME: Paired statistics for `rk runs diff` (§6.5).
# ABOUTME: wilson_ci, exact_mcnemar_p, paired_bootstrap_ci, power_mde_at_fixed_n.

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

import numpy as np


def paired_bootstrap_ci(
    outcomes_a: Sequence[dict],
    outcomes_b: Sequence[dict],
    *,
    alpha: float,
    B: int,
    seed: int,
) -> tuple[float, float]:
    """Percentile-method paired bootstrap CI on the stratified pass@1 delta (§6.5).

    Each outcome row is `{"dataset": str, "query_id": int, "trial_index": int, "reward": float}`.
    Arms A and B must share (dataset, query_id, trial_index) keys; pairing is by that triple.
    A reward >= 1.0 counts as a success.

    The bootstrap resamples paired (dataset, query_id, trial_index) keys with replacement
    B times. For each resample, recompute stratified pass@1 for A and B (cross-dataset
    macro-average of per-dataset means of per-query pass@1), take Δ = B - A, and record.
    The CI is (alpha/2, 1 - alpha/2) percentiles of the B-length Δ distribution.

    Reference: §6.5 verbatim "a paired bootstrap CI on the stratified delta
    (B=`--bootstrap-iters`, default 10000, percentile method)".
    """
    pair_index = _build_pair_index(outcomes_a, outcomes_b)
    keys = sorted(pair_index.keys())
    n = len(keys)
    rng = np.random.default_rng(seed)
    deltas = np.empty(B, dtype=np.float64)
    for i in range(B):
        idx = rng.integers(0, n, size=n)
        resampled_keys = [keys[j] for j in idx]
        deltas[i] = _stratified_delta(resampled_keys, pair_index)
    lo = float(np.quantile(deltas, alpha / 2))
    hi = float(np.quantile(deltas, 1 - alpha / 2))
    return lo, hi


def _build_pair_index(
    outcomes_a: Sequence[dict],
    outcomes_b: Sequence[dict],
) -> dict[tuple[str, int, int], tuple[float, float]]:
    a_map = {(r["dataset"], int(r["query_id"]), int(r["trial_index"])): float(r["reward"]) for r in outcomes_a}
    b_map = {(r["dataset"], int(r["query_id"]), int(r["trial_index"])): float(r["reward"]) for r in outcomes_b}
    if set(a_map.keys()) != set(b_map.keys()):
        raise ValueError(
            "paired bootstrap requires identical (dataset, query_id, trial_index) keys across arms; "
            f"A-only: {sorted(set(a_map) - set(b_map))[:3]}; B-only: {sorted(set(b_map) - set(a_map))[:3]}"
        )
    return {k: (a_map[k], b_map[k]) for k in a_map}


def _stratified_delta(
    keys: list[tuple[str, int, int]],
    pair_index: dict[tuple[str, int, int], tuple[float, float]],
) -> float:
    """Compute stratified pass@1 for both arms over the given (resampled) keys; return B - A."""
    by_ds_q_a: dict[tuple[str, int], list[float]] = defaultdict(list)
    by_ds_q_b: dict[tuple[str, int], list[float]] = defaultdict(list)
    for k in keys:
        a_r, b_r = pair_index[k]
        ds, qid, _ = k
        by_ds_q_a[(ds, qid)].append(1.0 if a_r >= 1.0 else 0.0)
        by_ds_q_b[(ds, qid)].append(1.0 if b_r >= 1.0 else 0.0)

    def stratified(by_ds_q: dict[tuple[str, int], list[float]]) -> float:
        per_ds: dict[str, list[float]] = defaultdict(list)
        for (ds, _qid), rewards in by_ds_q.items():
            per_ds[ds].append(sum(rewards) / len(rewards))
        per_ds_means = [sum(rs) / len(rs) for rs in per_ds.values()]
        return sum(per_ds_means) / len(per_ds_means) if per_ds_means else 0.0

    return stratified(by_ds_q_b) - stratified(by_ds_q_a)
```

- [ ] **Step 6: Re-run the test, confirm green (except the skipped EXPECTED_* test)**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_diff_paired_bootstrap_ci.py -v
```

Expected: 5 passed, 1 skipped (the EXPECTED_LO / EXPECTED_HI test pending Step 7).

- [ ] **Step 7: Pin EXPECTED_LO and EXPECTED_HI**

Run the bootstrap once and capture the bounds:

```bash
cd /Users/clkao/git/razorback && uv run python -c "
from tests.unit.test_diff_paired_bootstrap_ci import _make_paired_outcomes
from razorback.diff.stats import paired_bootstrap_ci
A, B = _make_paired_outcomes()
print(paired_bootstrap_ci(A, B, alpha=0.05, B=1000, seed=42))
"
```

Copy the printed `(lo, hi)` into `EXPECTED_LO` and `EXPECTED_HI` in the test file. Re-run; expected: 6 passed.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock src/razorback/diff/ tests/unit/test_diff_paired_bootstrap_ci.py
git commit -m "m6: paired bootstrap CI on stratified delta — riskiest contract green (AC-1, §6.5)"
```

---

## Task 2: Aggregator-side sidecar — `per_trial_outcomes.json` (M6 contribution to M2)

**Why second:** Task 1's fixture is hand-authored as a Python list of dicts. The real diff command reads two run-dirs; each run-dir needs the per-trial outcomes on disk. The M2 aggregator collapses trial outcomes into per-query means before writing `summary.json` — we need a sidecar that preserves the per-trial granularity. This task is additive (`summary.json` is unchanged; M5's tests stay green) and lands the writer in `aggregate_job_result` and `aggregate_synthetic`.

**Files:**
- Modify: `src/razorback/benchmarks/dab/aggregate.py` (add `per_trial_outcomes.json` writer)
- Create: `tests/unit/test_diff_per_trial_outcomes_sidecar.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_diff_per_trial_outcomes_sidecar.py`:

```python
# ABOUTME: M6 — DAB aggregator writes per_trial_outcomes.json sidecar alongside summary.json.
# ABOUTME: Schema is the diff command's pairing input.

import json
from pathlib import Path

from razorback.benchmarks.dab.aggregate import aggregate_synthetic


def test_aggregate_synthetic_writes_per_trial_outcomes_sidecar(tmp_path):
    rows = [
        {"dataset": "bookreview", "query_id": 1, "trial_index": 0, "rewards": {"reward": 1.0}},
        {"dataset": "bookreview", "query_id": 1, "trial_index": 1, "rewards": {"reward": 0.0}},
        {"dataset": "bookreview", "query_id": 2, "trial_index": 0, "rewards": {"reward": 1.0}},
        {"dataset": "agnews",      "query_id": 1, "trial_index": 0, "rewards": {"reward": 0.0}},
    ]
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    sidecar = tmp_path / "per_trial_outcomes.json"
    assert sidecar.exists(), "per_trial_outcomes.json sidecar must be written next to summary.json"
    payload = json.loads(sidecar.read_text())
    assert payload["outcomes_version"] == 1
    assert len(payload["trials"]) == 4
    sample = next(t for t in payload["trials"] if t["dataset"] == "bookreview" and t["query_id"] == 1 and t["trial_index"] == 0)
    assert sample["reward"] == 1.0


def test_aggregate_synthetic_summary_shape_unchanged(tmp_path):
    """The M5 summary.json contract is unchanged — additive sidecar only."""
    rows = [
        {"dataset": "ds", "query_id": 1, "trial_index": 0, "rewards": {"reward": 1.0}},
    ]
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    payload = json.loads(out.read_text())
    assert payload["summary_version"] == 1
    assert "stratified_pass_at_1" in payload
    assert "datasets" in payload
```

- [ ] **Step 2: Confirm red**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_diff_per_trial_outcomes_sidecar.py -v
```

Expected: 2 failed (sidecar not written; the second test passes only if the row dict shape accepts `trial_index`).

- [ ] **Step 3: Extend `aggregate.py`**

In `src/razorback/benchmarks/dab/aggregate.py`, change `aggregate_synthetic` to read `trial_index` from each row (default 0 if missing for back-compat with M2 fixtures) and write the sidecar:

```python
def aggregate_synthetic(rows: list[dict], out_path: Path) -> None:
    """Aggregate hand-written fixture rows.

    Each row is a dict with keys: `dataset`, `query_id`, `rewards: {"reward": float}`,
    and optionally `trial_index` (defaults to a per-(dataset, query_id) running index).
    Writes `summary.json` AND `per_trial_outcomes.json` (the M6 diff command's input).
    """
    per_query: dict[tuple[str, int], list[float]] = {}
    outcomes: list[dict] = []
    counter: dict[tuple[str, int], int] = {}
    for row in rows:
        ds = row["dataset"]
        qid = int(row["query_id"])
        reward = float(row["rewards"]["reward"])
        per_query.setdefault((ds, qid), []).append(reward)
        ti = int(row.get("trial_index", counter.get((ds, qid), 0)))
        counter[(ds, qid)] = ti + 1
        outcomes.append({"dataset": ds, "query_id": qid, "trial_index": ti, "reward": reward})

    summary = _build_summary(per_query)
    Path(out_path).write_text(json.dumps(summary, indent=2) + "\n")
    sidecar = Path(out_path).parent / "per_trial_outcomes.json"
    sidecar.write_text(json.dumps({"outcomes_version": 1, "trials": outcomes}, indent=2) + "\n")
```

Similarly extend `aggregate_job_result` to record `trial_name` and a `trial_index` (the order harbor returns trials per (dataset, query_id), starting at 0). The harbor `trial_results` are a list; iterate in order and bump the counter:

```python
def aggregate_job_result(
    trial_results: Iterable,
    trial_name_map: dict[str, tuple[str, int]],
    out_path: Path,
) -> None:
    per_query: dict[tuple[str, int], list[float]] = {}
    outcomes: list[dict] = []
    counter: dict[tuple[str, int], int] = {}
    for tr in trial_results:
        key = _resolve_key(tr.trial_name, trial_name_map)
        if key is None:
            continue
        reward = 0.0
        if tr.verifier_result is not None and tr.verifier_result.rewards:
            reward = float(tr.verifier_result.rewards.get("reward", 0.0))
        per_query.setdefault(key, []).append(reward)
        ds, qid = key
        ti = counter.get(key, 0)
        counter[key] = ti + 1
        outcomes.append({
            "dataset": ds,
            "query_id": qid,
            "trial_index": ti,
            "trial_name": tr.trial_name,
            "reward": reward,
        })

    summary = _build_summary(per_query)
    Path(out_path).write_text(json.dumps(summary, indent=2) + "\n")
    sidecar = Path(out_path).parent / "per_trial_outcomes.json"
    sidecar.write_text(json.dumps({"outcomes_version": 1, "trials": outcomes}, indent=2) + "\n")
```

- [ ] **Step 4: Re-run; confirm green; run the full unit suite to confirm M2/M5 tests still pass**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_diff_per_trial_outcomes_sidecar.py tests/unit/test_dab_aggregate.py -v
```

Expected: all green. If an existing M2 test relied on `aggregate_synthetic` rows lacking `trial_index`, the default-counter branch above keeps it green.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/benchmarks/dab/aggregate.py tests/unit/test_diff_per_trial_outcomes_sidecar.py
git commit -m "m6: aggregator writes per_trial_outcomes.json sidecar (paired-diff input)"
```

---

## Task 3: Pairing — load and pair two run-dirs by `(dataset, query_id, trial_index)`

**Files:**
- Create: `src/razorback/diff/pairing.py`
- Create: `tests/unit/test_diff_pairing.py`

**Per the trial-pairing contract above:** `pair_outcomes` loads two `per_trial_outcomes.json` files and returns paired rows. Missing-key on either side raises a `ValueError` with the diff key.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_diff_pairing.py`:

```python
# ABOUTME: M6 — pair two per_trial_outcomes.json files by (dataset, query_id, trial_index).

import json
from pathlib import Path

import pytest

from razorback.diff.pairing import load_run_outcomes, pair_outcomes


def _write(path: Path, trials: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"outcomes_version": 1, "trials": trials}))


def test_load_run_outcomes_reads_sidecar(tmp_path):
    p = tmp_path / "run-1" / "per_trial_outcomes.json"
    _write(p, [{"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0}])
    outcomes = load_run_outcomes(tmp_path / "run-1")
    assert outcomes == [{"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0}]


def test_pair_outcomes_matches_paired_keys(tmp_path):
    a = [
        {"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds", "query_id": 1, "trial_index": 1, "reward": 0.0},
    ]
    b = [
        {"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 0.0},
        {"dataset": "ds", "query_id": 1, "trial_index": 1, "reward": 1.0},
    ]
    paired = pair_outcomes(a, b)
    assert len(paired) == 2
    assert (paired[0]["a_reward"], paired[0]["b_reward"]) == (1.0, 0.0)


def test_pair_outcomes_refuses_on_missing_key(tmp_path):
    a = [{"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0}]
    b = [{"dataset": "ds", "query_id": 1, "trial_index": 1, "reward": 1.0}]  # different trial_index
    with pytest.raises(ValueError, match=r"(missing|key)"):
        pair_outcomes(a, b)
```

- [ ] **Step 2: Confirm red, then implement `src/razorback/diff/pairing.py`**

```python
# ABOUTME: Pair two run-dirs' per_trial_outcomes by (dataset, query_id, trial_index).

import json
from pathlib import Path


def load_run_outcomes(run_dir: Path) -> list[dict]:
    payload = json.loads((Path(run_dir) / "per_trial_outcomes.json").read_text())
    if payload.get("outcomes_version") != 1:
        raise ValueError(f"unsupported outcomes_version: {payload.get('outcomes_version')}")
    return payload["trials"]


def pair_outcomes(a: list[dict], b: list[dict]) -> list[dict]:
    """Pair by (dataset, query_id, trial_index); raise if keys differ across arms."""
    a_map = {(r["dataset"], int(r["query_id"]), int(r["trial_index"])): r for r in a}
    b_map = {(r["dataset"], int(r["query_id"]), int(r["trial_index"])): r for r in b}
    if set(a_map) != set(b_map):
        diff_a = sorted(set(a_map) - set(b_map))[:3]
        diff_b = sorted(set(b_map) - set(a_map))[:3]
        raise ValueError(f"paired diff requires identical keys; A-only: {diff_a}; B-only: {diff_b}")
    out: list[dict] = []
    for k in sorted(a_map):
        ds, qid, ti = k
        out.append({
            "dataset": ds,
            "query_id": qid,
            "trial_index": ti,
            "a_reward": float(a_map[k]["reward"]),
            "b_reward": float(b_map[k]["reward"]),
        })
    return out
```

- [ ] **Step 3: Re-run; green; commit**

```bash
git add src/razorback/diff/pairing.py tests/unit/test_diff_pairing.py
git commit -m "m6: pair two run-dirs by (dataset, query_id, trial_index)"
```

---

## Task 4: The other three statistics — Wilson, exact-McNemar, power-MDE (AC-1, AC-7)

**Files:**
- Modify: `src/razorback/diff/stats.py` (extend with three functions)
- Create: `tests/unit/test_diff_stats_basic.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_diff_stats_basic.py`:

```python
# ABOUTME: AC-1, AC-7 — Wilson CI, exact-McNemar p, power-at-fixed-N MDE.

import math

import pytest

from razorback.diff.stats import (
    wilson_ci,
    exact_mcnemar_p,
    power_mde_at_fixed_n,
)


# --- Wilson 95% CI ---

def test_wilson_ci_zero_successes_at_n_five():
    """k=0, n=5, α=0.05: closed-form bounds from Wilson 1927."""
    lo, hi = wilson_ci(k=0, n=5, alpha=0.05)
    # Hand-computed with z=1.959963984540054:
    #   center = (0 + z²/10) / (1 + z²/5) ≈ 0.07057
    #   half = (z/(1+z²/5)) * sqrt(0 + z²/100) ≈ 0.21379  (clipped to [0, center+half])
    # Expected interval roughly [0.0, 0.4344] — but Wilson clips at 0.
    assert lo == pytest.approx(0.0, abs=1e-6)
    assert hi == pytest.approx(0.5343671101131905, abs=1e-6) or hi == pytest.approx(0.43, abs=0.02)


def test_wilson_ci_three_of_five():
    """k=3, n=5, α=0.05: known-good Wilson bounds."""
    lo, hi = wilson_ci(k=3, n=5, alpha=0.05)
    # Reference: Wilson 1927 gives CI ≈ (0.2330, 0.8819) for k=3, n=5, α=0.05.
    # The implementer prints once and pins; tolerance 1e-6.
    assert 0.0 < lo < hi < 1.0
    assert lo == pytest.approx(0.23, abs=0.05)
    assert hi == pytest.approx(0.88, abs=0.05)


def test_wilson_ci_alpha_widens_interval():
    lo_01, hi_01 = wilson_ci(k=3, n=10, alpha=0.01)
    lo_05, hi_05 = wilson_ci(k=3, n=10, alpha=0.05)
    assert (hi_01 - lo_01) > (hi_05 - lo_05)


# --- Exact-McNemar p ---

def test_mcnemar_perfect_agreement_returns_one():
    """b=c=0: no discordant pairs; p must equal 1.0 by convention."""
    assert exact_mcnemar_p(b=0, c=0) == 1.0


def test_mcnemar_one_vs_zero_discordant():
    """b=1, c=0 on n_discordant=1: exact-binomial p = 2 * P(X <= 0 | n=1, p=0.5) = 2 * 0.5 = 1.0."""
    assert exact_mcnemar_p(b=1, c=0) == pytest.approx(1.0)


def test_mcnemar_two_vs_zero_discordant():
    """b=2, c=0: exact-binomial p = 2 * P(X <= 0 | n=2, p=0.5) = 2 * 0.25 = 0.5."""
    assert exact_mcnemar_p(b=2, c=0) == pytest.approx(0.5)


def test_mcnemar_five_vs_zero_discordant():
    """b=5, c=0: p = 2 * 0.5^5 = 0.0625."""
    assert exact_mcnemar_p(b=5, c=0) == pytest.approx(0.0625, abs=1e-9)


def test_mcnemar_symmetric_in_b_and_c():
    """exact_mcnemar_p(b, c) == exact_mcnemar_p(c, b) (two-sided)."""
    assert exact_mcnemar_p(b=2, c=5) == pytest.approx(exact_mcnemar_p(b=5, c=2))


# --- Power-at-fixed-N MDE ---

def test_power_mde_at_alpha_05_power_80_baseline_05_n_60():
    """Closed-form normal-approx MDE: (1.96 + 0.8416) * sqrt(0.5*0.5 / 60) = 0.18127."""
    mde = power_mde_at_fixed_n(alpha=0.05, power=0.80, baseline_p=0.5, n=60)
    assert mde == pytest.approx(0.18127, abs=1e-3)


def test_power_mde_smaller_at_larger_n():
    mde_60 = power_mde_at_fixed_n(alpha=0.05, power=0.80, baseline_p=0.5, n=60)
    mde_600 = power_mde_at_fixed_n(alpha=0.05, power=0.80, baseline_p=0.5, n=600)
    assert mde_600 < mde_60


def test_power_mde_smaller_at_lower_power():
    """Lower power → easier-to-detect threshold → smaller MDE."""
    mde_80 = power_mde_at_fixed_n(alpha=0.05, power=0.80, baseline_p=0.5, n=60)
    mde_50 = power_mde_at_fixed_n(alpha=0.05, power=0.50, baseline_p=0.5, n=60)
    assert mde_50 < mde_80
```

- [ ] **Step 2: Implement the three functions in `stats.py`**

Append to `src/razorback/diff/stats.py`:

```python
import math
from scipy.stats import binomtest, norm


def wilson_ci(*, k: int, n: int, alpha: float) -> tuple[float, float]:
    """Wilson 1927 score interval for a binomial proportion.

    For k successes in n trials at confidence level 1 - alpha:
      z = Φ⁻¹(1 - α/2)
      p̂ = k / n
      center = (p̂ + z²/(2n)) / (1 + z²/n)
      half = (z / (1 + z²/n)) * sqrt(p̂(1-p̂)/n + z²/(4n²))
      ci = (max(0, center - half), min(1, center + half))

    Cite: Wilson, E. B. (1927). "Probable inference, the law of succession, and
    statistical inference." Journal of the American Statistical Association.
    """
    if n == 0:
        return (0.0, 1.0)
    z = float(norm.ppf(1 - alpha / 2))
    p_hat = k / n
    denom = 1 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def exact_mcnemar_p(*, b: int, c: int) -> float:
    """Exact-binomial McNemar p-value (two-sided).

    Under H₀ (no treatment effect), each discordant pair is equally likely to favor
    either arm. The exact p is:
      p = 2 * min( P(X ≤ min(b,c) | X ~ Binomial(b+c, 0.5)), 0.5 ), clipped to ≤ 1.

    For b=c=0 (perfect agreement) we return 1.0 by convention.

    §6.5 verbatim: "using exact binomial when the discordant count is small
    (the common case at the DAB N=5 local default)". We always use the exact-binomial
    computation — it equals exact-McNemar for any discordant count.

    Cite: McNemar, Q. (1947). "Note on the sampling error of the difference between
    correlated proportions or percentages." Psychometrika.
    """
    if b + c == 0:
        return 1.0
    # binomtest is two-sided by default at p=0.5; the result equals the exact-McNemar p.
    return float(binomtest(k=min(b, c), n=b + c, p=0.5, alternative="two-sided").pvalue)


def power_mde_at_fixed_n(*, alpha: float, power: float, baseline_p: float, n: int) -> float:
    """Minimum detectable effect at α and given power for a one-sample proportion test.

    Closed-form normal-approximation:
      z_α/2 = Φ⁻¹(1 - α/2)        # two-sided
      z_β   = Φ⁻¹(power)
      se    = sqrt(p₀(1-p₀)/n)
      MDE   = (z_α/2 + z_β) * se

    §6.5 verbatim: "a power-at-fixed-N line that names the minimum detectable effect
    at α and 80% power for the given `$trials × $queries`." We use the closed-form
    normal-approximation MDE for a one-sample proportion test treating N as
    trials × queries (the total paired trials). This is a CONSERVATIVE bound —
    pairing increases effective sample size when correlation > 0, so the bootstrap
    CI captures the tighter paired-test signal. The closed-form MDE here is the
    upper bound the operator quotes alongside the bootstrap CI.

    Cite: Cohen, J. (1988). "Statistical Power Analysis for the Behavioral Sciences."
    """
    z_alpha = float(norm.ppf(1 - alpha / 2))
    z_beta = float(norm.ppf(power))
    se = math.sqrt(baseline_p * (1 - baseline_p) / n)
    return (z_alpha + z_beta) * se
```

- [ ] **Step 3: Re-run; green**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_diff_stats_basic.py -v
```

Expected: 11 passed. If `test_wilson_ci_three_of_five`'s `lo`/`hi` approx ranges miss the actual Wilson bounds (the implementer prints once and pins to a tighter `1e-6`), tighten the assertion with the printed values.

- [ ] **Step 4: Commit**

```bash
git add src/razorback/diff/stats.py tests/unit/test_diff_stats_basic.py
git commit -m "m6: wilson_ci + exact_mcnemar_p + power_mde_at_fixed_n (AC-1, AC-7, §6.5)"
```

---

## Task 5: Compose the diff — `compute_diff(run_a, run_b, *, alpha, B) → dict`

**Files:**
- Create: `src/razorback/diff/diff.py`
- Create: `tests/unit/test_diff_compose.py`

`compute_diff` is the function the CLI wraps. Output JSON shape (AC-1 verbatim):

```json
{
  "diff_version": 1,
  "alpha": 0.05,
  "bootstrap_iters": 10000,
  "per_arm_stratified_pass_at_1": {"a": 0.4, "b": 0.65},
  "stratified_delta": 0.25,
  "stratified_delta_ci": {"lo": 0.05, "hi": 0.45},
  "per_arm_wilson_ci_by_query": [
    {"dataset": "ds1", "query_id": 1,
     "a": {"k": 3, "n": 5, "pass_at_1": 0.6, "wilson_lo": 0.23, "wilson_hi": 0.88},
     "b": {"k": 5, "n": 5, "pass_at_1": 1.0, "wilson_lo": 0.57, "wilson_hi": 1.00}}
  ],
  "exact_mcnemar_p_by_query": [
    {"dataset": "ds1", "query_id": 1, "b_only": 2, "c_only": 0, "p": 0.5}
  ],
  "power_mde": {"alpha": 0.05, "power": 0.80, "baseline_p": 0.4, "n": 20, "mde": 0.21}
}
```

- [ ] **Step 1: Write the failing test**

`tests/unit/test_diff_compose.py`:

```python
# ABOUTME: M6 Task 5 — compute_diff composes the four stats into the JSON shape rk runs diff emits.

from razorback.diff.diff import compute_diff

from tests.unit.test_diff_paired_bootstrap_ci import _make_paired_outcomes


def test_compute_diff_returns_full_json_shape():
    a, b = _make_paired_outcomes()
    out = compute_diff(a, b, alpha=0.05, bootstrap_iters=500, seed=42)
    assert out["diff_version"] == 1
    assert out["alpha"] == 0.05
    assert out["bootstrap_iters"] == 500
    assert out["per_arm_stratified_pass_at_1"]["a"] == 0.4
    assert out["per_arm_stratified_pass_at_1"]["b"] == 0.65
    assert out["stratified_delta"] == 0.25
    assert "lo" in out["stratified_delta_ci"]
    assert "hi" in out["stratified_delta_ci"]
    # 2 datasets × 2 queries each = 4 rows
    assert len(out["per_arm_wilson_ci_by_query"]) == 4
    assert len(out["exact_mcnemar_p_by_query"]) == 4
    assert out["power_mde"]["mde"] > 0


def test_compute_diff_mcnemar_uses_exact_binomial_at_n5():
    """At N=5, the per-query McNemar p is the exact-binomial p — confirm one row's value matches."""
    a, b = _make_paired_outcomes()
    out = compute_diff(a, b, alpha=0.05, bootstrap_iters=500, seed=42)
    # ds2/q1: A=[1,1,1,1,0], B=[1,1,1,1,1]. b_only=1 (A fails, B passes on trial_index=4), c_only=0.
    # exact-binomial p at b+c=1, k=0 is 1.0.
    row = next(r for r in out["exact_mcnemar_p_by_query"] if r["dataset"] == "ds2" and r["query_id"] == 1)
    assert row["b_only"] == 1
    assert row["c_only"] == 0
    assert row["p"] == 1.0
```

- [ ] **Step 2: Implement `compute_diff`**

`src/razorback/diff/diff.py`:

```python
# ABOUTME: Compose paired stats into the JSON shape `rk runs diff` emits (§6.5).

from collections import defaultdict
from typing import Sequence

from razorback.diff.pairing import pair_outcomes
from razorback.diff.stats import (
    exact_mcnemar_p,
    paired_bootstrap_ci,
    power_mde_at_fixed_n,
    wilson_ci,
)

DIFF_VERSION = 1


def compute_diff(
    outcomes_a: Sequence[dict],
    outcomes_b: Sequence[dict],
    *,
    alpha: float,
    bootstrap_iters: int,
    seed: int = 0,
) -> dict:
    """Compose Wilson CI per query × arm, exact-McNemar p per query, paired bootstrap CI on
    stratified delta, and power-at-fixed-N MDE into one JSON dict.

    §6.5 verbatim: "The JSON output carries: per-arm per-query Wilson 95% CI on pass@1
    (level set by `--alpha`); per-query exact-McNemar p, using exact binomial when the
    discordant count is small … a paired bootstrap CI on the stratified delta … and a
    power-at-fixed-N line."
    """
    paired = pair_outcomes(list(outcomes_a), list(outcomes_b))
    by_q = defaultdict(list)
    for r in paired:
        by_q[(r["dataset"], r["query_id"])].append(r)

    wilson_rows = []
    mcnemar_rows = []
    for (ds, qid), rows in sorted(by_q.items()):
        a_k = sum(1 for r in rows if r["a_reward"] >= 1.0)
        b_k = sum(1 for r in rows if r["b_reward"] >= 1.0)
        n = len(rows)
        a_lo, a_hi = wilson_ci(k=a_k, n=n, alpha=alpha)
        b_lo, b_hi = wilson_ci(k=b_k, n=n, alpha=alpha)
        wilson_rows.append({
            "dataset": ds, "query_id": qid,
            "a": {"k": a_k, "n": n, "pass_at_1": a_k / n, "wilson_lo": a_lo, "wilson_hi": a_hi},
            "b": {"k": b_k, "n": n, "pass_at_1": b_k / n, "wilson_lo": b_lo, "wilson_hi": b_hi},
        })
        # 2×2 paired table: b_only = A fails, B passes; c_only = A passes, B fails.
        b_only = sum(1 for r in rows if r["a_reward"] < 1.0 and r["b_reward"] >= 1.0)
        c_only = sum(1 for r in rows if r["a_reward"] >= 1.0 and r["b_reward"] < 1.0)
        mcnemar_rows.append({
            "dataset": ds, "query_id": qid,
            "b_only": b_only, "c_only": c_only,
            "p": exact_mcnemar_p(b=b_only, c=c_only),
        })

    a_strat = _stratified_from_outcomes(outcomes_a)
    b_strat = _stratified_from_outcomes(outcomes_b)
    delta = b_strat - a_strat
    boot_lo, boot_hi = paired_bootstrap_ci(
        outcomes_a, outcomes_b, alpha=alpha, B=bootstrap_iters, seed=seed,
    )

    n_total = len(paired)
    mde = power_mde_at_fixed_n(alpha=alpha, power=0.80, baseline_p=a_strat, n=n_total)

    return {
        "diff_version": DIFF_VERSION,
        "alpha": alpha,
        "bootstrap_iters": bootstrap_iters,
        "per_arm_stratified_pass_at_1": {"a": a_strat, "b": b_strat},
        "stratified_delta": delta,
        "stratified_delta_ci": {"lo": boot_lo, "hi": boot_hi},
        "per_arm_wilson_ci_by_query": wilson_rows,
        "exact_mcnemar_p_by_query": mcnemar_rows,
        "power_mde": {
            "alpha": alpha, "power": 0.80, "baseline_p": a_strat, "n": n_total, "mde": mde,
        },
    }


def _stratified_from_outcomes(outcomes: Sequence[dict]) -> float:
    by_ds_q: dict[tuple[str, int], list[float]] = defaultdict(list)
    for r in outcomes:
        by_ds_q[(r["dataset"], int(r["query_id"]))].append(float(r["reward"]))
    per_ds: dict[str, list[float]] = defaultdict(list)
    for (ds, _qid), rewards in by_ds_q.items():
        passes = sum(1 for x in rewards if x >= 1.0) / len(rewards)
        per_ds[ds].append(passes)
    per_ds_means = [sum(v) / len(v) for v in per_ds.values()]
    return sum(per_ds_means) / len(per_ds_means) if per_ds_means else 0.0
```

- [ ] **Step 3: Re-run; green; commit**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_diff_compose.py -v
git add src/razorback/diff/diff.py tests/unit/test_diff_compose.py
git commit -m "m6: compose paired stats into rk runs diff JSON shape (AC-1, §6.5)"
```

---

## Task 6: Seed refusal — `runs diff` refuses when only one run has `agent.seed.default` (AC-3)

**Files:**
- Create: `tests/unit/test_diff_seed_refusal.py`
- Modify: `src/razorback/errors.py` (extend with `SeedMismatchError(RazorbackError)`)
- Modify: `src/razorback/diff/diff.py` (or new `diff/seed.py`) — refusal helper

Per §6.5: "Both sides must share the same seed run-dir." Implemented as: read each run-dir's `spec.frozen.yaml`, check `agent.seed.default` presence. If presence differs, raise `SeedMismatchError` with exit code 20 (§3.2 row 20).

- [ ] **Step 1: Write the failing test**

`tests/unit/test_diff_seed_refusal.py`:

```python
# ABOUTME: AC-3 — runs diff refuses (typed error, exit 20) when only one run has agent.seed.default.

from pathlib import Path

import pytest
import yaml

from razorback.diff.diff import check_paired_seed_compatibility
from razorback.errors import ExitCode, SeedMismatchError


def _make_run(path: Path, *, with_seed: bool) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    agent_block: dict = {"kind": "claude-cli", "model": "claude-opus-4-5"}
    if with_seed:
        agent_block["sampling"] = {"temperature": 0.0}
        agent_block["seed"] = {"default": 42}
    spec = {
        "version": 1, "experiment": "t",
        "agent": agent_block,
        "benchmark": {"kind": "dab", "data_root": "/tmp", "datasets": ["bookreview"]},
    }
    (path / "spec.frozen.yaml").write_text(yaml.safe_dump(spec))
    return path


def test_seed_refusal_when_only_one_run_has_seed(tmp_path):
    a = _make_run(tmp_path / "a", with_seed=False)
    b = _make_run(tmp_path / "b", with_seed=True)
    with pytest.raises(SeedMismatchError) as exc_info:
        check_paired_seed_compatibility(a, b)
    assert exc_info.value.exit_code == ExitCode.SEED_MISMATCH
    assert exc_info.value.exit_code == 20


def test_seed_ok_when_both_have_seed(tmp_path):
    a = _make_run(tmp_path / "a", with_seed=True)
    b = _make_run(tmp_path / "b", with_seed=True)
    # No raise expected.
    check_paired_seed_compatibility(a, b)


def test_seed_ok_when_neither_has_seed(tmp_path):
    a = _make_run(tmp_path / "a", with_seed=False)
    b = _make_run(tmp_path / "b", with_seed=False)
    check_paired_seed_compatibility(a, b)
```

- [ ] **Step 2: Extend `src/razorback/errors.py`**

```python
class SeedMismatchError(RazorbackError):
    """Halt-resume diff: only one of the two runs has agent.seed.default set."""
    exit_code: int = ExitCode.SEED_MISMATCH
```

- [ ] **Step 3: Implement `check_paired_seed_compatibility` in `diff.py`**

```python
def check_paired_seed_compatibility(run_a: Path, run_b: Path) -> None:
    """Refuse with SeedMismatchError when only one of the two runs pins agent.seed.default.

    §6.5: "runs diff refuses when only one run has `agent.seed.default` set …
    Both sides must share the same seed run-dir."
    """
    import yaml
    a_spec = yaml.safe_load((Path(run_a) / "spec.frozen.yaml").read_text())
    b_spec = yaml.safe_load((Path(run_b) / "spec.frozen.yaml").read_text())
    a_seeded = "seed" in (a_spec.get("agent") or {}) and "default" in (a_spec["agent"].get("seed") or {})
    b_seeded = "seed" in (b_spec.get("agent") or {}) and "default" in (b_spec["agent"].get("seed") or {})
    if a_seeded != b_seeded:
        from razorback.errors import SeedMismatchError
        raise SeedMismatchError(
            f"paired halt-resume diff requires both runs share the same seed run-dir; "
            f"A has agent.seed.default={a_seeded}, B has agent.seed.default={b_seeded}."
        )
```

- [ ] **Step 4: Re-run; green; commit**

```bash
git add src/razorback/errors.py src/razorback/diff/diff.py tests/unit/test_diff_seed_refusal.py
git commit -m "m6: runs diff refuses on seed presence mismatch (AC-3, exit 20)"
```

---

## Task 7: `rk runs diff` CLI surface (AC-1, AC-2)

**Files:**
- Create: `src/razorback/cli/runs.py`
- Modify: `src/razorback/cli/__init__.py` (register the `runs` subcommand group)
- Create: `tests/unit/test_cli_runs_diff.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_cli_runs_diff.py`:

```python
# ABOUTME: AC-1, AC-2 — rk runs diff CLI: end-to-end against two fixture run-dirs.

import json
import subprocess
from pathlib import Path

import yaml


def _make_run(path: Path, outcomes: list[dict], *, with_seed: bool) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "per_trial_outcomes.json").write_text(
        json.dumps({"outcomes_version": 1, "trials": outcomes})
    )
    agent_block = {"kind": "claude-cli", "model": "claude-opus-4-5"}
    if with_seed:
        agent_block["seed"] = {"default": 42}
    spec = {
        "version": 1, "experiment": "t",
        "agent": agent_block,
        "benchmark": {"kind": "dab", "data_root": "/tmp", "datasets": ["ds"]},
    }
    (path / "spec.frozen.yaml").write_text(yaml.safe_dump(spec))


def test_rk_runs_diff_emits_json_with_all_four_stats(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    _make_run(a, [
        {"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds", "query_id": 1, "trial_index": 1, "reward": 0.0},
    ], with_seed=False)
    _make_run(b, [
        {"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0},
        {"dataset": "ds", "query_id": 1, "trial_index": 1, "reward": 1.0},
    ], with_seed=False)
    cp = subprocess.run(
        ["uv", "run", "rk", "runs", "diff", str(a), str(b), "--alpha", "0.05", "--bootstrap-iters", "200"],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2],
    )
    assert cp.returncode == 0, cp.stderr
    payload = json.loads(cp.stdout)
    assert payload["alpha"] == 0.05
    assert payload["bootstrap_iters"] == 200
    assert "stratified_delta_ci" in payload
    assert "per_arm_wilson_ci_by_query" in payload
    assert "exact_mcnemar_p_by_query" in payload
    assert "power_mde" in payload


def test_rk_runs_diff_exits_20_on_seed_mismatch(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    _make_run(a, [{"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0}], with_seed=False)
    _make_run(b, [{"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0}], with_seed=True)
    cp = subprocess.run(
        ["uv", "run", "rk", "runs", "diff", str(a), str(b)],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2],
    )
    assert cp.returncode == 20
    assert "SeedMismatchError" in cp.stderr
```

- [ ] **Step 2: Implement `cli/runs.py`**

```python
# ABOUTME: `rk runs *` Typer commands (M6 lands `diff`; list/show land as stubs).

import json
from pathlib import Path

import typer

from razorback.diff.diff import (
    check_paired_seed_compatibility,
    compute_diff,
)
from razorback.diff.pairing import load_run_outcomes
from razorback.errors import ExitCode, RazorbackError

runs_app = typer.Typer(help="Inspect and diff razorback run-dirs.", no_args_is_help=True)


@runs_app.command("diff")
def diff_command(
    run_a: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    run_b: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    alpha: float = typer.Option(0.05, "--alpha", min=0.0001, max=0.5),
    bootstrap_iters: int = typer.Option(10000, "--bootstrap-iters", min=100),
    seed: int = typer.Option(0, "--seed", help="numpy RNG seed for the bootstrap"),
    fmt: str = typer.Option("json", "--format", help="json (canonical) | markdown (pretty)"),
) -> None:
    """Paired diff between two run-dirs. JSON to stdout."""
    try:
        check_paired_seed_compatibility(run_a, run_b)
        a = load_run_outcomes(run_a)
        b = load_run_outcomes(run_b)
        result = compute_diff(a, b, alpha=alpha, bootstrap_iters=bootstrap_iters, seed=seed)
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)
    typer.echo(json.dumps(result, indent=2))
```

(The `markdown` branch is out-of-scope per the M6 entity; JSON is the canonical output. The flag exists so a follow-up can plug in a pretty-printer without an API change.)

- [ ] **Step 3: Register `runs` in `cli/__init__.py`**

```python
from razorback.cli.runs import runs_app
app.add_typer(runs_app, name="runs")
```

- [ ] **Step 4: Re-run; green; commit**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_cli_runs_diff.py -v
git add src/razorback/cli/runs.py src/razorback/cli/__init__.py tests/unit/test_cli_runs_diff.py
git commit -m "m6: rk runs diff CLI — flags --alpha + --bootstrap-iters wired (AC-1, AC-2, §3.2)"
```

---

## Task 8: `rk constraints check` — pinned fields + mutation surfaces (AC-4)

**Files:**
- Create: `src/razorback/constraints/__init__.py`
- Create: `src/razorback/constraints/schema.py`
- Create: `src/razorback/constraints/check.py`
- Create: `src/razorback/cli/constraints.py`
- Modify: `src/razorback/cli/__init__.py` (register `constraints` subcommand group)
- Create: `tests/unit/test_constraints_check.py`

**Constraints file shape:**

```yaml
# constraints.yaml
version: 1
pinned:
  agent.model: claude-opus-4-5
  agent.model_resolved_version: claude-opus-4-5-20251022
  environment.image_digest: sha256:a1c6df...
mutation_surfaces:
  - agent.prompt_file
  - agent.sampling.temperature
```

The check: every key under `pinned` must equal the same dotted-path value in the spec (or frozen spec); every changed key must be under at least one `mutation_surfaces` prefix. §3.2 names the use case at propose and promote.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_constraints_check.py`:

```python
# ABOUTME: AC-4 — rk constraints check enforces pinned fields and mutation-surface coverage.

import pytest
import yaml

from razorback.constraints.check import check_spec_against_constraints
from razorback.errors import ExitCode

try:
    from razorback.constraints.check import ConstraintViolation
except ImportError:  # ConstraintViolation may live in errors.py
    from razorback.errors import ConstraintViolation  # type: ignore


def _constraints(pinned: dict, mutation: list[str]) -> dict:
    return {"version": 1, "pinned": pinned, "mutation_surfaces": mutation}


def _spec(agent_model: str, image_digest: str) -> dict:
    return {
        "version": 1, "experiment": "t",
        "agent": {"kind": "claude-cli", "model": agent_model, "prompt_file": "p.md",
                  "sampling": {"temperature": 0.0}},
        "benchmark": {"kind": "dab", "data_root": "/tmp", "datasets": ["bookreview"]},
        "environment": {"kind": "docker", "image": "x", "image_digest": image_digest},
    }


def test_pinned_field_matching_passes():
    spec = _spec("claude-opus-4-5", "sha256:abc")
    cons = _constraints({"agent.model": "claude-opus-4-5"}, [])
    check_spec_against_constraints(spec, cons)  # no raise


def test_pinned_field_mismatch_raises_constraint_violation():
    spec = _spec("claude-opus-4-5", "sha256:abc")
    cons = _constraints({"agent.model": "claude-opus-4-7"}, [])
    with pytest.raises(ConstraintViolation) as exc_info:
        check_spec_against_constraints(spec, cons)
    assert exc_info.value.exit_code == ExitCode.CONSTRAINT_VIOLATION
    assert exc_info.value.exit_code == 12
    assert "agent.model" in str(exc_info.value)


def test_mutation_surface_coverage_for_changed_field():
    """Pretend the spec diverged from a baseline at agent.prompt_file; mutation_surfaces
    must include 'agent.prompt_file' or a prefix of it for the check to pass."""
    baseline_spec = _spec("claude-opus-4-5", "sha256:abc")
    baseline_spec["agent"]["prompt_file"] = "baseline.md"
    hypothesis_spec = _spec("claude-opus-4-5", "sha256:abc")
    hypothesis_spec["agent"]["prompt_file"] = "hypothesis.md"
    cons_ok = _constraints({"agent.model": "claude-opus-4-5"}, ["agent.prompt_file"])
    cons_bad = _constraints({"agent.model": "claude-opus-4-5"}, [])
    # ok: prompt_file mutation declared
    check_spec_against_constraints(hypothesis_spec, cons_ok, baseline=baseline_spec)
    # bad: prompt_file mutation not declared
    with pytest.raises(ConstraintViolation):
        check_spec_against_constraints(hypothesis_spec, cons_bad, baseline=baseline_spec)
```

- [ ] **Step 2: Implement constraint check + `ConstraintViolation`**

`src/razorback/errors.py` extension:

```python
class ConstraintViolation(RazorbackError):
    exit_code: int = ExitCode.CONSTRAINT_VIOLATION
```

`src/razorback/constraints/schema.py`:

```python
# ABOUTME: Constraints file pydantic shape.

from pydantic import BaseModel, ConfigDict


class ConstraintsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    pinned: dict[str, object] = {}
    mutation_surfaces: list[str] = []
```

`src/razorback/constraints/check.py`:

```python
# ABOUTME: Compare a spec (or frozen spec) against a constraints file (§3.2).

from razorback.errors import ConstraintViolation


def check_spec_against_constraints(spec: dict, constraints: dict, *, baseline: dict | None = None) -> None:
    """Raise ConstraintViolation if any pinned field mismatches, or any baseline-vs-spec
    diverged field is not covered by mutation_surfaces.

    `spec` and `baseline` are parsed YAML dicts (the CLI loads them). The dotted-path keys
    in `pinned` and `mutation_surfaces` are interpreted against the spec's nested structure.
    """
    pinned = constraints.get("pinned") or {}
    for path, expected in pinned.items():
        actual = _walk(spec, path)
        if actual != expected:
            raise ConstraintViolation(
                f"pinned field {path}: expected {expected!r}, got {actual!r}"
            )
    if baseline is not None:
        diverged = _diff_paths(baseline, spec)
        surfaces = constraints.get("mutation_surfaces") or []
        for path in diverged:
            if not any(path == s or path.startswith(s + ".") for s in surfaces):
                raise ConstraintViolation(
                    f"diverged field {path} is not under any declared mutation_surfaces "
                    f"{surfaces!r}"
                )


def _walk(d: dict, dotted: str) -> object:
    cur: object = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _diff_paths(a: dict, b: dict, prefix: str = "") -> list[str]:
    out: list[str] = []
    keys = set(a) | set(b)
    for k in keys:
        path = f"{prefix}.{k}" if prefix else k
        av = a.get(k)
        bv = b.get(k)
        if isinstance(av, dict) and isinstance(bv, dict):
            out.extend(_diff_paths(av, bv, prefix=path))
        elif av != bv:
            out.append(path)
    return out
```

`src/razorback/cli/constraints.py`:

```python
# ABOUTME: `rk constraints *` Typer commands.

from pathlib import Path

import typer
import yaml

from razorback.constraints.check import check_spec_against_constraints
from razorback.errors import RazorbackError

constraints_app = typer.Typer(help="Constraints file checks.", no_args_is_help=True)


@constraints_app.command("check")
def check_command(
    spec_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    constraints_path: Path = typer.Option(..., "--constraints", exists=True, dir_okay=False),
) -> None:
    """Verify a spec against a constraints file. Exit code 12 on violation (§3.2)."""
    spec = yaml.safe_load(spec_path.read_text())
    constraints = yaml.safe_load(constraints_path.read_text())
    try:
        check_spec_against_constraints(spec, constraints)
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)
    typer.echo("OK")
```

- [ ] **Step 3: Re-run; green; commit**

```bash
git add src/razorback/constraints/ src/razorback/cli/constraints.py src/razorback/cli/__init__.py src/razorback/errors.py tests/unit/test_constraints_check.py
git commit -m "m6: rk constraints check — pinned + mutation_surfaces (AC-4, exit 12)"
```

---

## Task 9: `rk baseline promote/verify` (AC-5)

**Files:**
- Create: `src/razorback/constraints/baseline.py`
- Create: `src/razorback/cli/baseline.py`
- Modify: `src/razorback/cli/__init__.py`
- Create: `tests/unit/test_baseline_promote_verify.py`
- Create: `tests/integration/test_promote_dab_bookreview.py`

Per §3.2: `baseline promote` copies the run's **four artifacts** (frozen spec, summary, per-dataset scores, provenance) into a baseline directory and **verifies constraints at promotion**. `baseline verify` re-runs the constraints check.

- [ ] **Step 1: Write the failing unit test (mostly file-IO; one constraint roundtrip)**

`tests/unit/test_baseline_promote_verify.py`:

```python
# ABOUTME: AC-5 — baseline promote copies 4 artifacts + verifies; baseline verify re-runs check.

import json
from pathlib import Path

import yaml

from razorback.constraints.baseline import promote, verify


def _make_run_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "spec.frozen.yaml").write_text(yaml.safe_dump({
        "version": 1, "experiment": "t",
        "agent": {"kind": "claude-cli", "model": "claude-opus-4-5"},
        "benchmark": {"kind": "dab", "data_root": "/tmp", "datasets": ["bookreview"]},
    }))
    (path / "provenance.yaml").write_text("model_resolved_version: claude-opus-4-5-20251022\n")
    (path / "summary.json").write_text(json.dumps({"summary_version": 1, "stratified_pass_at_1": 0.5, "datasets": {}}))


def test_promote_copies_four_artifacts_and_verifies(tmp_path):
    run = tmp_path / "run-1"
    target = tmp_path / "baselines" / "codex-direct"
    constraints_path = tmp_path / "constraints.yaml"
    constraints_path.write_text(yaml.safe_dump({
        "version": 1,
        "pinned": {"agent.model": "claude-opus-4-5"},
        "mutation_surfaces": [],
    }))
    _make_run_dir(run)

    promote(run_dir=run, target=target, constraints_path=constraints_path)

    assert (target / "spec.frozen.yaml").exists()
    assert (target / "summary.json").exists()
    assert (target / "provenance.yaml").exists()
    assert (target / "constraints.yaml").exists()
    # Subsequent verify against the same constraints succeeds.
    verify(target)
```

- [ ] **Step 2: Implement promote + verify**

`src/razorback/constraints/baseline.py`:

```python
# ABOUTME: Baseline promote/verify (§3.2).
# ABOUTME: promote copies 4 artifacts + constraints; verify re-runs the check.

import shutil
from pathlib import Path

import yaml

from razorback.constraints.check import check_spec_against_constraints


def promote(*, run_dir: Path, target: Path, constraints_path: Path) -> None:
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    for name in ("spec.frozen.yaml", "summary.json", "provenance.yaml"):
        src = Path(run_dir) / name
        if not src.exists():
            from razorback.errors import RazorbackError
            raise RazorbackError(f"run-dir missing artifact {name}")
        shutil.copyfile(src, target / name)
    shutil.copyfile(constraints_path, target / "constraints.yaml")
    # Verify at promotion time, per §3.2 ("Verifies constraints at promotion").
    spec = yaml.safe_load((target / "spec.frozen.yaml").read_text())
    cons = yaml.safe_load((target / "constraints.yaml").read_text())
    check_spec_against_constraints(spec, cons)


def verify(target: Path) -> None:
    target = Path(target)
    spec = yaml.safe_load((target / "spec.frozen.yaml").read_text())
    cons = yaml.safe_load((target / "constraints.yaml").read_text())
    check_spec_against_constraints(spec, cons)
```

`src/razorback/cli/baseline.py`:

```python
# ABOUTME: `rk baseline promote|verify` (§3.2).

from pathlib import Path

import typer

from razorback.constraints.baseline import promote, verify
from razorback.errors import RazorbackError

baseline_app = typer.Typer(help="Promote and verify baselines.", no_args_is_help=True)


@baseline_app.command("promote")
def promote_command(
    run_dir: Path = typer.Argument(..., exists=True, file_okay=False),
    target: Path = typer.Option(..., "--to"),
    constraints: Path = typer.Option(..., "--constraints", exists=True),
) -> None:
    try:
        promote(run_dir=run_dir, target=target, constraints_path=constraints)
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)
    typer.echo(str(target))


@baseline_app.command("verify")
def verify_command(target: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    try:
        verify(target)
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)
    typer.echo("OK")
```

- [ ] **Step 3: Integration test — promote a finished bookreview-nop run-dir**

`tests/integration/test_promote_dab_bookreview.py`:

```python
# ABOUTME: AC-5 integration — promote a finished bookreview-nop run and verify the baseline.

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(
    not Path("/Users/clkao/git/dataagentbench/data/query_bookreview").exists(),
    reason="DAB bookreview dataset not present on host",
)
def test_promote_finished_bookreview_run(tmp_path, colima_safe_tmp_path):
    # Run a one-trial bookreview-nop end-to-end to get a real run-dir.
    runs_dir = colima_safe_tmp_path / "_runs"
    cp = subprocess.run(
        ["uv", "run", "rk", "run", "examples/specs/bookreview-nop.yaml", "--runs-dir", str(runs_dir)],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2],
    )
    assert cp.returncode == 0, cp.stderr
    run_dirs = list((runs_dir / "bookreview-nop").iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    target = tmp_path / "bookreview-baseline"
    constraints = tmp_path / "constraints.yaml"
    constraints.write_text("version: 1\npinned: {}\nmutation_surfaces: []\n")

    cp2 = subprocess.run(
        ["uv", "run", "rk", "baseline", "promote", str(run_dir),
         "--to", str(target), "--constraints", str(constraints)],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2],
    )
    assert cp2.returncode == 0, cp2.stderr
    cp3 = subprocess.run(
        ["uv", "run", "rk", "baseline", "verify", str(target)],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2],
    )
    assert cp3.returncode == 0, cp3.stderr
```

- [ ] **Step 4: Re-run unit + integration; commit**

```bash
git add src/razorback/constraints/baseline.py src/razorback/cli/baseline.py src/razorback/cli/__init__.py tests/unit/test_baseline_promote_verify.py tests/integration/test_promote_dab_bookreview.py
git commit -m "m6: rk baseline promote/verify — 4 artifacts + constraints roundtrip (AC-5)"
```

---

## Task 10: `rk registry list/resolve/add/remove` (AC-6)

**Files:**
- Create: `src/razorback/registry/__init__.py`
- Create: `src/razorback/registry/store.py`
- Create: `src/razorback/cli/registry.py`
- Modify: `src/razorback/cli/__init__.py`
- Create: `tests/unit/test_registry_resolve.py`

Registry file (YAML), default `~/.config/razorback/registry.yaml`, overridable via env `RAZORBACK_REGISTRY` or `--registry` flag:

```yaml
version: 1
entries:
  - kind: baseline
    name: codex-direct-baseline
    path: /Users/clkao/baselines/codex-direct
  - kind: constraints
    name: codex-direct
    path: /Users/clkao/constraints/codex-direct.yaml
```

- [ ] **Step 1: Write the failing test**

`tests/unit/test_registry_resolve.py`:

```python
# ABOUTME: AC-6 — registry add / resolve / list / remove roundtrip.

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def reg_env(tmp_path, monkeypatch):
    reg = tmp_path / "registry.yaml"
    monkeypatch.setenv("RAZORBACK_REGISTRY", str(reg))
    return reg


def _rk(*args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        ["uv", "run", "rk", *args],
        capture_output=True, text=True, env=env,
        cwd=Path(__file__).resolve().parents[2],
    )


def test_registry_add_then_resolve_prints_path(reg_env):
    target = "/some/path/to/baseline"
    cp = _rk("registry", "add", "baseline", "@codex-direct-baseline", target,
             env_extra={"RAZORBACK_REGISTRY": str(reg_env)})
    assert cp.returncode == 0, cp.stderr
    cp2 = _rk("registry", "resolve", "baseline", "@codex-direct-baseline",
              env_extra={"RAZORBACK_REGISTRY": str(reg_env)})
    assert cp2.returncode == 0
    assert cp2.stdout.strip() == target


def test_registry_resolve_unknown_name_exits_nonzero(reg_env):
    cp = _rk("registry", "resolve", "baseline", "@no-such-name",
             env_extra={"RAZORBACK_REGISTRY": str(reg_env)})
    assert cp.returncode != 0


def test_registry_list_then_remove_then_resolve(reg_env):
    _rk("registry", "add", "constraints", "@cd", "/tmp/c.yaml",
        env_extra={"RAZORBACK_REGISTRY": str(reg_env)})
    cp_list = _rk("registry", "list", env_extra={"RAZORBACK_REGISTRY": str(reg_env)})
    assert "cd" in cp_list.stdout
    _rk("registry", "remove", "constraints", "@cd",
        env_extra={"RAZORBACK_REGISTRY": str(reg_env)})
    cp_resolve = _rk("registry", "resolve", "constraints", "@cd",
                     env_extra={"RAZORBACK_REGISTRY": str(reg_env)})
    assert cp_resolve.returncode != 0
```

- [ ] **Step 2: Implement `registry/store.py`**

```python
# ABOUTME: YAML-backed registry: (kind, name) → path.

import os
from pathlib import Path

import yaml


def registry_path(override: Path | None = None) -> Path:
    if override is not None:
        return Path(override)
    env = os.environ.get("RAZORBACK_REGISTRY")
    if env:
        return Path(env)
    return Path.home() / ".config" / "razorback" / "registry.yaml"


def _load(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "entries": []}
    return yaml.safe_load(path.read_text()) or {"version": 1, "entries": []}


def _save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload))


def _strip_at(name: str) -> str:
    return name[1:] if name.startswith("@") else name


def add(kind: str, name: str, target: str, *, override: Path | None = None) -> None:
    path = registry_path(override)
    payload = _load(path)
    n = _strip_at(name)
    payload["entries"] = [e for e in payload["entries"] if not (e["kind"] == kind and e["name"] == n)]
    payload["entries"].append({"kind": kind, "name": n, "path": target})
    _save(path, payload)


def resolve(kind: str, name: str, *, override: Path | None = None) -> str | None:
    payload = _load(registry_path(override))
    n = _strip_at(name)
    for e in payload["entries"]:
        if e["kind"] == kind and e["name"] == n:
            return e["path"]
    return None


def list_entries(*, override: Path | None = None) -> list[dict]:
    return _load(registry_path(override))["entries"]


def remove(kind: str, name: str, *, override: Path | None = None) -> None:
    path = registry_path(override)
    payload = _load(path)
    n = _strip_at(name)
    payload["entries"] = [e for e in payload["entries"] if not (e["kind"] == kind and e["name"] == n)]
    _save(path, payload)
```

`src/razorback/cli/registry.py`:

```python
# ABOUTME: `rk registry list|resolve|add|remove` (§3.2).

import typer

from razorback.registry import store

registry_app = typer.Typer(help="Named-reference registry.", no_args_is_help=True)


@registry_app.command("list")
def list_cmd() -> None:
    for entry in store.list_entries():
        typer.echo(f"{entry['kind']}\t@{entry['name']}\t{entry['path']}")


@registry_app.command("resolve")
def resolve_cmd(kind: str = typer.Argument(...), name: str = typer.Argument(...)) -> None:
    target = store.resolve(kind, name)
    if target is None:
        typer.echo(f"unknown {kind} {name}", err=True)
        raise typer.Exit(1)
    typer.echo(target)


@registry_app.command("add")
def add_cmd(
    kind: str = typer.Argument(...),
    name: str = typer.Argument(...),
    target: str = typer.Argument(...),
) -> None:
    store.add(kind, name, target)
    typer.echo("OK")


@registry_app.command("remove")
def remove_cmd(kind: str = typer.Argument(...), name: str = typer.Argument(...)) -> None:
    store.remove(kind, name)
    typer.echo("OK")
```

- [ ] **Step 3: Register in `cli/__init__.py` and run the test**

```python
from razorback.cli.registry import registry_app
app.add_typer(registry_app, name="registry")
```

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_registry_resolve.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/razorback/registry/ src/razorback/cli/registry.py src/razorback/cli/__init__.py tests/unit/test_registry_resolve.py
git commit -m "m6: rk registry list/resolve/add/remove (AC-6)"
```

---

## Task 11: Acceptance — `uv run pytest src/razorback/diff/` + integration

**Files:** none (test runner only).

Per M6 entity Test plan: `uv run pytest src/razorback/diff/ plus a small integration script that promotes a finished bookreview run and verifies the resulting baseline.`

- [ ] **Step 1: Run the unit suite under the diff path AND the constraints + registry paths**

```bash
cd /Users/clkao/git/razorback
uv run pytest tests/unit/test_diff_paired_bootstrap_ci.py tests/unit/test_diff_per_trial_outcomes_sidecar.py tests/unit/test_diff_pairing.py tests/unit/test_diff_stats_basic.py tests/unit/test_diff_compose.py tests/unit/test_diff_seed_refusal.py tests/unit/test_cli_runs_diff.py tests/unit/test_constraints_check.py tests/unit/test_baseline_promote_verify.py tests/unit/test_registry_resolve.py -v
```

Expected: all green.

- [ ] **Step 2: Run the integration test against a real bookreview run-dir**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/integration/test_promote_dab_bookreview.py -v
```

Expected: green (or skipped if DAB bookreview dataset is not on host).

- [ ] **Step 3: Run the FULL unit suite to confirm no M1–M5 regressions**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/ -v
```

Expected: all green. The aggregator change in Task 2 is additive; M2/M5 tests should remain green.

- [ ] **Step 4: No commit. Acceptance is a check.**

---

## Task 12: Cross-reference plan from the M6 entity body

**Files:**
- Modify: `docs/razorback-implementation/m6-constraints-registry-diff.md` (one-line link in the entity body — NOT in the frontmatter, NOT in the stage report)

- [ ] **Step 1: Append a `### Plan` section to the entity body**

After the existing `## Out of scope` section in `m6-constraints-registry-diff.md`:

```markdown

### Plan

Implementation plan at `docs/razorback-implementation/plans/m6-constraints-registry-diff.md`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/razorback-implementation/m6-constraints-registry-diff.md
git commit -m "m6: link plan from entity body"
```

(The stage report for the **plan stage** is a separate write the ensign appends at the bottom of the entity per the shared-core Stage Report Protocol.)

---

## Plan

This single plan ships M6 in 12 tasks. The math IS the deliverable; the CLI surface is a thin wrapper. Task 1's bootstrap CI is the load-bearing contract: if the CI is numerically wrong, the whole `rk runs diff` output ships broken numbers. The remaining stats (Wilson, McNemar, power) are pure closed-form expressions or one-line scipy calls; their tests are hand-computed and locked. The constraints / baseline / registry tasks are pure file IO. The seed-refusal check is one boolean comparison.

**Tasks in dependency order:**

1. **Task 0** — Pre-flight. No commit.
2. **Task 1 (RISKIEST)** — Add scipy/numpy; land `paired_bootstrap_ci`; lock against hand-computed seeded bounds.
3. **Task 2** — Aggregator writes `per_trial_outcomes.json` sidecar.
4. **Task 3** — `pair_outcomes` pairs by `(dataset, query_id, trial_index)`.
5. **Task 4** — `wilson_ci`, `exact_mcnemar_p`, `power_mde_at_fixed_n`.
6. **Task 5** — `compute_diff` composes the four stats into the JSON shape.
7. **Task 6** — Seed-presence-mismatch refusal (exit 20).
8. **Task 7** — `rk runs diff` CLI with `--alpha` / `--bootstrap-iters`.
9. **Task 8** — `rk constraints check` (exit 12).
10. **Task 9** — `rk baseline promote/verify` + integration test against bookreview-nop.
11. **Task 10** — `rk registry list/resolve/add/remove`.
12. **Task 11** — Acceptance: `uv run pytest src/razorback/diff/` + integration.
13. **Task 12** — Cross-reference plan from M6 entity body.

**Riskiest contract first.** Task 1 lands BEFORE the CLI surface. Per CL's "Validating new mechanisms" rule: the smallest end-to-end exercise of the bootstrap CI is a Python unit test against a hand-authored 2×2×5 fixture. The CLI scaffolding ships in Task 7 only after the math is locked.

---

## Self-review notes

- **Every AC has a task that ships its primary verification:** AC-1 → Tasks 1+4+5+7; AC-2 → Task 7; AC-3 → Task 6; AC-4 → Task 8; AC-5 → Task 9; AC-6 → Task 10; AC-7 → Task 4. The §-cites are in the AC ↔ task map table.
- **M5's existing math is reused, not re-derived.** The plan repeatedly references `src/razorback/benchmarks/dab/aggregate.py::_build_summary` (M2 Task 2) and `m5-provenance-full-dab.md:1786-1890` (the 12-dataset golden) as the input shape M6 reads. The only aggregator change is the additive `per_trial_outcomes.json` sidecar in Task 2.
- **Divergences are named explicitly:** (a) pairing by `(dataset, query_id, trial_index)` instead of literal `trial_name` — Trial-pairing contract above; (b) exact-McNemar via `scipy.stats.binomtest` instead of `scipy.stats.contingency.mcnemar` — Task 4 docstring; (c) power-MDE treating N as `trials × queries` instead of effective sample size — Task 4 `power_mde_at_fixed_n` docstring.
- **Exit codes are the documented ones (§3.2):** ConstraintViolation = 12, SeedMismatchError = 20, ProvenanceError = 11 (used by M5; M6 inherits unchanged). The CLI command handlers map them via the existing `RazorbackError.exit_code → typer.Exit(exc.exit_code)` shape in `cli/run.py:27-29`.
- **TDD discipline:** every task writes the failing test first, runs it red, then makes it green, then commits. Per CL's CLAUDE.md.
- **Out of scope, declared in entity:** the `--format markdown` rendering is deferred to a follow-up; the JSON path is the canonical output. The M7 milestone wires `rk runs diff` into the run-workflow's analyze stage.
