# Validation report — spider2-dbt duckdb_match verifier (cycles 1–10, final)

- Entity: `docs/razorback-implementation/spider2-dbt-duckdb-match-verifier.md`
- Branch: `spacedock-ensign/spider2-dbt-duckdb-match-verifier`
- Validated HEAD: `965f2ea` (includes cycles 1–10)
- Merge-base with `main`: `9c39af2`
- Method: independent validation of the current worktree HEAD — fresh suite
  runs from the clean branch checkout, standalone behavioral probes (not a
  re-read of prior reports), and `superpowers:requesting-code-review`.

## Acceptance criteria — PASS/FAIL with command + output

### AC-1 — comparator scores 1.0 on a matching DB, 0.0 on a mismatch — PASS

Verified by the comparator unit suite and a standalone live probe driving
`compare_duckdb` over in-test DuckDB fixtures.

```
$ uv run pytest -k spider2_dbt_verify --ignore=tests/unit/test_task_identity_scoring.py -q
49 passed, 795 deselected in 2.84s
```

Standalone probe drives `compare_duckdb` directly: matching DB → True,
mismatched DB → False; missing predicted table → False; multi-table AND with one
table mismatched → overall False. All PASS.

### AC-2 — column subsetting + ignore_orders honor duckdb_match semantics — PASS

Same probe, exercised live:

- `ignore_orders=True` over a row-reordered table → match (True); same data with
  `ignore_orders=False` → mismatch (False).
- A difference in a column NOT in `condition_cols` → still match (True); the same
  difference WITH that column in `condition_cols` → mismatch (False).
- Column-containment: pred columns reordered + an extra pred column → still match.
- `math.isclose(abs_tol=1e-2)`: within 1e-2 → match, beyond → mismatch.
- DECIMAL(10,3) within 1e-2 → match (cycle-9 `_normalize` Decimal→float).
- NULL==NULL → match (NA==NA).

All 11 probe cases PASS. Independently re-confirmed against the upstream
`xlang-ai/Spider2` `eval_utils.duckdb_match`/`compare_pandas_table` by the code
reviewer (fetched live during review) — line-accurate port, including the
`(x is None, str(x), isinstance(x,(int,float)))` sort key.

### AC-3 — emitted test.sh writes a Harbor-shaped reward.json — PASS

Verified by the integration suite and a standalone `emit_reward` probe:

- Matching pred/gold → reward.json parses to `{"reward": 1.0}`,
  `set(payload) == {"reward"}`, value is a `float`.
- Mismatch → `{"reward": 0.0}`.
- `emit_reward` never crashes-into-pass: garbage (non-JSON) spec over MATCHING
  DBs → `{"reward": 0.0}`; empty-`condition_tabs` wrapped spec over matching DBs
  → `{"reward": 0.0}` (the would-be-1.0 fail-open is closed); missing predicted
  DB → `{"reward": 0.0}`.

Integration test (`test_spider2_dbt_verify_test_sh.py`) executes the emitted
`test.sh` end-to-end and asserts the reward.json shape — green within the
`spider2_dbt_verify` 49-passed run above.

## Stage-checklist verification of the dispatch focus areas

- **Comparator faithfulness** — PASS. Column-containment, isclose 1e-2, per-column
  sort, condition_cols restriction, multi-table AND, missing-table → 0, NA==NA,
  DECIMAL within tolerance all confirmed live (probe) + reviewer's line-by-line
  oracle comparison.
- **duckdb-only dependency** — PASS.
  `grep -rn "import pandas\|from pandas\|import numpy\|from numpy"
  src/razorback/benchmarks/spider2_dbt/` → no matches. Only `duckdb` + stdlib are
  imported by the comparator/verifier.
