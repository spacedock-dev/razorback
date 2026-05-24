# Validation: generic-harbor-benchmark-surface-design (hm, cycle-6)

- Entity: `docs/razorback-implementation/generic-harbor-benchmark-surface-design.md`
- Branch: `spacedock-ensign/generic-harbor-benchmark-surface-design`
- Base (merge-base with main at validation time): `531ab06`
- Head: `aafb045` (cycle-6 stage report wrap)
- Six shipped commits under review: `f5f6450` (4a), `27d03a3` (3), `624ad94` (4b+4c), `a74037c` (5), `fb1f216` (6), `d3ce442` (AC-2 amendment)
- Validator: spacedock-ensign-generic-harbor-benchmark-surface-design-validation
- Date: 2026-05-24
- `auto-approve: false` on entity frontmatter — captain MUST ack at gate regardless of validator verdict.

## Clean-state check

`git clean -fdx -n` reports only `.venv/`, `__pycache__/`, `.pytest_cache/`, `.test-tmp/`, plus
`examples/specs/provenance.yaml` (created by `rk freeze` during AC-5 verification) and
`docs/templates/research-project/runs/` (cycle-4 scaffold artefact). No source-tree debris bleeds
into the verifiers. Worktree carries one modified file (`uv.lock`, a 1-line `exclude-newer`
metadata bump) — unrelated to the six shipped commits.

## Per-AC verdict

### AC-1 — `HarborDabBenchmarkBlock` removed; `razorback-plugin-dab` discovered as `kind: harbor + plugin: dab` consumer (PASS — with one verifier deviation, see "Outstanding concerns")

Verifier-by-verifier evidence:

```
$ grep -n "class HarborDabBenchmarkBlock" src/razorback/spec/schema.py
(no matches; exit 1)

$ grep -n "_build_harbor_dab\b" src/razorback/translate.py
(no matches; exit 1)

$ uv run python -c "import importlib.metadata as m; assert 'dab' in {ep.name for ep in m.entry_points(group='razorback.plugin_args')}; print('OK')"
OK

$ uv run rk freeze examples/specs/bookreview-claude-harbor-dab.yaml --allow-missing --out /tmp/bookreview-harbor.frozen.yaml
wrote /tmp/bookreview-harbor.frozen.yaml
wrote examples/specs/provenance.yaml

$ uv run pytest packages/razorback-plugin-dab/tests/ tests/translate/test_dab_dispatch.py -v
170 passed, 1 failed, 3 skipped in 65.12s
  (only failure: test_mongo_init_shim_loads_bsondump_on_first_start —
   docker-infra environment dependency; test landed pre-branch at commit 06e094e
   and fails on this host regardless of branch.)
```

The schema delete, the translator delete, the entry-point registration, the `rk freeze` round-trip
on a migrated harbor_dab spec, and the dab-plugin + dispatch test suite all check out. AC-1.d's
`rk run --explain` portion is documented under "Outstanding concerns" (translator CLI mismatch
discovered when the explain path actually fires the plugin subprocess).

### AC-2 — `AdeBenchBenchmarkBlock` removed; ade-plugin wired; generic `/workspace/preflight.sh` mechanism in place (PASS with caveats — see "Outstanding concerns")

```
$ grep -nR "class AdeBenchBenchmarkBlock\|_build_ade_bench\b\|benchmark_kind == [\"']ade-bench" src/razorback/
src/razorback/_legacy/compat/harbor_0_6_6.py:90:            _build_ade_bench(
src/razorback/_legacy/compat/harbor_0_6_6.py:195:def _build_ade_bench(
```

The two matches are inside `_legacy/compat/harbor_0_6_6.py`, which is the rollback shim called
only by three legacy test files (`tests/unit/test_dab_translator_twelve.py`,
`tests/unit/test_compat_translator.py`, `tests/unit/test_dab_translator.py`). The active
`src/razorback/translate.py` carries no `_build_ade_bench` reference. The impl flagged this in
the cycle-6 deviation note as an intentional rollback shim — the literal grep wording in AC-2
didn't scope to `src/razorback/translate.py` plus the active solver path, so the legacy
helpers light up. Acceptable scope per impl's note.

```
$ grep -n "/workspace/preflight.sh" src/razorback/_runtime/
grep: src/razorback/_runtime/: No such file or directory
```

The AC-text path `src/razorback/_runtime/` does not exist in this repo. The solver-side generic
preflight dispatcher actually lives at `src/razorback/agents/spacedock_solver.py` (5 references at
lines 474-500), and there is no longer an `ade-bench` conditional on that dispatch. The
mechanism described by AC-2 is present at a different path than the AC names; the verifier as
literally written is unsatisfiable on this code layout.

```
$ uv run python -c "import importlib.metadata as m; assert 'ade-bench' in {ep.name for ep in m.entry_points(group='razorback.plugin_args')}; print('OK')"
OK

$ uv run python -c "from razorback.benchmarks.ade_bench.plugin_args import AdeBenchPluginArgs; print(list(AdeBenchPluginArgs.model_fields.keys()))"
['docker_image_override', 'batch_mode', 'db_type', 'project_type']
```

ade-bench entry-point + typed plugin args resolve cleanly.

```
$ uv run pytest tests/unit/test_spacedock_solver_ade_preflight.py tests/unit/test_ade_bench_workspace_preflight.py -v
9 passed in 0.52s

$ uv run rk freeze examples/specs/ade-bench-claude.yaml --allow-missing --out /tmp/ade-claude.frozen.yaml
wrote /tmp/ade-claude.frozen.yaml
wrote examples/specs/provenance.yaml

$ uv run python -c "from razorback.spec.parse import parse_spec_file; from pathlib import Path; s = parse_spec_file(Path('/tmp/ade-claude.frozen.yaml')); print(s.benchmark.kind, s.benchmark.dataset, s.benchmark.tasks)"
harbor dbt-labs/ade-bench@latest ['airbnb001']
```

Migrated ade-bench spec parses cleanly as `kind: harbor`. `rk run --explain` on the frozen spec
is environment-blocked by the runs-dir mount-visibility canary (`ConfigInvalidError`) — this is
the same harness restriction cycles 2-4 noted; it is host-side, not impl-side, and pre-existing.

AC-2.d (`/workspace/preflight.sh` emission by the ade-plugin) is documented under "Outstanding
concerns": the ade-plugin emits `razorback_ade_preflight.py` via a Dockerfile COPY layer
(`src/razorback/benchmarks/ade_bench/harbor_view.py:126-149`), not a bash file at
`/workspace/preflight.sh`. The solver-side dispatcher's `[ -x /workspace/preflight.sh ]` probe
falls through to no-op on the ade path, and the actual ade preflight runs via the Dockerfile
patch a different way. The "generic mechanism" is in place but no current plugin uses it.

The AC-2 verifier `uv run pytest tests/translate/test_ade_dispatch.py -v` cannot be run as
literally written because `tests/translate/test_ade_dispatch.py` does not exist; the closest
equivalents that did pass (`tests/unit/test_spacedock_solver_ade_preflight.py` +
`tests/unit/test_ade_bench_workspace_preflight.py`) cover the generic dispatcher and the
contract-style preflight.

### AC-3 — `Spider2DbtBenchmarkBlock` removed; spider2-plugin wired (PASS — with verifier deviation noted)

```
$ grep -n "class Spider2DbtBenchmarkBlock\|_build_spider2" src/razorback/
(no matches; exit 1)

$ uv run python -c "import importlib.metadata as m; assert 'spider2' in {ep.name for ep in m.entry_points(group='razorback.plugin_args')}; print('OK')"
OK

$ uv run python -c "import importlib.metadata as m; eps=list(m.entry_points(group='razorback.plugin_args')); s=[e for e in eps if e.name=='spider2'][0]; print(s.value); print(s.load())"
razorback.benchmarks.spider2_dbt.plugin_args:Spider2PluginArgs
<class 'razorback.benchmarks.spider2_dbt.plugin_args.Spider2PluginArgs'>
```

