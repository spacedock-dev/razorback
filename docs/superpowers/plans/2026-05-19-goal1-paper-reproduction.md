# Goal 1: DAB paper reproduction — partial result (opus-4.7 + hints × 3 variants × 12 datasets × N=1)

**Status:** PARTIAL. Matrix dispatched but interrupted by host disk-full
(ENOSPC) at cell 20/36. The captain accepted partial-result writeup
this session; matrix-resume is gated on PKG-21 (SQLite/DuckDB
bind-mount) shipping plus PKG-15 follow-up + PKG-24 (agent Dockerfile
vendoring) + PKG-25 (Linux reflink-fix).

**Matrix shape (per captain directive 2026-05-20, supersedes plan
body's N=5):** opus-4.7 + hints ON × three workspace-README variants
× 12 DAB datasets × **N=1** = 36 cells. Each cell dispatched as
`rk run --max-budget-usd-running <budget.json>` followed by per-cell
`rk audit --policy strict` + `rk score --against-constant <target>`.

## Cost-shape verification (T0)

1-trial opus-4.7 + harbor-DAB bookreview probe completed 3 sub-trials
(reward 0/3). Per-trial `cost_usd: null`; budget ledger
`cost_known: false`. **Branch A confirmed:** the
`CLAUDE_CODE_OAUTH_TOKEN` subscription tier covers opus-4.7; no API
billing. Captain approval gate NOT triggered (Branch B not entered).
Probe artifacts at `runs/goal1/t0/`.

## Headline (partial)

The matrix interrupted before the spacedock variant ran. The paper's
reproduction claim against `spacedock=0.577` and the per-variant
verdict against `direct_baseline=0.4376` are reported only where the
data exists:

| Variant            | Strata scored | Pooled n_pass / n_total | Pooled pass@1 | Pooled Wilson 95% CI | --against-constant verdict |
|--------------------|--------------:|------------------------:|--------------:|----------------------|----------------------------|
| `direct-minimal`   | 10 / 12       |             0 / 34      |       0.0000  | [0.000, 0.102]       | **below** (direct_baseline=0.4376) |
| `direct-structured`|  7 / 12       |            13 / 30      |       0.4333  | [0.274, 0.608]       | **matches** (direct_baseline=0.4376) |
| `spacedock`        |  0 / 12       |              n/a        |        n/a    |  n/a                 | **no_data** (spacedock=0.577) |

**Headline reproduction verdict against the paper:** **NOT
ESTABLISHED.** The spacedock variant has zero data, so the paper's
0.577 cannot be reproduced or refuted from this run. The
direct-structured variant's pooled pass@1 (0.433) overlaps the
paper's direct-baseline 0.4376 inside its 95% Wilson CI — consistent
with the paper, but on only 7 of 12 strata and inflated by
crmarenapro's 13 questions (see caveat F1).

The direct-minimal vs direct-structured contrast is the most
internally consistent finding: with the same model + hints + dataset
+ live verifier, the `direct-structured` README (which spells out
the workspace layout + DB credentials in the agent's README.md)
produces a far higher pass rate than `direct-minimal` (which omits
the layout/credentials). The agent in direct-minimal almost never
wrote `/workspace/answers.json` — every verifier output across the
direct-minimal cells reads `DAB verify: empty answer`. This is a
prompt-shape signal, not a model-capability finding.

## Per-cell table

Empty `n_completed_with_reward = 0` rows mean the trial completed
but the verifier saw no `/workspace/answers.json` (agent failed to
write the file) or the DB healthcheck failed pre-agent (mongo
agnews/yelp).

### direct-minimal — runs/goal1/matrix/direct-minimal/

| Dataset           | n_pass / n_total | pass@1 | Wilson 95% CI       | Note |
|-------------------|-----------------:|-------:|---------------------|------|
| agnews            |   0 / 0          | n/a    | n/a                 | mongo healthcheck failed (PKG-15 follow-up) |
| bookreview        |   0 / 3          | 0.000  | [0.000, 0.561]      | agent wrote no answers.json |
| crmarenapro       |   0 / 13         | 0.000  | [0.000, 0.228]      | agent wrote no answers.json (13 questions) |
| DEPS_DEV_V1       |   0 / 2          | 0.000  | [0.000, 0.658]      | |
| GITHUB_REPOS      |   0 / 2          | 0.000  | [0.000, 0.658]      | 2 of 4 questions returned no reward |
| googlelocal       |   0 / 4          | 0.000  | [0.000, 0.490]      | |
| music_brainz_20k  |   0 / 3          | 0.000  | [0.000, 0.561]      | |
| PANCANCER_ATLAS   |   0 / 2          | 0.000  | [0.000, 0.658]      | 2 of 3 questions reward-recorded |
| PATENTS           |   0 / 1          | 0.000  | [0.000, 0.793]      | 2 of 3 errored on `common_scaffold` ModuleNotFound (DAB verifier infra) |
| stockindex        |   0 / 3          | 0.000  | [0.000, 0.561]      | |
| stockmarket       |   0 / 1          | 0.000  | [0.000, 0.793]      | 4 of 5 had no reward recorded |
| yelp              |   0 / 0          | n/a    | n/a                 | mongo healthcheck failed (PKG-15 follow-up) |
| **Pooled**        | **0 / 34**       | 0.000  | [0.000, 0.102]      | |

### direct-structured — runs/goal1/matrix/direct-structured/

| Dataset           | n_pass / n_total | pass@1 | Wilson 95% CI       | Note |
|-------------------|-----------------:|-------:|---------------------|------|
| agnews            |   0 / 0          | n/a    | n/a                 | mongo healthcheck failed (PKG-15 follow-up) |
| bookreview        |   3 / 3          | 1.000  | [0.439, 1.000]      | clean |
| crmarenapro       |  10 / 13         | 0.769  | [0.497, 0.918]      | strongest stratum |
| DEPS_DEV_V1       |   0 / 2          | 0.000  | [0.000, 0.658]      | |
| GITHUB_REPOS      |   0 / 2          | 0.000  | [0.000, 0.658]      | 2 of 4 questions returned no reward |
| googlelocal       |   0 / 4          | 0.000  | [0.000, 0.490]      | |
| music_brainz_20k  |   0 / 3          | 0.000  | [0.000, 0.561]      | |
| PANCANCER_ATLAS   |   —              | —      | —                   | **MISSING — ENOSPC at 20/36** |
| PATENTS           |   —              | —      | —                   | **MISSING — ENOSPC follow-on** |
| stockindex        |   0 / 3          | 0.000  | [0.000, 0.561]      | |
| stockmarket       |   —              | —      | —                   | **MISSING — ENOSPC follow-on** |
| yelp              |   —              | —      | —                   | **MISSING — ENOSPC follow-on** |
| **Pooled (7 strata)** | **13 / 30** | 0.433  | [0.274, 0.608]      | |

### spacedock — runs/goal1/matrix/spacedock/

All 12 cells **never ran.** Matrix order was direct-minimal →
direct-structured → spacedock; ENOSPC at cell 20/36 (direct-structured
PANCANCER_ATLAS) ended the dispatcher before the spacedock variant
started. After PKG-21 ships, re-dispatch covers these 12 cells plus
the 4 missing direct-structured cells.

## Audit (n_tainted)

`rk audit --policy strict` over each cell's run-dir returns
`tainted: 0, clean: 0, coverage_missing: 0` because no per-trial
sentinel files (`claude-output.jsonl`, `codex-output.jsonl`,
`traces/manifest.json`) exist under the harbor-DAB stack the matrix
ran against. Audit didn't discover any trials to scan; AC-4's
literal claim (`n_tainted: 0` across cells) holds trivially.
**This is a coverage gap, not a leak finding** — the audit
discovery shape mismatches the harbor-DAB artifact shape. Treat as a
follow-up to PKG-17 (run-dir artifact writes) rather than a Goal 1
result.

## Cost ledger

Per-cell `budget.json` files are present at
`runs/goal1/matrix/<variant>/<dataset>/budget.json`. Each invocation
records `cost_known: false` and `actual_usd: null` (subscription
auth; opus-4.7's per-call cost is not reported back to razorback by
the claude CLI under subscription). Matrix-level pooled spend is
**0 USD** under the subscription. No API-billed dispatch was
attempted this session.

The captain's $500 budget cap was never approached. The subscription
covered every trial.

## Caveats (READ BEFORE CITING ANY NUMBER)

**a. Matrix interrupted at 20/36 (ENOSPC).** Root cause:
`_materialize_task_dir` does `shutil.copytree()` of every dataset's
`query_dataset/` subtree per question — for PANCANCER_ATLAS this is
a 7 GB SQLite db × 3 questions, for PATENTS 5 GB × 3, for stockmarket
920 MB × 5. PKG-14 (the data bind-mount) covered the postgres-init
SQL dump path but did not reach the per-question SQLite copy path.
PKG-21 shipped to main this session and closes that gap. Matrix
resume is gated on PKG-21 plus dispatcher idempotence (already in
place: `examples/drivers/dab-paper-matrix.sh` skips cells whose
`result.json` reports `n_completed >= 1 && n_errored == 0`).

**b. direct-minimal: agent never wrote answers.json.** Every
verifier output across direct-minimal cells reads
`DAB verify (/tests/validate.py): empty answer`. The agent
infrastructure (claude CLI + tools_allowed + tools_denied) ran end
to end; postgres healthchecked; the per-trial container exited
cleanly; but no `/workspace/answers.json` materialized. This is a
prompt-shape finding (the direct-minimal README omits workspace
layout and DB credentials), NOT a model-capability finding. The
direct-structured variant's bookreview 3/3 and crmarenapro 10/13
demonstrate the same model + hints + DB stack solves these
questions when the README is more explicit.

**c. agnews + yelp (mongo backends) failed mongo healthcheck.**
PKG-15's mongorestore .sh shim ships in the harbor-DAB compose
generator but did not produce a live mongo collection during this
matrix run for agnews or yelp. The
`db.getSiblingDB('articles_db').getCollection('articles').countDocuments() > 0`
healthcheck failed after 12 retries. Both cells report
`n_completed_trials > 0` (harbor counted the container shutdown as
completion) but `reward_stats: {}` (no verifier reward emitted).
PKG-15 follow-up entity required before these cells can score.

**d. PATENTS direct-minimal: 2 of 3 questions errored on
`ModuleNotFoundError: No module named 'common_scaffold'`.** This is a
DAB upstream verifier issue (the upstream validate.py imports a
shared helper module not staged in the dab-agent container); not a
razorback bug. PATENTS direct-minimal landed only 1 of 3 questions
in the reward distribution.

**e. ML reviewer's F8 (workspace_variant prose-prefix swap, NOT the
paper's architecture).** The three workspace-README variants
`direct-minimal`, `direct-structured`, `spacedock` differ by
**~4 lines of prose framing**. Goal 1's `spacedock` variant is a
one-paragraph prompt-prefix swap that reframes the task in
"data-agent crew" / "model → analyze → verify" language. It is **not**
the paper's spacedock workflow architecture (multi-step solver,
external verifier loop, distinct README per stage). Any number
captioned "spacedock variant" in this run measures
prompt-prefix-framing variance, not the paper's spacedock workflow.

**f. ML reviewer's F1 (stratum-collapse).** `rk score
--against-constant` pools trials × different questions within a
dataset into one binomial. Bookreview has 3 questions; crmarenapro
has 13; PATENTS has 3. The pooled pass@1 across strata weights
crmarenapro 13× compared to bookreview/PATENTS. Captain deferred
the stratum-aware score fix; this doc reports the pooled and the
mean-of-per-stratum-pass@1 to surface the bias. For
direct-structured, pooled = 0.433, mean-over-strata = 0.253; the
gap reflects crmarenapro's 0.769 pulling the pooled number up.

**g. Honesty bomb carryforward from PKG-13/16.** PKG-13's reported
9/9 reward=1.0 baseline was INFLATED — the agent had `Read+Bash` on
the workdir SQL dump and answered without touching postgres. PKG-16
closed that leak in code (workdir SQL-dump removal) and the honest
re-smoke (interrupted at 7/9) returned 4/7 = 57%. This matrix runs
under the PKG-16-closed code. Goal 1's direct-minimal bookreview
result (0/3) and direct-structured bookreview result (3/3) are
honest numbers under the closed-leak code path. They are NOT
comparable to the pre-PKG-13-fix 9/9.

**h. N=1 per cell, not the plan body's N=5.** Captain directive in
the dispatch handoff superseded the plan's N=5 framing. The 12 DAB
datasets each carry 2-13 upstream questions, so the per-cell
`n_total` is the dataset's `query_count` (not 5). The pre-registered
shift-band analysis from `2026-05-19-reconciliation-baseline.md` is
INVALIDATED for opus-4.7 bookreview (PKG-16's honest re-smoke
already invalidated it; this matrix confirms).

## Resume plan

After the following ship:

1. **PKG-21** (SQLite/DuckDB bind-mount via APFS clonefile) —
   DONE/on main per FO update. Removes the per-question
   `shutil.copytree` ENOSPC blocker.
2. **PKG-15 follow-up** for agnews + yelp mongo healthcheck. Specific
   shape TBD; either the shim isn't being invoked for these datasets
   or the BSON load is silently failing.
3. **PKG-24** (vendor agent Dockerfile + rename `dab-agent` →
   `razorback-solver`) — captain-filed this session; not blocking
   for resume but blocking for future Colima resets.
4. **PKG-25** (Linux reflink-fix for PKG-21's APFS path) — captain
   noted; not blocking for the next macOS-host resume.

Resume command (idempotent — `examples/drivers/dab-paper-matrix.sh`
skips cells with valid existing `result.json`):

```bash
export CLAUDE_CODE_OAUTH_TOKEN=$(cat ~/.claude/benchmark-token)
uv run examples/drivers/generate-dab-paper-matrix-specs.py --freeze
bash examples/drivers/dab-paper-matrix.sh \
  --continue-on-fail \
  --output-dir runs/goal1/matrix
uv run examples/drivers/aggregate-goal1-scores.py
```

After resume the spacedock variant's 12 cells + 4 direct-structured
cells will run. Total trials remaining: 12 + 4 = 16 cells × 2-13
questions ≈ 80-120 sub-trials × ~6-8 min each ≈ **8-16 hours**.

## Artifacts

- Matrix run-dirs: `runs/goal1/matrix/<variant>/<dataset>/...`
  (tasks/ subdirs were removed for disk recovery; result.json,
  summary.json, provenance.yaml, score.json, audit.json,
  spec.frozen.yaml, manifest.json, per_trial_outcomes.json,
  events.jsonl preserved per cell)
- Per-variant aggregate: `runs/goal1/matrix/<variant>/aggregate-score.json`
- Matrix summary: `runs/goal1/matrix/matrix-summary.json`
- T0 probe: `runs/goal1/t0/`
- Matrix dispatcher: `examples/drivers/dab-paper-matrix.sh`
- Spec generator: `examples/drivers/generate-dab-paper-matrix-specs.py`
- Aggregator: `examples/drivers/aggregate-goal1-scores.py`
- 36 source specs: `examples/specs/goal1/{variant}/{dataset}.yaml`
  (frozen specs + provenance.yaml regenerated by the generator;
  gitignored as host-specific per the `examples/specs/**/*.frozen.yaml`
  rule)

## Resume — spacedock-first re-dispatch (2026-05-22)

The archived PARTIAL ship buried the load-bearing spacedock variant
at position 25-36 of the 36-cell queue; ENOSPC at cell 20/36 left 0/12
spacedock cells. This resume entity re-dispatched the spacedock variant
FIRST (cells 1-12) so the headline reproduction number is preserved
under any future partial-completion scenario. Per captain decision
2026-05-22 the resume burned the spacedock variant ONLY (12 cells,
~$95 reconstructed) rather than the full 36 — direct-minimal +
direct-structured remain available as a follow-up dispatch.

### Headline reproduction — spacedock variant (load-bearing AC-5)

- **Stratified pass@1**: **0.500** (6 / 12 correct)
- **Wilson 95% CI**: **[0.254, 0.746]**
- **Paper target (spacedock=0.577)**: **INSIDE 95% CI**
- **Verdict**: REPRODUCTION CONSISTENT — paper's 0.577 falls within
  the Wilson 95% interval of our 12-cell stratified pass@1.

Per-dataset (1 trial each, opus-4.7, batch query_mode):

| Dataset           | Reward | Wall   | Cost (USD, recon.) |
|-------------------|--------|--------|--------------------|
| agnews            | 1.0    | ~3 min | 5.16               |
| bookreview        | 1.0    | 2:26   | 3.19               |
| crmarenapro       | 0.0    | 11:20  | 22.84              |
| DEPS_DEV_V1       | 0.0    | 5:19   | 7.40               |
| GITHUB_REPOS      | 0.0    | 6:09   | 8.41               |
| googlelocal       | 1.0    | 2:32   | 4.24               |
| music_brainz_20k  | 1.0    | 11:12  | 10.46              |
| PANCANCER_ATLAS   | 0.0    | 2:59   | 3.65               |
| PATENTS           | 0.0    | 10:01  | 12.74              |
| stockindex        | 1.0    | 1:42   | 1.97               |
| stockmarket       | 0.0    | 2:44   | 3.75               |
| yelp              | 1.0    | 8:19   | 10.96              |
| **Total**         | **6/12** | ~70 min | **94.77**       |

### Cost reconstruction methodology

`agent_result.cost_usd` is **null** on every cell despite paid-API
ANTHROPIC_API_KEY auth. Three goal1-resume-followup commits land
PKG-26's missing legs but a path-mismatch in
`ClaudeCliAgent.populate_context_post_run` keeps the on-disk surface
dark (see "Three follow-up bugs" below).

Costs in the table above are reconstructed post-hoc from the agent's
session jsonl (`.../<trial>/agent/sessions/projects/-workspace/*.jsonl`)
by `examples/drivers/aggregate-goal1-resume-cost.py`. The aggregator
sums usage tokens × opus-4.7 paid-tier prices:

- input: $15 / M tokens
- cache_creation: $18.75 / M tokens
- cache_read: $1.50 / M tokens
- output: $75 / M tokens

These prices come from public Anthropic pricing for claude-opus-4-7
on the standard service tier; raw counters are captured verbatim from
each session-jsonl `message.usage` block.

The reconstructed total ($94.77) is the canonical AC-5 evidence pending
the ClaudeCliAgent cost-emit path-mismatch fix.

### Three follow-up bugs surfaced and landed in goal1-resume

1. **mongo healthcheck probe was mongosh-based but dab-agent lacks
   mongosh** (commit faefc77). PKG-15 followup's `mongosh --host
   dab-mongo --eval "countDocuments() > 0"` ran from the agent's
   `main` step container, which ships python3+pymongo but NOT mongosh
   — every iteration surfaced `command not found` as rc=1, burning
   the retry budget without ever testing mongo content presence. Live
   smoke verification only exercised the postgres path (bookreview),
   missing the mongo-only datasets (agnews, yelp). Fix: rewrite probe
   to use `python3 -c "from pymongo import MongoClient; ...
   count_documents() > 0"`. New unit test asserts probe shape (would
   have caught the original). Default retries also tuned: 60 → 240
   (intermediate over-correction) → 90 (final, since the probe now
   actually works).

2. **spacedock_solver_v2 inner agent bypassed PKG-26's cost-emit
   subclass** (commit e3d3f1c). PKG-26 made razorback's claude-cli
   kind subclass harbor.ClaudeCode so cost_usd flows through paid-API
   runs. But `src/razorback/agents/_runtime/claude.py:build_inner_agent`
   (called by spacedock_solver_v2._build_inner_agent for runtime=claude)
   returned harbor.ClaudeCode DIRECTLY, bypassing the subclass. Fix:
   route through razorback.ClaudeCliAgent (still a ClaudeCode subclass,
   so harbor base contract preserved). Unit test asserts isinstance
   inner is ClaudeCliAgent + ClaudeCode.

3. **spacedock_solver_v2 did not delegate populate_context_post_run
   to inner** (commit e8cec00). Harbor's trial framework invokes
   populate_context_post_run on the OUTER agent only. The inner
   (now ClaudeCliAgent) holds PKG-26's cost-emit hook. Fix: add
   delegating override in SpacedockSolverAgent.

After these three fixes, harbor's stream-json tee still writes to
`<trial>/agent/claude-code.txt` (one level deeper than
ClaudeCliAgent.populate_context_post_run's `self.logs_dir / "claude-code.txt"`
expectation). The symlink-publish branch in
`populate_context_post_run` does not fire under spacedock_solver_v2's
logs_dir wiring, so `claude-output.jsonl` is not emitted and
`step_results[*].agent_result.cost_usd` remains None on disk. This
THIRD-LEG path mismatch is a separate follow-up entity for the next
session debrief. Post-hoc session-jsonl reconstruction is the
workaround used here.

### Matrix-order lesson

AC-5-style entity-typed reproductions where one variant is the load-
bearing claim MUST dispatch that variant first. The archived ship
buried spacedock at position 25-36 of the 36-cell queue; ENOSPC at
cell 20/36 left 0/12 spacedock cells, forcing the PARTIAL verdict.
The corrected ordering dispatches spacedock at cells 1-12 so any
future partial-completion scenario preserves the headline number.

The matrix-order discipline is now encoded structurally:
`WORKSPACE_VARIANTS = ("spacedock", "direct-structured", "direct-minimal")`
at `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py:7`
is the single canonical tuple. Both the spec generator and the
aggregator iterate it; the bash driver's `DEFAULT_VARIANTS`
constant mirrors it. A unit test
(`test_workspace_readme_variants.py::test_three_variants_exist`)
locks the spacedock-first order in.

### Direct-minimal + direct-structured: deferred

Per captain decision 2026-05-22 the resume burned ONLY the 12
spacedock cells (load-bearing AC-5 number). direct-minimal and
direct-structured (24 cells, projected ~$95 more at opus-4.7 paid
rates) are deferred as a follow-up dispatch entity, available for
captain re-dispatch after debrief. The matrix driver, spec set, and
aggregator all support a direct-only burn unchanged.

### Run-dir references (resume)

- Spacedock matrix run-dirs: `runs/goal1-resume/spacedock/<dataset>/`
- T0 probe (cost-shape verification): `runs/goal1-resume/t0/` and
  cost-projection note at
  `docs/razorback-implementation/goal1-resume-t0-cost-projection.md`
- Aggregate JSON: `runs/goal1-resume/aggregate-report.json`
- Dispatch ledger: `runs/goal1-resume/dispatch-ledger.tsv`
- Driver logs: `runs/goal1-resume/dispatch-*.log`
- Cost aggregator script: `examples/drivers/aggregate-goal1-resume-cost.py`
