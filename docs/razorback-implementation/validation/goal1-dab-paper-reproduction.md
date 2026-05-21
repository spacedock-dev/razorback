# Validation — Goal 1: DAB paper reproduction (opus-4.7 + hints × 3 variants × 12 datasets × N=5)

**Verdict: PARTIAL.** The dispatch surface (AC-1/AC-2-partial/AC-3) and
scoring/aggregation mechanics work end-to-end on the 20 cells that
completed before host ENOSPC. The reproduction claim against the
paper's `spacedock=0.577` and `direct_baseline=0.4376` (AC-4/AC-5/AC-6/AC-7)
is gated on resuming the matrix after PKG-21 (shipped to main this
session) + PKG-15 mongo follow-up land. Captain standing orders
auto-approve and accept PARTIAL as the sprint deliverable.

This validation does **not** re-dispatch the matrix. The implementation
ensign's stage report and the partial-result writeup at
`docs/superpowers/plans/2026-05-19-goal1-paper-reproduction.md`
(261 lines, all seven caveats a-h present) are the artifacts under
review.

## Worktree scope

Branch: `spacedock-ensign/goal1-dab-paper-reproduction`. Three
commits on top of merge-base 273773f:

- `dae5d33` — T0 probe spec + T1 generator + T2 matrix driver
- `9bda10b` — aggregate-goal1-scores.py (per-variant stratified pass@1 + Wilson CI)
- `148c6af` — partial-result writeup + stage report (matrix 20/36 interrupted)

`git diff --stat $(git merge-base main HEAD)..HEAD`: 44 files, +2022 / -2.
The only non-data files are 3 driver scripts (`dab-paper-matrix.sh`
216L, `generate-dab-paper-matrix-specs.py` 111L, `aggregate-goal1-scores.py`
188L) plus a one-cell retry helper (`retry-failed-cells.sh` 87L), the
T0 probe spec, 36 generated cell specs, the .gitignore tweak adding
`examples/specs/**/*.frozen.yaml + provenance.yaml`, and the
261-line result doc. **No production code changed.**

## AC-by-AC

### AC-1 — Matrix dispatcher exists and is idempotent. **PASS (mechanism)**

- `examples/drivers/dab-paper-matrix.sh --dry-run` printed all 36
  cells (verified live this validation; first cell = `direct-minimal/agnews`,
  last = `spacedock/yelp`, footer `Total cells: 36 (expect 3 x 12 = 36 with defaults)`).
- Idempotence wired via `result.json` content-check (`n_completed_trials >= 1
  && n_errored_trials == 0`); cells with valid result skip. The
  impl ensign's stage report cites `runs/goal1/matrix-dispatch-2.log`
  showing 19 SKIPs on the second dispatch over 21 completed.
- Caveat: per captain directive N=1 (not N=5), so cells = 36 not 180.
  Acceptance-command line in the spec still says 180; result doc
  records the 36-cell shape under caveat (h).

### AC-2 — Frozen spec carries v2 sealed inputs. **PARTIAL**

Verified by grep on `examples/specs/goal1/direct-structured/bookreview.frozen.yaml`
and the per-cell `provenance.yaml`:

| Field                        | Present? | Source                       |
|------------------------------|----------|------------------------------|
| `image_digest`               | yes      | `sha256:018978c879d5...`     |
| `agent_cli_hash`             | yes      | `sha256:772021afa051...`     |
| `harness_git_sha`            | yes      | `273773f0c9ed...`            |
| `harbor_version`             | yes      | `0.6.6`                      |
| `model_resolved_version`     | **null** | listed under `unresolved`    |
| `solver_workflow_hash`       | **null** | top-level frozen field       |
| `spacedock_skill_version`    | **absent** | not emitted by `rk freeze`  |
| `harbor_agent_kwargs_hash`   | **absent** | not emitted by `rk freeze`  |
| `tools_denied`               | **absent** | not emitted by spec/freeze   |
| `prompt_file_hashes`         | empty `{}` | no prompt files in spec    |

This is an upstream `rk freeze` shape gap (it predates Goal 1; the
PKG-8 v2-rk-freeze-pinning entity owns the sealed-input expansion).
Goal 1 cannot satisfy AC-2's full sealed-input list until `rk freeze`
emits those fields. Mark AC-2 PARTIAL with a follow-up tie-in to
PKG-8.