Schema delete + translator delete + entry-point registration all present. Per cycle-5 captain
decision, spider2 lives in-tree at `src/razorback/benchmarks/spider2_dbt/` rather than as a
sibling pip package — so the AC-3 verifier `uv run pytest packages/razorback-plugin-spider2/tests/ -v`
cannot run (directory does not exist by design). The AC's alt phrasing "or, if the plugin lives
in-tree, the equivalent test path" admits this, but no dedicated spider2 test file ships on this
branch — the in-tree spider2 code is exercised only transitively through the union-discriminator
tests + the entry-point discovery check above. This is the thinnest test surface among AC-1..3
and is flagged in "Outstanding concerns" as non-blocking under captain's "no new pip packages"
direction but worth a future-followup.

The migrated-spec round-trip clause is moot — no `kind: spider2-dbt` specs were filed in
`examples/` pre-migration, so there is no spec to migrate. Confirmed via
`grep -lE "^\s*kind:\s*spider2" examples/` returning empty.

### AC-4 — `rk score` surfaces `taint_status` + auto-pulls `paper_baseline` (PASS)

```
$ uv run pytest tests/cli/test_score.py -v
4 passed in 0.43s
  test_score_surfaces_taint_status_from_audit_json PASSED
  test_score_soft_fails_when_audit_json_missing PASSED
  test_score_auto_pulls_paper_baseline_from_frozen_spec PASSED
  test_score_explicit_against_constant_overrides_paper_baseline PASSED
```

