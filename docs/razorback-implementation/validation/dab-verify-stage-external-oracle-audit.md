# Validation: dab-verify-stage-external-oracle-audit (wp, cycle-2)

- Entity: `docs/razorback-implementation/dab-verify-stage-external-oracle-audit.md`
- Branch: `spacedock-ensign/dab-verify-stage-external-oracle-audit`
- Base (merge-base with main): `2abdd05`
- Head: `d9326f1`
- Validator: spacedock-ensign-dab-verify-stage-external-oracle-audit-validation
- Date: 2026-05-23

## Per-AC verdict

### AC-1 — Solver workflow README carries the External-oracle audit block (PASS)

Verified by grep against `examples/solver_workflows/dab_paper_matrix/README.md`:

      $ grep -nF 'External-oracle audit' examples/solver_workflows/dab_paper_matrix/README.md
      35:### External-oracle audit
      $ grep -nF 'datasets.load_dataset' examples/solver_workflows/dab_paper_matrix/README.md
      44:- `datasets.load_dataset` (or the bare `load_dataset(...)` after a
      $ grep -nF 'huggingface' examples/solver_workflows/dab_paper_matrix/README.md
      43:- `huggingface` (the host or the python library)
      51:  `datasets`, `huggingface_hub`, `transformers`, `evaluate`
      54:- `huggingface-cli` or `hf` binary invocations
      $ grep -nF 'hf://' examples/solver_workflows/dab_paper_matrix/README.md
      46:- `hf://` URI references
      $ grep -nF 'from datasets import' examples/solver_workflows/dab_paper_matrix/README.md
      45:  `from datasets import load_dataset`)
      47:- `from datasets import` Python imports (the import-layer attack the
      $ grep -nF 'requests.get' examples/solver_workflows/dab_paper_matrix/README.md
      49:- `requests.get` / `curl` / `wget` to public data hosts
      $ grep -nE 'WebSearch|WebFetch|web-search' examples/solver_workflows/dab_paper_matrix/README.md
      55:- web-search tool invocations (`WebSearch`, `WebFetch`,
      $ grep -nF -- '--policy strict' examples/solver_workflows/dab_paper_matrix/README.md
      59:The audit is mechanized by `rk audit --policy strict`, which delegates
      65:    uv run rk audit <cell-run-dir> --policy strict --format json

All upstream forbidden patterns present + the CLI reference to `rk audit --policy strict`.

### AC-2 — `rk audit` helper exists, mechanizes the verify-stage check (PASS via cycle-2 SUPERSEDED contract)

Entity body documents the SUPERSEDED status: cycle-1's standalone module
was replaced by extending `audit/taint.py` + adding `audit/claude_code.py`.
The captain-facing CLI is now `rk audit <cell-run-dir> --policy strict`
with exit 0 / 23 / other-non-zero. Live verification:

      $ uv run rk audit \
            .worktrees/spacedock-ensign-goal1-direct-structured-dab-opus47-xhigh/_runs/.../agnews/.../2fa90bb140485d77 \
            --policy strict --format json
      exit=23
      summary: { clean: 0, tainted: 1, coverage_missing: 0 }
      first finding: source_kind=claude_code_trace, line=26, pattern="from datasets import",
                     scanned_field=command.python, event_id=toolu_01PoLakXsdsXDY6GEHNS1FWe

      $ uv run rk audit \
            .worktrees/spacedock-ensign-goal1-direct-structured-dab-opus47-xhigh/_runs/.../music_brainz_20k/.../6b369cb7e9482e12 \
            --policy strict --format json
      exit=0
      summary: { clean: 1, tainted: 0, coverage_missing: 0 }

(Full JSON captured at `/tmp/wp-validation-agnews-audit.json` and
`/tmp/wp-validation-mbr-audit.json` on the validator host.)

### AC-3 — Solver workflow prose references the helper (PASS)

`examples/solver_workflows/dab_paper_matrix/README.md` lines 59-77 name
`rk audit --policy strict` + the 0 / 23 / other-non-zero exit-code semantic
and tie REJECT to exit 23. Synthetic-cell behavior asserted by
`tests/integration/test_dab_paper_matrix_external_oracle_gate.py::test_rk_audit_strict_rejects_synthetic_cheating_cell`
(exit 23) and `…test_rk_audit_strict_passes_synthetic_clean_cell` (exit 0),
both PASS.

### AC-4 — Per-cell post-run hook automation, NOT variant-gated (PASS)

`examples/drivers/dab-paper-matrix.sh` lines 186-219 invoke
`rk audit --policy strict` between `rk run` and `rk score`, with no
variant guard around the audit. Exit-23 → ledger
`status=external-oracle-cheating` + decrement `ok_cells` + increment
`failed_cells` + append to `FAILURES_LOG` + `continue` (skip scoring).
Other non-zero → `external-oracle-audit-error` with the same rollback.

Integration tests (5/5 PASS):

      tests/integration/test_dab_paper_matrix_external_oracle_gate.py
        test_driver_invokes_rk_audit_strict_after_rk_run
        test_driver_maps_audit_exit_23_to_external_oracle_cheating
        test_driver_failing_audit_appends_to_failures_log
        test_rk_audit_strict_rejects_synthetic_cheating_cell
        test_rk_audit_strict_passes_synthetic_clean_cell

### AC-5 — Unit tests cover claude-cli adapter + rebalanced PyPI regex + ≥4 fixture variants (PASS)

`tests/unit/audit/test_claude_code_adapter.py` (11 tests, all PASS) covers
the four required variant classes:

- load_dataset (python heredoc): `test_load_dataset_python_heredoc_flagged`
- clean Bash: `test_clean_bash_passes`
- requests.get / curl to public host: `test_curl_to_huggingface_flagged`
- python-import (`from datasets import`): `test_rk_audit_strict_taints_claude_code_load_dataset`
- captain-principle generic-lib CLEAN: `test_pip_install_generic_lib_stays_clean`
- named-lib pip flagged: `test_pip_install_named_lib_flagged`
- WebSearch tool_use flagged: `test_websearch_tool_use_flagged`
- tool_result echo defense: `test_tool_result_echo_not_flagged`
- missing trace empty: `test_missing_claude_code_txt_returns_empty`
- discover_trial_roots: `test_discover_trial_roots_finds_claude_code_txt`
- rk audit strict CLEAN end-to-end: `test_rk_audit_strict_treats_pip_install_rapidfuzz_as_clean`

`tests/unit/audit/test_taint_keep_verbatim.py` adds the captain-principle
regression-guard tests (all PASS): `test_shell_pip_install_generic_lib_stays_clean`,
`test_shell_pip_install_each_named_lib_taints_attempt`,
`test_shell_pip_install_named_lib_with_version_pin_taints_attempt`,
`test_shell_huggingface_cli_taints_attempt`. Combined audit-test run:

      uv run pytest tests/unit/audit/ tests/integration/test_dab_paper_matrix_external_oracle_gate.py -v
      → 51 passed in 1.10s

## Silent-blindness fix end-to-end verification (assignment §2)

The contract-changing diff is `audit/taint.py` + new `audit/claude_code.py`.
Before the fix, `rk audit` against any claude-cli trace silently returned
CLEAN regardless of contents. Reproduced empirically against real 7q
direct-structured cells:

- `agnews/.../2fa90bb140485d77` → exit **23**, 1 tainted trial, finding at
  trace line 26, pattern `from datasets import`, event_id
  `toolu_01PoLakXsdsXDY6GEHNS1FWe`, scanned_field `command.python`.
  This is the agnews cheating event the 7q validator flagged by manual
  grep — now mechanically detectable.
- `music_brainz_20k/.../6b369cb7e9482e12` → exit **0**, 1 clean trial.
  Confirms the captain-principle rebalance: `pip install duckdb` /
  `pip install rapidfuzz` stay CLEAN under the rebalanced
  named-lib-only regex.

The previously silent-blindness bug is fixed and the rebalance does not
regress generic compute libs.

## Full pytest (assignment §3)

      cd .worktrees/spacedock-ensign-dab-verify-stage-external-oracle-audit
      uv run pytest --ignore=tests/unit/test_task_identity_scoring.py
      → 655 passed, 12 skipped, 9 failed in 48.39s

The 9 failing tests are pre-existing on the worktree's base (`2abdd05`)
and were not touched by wp's diff:

      tests/integration/test_worktree_teardown_preserves_runs.py::test_worktree_remove_force_does_not_destroy_runs
      tests/unit/test_claude_benchmark_spec_generator.py::test_goal1_claude_specs_use_per_variant_agent_kind
      tests/unit/test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch
      tests/unit/test_generate_matrix_specs.py::test_matrix_specs_query_mode_batch_for_all_variants
      tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_spacedock_variant_emits_spacedock_solver_kind
      tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_direct_minimal_variant_emits_claude_cli_kind
      tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_direct_structured_variant_emits_claude_cli_kind
      tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_spacedock_variant_workflow_path_exists  (sic; spec_workflow_path_exists)
      tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_spacedock_block_does_not_carry_tools_allowed_default_csv

`git log 2abdd05..HEAD -- <each-file>` returns empty for all four files,
confirming wp did not touch them. The ensign's claim of "9 pre-existing
failures identical to sibling k3 worktree at the same base" matches the
roster reproduced here.

The one collection-error file (`tests/unit/test_task_identity_scoring.py`
imports a missing `razorback.score.load` module) is the same pre-existing
import error the ensign documented and was ignored here via
`--ignore=...`.

Net new tests on wp's branch: +11 claude_code adapter tests, +4
captain-principle taint tests, +5 integration tests = +20 new passing
tests (after removing cycle-1's 7 unit + 5 integration that the cycle-2
rewire discarded, net +8 vs. cycle-1's 647). Matches the ensign's claim
of 655 passed.

## Code review (assignment §4)

A subagent dispatch tool (`Task` / general-purpose Agent) is not exposed
to this worker — only `SendMessage` to the team-lead is available. I
performed the review directly using the
`superpowers:requesting-code-review` template against every changed file
in `2abdd05..HEAD`. Findings:

### Strengths

- The contract change is documented in three places: the
  `audit/taint.py` module docstring (`Razorback divergence from upstream:
  ...`), the cycle-2 commit message body (`d9326f1`), and the entity
  body's Out-of-scope + Stage Report sections. Future readers can find
  the rationale from any of those entry points.
- `audit/claude_code.py` mirrors the `audit/harbor_codex.py` sibling
  closely: identical `_rel`, `_trial_root_for_source`,
  `discover_trial_roots`, `scan_trial`, and scanner-error fallback
  shapes. The diff is exactly what's needed for the claude-cli event
  shape (assistant.message.content[*].tool_use) and reuses
  `taint._scan_command` for pattern logic — no duplicated pattern
  surface.
- Pattern logic remains in `audit/taint.py`; the adapter only translates
  event shape. Adding a third runtime adapter later (e.g. for a future
  claude-bedrock trace) would follow the same template without touching
  patterns.
- The captain-principle list (`_FORBIDDEN_LIB_NAMES`) is built once and
  re-used in the regex, with an explicit comment that it mirrors
  `razorback.agents.claude_invoke.DISALLOWED_TOOLS`. The mirroring is
  the right place to encode the "audit and runtime agree" invariant.
- The tool_result echo defense (`test_tool_result_echo_not_flagged`)
  preserves cycle-1's correct behavior: the offense lives in the
  assistant tool_use, not the user-role tool_result echo. The
  `_iter_assistant_tool_uses` filter on `event.type == "assistant"` is
  the load-bearing guard for this — confirmed by the test.
- 5 integration tests + 11 claude_code adapter tests + 4
  captain-principle regression tests give end-to-end coverage from
  Python module up through the typer CLI.
- The `cli.py` ghost-trial dedup (lines 49-62) correctly handles the
  claude-cli runtime's `claude-output.jsonl → claude-code.txt` symlink
  that would otherwise double-discover the nested agent dir as a
  redundant CLEAN row.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)
None blocking. The implementation matches the AC clauses, the silent-
blindness fix is empirically verified, and all owned tests pass.

#### Minor (Nice to Have)

1. **`scan_trial` scanner-error fallback emits `source_path` of
   `trial_root` relative to itself (i.e. `"."`)**
   - File: `src/razorback/audit/claude_code.py:159`
   - The harbor_codex sibling has the same shape
   (`harbor_codex.py:339`), so this is consistent — but the resulting
   finding's `source_path == "."` is not very informative for an
   operator triaging an audit error. Future improvement (apply to both
   adapters together): pass `run_dir` into `scan_trial` so the
   fallback can render a more useful relative path.

2. **`_scan_tool_use` web-tool fallback emits a synthesized pattern
   string `rf"\b{name}\b"` when the taint scanner returns no finding**
   - File: `src/razorback/audit/claude_code.py:101-107`
   - Rationale: `taint.FORBIDDEN_TOOL_PATTERNS` covers `web_search` and
   `web.run` but not the literal `WebSearch` / `WebFetch` tool names
   the claude-cli uses. The fallback ensures those flag. The
   harbor_codex adapter handles its analogue (`web_search_call`)
   differently — it just calls `_scan_tool_name`. Both work, but the
   asymmetry is worth a note. If `taint.FORBIDDEN_TOOL_PATTERNS` ever
   grew literals for `WebSearch` / `WebFetch`, this fallback could be
   removed.

3. **The captain-principle regex consumes any number of flag args
   before the package name (`(?:\s+-[^\s;&|]+)*`)**
   - File: `src/razorback/audit/taint.py:36-38`
   - This is correct for the common `pip install -U datasets` shape,
   but an adversarial agent could conceivably interleave a flag-form
   that swallows the package name, e.g. `pip install --target=/tmp
   datasets`. Manually testing: `pip install --target=/tmp datasets`
   matches the regex (the flag is `--target=/tmp`, then whitespace,
   then `datasets`). Conversely `pip install datasets --upgrade` also
   matches. I cannot construct an adversarial form that evades it
   under the current flag pattern. This is a robustness note, not a
   bug.

4. **No `--variant`-gated escape hatch in the dispatcher hook**
   - File: `examples/drivers/dab-paper-matrix.sh:186-219`
   - Intentional per the entity body (AC-4: "for every variant, NOT
   variant-gated"). Flagging here only because future captain decisions
   to skip the audit for a specific variant (e.g. spacedock with the
   verify stage running it in-process) would require a code change
   rather than a flag. Not a problem now.

### Recommendations

- Consider lifting the captain-principle regex into a named module
  constant (already `_FORBIDDEN_LIB_NAMES`) and exporting it from
  `audit/taint.py` so the workflow README's named-lib list and the
  `claude_invoke.DISALLOWED_TOOLS` allowlist can import from one
  source of truth. Right now the three lists (taint.py, claude_invoke,
  README prose) are documented to mirror each other but rely on prose
  to stay in sync.
- If/when this is upstreamed back to dab, the README's "captain
  principle" framing should be re-named with a more neutral term
  (e.g. "narrowed pip-install allowlist") so upstream readers without
  the razorback session context can parse it.

### Assessment

**Ready to merge: Yes.**

**Reasoning:** All 5 AC clauses reproduce against the worktree branch
with exact-match evidence. The silent-blindness fix is empirically
verified end-to-end against the 7q agnews cell (exit 23) and the
captain-principle rebalance is empirically verified to keep
music_brainz_20k CLEAN. All 51 owned tests pass; the 9 pre-existing
full-suite failures are confirmed unchanged from base via `git log
2abdd05..HEAD` on each file. The contract change to `audit/taint.py` is
documented in three places and the new `audit/claude_code.py` adapter
is structurally consistent with the existing `audit/harbor_codex.py`
sibling.

## Gate decision

**APPROVE (validator side)** — advance to `done`.

No blocking findings. The four "Minor" items are nice-to-have follow-up
improvements; none of them gate the merge.

### Captain-attention note

The dispatch prompt stated: "wp's frontmatter does NOT carry
`auto-approve: false` — sprint pre-auth applies." This is **incorrect**:
the entity's frontmatter at line 7 is `auto-approve: false`, with the
rationale in line 5 ("Auto-approve: false because the workflow contract
is captain-facing"). Per the workflow's validation-stage discipline,
auto-merge should NOT happen automatically here — the captain (or first
officer with captain ack) should review this validation report before
the no-ff merge + archive. Flagging so the FO does not silently
auto-mod-block + merge based on the dispatch's mistaken claim.