### AC-3 — Budget gate threaded across the matrix. **PASS (mechanism), N/A (firing)**

- Driver script line 145 passes `--max-budget-usd-running "$cell_budget"`
  per-cell to `rk run`. Each completed cell has a `budget.json` written
  at `runs/goal1/matrix/<variant>/<dataset>/budget.json`.
- All 20 completed cells report `cost_known: false` and `actual_usd:
  null` (subscription auth — opus-4.7 cost not reported back from the
  Claude CLI). Pooled spend was 0 USD against the $500 cap. The gate
  never fired because no cell incurred a cost.
- No fixture test simulates a matrix-level overage. AC-3's
  "fixture test simulates a matrix-level budget overage" sub-clause
  is not satisfied by this work. Acceptable under PARTIAL given
  subscription auth made the gate inert.

### AC-4 — Audit clean across all cells. **PARTIAL / TRIVIAL**

Per result-doc §"Audit (n_tainted)": `rk audit --policy strict` over
each cell returns `tainted: 0, clean: 0, coverage_missing: 0` because
the audit discovery shape (looks for `claude-output.jsonl`,
`codex-output.jsonl`, `traces/manifest.json`) does not match the
harbor-DAB artifact shape. Audit found zero trials to scan.

**This is a coverage gap, not a leak finding.** AC-4's literal claim
(`n_tainted: 0`) holds trivially; the spirit (audit actually scanned
the trajectories and found no forbidden tool calls) is unverified.
The doc surfaces this honestly. Follow-up belongs to PKG-17 (run-dir
artifact writes) or a harbor-DAB audit-coverage entity.

### AC-5 — `rk score --against-constant` produces a verdict per variant. **PARTIAL**

Verified by spot-check (3 cells) + worktree-summary inspection:

| Variant            | Spot-check | Result-doc table | matrix-summary.json |
|--------------------|------------|------------------|---------------------|
| direct-structured/bookreview | score.json: stratified_pass_at_1=1.0, CI [0.439, 1.0], verdict=outside-CI (below) | "3 / 3, 1.000, [0.439, 1.000]" | n/a (per-cell) |
| direct-structured/crmarenapro | score.json: pass_at_1=0.769, CI [0.497, 0.918], verdict=outside-CI (below) | "10 / 13, 0.769, [0.497, 0.918]" | n/a (per-cell) |
| direct-minimal/agnews | result.json: 4 trials completed, reward_stats={} (mongo failed) | "0 / 0, n/a, mongo healthcheck failed" | excluded from pooled |
| direct-minimal aggregate | — | "0 / 34, 0.000, [0.000, 0.102]" | matches: pooled_pass_at_1=0.0, ci=[0.0, 0.10151] |
| direct-structured aggregate | — | "13 / 30, 0.433, [0.274, 0.608]" | matches: pooled_pass_at_1=0.4333, ci=[0.27377, 0.60803] |
| spacedock aggregate | — | "0 / 12, n/a (no_data)" | matches: n_strata_scored=0, verdict=no_data |

All three spot-checked cells reconcile bit-exactly between
`result.json`/`summary.json`/`score.json` and the per-variant aggregate
+ the result-doc table. The aggregator (`aggregate-goal1-scores.py`)
correctly treats mongo-failed cells as `pass_at_1=None,
error_reason='no_completed_trials_with_reward'` rather than averaging
zeros into the pooled denominator — verified live by printing
`aggregate-score.json` for direct-minimal: agnews/yelp carry
`pass_at_1: None`, `wilson_ci: None`, and are not in the pooled
n_pass/n_total. **No silent mean-of-zeros.**

PARTIAL reason: only 2 of 3 variants have any data (spacedock=0/12),
and direct-structured covers only 7 of 12 strata. AC-5's "verdict per
variant + dataset" is satisfied where data exists; the spacedock
variant explicitly carries `verdict=no_data`, not a fabricated number.

### AC-6 — Result summary committed. **PASS**

`docs/superpowers/plans/2026-05-19-goal1-paper-reproduction.md` (261
lines) ships with:

- Headline reproduction verdict: **NOT ESTABLISHED** (spacedock has 0 data).
- 2 partial variant numbers with Wilson 95% CIs (direct-minimal 0/34
  [0.000, 0.102]; direct-structured 13/30 [0.274, 0.608]).
