# Razorback v2 test inventory

**Date:** 2026-05-20
**Scope:** Every test file under `tests/` as of commit a2e9c49
**Resolves:** AC-0.14 in 2026-05-19-razorback-reconciliation-plan.md
**Companion:** 2026-05-19-razorback-inventory.md (AC-0.10, pending — produced by sibling module-inventory agent)

## Reading guide

Labels per AC-0.14:

- **KEEP-VERBATIM** — survives unchanged in v2, only import paths may be re-pointed.
- **RE-AUTHOR** — intent survives but the test needs new framing (e.g., dump-file → live-DB,
  in-tree adapter → harbor-DAB adapter, v1 `SpacedockSolverAgent` → v2 runtime adapter).
- **DROP** — exclusively exercises a v1 module marked DROP in the module inventory.
- **PORT-OUT** — exercises behavior that moves to `packages/razorback-plugin-dab/` (the DAB
  harbor adapter) or another sibling package; test goes with the code.

Module-inventory (AC-0.10) classifications relied on by this doc are derived from the v2 spec
itself (sections 3, 4, 6, 7, 8) and the reconciliation plan's per-phase ACs. Where a module's
classification could be either ADAPT-EXTRACT or DROP, I record `RE-AUTHOR (pending
module-inventory)` and note the uncertainty. The companion AC-0.10 doc is authoritative when
it lands.

## Summary table