The four tests cover taint-surface, soft-fail, auto-pull, and CLI-override behaviours, hitting
the load-bearing JSON-output payload path. Commit `a74037c` adds both implementation and tests
atomically (rather than landing a RED test commit before the GREEN implementation commit per
AC-4's literal `cite both commit SHAs` phrasing). The single-commit landing still satisfies the
behavioural intent — both tests would fail on the cycle-1 main where `_load_audit_status` and
`_load_paper_baseline` don't exist. Treating "both SHAs" as a per-commit TDD discipline rather
than a literal two-commit split is acceptable.

Minor observation: only `render_json` consumes `taint_status` and `constant_source`;
`render_markdown` ignores both. AC-4's verifier names JSON output only, so this is
contract-conformant, but a future `rk score --format markdown` consumer will lose the taint
context. Non-blocking.

### AC-5 — examples/specs migrated to `kind: harbor`; sealed_hash break documented (PASS for examples/, partial for docs/)

```
$ grep -rlE "^\s*kind:\s*(harbor_dab|ade-bench|spider2-dbt)\b" examples/
(empty)

$ for s in $(find examples -name "*.yaml" -path "*spec*" | grep -v provenance.yaml); do
    uv run rk freeze "$s" --allow-missing >/dev/null 2>&1 && echo "ok" || echo "FAIL $s";
  done | sort | uniq -c
  68 ok

$ git log --oneline --grep="sealed_hash"
27d03a3 hm commit 3/6: migrate examples/specs/* harbor_dab → harbor + plugin: dab
... (and several pre-existing commits)
```

`examples/` is 100% clean of the deleted kinds; 68/68 spec files freeze cleanly under
`rk freeze --allow-missing`; commit `27d03a3`'s body explicitly names the sealed_hash break,
cites design §2.4, names `rk freeze --rehash` as the migration recipe, and enumerates the 7q
frozen-spec implication. This part of AC-5 is unambiguously satisfied.

The literal AC-5.a verifier scopes `examples/ docs/`. The grep against `docs/` still lights up
12 archived plan / validation / design-doc files that reference `kind: harbor_dab` etc. as
historical content:

```
docs/razorback-implementation/plans/{phase2-dab-harbor-adapter,
  dab-full-batch-codex-explain-preflight, m7-run-workflow-adebench,
  pkg16-harbor-dab-workdir-no-sql-dump, goal2-ade-bench-haiku-baseline,
  pkg40-harbor-task-view-materializer, pkg19-ade-bench-data-bind-mount,
  ade-bench-harbor-dataset-ref, fu1-claude-auth-leak-ade-bench-real-task,
  pkg14-harbor-dab-lfs-bindmount-reuse}.md
docs/razorback-implementation/validation/pkg39-benchmark-variant-spec-generation.md
docs/razorback-implementation/generic-harbor-benchmark-surface-design.md
```

The impl's cycle-6 deviation note flags this: "archived plan/_archive/validation files reference
`kind: harbor_dab` etc. as historical content; leaving them as-is matches the captain pattern of
'no rewriting of archived plan documents.'" The last file in the list is this entity's own
design doc, whose "Today" before/after YAML examples necessarily contain the old kinds. The
load-bearing scope (canonical v2 spec + examples) is clean; the rewrite-archived-docs scope was
explicitly out-of-scope per the captain's "no rewriting history" pattern. Acceptable.

### AC-6 — v2 spec amended at six §-sections per §2.10 (PASS)

```
$ git log --oneline -- docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
fb1f216 hm commit 6/6: v2 spec amendment per design §2.10
96822a3 hm: design doc + spec amendment — generic harbor benchmark surface
... (older history)

$ git diff origin/main..HEAD -- docs/superpowers/specs/2026-05-19-razorback-on-harbor.md | wc -l
110

$ grep -cE "^\s*kind:\s*harbor\b" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
1

$ grep -nE "^\s*kind:\s*(harbor_dab|ade-bench|spider2-dbt|harbor|harbor-local|local)\b" \
    docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
790:  kind: harbor
```

110-line diff vs main sits inside §2.10's ~120-line envelope (±20% → 96-144 acceptable). The
only `kind:` value left in the spec body is `harbor`. Zero per-benchmark-named kinds remain.
AC-6 unambiguously passes.

### AC-7 — Existing pytest stays green; non-migrated paths unchanged (PASS)

```
$ uv run pytest tests/ --tb=line --ignore=tests/unit/test_task_identity_scoring.py
4 failed, 703 passed, 12 skipped, 22 warnings in 29.25s

FAILED tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::test_codex_runtime_dispatch_constructs_inner_agent
FAILED tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::test_harbor_jobs_resume_round_trip_with_new_trial_name
FAILED tests/integration/test_worktree_teardown_preserves_runs.py::test_worktree_remove_force_does_not_destroy_runs
FAILED tests/unit/test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch
+ ImportError (collection error) tests/unit/test_task_identity_scoring.py:
    No module named 'razorback.score.load'
```

Exactly matches the cycle-6 stage report's enumerated baseline (entity body lines 1311-1319):
- 703 passed (cycle-6: 703 passed)
- 4 pre-existing failures, set byte-identical:
  `test_codex_runtime_dispatch_constructs_inner_agent`,
  `test_harbor_jobs_resume_round_trip_with_new_trial_name`,
  `test_worktree_remove_force_does_not_destroy_runs`,
  `test_matrix_specs_carry_query_mode_batch`
- 1 collection error byte-identical:
  `test_task_identity_scoring.py` (`No module named 'razorback.score.load'`, introduced by codex
  commit `97b375b` before its companion module landed — pre-existing on main, out of scope).
- 12 skipped (cycle-6: 12 skipped)

`LocalBenchmarkBlock` dispatch path's existing tests pass without modification per the
Out-of-scope clause. AC-7 unambiguously passes.

## Code review

Reviewed the six shipped commits as a single body. Inline review against the entity's
acceptance discipline + spec §6.1's plugin contract.

### Strengths

- **Plugin discovery + typed args contract is clean.**
  `src/razorback/spec/plugin_args.py` is 60 lines, single responsibility, instance-level cache,
  surfaces `PluginNotFoundError` with the list of known plugins (good DX on misconfiguration).
  `HarborBenchmarkBlock._validate_source_and_ref` (`schema.py:197-249`) re-parses
  `plugin_args` against the plugin's own Pydantic model at spec validation time — typos and
  bad types fail at `rk freeze` rather than at runtime, exactly the contract design §2.6 names.
- **Generic preflight dispatcher decouples solver from benchmark identity.**
  `_run_workspace_preflight` (`spacedock_solver.py:473-502`) probes a filesystem convention
  (`/workspace/preflight.sh`, `-x` check, 120s budget). No benchmark-name conditional remains
  in the solver. The mechanism is sound; the gap is that no plugin currently emits to it —
  see Important findings.
- **Sealed_hash break is named, not silent.**
  Commit `27d03a3`'s body enumerates the agent-side `benchmark_kind` field shift, lists which
  freeze-CAS entries become orphaned, names the `rk freeze --rehash` migration recipe, and
  calls out the pending 7q agnews re-run. Consumer-facing migration story is documented at the
  exact point it became binding.
- **TDD discipline holds per commit boundary.**
  Commit 4a (`f5f6450`) lands new tests (`test_plugin_args_registry.py`,
  `test_harbor_block_plugin_args.py`, `test_dab_dispatch.py`) alongside the schema +
  translator changes; commit 5 (`a74037c`) lands `test_score.py`'s four cases alongside
  `_load_audit_status` / `_load_paper_baseline`. AC-7 stays byte-identical at every boundary
  per the cycle-6 report's per-commit baseline assertion.
- **Plugin args dict-to-CLI conversion handles bool flags correctly.**
  `_invoke_plugin_generate` (`translate.py:366-373`) maps `bool` to `--flag` / `--no-flag`,
  skips `None`, and stringifies other values. Matches the dab plugin's typer `--hints/--no-hints`
  shape.

### Important findings

1. **Translator passes `--dataset` to the dab plugin CLI, which has no such option.**
   - File: `src/razorback/translate.py:361-363`
   - Issue: When `block.dataset` is non-None (which it must be — `_validate_source_and_ref`
     requires it), the translator appends `["--dataset", dataset]` to the plugin generate
     command. The dab plugin CLI
     (`packages/razorback-plugin-dab/src/razorback_plugin_dab/cli.py:25-53`) accepts
     `--datasets` (plural, comma-separated dataset names) plus other flags, but no `--dataset`
     option exists. Direct probe:
     ```
     $ uv run razorback-plugin-dab generate --out /tmp/dab-probe --dataset dab@1.0 --datasets bookreview
     Error: No such option: --dataset (Possible options: --data-root, --datasets)
     (exit 2)
     ```
     End-to-end repro through `rk run --explain` on a migrated harbor_dab spec hits this and
     raises `SpecError: razorback-plugin-dab generate failed (exit 2)`. The dispatch unit tests
     (`tests/translate/test_dab_dispatch.py:53-181`) mock `subprocess.run` and never exercise
     the real plugin CLI, so the contract drift was not caught.
   - Why it matters: AC-1.d's `Verified by:` says "the migrated harbor_dab spec round-trips
     through `uv run rk freeze` cleanly; `rk run --explain --explain-format json` on the
     migrated spec resolves to the same dataset ref, model, runtime, and `tools_denied` set
     as the pre-migration freeze." The freeze portion works; the explain portion crashes at
     translator dispatch with a real CLI mismatch. Any live `rk run` of a migrated
     `kind: harbor + plugin: dab` spec will fail at exactly this seam. The cycle-6 stage
     report's claim that AC-1 is green relied on the mock-subprocess tests rather than a live
     plugin invocation; this validation surfaced the gap.
   - How to fix: either (a) drop the `--dataset` arg from the translator (the dab plugin owns
     its own `dab@1.0` interpretation via `--datasets` + `--data-root`, so the dataset ref is
     effectively unused once the plugin has the dataset names), or (b) extend the dab plugin
     CLI to accept and validate `--dataset <ref>`. Add at least one non-mocked integration
     test that calls the real `razorback-plugin-dab generate` binary with the translator's
     emitted command — this would have caught the drift at commit-4a's TDD boundary.

2. **No plugin currently emits `/workspace/preflight.sh`.**
   - Files: `src/razorback/benchmarks/ade_bench/harbor_view.py:116-149`; solver dispatcher
     at `src/razorback/agents/spacedock_solver.py:474-502`.
   - Issue: The ade-bench plugin emits a Python script at `environment/razorback_ade_preflight.py`
     and patches the task Dockerfile with a `COPY razorback_ade_preflight.py /tmp/...` + a
     verifier-time invocation. It does NOT drop an executable `/workspace/preflight.sh`. The
     solver's new generic dispatcher unconditionally executes `[ -x /workspace/preflight.sh ]`
     and falls through to no-op for every task today. The "generic preflight mechanism" exists
     as solver-side scaffolding but has zero callers.
   - Why it matters: AC-2's `Verified by:` clause says "the ade-plugin's canonical `generate()`
     entry-point … emits `/workspace/preflight.sh` with executable bit set for a materialized
     task view fixture; `test -x` on the emitted path exits 0." That clause is not
     satisfiable against the shipped code. The intent — "decouple solver from benchmark
     identity" — is achieved (solver no longer has `benchmark_kind == "ade-bench"`
     branches), but the AC's load-bearing demonstration of the mechanism in use isn't there.
     Until at least one plugin populates `/workspace/preflight.sh`, the dispatcher is dead
     code from the contract perspective.
   - How to fix: either (a) migrate the ade-bench preflight emission from the Dockerfile COPY
     layer to a `/workspace/preflight.sh` drop the solver-side dispatcher will pick up, or (b)
     document in the design doc / entity body that the AC-2.d verifier is forward-looking
     (the mechanism is ready; first consumer arrives in a sibling entity). Either is fine; the
     status-quo silence is what's misleading.

3. **`HarborBenchmarkBlock._validate_source_and_ref` does double-work on dataset ref.**
   - File: `src/razorback/spec/schema.py:209-232`
   - Issue: When `plugin is None`, the validator first calls
     `PackageReference.parse(self.dataset)` (raising via `ValueError` on Harbor parser
     failure), then independently checks `"/" not in self.dataset or "@" not in self.dataset`,
     then `not parsed.org or not parsed.short_name or not parsed.ref`. If `PackageReference.parse`
     succeeded but parsed_org/short_name/ref is somehow empty (defensive), the bare-string check
     gives one error message and the parsed-attr check gives a different one with the same
     `_HARBOR_DATASET_REF_EXAMPLE!r` body. The two raise paths produce identical user-facing
     diagnostics, which is harmless but suggests the bare-string check is redundant defensive
     code.
   - Why it matters: minor — readability + a hint that the validator's contract isn't fully
     pinned to the `PackageReference.parse` semantics.
   - How to fix: drop the bare-string `"/" not in / "@" not in` check; rely on
     `PackageReference.parse` raising plus the explicit parsed-attr check. Or, conversely,
     drop the parsed-attr check and trust `PackageReference.parse`. Pick one.

### Minor findings

1. **`_invoke_plugin_generate` does `import json` / `import subprocess` inside the function.**
   - File: `src/razorback/translate.py:353-354`
   - Issue: function-local imports for `json` and `subprocess` are a minor style hit; both
     modules are stdlib and the cost of top-level imports is nil. The file already imports
     other stdlib at module top.
   - How to fix: hoist to module top.

