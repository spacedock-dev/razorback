---
title: Goal 1 Re-run — DAB Spacedock Matrix (opus-4.7, reasoning_effort=xhigh) — Captain Report
entity: docs/razorback-implementation/goal1-rerun-dab-spacedock-opus47-xhigh.md
date: 2026-05-23
status: matrix complete (cycle 2), 12/12 strata scored
---

## Headline (cycle 2 — clean 12/12)

**Spacedock pooled pass@1 = 0.333 (95% Wilson CI [0.138, 0.609]) across 12 scored strata.**
**Verdict vs paper `spacedock=0.577`: `matches` (paper inside CI).**

- 12/12 cells dispatched + scored, 0 model-side failures, 0 verifier-infra failures.
- 4 strata (`bookreview`, `music_brainz_20k`, `stockindex`, `stockmarket`) scored
  pass@1=1.0; remaining 8 strata scored pass@1=0.0 with partial rewards in the
  0.0–0.857 range.
- The four cells dropped by cycle 1 (`GITHUB_REPOS`, `PANCANCER_ATLAS`, `PATENTS`,
  `stockmarket`) were re-scored cleanly after rebasing onto Codex's verifier fix
  (`d6fbfdd Fix DAB batch common_scaffold verifier imports`). The 8 cycle-1 cells
  were preserved and rolled into the aggregate; only the 4 dropped cells were
  re-executed.

## Cycle-1 headline (preserved for trail)

**Cycle 1 — 8/12 scored: pooled pass@1 = 0.375 (95% Wilson CI [0.137, 0.694]).**
Same verdict (`matches`). 4/12 cells crashed at the verifier layer with
`ModuleNotFoundError: No module named 'common_scaffold'`. These 4 cells were
re-executed in cycle 2 against the same frozen specs (sealed_hash unchanged at
`377bd09522713c54668a004eb8a06834`) after the verifier-container fix landed in
main and was rebased into the worker branch. The cycle-1 cell run-dirs are
preserved on disk under `_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/cycle1.<dataset>/`
for evidence comparison; the cycle-1 dispatch ledger is preserved as
`dispatch-ledger.cycle1.tsv`.

## Per-dataset table (cycle 2 — 12/12 scored)

| dataset | n_total | n_pass | reward | pass@1 | wilson_95ci | wallclock | cycle | verifier_ok | against `paper=0.577` |
|---|---:|---:|---:|---:|---|---:|:---:|:---:|:---|
| agnews | 1 | 0 | 0.500 | 0.0 | [0.0, 0.793] | 2905s | 1 | yes | inside CI |
| bookreview | 1 | 1 | 1.000 | 1.0 | [0.207, 1.0] | 161s | 1 | yes | inside CI |
| crmarenapro | 1 | 0 | 0.692 | 0.0 | [0.0, 0.793] | 698s | 1 | yes | inside CI |
| DEPS_DEV_V1 | 1 | 0 | 0.500 | 0.0 | [0.0, 0.793] | 358s | 1 | yes | inside CI |
| GITHUB_REPOS | 1 | 0 | 0.500 | 0.0 | [0.0, 0.793] | 417s | 2 | yes | inside CI |
| googlelocal | 1 | 0 | 0.750 | 0.0 | [0.0, 0.793] | 181s | 1 | yes | inside CI |
| music_brainz_20k | 1 | 1 | 1.000 | 1.0 | [0.207, 1.0] | 509s | 1 | yes | inside CI |
| PANCANCER_ATLAS | 1 | 0 | 0.667 | 0.0 | [0.0, 0.793] | 209s | 2 | yes | inside CI |
| PATENTS | 1 | 0 | 0.000 | 0.0 | [0.0, 0.793] | 617s | 2 | yes | inside CI |
| stockindex | 1 | 1 | 1.000 | 1.0 | [0.207, 1.0] | 115s | 1 | yes | inside CI |
| stockmarket | 1 | 1 | 1.000 | 1.0 | [0.207, 1.0] | 201s | 2 | yes | inside CI |
| yelp | 1 | 0 | 0.857 | 0.0 | [0.0, 0.793] | 392s | 1 | yes | inside CI |
| **pooled** | **12** | **4** | **—** | **0.333** | **[0.138, 0.609]** | **6675s + 1444s = 8119s (2.26h)** | — | — | **matches** |

Per-query rewards span 0.0–1.0; 4 strata achieved a clean 1.0 pass
(`bookreview`, `music_brainz_20k`, `stockindex`, `stockmarket`). The
aggregator's `verdict=matches` follows from `paper=0.577 ∈ [0.138, 0.609]`.
Compared with the cycle-1 partial headline (`0.375 [0.137, 0.694]` on 8/12),
the 12/12 pooled headline is slightly lower (`0.333` vs `0.375`) but the
95% Wilson CI tightened on the upper bound (`0.609` vs `0.694`) and the
paper constant remains inside CI.

## Cycle-2 re-execution detail (4 cells re-scored)

The four cells dropped by cycle 1 were re-executed on 2026-05-23 against the
same frozen specs (sealed_hash `377bd09522713c54668a004eb8a06834` preserved
byte-identically). The dispatcher invocation was scoped via
`--variants spacedock --datasets GITHUB_REPOS,PANCANCER_ATLAS,PATENTS,stockmarket`;
all four cells produced clean `score.json` with `n_completed=1, n_errored=0`
and no `ModuleNotFoundError: common_scaffold` in any verifier output.