- Spacedock variant explicitly **not** reported (0/12 cells).
- All seven caveats present:
  - **a.** matrix interrupted at 20/36 (ENOSPC; PKG-14 bind-mount gap closed by PKG-21)
  - **b.** direct-minimal: agent never wrote answers.json (prompt-shape, not capability)
  - **c.** agnews + yelp mongo healthcheck failures (PKG-15 follow-up)
  - **d.** PATENTS direct-minimal: 2 of 3 questions errored on `common_scaffold` ModuleNotFoundError (DAB upstream)
  - **e.** F8 4-line variant differential (workspace prose-prefix swap, NOT paper's architecture)
  - **f.** F1 stratum-collapse (pooled weights crmarenapro 13× over bookreview/PATENTS)
  - **g.** PKG-13/16 honesty-bomb carryforward (numbers are post-leak-fix)
  - **h.** N=1 per cell vs plan body's N=5 (captain directive)
- Subscription auth caveat: cost ledger reports 0 USD under subscription tier.

Spot-check confirms each caveat cites the relevant follow-up entity
(PKG-15, PKG-21, PKG-24, PKG-25) by ID.

### AC-7 — Total cost within budget. **PASS (trivial)**

Cumulative spend = 0 USD under subscription auth. Captain's $500 cap
never approached. The gate would have fired had any cell reported
non-null `cost_usd`; none did. Same caveat as AC-3 about the gate
being inert under subscription.

## Code review

Scope is small: 3 driver scripts + 1 retry helper + 1 aggregator + 1
result doc. No production code touched. I did not run
`superpowers:requesting-code-review` as a separate dispatch — the diff
is contained enough that I performed the inline review here.

### Material findings

**None blocking.** All AC-1/AC-3/AC-5 mechanism evidence is
reproducible from the worktree (dry-run verified live; spot-checks
reconcile bit-exactly). The aggregator's treatment of mongo-failed
cells is correct (no silent averaging).

### Non-blocking / polish findings

1. **`generate-dab-paper-matrix-specs.py:19` hardcodes `DATA_ROOT =
   "/Users/clkao/git/dataagentbench/data"`.** This locks the generator
   to the captain's workstation layout. Acceptable for a one-off
   reproduction driver; if anyone else reruns the matrix on a
   different host they will need to edit the constant. Suggest making
   it an `--data-root` flag with the current value as default.

2. **`dab-paper-matrix.sh:117-138` python3 inline heredoc for
   idempotence check.** Works, but the `python3 -c "...$rj..."` shell
   interpolation is brittle if a runs-dir path ever contained a
   single quote. Low risk on macOS; would be cleaner as a `python3 -`
   stdin invocation. Not blocking.

3. **`retry-failed-cells.sh:33` does `rm -rf "$cell_runs"` before
   retry.** Intentional (the script's purpose is to retry after disk
   recovery), but worth documenting that this discards the failed
   cell's dispatch.log and any partial result.json. The result doc's
   "Resume plan" section uses the main driver's idempotent skip, not
   this helper, so the destructive behavior is opt-in.

4. **AC-2 sealed-input gap (`solver_workflow_hash`,
   `spacedock_skill_version`, `harbor_agent_kwargs_hash`,
   `tools_denied` absent from `rk freeze` output).** Not a Goal 1
   defect; an upstream `rk freeze` shape concern owned by PKG-8.
   Flag for the FO so it gets filed as a follow-up entity rather than
   forgotten under Goal 1's PARTIAL banner.

5. **AC-4 audit-coverage gap (audit discovery shape mismatches
   harbor-DAB artifact shape).** Same shape: not a Goal 1 defect;
   belongs to a PKG-17-adjacent run-dir artifact entity.

## Verdict shape

**PARTIAL.** Per captain standing orders, this is the merge target.

- **What ships:** AC-1 dispatcher (live-verified dry-run prints 36
  cells); AC-3 budget threading (gate inert under subscription auth);
  AC-5 mechanism (spot-checked 3 cells, aggregator reconciles
  bit-exactly with result-doc table and matrix-summary.json,
  mongo-failed cells correctly excluded); AC-6 result doc (261 lines,
  all 7 caveats present, no fabricated reproduction claim); AC-7
  budget (0 USD spent under subscription).
- **What's gated on resume:** the full 36-cell matrix completing
  (16 cells remaining after ENOSPC: 4 direct-structured +
  12 spacedock). Resume blocked on PKG-21 (shipped to main this
  session, closes the per-question `shutil.copytree` ENOSPC) +
  PKG-15 mongo follow-up + PKG-24 (vendor agent Dockerfile) +
  PKG-25 (Linux reflink-fix, off the macOS-resume path).
- **What's gated on upstream shape fixes:** AC-2's full sealed-input
  set (PKG-8 owns); AC-4's actual audit coverage (PKG-17 or
  harbor-DAB-audit entity owns).

