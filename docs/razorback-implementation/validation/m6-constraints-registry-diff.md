# M6 — Constraints, registry, baselines, runs diff — Validation Report

**Branch validated:** `spacedock-ensign/m6-constraints-registry-diff` @ `7247429`
**Validator:** fresh ensign (did NOT write implementation)
**Gate decision:** PASSED

## Acceptance run

```
$ uv run pytest tests/unit/ -q
196 passed in 10.71s
```

196 / 196 unit tests green from a clean checkout. The 54 new M6 tests
land alongside the 142 carried-forward M1+M2+M3+M4+M5 tests.

The narrower M6-targeted run (10 test files):

```
$ uv run pytest tests/unit/test_diff_*.py \
    tests/unit/test_constraints_check.py \
    tests/unit/test_baseline_promote_verify.py \
    tests/unit/test_registry_resolve.py \
    tests/unit/test_cli_runs_diff.py -v
54 passed in 9.04s
```

M2/M5 carry-forward (the additive aggregator-sidecar surface):

```
$ uv run pytest tests/unit/test_dab_aggregate.py \
    tests/unit/test_dab_aggregate_twelve_datasets.py \
    tests/unit/test_dab_aggregate_grep.py -q
7 passed in 0.02s
```

## Per-AC verification

### AC-1 — `rk runs diff` emits Wilson CI + exact-McNemar + paired bootstrap + power MDE — PASS

**Verified by clause:** "a unit test feeds two fixture run-dirs (one
baseline, one hypothesis) with hand-computed expected values and
asserts each statistic in the JSON output matches the expected value
(within numerical tolerance for the bootstrap)."

**Reproduction:**

- Math cross-check (independent reimpl matches scipy to machine
  precision):
  - Wilson CI(k=7,n=10,α=0.05) = (0.39677814746114537,
    0.8922087325936989) — hand-derived from Wilson 1927 formula;
    matches `wilson_ci` bit-for-bit.
  - Wilson CI(k=4,n=10,α=0.05) = (0.168, 0.687) — matches published
    Agresti-Coull/Wilson tables.
  - `exact_mcnemar_p(b=3,c=8)` = 0.2265625 — matches
    `scipy.stats.binomtest(k=3,n=11,p=0.5,two-sided).pvalue` exactly.
  - Bootstrap CI on the 2×2×5 fixture at seed=42, B=1000, α=0.05:
    `(0.07137896825396822, 0.4854340277777777)` — reproduced exactly
    by an independent reimplementation written from scratch by the
    validator (same numpy seed semantics, same sorted-keys algorithm,
    same percentile method). Match within `1e-12`.
  - Power MDE at (α=0.05, p₀=0.5, n=100) = 0.14007926090564843 —
    matches `(z_{α/2}+z_β)·√(p₀(1−p₀)/n)` exactly.
- End-to-end against real M5 data shape: `uv run rk runs diff` on
  baseline (M5 6-dataset snapshot, 24 trials, stratified pass@1 =
  0.6746) vs synthesized hypothesis run (stratified pass@1 = 0.8234,
  delta = 0.1488, bootstrap CI [0.040, 0.283] excludes 0).
  JSON shape includes `per_arm_stratified_pass_at_1`,
  `stratified_delta`, `stratified_delta_ci`,
  `per_arm_wilson_ci_by_query` (24 rows),
  `exact_mcnemar_p_by_query` (24 rows), `power_mde`. Exit 0.

The "hand-computed" bootstrap bounds in
`test_paired_bootstrap_ci_hand_computed_bounds` are a numerical
regression pin against the seeded `numpy.random.default_rng(42)`
sequence rather than a closed-form derivation. The entity body's
Implementation summary names this honestly. Validator confirms the
pinned values are correct by independent reimplementation. The
qualitative properties (true delta inside CI, alpha widens, identical
arms straddle 0, pairing preserved, determinism) ARE hand-derivable
and all pass.

### AC-2 — `--alpha` sets confidence level; `--bootstrap-iters` sets B — PASS