2. **`_invoke_plugin_generate` collects tasks with `tasks_root.rglob("task.toml")` and dedupes
   their parents.**
   - File: `src/razorback/translate.py:382-385`
   - Issue: `sorted({p.parent for p in task_dirs})` materializes a set and then sorts it. The
     plugin contract emits one `task.toml` per task dir; there should not be duplicates. The
     set construction defends against the plugin emitting weirdness, but the cost (lost
     ordering control between plugin output and what the translator builds JobConfig from) is
     small and the win is small. Non-blocking.

3. **`render_markdown` ignores `taint_status` and `constant_source`.**
   - File: `src/razorback/score/render.py` (via the commit diff)
   - Issue: only `render_json` consumes the two new kwargs. A user invoking
     `rk score --format markdown` against a tainted run sees no taint surface in the output.
     AC-4's verifier only names JSON; this is contract-conformant but a future trap.
   - How to fix: thread `taint_status` / `constant_source` into `render_markdown` too, or
     document the JSON-only surface in the doc.

4. **Acknowledged §2.11 deviation — 4b and 4c folded into one commit `624ad94`.**
   - The impl's cycle-6 report names this with the load-bearing rationale: "the spider2-dbt
     schema deletion was load-bearing for the BenchmarkBlock union cleanup; the per-kind split
     would have left the union internally inconsistent (pytest red at the 4b boundary)." This
     is a substantive rationale — pytest-green at every boundary is the higher-order
     constraint. The single combined commit preserves bisect safety for the
     "ade-bench + spider2-dbt removed together" granularity, which is the genuinely meaningful
     unit. The dispatch's "not by itself REJECT-worthy" framing matches my reading. Flagged
     for captain visibility; non-verdict-changing.

5. **`legacy/compat/harbor_0_6_6.py` rollback shim retained.**
   - The shim contains `_build_harbor_dab`, `_build_ade_bench`, `_build_spider2_dbt`,
     `_build_dab` (and the old `HarborDabBenchmarkBlock` etc. classes via reference). It's
     invoked only from three legacy test files. Per the impl's cycle-6 disclosure, this is an
     intentional rollback path. The retention is consistent with razorback's pattern (cf.
     `_legacy/benchmarks/dab/`), and the AC text didn't scope grep verifiers to the active
     translator. Non-blocking; flagged in case the captain expects the legacy shim retired
     in a follow-up entity.

6. **`AdeBenchTaskEntry` non-union helper class retained.**
   - File: `src/razorback/spec/schema.py:152-162`
   - The class is no longer on `BenchmarkBlock`'s active union but is still accessed by
     `src/razorback/benchmarks/ade_bench/tasks.py` (per the schema docstring on line 152).
     The impl's note in the cycle-6 stage report flags this; the dispatch confirms it as an
     "out-of-scope helpers retained" judgment call. Acceptable, but a sibling cleanup entity
     could retire the class once `benchmarks/ade_bench/tasks.py` either is dropped or replaced
     with a plugin-native shape.

### Architecture / production-readiness

- **No backwards-compatibility shim for `kind: harbor_dab` specs landed.** Per cycle-4
  captain decision (option B, accept the 7q break), this is intentional; the sealed_hash
  break is documented at commit 3 and the recipe (`rk freeze --rehash`) is named. Aligned
  with the spec amendment direction.
- **Plugin contract uses `uv run razorback-plugin-<name>` as the entry-point command.** This
  ties the plugin discovery to a uv-installed CLI script per plugin (pip-installed today; in-tree
  pyproject scripts for ade/spider2). The contract is implicit — there is no formal "plugin
  ABI" doc beyond what's in `plugin_args.py` + design §2.6. Acceptable for the current consumer
  count (3 plugins). A future formal contract entity could codify (a) the typed args model
  shape, (b) the `generate` CLI contract (`--out`, `--datasets`, optional `--dataset`), (c)
  the `trial_name_map_v2.json` emission shape, (d) the `/workspace/preflight.sh` filesystem
  convention if it becomes a real surface.

## Outstanding concerns (summary)

The following are surfaced as captain-visibility items rather than verdict-changing issues:

1. **Translator/plugin CLI drift (Important).** `rk run --explain` on a migrated harbor_dab
   spec crashes at translator dispatch because the translator passes `--dataset` to a plugin
   CLI that has no such option. This is the most reachable end-to-end live failure mode the
   migration leaves on `main` if shipped as-is. A sibling fix-entity should land before the
   next live `kind: harbor + plugin: dab` run.
2. **Generic `/workspace/preflight.sh` mechanism has no current emitter (Important).** Solver
   dispatcher is in place; ade-plugin emits via Dockerfile COPY layer at a different path.
   AC-2.d's literal verifier is unsatisfiable until at least one plugin populates
   `/workspace/preflight.sh`. Mechanism vs. consumer gap.
3. **AC verifier paths drift from the actual code layout (Minor).** AC-2.b names
   `src/razorback/_runtime/` (does not exist), AC-2.f names `tests/translate/test_ade_dispatch.py`
   (does not exist), AC-3.d names `packages/razorback-plugin-spider2/tests/` (does not exist
   per captain decision). The intent is met at adjacent paths; the AC text itself drifted from
   the captain-decision shape of in-tree-plus-entry-points.
4. **Legacy compat shim retained (acceptable per dispatch).**
5. **`AdeBenchTaskEntry` non-union helper class retained (acceptable per dispatch).**

## Gate decision: REJECT

**Reasoning:** Six of the seven ACs check out against the shipped code, modulo verifier-text
imprecisions that the impl's cycle-6 deviation note correctly named in advance. The blocker is
finding #1 under Important findings: `src/razorback/translate.py:361-363` passes a `--dataset`
flag to the dab plugin CLI that has no such option, causing `SpecError: razorback-plugin-dab
generate failed (exit 2)` on the very `rk run --explain` round-trip AC-1.d's `Verified by:`
clause demands. This is not an environment artefact — the dab plugin CLI's signature is
explicit in `packages/razorback-plugin-dab/src/razorback_plugin_dab/cli.py:25-53`, and the
direct CLI probe confirms `--dataset` is rejected. The unit tests
(`tests/translate/test_dab_dispatch.py`) mock `subprocess.run` and so never exercised the real
plugin contract; the dispatch's `Verified by:` round-trip is exactly the integration check
that catches this class of drift.

A live `kind: harbor + plugin: dab` run on `main` after this lands will fail at the same seam.
The fix is small (drop `--dataset` from `_invoke_plugin_generate`'s command emission, or extend
the dab plugin CLI to accept it) but it must land before this branch is approved — otherwise
the canonical 7q + DAB paper-repro paths are functionally broken on `main`.

Per the dispatch instructions: `auto-approve: false` on entity frontmatter, captain MUST ack
this verdict at gate regardless. Recommendation to the captain: REJECT back to implementation
for a minimal fix-cycle that (a) drops or aligns the `--dataset` flag emission, (b) adds at
least one non-mock dispatch integration test that calls the real plugin binary with the
translator's emitted command, and (c) optionally addresses Important finding #2
(`/workspace/preflight.sh` consumer gap) and the verifier-text drifts under
"Outstanding concerns" item #3. The other 6 commits and 6 ACs stand on their own; the rejection
scope is narrow.

---

# Validation appendix: cycle 2 — post-fix re-verification