| dataset | cycle-1 verifier output | cycle-2 reward | cycle-2 pass@1 | wallclock |
|---|---|---:|---:|---:|
| GITHUB_REPOS | `ModuleNotFoundError: common_scaffold` (validate_q2 import) | 0.500 | 0.0 | 417s |
| PANCANCER_ATLAS | same | 0.667 | 0.0 | 209s |
| PATENTS | same | 0.000 | 0.0 | 617s |
| stockmarket | same | 1.000 | 1.0 | 201s |

Total cycle-2 wallclock: 1444s (24m), under the 40-60m assignment budget.

### Root-cause + fix

Cycle 1's verifier containers crashed when importing
`common_scaffold.validate.levenshtein` from upstream `validate_q*.py` files. The
common_scaffold package lives at `${DATAAGENTBENCH_DATA_ROOT}/common_scaffold/`
on the host but was not copied into the per-trial verifier `tests/` directory
during batch task materialization.

Codex's fix (commit `d6fbfdd` on `main`, 2026-05-23): add
`_install_common_scaffold(tests_dir, data_root)` to
`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py`,
called from `_materialize_batch_task_dir`. The function copies
`data_root/common_scaffold/` into `tests_dir/common_scaffold/` (excluding
`__pycache__`). After the worker's branch was rebased onto main,
`git merge-base --is-ancestor d6fbfdd HEAD` returns 0, and the next dispatch
sees the file copy in the materialized tests dir at verifier-image build time.

Verifier-output crosscheck for the 4 cells:
`grep -c "common_scaffold\|ModuleNotFoundError" <cell>/.../steps/main/verifier/test-stdout.txt`
returns 0 for all four cycle-2 cells.

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

- Cycle 1 — total wallclock across 12 cells (sequential, concurrency.trials=1):
  **6675s ≈ 1.85h** (115s stockindex – 2905s agnews).
- Cycle 2 — total wallclock across the 4 re-executed cells: **1444s ≈ 24m**
  (201s stockmarket, 209s PANCANCER_ATLAS, 417s GITHUB_REPOS, 617s PATENTS).
- Combined wallclock (cycle 1 + cycle 2): **8119s ≈ 2.26h**.
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

5. **Cost telemetry.** Every cell's `cost_usd` is `null` in both cycles. This
   is consistent with prior goal1 runs; the cost telemetry layer is a known gap.
   Not a blocker for the headline pass@1 number.

6. **Cycle-2 verifier-fix rebase.** Cycle 1 dropped 4 cells (GITHUB_REPOS,
   PANCANCER_ATLAS, PATENTS, stockmarket) at the DAB verifier-container layer
   with `ModuleNotFoundError: No module named 'common_scaffold'`. Codex's fix
   landed on main as commit `d6fbfdd Fix DAB batch common_scaffold verifier imports`
   the same day. The worker's branch was rebased onto main to pick up the fix
   (`git merge-base --is-ancestor d6fbfdd HEAD` returns 0 from HEAD of branch
   `spacedock-ensign/goal1-rerun-dab-spacedock-opus47-xhigh`), then the dispatcher
   was re-run scoped to the 4 dropped cells only. The 8 cycle-1 cells were
   preserved and rolled into the aggregate as-is; their frozen specs are
   sealed-hash-identical across cycles, so the per-cell stratum values stay
   stable. Cycle-1 cell run-dirs are preserved on disk at
   `_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/cycle1.<dataset>/` and
   the cycle-1 dispatch ledger is preserved as `dispatch-ledger.cycle1.tsv`.

## Artifact retention

Per-cell `summary.json` + `provenance.yaml` + `result.json` + `score.json`
mirrored to `docs/razorback-implementation/_evidence/an-goal1-rerun-cells/<dataset>/`.
For the 4 cycle-2 cells (`GITHUB_REPOS`, `PANCANCER_ATLAS`, `PATENTS`,
`stockmarket`), `reward_per_query.json` from the verifier step is also mirrored
into the same per-cell evidence directories.
Full per-trial trajectories (including `claude-code.txt` jsonl logs) remain in
`/Users/clkao/git/razorback/_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/<dataset>/`;
these are ~5–500MB per cell and not committed to git.

Re-run reproducibility: from the 12 committed `examples/specs/goal1/spacedock/<dataset>.yaml`,
re-run `rk freeze <spec> --allow-missing` to regenerate the host-specific frozen.yaml
and provenance.yaml sidecars; then dispatch the matrix as described in
`docs/razorback-implementation/plans/goal1-rerun-dab-spacedock-opus47-xhigh.md`.

## Follow-ups suggested

1. **DAB verifier `common_scaffold` import.** RESOLVED by Codex commit `d6fbfdd`
   (`Fix DAB batch common_scaffold verifier imports`) on 2026-05-23, picked up
   in cycle 2 via branch rebase onto main.
2. **Surface cost telemetry.** Every cell `cost_usd: null` despite successful
   API calls (both cycles). Cost ledger entity to make the budget guardrail
   actually backed by recorded numbers.
3. **N=5 reproduction.** Headline `pass@1=0.333 [0.138, 0.609]` is N=1 with
   wide CI; an N=5 follow-up would tighten the CI around whatever the true
   spacedock baseline is for opus-4.7+xhigh.
4. **canonical XDG runs-dir for headless agent contexts.** Sandbox blocks
   `~/.local/share/razorback/` — either grant the permission in this harness
   config or document the project-root `_runs/` convention as the supported
   alternative.