**Verified by clause:** "unit tests assert both flags flow through to
the statistics module."

**Reproduction:** `uv run rk runs diff <a> <b> --alpha 0.10
--bootstrap-iters 500` produces JSON with `"alpha": 0.1,
"bootstrap_iters": 500` in the top-level payload and the
`power_mde.alpha = 0.1`. The pytest
`test_rk_runs_diff_alpha_flows_through` and the `test_diff_compose.py`
suite gate this independently.

### AC-3 — refuses when only one run has `agent.seed.default` set, exit 20 — PASS

**Verified by clause:** "a unit test feeds a baseline with no seed and
a hypothesis with `seed.default: 42`; the command exits non-zero with
the §6.5 refusal text."

**Reproduction:** validator authored a baseline (no seed) and
hypothesis (with `agent.seed.default: 42`) and ran:

```
$ uv run rk runs diff /tmp/m6-validation/run-baseline \
    /tmp/m6-validation/run-seeded --bootstrap-iters 200
SeedMismatchError: paired diff requires both runs share the same seed
run-dir; A has agent.seed.default=False, B has agent.seed.default=True.
EXITCODE=20
```

Exit 20 matches `ExitCode.SEED_MISMATCH`. Tests
`test_diff_seed_refusal.py` (4) + `test_cli_runs_diff.py::
test_rk_runs_diff_exits_20_on_seed_mismatch` gate this.

### AC-4 — `rk constraints check` enforces pinned + mutation surfaces, exit 12 — PASS

**Verified by clause:** "a unit test feeds a constraints file with a
pinned `model_resolved_version` and a spec whose value differs; the
command exits with `ConstraintViolation` (exit code 12)."

**Reproduction:**

- Pinned mismatch:
  ```
  $ uv run rk constraints check /tmp/m6-validation/run-baseline/spec.frozen.yaml \
      --constraints /tmp/m6-validation/constraints-bad.yaml
  ConstraintViolation: pinned field agent.model: expected 'claude-opus-4-7',
  got 'claude-opus-4-5'
  EXIT=12
  ```
- Mutation-surface coverage (with `--baseline`):
  ```
  $ uv run rk constraints check /tmp/m6-validation/spec-changed.yaml \
      --constraints /tmp/m6-validation/constraints-mut-only-agent.yaml \
      --baseline /tmp/m6-validation/baseline-spec.yaml
  ConstraintViolation: diverged field benchmark.datasets is not under any
  declared mutation_surfaces ['agent']
  EXIT=12
  ```
- Pass case exits 0 ("OK"). `ExitCode.CONSTRAINT_VIOLATION = 12`
  matches §3.2.

### AC-5 — `rk baseline promote` copies 4 artifacts + verifies constraints — PASS

**Verified by clause:** "an integration test promotes a finished
run-dir and asserts the target baseline directory contains all four
artifacts, and that a subsequent `rk baseline verify` against the same
constraints exits 0."

**Reproduction:**

```
$ uv run rk baseline promote /tmp/m6-validation/run-baseline \
    --to /tmp/m6-validation/baseline-promoted \
    --constraints /tmp/m6-validation/constraints-good.yaml
/tmp/m6-validation/baseline-promoted
PROMOTE EXIT=0
$ ls /tmp/m6-validation/baseline-promoted/
constraints.yaml  provenance.yaml  spec.frozen.yaml  summary.json
$ uv run rk baseline verify /tmp/m6-validation/baseline-promoted
OK
VERIFY EXIT=0
```

The 4 artifacts that land in the target are `spec.frozen.yaml`,
`summary.json` (carrying per-dataset scores per the M2/M5 shape),
`provenance.yaml`, and `constraints.yaml`. This is the design's
"frozen spec, summary (carrying per-dataset scores), provenance" plus
the constraints file the baseline is bound to.

`test_promote_uses_m5_summary_snapshot` exercises this against the
real M5 first-DAB-result snapshot at
`docs/razorback-implementation/m5-first-dab-result-summary.json`.

### AC-6 — `rk registry resolve` resolves `@name` to registered path — PASS

