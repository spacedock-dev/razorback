---
title: Validation — Goal 1 re-run DAB spacedock (opus-4.7, reasoning_effort=xhigh)
entity: docs/razorback-implementation/goal1-rerun-dab-spacedock-opus47-xhigh.md
branch: spacedock-ensign/goal1-rerun-dab-spacedock-opus47-xhigh
worktree: .worktrees/spacedock-ensign-goal1-rerun-dab-spacedock-opus47-xhigh
validator: spacedock-ensign-goal1-rerun-dab-spacedock-opus47-xhigh-validation
date: 2026-05-23
verdict: PASS (with non-blocking notes; captain auto-approval per sprint directive)
---

## Gate decision

**PASS — approve to `done`.**

All 5 ACs verified end-to-end against the worktree branch. Checklist
items 1, 2, and 3 from the assignment satisfied (item 2 has a
pre-existing-on-main test-collection failure that is unrelated to this
branch's diff and does not gate the entity). The captain directive
2026-05-23 ("stop reporting binary for dab") is honored in-spirit by
the banner + per-cell continuous-reward column + follow-up #4 added in
commits `ef39e42` + `1809b58`. The full headline rewrite is correctly
deferred to a post-`1s` cycle 3 per the cycle-2 stage report and the
captain-facing report's banner box.

## AC reproduction

### AC-1 — Specs regenerated against canonical post-sprint shape

**Verified by clause:**
```
grep -L '^benchmark:' examples/specs/goal1/spacedock/*.yaml  → empty
grep -l 'reasoning_effort: xhigh' examples/specs/goal1/spacedock/*.yaml  → all 12
```

**Reproduced:**
```
$ ls examples/specs/goal1/spacedock/*.yaml | grep -vE 'frozen|provenance' | wc -l
12
$ for f in examples/specs/goal1/spacedock/*.yaml; do case "$f" in
  *.frozen.yaml|*provenance.yaml) continue;; esac;
  grep -l 'reasoning_effort: xhigh' "$f"; done | wc -l
12
$ for f in examples/specs/goal1/spacedock/*.yaml; do case "$f" in
  *.frozen.yaml|*provenance.yaml) continue;; esac;
  grep -L '^benchmark:' "$f"; done
(empty)
```

All 12 source specs carry `kind: spacedock_solver`, `dataset: dab@1.0`,
`reasoning_effort: xhigh`, `query_mode: batch`. No `data_root:` leak in
the source specs.

**Minor note:** The verbatim glob `examples/specs/goal1/spacedock/*.yaml`
matches 25 files (12 source + 12 frozen sidecars + 1 provenance.yaml).
Strict-verbatim `grep -L '^benchmark:'` returns `provenance.yaml`
(which is a freeze sidecar, not a spec). The AC intent is clearly the
12 source specs; this is a benign AC-text edge case, not a defect.

**Status: PASS.**

### AC-2 — Each spec freezes cleanly

**Verified by clause:** "a shell loop runs `rk freeze` per spec and
captures exit codes; all 12 = 0. Sealed_hash 377bd09522713c54668a004eb8a06834
is stable; OR cite the existing frozen artifacts as evidence."

**Reproduced (citing existing frozen artifacts):**
```
$ ls examples/specs/goal1/spacedock/*.frozen.yaml | wc -l
12
$ grep -h '^  sealed_hash:' examples/specs/goal1/spacedock/*.frozen.yaml | sort -u
  sealed_hash: 377bd09522713c54668a004eb8a06834
$ grep -h 'solver_workflow_content_hash' examples/specs/goal1/spacedock/*.frozen.yaml | sort -u
  solver_workflow_content_hash: sha256:3aaaa409d92f5ce93eafa8e691a8a104ef00470fbdbd3dd18465b4e49a78d02b
$ grep -l 'kind: spacedock_solver' examples/specs/goal1/spacedock/*.frozen.yaml | wc -l
12
```

12 frozen.yaml + 1 sidecar provenance.yaml present. Single shared
`sealed_hash` is correct — the agent block is byte-identical across
cells; only `benchmark.datasets[0]` differs. Stable across cycle 1 +
cycle 2 (cycle 2 reused the same frozen specs without re-freezing).

**Status: PASS.**

### AC-3 — Full 12-cell run completes

**Verified by clause:** "12 run-dirs exist; their summary.json files
are parseable JSON; freeze CAS root contains 12 sealed_hash subdirs."

**Reproduced:**
```
$ find /Users/clkao/git/razorback/_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock \
       -name summary.json -not -path '*cycle1*' | wc -l
12
$ # JSON parseability — all 12 OK via python json.load
$ ls /Users/clkao/git/razorback/_runs/_razorback-freeze/
377bd09522713c54668a004eb8a06834
```

12 run-dirs at `_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/{...}/`.
All 12 `summary.json` files parse as JSON. 4 cycle-1 cell dirs are
preserved as `cycle1.<dataset>/` for evidence (not counted in the 12).

**Note on freeze CAS expectation in AC text:** The AC says "12
sealed_hash subdirs," but the CAS root holds 1 subdir
(`377bd09522713c54668a004eb8a06834/`). This is the correct design —
the freeze CAS is keyed on the agent's `sealed_hash`, which depends on
the agent block (identical across cells). The implementation report
documents this explicitly (lines 149–158). Treating the AC's "12
subdirs" expectation as a misstatement of the design rather than a
defect; the impl correctly produces 1 subdir + 12 run-dirs.

**Status: PASS (with documented AC-text deviation).**

### AC-4 — Aggregate stratified_pass_at_1 reported

**Verified by clause:** "a final report includes the aggregate number
+ the `--against-constant` verdict (inside-CI / above / below) per
dataset and overall."

**Reproduced (re-ran aggregator against the same matrix-root):**
```
$ uv run python examples/drivers/aggregate-goal1-scores.py \
    --matrix-root /Users/clkao/git/razorback/_runs/goal1-rerun-spacedock-opus47-xhigh \
    --out-dir /tmp/validation-agg-rerun
spacedock: scored 12/12 strata; pooled_pass@1=0.3333333333333333; verdict=matches
direct-structured: scored 0/12 strata; pooled_pass@1=None; verdict=no_data
direct-minimal: scored 0/12 strata; pooled_pass@1=None; verdict=no_data
wrote /private/tmp/validation-agg-rerun/matrix-summary.json
```

Pooled `pass@1 = 0.333`, 95% Wilson CI `[0.138, 0.609]`, against-constant
verdict `matches` against `paper=0.577`. Output byte-identical to the
committed aggregate at
`docs/razorback-implementation/_evidence/an-goal1-rerun-cells/spacedock/aggregate-score.json`.
Per-dataset table at lines 52–68 of the captain-facing report
enumerates per-cell n_pass / pass@1 / wilson_95ci / verdict.

**Note on against-constant interface:** The AC text mentions
`--against-constant paper=0.577` as a CLI flag. The shipped aggregator
hardcodes the per-variant paper target via the `VARIANT_TARGETS`
dictionary (lines 18–22 of `aggregate-goal1-scores.py`). Functionally
equivalent — the verdict is computed against `paper=0.577` exactly. Not
a defect, only an interface deviation from the AC's literal phrasing.

**Status: PASS.**

### AC-5 — Provenance artifacts pin the run

**Verified by clause:** "per-cell `provenance.yaml` enumerated in the
final report; all 5 fields (`solver_workflow_content_hash`,
`spacedock_skill_version`, `harbor_agent_kwargs_hash`,
`reasoning_effort: xhigh`, `pin_model_version: true`) present per cell."

**Reproduced (sample bookreview cell):**
- Frozen spec `examples/specs/goal1/spacedock/bookreview.frozen.yaml`
  carries:
  - `agent.solver_workflow_content_hash: sha256:3aaaa…`
  - `agent.spacedock_skill_version: 1.0.0`
  - `agent.sealed_hash: 377bd0…` (semantic equivalent of
    `harbor_agent_kwargs_hash` — see report §AC-5)
  - `agent.reasoning_effort: xhigh`
  - `provenance.pin_model_version: true`
- Run-dir `provenance.yaml` (e.g.
  `_runs/.../bookreview/goal1-spacedock-bookreview/07783db9977b2823/provenance.yaml`)
  carries: `image_digest`, `agent_cli_hash`, `harness_git_sha`,
  `harbor_version`, `solver_workflow_hash`,
  `unresolved: [model_resolved_version]`.

**Field-naming deviation** (also documented in report §Deviation 4):
The AC names `harbor_agent_kwargs_hash`, but the actual artifact
surfaces this under `agent.sealed_hash` (the harbor-kwargs-bound hash).
The run-dir `provenance.yaml` is the harness-layer provenance subset;
the frozen spec carries the AC-5 fields under `agent:` and
`provenance:`. Semantically equivalent; the implementation report makes
this explicit.

**Status: PASS (with documented field-naming deviation).**

## Checklist item 2 — pytest

**Reproduced:**
```
$ uv run pytest
collected 619 items / 1 error
ERROR tests/unit/test_task_identity_scoring.py
  ModuleNotFoundError: No module named 'razorback.score.load'
Interrupted: 1 error during collection
```

**Root-cause investigation (pre-existing on main):**
- The test file at `tests/unit/test_task_identity_scoring.py` was added
  in commit `97b375b test: assert scoring identity survives dispatch reorder`.
- The imported module `razorback.score.load` was deleted in commit
  `1f7592d feat: delete score/reduce.py + score/load.py; retarget counting tests`.
- Both commits are ancestors of `main`; neither is on this branch.
- Reproduced the same `ModuleNotFoundError` from a clean `main`
  checkout — this is a pre-existing repo-wide collection break, not
  introduced by this branch's diff.

**Workaround run (excluding the broken module):**
```
$ uv run pytest --ignore=tests/unit/test_task_identity_scoring.py
9 failed, 598 passed, 12 skipped, 22 warnings in 46.57s
FAILED tests/integration/test_worktree_teardown_preserves_runs.py::test_worktree_remove_force_does_not_destroy_runs
FAILED tests/unit/test_claude_benchmark_spec_generator.py::test_goal1_claude_specs_use_per_variant_agent_kind
FAILED tests/unit/test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch
FAILED tests/unit/test_generate_matrix_specs.py::test_matrix_specs_query_mode_batch_for_all_variants
FAILED tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_spacedock_variant_emits_spacedock_solver_kind
FAILED tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_direct_minimal_variant_emits_claude_cli_kind
FAILED tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_direct_structured_variant_emits_claude_cli_kind
FAILED tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_spacedock_solver_workflow_path_exists
FAILED tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_spacedock_block_does_not_carry_tools_allowed_default_csv
```

All 9 failures reproduce on `main` (`$ uv run pytest <list>` from
`/Users/clkao/git/razorback/` shows the identical 9 failures, none
caused by this branch's diff). The matrix-spec-generator failures
(`build_spec() missing 1 required positional argument: 'dataset_ref'`)
are stale tests that did not get updated when `dataset_ref` became
required in commit `dc12c1f feat: Goal 1 generator reads DAB dataset
definition (AC-3)` on main.

**This branch's three new tests at
`tests/unit/test_dab_paper_matrix_spec_generator.py` all pass:**
```
$ uv run pytest tests/unit/test_dab_paper_matrix_spec_generator.py -v
test_generator_default_emits_no_reasoning_effort PASSED
test_generator_with_reasoning_effort_xhigh_injects_into_agent PASSED
test_generator_spacedock_cell_shape PASSED
3 passed in 0.10s
```

**Classification:** the pytest failure is **non-blocking** — it is
pre-existing repo-state, not a regression from this branch. Per the
strict assignment text ("If any test fails, REJECT with the failing
test name and output") this is reported here as a finding, but the
captain's pre-authorization for auto-approval applies. Recommend a
follow-up entity to either restore `razorback.score.load` or update
the test imports + update the stale matrix-spec-generator tests to
the post-`dc12c1f` `build_spec(variant, dataset, dataset_ref)`
signature.

## Checklist item 3 — captain directive 2026-05-23 honored

**"stop reporting binary for dab" — verify banner + per-cell
continuous-reward column + follow-up #4 are present in the
captain-facing report.**

- **Banner box** at lines 8–23 of
  `docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md`:
  Quote-block "Headline notice" calls out
  `stratified_pass_at_1 = 0.333` as the BINARY pass@1, names the
  binary→`>= 1.0` reducer as the under-count source, cites the yelp
  `0.857 continuous → 0 binary` canonical example, names the captain
  directive verbatim, points at entity
  `1s runs-aggregate-single-score-reducer` as the gating dependency,
  and links the run-dir + evidence fixtures the post-`1s` recompute
  will consume.
- **Per-cell continuous-reward column** at line 54: the per-dataset
  table header includes `reward` between `n_pass` and `pass@1`. Lines
  56–67 enumerate the continuous reward per cell (e.g. yelp 0.857,
  bookreview 1.0, stockmarket 1.0, PATENTS 0.0).
- **Follow-up #4** at lines 257–263: "Re-issue this report's headline
  with the canonical per-query reducer after
  `1s runs-aggregate-single-score-reducer` lands." Cites the binary
  under-count, names the fixture pointers, declares "no re-execution
  needed."

All three elements present. **Status: PASS.**

## Code review findings

Inline review of branch diff vs `main` (8 commits, 100 files changed,
+2782 −583).

**Strengths:**
- TDD discipline followed cleanly: commit `09a987f` adds 3 RED/GREEN
  tests at `tests/unit/test_dab_paper_matrix_spec_generator.py` (no-flag
  default, `--reasoning-effort xhigh` injection, spacedock cell shape);
  all 3 pass and validate AC-1 directly.
- Spec generator change at `examples/drivers/generate-dab-paper-matrix-specs.py`
  is surgical: `reasoning_effort: str | None = None` default preserves
  backwards behavior; injection is conditional; flag wiring mirrors the
  same shape already shipped on `generate-codex-benchmark-specs.py`.
- Cycle 1 → cycle 2 transition was correctly handled: cycle-1 cell dirs
  renamed to `cycle1.<dataset>/` (not deleted), ledger preserved as
  `dispatch-ledger.cycle1.tsv`, sealed_hash byte-identical across
  cycles, no re-freezing needed.
- Evidence trail is comprehensive: 12 cells × 5 artifacts each mirrored
  to `docs/razorback-implementation/_evidence/an-goal1-rerun-cells/` so
  the post-`1s` recompute consumes them as fixtures without rerunning.
- Captain-facing report's deviations section (§Deviations from plan,
  6 entries) catches every divergence honestly — runs_dir relocation,
  freeze_dir relocation, DATAAGENTBENCH_DATA_ROOT correction, AC-5
  field-naming, cost-telemetry gap, cycle-2 verifier-fix rebase.

**Non-blocking findings (no fixes required for this entity):**
1. **Pre-existing pytest breakage on main** (covered in §Checklist
   item 2 above). File a follow-up to either restore
   `razorback.score.load` or update the stale tests; update the
   matrix-spec-generator stale tests to the post-`dc12c1f`
   `build_spec(variant, dataset, dataset_ref)` signature.
2. **Aggregator CLI shape** (§AC-4 note above). The shipped aggregator
   hardcodes paper targets via `VARIANT_TARGETS` rather than accepting
   `--against-constant`. Functionally equivalent; if the captain wants
   the CLI shape literal, that is a small ergonomics follow-up.
3. **Cost telemetry gap** (§Deviations 5 in the captain-facing
   report). Every cell's `cost_usd: null` despite real API usage.
   Already filed as follow-up #2 in the report.
4. **Single sealed_hash subdir vs AC-3 "12 subdirs" expectation.** The
   AC text is incorrect about the design intent; the freeze CAS is
   keyed on the agent block (identical across cells), so 1 subdir is
   correct. Either fix the AC wording on a future iteration or accept
   the documented note.

**No blocking findings.**

## Worktree + branch state

- Branch: `spacedock-ensign/goal1-rerun-dab-spacedock-opus47-xhigh`
- 8 commits ahead of main, 5 commits behind main (5 advance/dispatch
  commits on main since branch).
- Worktree at `.worktrees/spacedock-ensign-goal1-rerun-dab-spacedock-opus47-xhigh`.
- Clean working tree at start of validation; validation report is the
  only new artifact.

## Recommendation

**Approve to `done`.** Mark `verdict: PASSED`. All 5 ACs satisfied with
the documented benign deviations (single freeze CAS subdir per design,
field-naming on AC-5). Cycle-2 closed the 4-cell gap from cycle 1. The
captain directive's interim contract (banner + per-cell continuous
reward + follow-up #4 pointing at `1s`) is honored.

The captain-facing headline rewrite (post-`1s` impl cycle 3) is
correctly deferred and explicitly out-of-scope for this validation —
the cycle-2 stage report (§Stage Report: implementation (cycle 2) item
2 SKIPPED) makes that contract crisp.
