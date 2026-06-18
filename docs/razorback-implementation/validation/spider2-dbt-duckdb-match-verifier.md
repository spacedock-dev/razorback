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
