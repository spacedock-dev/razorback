---
title: Goal 1 Re-run — DAB Spacedock Matrix (opus-4.7, reasoning_effort=xhigh) — Captain Report
entity: docs/razorback-implementation/goal1-rerun-dab-spacedock-opus47-xhigh.md
date: 2026-05-23
status: matrix complete, 8/12 strata scored, 4/12 verifier-infra failures
---

## Headline

**Spacedock pooled pass@1 = 0.375 (95% Wilson CI [0.137, 0.694]) across 8 scored strata.**
**Verdict vs paper `spacedock=0.577`: `matches` (paper inside CI).**

- 12/12 cells dispatched, 0 model-side failures.
- 8/12 strata produced rewards usable by the aggregator.
- 4/12 strata (`GITHUB_REPOS`, `PANCANCER_ATLAS`, `PATENTS`, `stockmarket`) failed at the
  verifier layer with `ModuleNotFoundError: No module named 'common_scaffold'` — an infrastructure
  bug in the DAB verifier container, unrelated to the agent's solutions.

## Per-dataset table

| dataset | n_total | n_pass | reward | pass@1 | wilson_95ci | wallclock | verifier_ok | against `paper=0.577` |
|---|---:|---:|---:|---:|---|---:|:---:|:---|
| agnews | 1 | 0 | 0.500 | 0.0 | [0.0, 0.793] | 2905s | yes | inside CI |
| bookreview | 1 | 1 | 1.000 | 1.0 | [0.207, 1.0] | 161s | yes | inside CI |
| crmarenapro | 1 | 0 | 0.692 | 0.0 | [0.0, 0.793] | 698s | yes | inside CI |
| DEPS_DEV_V1 | 1 | 0 | 0.500 | 0.0 | [0.0, 0.793] | 358s | yes | inside CI |
| GITHUB_REPOS | 0 | 0 | null | null | n/a | 470s | NO | dropped |
| googlelocal | 1 | 0 | 0.750 | 0.0 | [0.0, 0.793] | 181s | yes | inside CI |
| music_brainz_20k | 1 | 1 | 1.000 | 1.0 | [0.207, 1.0] | 509s | yes | inside CI |
| PANCANCER_ATLAS | 0 | 0 | null | null | n/a | 246s | NO | dropped |
| PATENTS | 0 | 0 | null | null | n/a | 463s | NO | dropped |
| stockindex | 1 | 1 | 1.000 | 1.0 | [0.207, 1.0] | 115s | yes | inside CI |
| stockmarket | 0 | 0 | null | null | n/a | 176s | NO | dropped |
| yelp | 1 | 0 | 0.857 | 0.0 | [0.0, 0.793] | 392s | yes | inside CI |
| **pooled** | **8** | **3** | **—** | **0.375** | **[0.137, 0.694]** | **6675s (1.85h)** | — | **matches** |

Per-query rewards (the 8 scored strata) range 0.5–1.0; 3 strata achieved a clean 1.0
pass (`bookreview`, `music_brainz_20k`, `stockindex`). The aggregator's `verdict=matches`
follows from `paper=0.577 ∈ [0.137, 0.694]`.

## Verifier-infra failure analysis (4 dropped cells)