- **Fail-closed guards** — PASS. Live probe: empty file, wrong `evaluation.func`,
  empty/missing `condition_tabs`, and a wrapped spec missing `parameters.gold`
  each RAISE; the gold-basename allowlist rejects all traversal/metachar cases
  (`../…`, `/etc/passwd`, `sub/dir/g.duckdb`, `..`, `.`, `x.duckdb; … #`,
  `g.duckdb $(id)`, `g .duckdb`, `g.sqlite`). Missing `tests/gold/` →
  `_ensure_verifier_assets` raises `FileNotFoundError`.
- **Shell/SQL injection sealed** — PASS. `harbor_view.py` `shlex.quote`s BOTH
  `--predicted-db` and `--gold-db` at the single emission point;
  `condition_tabs` is identifier-quoted (doubled `"`) in `_fetch_columns`, and a
  breakout value (`realt"; select 999 AS a; --`) over genuinely-mismatched DBs
  RAISES (cannot force a match) — confirmed live.
- **Link-mode symlink-write-through** — PASS. All 5 verifier-asset copies route
  through `_copy_into_view` (unlink-symlink-then-copy); test.sh, Dockerfile, and
  preflight writes carry the same guard. Regression
  `..._never_mutate_colliding_source_file` is green.
- **AC-3 reward.json shape / never-crash-into-pass** — PASS (see AC-3).

## Suite results (clean branch checkout)

```
$ uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py -q
93 passed, 751 deselected in 5.34s

$ uv run pytest --ignore=tests/unit/test_task_identity_scoring.py -q
4 failed, 828 passed, 12 skipped, 80 warnings in 68.05s
```

The 4 full-suite failures are pre-existing on the merge-base `9c39af2`
(verified by running exactly those 4 node-ids in a throwaway base worktree →
`4 failed`) and live in files UNTOUCHED by this branch
(`git diff 9c39af2..HEAD --name-only` is spider2_dbt scope + docs only).
NOT regressions:

- `test_spacedock_solver_freeze_dir_mechanism.py::test_codex_runtime_dispatch_constructs_inner_agent`
- `test_worktree_teardown_preserves_runs.py::test_worktree_remove_force_does_not_destroy_runs`
- `test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch`
- `test_rk_research_new.py::test_rk_research_new_creates_scaffold_tree`

## Code review findings (superpowers:requesting-code-review)

Reviewer dispatched against `9c39af2..965f2ea`; it independently fetched the
upstream Spider2 oracle and ran the suite.

- **Critical:** none. The reviewer could not construct any external input
  (eval-spec JSON, gold basename, condition_tabs, task profile) that forces a
  false reward 1.0.
- **Important:** none.
- **Minor (non-blocking):**
  1. `eval_spec.py:73` — `condition_cols` `[[]]`/`[None]` is expanded to
     `[[]]*n` for any `n`; this is the *forgiving* direction and mirrors
     upstream `compare_multi_pandas_table` defaulting (stricter `duckdb_match`
     would assert). No correctness risk for well-formed specs; a clarifying
     comment was suggested.
  2. The leakage-scan scoping that excludes the verify-only `tests/` subtree
     rests on the Harbor "tests/ uploaded only at verify time, reset around the
     agent run" lifecycle; a version-pinned comment was suggested so a future
     Harbor bump can't silently invalidate it. The guard test proves the change
     is scoping not weakening.
  3. `harbor_view.py:163` `spec.gold or "gold.duckdb"` fallback is effectively
     dead for wrapped specs (they already raise without gold); reachable only
     for the unwrapped-fixture path. A clarifying comment was suggested.

All three are clarity/robustness polish, not correctness defects — classified
non-blocking. No production code was changed during validation.

## Gate decision

**PASSED → done.**

Rationale: all three ACs reproduce green from a clean checkout with actual
command output (gating suite 93 passed; acceptance `-k spider2_dbt_verify` 49
passed), every dispatch-named focus area is confirmed by live behavioral probes
(comparator faithfulness, duckdb-only, fail-closed guards, shell+SQL injection
sealed, symlink write-through, reward.json shape), the only full-suite failures
are pre-existing on the merge-base and outside this branch's scope, and the
independent code review found zero blocking issues (3 minor polish notes). No
external input forces a false reward 1.0.
