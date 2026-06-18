# Validation: spider2-dbt — duckdb_match verifier emitting binary reward.json

**Branch:** `spacedock-ensign/spider2-dbt-duckdb-match-verifier` @ `7ab0bf7`
**Merge-base with main:** `9c39af2`
**Gate verdict:** **REJECTED → implementation**

Two blocking findings: (B1) a branch-induced regression in the spider2
production translate leakage suite, and (B2) the `duckdb_match`
reproduction is **not faithful** to Spider2's `eval_utils.duckdb_match`
semantics (verdict-flipping divergences, plus an incompatible eval-spec
schema). The 3 ACs as literally written all reproduce green, but a
verifier whose comparator disagrees with the benchmark's own oracle and
whose change breaks the shipping leakage suite must not advance.

---

## Acceptance command (gating)

`uv run pytest -k spider2_dbt_verify --ignore=tests/unit/test_task_identity_scoring.py`
→ **18 passed, 793 deselected** (clean checkout of the branch HEAD).

## AC reproduction (independent, not trusting the in-repo tests)

Driven via a standalone script against the `compare_duckdb` comparator
and the materializer, from a clean worktree.

- **AC-1 — 1.0 on match / 0.0 on mismatch:** PASS.
  `compare_duckdb` on a matching DB → `True`; on a differing
  condition-col value → `False`. Missing predicted table → `False`.
- **AC-2 — column subset + ignore_orders:** PASS *(as literally
  specified)*.
  (a) Row-reordered table + `ignore_orders=True` → `True`; same with
  `ignore_orders=False` → `False`. (b) A diff in a NON-condition column
  (excluded from `condition_cols`) → `True`; the same diff with the
  column included → `False`.
- **AC-3 — emitted test.sh writes harbor-shaped reward.json:** PASS.
  Materialized the view, then **actually executed the emitted
  `test.sh`** (container paths `/tests`,`/app/<db>`,`/logs/verifier`
  substituted to temp dirs): exit 0, wrote
  `/logs/verifier/reward.json` = `{"reward": 0.0}` on a mismatch and
  `{"reward": 1.0}` on a match. `set(payload) == {"reward"}`,
  `isinstance(payload["reward"], float)`.
  Note: the in-repo integration test invokes `verify.py` directly and
  only `sh -n` syntax-checks `test.sh`; I additionally ran the script
  itself to satisfy AC-3's "running the emitted test.sh" clause.

## Mandatory rider (resolver-driven predicted-db path)

**CONFIRMED.** Materialized with `task_slug="not-spider2-slug"` (fixture
ships no profiles.yml / *.duckdb → resolver slug fallback). Emitted
`test.sh` `--predicted-db` = `/app/not-spider2-slug.duckdb`;
`/app/spider2.duckdb` absent. The path flows from ny's
`resolve_spider2_db_name` (imported from `preflight.py`, unchanged on
this branch), satisfying the SHARED `/app/<db_name>.duckdb` contract for
a NON-`spider2` slug.

## Verifier-only gold assets / leakage (path-based)

Gold `.duckdb` + `spider2_eval.jsonl` + the 3 comparator modules +
`test.sh` land in the view's `tests/` (uploaded to the container only at
verify time). No `gold/` path SEGMENT survives in the materialized view
(`rglob("gold")` dirs = none; the empty `gold/` dir left by the
deny-glob file-strip is pruned). The path-based deny-glob isolation is
sound — but see B1: the assets still trip the production-path *content*
leakage scanner.

---

## BLOCKING findings

### B1 — Regression in the spider2 translate leakage suite

`tests/unit/test_translate_spider2_dbt.py` has TWO tests that **pass on
`9c39af2` (base) and FAIL on `7ab0bf7` (this branch)** — verified by
running them in a base worktree (2 passed) and on the branch (2 failed):

- `test_spider2_resolves_n_views_all_leakage_clean`
- `test_planted_forbidden_files_are_excluded_from_view`

The test file is **unchanged** by this branch (`git diff base..HEAD --
test_translate_spider2_dbt.py` empty), so this is a behavior regression,
not a test edit. Root cause: these tests drive the production path
`spec_to_job_config → materialize_spider2_harbor_task_view`, and this
branch's new `_ensure_verifier_assets` writes `duckdb_match.py`,
`eval_spec.py`, `verify.py`, `gold.duckdb`, and `test.sh` into the view's
`tests/`. The suite's `_leakage_hits` scans file NAME **and CONTENT** for
the alternation `gold|expected|golden`; the assets contain "gold"
(`gold.duckdb` filename; `--gold-db`/`gold_db`/`gold_rows`/docstrings
inside the .py and test.sh — confirmed: duckdb_match.py has 9 hits,
verify.py 5, eval_spec.py 4). All 5 assets are flagged as leakage.

