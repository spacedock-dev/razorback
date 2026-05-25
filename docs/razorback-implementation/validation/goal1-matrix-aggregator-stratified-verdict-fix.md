# Validation report — goal1 matrix aggregator stratified-verdict fix

- entity: `docs/razorback-implementation/goal1-matrix-aggregator-stratified-verdict-fix.md`
- branch: `spacedock-ensign/goal1-matrix-aggregator-stratified-verdict-fix`
- HEAD validated: `c0fa892` (4 commits ahead of `main` at `63623ee`)
- substantive commits reviewed: `b875da9` (T0 RED), `f554446` (T1 GREEN + T2 null-CI), `f106beb` (T3 reports amendment)
- captain `auto-approve: false` on this entity — gate decision requires captain ack regardless of sprint-wide auto-approval state

## AC-1 — Aggregator emits stratified-mean verdict against paper_baseline

**Verified by (per AC):**
- `grep -n "stratified_verdict\|per_query_pass_at_1_mean_over_strata" examples/drivers/aggregate-goal1-scores.py` shows the new field-building logic.
- Running `module.aggregate_variant(matrix_root, "direct-structured")` against a 7q-shape fixture produces `against_constant.stratified_verdict = {value: 0.4376, stratified_mean: 0.6719…, ci: null, verdict: "above"}`.
- The verdict is computed against `per_query_pass_at_1_mean_over_strata`, NOT against `pooled_per_query_pass_at_1`.

