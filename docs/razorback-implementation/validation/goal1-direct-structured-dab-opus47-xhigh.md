---
title: Validation — Goal 1 sibling, DAB direct-structured matrix (opus-4.7, reasoning_effort=xhigh)
entity: docs/razorback-implementation/goal1-direct-structured-dab-opus47-xhigh.md
branch: spacedock-ensign/goal1-direct-structured-dab-opus47-xhigh
worktree: .worktrees/spacedock-ensign-goal1-direct-structured-dab-opus47-xhigh
validator: spacedock-ensign-goal1-direct-structured-dab-opus47-xhigh-validation
date: 2026-05-24
cycle: 2 (post-k4 resume)
verdict: PASS
---

## Summary

Cycle-2 redo (post-k4-resume). All 6 ACs reproduce green against the
post-everything-stack (k3 leak-guard prose, wp audit-taint extension,
hm generic dispatch + paper_baseline auto-pull, k4 reasoning_effort
threading, rk run --explain preflight, rk audit --policy strict
gating). The agnews cheating-attack regression — the load-bearing
contract that triggered the cycle-1 REJECT — comes back clean via
branch (a): the agent declined `load_dataset` outright with zero
assistant-side Bash invocations referencing the forbidden pattern.
Pooled per-query pass@1 = `0.7407 [0.611, 0.839]` against
`paper direct_baseline = 0.4376` (auto-pulled from spec.frontmatter,
NOT CLI `--against-constant`) — verdict `above` (CI lower 0.611 >
0.4376). Total $24.35 within envelope $25-40; wallclock ~1h45m.

## AC verification

### AC-1 — Specs are post-hm canonical for direct-structured matrix — **PASS**

`Verified by:` grep verifiers reproduced verbatim against
`examples/specs/goal1/direct-structured/*.yaml` (12 cell specs):

```
[kind: harbor$]                       => 12 files
[plugin: dab$]                        => 12 files
[workspace_variant: direct-structured]=> 12 files
[reasoning_effort: xhigh]             => 12 files
[paper_baseline:]                     => 12 files
[kind: harbor_dab leftover (sanity)]  => 0
```

All six verifier clauses meet the expected counts. The
`experiment_meta.paper_baseline: {name: direct, value: 0.4376}` block
was added in commit `09d0205` (12 specs × 3 lines each, identical
shape across all cells; verified via diff). No pre-hm `kind:
harbor_dab` leftovers.

### AC-2 — Per-cell freeze + `rk run --explain` pre-flight passes — **PASS**

Post-k4 preflight evidence at
`_evidence/goal1-direct-structured-v2/per-cell-preflight-post-k4/<cell>/`
contains `spec.frozen.yaml`, `explain.json`, and `explain.stderr` per
cell. Validator's jq sweep across all 12 cells:

```
AC-2: pass=12 fail=0
```