This is exactly the "no regression to ny's generic behavior" guard the
entity required. The gating `-k spider2_dbt_verify` selector does NOT
match `test_translate_spider2_dbt`, which is why the implementer's green
run missed it.

**Fix direction (for implementation):** reconcile the two leakage
notions. Either (a) make `_ensure_verifier_assets` write the verifier
modules under a name/location the content+name scanner treats as
verifier-internal (the scanner already exempts `view_manifest.json` —
an analogous exemption for the verifier `tests/` payload is the natural
move), or (b) update the shipping leakage contract/test to recognize the
verifier `tests/` payload as verifier-only (uploaded at verify time, not
agent-visible) rather than answer leakage. Coordinate with whoever owns
`test_translate_spider2_dbt.py`'s `_leakage_hits` contract; do not
silently weaken the scan.

### B2 — `duckdb_match` reproduction is NOT faithful to Spider2 eval_utils

The canonical oracle is `spider2-dbt/evaluation_suite/eval_utils.py`
`duckdb_match` (fetched from xlang-ai/Spider2 main). The reproduction
diverges in ways that **flip the reward** versus the real benchmark, so a
model scored by this verifier would be graded differently than by
Spider2's own scorer:

1. **Comparison axis — column-containment vs row-tuple.** Spider2
   transposes both tables and checks *each gold column-vector matches
   SOME pred column-vector* (`for gcol in t_gold: any(vectors_match(gcol,
   pcol) for pcol in t_pred)`). The impl compares **row tuples
   positionally** after `SELECT *`. Demonstrated divergences (Spider2 →
   1, impl → 0): pred with **reordered columns**; pred with an **extra
   column** beyond the gold/condition set.
2. **Float tolerance.** Spider2 uses `math.isclose(abs_tol=1e-2)` (and
   NaN-equality). The impl uses exact `==` on raw tuples. Gold 1.000 vs
   pred 1.005 → Spider2 1, impl 0.
3. **`ignore_orders` granularity.** Spider2 sorts **each column-vector
   independently**; the impl sorts **row-tuples as units**. These are not
   the same multiset relation — Spider2 can match a table whose
   cross-column row association is scrambled; the impl cannot.
4. **Eval-spec schema is incompatible.** Real `spider2_eval.jsonl` lines
   are `{"instance_id":..., "evaluation":{"func":"duckdb_match",
   "parameters":{"gold":..., "condition_tabs":[...],
   "condition_cols":[[...],...], "ignore_orders":[bool,...]}}}` —
   `condition_cols` is `List[List[int]]` (positional, parallel to
   `condition_tabs`) and `ignore_orders` is `List[bool]` (per-table),
   nested under `evaluation.parameters`. The impl's `EvalSpec` /
   `load_eval_spec` model `condition_cols: dict[str,list[int]]` and a
   single `ignore_orders: bool`, read flat from the top level. The impl's
   loader would **not parse a real Spider2 gold line** — it would silently
   produce empty `condition_tabs` (`raw.get("condition_tabs", [])`) and
   score every prediction 1.0 (vacuous AND over zero tables).

The entity body asserts (verbatim) "per-table SELECT *, 0-based
condition_cols subset, ignore_orders multiset, AND across condition_tabs,
missing table = mismatch" — that description matches the IMPL but **not
Spider2's actual `compare_pandas_table`**, which is column-containment +
float-tolerant + per-column sort. The plan/AC contract treated a
row-tuple multiset model as the target; the real oracle is materially
different. This is the faithfulness check the rider demanded, and it
fails.

**Fix direction (for implementation):** port `compare_pandas_table`
(transpose + per-column vectors_match with `abs_tol=1e-2` + per-column
ordered/sorted compare + gold-column-containment) rather than a row-tuple
compare; adopt the real `List[List[int]]` / `List[bool]` /
`evaluation.parameters` spec schema (or document an explicit, approved
deviation if the dbt track intentionally tightens the oracle — but that
needs a captain decision, not a silent reinterpretation). Update the gold
fixture + AC-2 wording to the column-containment semantics.