**Evidence run:**
- Grep output: `examples/drivers/aggregate-goal1-scores.py:188 def _verdict_point(...)`, `:208 # stratified_verdict.ci == null — verdict is a point comparison`, `:209 stratified_verdict_value = _verdict_point(per_query_mean_over_strata, target_value)`, `:228 "stratified_verdict": {`, `:232 "verdict": stratified_verdict_value`. Direct comparison helper is wired against the stratified mean; pooled CI is no longer the verdict source.
- `uv run pytest tests/unit/test_aggregate_goal1_stratified_verdict.py -v` on branch `c0fa892`: `2 passed in 0.67s`.
- RED reproduction on `main` aggregator: `git stash && git checkout main -- examples/drivers/aggregate-goal1-scores.py && uv run pytest tests/unit/test_aggregate_goal1_stratified_verdict.py -v` produces `KeyError: 'stratified_verdict'` at the first test's `sv = agg["against_constant"]["stratified_verdict"]` line — matches the RED commit message of `b875da9`. Worktree restored, no residual diff outside the pre-existing `uv.lock` modification.
- Source inspection at `examples/drivers/aggregate-goal1-scores.py:209` confirms the verdict is built from `per_query_mean_over_strata` (the local for `per_query_pass_at_1_mean_over_strata`, L156), not from `pooled_per_query_pass_at_1` (L221) or `pooled_per_query_ci` (L196's `_verdict(pooled_per_query_ci)` is now demoted to `per_query_verdict`).

**Verdict: PASS.**

## AC-2 — CI methodology for stratified mean documented + implemented

**Verified by (per AC):**
- Aggregator source carries a documented CI methodology choice (a) or (b) in a comment block above the `stratified_verdict` building.
- For choice (b): `stratified_verdict.ci` is null; verdict logic uses point comparison; no downstream significance claim is implied.

**Evidence run:**
- `examples/drivers/aggregate-goal1-scores.py:197-208` carries the docstring block: "Canonical paper-comparison lens. The DAB paper's `paper_baseline` is stratified-per-query…", "CI methodology: null. Mean-of-proportions across non-identical-N strata is not binomial; pick a stratified-CI methodology in a later entity if statistical-significance machinery is needed. Bootstrap over 12 cells at N=1 query trial per query is uninformative. Downstream consumers MUST NOT claim statistical significance from `stratified_verdict.ci == null` — verdict is a point comparison."
- `examples/drivers/aggregate-goal1-scores.py:188-193` defines `_verdict_point(mean, target)` returning "no_data"/"matches"/"above"/"below" by direct numeric comparison — no CI input, no bootstrap, no statistical claim.
- Emitted field at `:228-233`: `"stratified_verdict": {"value": target_value, "stratified_mean": per_query_mean_over_strata, "ci": None, "verdict": stratified_verdict_value}` — `ci` literally `None`.
- The aggregator imports `math` only (no `numpy`, no `scipy`, no `random`) — confirms no bootstrap dependency was introduced.
- Methodology rationale matches the captain's choice (b) per plan-stage Captain-decision gate and the implementation-stage stage report ("T2 CI methodology = (b) null-CI per captain decision … DO NOT implement bootstrap").

**Verdict: PASS.**

## AC-3 — Captain-facing reports for 7q + d8 carry amendment commit on main

**Verified by (per AC):**
- Both reports carry an `## Amendment 2026-MM-DD post-aggregator-fix` section near the top with the stratified-only headline + verdict.
- The aggregator-fix entity's archived stage report cites which evidence reports were amended + commit SHAs.

**Evidence run:**
- `docs/razorback-implementation/_evidence/goal1-direct-structured-v2/report.md:9` carries `## Amendment 2026-05-25 post-aggregator-fix`; body at L11-30 cites entity ID `docs/razorback-implementation/goal1-matrix-aggregator-stratified-verdict-fix.md` and branch `spacedock-ensign/goal1-matrix-aggregator-stratified-verdict-fix`; corrected headline `direct-structured stratified-per-query pass@1 = 0.6719 across 12 DAB datasets at N=1`; verdict `above` against `paper direct_baseline=0.4376` with explicit point-comparison framing and `CI null per stratified-mean-of-proportions not being binomial`. Forward-pointing correction explicitly noted.
- `docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md:8` carries `## Amendment 2026-05-25 post-aggregator-fix`; body at L10-34 cites the same entity ID; corrected headline `spacedock stratified-per-query pass@1 = 0.7055 across 12 DAB datasets`; verdict `above` against `paper spacedock=0.577` with point comparison + null CI rationale.
- d8 stratified mean independently recomputed from the 12 per-cell values cited in the amendment (`0.5, 1.0, 9/13, 0.5, 0.5, 0.75, 1.0, 2/3, 0.0, 1.0, 1.0, 6/7`): `python3 -c "vals=[…]; print(sum(vals)/len(vals))"` → `0.705509768009768`, matches the `0.7055` headline.
- Both amendment headlines follow the captain's 2026-05-25 stratified-only standing directive — no pooled-per-query lead, no binary lead.
- Implementation-stage stage report at the entity body cites commit `f106beb` as the amendment-bearing commit (entity body L237).
- `git log --oneline 47bbfab..HEAD` on the branch: 4 commits — `b875da9`, `f554446`, `f106beb`, `c0fa892` (the impl stage report commit). T3's amendment commit `f106beb` is present and named per the AC.

**Verdict: PASS.**

## AC-4 — Existing pytest stays green; backward compat preserved

**Verified by (per AC):**
- `uv run pytest tests/` exits 0 modulo pre-existing failures (5 known, byte-identical to baseline).
- `per_query_verdict` (pooled) and `verdict` (binary) fields remain emitted per their original logic.

**Evidence run:**
- `examples/drivers/aggregate-goal1-scores.py:236-237` still emit `"verdict": verdict` (from `_verdict(stratified_ci)` at L195, unchanged from main) and `"per_query_verdict": per_query_verdict` (from `_verdict(pooled_per_query_ci)` at L196, unchanged from main). Backward-compat assertion in `tests/unit/test_aggregate_goal1_stratified_verdict.py::test_stratified_verdict_backward_compat_fields_preserved` also asserts these fields plus that `per_query_verdict == "above"` for the 7q fixture.
- Full suite: `uv run pytest tests/ --ignore=tests/unit/test_task_identity_scoring.py --tb=no -q` → `5 failed, 707 passed, 12 skipped, 22 warnings in 38.19s`. Failing tests: `tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::{test_codex_runtime_dispatch_constructs_inner_agent,test_harbor_jobs_resume_round_trip_with_new_trial_name}`, `tests/integration/test_worktree_teardown_preserves_runs.py::test_worktree_remove_force_does_not_destroy_runs`, `tests/unit/test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch`, `tests/unit/test_rk_research_new.py::test_rk_research_new_creates_scaffold_tree`. `grep -l "stratified_verdict\|aggregate-goal1\|paper_baseline"` returns empty on all five files — none touch the aggregator surface; pre-existing on `main`.
- Collection-error file `tests/unit/test_task_identity_scoring.py` matches the impl-stage stage report's note ("has a pre-existing import error excluded from collection"). Excluded via `--ignore`, byte-identical to impl ensign's pytest invocation; full-set failure parity holds.
- Targeted aggregator-relevant suite (4 files cited in impl report) green: re-ran `tests/unit/test_aggregate_goal1_stratified_verdict.py` (2/2 passed); the existing `tests/unit/test_aggregate_goal1_from_definition.py` is included in the 707-passed total above.

**Verdict: PASS.**

## Code review findings

Reviewed the three substantive commits on branch `spacedock-ensign/goal1-matrix-aggregator-stratified-verdict-fix`:
- `b875da9` — T0 RED: adds `tests/unit/test_aggregate_goal1_stratified_verdict.py` (+112 lines).
- `f554446` — T1 GREEN + T2 docstring: edits `examples/drivers/aggregate-goal1-scores.py` (+26 lines).
- `f106beb` — T3 reports amendment: edits two archived evidence reports (+23 + +28 lines).

### Blocking — none

### Non-blocking

- **`_verdict_point` "matches" branch is effectively dead under float arithmetic.** Strict-equality on `mean == target` (line 191-192) rarely fires on a 12-cell mean of fractions vs a 4-decimal baseline. The "above"/"below" fallback is correct; the entity's plan body explicitly notes "this branch produces above/below only" — by design. No fix needed at this stage.
- **D8 amendment's 0.7055 is computed from the cycle-2 per-dataset table, not from a fresh aggregator re-run.** The amendment narrates this explicitly: archived `matrix-aggregate/aggregate-score.json` predates the new field, and the amendment is a forward-pointing correction (not a re-run) per the entity's research-integrity framing. The 12 per-cell values cited inside the amendment are sourced from the cycle-2 per-dataset table already in the same report — independently arithmetic-verified above (0.705509768…).
- **Docstring methodology rationale matches captain's choice (b)** verbatim: null CI, mean-of-proportions not binomial, bootstrap-uninformative-at-N=1, no statistical-significance claim from null CI. The wording at L197-208 mirrors the plan's T2-choice-b paragraph.
- **No new dependency introduced.** The aggregator imports only `math` (existing); no `numpy`, `scipy`, or `random` — consistent with the captain's "DO NOT implement bootstrap" instruction.
- **Backward-compat dict ordering is intentional.** `stratified_verdict` is placed first in the `against_constant` dict (line 228) to signal canonical lens; `name`/`value`/`verdict`/`per_query_verdict` follow. JSON consumers that key off field names are unaffected; consumers that rely on positional iteration would see the new field first, which is the intended signal.

### Reviewer assessment

The three commits implement the entity's plan to spec. The RED→GREEN transition reproduces under a fresh checkout. The captain's choice-(b) methodology is documented in source and propagated into both amendment reports. Backward-compat fields are preserved unchanged. Full pytest parity with the implementation-stage baseline holds (5 pre-existing failures, no aggregator-touching test regressed). Ready to advance.

## Gate decision: APPROVE

Per `auto-approve: false` on the entity frontmatter, the first officer MUST surface this gate to the captain for explicit ack before advancing to `done`. The validation evidence supports approval on all four ACs with no blocking findings.

- AC-1: PASS — `stratified_verdict` field emits with correct shape; verdict reads off the stratified mean, not pooled CI.
- AC-2: PASS — null-CI methodology documented in-source matching captain's choice (b); `_verdict_point` is point-comparison only; no bootstrap.
- AC-3: PASS — both archived captain-facing reports carry amendment blocks citing the right entity ID and emitting stratified-only headlines + verdicts; d8 arithmetic independently verified.
- AC-4: PASS — backward-compat fields emit; full pytest 707 passed / 12 skipped / 5 failed, byte-identical to impl baseline; the 5 failures are pre-existing on main and untouched by this branch.

Recommended next step on approve: archive the entity per the workflow's done-stage protocol (PR merge / archive move). Phase 5's hard-precondition reference to entity `08` is then satisfied and the phase5 impl ensign can resume.