All four dropped cells share the same root cause: the verifier container that runs
inside harbor's docker network cannot import `common_scaffold.validate.levenshtein`
(present in the validators path on disk but not on the verifier's Python `sys.path`).

Examples (first line of `<cell>/.../verifier/test-stdout.txt`):

- `GITHUB_REPOS`: `ModuleNotFoundError: No module named 'common_scaffold'`
- `PANCANCER_ATLAS`: same (`Missing histology type: 9382/3` warning + import crash)
- `PATENTS`: same (`Missing CPC code: A22B` warning + import crash)
- `stockmarket`: same (raw stack trace)

The agent's `answers.json` is written successfully in each case; only the verifier's
reward emission step fails. The harness records `n_completed_trials: 1, n_errored: 0`
and `reward: null` in result.json — the cell appears "ok" in dispatch-ledger.tsv but
contributes no scoring data to the aggregator.

This is a follow-up infra fix (DAB plugin verifier image bundling), not part of this
research run's scope.

## AC-5 — Provenance enumeration

Each cell's frozen spec carries 5 of 6 AC-5 fields directly; `model_resolved_version`
remains `null` per `--allow-missing` (resolved at API call time, not at freeze).
The remaining fields come from each cell's `provenance.yaml`. All cells share the
same harness-layer hashes because the agent block is identical across the 12 specs
(only `benchmark.datasets[0]` differs).

### Frozen-spec fields (per-cell from `examples/specs/goal1/spacedock/<dataset>.frozen.yaml`)

| dataset | sealed_hash | spacedock_skill_version | reasoning_effort | pin_model_version | model_resolved_version |
|---|---|---|---|---|---|
| all 12 cells | `377bd09522713c54668a004eb8a06834` | `1.0.0` | `xhigh` | `true` | `null` (allow-missing) |

(Identical sealed_hash across cells is correct — freeze hashes the agent block,
which is byte-identical across cells; only the benchmark.dataset name differs.)

### Provenance.yaml fields (per-cell from run-dir)

| field | value (shared across 12 cells) |
|---|---|
| `image_digest` | `sha256:d29dec396ea6651ca4a622e87e5e9607819e8e894868daa733818e534af961cc` |
| `agent_cli_hash` | `sha256:f4a1860d3d9b01653dde4183e2f1216ca9e0c1a404dd63caa4edf07c904102aa` |
| `harness_git_sha` | `642837af4cd99f232cd530385a04fcf03f1039b4` |
| `harbor_version` | `0.6.6` |
| `solver_workflow_hash` | `sha256:3aaaa409d92f5ce93eafa8e691a8a104ef00470fbdbd3dd18465b4e49a78d02b` |
| `unresolved` | `[model_resolved_version]` |

`harbor_agent_kwargs_hash` field (named in entity AC-5) does not appear under
this name in the actual provenance shape — the agent block's `sealed_hash` is
the harbor-kwarg-bound hash (and is recorded in the frozen spec instead).

## Freeze CAS check

- `RAZORBACK_FREEZE_DIR=/Users/clkao/git/razorback/_runs/_razorback-freeze/`
- Contents: 1 sealed_hash subdirectory (`377bd09522713c54668a004eb8a06834/`)
- Note: a single sealed_hash subdirectory is correct because the agent block is
  byte-identical across the 12 specs (see above). The freeze CAS is keyed on
  agent identity, not (agent, benchmark).
- Frozen spec count on disk under `examples/specs/goal1/spacedock/`:
  12 `*.frozen.yaml` (gitignored host-specific artifacts) + 1 `provenance.yaml`
  sidecar (last-write-wins per directory, expected shape).

## Cost ledger

- `dispatch-ledger.tsv` records `cost_usd: null` for every cell. The harness's
  cost-telemetry layer (claude-cli → harbor → result.json `stats.cost_usd`) did
  not populate this field in any cell despite successful model interaction.
  Per-cell `claude-code.txt` event logs show real `assistant` + `tool_use` events
  with thinking blocks, indicating non-trivial opus-4.7 API usage occurred.
- No per-cell `cost_usd` is available; total cost is unknown from artifacts.
  The `--max-cell-budget-usd 10.0` gate did not trip (no cell aborted on budget).
- This is a known shape from prior goal1 dispatches; cost telemetry is a separate
  follow-up entity, not blocking the headline.

## Wallclock ledger

- Total wallclock across 12 cells (sequential, concurrency.trials=1): **6675s ≈ 1.85h**.
- Per-cell range: 115s (stockindex) to 2905s (agnews).
- Faster than the plan's 10–15min/cell estimate because batch query_mode bundles
  all queries per dataset into a single composite trial; many cells finished in
  2–5 min.

## Deviations from plan

1. **runs_dir relocation.** Plan specified `$XDG_DATA_HOME/razorback/runs/...`.
   Used `/Users/clkao/git/razorback/_runs/goal1-rerun-spacedock-opus47-xhigh/`
   instead because (a) sandbox blocked the canonical XDG path
   (`~/.local/share/razorback/` — Operation not permitted), (b) Colima virtiofs
   requires runs-dir under `/Users/...` (`/tmp` path rejected with
   `ConfigInvalidError: runs-dir not visible to harbor docker containers`).
   Captain-approved deviation; project-root `_runs/` is gitignored and
   "outside-worktree-and-persistent" per x9's spirit.

2. **freeze_dir relocation.** Same reason as runs_dir. Used
   `/Users/clkao/git/razorback/_runs/_razorback-freeze/` instead of
   `~/.local/share/razorback/freeze/`. Same captain-approved deviation.

3. **DATAAGENTBENCH_DATA_ROOT correction.** The 12 frozen specs default
   `data_root: ${DATAAGENTBENCH_DATA_ROOT:-~/dataagentbench/data}` resolves to
   `~/dataagentbench/data` if the env var is unset. The hydrated data is at
   `~/git/dataagentbench/data`. Set `DATAAGENTBENCH_DATA_ROOT=/Users/clkao/git/dataagentbench/data`
   in the dispatcher's env before retrying. First T5 attempt fast-failed all
   12 cells with `razorback-plugin-dab: dataset X not hydrated, found LFS pointer at
   ~/dataagentbench/data/...`; second attempt with the corrected env var ran
   the full matrix.

4. **AC-5 field naming.** The `harbor_agent_kwargs_hash` field named in entity
   AC-5 does not appear under that name in the actual `provenance.yaml`; the
   semantically-equivalent value is `agent.sealed_hash` in the frozen spec
   (the harbor-kwargs sealed_hash). Documented in the provenance section above.

5. **Cost telemetry.** Every cell's `cost_usd` is `null`. This is consistent
   with prior goal1 runs; the cost telemetry layer is a known gap. Not a
   blocker for the headline pass@1 number.

## Artifact retention

Per-cell `summary.json` + `provenance.yaml` + `result.json` + `score.json`
mirrored to `docs/razorback-implementation/_evidence/an-goal1-rerun-cells/<dataset>/`.
Full per-trial trajectories (including `claude-code.txt` jsonl logs) remain in
`/Users/clkao/git/razorback/_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/<dataset>/`;
these are ~5–500MB per cell and not committed to git.

Re-run reproducibility: from the 12 committed `examples/specs/goal1/spacedock/<dataset>.yaml`,
re-run `rk freeze <spec> --allow-missing` to regenerate the host-specific frozen.yaml
and provenance.yaml sidecars; then dispatch the matrix as described in
`docs/razorback-implementation/plans/goal1-rerun-dab-spacedock-opus47-xhigh.md`.

## Follow-ups suggested

1. **Fix DAB verifier `common_scaffold` import.** 4/12 strata dropped due to a
   verifier-container Python path bug. Filing this entity would unblock
   GITHUB_REPOS, PANCANCER_ATLAS, PATENTS, stockmarket scoring on future runs.
2. **Surface cost telemetry.** Every cell `cost_usd: null` despite successful
   API calls. Cost ledger entity to make the budget guardrail actually backed
   by recorded numbers.
3. **N=5 reproduction.** Headline `pass@1=0.375 [0.137, 0.694]` is N=1 with
   wide CI; an N=5 follow-up would tighten the CI around whatever the true
   spacedock baseline is for opus-4.7+xhigh.
4. **canonical XDG runs-dir for headless agent contexts.** Sandbox blocks
   `~/.local/share/razorback/` — either grant the permission in this harness
   config or document the project-root `_runs/` convention as the supported
   alternative.