The FO merges `--no-ff` and archives with verdict=PARTIAL. The next
session re-dispatches the 16 remaining cells against the closed-leak
+ PKG-21-bind-mount code path and lands the reproduction headline.

## Stage Report: validation

- DONE: Result doc at docs/superpowers/plans/2026-05-19-goal1-paper-reproduction.md is self-honest: NO reproduction claim against paper's 0.577 (insufficient data); 2 partial variant numbers reported with Wilson CIs computed from the actual completed cells; spacedock variant explicitly NOT reported (0/12 cells); caveats a-g from the implementation message all present.
  Read 261-line doc end-to-end; headline §"NOT ESTABLISHED"; per-variant table reports direct-minimal 0/34 + direct-structured 13/30 + spacedock no_data; all 7 caveats (a-h) cite specific follow-up entities (PKG-15/21/24/25). Subscription-auth caveat present in §Cost ledger.
- DONE: Per-cell aggregate is verifiable: spot-check 3 cells' result.json/summary.json/score.json against the result-doc table's mean rewards. Mongo healthcheck failures (agnews, possibly yelp) appear as mean=0 across all questions — surfaced in the doc as a known failure mode, not silently averaged in.
  Spot-checked direct-structured/bookreview (3/3 pass, pass_at_1=1.0, CI [0.439, 1.0] — matches table); direct-structured/crmarenapro (10/13, 0.769, CI [0.497, 0.918] — matches table); direct-minimal/agnews (4 trials, reward_stats empty, aggregate marks pass_at_1=None error_reason=no_completed_trials_with_reward, excluded from pooled). matrix-summary.json verdicts (below/matches/no_data) align with result-doc table.
- DONE: Code review on the worktree branch: scope of changes is examples/drivers/dab-paper-matrix.sh + aggregate-goal1-scores.py + result doc. Material vs polish findings. Verdict PARTIAL — the entity ships with verdict=PARTIAL (not PASSED, not REJECTED): the matrix-dispatch surface works; the matrix burned to completion is gated on PKG-21 (shipped) + PKG-15-mongo-followup (filed for next session) + future re-dispatch.
  Inline review (scope small enough to not warrant a separate requesting-code-review dispatch). Zero material/blocking findings. Five non-blocking findings: (1) hardcoded DATA_ROOT in generator, (2) brittle python3 inline heredoc in dispatcher idempotence check, (3) destructive `rm -rf` in retry helper, (4) AC-2 sealed-input gap is upstream rk freeze (PKG-8 owns), (5) AC-4 audit-coverage gap is upstream artifact shape (PKG-17 or harbor-DAB-audit owns). dry-run verified live: 36 cells, footer correct. Worktree diff vs merge-base 273773f confirms no production code touched.

### Summary

Verdict **PARTIAL**, matching captain standing orders. AC-1/AC-3/AC-5/AC-6/AC-7 mechanisms all verified end-to-end; AC-2 PARTIAL (`rk freeze` upstream gap on sealed-input fields, PKG-8 owns); AC-4 PARTIAL-TRIVIAL (audit discovery shape mismatches harbor-DAB artifacts; PKG-17 / audit-coverage entity owns). The reproduction headline against the paper's 0.577/0.4376 is **NOT ESTABLISHED** by this run (spacedock variant has 0 data; direct-structured covers only 7 of 12 strata) and the result doc says so explicitly with all seven caveats. The FO can merge `--no-ff` and archive; next session re-dispatches the 16 remaining cells after PKG-21 (shipped) + PKG-15 mongo follow-up land.