| Test file | Classification | LoC | Modules exercised | Notes |
|---|---|---|---|---|
| tests/conftest.py | KEEP-VERBATIM | 24 | (shared fixtures) | colima_safe_tmp_path fixture survives — used by any docker-touching test. |
| tests/__init__.py | KEEP-VERBATIM | 0 | n/a | empty marker |
| tests/integration/__init__.py | KEEP-VERBATIM | 0 | n/a | empty marker |
| tests/unit/__init__.py | KEEP-VERBATIM | 0 | n/a | empty marker |
| tests/integration/test_ade_bench_claude_smoke.py | RE-AUTHOR | 52 | rk CLI, in-tree ade-bench adapter | v2 path is harbor-ade-bench adapter (Phase 8 reach); same smoke shape applies, retargeted spec. |
| tests/integration/test_dab_dev_claude_full.py | RE-AUTHOR | 82 | rk CLI, in-tree DAB adapter, full 12-dataset | retarget at harbor-DAB adapter; v2 lifts AC into the matrix dispatcher (AC-4a.12) + AC-4a.13 smoke. |
| tests/integration/test_dab_workflow_lifecycle.py | RE-AUTHOR | 102 | rk CLI, in-tree DAB adapter, workflow lifecycle | v2 equivalent is AC-5.4 (template-driven hypothesis smoke); recompose against Phase 5 templates + harbor-DAB. |
| tests/integration/test_no_auth_leak_in_run_dir.py | KEEP-VERBATIM | 150 | rk run, auth resolution (`extra_env`), provenance writes | FU-1 AC-1 leak test. Auth-redaction discipline survives wholesale into v2 (spec §6.2 + Phase 3 extractions AC-3.4); retarget at v2 `rk run` path. Sentinel-grep mechanic is benchmark-agnostic. |
| tests/integration/test_rk_run_bookreview_claude.py | RE-AUTHOR | 66 | rk run, in-tree DAB adapter, claude-cli agent | v2 retargets at the v2-class × harbor-DAB smoke (AC-4a.13); the assertion shape (summary.json + bookreview pass@1 > 0) survives, the adapter under it changes. |
| tests/integration/test_rk_run_bookreview_nop.py | RE-AUTHOR | 76 | rk run, in-tree DAB adapter, nop agent | Same as above, nop-runtime variant. v2 equivalent uses harbor's nop or claude_code-stub against harbor-DAB. |
| tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py | RE-AUTHOR | 58 | rk run, v1 `SpacedockSolverAgent`, in-tree DAB | v2 halt-resume is hand-faked smoke (AC-3.6) plus deferred real-mod validation. Re-author against `spacedock_solver_v2` discriminator + AC-3.6 contract. |
| tests/integration/test_rk_run_nop.py | KEEP-VERBATIM | 102 | rk run, nop agent, manifest.json shape | AC-1..AC-8 smoke against the simplest agent. Survives directly: v2 still has `rk run` against a nop agent producing a run-dir + manifest. |
| tests/integration/test_spacedock_git_freeze.py | RE-AUTHOR | 143 | v1 `SpacedockSolverAgent`, `seal.compute_sealed_hash`, `prompt_sha256`, agent_freeze/.git layout | Sealed-hash + workspace-snapshot mechanism survives (AC-3.4 extracts `compute_sealed_hash` + `prompt_sha256`); test retargets at v2 class. Halt-resume real-mod path defers (§5.2). |
| tests/unit/test_ade_bench_aggregate.py | RE-AUTHOR | 60 | `razorback.benchmarks.ade_bench.aggregate` | The in-tree ade-bench aggregator is replaced by harbor-ade-bench-adapter + razorback's `rk score` stratified mean. Same intent (mean reward → numeric `score`); new shape lives in `rk score` tests. |
| tests/unit/test_ade_bench_materialize_git_task.py | PORT-OUT | 128 | `razorback.benchmarks.ade_bench.tasks.materialize_git_task` | FU-2 AC-1. The `materialize_git_task` mechanism is benchmark-runner concern; in v2 it moves to the harbor ade-bench adapter package. Test goes with the code. |
| tests/unit/test_ade_bench_missing_tool_graceful_error.py | RE-AUTHOR | 57 | `ClaudeCliAgent` (v1) | FU-2 AC-4 graceful-error contract survives, but routes through v2's per-runtime adapter sub-module (`agents/_runtime/claude.py`) wrapping harbor's installed `claude_code`. Re-frame the typed-error assertion against the v2 surface. |
| tests/unit/test_ade_bench_schema_docker_image_override.py | PORT-OUT | 51 | `razorback.spec.schema.AdeBenchBenchmarkBlock` | FU-2 AC-2. `docker_image_override` is benchmark-config schema; v2's `rk run` passes through to harbor and the override semantics live on the harbor ade-bench adapter's task config. Schema test moves with adapter. |
| tests/unit/test_ade_bench_schema_git_tasks.py | PORT-OUT | 110 | `razorback.spec.schema.AdeBenchBenchmarkBlock`, `AdeBenchTaskEntry` | FU-1 AC-3. Same reasoning: git-task entry shape is harbor TaskConfig territory. Adapter owns the schema in v2. |
| tests/unit/test_ade_bench_schema.py | PORT-OUT | 66 | `razorback.spec.schema.AdeBenchBenchmarkBlock` | ade-bench schema entirely; harbor's ade-bench adapter owns it. Drops from razorback's surface. |
| tests/unit/test_ade_bench_tasks_loader.py | PORT-OUT | 46 | `razorback.benchmarks.ade_bench.tasks.resolve_task_dirs` | tasks_root + slug resolution is adapter machinery. Goes with the adapter. |
| tests/unit/test_ade_bench_translator_docker_image_override.py | DROP | 119 | `razorback.compat.spec_to_job_config` | Tests v1 spec→JobConfig translator. v2 razorback does not own JobConfig translation (spec §8.1: "razorback does not own JobConfig construction"); the whole `compat/` module is DROP (Phase 6 AC-6.4 commit 4 sidelines `compat/`). |
| tests/unit/test_ade_bench_translator_git_task.py | DROP | 108 | `razorback.compat.spec_to_job_config` | Same. v1 compat translator drops. |
| tests/unit/test_ade_bench_translator.py | DROP | 50 | `razorback.compat.spec_to_job_config` | Same. v1 compat translator drops. |
| tests/unit/test_baseline_promote_verify.py | DROP | 176 | `razorback.constraints.baseline.promote`/`verify` | `rk baseline promote/verify` is deferred-optional (spec §3.2 "Optional follow-ons"). Plan does not ship `constraints/` or `baseline` in the first cut (D3, deferred); current `src/razorback/constraints/` is DROP/PORT-OUT pending the optional-CLI decision. RE-AUTHOR if D3 ships baseline. |
| tests/unit/test_channel_drainer.py | DROP | 53 | `razorback.observers.{channel,jsonl,stdout}` | `observers/` is DROP per Phase 6 AC-6.4 commit 5 ("harbor's hook system replaces"). The event-channel/single-writer mechanism is harbor's, not razorback's, in v2. |
| tests/unit/test_claude_cli_auth_dotenv_only.py | KEEP-VERBATIM | 75 | `razorback.agents.auth.resolve_claude_auth` | **FU-1 M3 AC-3** — `.env`-via-`dotenv_values` discipline (NOT `os.environ`). AC-1.3 + AC-3.4 explicitly preserve this. Test survives; auth module is KEEP-EXTRACT. |
| tests/unit/test_claude_cli_registry.py | DROP | 32 | `razorback.agents.registry.resolve_agent_kind("claude-cli")` | v2 routes `agent.kind: claude_code` to harbor's installed agent directly; razorback's `claude-cli` agent-kind registry entry is replaced by harbor's catalog (Phase 6 AC-6.4 commit 1). |
| tests/unit/test_claude_cli_required_env.py | DROP | 16 | `ClaudeCliAgent.required_env` | Tests v1 `ClaudeCliAgent` class. v2 replaces with harbor's installed `claude_code` via per-runtime adapter sub-module; the required-env declaration moves with it. The auth-resolution semantics survive via the dotenv test (above). |
| tests/unit/test_claude_cli_setup_env_scrub.py | RE-AUTHOR | 80 | `ClaudeCliAgent.setup`, `extra_env` kwarg | **FU-1 AC-2 + `extra_env` mechanism.** Per AC-3.4: "FU-1 `extra_env` mechanism (auth via harbor's `extra_env` kwarg, env-field redaction on disk)" is explicitly preserved. Intent (auth carried only via `extra_env`, never co-mingled) survives; the assertion shape changes because the agent class moves to per-runtime adapter wrapping harbor's `claude_code`. Re-author against `agents/_runtime/claude.py`. |
| tests/unit/test_claude_cli_supported_sampling.py | DROP | 13 | `ClaudeCliAgent.supported_sampling` | Tests v1 class API. v2 surface is the per-runtime adapter; supported_sampling shape is harbor's concern. |
| tests/unit/test_claude_cli_translator_proxy.py | DROP | 167 | `razorback.compat.harbor_0_6_6.spec_to_job_config`, proxy block stamping | v1 compat translator drops (see ade_bench translator). The proxy-block content survives in the adapter's task config, but not as a razorback-translator concern. |
| tests/unit/test_claude_cli_version.py | DROP | 41 | `ClaudeCliAgent.version` | v1 class API; harbor's installed claude_code reports its own version. |
| tests/unit/test_cli_exit_codes.py | KEEP-VERBATIM | 20 | `razorback.cli.app`, SpecError → exit 10 | Exit-code contract is spec §3.4 surface; SpecError → 10 + usage-error → 2 survives unchanged. v2 grows codes (21, 22, 23) but does not remove these. |
| tests/unit/test_cli_runs_diff.py | RE-AUTHOR | 119 | `rk runs diff` CLI | Subsumed by `rk diff` in v2 spec (§3.2; ships in Phase 4b). The fixture shape (per_trial_outcomes.json + frozen-spec sidecars) survives; the command name changes from `rk runs diff` → `rk diff`. |
| tests/unit/test_cli_validate_per_trial_state_reset.py | DROP | 83 | `rk validate` CLI, ade-bench schema | `rk validate` is not in v2's first-ship surface (§3.2). The `per_trial_state_reset` declaration is harbor-adapter concern; warning moves to adapter validation. |
| tests/unit/test_cli_validate_tools_allowed.py | DROP | 99 | `rk validate` CLI, ade-bench schema, §9.2 warning | Same — `rk validate` not in v2 first-ship; tools_allowed validation moves to harbor-adapter. |
| tests/unit/test_compat_translator.py | DROP | 45 | `razorback.compat.harbor_0_6_6.spec_to_job_config` | Entire `compat/` module DROPs per Phase 6 AC-6.4 commit 4. |
| tests/unit/test_constraints_check.py | DROP | 110 | `razorback.constraints.check.check_spec_against_constraints` | `rk constraints check` deferred-optional (D3); `constraints/` module not in v2 first-ship. RE-AUTHOR if D3 ships constraints. |
| tests/unit/test_dab_aggregate_grep.py | PORT-OUT | 15 | `razorback.benchmarks.dab.aggregate` source grep | DAB aggregator moves to harbor-DAB adapter per AC-2.3. Static "no `stats.evals`" grep goes with it. |
| tests/unit/test_dab_aggregate_twelve_datasets.py | PORT-OUT | 30 | `razorback.benchmarks.dab.aggregate.aggregate_synthetic`, 12-dataset fixture | DAB aggregator → harbor-DAB adapter. Cross-dataset stratification math moves to `rk diff` per AC-2.8 ("razorback's `rk diff` owns the stratified math; benchmark adapter owns stratum tagging"); aggregator-as-such is adapter territory. |
| tests/unit/test_dab_aggregate.py | PORT-OUT | 81 | `razorback.benchmarks.dab.aggregate.aggregate_synthetic` | Same — adapter test. |
| tests/unit/test_dab_per_trial_state_reset.py | PORT-OUT | 12 | `razorback.benchmarks.dab.per_trial_state_reset` | Per-trial-state-reset declaration is the adapter's contract with harbor. Moves to harbor-DAB adapter. |
| tests/unit/test_dab_prepare.py | PORT-OUT | 117 | `razorback.benchmarks.dab.prepare.prepare_dataset_tasks` | DAB prepare logic → harbor-DAB adapter (AC-2.3). Ground-truth.csv non-leakage assertion moves with it. |
| tests/unit/test_dab_spec_parse.py | PORT-OUT | 56 | `razorback.spec.parse`, DAB benchmark block | DAB-specific spec schema → harbor-DAB adapter task-config schema. |
| tests/unit/test_dab_translator_twelve.py | DROP | 90 | `razorback.compat.harbor_0_6_6.spec_to_job_config`, 12-dataset fanout | v1 compat translator drops. The 12-dataset fanout shape is harbor's job-fan-out concern in v2, not razorback's. |
| tests/unit/test_dab_translator.py | DROP | 108 | `razorback.compat.harbor_0_6_6.spec_to_job_config` | v1 compat translator drops. |
| tests/unit/test_dab_verify.py | PORT-OUT | 53 | `razorback.benchmarks.dab.verify.emit_reward` | DAB verifier → harbor-DAB adapter. |
| tests/unit/test_diff_compose.py | RE-AUTHOR | 66 | `razorback.diff.diff.compute_diff` | `rk diff` survives (spec §3.2, ships Phase 4b). Existing implementation is ADAPT-EXTRACT — the JSON shape changes (per AC-4b.2: cluster bootstrap, family-wise correction); test re-frames against the v2 output schema. |
| tests/unit/test_diff_paired_bootstrap_ci.py | RE-AUTHOR | 137 | `razorback.diff.stats.paired_bootstrap_ci` | Paired-bootstrap CI survives, but v2 changes the cluster level (default `query`, per AC-4b.3). Test re-authors against cluster-bootstrap fixture (AC-4b.3 calls out "Cluster-bootstrap fixture is critical"). |
| tests/unit/test_diff_pairing.py | KEEP-VERBATIM | 52 | `razorback.diff.pairing.load_run_outcomes`, `pair_outcomes` | Pairing by `(task, query, trial_index)` is spec §8.3 contract verbatim. Survives unchanged. |
| tests/unit/test_diff_per_trial_outcomes_sidecar.py | RE-AUTHOR | 62 | `razorback.benchmarks.dab.aggregate.aggregate_synthetic`, `per_trial_outcomes.json` sidecar | Sidecar contract survives (it's the diff input). The aggregator that produces it moves to the harbor-DAB adapter, so the test re-authors against the adapter's emitted sidecar shape. |
| tests/unit/test_diff_seed_refusal.py | KEEP-VERBATIM | 53 | `razorback.diff.diff.check_paired_seed_compatibility`, `SeedMismatchError`, exit 20 | Spec §8.3: "rk diff refuses when only one run has a seed set." Exit code 20 stable. Survives unchanged. |
| tests/unit/test_diff_stats_basic.py | KEEP-VERBATIM | 108 | `razorback.diff.stats.{wilson_ci,exact_mcnemar_p,power_mde_at_fixed_n}` | Wilson CI + exact McNemar + power-MDE all survive in v2 per spec §8.3 (`rk diff`) + §8.3a (`rk score` uses Wilson). Hand-computed assertions survive verbatim. |
| tests/unit/test_freeze.py | KEEP-VERBATIM | 40 | `razorback.spec.freeze.freeze_spec`, parse | M1 frozen-spec writer; AC-1.3 + spec §3.3 stability promise preserve this. Survives. |
| tests/unit/test_job_name.py | KEEP-VERBATIM | 31 | `razorback.spec.freeze.derive_job_name` | job_name = sha256(frozen-spec)[:16] is content-derived determinism the matrix dispatcher relies on (AC-4a.12: "idempotent on `rk run`'s `(jobs_dir, job_name)` content-hash determinism"). Survives. |
| tests/unit/test_manifest.py | KEEP-VERBATIM | 34 | `razorback.manifest.write_manifest`, RUN_DIR_VERSION | Run-dir manifest shape; spec §7 declares razorback adds `spec.frozen.yaml` + `provenance.yaml` to the run-dir; manifest.json is the harbor-side anchor razorback writes through (AC-1.3 "run-dir creation helpers — path conventions, manifest write" preserved). Survives. |
| tests/unit/test_provenance_alias_drift.py | KEEP-VERBATIM | 81 | `razorback.provenance.drift.check_alias_drift`, `AliasDriftError`, exit 21 | Spec §3.4 + §8.1: alias-drift refusal at exit 21. AC-1.3 explicitly preserves "alias-drift detection". Survives. |
| tests/unit/test_provenance_harbor_drift.py | KEEP-VERBATIM | 36 | `razorback.provenance.drift.check_harbor_drift`, `HarborDriftError` | Spec §8.2: "major-version drift between freeze and `harbor run` is a hard error." Survives. |
| tests/unit/test_provenance_refuses_missing.py | KEEP-VERBATIM | 64 | `razorback.provenance.provenance_yaml.refuse_if_any_unresolved`, `ProvenanceError`, exit 11 | Spec §3.4 exit 11; `rk freeze` refuses on unresolved fields per §3.2. Survives. |
| tests/unit/test_provenance_resolvers.py | KEEP-VERBATIM | 160 | `razorback.provenance.resolvers.*` (6 resolvers) | Per AC-4a.5: "Provider model-version resolution, Docker image digest pinning, agent CLI binary hashing, prompt content hashing, all extracted from current `provenance/` with attribution." All 6 resolvers KEEP-EXTRACT; tests survive verbatim. |
| tests/unit/test_provenance_retry.py | KEEP-VERBATIM | 71 | `razorback.provenance.retry.retry_with_backoff` | Per AC-0.10 callout: "retry/backoff against provider 503s, provider-specific error-class taxonomy, Anthropic 503 patterns vs OpenAI auth-vs-org-quota distinctions" is named for preservation. Survives. |
| tests/unit/test_provenance_yaml.py | KEEP-VERBATIM | 64 | `razorback.provenance.provenance_yaml.write_provenance_yaml` | provenance.yaml writer + shape stability per spec §3.3. Survives. (v2 adds fields per AC-4a.4 — `solver_workflow_hash`, `spacedock_skill_version`, `harbor_agent_kwargs_hash` — additive within major version; existing assertions remain valid.) |
| tests/unit/test_reconcile_run_workflow.py | KEEP-VERBATIM | 142 | `razorback.runtime.reconcile.reconcile_run_workflow` | Run-workflow reconciliation logic (spec §5.2: dispatch make-up runs until target trial count met). Survives. |
| tests/unit/test_registry_resolve.py | DROP | 67 | `rk registry` CLI | `rk registry` is deferred-optional (D3, spec §3.2). Not in v2 first-ship. |
| tests/unit/test_run_drift_wired.py | KEEP-VERBATIM | 86 | `rk run` wires alias-drift + harbor-drift before `Job.create` | AC-1.2 verbatim: "runs alias-drift pre-check... refuses with `AliasDriftError` on drift". Test asserts the wiring is in place. Survives, retargeted at v2 `rk run`. |
| tests/unit/test_runs_diff_cross_benchmark_refusal.py | RE-AUTHOR | 73 | `razorback.diff.diff.check_paired_benchmark_kind`, `BenchmarkMismatchError` | Cross-benchmark refusal survives in v2 `rk diff` (sensible invariant). The error class location may move; assertion shape stays. |
| tests/unit/test_spacedock_cli_seed_mismatch_exit_code.py | RE-AUTHOR | 117 | `rk run` against resume spec, sealed_hash mismatch → exit 20 | Spec §3.4 exit 20 (`SeedMismatchError`) survives. v2 routes via `spacedock_solver_v2` discriminator (AC-3.2); test re-authors against the v2 class but the exit-code contract is identical. |
| tests/unit/test_spacedock_no_agent_dir_writes.py | RE-AUTHOR | 49 | static grep on razorback source: no writes under `agent_dir/` | The "all razorback-owned state lives under logs_dir/agent_freeze/" invariant survives verbatim (spec §7.1: "logs_dir/agent_freeze/ is the only razorback-owned subtree under harbor's run-dir layout"). The grep set updates to v2 paths (v2 agent class location); intent unchanged. |
| tests/unit/test_spacedock_phase_stats.py | KEEP-VERBATIM | 45 | `razorback.agents.spacedock_solver.assert_phase_stats_schema` | Spec §7.2 + §4.3: `assert_phase_stats_schema` is surfaced by `SpacedockSolverAgent` for downstream consumers. AC-3.4 explicitly extracts this. Note: v2 §7.2 adds three token fields (`tokens_reasoning`, `tokens_cache_read`, `tokens_cache_write`) — test fixture may need additive field updates; mark KEEP-VERBATIM at intent level but a minor fixture refresh is needed at execution time. |
| tests/unit/test_spacedock_prompt_drift.py | RE-AUTHOR | 73 | v1 `SpacedockSolverAgent` prompt-content hash refusal | Hash-refusal mechanism survives (sealed-input hash includes prompt content hashes per spec §4.3). v2 class lives at `agents/spacedock_solver_v2.py` (AC-3.2); test re-authors against the v2 class. |
| tests/unit/test_spacedock_registry.py | RE-AUTHOR | 105 | v1 agent registry `spacedock-solver` kwargs schema | v2 routes via harbor entry-point or `rk run` translation (D1/AC-3.7). Razorback's pydantic schema for the `spacedock_solver` agent block (§6.2) survives (AC-4a.11 plumbs `tools_denied`); test re-authors against v2 schema path. |
| tests/unit/test_spacedock_seed_mismatch.py | RE-AUTHOR | 153 | v1 `SpacedockSolverAgent.__init__` sealed_hash mismatch refusal | Same as `test_spacedock_prompt_drift.py`. AC-3.6 explicitly: "refuses with `SeedMismatchError` (exit 20) when a sealed input is perturbed." Re-author against v2 class. |
| tests/unit/test_spacedock_tools_allowed.py | RE-AUTHOR | 132 | v1 `SpacedockSolverAgent.setup`, DISALLOWED_TOOLS, MCP server filtering | tools_allowed/tools_denied semantics survive (spec §6.2 + AC-4a.11). DISALLOWED_TOOLS constant location moves (benchmark adapter publishes it per spec §6.2 "benchmark adapter publishes a recommended list as documentation"). Re-author against v2 class + spec-level `tools_denied` field. |
| tests/unit/test_spec_freeze_cli.py | KEEP-VERBATIM | 110 | `rk spec freeze` CLI surface | Spec §3.2 `rk freeze` survives verbatim. (v2 spec collapses `rk spec freeze` → `rk freeze` per §3.2; the CLI command name in the test may need a one-line update, but the assertion shape is unchanged. KEEP-VERBATIM treating the command-name update as the "re-pointing" AC-0.14 permits.) |
| tests/unit/test_spec_freeze_prompts.py | KEEP-VERBATIM | 80 | `razorback.spec.freeze.freeze_spec`, prompt-hash + embed | Prompt content hashing + embedding survives (spec §8.2; AC-4a.5 extracts prompt content hashing). Survives. |
| tests/unit/test_spec_parse.py | KEEP-VERBATIM | 48 | `razorback.spec.parse.parse_spec_text`, M1 spec shape | Core spec-parsing survives (spec §6); the M1 valid spec is a v2-valid subset (nop agent + local benchmark). Survives. |
| tests/unit/test_workflow_markdown_shape.py | RE-AUTHOR | 42 | `examples/workflows/dab-claude/README.md` references rk commands | v2 workflow templates live at `docs/templates/{experiment,run}-workflow/README.md` (spec §5; Phase 5 AC-5.2). Re-author against the new template locations + spec §5 stage names. |

## FU-1 / FU-2 acceptance tests

This subsection explicitly classifies every test that exercises FU-1 (image-override / auth /
extra_env / dotenv discipline) or FU-2 (git-task materialization / image-override schema)
contracts. Per AC-0.14: KEEP-VERBATIM unless the target behavior moves to the DAB harbor
adapter (then PORT-OUT).

| Test file | FU | Classification | Rationale |
|---|---|---|---|
| tests/integration/test_no_auth_leak_in_run_dir.py | FU-1 AC-1 | KEEP-VERBATIM | Auth-leak grep over run-dir is razorback's surface (spec §6.2 `extra_env` + on-disk redaction; AC-3.4 extraction). Stays in razorback's test tree, re-pointed at v2 `rk run`. |
| tests/unit/test_claude_cli_auth_dotenv_only.py | FU-1 M3 AC-3 | KEEP-VERBATIM | `.env`-via-`dotenv_values` discipline is the razorback-owned auth-resolution contract (AC-1.3 explicit). Survives in razorback. |
| tests/unit/test_claude_cli_setup_env_scrub.py | FU-1 AC-2 | RE-AUTHOR | `extra_env` mechanism survives in razorback (AC-3.4); the `ClaudeCliAgent` class itself moves to per-runtime adapter wrapping harbor's `claude_code`. Razorback retains the test, re-authored against the v2 adapter path. **NOT PORT-OUT**: the env-scrub contract is razorback's runtime-adapter responsibility, not the benchmark adapter's. |
| tests/unit/test_ade_bench_materialize_git_task.py | FU-2 AC-1 | PORT-OUT | `materialize_git_task` is benchmark-runner machinery — git-fetch + rewrite the task's `docker_image` line. In v2 this lives in the harbor ade-bench adapter package; the test goes with it. |
| tests/unit/test_ade_bench_schema_docker_image_override.py | FU-2 AC-2 | PORT-OUT | `AdeBenchBenchmarkBlock.docker_image_override` is benchmark-config schema. Harbor adapter owns it in v2. |
| tests/unit/test_ade_bench_translator_docker_image_override.py | FU-2 AC-2 | DROP | Tests the v1 `compat.spec_to_job_config` translator path (a DROP module per Phase 6 AC-6.4). The image-override behavior survives via the adapter (the PORT-OUT schema test above), so the translator-specific assertions drop without behavior loss. |
| tests/unit/test_ade_bench_schema_git_tasks.py | FU-1 AC-3 | PORT-OUT | `AdeBenchTaskEntry` git-task schema is harbor TaskConfig territory; harbor ade-bench adapter owns it. |
| tests/unit/test_ade_bench_translator_git_task.py | FU-2 | DROP | v1 compat-translator path drops; git-task materialization behavior survives via the PORT-OUT `materialize_git_task` test (above). |
| tests/unit/test_ade_bench_missing_tool_graceful_error.py | FU-2 AC-4 | RE-AUTHOR | The typed-error-naming-the-binary contract survives, but the agent class moves to the v2 per-runtime adapter. Razorback retains the test; re-authored. |

## Coverage cross-check

- Every `tests/**/*.py` file appears above: **YES** (77 files total: 4 marker/conftest
  files (`tests/__init__.py`, `tests/conftest.py`, `tests/integration/__init__.py`,
  `tests/unit/__init__.py`), 9 integration test files, 64 unit test files; each appears as
  one row in the summary table).
- Every FU-1 / FU-2 acceptance test classified: **YES** (9 tests across the two FU groups,
  each individually labeled with rationale).

## Classification totals

Counts taken directly from the summary table (one row per `tests/**/*.py` file):

| Label | Count | Notes |
|---|---|---|
| KEEP-VERBATIM | 26 | Core CLI exit codes, provenance freeze + drift + resolvers + retry, manifest, spec.parse, spec.freeze, diff stats/pairing/seed-refusal, FU-1 dotenv + leak-grep, run-workflow reconciler, phase-stats schema (with minor fixture refresh for v2 token-field additions), `__init__.py` markers, conftest. |
| RE-AUTHOR | 22 | Integration smokes retargeted at v2 (harbor-DAB adapter, v2 agent class), v1-class-based spacedock tests retargeted at v2 class, `extra_env` env-scrub against v2 adapter, ade-bench missing-tool against v2 adapter, `rk runs diff` → `rk diff` rename, workflow markdown moved to template locations, diff cluster-bootstrap re-fixturing. |
| DROP | 17 | All `compat/` translator tests (v1 spec → JobConfig), v1 `ClaudeCliAgent` API tests (registry/required-env/supported-sampling/version), `rk validate` tests, `rk registry` / `baseline promote-verify` / `constraints check` (deferred-optional D3), observer/event-channel (harbor's hook system replaces), v1 DAB translator. |
| PORT-OUT | 12 | All `benchmarks/dab/` tests (aggregate, prepare, verify, spec parse, per_trial_state_reset) → harbor-DAB adapter; `benchmarks/ade_bench/` schema + tasks/materialize → harbor ade-bench adapter. (`test_ade_bench_aggregate.py` is RE-AUTHOR rather than PORT-OUT since v2's stratified mean is razorback's `rk score`.) |

**Sum: 26 + 22 + 17 + 12 = 77 entries. ✔** Matches file count exactly.

## Uncertainties tagged for module-inventory resolution

The following entries depend on classifications the companion AC-0.10 doc will make
authoritatively. They are marked `RE-AUTHOR (pending module-inventory)` in the table above
or in adjacent notes; resolution may flip them to KEEP-VERBATIM (no test change) or DROP
(test deletes with the module):

- `test_baseline_promote_verify.py`, `test_constraints_check.py`, `test_registry_resolve.py` —
  the deferred-optional `rk constraints check` / `rk baseline promote-verify` / `rk registry`
  commands are gated by D3. If D3 ships any of them at first-cut, the corresponding tests
  flip from DROP to RE-AUTHOR (or KEEP-VERBATIM if the implementation lifts intact).
- `test_compat_translator.py` and its DAB/ade-bench translator companions are classified DROP
  on the assumption that all of `src/razorback/compat/` is DROP per Phase 6 AC-6.4 commit 4.
  If the module-inventory finds a KEEP-EXTRACT-able piece (unlikely given spec §8.1's
  "razorback does not own JobConfig construction" stance), revisit.
- `test_channel_drainer.py` is classified DROP on the assumption that `observers/` is DROP per
  Phase 6 AC-6.4 commit 5 ("harbor's hook system replaces"). Confirm against module inventory.

## Notes on v2 test-tree shape

Beyond classification, AC-0.14 names the v2 test tree as the destination for KEEP-VERBATIM /
RE-AUTHOR survivors. No new directory layout is mandated here; the existing
`tests/{unit,integration}/` split survives. PORT-OUT tests land in the harbor-DAB adapter
package's own test suite (`packages/razorback-plugin-dab/tests/` per D5, or wherever D5 lands)
or — for the ade-bench items — in the harbor ade-bench adapter's repo (out-of-tree).