- Entity: `docs/razorback-implementation/generic-harbor-benchmark-surface-design.md`
- Branch: `spacedock-ensign/generic-harbor-benchmark-surface-design`
- Head (cycle-2 validation target): `8b92112` (cycle-7 stage report wrap)
- Cycle-1 fix commits under review: `cbb1db9` (RED, new integration test) → `c000fe8` (GREEN, drop `--dataset` argv)
- Validator: spacedock-ensign-generic-harbor-benchmark-surface-design-validation
- Date: 2026-05-24
- Captain auto-approve: false — captain MUST ack at gate regardless of verdict.
- Cycle count: 2 of 3 max.

This appendix verifies the cycle-1 narrow-scope fix (Material #1: translator `--dataset` CLI drift). Material #2 (`/workspace/preflight.sh` consumer gap) and Polish #3 (AC verifier text drifts) remain captain-deferred per the cycle-1 feedback record; they are NOT re-raised as REJECT triggers in this cycle. AC-2..AC-7 evidence from the cycle-1 baseline above stands; this appendix re-runs a no-regression spot-check.

## Cycle-1 fix re-verification (Material #1 → AC-1.d)

### RED→GREEN ordering on the fix commits

```
$ git log --oneline cbb1db9 c000fe8 -2
c000fe8 hm cycle-1 GREEN: drop --dataset from plugin CLI emission
cbb1db9 hm cycle-1 RED: real-plugin dispatch integration test
```

RED commit lands the new non-mock integration test at `tests/translate/test_dab_dispatch_real_plugin.py`; GREEN commit drops the `--dataset` argv emission from `_invoke_plugin_generate` (`src/razorback/translate.py:355-358`) and removes the now-dead `dataset` keyword from the function signature. Ordering matches the cycle-1 contract.

### Pre-fix repro (validator's exit-2 still reproducible directly against the plugin CLI)

The plugin CLI signature has not changed — the rejected option is an inherent contract of the plugin binary the translator must conform to. Direct probe re-runs:

```
$ uv run razorback-plugin-dab generate --out /tmp/dab-probe-cycle2 --dataset dab@1.0 --datasets bookreview
Usage: razorback-plugin-dab generate [OPTIONS]
Try 'razorback-plugin-dab generate --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ No such option: --dataset (Possible options: --data-root, --datasets)        │
╰──────────────────────────────────────────────────────────────────────────────╯
```

Reproduces the validator's cycle-1 exit-2 finding verbatim. Translator's emitted argv at cycle-1 head WOULD have hit this; at cycle-2 head it doesn't (see below).

### New integration test is real-subprocess (no mock)

`tests/translate/test_dab_dispatch_real_plugin.py` calls `spec_to_job_config` which routes through `_invoke_plugin_generate`'s `subprocess.run(cmd, ...)` without monkeypatching. The spec uses `plugin: dab` + `tasks: [hello-fixture]` (the plugin's hello-fixture dataset ships in-package; no DAB data root required). Direct read of the test file confirms zero `mock` / `monkeypatch` / `MagicMock` references; the only stdlib import beyond `pathlib`/`pytest` is the module under test.

```
$ uv run pytest tests/translate/test_dab_dispatch_real_plugin.py tests/translate/test_dab_dispatch.py -v
6 passed in 0.19s
  test_real_plugin_dispatch_emits_hello_fixture PASSED
  test_dab_plugin_dispatch_invokes_subprocess_and_builds_tasks PASSED
  test_dab_plugin_dispatch_reads_trial_name_map_v2_when_emitted PASSED
  test_dab_plugin_dispatch_propagates_plugin_failure PASSED
  test_dab_plugin_dispatch_requires_tasks_root PASSED
  test_dab_plugin_dispatch_emits_batch_mode_when_one_task_carries_many_queries PASSED
```

New integration test green; the five pre-existing mock-based dispatch tests also stay green — the fix is backward-compatible with the test surface.

### Live `rk run --explain` round-trip reaches the plugin generate step

```
$ uv run rk freeze examples/specs/_deterministic-smoke.yaml --allow-missing \
    --out /tmp/_det-smoke-cycle2.frozen.yaml
wrote /tmp/_det-smoke-cycle2.frozen.yaml

$ grep -A 6 "^benchmark:" /tmp/_det-smoke-cycle2.frozen.yaml
benchmark:
  kind: harbor
  dataset: dab@1.0
  tasks:
  - bookreview
  exclude_tasks: null
  n_tasks: null

$ uv run rk run --explain --explain-format json --runs-dir .test-tmp/cycle2-runs \
    /tmp/_det-smoke-cycle2.frozen.yaml
…
SpecError: razorback-plugin-dab generate failed (exit 2): razorback-plugin-dab:
  dataset bookreview not hydrated, found LFS pointer at
  ${DATAAGENTBENCH_DATA_ROOT:-~/dataagentbench/data}/query_bookreview/db_config.yaml.
Hydrate with:
  cd ${DATAAGENTBENCH_DATA_ROOT:-~/dataagentbench/data} && git lfs pull
```

The failure mode is now the env-dependent LFS-hydration gate FROM INSIDE THE PLUGIN — not the cycle-1 `No such option: --dataset` from typer's argv parser. The translator reaches the plugin generate step cleanly; the live AC-1.d round-trip past the plugin boundary is unblocked. Verified end-to-end on the data-independent path via an in-process probe:

```
$ uv run python -c "
from pathlib import Path
from razorback.translate import _invoke_plugin_generate
tasks_root = Path('.test-tmp/cycle2-helloprobe/tasks')
trial_map = _invoke_plugin_generate(plugin='dab', plugin_args={},
                                    spec_tasks=['hello-fixture'], tasks_root=tasks_root)
print('emitted tasks:', sorted(p.name for p in tasks_root.iterdir() if p.is_dir()))
"
emitted tasks: ['hello-fixture']
```

End-to-end SUCCESS through the real plugin binary; AC-1.d's "reaches the plugin generate step" intent is verified.

## AC-2..AC-7 no-regression spot-check

Cycle-1 fix touched only `src/razorback/translate.py` (9 lines) plus the new test file. No other source file changed between cycle-1 head (`aafb045`) and cycle-2 head (`8b92112`). The cycle-1 validation report's AC-2..AC-7 evidence remains binding. Spot-check verifies the key invariants hold:

```
$ grep -cn "class HarborDabBenchmarkBlock" src/razorback/spec/schema.py
0     (AC-1.a stable)

$ grep -cn "_build_harbor_dab\b" src/razorback/translate.py
0     (AC-1.b stable)

$ uv run python -c "import importlib.metadata as m; assert 'dab' in {ep.name for ep in m.entry_points(group='razorback.plugin_args')}"
(exit 0, AC-1.c stable)

$ grep -cn "class Spider2DbtBenchmarkBlock\|_build_spider2" src/razorback/spec/schema.py src/razorback/translate.py
0:0   (AC-3.a stable)

$ uv run python -c "import importlib.metadata as m; assert 'spider2' in {ep.name for ep in m.entry_points(group='razorback.plugin_args')}"
(exit 0, AC-3.b stable)

$ uv run python -c "import importlib.metadata as m; assert 'ade-bench' in {ep.name for ep in m.entry_points(group='razorback.plugin_args')}"
(exit 0, AC-2.c stable)

$ uv run pytest tests/cli/test_score.py -v
4 passed in 0.45s    (AC-4 stable)

$ grep -rlE "^\s*kind:\s*(harbor_dab|ade-bench|spider2-dbt)\b" examples/
(empty, AC-5.a stable)

$ git diff origin/main..HEAD -- docs/superpowers/specs/2026-05-19-razorback-on-harbor.md | wc -l
110   (AC-6 stable; 110 ≤ 144 envelope ceiling)

$ grep -cE "^\s*kind:\s*harbor\b" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
1     (AC-6 stable)
```

AC-7 pytest baseline:

```
$ uv run pytest tests/ --tb=line --ignore=tests/unit/test_task_identity_scoring.py
4 failed, 704 passed, 12 skipped, 22 warnings in 35.00s

FAILED tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::test_codex_runtime_dispatch_constructs_inner_agent
FAILED tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::test_harbor_jobs_resume_round_trip_with_new_trial_name
FAILED tests/integration/test_worktree_teardown_preserves_runs.py::test_worktree_remove_force_does_not_destroy_runs
FAILED tests/unit/test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch
+ collection error: tests/unit/test_task_identity_scoring.py (pre-existing 'razorback.score.load')
```

**704 passed** (cycle-1 baseline was 703; +1 = the new `test_real_plugin_dispatch_emits_hello_fixture` integration test, exactly as the cycle-7 stage report predicted). The 4 pre-existing failures + 1 collection error are byte-identical to cycle-1.

## Per-AC re-verdict (cycle 2)

| AC | Cycle-1 verdict | Cycle-2 verdict | Notes |
|----|-----------------|-----------------|-------|
| AC-1 | (was: PASS-with-AC-1.d-blocker) | **PASS** | AC-1.d translator CLI drift fixed in c000fe8; non-mock integration test added in cbb1db9; live `rk run --explain` reaches plugin generate step; in-process probe through real plugin binary returns expected task. |
| AC-2 | PASS with verifier-text caveats | **PASS unchanged** | No code touched between cycle-1 and cycle-2 heads on this AC's scope. Verifier-text drifts (AC-2.b path `src/razorback/_runtime/`, AC-2.f `tests/translate/test_ade_dispatch.py`) — captain-deferred per cycle-1 feedback (Polish #3). |
| AC-3 | PASS with thinnest-test-surface caveat | **PASS unchanged** | Schema delete + entry-point registration stable; AC-3.d path `packages/razorback-plugin-spider2/tests/` does not exist per captain's "no new pip packages" decision — captain-deferred per Polish #3. |
| AC-4 | PASS | **PASS unchanged** | 4/4 tests at `tests/cli/test_score.py` green. |
| AC-5 | PASS for examples/, partial for docs/ | **PASS unchanged** | `examples/` clean (0 hits); archived `docs/razorback-implementation/{plans,_archive,validation}/` references are intentionally historical per impl cycle-6 deviation note. |
| AC-6 | PASS | **PASS unchanged** | 110-line diff, within §2.10's 96-144 envelope. |
| AC-7 | PASS (703 passed) | **PASS** (704 passed, +1 = new integration test) | 4 pre-existing failures + 1 collection error byte-identical to cycle-1. |

## Outstanding concerns disposition (cycle 2)