## Two pre-flagged deviations — explicit verdict each

1. **Rider override of the plan's hardcoded `/app/spider2.duckdb`
   test.sh path → resolver-driven `/app/<db_name>.duckdb`:**
   **ACCEPTED / CORRECT.** This is exactly what the rider mandated;
   proven for a non-spider2 slug above. Not a blocker.
2. **Pruning the empty `gold/` dir left after deny-glob file-stripping:**
   **ACCEPTED.** Narrow, targeted (`rglob("gold")` dirs, only removed
   when `not any(iterdir())`), keeps the path-segment leakage assertion
   exact, and does not touch non-empty dirs. Not a blocker. (Note: it
   does not address B1, which is about file CONTENT, not the `gold/`
   directory segment.)

## Regression scope (full suite, minus known-broken file)

`uv run pytest --ignore=tests/unit/test_task_identity_scoring.py` →
**6 failed, 793 passed, 12 skipped**.
- 4 failures (`test_spacedock_solver_freeze_dir_mechanism`,
  `test_worktree_teardown_preserves_runs`,
  `test_generate_matrix_specs`, `test_rk_research_new`) **also fail on
  base `9c39af2`** → pre-existing, unrelated, NOT regressions.
- 2 failures (`test_translate_spider2_dbt.py`, both) → **branch-induced
  regression** (B1).
- `test_task_identity_scoring.py` ignored per the assignment
  (pre-existing `razorback.score.load` import break).
- harbor_view + preflight suites (`-k "harbor_view or preflight"`):
  **45 passed** — no regression there.

## Code review

The stage asks for `superpowers:requesting-code-review`. The substantive
findings it would surface are captured above (B1 regression, B2
faithfulness + schema). No additional blocking correctness issues found
in `verify.py` / `eval_spec.py` / the materializer beyond B1/B2; the
flat-import fallbacks, fail-closed `predicted_db` existence check, and
harbor reward shape are sound.

## Gate decision

**REJECTED → implementation.** Fix B1 (restore the spider2 translate
leakage suite to green without weakening the leakage contract) and B2
(make `duckdb_match` faithful to Spider2 `eval_utils.duckdb_match`, or
get an explicit captain-approved deviation, AND adopt the real
`spider2_eval.jsonl` schema so the loader parses real gold lines). The 3
ACs as written pass and the rider is satisfied, but those ACs encode the
wrong oracle semantics — re-derive AC-2 against column-containment when
re-entering implementation.

---

# Re-review (cycle 2): validation gate

**Branch:** `spacedock-ensign/spider2-dbt-duckdb-match-verifier` @ `f878967`
**Merge-base with main:** `9c39af2`
**Gate verdict:** **PASSED → done**

Independent re-verification of the two cycle-1 blocking findings after the
fix commits `61a1b9c` (B2) and `22b9b6c` (B1). The authoritative
xlang-ai/Spider2 `spider2-dbt/evaluation_suite/eval_utils.py` was fetched
live via `gh api` (387 lines, decoded to `/tmp`); the impl was checked
line-by-line against it and differential-tested against an inline
transcription of that source. Both findings are resolved; no new
regressions; rider + AC-3 intact.

## B2 — comparator faithfulness to Spider2 `eval_utils.duckdb_match`: CONFIRMED

`src/razorback/benchmarks/spider2_dbt/duckdb_match.py` is a faithful port of
Spider2 `duckdb_match` + `compare_pandas_table` + `vectors_match`:

- **Column-containment** (not row-tuple equality): gold restricted to
  `condition_cols` via `iloc[:, ...]`, pred uses all columns, both
  transposed to column-vectors, each gold column must match SOME pred
  column — matches Spider2 `eval_utils.py:132-149`. (impl drops Spider2's
  dead `else` loop at 145-148; no behavioral effect.)
- **Per-column sort under `ignore_order`** with Spider2's exact sort key
  `(x is None, str(x), isinstance(x,(int,float)))` — matches 115-117.
- **Numeric `math.isclose(abs_tol=1e-2)`** — matches 124.
- **NaN: `pd.isna(a) and pd.isna(b)` → equal** — matches 121.
- **AND across `condition_tabs`**, **predicted-fetch failure = mismatch**
  (try/except → False) — matches 221-243.

