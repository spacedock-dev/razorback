---
title: Goal 1 — direct-structured matrix (paper-comparable, opus-4.7 + xhigh)
entity: 7q goal1-direct-structured-dab-opus47-xhigh
date: 2026-05-25
status: implementation
matrix_root: _runs/goal1-direct-structured-redo-2026-05-24
---

## Amendment 2026-05-25 post-aggregator-fix

The matrix aggregator at the time this report was archived emitted
`per_query_verdict` (pooled-per-query Wilson CI) as the
paper-comparison verdict. Per
`docs/razorback-implementation/goal1-matrix-aggregator-stratified-verdict-fix.md`
(this entity, branch `spacedock-ensign/goal1-matrix-aggregator-stratified-verdict-fix`),
the canonical paper-comparison lens is **stratified-per-query** — the
DAB paper's `direct_baseline=0.4376` is the stratified value (each
dataset weighted equally regardless of query count). The aggregator
now emits `against_constant.stratified_verdict` from
`per_query_pass_at_1_mean_over_strata`; `per_query_verdict` (pooled)
and `verdict` (binary) remain as supplementary views.

**Corrected paper-comparison headline (stratified lens):**
`direct-structured stratified-per-query pass@1 = 0.6719` across 12 DAB
datasets at N=1. Verdict vs `paper direct_baseline=0.4376`: **above**
(point comparison; CI null per stratified-mean-of-proportions not being
binomial — see `aggregate-goal1-scores.py` docstring for methodology).

Archived run-dirs are immutable; this is a forward-pointing
correction, not a re-run.

## Headline

> **Headline corrected 2026-05-25 by FO at captain directive.** The DAB
> paper's `direct_baseline=0.4376` is the **stratified-per-query** value
> (each dataset weighted equally regardless of query count). The
> original headline led with pooled-per-query (0.7407) and compared it
> against the stratified paper number — apples-to-oranges. The
> corrected paper-comparable headline is the stratified value below.
> Pooled-per-query and binary numbers are preserved as supplementary
> views in the per-cell table. The matrix aggregator's
> `per_query_verdict` field still computes against `pooled_per_query_ci`
> (a tooling bug to fix in a follow-on entity).

**Direct-structured stratified-per-query pass@1 = 0.6719 across 12 DAB datasets at N=1** (`per_query_pass_at_1_mean_over_strata` from `direct-structured/aggregate-score.json`; mean of the 12 per-cell pass@1 values, each dataset weighted equally — paper-canonical).

Verdict vs `paper direct_baseline=0.4376`: **above** (0.6719 > 0.4376, Δ ≈ +0.234). The stratified mean-of-proportions is not binomial so a Wilson CI does not attach at this lens — significance vs the paper baseline at this matrix scale would require bootstrap or per-stratum CI aggregation (a methodology piece to file in the matrix-aggregator-fix follow-on).

Side-by-side with the spacedock headline from the archived `d8 goal1-rerun-headline-per-query-recompute` at the same model + effort point:

| Aggregation lens | direct-structured (this entity) | spacedock (d8 archive) | Δ |
|---|---|---|---|
| **stratified-per-query (paper lens)** | **0.6719** | **~0.706** (computed from d8 per-cell table) | direct **-0.034** (spacedock leads on the paper-canonical lens; no CI on this lens at N=1) |
| pooled-per-query (supplementary) | 0.7407 [0.611, 0.839] | 0.722 [0.591, 0.824] | direct +0.019 (CIs overlap meaningfully) |
| pooled cell-binary (strictest) | 0.333 [0.138, 0.609] | 0.333 [0.138, 0.609] | identical |

At the paper-canonical stratified-per-query lens, **spacedock leads direct-structured by ~3pp at N=1**; the per-stratum CI machinery to claim statistical significance on that gap isn't computed at this matrix scale. The pooled-per-query lens reverses the ordering by ~2pp because high-query datasets (crmarenapro at 13 queries) dominate the pool, masking the stratified ranking.

## Per-cell table