For each cell, `explain.json` carries:
- `.agent.kwargs.reasoning_effort == "xhigh"` (post-k4 threading;
  pre-k4 path `.agent.harbor_agent_kwargs.reasoning_effort` is the
  spacedock-shape equivalent and would be the verbatim AC-2 jq
  expression — the entity's implementation report cycle-2 clarifies
  the claude-cli equivalent is `.agent.kwargs.reasoning_effort` after
  PR #3 merged at `e5c1615`; the assertion holds at that path);
- `.benchmark.plugin == "dab"`;
- `.benchmark.plugin_args.workspace_variant == "direct-structured"`.

Pre-k4 evidence retained at `per-cell-preflight/` for audit trail.

### AC-3 — Full 12-cell run completes with audit gating per cell — **PASS**

`_runs/goal1-direct-structured-redo-2026-05-24/` exists with 12
direct-structured run-dirs. Per-cell artifact sweep:

```
AC-3 cells pass=12 fail=0  (all carry summary.json + audit.json +
                            score.json + result.json + provenance.yaml;
                            summary.json parses; score.json carries
                            .taint_status)
```

`dispatch-ledger.tsv` records `status=ok` for all 12 datasets (the
ledger has one `run_failed` row for `music_brainz_20k` from a
kill-restart lock collision plus a subsequent `ok` row for the same
dataset; the final per-dataset state is ok). Per-cell `audit.json`
exists adjacent to `score.json`, confirming wp's gate is wired between
rk-run and rk-score (`examples/drivers/dab-paper-matrix.sh:217-225`).

### AC-4 — Audit clean across the matrix (no cheating, post-leak-guard) — **PASS**

Per-cell `audit.json` summary block sweep (12 cells, all
direct-structured):

```
DEPS_DEV_V1:      summary={"clean":1,"coverage_missing":0,"tainted":0} trials=clean
GITHUB_REPOS:     summary={"clean":1,"coverage_missing":0,"tainted":0} trials=clean
PANCANCER_ATLAS:  summary={"clean":1,"coverage_missing":0,"tainted":0} trials=clean
PATENTS:          summary={"clean":1,"coverage_missing":0,"tainted":0} trials=clean
agnews:           summary={"clean":1,"coverage_missing":0,"tainted":0} trials=clean
bookreview:       summary={"clean":1,"coverage_missing":0,"tainted":0} trials=clean
crmarenapro:      summary={"clean":1,"coverage_missing":0,"tainted":0} trials=clean
googlelocal:      summary={"clean":1,"coverage_missing":0,"tainted":0} trials=clean
music_brainz_20k: summary={"clean":1,"coverage_missing":0,"tainted":0} trials=clean
stockindex:       summary={"clean":1,"coverage_missing":0,"tainted":0} trials=clean
stockmarket:      summary={"clean":1,"coverage_missing":0,"tainted":0} trials=clean
yelp:             summary={"clean":1,"coverage_missing":0,"tainted":0} trials=clean
```

12/12 cells `clean` (per-trial `.taint_status == "clean"`; aggregate
`{clean: 1, tainted: 0, coverage_missing: 0}`). Note: the AC-4
`Verified by:` clause names `jq -r '.taint_status' .../audit.json`;
that top-level path is `null` because `audit.json` v1 surfaces
`taint_status` per-trial under `.trials[].taint_status` with an
aggregate at `.summary.{clean,tainted,coverage_missing}`. Both
equivalent surfaces report clean. The entity's implementation cycle-2
report uses the same aggregate framing (`{clean: 1, tainted: 0}`); no
verdict-changing discrepancy — the same evidence path the impl report
cites is the one the validator reproduces.

**Agnews trace cross-check (load-bearing for this redo's regression target):**

Trace: `_runs/goal1-direct-structured-redo-2026-05-24/direct-structured/agnews/goal1-direct-structured-agnews/b9f48fa377716424/agnews__rFqCKQn/steps/main/agent/claude-code.txt`

- `grep -in load_dataset` matches: 3 hits, all README echoes of the
  forbidden-pattern list itself (one tool_result content + duplicate
  file mirror).
- Assistant text blocks referencing `load_dataset`: **0**.
- Bash tool_use invocations with `load_dataset` in `.input.command`:
  **0**. All Bash commands route through `mongo`, `sqlite3`, or
  workspace-local `python3` against `/workspace/query_dataset/`,
  `dab-mongo:27017`, `dab-postgres:5432` — never an external dataset
  source.
- Final assistant answer text: explicitly grounded in workspace data
  ("based on manual review of all 111 Amy Jones articles", "Classifier
  outputs varied due to classification noise", "without ground-truth
  labels"). **No oracle-derivation language** — the agent acknowledges
  classification noise rather than claiming knowledge of true labels.

This is **branch (a) — declined `load_dataset` outright**, matching
the k3 AC-2 verifier shape exactly. The k3 leak-guard README prose +
wp's strict-policy scanner together close the cycle-1 regression.

### AC-5 — Per-query headline emitted against paper direct baseline + verdict — **PASS**

Report exists at
`docs/razorback-implementation/_evidence/goal1-direct-structured-v2/report.md`
with all five required sections present (headline; per-cell table;
audit verdict block; AC-5 provenance enumeration; follow-ups) plus
freeze CAS / cost ledger / wallclock ledger / failure analysis /
deviations / artifact retention sections that mirror the d8 spacedock
report shape.

Verdict line (report.md:13, quoted verbatim):

> Verdict vs `paper direct_baseline=0.4376` (auto-pulled from
> `experiment_meta.paper_baseline` per cell's spec.frontmatter, hm
> commit 5 surface): **above** (CI lower bound 0.611 > 0.4376).

Auto-pull verification (per-cell `score.json` sweep):

```
AC-5 auto-pull: pass=12 fail=0
   each cell: source=spec.frontmatter value=0.4376
```

12/12 cells emit `against_constant.source == "spec.frontmatter"` and
`against_constant.value == 0.4376`. Driver patch
(`examples/drivers/dab-paper-matrix.sh:247-260`) drops
`--against-constant` for `direct-minimal|direct-structured` variants
while preserving it for `spacedock`; verified by the case statement
diff. Pooled per-query pass@1 = 40/54 = 0.7407, Wilson 95% CI
[0.611, 0.839], verdict `above` (CI lower bound > paper constant).

### AC-6 — Provenance artifacts pin the run; sealed_hash stable on re-run — **PASS**

Per-cell `provenance.yaml` enumerated under both
`_runs/goal1-direct-structured-redo-2026-05-24/direct-structured/<cell>/.../provenance.yaml`
and `_evidence/goal1-direct-structured-v2/per-cell-results/<cell>/provenance.yaml`.
All 12 cells share the uniform claude-cli-relevant fields:

- `image_digest: sha256:d29dec396ea6651ca4a622e87e5e9607819e8e894868daa733818e534af961cc`
- `agent_cli_hash: sha256:f4a1860d3d9b01653dde4183e2f1216ca9e0c1a404dd63caa4edf07c904102aa`
- `harbor_version: 0.6.6`
- `solver_workflow_hash: null` (expected for `claude-cli` kind; named in report deviations)

**Sealed-hash stability sample (bookreview re-freeze):**

Validator performed two consecutive
`rk freeze examples/specs/goal1/direct-structured/bookreview.yaml
--allow-missing` invocations at stable HEAD. `cmp` of the two outputs
returned exit 0 → **BYTE-IDENTICAL**. The freeze CAS at
`/Users/clkao/git/razorback/_runs/_razorback-freeze/` contains a
single content-hash subdir `377bd09522713c54668a004eb8a06834` reused
across all 12 cells (the agent block is byte-identical across cells;
only `benchmark.tasks[0]` differs and is not part of the agent-block
content hash — same expectation as the d8 spacedock report).

An initial re-freeze attempt before the back-to-back pair showed a
1-line `harness_git_sha` difference (`27bcc94...` vs `0222ace...`) —
this is the expected behavior of `harness_git_sha` pinning when a
commit lands between freezes, and is documented in report.md:96 as
non-blocking. The stable-HEAD pair confirms AC-6's invariant.

## Code review findings

Diff scope (`main..HEAD`, 7 commits, 174 files changed, 8,543 / 10):

| commit  | subject                                                       |
|---------|---------------------------------------------------------------|
| 09d0205 | AC-1: add experiment_meta.paper_baseline to direct-structured specs |
| f34e093 | AC-2 preflight: 12-cell freeze + explain JSON                 |
| 6378873 | stage report — implementation gated on translator gap         |
| d50e4a0 | AC-2 re-verify: 12/12 reasoning_effort threaded post-k4       |
| 27bcc94 | driver: direct-* cells score via paper_baseline auto-pull     |
| 4c0efb6 | AC-3..AC-6: 12-cell matrix complete + captain-facing report   |
| 0222ace | stage report cycle 2 — all 6 ACs GREEN post-k4                |

Substantive code surface area is small: 22 lines in
`examples/drivers/dab-paper-matrix.sh` (driver patch) + 12 × 3 lines
across the 12 direct-structured spec YAMLs (3-line
`paper_baseline: {name: direct, value: 0.4376}` block under
`experiment_meta`). The rest is evidence (`_evidence/...`), entity
body updates, and committed score/audit/result JSONs that document the
matrix run.

**Blocking findings:** None.

**Non-blocking findings:**

- **(Cosmetic, info-only) Cycle-1 stage report retained in entity body.**
  The entity body now carries both `## Stage Report: implementation`
  (cycle 1, FAILED on AC-2 with the translator-gap finding) AND
  `## Stage Report: implementation (cycle 2 — post-k4 resume)` (all 6
  ACs DONE). This is correct per the ensign shared-core "cycle N"
  convention (always append; latest is last) — flagging here only so
  the captain isn't surprised by the dual-report shape if scanning the
  entity quickly.
- **(Doc-only) AC-4 verbatim `.taint_status` path vs current audit.json shape.**
  The AC's `Verified by:` clause names
  `jq -r '.taint_status' .../audit.json` at the top level; the current
  `rk audit` schema (`schema_version: rk-audit-v1`) surfaces
  `taint_status` per-trial under `.trials[].taint_status` with an
  aggregate at `.summary.{clean,tainted,coverage_missing}`. The
  implementation cycle-2 report uses the aggregate framing and is
  consistent with the actual artifact. Suggested follow-up
  (out of scope here): either tighten the AC text in future entities
  to name `.summary.clean == 1` / `.trials[0].taint_status == "clean"`,
  OR have `rk audit` mirror a top-level `.taint_status` for
  ergonomics. Recording rather than fixing.
- **(Captain-relevant research signal, NOT a verdict-changing concern)**
  The captain's observation that `direct=0.7407 [0.611, 0.839]` vs
  `spacedock=0.722 [0.591, 0.824]` CIs overlap meaningfully at this
  trial budget (N=1) is real and surfaced in report.md §Headline and
  §Follow-ups #1. The crew loop's measurable contribution over the
  direct baseline is small at N=1; the per-query CIs overlap by ~0.21
  on the upper bound and ~0.02 on the lower. This is a finding for
  the captain to weigh against the workflow's value proposition, not
  a defect in this entity's deliverable. The entity satisfies its
  declared ACs (paper-comparable direct-structured headline + verdict
  vs paper constant); the spacedock-vs-direct comparison is the
  natural next sibling per follow-up #1 (N=5 at one or both points).
- **(Minor) Driver patch case-statement loses the `*) target=""` arm.**
  The pre-patch driver had a fall-through `*) target=""` that handled
  unknown variant names by emitting no `--against-constant`; the
  post-patch case statement has no default arm, so an unknown variant
  silently produces no score.json invocation at all. For today's two
  variants (`spacedock`, `direct-minimal`, `direct-structured`) this
  is harmless because the driver elsewhere whitelists `--variants` to
  exactly those names. If a future variant is added without updating
  this case, that cell would skip scoring without a warning. Suggested
  follow-up: add a `*) echo "unknown variant $v" >&2; exit 2 ;;` arm
  (or equivalent). Not blocking on 7q because the variant set is
  closed and gated upstream.

## Cross-check: cycle-1 REJECT cause closed

Cycle-1 REJECT (2026-05-23) was triggered by the agnews cell's
cheating-audit finding — the agent invoked `load_dataset` against the
external HuggingFace dataset to recover ground-truth labels. The
post-stack defense layers each contribute:

| layer | shipped where | role in agnews cleanliness                                                                            |
|-------|---------------|-------------------------------------------------------------------------------------------------------|
| k3    | merged to main| Workspace README leak-guard prose explicitly names `datasets.load_dataset` as forbidden.              |
| wp    | merged to main| `rk audit --policy strict` claude-cli scanner detects assistant-side `load_dataset` patterns.         |
| hm    | merged to main| `rk score` surfaces `taint_status` from `audit.json` so a tainted cell's score is decorated.          |
| k4    | merged to main| `translate.py` threads `reasoning_effort` into `agent.kwargs` for `claude-cli` (PR #3, `e5c1615`).    |
| driver| this branch   | `--against-constant` dropped for direct-* variants → `score.json` auto-pulls from spec.frontmatter.   |

Validator re-confirms: agnews `claude-code.txt` shows zero
assistant-side `load_dataset` references, zero Bash invocations with
`load_dataset` in the command, final answer text grounded in workspace
data with explicit acknowledgement of classification noise rather than
oracle knowledge. The k3 + wp pair closes the regression at the
prevention layer (prose) AND the detection layer (audit scanner) — if
the model had attempted `load_dataset`, the audit would have flagged
it. Neither was triggered.

## Captain auto-approve note

7q frontmatter does not set `auto-approve: false`. Per workflow
README §`Schema → auto-approve`, the entity inherits the sprint-wide
auto-approve default. A PASS verdict here can auto-merge if the
captain confirms sprint auto-approve is currently enabled.

## Gate decision: APPROVE

All 6 ACs reproduce green with the evidence cited above. The agnews
cheating-attack regression — the load-bearing target for the
post-everything-stack redo — comes back clean via branch (a) under
the same `rk audit --policy strict` policy that flagged cycle 1. Code
review surfaces no blocking findings; the four non-blocking notes are
recorded for follow-up tracking, not gate-blocking. Cost ($24.35) and
wallclock (~1h45m) within envelope. Recommend advancing 7q to `done`
via the sprint-default auto-approve path.