Differential test (impl vs an inline transcription of the upstream oracle)
on 10 verdict-flipping cases — float within/beyond 1e-2, row reorder
with/without ignore_order, extra pred columns, diff in non-condition col,
NaN, missing pred table, multi-table 1-mismatch, multi-table all-match —
**all 10 agree and match the expected verdict**.

`load_eval_spec` drilled into the REAL `playbook001`/`provider001` gold
lines fetched from upstream `gold/spider2_eval.jsonl`: parses
`evaluation.parameters` with per-table `condition_tabs: List[str]`,
`condition_cols: List[List[int]]` (`[[0,1],[0,1,2,5,6,7,9,10,11,12,13]]`),
`ignore_orders: List[bool]` (`[True,True]`) — matches `evaluate.py:96-99`
(`duckdb_match(result, **parameters)`). All 68 real duckdb_match gold lines
carry explicit tabs/cols/orders, so the impl's explicit-`condition_tabs`
requirement (no None→all-tables default) is never exercised on real data.

Minor non-blocking note: impl uses `SELECT * FROM "{table}"` (quoted) vs
Spider2's unquoted `{table_name}` — a robustness improvement, not a
faithfulness divergence.

## B1 — leakage scoping sound, protection not weakened: CONFIRMED

`_leakage_hits` (in `tests/unit/test_translate_spider2_dbt.py`) now excludes
the verify-time-only `tests/` subtree via `_is_verifier_only`. Verified the
Harbor lifecycle claim against the installed package source:

- `harbor/verifier/verifier.py:123 def verify()` → lines 133-138 upload
  the task's `tests/` to `env_paths.tests_dir` ONLY inside `verify()`.
- `harbor/trial/trial.py:570 _verify_step` → line 587-591
  `reset_dirs(remove_dirs=[verifier_dir, tests_dir], create_dirs=[...])`
  wipes+recreates them EMPTY immediately before verification.
- The agent step receives only `_upload_step_workdir` (`workdir/`), never
  the host view's `tests/`. So the host `tests/` assets genuinely never
  reach the agent — excluding them from the host scan is principled.

Scoping ≠ weakening, proven two ways: (1) the shipped guard test
`test_leakage_scan_still_fires_on_agent_visible_answer_content` plants
`gold`-content in BOTH an agent-visible path (caught) and `tests/`
(ignored); (2) a mutation probe — forcing `_is_verifier_only` to blanket-
`True` — makes that guard FAIL on the agent-visible leak, confirming the
guard is meaningful. Production deny-globs (`gold/**`, `**/gold/**`,
`expected/**`, `golden/**`) — the real agent-view protection — are
UNCHANGED; only the test's scan scope moved.

The 2 previously-failing `test_translate_spider2_dbt.py` tests are green:
full file = 13 passed.

## Regression / rider / AC-3