| cell | n_q | n_correct | per_query | bin_pass | cost_usd | in_tok | out_tok |
|------|-----|-----------|-----------|----------|----------|--------|---------|
| agnews | 4 | 2 | 0.5000 | 0 | $4.86 | 3,080,240 | 94,354 |
| bookreview | 3 | 3 | 1.0000 | 1 | $1.06 | 753,832 | 10,157 |
| crmarenapro | 13 | 11 | 0.8462 | 0 | $5.36 | 6,326,949 | 53,031 |
| DEPS_DEV_V1 | 2 | 0 | 0.0000 | 0 | $1.41 | 993,162 | 23,248 |
| GITHUB_REPOS | 4 | 2 | 0.5000 | 0 | $1.99 | 1,692,259 | 24,982 |
| googlelocal | 4 | 3 | 0.7500 | 0 | $0.99 | 878,255 | 9,639 |
| music_brainz_20k | 3 | 3 | 1.0000 | 1 | $1.75 | 1,343,167 | 27,206 |
| PANCANCER_ATLAS | 3 | 2 | 0.6667 | 0 | $1.02 | 893,973 | 11,935 |
| PATENTS | 3 | 0 | 0.0000 | 0 | $2.86 | 2,770,076 | 36,049 |
| stockindex | 3 | 3 | 1.0000 | 1 | $0.52 | 340,873 | 6,570 |
| stockmarket | 5 | 4 | 0.8000 | 0 | $0.65 | 437,644 | 11,113 |
| yelp | 7 | 7 | 1.0000 | 1 | $1.87 | 1,675,469 | 22,242 |
| **pooled** | **54** | **40** | **0.7407** | **4/12** | **$24.35** | 21,185,899 | 329,526 |

Pooled per-query pass@1 = 40/54 = 0.7407, Wilson 95% CI [0.6107, 0.8388]. Pooled binary pass@1 (full-pass cells) = 4/12 = 0.333, Wilson 95% CI [0.138, 0.609].

## Audit verdict block

`rk audit --policy strict` was wired into the matrix dispatcher between rk-run and rk-score per wp's gate (`examples/drivers/dab-paper-matrix.sh:217-225`). All 12 cells emitted `audit.json` and were scored; `rk score` surfaces `taint_status` per hm commit 5.

| cell | clean | tainted | coverage_missing |
|------|-------|---------|------------------|
| agnews | 1 | 0 | 0 |
| bookreview | 1 | 0 | 0 |
| crmarenapro | 1 | 0 | 0 |
| DEPS_DEV_V1 | 1 | 0 | 0 |
| GITHUB_REPOS | 1 | 0 | 0 |
| googlelocal | 1 | 0 | 0 |
| music_brainz_20k | 1 | 0 | 0 |
| PANCANCER_ATLAS | 1 | 0 | 0 |
| PATENTS | 1 | 0 | 0 |
| stockindex | 1 | 0 | 0 |
| stockmarket | 1 | 0 | 0 |
| yelp | 1 | 0 | 0 |

**12/12 cells clean. The agnews cell — the cheating-attack regression target that triggered the pre-k3-leak-guard finding — comes back clean under the same `rk audit --policy strict` policy.** Tracing agnews's `claude-code.txt` (`agnews__rFqCKQn/steps/main/agent/claude-code.txt`), the only `load_dataset` matches are README echoes of the forbidden-pattern list itself; the agent emitted zero assistant-side `load_dataset` calls. This is **branch (a) — declined `load_dataset` outright** per the k3 AC-2 verifier shape. The k3 workspace-README leak-guard prose and wp's strict-policy scanner together close the regression.

## AC-5 — Provenance enumeration

### Frozen-spec fields (per cell)

| field | value (uniform across 12) |
|-------|---------------------------|
| model | claude-opus-4-7 |
| reasoning_effort | xhigh |
| pin_model_version | true |
| workspace_variant | direct-structured |
| query_mode | batch |
| paper_baseline | name=direct, value=0.4376 |