**Verified by clause:** "a unit test registers `@codex-direct-baseline
→ /some/path` via `rk registry add` then asserts `rk registry resolve
baseline @codex-direct-baseline` prints that path."

**Reproduction:**

```
$ uv run rk registry add baseline @codex-direct-baseline \
    /tmp/m6-validation/baseline-promoted        # EXIT=0  "OK"
$ uv run rk registry resolve baseline @codex-direct-baseline
/tmp/m6-validation/baseline-promoted             # EXIT=0
$ uv run rk registry list
baseline	@codex-direct-baseline	/tmp/m6-validation/baseline-promoted
$ uv run rk registry remove baseline @codex-direct-baseline   # EXIT=0
$ uv run rk registry resolve baseline @codex-direct-baseline
unknown baseline @codex-direct-baseline           # EXIT=1
```

Add → resolve → list → remove → resolve-after-remove all behave
correctly. `@`-prefix and bare-name forms both supported.

### AC-7 — Power-at-fixed-N MDE — PASS

**Verified by clause:** "a unit test feeds a known fixture and asserts
the MDE matches the hand-computed value for the given trials ×
queries."

**Reproduction:** validator hand-derived MDE for three independent
triples:

| α    | p₀     | n   | hand-derived MDE       | got                    |
|------|--------|-----|------------------------|------------------------|
| 0.05 | 0.5    | 100 | 0.140079260906         | 0.140079260906         |
| 0.05 | 0.3    | 50  | 0.181563473431         | 0.181563473431         |
| 0.10 | 0.6746 | 24  | 0.237799202898         | 0.237799202898         |

All match to `1e-12`. The closed-form normal-approximation
`(z_{α/2}+z_β)·√(p₀(1−p₀)/n)` is the conservative upper bound the
implementation documents (named in the docstring and entity-body
deviations).

## Code review

Validator performed a focused review pass on every M6 source surface:

**Strengths**

- Math implementations cite design §6.5 verbatim and the canonical
  primary sources (Wilson 1927, McNemar 1947, Cohen 1988).
- Three design-aligned deviations are openly documented in the entity
  body AND in function docstrings: pairing surrogate
  `(dataset,query_id,trial_index)`, McNemar via stable `binomtest`,
  power MDE as conservative upper bound.
- Zero mocks in M6 tests (verified via `grep mock|patch|MagicMock`
  across all 10 new test files). Subprocess-based CLI tests use the
  real `uv run rk` invocation.
- `summary.json` v1 contract preserved. Aggregator extension is
  strictly additive (new sidecar file).
- Typed-error → exit-code mapping is consistent across all 4 new CLI
  surfaces: `ConstraintViolation`→12, `SeedMismatchError`→20 reused
  from M3.

**Minor (non-blocking) findings**

- `constraints/baseline.py::promote` copies the 4 artifacts to the
  target dir BEFORE running `check_spec_against_constraints`; if the
  spec violates constraints, the partially-populated target dir
  remains. Caller sees the exception (and exit 12), so this does not
  affect correctness — just cleanliness. Non-blocking.
- `cli/registry.py::resolve_cmd` exits 1 (generic) on unknown name
  rather than a more specific code. The §3.2 exit-code map doesn't
  reserve a code for "registry miss", so 1 is a reasonable fallback.
  Non-blocking.
- The aggregator's `trial_index` is assigned by per-key arrival order
  inside `aggregate_job_result`. For paired diff to be meaningful
  across runs, harbor must return trials in deterministic order
  (which it does for seeded runs; for unseeded runs, pairing is
  positional). The deviation is named in the entity body.
  Non-blocking — design-aligned.

**Blocking findings**

None.

## Gate decision

**PASSED.** All 7 ACs verified independently against their
`Verified by:` clauses; the math is cross-checked against scipy and
against an independent reimplementation by the validator; the
acceptance command is reproduced from a clean checkout; M1–M5
carry-forward tests stay green at 196/196; no blocking review
findings.

Recommend advancing the entity from `validation` to `done`.