- Acceptance/gating: `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` → **66 passed**.
- Rider (independent end-to-end): materialized a view with `task_slug=not-spider2-slug`; emitted `tests/test.sh` resolves `--predicted-db /app/not-spider2-slug.duckdb` (ny's `resolve_spider2_db_name`), no hardcoded `/app/spider2.duckdb`.
- AC-3 (independent end-to-end): ran the emitted `verify.py` against the gold fixture → `/logs/verifier/reward.json` = `{"reward": 1.0}` (match) and `{"reward": 0.0}` (missing pred); reward is a float.
- Branch touches only `spider2_dbt`-scoped modules/tests + the gold fixture. None of the 3 known pre-existing failures (`test_task_identity_scoring`, `test_generate_matrix_specs`, `test_rk_research_new`) are touched by this branch — not regressions. Ignored harness `uv.lock` churn.

## Gate decision

**PASSED → done.** Both cycle-1 blocking findings are independently
resolved against the live Spider2 source: B2 — the comparator and eval-spec
schema faithfully reproduce `eval_utils.duckdb_match` (verified by a 10-case
differential test against the upstream oracle and a real multi-table gold
line); B1 — the leakage fix is scoping, not weakening (mutation-probed),
justified by the verified Harbor verify-only-tests/ lifecycle. Rider and
AC-3 reward.json shape intact; no regressions outside the known pre-existing
set. No blocking findings remain.

---

# Re-review (cycle 3): validation gate — fail-closed fix

**Branch:** `spacedock-ensign/spider2-dbt-duckdb-match-verifier` @ `11c66f4`
**Merge-base with main:** `9c39af2`
**Fix commit under review:** `869918d` (fail-closed eval-spec validation)
**Gate verdict:** **PASSED → done**

Independent re-verification of the cycle-2 fail-open hazard fix (Codex
finding: empty/malformed eval spec awarded `{"reward": 1.0}`). No
production code written.

## Fail-closed fix is real and load-bearing: CONFIRMED

`load_eval_spec` / `EvalSpec.__post_init__` (`eval_spec.py`) now fail closed,
and `emit_reward` (`verify.py:33-42`) wraps spec-load + compare in
`try/except → reward 0`. Independent probe at clean branch HEAD:

- **RAISE cases** (all `ValueError`): empty file; `evaluation.parameters`
  with no `condition_tabs`; explicit empty `condition_tabs`; non-`duckdb_match`
  `evaluation.func` (`string_match`); direct `EvalSpec(condition_tabs=[])`.
- **Hazard-beating** — over a MATCHING pred/gold pair (cloned tables):
  an empty/zero-table spec → `{"reward": 0.0}` and a wrong-func spec →
  `{"reward": 0.0}` — **not the prior 1.0**. Garbage non-JSON → `0.0` with
  no exception (no crash-into-pass).
- **Positive control:** a VALID matching spec still → `{"reward": 1.0}`,
  so the guards are targeted, not blanket-failing.

**Mutation test (guards are load-bearing):** stripping the `n==0` guard,
the empty-file raise, and the wrong-func raise from `eval_spec.py` made all
6 negative tests FAIL — and the CLI negative reproduced the exact
`{'reward': 1.0}` == `{'reward': 0.0}` assertion failure, i.e. the original
hazard returned. Tree restored to clean (`git diff` on `eval_spec.py` empty).

Root-cause confirmed in source: `compare_duckdb` (`duckdb_match.py:116`)
returns `True` after the per-table AND-loop, so a zero-`condition_tabs` spec
would vacuously match — the guards prevent that spec from ever being built.

## Cycle-1 fixes intact (B2 comparator + B1 leakage): CONFIRMED

`git diff 0b64e92..869918d --name-only` (the cycle-2 fix delta) touches ONLY
`eval_spec.py`, `verify.py`, `test_spider2_dbt_verify_cli.py`,
`test_spider2_dbt_verify_comparator.py`. `duckdb_match.py` (B2),
`harbor_view.py` + `test_translate_spider2_dbt.py` (B1) are **untouched** —
cycle-1 is intact by construction, and re-confirmed live:

- **B2 faithfulness:** column-containment with reordered + extra pred
  columns → True; `math.isclose(1e-2)` within → True / beyond → False;
  per-column sort under `ignore_order` → True; ordered mismatch → False;
  missing pred table → False (mismatch).
- **B1 leakage scoping:** `test_translate_spider2_dbt.py` leakage/planted/
  resolves tests → 3 passed; the `leakage_scan_still_fires_on_agent_visible`
  guard among 9 rider/AC-3/leakage tests → 9 passed (agent-visible leaks
  still caught; only verify-only `tests/` excluded).

## Regression / rider / AC-3

- **Gating:** `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py`
  → **73 passed, 751 deselected** (was 66 in cycle 2; +7 negatives).
- **Rider:** materialized view with `task_slug=not-spider2-slug` → emitted
  `test.sh` `--predicted-db /app/not-spider2-slug.duckdb`; `/app/spider2.duckdb`
  absent (ny's `resolve_spider2_db_name`).
- **AC-3:** independent end-to-end via `emit_reward` against the materialized
  gold fixture — matching pred → `{"reward": 1.0}`, mismatch → `{"reward": 0.0}`;
  `set(payload) == {"reward"}`, reward is `float`.
- Working tree clean apart from the known harness `uv.lock` churn (ignored
  per assignment). Pre-existing unrelated failures on base
  (`test_task_identity_scoring`, `test_generate_matrix_specs`,
  `test_rk_research_new`, etc.) are not regressions and not touched.

## Gate decision

**PASSED → done.** The cycle-2 fail-open hazard is independently closed:
empty/malformed/schema-drifted specs raise or score 0, the matching-pair
hazard now yields 0 not 1.0, and a mutation test proves the guards (and their
negative tests) are load-bearing. Cycle-1 comparator faithfulness and leakage
scoping are intact (untouched by the fix + re-confirmed live); rider and AC-3
reward shape intact; no new regressions. Per the convergence plan this was the
last re-validation before PR.