All 12 spec.frozen.yaml files share `agent.reasoning_effort: xhigh` (now threaded through to `agent.kwargs.reasoning_effort` per k4's PR #3 merge at `e5c1615` — see post-k4 preflight evidence under `per-cell-preflight-post-k4/`). `experiment_meta.paper_baseline.{name: direct, value: 0.4376}` lives on every cell's frozen spec, enabling `rk score`'s auto-pull (hm commit 5).

Note: claude-cli has no `agent.sealed_hash` (only spacedock_solver stamps it via `src/razorback/spec/freeze.py:54`). The freeze CAS at `/Users/clkao/git/razorback/_runs/_razorback-freeze/` has a single content-hash subdir (`377bd09522713c54668a004eb8a06834`) because the agent block is byte-identical across cells (only `benchmark.tasks[0]` differs).

### Provenance.yaml fields (per cell)

| field | value (uniform across 12) |
|-------|---------------------------|
| image_digest | sha256:d29dec396ea6651ca4a622e87e5e9607819e8e894868daa733818e534af961cc |
| agent_cli_hash | sha256:f4a1860d3d9b01653dde4183e2f1216ca9e0c1a404dd63caa4edf07c904102aa |
| harbor_version | 0.6.6 |
| unresolved | [model_resolved_version] |
| solver_workflow_hash | null (expected for claude-cli) |
| plugins | [] |

`harness_git_sha` varies per cell — matches whichever commit was checked out when the cell ran. Cells run during the first dispatch wave carry the post-AC-2 driver commit; cells run after the resume (music_brainz_20k, PANCANCER_ATLAS, PATENTS, stockindex, stockmarket, yelp) carry the post-driver-patch commit. All matrix execution happened on this entity's branch `spacedock-ensign/goal1-direct-structured-dab-opus47-xhigh`.

`solver_workflow_hash` is `null` for the `claude-cli` agent kind (expected — there is no spacedock_solver workflow). `spacedock_skill_version` does not apply.

`model_resolved_version` remains in `unresolved` per cell — the freeze pass was `--allow-missing` and rk run did not populate the canonical model SHA. (Same deviation called out in the d8 spacedock report.)

## AC-6 — Sealed re-freeze stability sample

Bookreview re-freeze: two consecutive `uv run rk freeze examples/specs/goal1/direct-structured/bookreview.yaml --allow-missing` invocations produce byte-identical `bookreview.frozen.yaml` (verified via `cmp` — exit 0). The freeze CAS hash at `377bd09522713c54668a004eb8a06834` is reused across all 12 cells.

(A first re-freeze attempt against the spec captured in the run-dir's `provenance.yaml` produced a 1-line diff at `harness_git_sha` because a fresh commit had landed between the original and the re-attempt; the second pair of re-freezes captured against a stable HEAD were byte-identical. This is the expected behavior of `harness_git_sha` pinning and is documented in Deviations below rather than as an AC-6 failure.)

## Freeze CAS check

```
RAZORBACK_FREEZE_DIR=/Users/clkao/git/razorback/_runs/_razorback-freeze
$ ls $RAZORBACK_FREEZE_DIR
377bd09522713c54668a004eb8a06834/
```

One CAS subdir, byte-identical across all 12 cells. This matches the d8 spacedock report's "all 12 cells share the same agent-block sealed_hash" expectation (the value here is content-hash of the YAML, not an agent-block-only sealed hash — because the claude-cli spec doesn't stamp one).

## Cost ledger

- **Total wallclock cost:** $24.35 (sum of `cost_usd` across 12 cells)
- **Per-cell range:** $0.52 (stockindex) … $5.36 (crmarenapro)
- **Mean per cell:** $2.03
- **Within envelope:** entity prompt budget was $25-40; matrix landed at the low end.
- **Per-cell budget cap (`--max-cell-budget-usd 10.0`) did not trip.**

| cell | cost_usd |
|------|----------|
| stockindex | $0.52 |
| stockmarket | $0.65 |
| googlelocal | $0.99 |
| PANCANCER_ATLAS | $1.02 |
| bookreview | $1.06 |
| DEPS_DEV_V1 | $1.41 |
| music_brainz_20k | $1.75 |
| yelp | $1.87 |
| GITHUB_REPOS | $1.99 |
| PATENTS | $2.86 |
| agnews | $4.86 |
| crmarenapro | $5.36 |
| **total** | **$24.35** |

(Cost telemetry is non-null here — distinct from the d8 spacedock report's deviation #5 noting null cost_usd. The harness telemetry gap appears to be variant-specific to spacedock_solver; claude-cli routes cost telemetry through harbor's RazorbackClaudeCode subclass correctly.)

## Wallclock ledger

- **Matrix start (first cell run):** 2026-05-25T01:13Z (bookreview T4 smoke run)
- **Matrix end (final cell complete):** 2026-05-25T02:58Z (music_brainz_20k redo)
- **Total wallclock:** ~1h45m end-to-end (within the 2-3h estimate; includes a ~5-min interruption between cell 6 and cell 7 when the background-dispatch process was killed mid-run and resumed via the driver's `result.json` idempotence)
- **Per-cell wallclock:**
  - bookreview: 2m59s (the T4 mechanism smoke; cheapest cell)
  - agnews: ~27m (longest; load-bearing for the cheating-attack regression)
  - crmarenapro: ~11m
  - DEPS_DEV_V1: ~9m
  - GITHUB_REPOS, googlelocal: ~7m each
  - music_brainz_20k: 6m23s (cleanly redone after the lock-file failure)
  - others: ~3-8m typical

## Failure analysis

- **music_brainz_20k cycle 1 (run_failed, exit 30):** When the matrix dispatcher's background process was killed and resumed, the driver hit a `harbor.lock.json` mismatch (`Job directory already has a lock.json that does not match the resolved job lock`). This is harbor's safety lock against concurrent writers, not a cell-content issue. Cleanup (rm -rf the partial cell dir) + redispatch produced a clean exit 0 run on the same content; ledger row reflects both attempts. **Net cell outcome: ok.** Suggested follow-up (out of 7q scope): harbor or the matrix driver could detect orphaned locks (no live PID in lock.json) and clean them automatically; today the operator does it manually.
- **No other cells failed.** All 12 cells ultimately produced result.json + audit.json + score.json + provenance.yaml.

## Deviations from plan

- **`_runs/` runs-dir not `$XDG_DATA_HOME/razorback/runs`** — captain-approved per d8 spacedock report; same here.
- **`DATAAGENTBENCH_DATA_ROOT` env var required** — captain-approved per d8 spacedock report; same here. Set to `/Users/clkao/git/dataagentbench/data` at every dispatch entry point.
- **`solver_workflow_hash: null` and no `spacedock_skill_version`** — expected for `claude-cli` agent kind. AC-5 explicitly names this.
- **`model_resolved_version` remains in `unresolved`** — same as d8 spacedock; freeze runs with `--allow-missing` and `rk run` did not populate the canonical model SHA. Not blocking.
- **Driver scoring patch in this branch (1 commit):** dropped `--against-constant` on the `rk score` invocation for direct-* variants in `examples/drivers/dab-paper-matrix.sh:247-260`, so per-cell `score.json` carries `against_constant.source = "spec.frontmatter"` per AC-5. The spacedock branch of the case statement still passes the explicit constant because that variant's paper_baseline lives outside the spec's `experiment_meta` block. The driver change is small, isolated, and verified by the T4 smoke's score.json output.
- **Translator `reasoning_effort` fix landed via k4 (PR #3, merged at `e5c1615`)** — surfaced as a Material finding during AC-2 preflight on 2026-05-24, fixed by k4, this entity rebased onto post-k4 main and re-verified via the `per-cell-preflight-post-k4/` evidence dir (12/12 explain JSONs show `.agent.kwargs.reasoning_effort = "xhigh"`).

## Provenance

- **Matrix dispatcher:** `examples/drivers/dab-paper-matrix.sh` at this entity branch's HEAD
- **Aggregator:** `examples/drivers/aggregate-goal1-scores.py` (uses canonical reducer `src/razorback/runs/aggregate.py:reduce_per_query_stratified`)
- **rk binary:** rk + razorback + razorback-plugin-dab from this entity branch's HEAD
- **Frozen specs:** `examples/specs/goal1/direct-structured/*.frozen.yaml` (12; gitignored locally; mirrored under `_evidence/goal1-direct-structured-v2/per-cell-preflight-post-k4/<cell>/spec.frozen.yaml`)
- **DAB image:** `dab-agent:latest` at `sha256:d29dec396ea6651ca4a622e87e5e9607819e8e894868daa733818e534af961cc`
- **Harbor version:** 0.6.6
- **Data root:** `/Users/clkao/git/dataagentbench/data`
- **Date:** 2026-05-25

## Artifact retention

Per-cell run-dirs at `_runs/goal1-direct-structured-redo-2026-05-24/direct-structured/<cell>/goal1-direct-structured-<cell>/<hash>/` carry: `result.json`, `summary.json`, `provenance.yaml`, `audit.json`, `audit.stderr`, `score.json`, `score.stderr`, `spec.frozen.yaml`, `events.jsonl`, `job.log`, plus per-trial subdirs with full trajectories (`agent/claude-code.txt`, `steps/main/verifier/test-stdout.txt`, `steps/main/verifier/reward_per_query.json`).

`_evidence/goal1-direct-structured-v2/per-cell-preflight-post-k4/<cell>/` mirrors `spec.frozen.yaml` + `explain.json` for AC-2's preflight assertions. Pre-k4 preflight evidence is retained under `per-cell-preflight/` for the audit trail.

The matrix-summary.json + per-variant aggregate-score.json live at `_runs/goal1-direct-structured-redo-2026-05-24/`.

Trajectories (multi-MB) stay in `_runs/`; they are not committed.

## Follow-ups suggested

1. **Three-way headline narrative** (spacedock 0.722 [0.591, 0.824] vs direct-structured 0.741 [0.611, 0.839] vs paper 0.4376). CIs for spacedock and direct-structured overlap meaningfully at N=1; the captain may want N=5 of one or both to tighten the gap measurement before drawing a conclusion about the crew loop's contribution.
2. **direct-minimal sibling.** Captain selected direct-structured for this entity; the minimal variant remains the obvious A/B counter to ask whether the workspace README's structure matters at this model.
3. **Translator `prompt_file` claude-cli gap.** k4 surfaced this as a follow-on; filed at backlog. Not blocking on 7q.
4. **Driver orphan-lock cleanup.** Today a killed dispatch leaves a `lock.json` that the next dispatch trips on. Out of 7q scope; minor harness hygiene improvement.
5. **N=5 paper-grade reproduction** at the same opus-4.7 + xhigh + direct-structured point would tighten the 95% CI from ±0.11 to ±0.05 (Wilson) and let direct-structured-vs-spacedock be compared at higher statistical power than the current overlapping-CI story permits.