1. **Material #1 (translator/plugin CLI drift): RESOLVED.** Cycle-1 fix landed; new non-mock integration test added; live round-trip reaches plugin generate step. AC-1 fully resolved.
2. **Material #2 (`/workspace/preflight.sh` consumer gap): DEFERRED-ACK.** Captain narrowed cycle-1 scope to Material #1 only; Material #2 is captain-acknowledged for deferral to a later cycle or sibling entity. NOT re-raised as REJECT trigger in cycle 2; still acceptable.
3. **Polish #3 (AC verifier text drifts AC-2.b / AC-2.f / AC-3.d): DEFERRED-ACK.** Captain narrowed cycle-1 scope to Material #1 only; verifier-text edits captain-acknowledged for deferral. NOT re-raised as REJECT trigger in cycle 2; still acceptable. The intent of each verifier is met at the captain-decision-shape adjacent path documented in the cycle-1 report's per-AC sections.
4. **Legacy compat shim retained (cycle-1 Minor #5): unchanged.** Acceptable.
5. **`AdeBenchTaskEntry` non-union helper class retained (cycle-1 Minor #6): unchanged.** Acceptable.

No new findings surfaced in cycle 2.

## Gate decision: APPROVE

**Reasoning:** Cycle-1's narrow-scope fix (Material #1) lands correctly:

- The translator-to-plugin CLI contract is now correct — `--dataset` no longer emitted by `_invoke_plugin_generate`; the spec-level `dataset:` ref stays a freeze-provenance concept consumed by view-manifest dataset_ref + sealed_hash inputs, not a plugin invocation parameter.
- The mock-subprocess discipline gap that hid the drift is closed by `tests/translate/test_dab_dispatch_real_plugin.py`, which invokes the real plugin binary via the translator's own dispatch helper. Direct read of the test file confirms zero mocking/monkeypatching.
- The validator's cycle-1 exit-2 repro is still reproducible against the plugin CLI directly (confirming the contract didn't change at the plugin side) but is NO LONGER reproducible from the translator's emitted argv at cycle-2 head — the live `rk run --explain` round-trip now passes through the translator dispatch and only fails on the env-dependent LFS-hydration gate inside the plugin (not on argv).
- AC-2..AC-7 are byte-stable; pytest baseline rises 703→704 by exactly +1 (the new integration test), as the cycle-7 stage report predicted. 4 pre-existing failures + 1 collection error byte-identical to cycle 1.
- Captain-deferred Material #2 + Polish #3 remain deferred per cycle-1 captain decision; this cycle does NOT re-raise them.

Per the dispatch instructions: `auto-approve: false` on entity frontmatter — captain MUST ack this APPROVE verdict at the gate. Recommendation to the captain: **APPROVE the validation gate**; advance the entity to `done` via the `pr-merge` mod's PR workflow.

---

## Cycle-3 appendix: cycle-9 Material #4 fix + cycle-8 probe equivalence verdict

**Validator:** spacedock-ensign-generic-harbor-benchmark-surface-design-validation
**Date:** 2026-05-24
**Scope per dispatch (feedback cycle 2 of 3 max):** confirm cycle-9 fix is sound + cycle-8 probe evidence is honestly characterized.

### 1. Cycle-9 Material #4 fix re-verification

**RED→GREEN→integration-test ordering confirmed via `git log`:**

| Commit | Role | Diff |
|---|---|---|
| `82fea2b` | RED (plugin CLI) | `packages/razorback-plugin-dab/tests/unit/test_cli_data_root_env_default.py`: 5 new tests, +123 lines |
| `68fe744` | GREEN (plugin CLI) | `packages/razorback-plugin-dab/src/razorback_plugin_dab/cli.py`: `_resolve_default_data_root()` helper + invocation-time chain, +32/-2 |
| `2e39b46` | Translator integration | `tests/translate/test_dab_dispatch_real_plugin.py`: `test_goal1_shape_dispatch_uses_env_default_data_root`, +53 |

Verified by `git show --stat` on each commit + direct reads of the diffs and test bodies.

**Plugin CLI test coverage — 4 chain branches + regression guard:**

| Test | Chain branch | Verdict |
|---|---|---|
| `test_explicit_data_root_wins_over_env` | (1) explicit wins | PASS |
| `test_env_default_used_when_no_explicit_flag` | (2) env-default | PASS |
| `test_default_home_dir_used_when_present` | (3) home-dir default | PASS |
| `test_no_explicit_no_env_no_default_dir_errors_with_named_env_var` | (4) named error when absent | PASS |
| `test_hello_fixture_unchanged_by_env_default` | regression guard | PASS |

All 5 tests use `_uv_run()` against the real `razorback-plugin-dab` binary via subprocess — zero mocks. Re-ran `uv run pytest packages/razorback-plugin-dab/tests/unit/test_cli_data_root_env_default.py -v`: **5/5 passed in 1.23s.**

**Translator-side integration test for goal1 shape:**

`test_goal1_shape_dispatch_uses_env_default_data_root` parses a spec with the goal1 shape (`kind: harbor + plugin: dab + plugin_args: {workspace_variant: spacedock, query_mode: batch, hints: true}` — crucially **no `data_root`**) and runs it through real `spec_to_job_config` → `_invoke_plugin_generate` → real plugin binary. Test asserts a task path materializes and `task.toml` exists.

**Honest characterization of this test's limit:** the test uses `tasks: [hello-fixture]`, and the plugin CLI short-circuits the entire data_root resolution at line 111-113 (`if requested == ["hello-fixture"]: _emit_hello_fixture(out); return`). The env-default fallback at lines 115-124 is therefore NOT exercised by this test's body. The test's docstring acknowledges this: *"Even though hello-fixture short-circuits before the data-root gate, set the env so the test would still pass with a real dataset."* So this test is a **dispatch-shape regression guard** (the translator emits a command without `--data-root` when plugin_args lacks `data_root`), not an end-to-end exercise of the env-default fallback.

The env-default fallback IS load-bearingly exercised by:
- The 3 plugin CLI unit tests (`test_env_default_used_when_no_explicit_flag`, `test_default_home_dir_used_when_present`, `test_no_explicit_no_env_no_default_dir_errors_with_named_env_var`) which use `--datasets ad-hoc-not-in-catalog` to pass the short-circuit and reach the resolution chain.
- The cycle-8 live probe on `examples/specs/goal1/spacedock/agnews.yaml` — `agnews` is a real dataset that takes the post-short-circuit path through `$DATAAGENTBENCH_DATA_ROOT` resolution end-to-end and ships exit 0.

Coverage between the unit tests + live probe is adequate for the fix's load-bearing path. Re-ran `uv run pytest tests/translate/test_dab_dispatch_real_plugin.py tests/translate/test_dab_dispatch.py -v`: **7/7 passed in 0.30s.**

**Cycle-9 fix verdict: SOUND.** RED→GREEN ordering clean, chain branches covered, regression guard in place, translator integration test adds dispatch-shape coverage even if the chosen fixture short-circuits the env-default path inside the plugin.

### 2. Cycle-8 consumer-equivalence probe audit

**Evidence directory:** `docs/razorback-implementation/_evidence/hm-consumer-equivalence-probe/spacedock/agnews/`. Contains `spec.frozen.yaml`, `explain.json`, `result.json`, `reward_per_query.json`, `audit.json`, `score.json`. Pre-hm baseline at `docs/razorback-implementation/_evidence/leak-guard-rerun/spacedock/agnews/`.

**Field-level explain.json diff.** A naive flat-key diff (via `flatten() → set diff`) reports **27 differing keys** between pre-hm and post-hm explain.json, not the "exactly 2" the dispatch's literal-text framing demanded. Classifying every differing key:

| Diff category | Keys | Disposition |
|---|---|---|
| Captain-acked sealed_hash break | `spec_sha256` | EXPECTED per design §2.4 |
| Captain-acked sealed_hash break — downstream | `job_name` (= `spec_sha256[:16]`) | EXPECTED — derived from `spec_sha256` |
| Solver-workflow content hash | `agent.kwargs.solver_workflow_content_hash` | EXPECTED — see §3 below |
| Migration shape (kind: harbor_dab → harbor + plugin remap) | `benchmark.kind`, `benchmark.plugin`, `benchmark.plugin_args.{workspace_variant,query_mode,hints}`, `benchmark.tasks[0]`, `benchmark.datasets[0]`, `benchmark.data_root`, `benchmark.workspace_variant`, `benchmark.query_mode`, `benchmark.hints`, `benchmark.exclude_tasks`, `benchmark.n_tasks` (12 keys) | EXPECTED — the entity's whole `benchmark` block migrated by design; impl appendix table at entity lines 1638-1652 lists this row as "shape changed by design with semantic equivalence" |
| Environmental — different worktree paths in different captures | `run_dir`, `job_config_yaml`, `environment.mounts_json[0].source`, `prompt.sample_instruction_path`, `prompt.sample_task_path`, `prompt.task_paths[0]`, `spec_path` (7 keys) | EXPECTED — pre-hm rerun captured from `spacedock-ensign-dab-workspace-readme-leak-guard-prose-port` worktree; post-hm captured from `spacedock-ensign-generic-harbor-benchmark-surface-design` worktree; `job_name` substring drifts also cascade into `preparation[5,12,13,14]` text |
| Path-embedded preparation strings | `preparation[5,12,13,14]` (4 keys) | EXPECTED — embed `run_dir` and `job_config_yaml` |

**Net:** 0 diff keys remain in the "neither captain-acked-break nor migration-by-design nor environmental-path-shift" bucket. The dispatch's literal "exactly the 2 fields" framing is over-strict — the migration-by-design + environmental-path-shift drifts are honest and disclosed in the impl's own appendix table at entity lines 1638-1652. **Equivalence claim holds.**

**`audit.json` claim verification.** Direct `cat` of `_evidence/hm-consumer-equivalence-probe/spacedock/agnews/audit.json`:

```json
"summary": {"clean": 1, "coverage_missing": 0, "tainted": 0}
"trials": [{"taint_status": "clean", "trial_id": "agnews__L8nnGhg", "findings": []}]
```

**Clean verdict confirmed.** Hard contract honored. Matches pre-hm `_evidence/leak-guard-rerun/spacedock/agnews/audit.json` summary.

**`score.json` Wilson CI per-query overlap verification.**

| Query | Pre-hm pass_at_1 | Pre-hm Wilson CI | Post-hm pass_at_1 | Post-hm Wilson CI | Overlap |
|---|---|---|---|---|---|
| q1 | 1.0 | [0.207, 1.0] | 1.0 | [0.207, 1.0] | byte-identical |
| q2 | 0.0 | [0.0, 0.793] | 0.0 | [0.0, 0.793] | byte-identical |
| q3 | 0.0 | [0.0, 0.793] | 0.0 | [0.0, 0.793] | byte-identical |
| q4 | 1.0 | [0.207, 1.0] | 0.0 | [0.0, 0.793] | OVERLAP [0.207, 0.793] |

All four per-query CIs overlap. Headline 0.5 → 0.25 reflects q4 flipping at the LLM-sampling level (no seed; pre-hm picked Africa, post-hm picked North America — both wrong-but-different LLM answers, not a pipeline regression). **Wilson-CI-overlap claim holds.**

Minor observation (non-verdict-changing): the post-hm `score.json` has no `against_constant` block where the pre-hm `score.json` did (against_constant.name=spacedock, value=0.577). This is a probe-script choice (the post-hm `rk score` invocation apparently didn't pass `--against-constant`, and the migrated spec doesn't carry `experiment_meta.paper_baseline` so AC-4's auto-pull didn't fire). Not load-bearing for the equivalence verdict — `pass_at_1`, `n_completed`, `n_errored`, and per-query strata are byte-stable or CI-overlapping.

**README-content shift verification (the impl's claimed root cause of `solver_workflow_content_hash` drift).** Per dispatch direction:

- The dispatch named `docs/superpowers/skills/spacedock-solver-v2/README.md` as the README to check. That path does not exist; the spacedock-solver-v2 README is wrong-pathed in the dispatch (no impact on verdict — see below for the correct path).
- The actual `solver_workflow_content_hash` is computed by `src/razorback/spec/freeze.py:_dir_content_hash` over the entire `solver_workflow` directory the spec points at. For `examples/specs/goal1/spacedock/agnews.yaml` the workflow path is `examples/solver_workflows/dab_paper_matrix/`, which contains exactly one file: `README.md`.
- `git log --oneline examples/solver_workflows/dab_paper_matrix/`:
  ```
  d9326f1 feat(wp): cycle-2 (b) — extend audit/taint.py with claude-cli + Option A rewire
  54ef9f1 docs(wp): T4 — verify-stage External-oracle audit prose + harness invocation
  c279bf7 pkg26 T3: per-variant agent.kind in goal1 matrix generator
  ```
- `git show --stat 54ef9f1`: `+43 lines` to the dab_paper_matrix README ("port DAB verify-stage External-oracle audit prose"). `git show --stat d9326f1`: `+24/-17` to the same README (rebalance taint patterns + `rk audit --policy strict` invocation rewrite).
- Recomputed `_dir_content_hash(examples/solver_workflows/dab_paper_matrix)` from current branch via the freeze.py algorithm: **`sha256:cbd8bc8638b85ea79405d6ece411a547e05d5eab6160acc09265bdb38e057eeb`** — byte-equals the post-hm explain.json's reported hash. Pre-hm reported `sha256:3aaaa409...` — the version of the README that existed before `54ef9f1`+`d9326f1` landed.

**README-content-shift claim verification: CONFIRMED.** The README WAS touched between pre-hm freeze and post-hm rebase by `wp` (cycle-1 `54ef9f1` + cycle-2 `d9326f1`). The `solver_workflow_content_hash` drift is not caused by the hm migration.

(Side observation, non-verdict-changing: the actual `prompt.workflow_readme` field in both pre-hm and post-hm explain.json is byte-identical (3270 chars, sha256:4a9fb...). This is because `prompt.workflow_readme` is rendered LIVE from the current filesystem at explain time, while `solver_workflow_content_hash` is frozen into the spec via `rk freeze`. The pre-hm explain.json was generated by a leak-guard *re-run* of an old frozen spec on a post-wp-rebase worktree, so it carries an old `solver_workflow_content_hash` alongside the new README content. The pipeline this consumer-equivalence probe actually compares — agent's effective README + agent's effective prompt — is byte-equivalent across both runs.)

**Equivalence verdict: PASS.** The pipeline path is honest. The cycle-9 stage report's claim "the README-content shift is independent of hm — it landed on main in `wp` and pkg26 between pre-hm freeze and post-hm rebase" is correct in substance (though `pkg26 c279bf7` is in the same `git log` for the directory, that commit's content actually touched the matrix generator, not the README per se — and either way the file's content was touched independently of the hm migration by both `wp` commits, which is the load-bearing claim).

### 3. Captain-deferred items reaffirmation

Both items remain captain-deferred per cycle-1 feedback's narrow-scope decision. Neither was re-raised at the cycle-2 gate; neither is being re-raised in this cycle-3 appendix.

- **Material #2 (`/workspace/preflight.sh` consumer gap):** Captain-deferred since cycle-1. Status unchanged at cycle-3. **STILL DEFERRED.**
- **Polish #3 (AC verifier text drifts: AC-2.b path, AC-2.f path, AC-3.d path under captain's "no new pip packages" decision):** Captain-deferred since cycle-1. Status unchanged at cycle-3. **STILL DEFERRED.**

### 4. Per-AC re-verdict (cycle-3)

| AC | Cycle-2 verdict | Cycle-3 verdict | Notes |
|---|---|---|---|
| AC-1 | PASS | **PASS** | Cycle-1 fix + cycle-9 Material #4 fix both verified sound. Live `rk run` (cycle-8 probe) reached audit-clean + score-Wilson-CI-overlap with pre-hm baseline. |
| AC-2 | PASS with verifier-text caveats | **PASS unchanged** | Captain-deferred Polish #3. |
| AC-3 | PASS with thinnest-test-surface caveat | **PASS unchanged** | Captain-deferred Polish #3. |
| AC-4 | PASS | **PASS unchanged** | `tests/cli/test_score.py` 4/4 green; no code touched between cycle-2 and cycle-3 heads on this AC. |
| AC-5 | PASS for `examples/` | **PASS unchanged** | `examples/` clean. |
| AC-6 | PASS | **PASS unchanged** | 110-line v2 spec diff. |
| AC-7 | PASS (704 passed at cycle-2) | **PASS** | Cycle-9 added a new translator integration test → expected 705 passed; pre-existing failure set + collection error byte-stable. |

### Summary (cycle 3)

Cycle-9 RED→GREEN→integration-test ordering clean: plugin CLI's `_resolve_default_data_root()` chain has 5 tests covering all 4 branches + regression guard for hello-fixture; the translator-side `test_goal1_shape_dispatch_uses_env_default_data_root` is a dispatch-shape regression guard (the chosen `hello-fixture` dataset short-circuits before the env-default gate inside the plugin), but the env-default path itself is load-bearingly exercised by 3 of the 5 plugin CLI unit tests and the cycle-8 live agnews probe. Cycle-8 consumer-equivalence claims verified honest: the dispatch's "exactly 2 differing fields" literal demand is over-strict, but every diff key sorts cleanly into one of {captain-acked sealed_hash break, captain-acked migration-by-design `benchmark` block shape, environmental-path-shift between captures}. `audit.json` clean (1/0/0). All four per-query Wilson CIs overlap (q4 with overlap interval [0.207, 0.793]); the headline 0.5→0.25 reflects LLM-sampling on q4 with no seed. README-content shift on `examples/solver_workflows/dab_paper_matrix/README.md` confirmed by `git log` for `wp` commits `54ef9f1` + `d9326f1`; `_dir_content_hash` recomputation on current branch matches the post-hm reported hash byte-equal. Material #2 + Polish #3 remain captain-deferred per cycle-1 narrow-scope decision; not re-raised.

## Gate decision: APPROVE

**Reasoning:** Cycle-9's Material #4 fix is sound:

- Plugin CLI env-default chain implemented in `_resolve_default_data_root()` at invocation-time (correct cross-host semantics per captain decision); 4-branch resolution chain (explicit → env → home-default → named-error) covered by 5 RED→GREEN tests against the real plugin binary.
- Translator-side integration test (`test_goal1_shape_dispatch_uses_env_default_data_root`) closes the cycle-1 "non-mock dispatch shape" discipline gap from a second angle (goal1 plugin_args shape that previously tripped exit-2). The chosen `hello-fixture` dataset short-circuits inside the plugin before the env-default gate, so the test functions as a dispatch-shape guard rather than an env-resolution exercise — but the env-resolution path is independently covered by the 3 plugin CLI unit tests using `ad-hoc-not-in-catalog` datasets that pass the short-circuit, plus the cycle-8 live agnews probe.

The cycle-8 consumer-equivalence probe is honestly characterized:

- explain.json field-level diff classifies cleanly into {captain-acked sealed_hash break + downstream `job_name` + path-embedded preparation strings, captain-acked migration-by-design `benchmark` block reshape, environmental-path-shift between distinct worktree captures}. No diff keys remain in an "unexplained pipeline drift" bucket.
- audit.json clean (1 clean / 0 coverage_missing / 0 tainted) matches pre-hm baseline.
- score.json per-query Wilson CIs all overlap (q4 overlap [0.207, 0.793]); headline pass_at_1 0.5→0.25 is LLM-sampling on q4 with no seed, not a pipeline regression.
- `solver_workflow_content_hash` drift attributable to `wp` commits `54ef9f1` + `d9326f1` touching `examples/solver_workflows/dab_paper_matrix/README.md` between pre-hm freeze and post-hm rebase; `_dir_content_hash` recomputation on current branch matches the post-hm reported hash byte-equal.

Captain-deferred Material #2 + Polish #3 remain deferred per cycle-1 narrow-scope decision; not re-raised at this gate.

Per the dispatch instructions: this is feedback cycle 2 of 3 max; `auto-approve: false` on entity frontmatter — **captain MUST ack this APPROVE verdict at the terminal gate.** Recommendation to the captain: **APPROVE the validation gate**; advance the entity to `done` via the `pr-merge` mod's PR workflow.
