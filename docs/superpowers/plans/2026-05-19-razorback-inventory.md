# Razorback v2 module inventory

**Date:** 2026-05-20
**Scope:** Every module under `src/razorback/` as of commit a2e9c49
**Resolves:** AC-0.10 in 2026-05-19-razorback-reconciliation-plan.md
**Companion:** 2026-05-19-razorback-test-inventory.md (AC-0.14)

This inventory classifies each existing razorback module against the v2 spec
(`docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`). v2 is a
rewrite-from-spec; this document names which proven behavior is extracted
verbatim, which adapts, which drops, and which ports out to a sibling package.

Classification labels:

- **KEEP-EXTRACT** — proven behavior survives in v2 verbatim; v2 imports or
  re-uses with attribution. Cited line ranges are the load-bearing slices.
- **ADAPT-EXTRACT** — the core algorithm survives; signature, surrounding
  scaffolding, or call shape needs change for v2.
- **DROP** — responsibility no longer exists in v2.
- **PORT-OUT** — content moves to a sibling package (DAB → `packages/razorback-plugin-dab/`,
  ade-bench → harbor adapter test suite).

The v1 codebase is built on harbor 0.6.6 directly (a custom JobConfig
translator, custom benchmark adapters baked into razorback). v2 reverses
that: razorback is the thin research-stats layer above `harbor run`, and
benchmark adapters live as published harbor adapters in their own repos. The
inventory reflects that shift: most benchmark-adapter code ports out, the
Spec → JobConfig translator drops (replaced by spec pass-through), but the
freeze-resolver, halt-resume sealed-hash, auth handling, leak guards, and
paired statistics all survive — that is the v2 surface area.

## Summary table

| Module | Classification | LoC | Notes |
|---|---|---|---|
| src/razorback/__init__.py | KEEP-EXTRACT | 4 | package `__version__`; trivial. |
| src/razorback/errors.py | ADAPT-EXTRACT | 35 | ExitCode + RazorbackError + SpecError/SeedMismatch/ConstraintViolation. Add BudgetExceededError(22), TaintFindingsError(23), and rename CONSTRAINT_VIOLATION codepoint usage for v2's `rk constraints` (optional). |
| src/razorback/manifest.py | DROP | 26 | v1 manifest.json is razorback-owned at run-dir root; v2 §7.1 hands run-dir layout to harbor (`spec.frozen.yaml` and `provenance.yaml` are the only razorback artifacts). |
| src/razorback/run.py | DROP | 192 | v1 orchestrates harbor.Job + observers + aggregate. v2 `rk run` shells `harbor run` (§8.1) and never owns JobConfig construction. The drift pre-check survives elsewhere; the rest goes. |
| src/razorback/cli/__init__.py | ADAPT-EXTRACT | 43 | Typer wiring pattern survives; subcommand topology changes (`spec freeze` → `freeze`, drop `validate`, add `score`/`audit`/`runs cost`). |
| src/razorback/cli/__main__.py | KEEP-EXTRACT | 7 | `python -m razorback.cli` shim. |
| src/razorback/cli/run.py | ADAPT-EXTRACT | 34 | Error→exit-code mapping pattern survives; body is replaced by alias-drift pre-check + budget pre-check + `harbor run` exec (§8.1). |
| src/razorback/cli/validate.py | DROP | 72 | v1 `rk validate` warns on ade-bench reset surfaces / tools_allowed semantics; v2 has no `rk validate`. The ade-bench warnings port out to the adapter's own validation. |
| src/razorback/cli/spec.py | DROP | 8 | v1's `rk spec freeze` flattens to v2's top-level `rk freeze`. |
| src/razorback/cli/runs.py | ADAPT-EXTRACT | 45 | `runs diff` exists in v1; v2 moves it to top-level `rk diff` (§3.2) and adds `runs list/show/cost`. The Typer plumbing pattern + exit-code mapping survive. |
| src/razorback/cli/constraints.py | KEEP-EXTRACT | 38 | Optional-surface `rk constraints check` (§3.2 row); ships when consumer demand exists. Compatible with v2 verbatim. |
| src/razorback/cli/baseline.py | KEEP-EXTRACT | 39 | Optional-surface `rk baseline promote|verify` (§3.2 row); ships when consumer demand exists. Compatible verbatim. |
| src/razorback/cli/registry.py | KEEP-EXTRACT | 49 | Optional `rk registry list|resolve|add|remove` (§3.2 row); ships when consumer demand exists. |
| src/razorback/compat/__init__.py | DROP | 6 | Per-harbor-minor translator package; v2 has no translator. |
| src/razorback/compat/harbor_0_6_6.py | DROP | 264 | Spec → harbor 0.6.6 JobConfig translator. v2 has no JobConfig construction inside razorback (§8.1: harbor owns JobConfig). The auth-routing block (§:96-157) is the load-bearing v1 contract; the *invariant* it encodes (auth via AgentConfig.env, never kwargs) survives in v2 as test guidance for SpacedockSolverAgent (FU-1 AC-1). |
| src/razorback/spec/__init__.py | KEEP-EXTRACT | 7 | Package shim. |
| src/razorback/spec/parse.py | KEEP-EXTRACT | 27 | YAML → Spec via pydantic with ValidationError → SpecError wrap. Reused verbatim by `rk freeze`. |
| src/razorback/spec/schema.py | ADAPT-EXTRACT | 143 | SpacedockSolverAgentBlock (`:31-65`) and the ProvenanceBlock (`:120-132`) survive. Drop `ClaudeCliAgentBlock`, `NopAgentBlock`, `LocalBenchmarkBlock`, `DabBenchmarkBlock`, `AdeBenchBenchmarkBlock`, `ObserverBlock`. v2 spec adds `tools_denied`, `runtime` enum, `solver_workflow` path, `resume_from_freeze`, `experiment.max_budget_usd` (§6). |
| src/razorback/spec/freeze.py | KEEP-EXTRACT | 61 | Canonical-YAML freeze with sha256:-prefixed prompt hashes and sealed_hash stamp (§6.2, §6.4). The prompt-content embedding shape is the v2 wire format. |
| src/razorback/provenance/__init__.py | KEEP-EXTRACT | 10 | Package shim. |
| src/razorback/provenance/resolvers.py | ADAPT-EXTRACT | 139 | Anthropic model resolution + image digest + agent CLI hash + git SHA + harbor version + prompt hashes. v2 adds: solver-workflow directory recursive content hash, spacedock skill version pin. The retry / transient-503 classifier (`:46-54`) is core; preserve. |
| src/razorback/provenance/retry.py | KEEP-EXTRACT | 38 | Exponential backoff with injectable `is_transient` and `sleep`. Provider-503 retry mechanism per v2 §8.2 ("retries each external call with exponential backoff"). |
| src/razorback/provenance/errors.py | ADAPT-EXTRACT | 39 | ProvenanceError, AliasDriftError, HarborDriftError. v2 keeps AliasDriftError (exit 21); HarborDriftError may downgrade from hard error to warning depending on D5. |
| src/razorback/provenance/freeze_cmd.py | ADAPT-EXTRACT | 105 | Orchestrates the six resolvers + writes spec.frozen.yaml + provenance.yaml. v2 adds the solver-workflow hash and refuses on unresolved fields unless `--allow-missing` per §3.2. The orchestration shape (resolve → refuse_if_any_unresolved → write_provenance_yaml) is the v2 shape. |
| src/razorback/provenance/drift.py | KEEP-EXTRACT | 54 | `check_alias_drift` is the runtime pre-check (§8.1 step 2). Verbatim into v2's `rk run`. `check_harbor_drift` survives. |
| src/razorback/provenance/provenance_yaml.py | KEEP-EXTRACT | 61 | provenance.yaml writer + REQUIRED_FIELDS refusal predicate. Stable wire format (§7.3). The unresolved/drift_record fields are v2's documented surface. |
| src/razorback/agents/__init__.py | KEEP-EXTRACT | 2 | Package shim. |
| src/razorback/agents/auth.py | KEEP-EXTRACT | 67 | `.env`-via-`dotenv_values` discovery + `~/.claude/benchmark-token` fallback. FU-1 M3 AC-3 contract. Verbatim into v2's auth path. |
| src/razorback/agents/claude_cli.py | DROP | 118 | v1 `ClaudeCliAgent` is a thin direct wrapper around `claude -p`. v2's `SpacedockSolverAgent` subsumes it; standalone claude-cli wrapper no longer exists (v2 §4 — exactly one custom harbor agent). The proxy-env + co-mingled-auth refusal pattern (`:46-56`) survives inside SpacedockSolverAgent. |
| src/razorback/agents/claude_invoke.py | KEEP-EXTRACT | 38 | Shared `claude -p` argv builder + `DISALLOWED_TOOLS` (verbatim run_experiment.py:1531-1549). v2's per-runtime claude adapter uses this verbatim for the inner runtime. |
| src/razorback/agents/proxy.py | KEEP-EXTRACT | 24 | `PROXY_BLOCK_ENV` + `PROXY_EXEMPT_HOSTS` (verbatim run_experiment.py:1497-1525). Inner-runtime env-builder uses this verbatim. |
| src/razorback/agents/registry.py | DROP | 94 | Razorback-internal agent-kind registry (NopAgentConfig, ClaudeCliAgentConfig, SpacedockSolverAgentConfig). v2 registers via harbor's `[project.entry-points."harbor.agents.installed"]` (§4.5). The Spacedock pydantic config schema's invariants (stages exact order, prompts cover stages) port into the v2 SpacedockSolverAgent spec block. |
| src/razorback/agents/seal.py | KEEP-EXTRACT | 53 | Sealed-input hashing (§6.2 AC-5). v2 expands the sealed fields to include `solver_workflow_content_hash`, `spacedock_skill_version`, `harbor_agent_kwargs` (§4.3.5); the canonical-JSON + sha256[:32] mechanism is verbatim. |
| src/razorback/agents/spacedock_solver.py | ADAPT-EXTRACT | 315 | v2's only custom harbor agent. Heavy adaptation. **KEEP verbatim:** sealed-hash refusal in `__init__` before harbor I/O (`:91-128`); co-mingled-auth refusal (`:80-86`); `verify_prompt_contents` (`:145-160`); `assert_phase_stats_schema` schema check shape (`:25-37`); `agent_freeze/.git` init + per-stage commit pattern (`:267-299`). **ADAPT:** runtime is now an enum (claude\|codex\|pi) not a hardcoded claude path — split per-runtime adapter sub-modules (§8.4 `_claude.py`, `_codex.py`, `_pi.py`); stages drop the hardcoded `["model", "analyze", "verify"]` list (v2 reads stages from the solver workflow README); workspace bootstrap copies `solver_workflow` contents (§4.3.2); `phase_stats.json` schema gains `tokens_reasoning`, `tokens_cache_read`, `tokens_cache_write` (§7.2). |
| src/razorback/diff/__init__.py | KEEP-EXTRACT | 16 | Package shim. |
| src/razorback/diff/diff.py | ADAPT-EXTRACT | 175 | The compose pattern (Wilson + McNemar + bootstrap + power MDE → JSON) is the v2 `rk diff` JSON output shape. **ADAPT:** add family-wise correction (Holm-Bonferroni at `--family-wise-alpha`); add `--bootstrap-cluster` argument that selects cluster level (query vs trial) per §3.2 / §8.3. seed-compatibility refusal (`:21-35`) survives. The benchmark-kind refusal (`:44-54`) survives. |
| src/razorback/diff/stats.py | ADAPT-EXTRACT | 171 | `wilson_ci` and `exact_mcnemar_p` verbatim. `paired_bootstrap_ci` adapts: v2 §8.3 mandates cluster-level resampling (queries as units, not trials), the v1 implementation resamples (dataset, query_id, trial_index) triples which is trial-level. Power MDE `power_mde_at_fixed_n` verbatim. |
| src/razorback/diff/pairing.py | KEEP-EXTRACT | 45 | Trial-pairing by (dataset, query_id, trial_index). v2 `rk diff` reuses verbatim; the outcomes JSON shape is the v2 wire format. |
| src/razorback/diff/errors.py | KEEP-EXTRACT | 17 | `BenchmarkMismatchError` typed error pattern. Survives. |
| src/razorback/runtime/__init__.py | DROP | 6 | Package shim for reconcile_run_workflow. |
| src/razorback/runtime/reconcile.py | DROP | 134 | v1 reconciles a run-workflow entity by dispatching `rk run` from inside razorback. v2 (§5.2) moves reconciliation to the spacedock run-workflow's `reconciling` stage prompt — the operator-ensign runs `harbor run` directly; razorback no longer hosts the loop. |
| src/razorback/constraints/__init__.py | KEEP-EXTRACT | 7 | Package shim. |
| src/razorback/constraints/check.py | KEEP-EXTRACT | 62 | Optional `rk constraints check` engine (§3.2 row). Dotted-path pinned + mutation_surfaces check. Ships when consumer demands. |
| src/razorback/constraints/baseline.py | KEEP-EXTRACT | 44 | Optional `rk baseline promote|verify` engine (§3.2). Ships when consumer demands. |
| src/razorback/constraints/schema.py | KEEP-EXTRACT | 12 | ConstraintsFile pydantic shape. Optional surface. |
| src/razorback/registry/__init__.py | KEEP-EXTRACT | 6 | Package shim. |
| src/razorback/registry/store.py | KEEP-EXTRACT | 70 | Optional `rk registry` engine (§3.2). Ships when consumer demands. |
| src/razorback/observers/__init__.py | DROP | 8 | v1 observer fan-out is gone; v2 uses harbor's run-dir event surface (§7.1 — razorback adds two files, not an event channel). |
| src/razorback/observers/channel.py | DROP | 43 | EventChannel + drainer. v2 has no razorback-owned event channel; harbor publishes its own JSONL via the run-dir. |
| src/razorback/observers/jsonl.py | DROP | 18 | JSONL observer. v2: harbor's run-dir already emits events.jsonl; razorback does not write to it. |
| src/razorback/observers/stdout.py | DROP | 16 | Stdout observer. v2: `rk run` passes through harbor's stdout; razorback does not duplicate it. |
| src/razorback/benchmarks/__init__.py | PORT-OUT | 2 | Package shim. v2: benchmark adapters live in their own repos. |
| src/razorback/benchmarks/dab/__init__.py | PORT-OUT | 6 | DAB adapter package shim. Ports to `packages/razorback-plugin-dab/`. |
| src/razorback/benchmarks/dab/aggregate.py | PORT-OUT | 133 | DAB-shaped stratified pass@1 aggregator. v2's `rk score` does stratified-mean reduction generically off the adapter's stratum tags (§3.2 `rk score`). The DAB-specific aggregator ports to the DAB harbor adapter's test suite as the reference scoring path; razorback ships only the generic Wilson-CI + stratified-mean reducer. |
| src/razorback/benchmarks/dab/prepare.py | PORT-OUT | 237 | DAB-specific task materialization (per-query dirs, ground_truth.csv exclusion, task.toml emission). v2: harbor adapters own their own task materialization; ports to `packages/razorback-plugin-dab/`. The leak-protection invariant (`_QUERY_FORBIDDEN` at `:20`) ports as a benchmark-adapter responsibility. |
| src/razorback/benchmarks/dab/reset.py | PORT-OUT | 8 | DAB per_trial_state_reset declaration. Ports to the harbor adapter. |
| src/razorback/benchmarks/dab/verify.py | PORT-OUT | 76 | DAB verifier (`/work/answers.json` → reward.json). Lives inside the DAB harbor adapter, not in razorback. |
| src/razorback/benchmarks/ade_bench/__init__.py | PORT-OUT | 7 | ade-bench adapter package shim. |
| src/razorback/benchmarks/ade_bench/aggregate.py | PORT-OUT | 50 | ade-bench summary aggregator. v2 §3.2: generic `rk score` reads adapter stratum tags; the ade-bench-shaped aggregator lives in the harbor adapter. |
| src/razorback/benchmarks/ade_bench/reset.py | PORT-OUT | 8 | ade-bench per_trial_state_reset (compose_services=False). Lives in the harbor adapter. |
| src/razorback/benchmarks/ade_bench/tasks.py | PORT-OUT | 192 | ade-bench harbor-task loader + git-task fetch + `docker_image` rewrite (FU-2 image-override mechanism). Ports to `packages/razorback-plugin-ade-bench/` (or merges into the harbor adapter's task surface). |

LoC totals: 60 modules, ~3826 LoC. Breakdown by classification:
- KEEP-EXTRACT: 26 modules (~700 LoC)
- ADAPT-EXTRACT: 10 modules (~1100 LoC)
- DROP: 12 modules (~900 LoC)
- PORT-OUT: 9 modules (~700 LoC) — DAB + ade-bench adapters and v1 spec/translator scaffolding around them
- Trivial shims (PORT-OUT package `__init__`s): 3

## Per-module entries

### src/razorback/provenance/resolvers.py — ADAPT-EXTRACT

**Why keep:** This is the freeze-resolver. v2 §8.2 keeps the same surface
(Anthropic model resolution, image digest, agent CLI hash, harness git SHA,
harbor version, prompt content hashes). v2 adds two resolvers
(solver-workflow content hash, spacedock skill version) and extends model
resolution to OpenAI / pi runtimes.

**Lines to extract:**
- `:17-43` `resolve_model_version` (Anthropic-only) — retry-wrapped
  `client.models.retrieve(alias)` returning `(id, created_at)`. Verbatim into
  v2's claude runtime adapter. **Adaptation:** v2 adds codex / pi
  equivalents; this function becomes the claude-specific path.
- `:46-49` `_default_anthropic_client` — `anthropic.Anthropic()` factory.
  Verbatim.
- `:52-54` `_default_is_transient` — the Anthropic 503 classifier
  (status_code in (502, 503, 504)). **Load-bearing**: this is the 503-vs-fatal
  taxonomy the spec calls out. Verbatim. v2 must keep the same predicate
  shape for the claude path; codex/pi paths get their own `is_transient`
  predicates wired into the same `retry_with_backoff` harness (auth-vs-
  org-quota distinctions for OpenAI per AC-0.10 wording belong in the codex
  predicate that v2 adds).
- `:57-68` `resolve_image_digest` — `docker image inspect`. Verbatim.
- `:81-92` `resolve_agent_cli_hash` — sha256 of the CLI binary. Verbatim.
- `:95-114` `resolve_harness_git_sha` — `git rev-parse HEAD`. Verbatim.
- `:123-125` `resolve_harbor_version` — `harbor.__version__`. Verbatim.
- `:128-139` `resolve_prompt_hashes` — content-hash list of prompt files.
  Verbatim; v2 extends with recursive solver-workflow directory hashing as
  a sibling resolver.

**Phase that consumes this:** Phase 1 (freeze-resolver extraction) + Phase 4
(when OpenAI / pi resolvers ship).

### src/razorback/provenance/retry.py — KEEP-EXTRACT

**Why keep:** The exponential-backoff harness with dependency-injected
sleep and `is_transient` predicate. v2 §8.2: "retries each external call
with exponential backoff." This module is the implementation.

**Lines to extract:**
- `:12-38` `retry_with_backoff` — verbatim. Used by every resolver that
  hits an external API. Dependency injection of `sleep` keeps unit tests
  at zero wallclock; v2 reuses verbatim.

**Phase that consumes this:** Phase 1.

### src/razorback/provenance/drift.py — KEEP-EXTRACT

**Why keep:** This is the v2 §8.1 `rk run` pre-check: re-resolve the model
alias against the provider, refuse with `AliasDriftError` if it differs
from the frozen value. Verbatim into v2's `rk run`.

**Lines to extract:**
- `:11-35` `check_alias_drift` — verbatim. Returns `(resolved_id,
  resolved_at)` on no-drift or `allow=True`, raises `AliasDriftError`
  otherwise. The `model.created_at` str-coercion handles the Anthropic SDK
  shape correctly.
- `:38-50` `check_harbor_drift` + `_installed_harbor_version` —
  major-version drift refusal. v2 keeps this as a hard error (§8.2).

**Phase that consumes this:** Phase 1.

### src/razorback/provenance/provenance_yaml.py — KEEP-EXTRACT

**Why keep:** Writes `provenance.yaml`, the v2-stable wire format
(§7.3). Includes the `refuse_if_any_unresolved` predicate that backs
`--allow-missing` semantics (§3.2 `rk freeze`).

**Lines to extract:**
- `:14-21` `REQUIRED_FIELDS` — the canonical list of required provenance
  fields. v2 extends with `solver_workflow_hash`, `spacedock_skill_version`.
- `:24-33` `refuse_if_any_unresolved` — verbatim refusal predicate.
- `:36-61` `write_provenance_yaml` — verbatim writer; the `unresolved:` list
  and `alias_drift:` record fields are v2 wire format.

**Phase that consumes this:** Phase 1.

### src/razorback/provenance/freeze_cmd.py — ADAPT-EXTRACT

**Why keep:** The orchestration shape (parse → resolve → refuse → write
frozen-spec + provenance) is the v2 `rk freeze` shape. The body adapts to
v2's new resolvers and v2's at-top-level CLI surface (`rk freeze` instead
of `rk spec freeze`).

**Lines to extract:**
- `:27-96` `freeze_command` Typer body — the orchestration sequence
  (parse_spec_file → resolve six things → refuse_if_any_unresolved →
  write frozen + provenance). Verbatim shape, body extends to:
  - call `resolve_solver_workflow_hash` (new, v2-only)
  - call `resolve_spacedock_skill_version` (new, v2-only)
  - stamp `sealed_hash` over the expanded sealed fields (§4.3.5)
- `:43-62` per-field resolver invocation sequence — verbatim pattern;
  reorder is fine.
- `:99-105` `_collect_prompt_paths` — adapts to walk solver-workflow READMEs
  in addition to the agent block.

**Phase that consumes this:** Phase 1.

### src/razorback/provenance/errors.py — ADAPT-EXTRACT

**Why keep:** Typed errors with stable exit codes (§3.4). v2 keeps
`ProvenanceError` (exit 11) and `AliasDriftError` (exit 21) verbatim;
`HarborDriftError` stays under exit 1 (generic) per its current shape.

**Lines to extract:**
- `:7-10` `ProvenanceError` — verbatim.
- `:13-25` `AliasDriftError` with `(model_alias, frozen, resolved)` attrs.
  Verbatim. v2 §8.1 contract.
- `:28-39` `HarborDriftError` — verbatim.

**Phase that consumes this:** Phase 1.

### src/razorback/agents/auth.py — KEEP-EXTRACT

**Why keep:** The `.env`-via-`dotenv_values` discipline per FU-1 M3 AC-3.
Specifically named in AC-0.10. The precedence rule (1. ANTHROPIC_API_KEY
from `.env`, 2. CLAUDE_CODE_OAUTH_TOKEN from `~/.claude/benchmark-token`)
is verbatim from `run_experiment.py:1993-2003`. v2 reuses this auth path
unchanged.

**Lines to extract:**
- `:13-14` `AuthDiscoveryError` typed error.
- `:17-20` `AuthResolution` dataclass — `(mode, env)`. Verbatim.
- `:23-35` `_load_env_api_key` — **load-bearing**: uses
  `dotenv_values(env_path)`, not `os.environ.get`. Mirrors
  `run_experiment.py:1905-1917`. Verbatim into v2; v2 tests must assert
  this discipline (no `os.environ` fallback).
- `:38-44` `_read_claude_token` — `~/.claude/benchmark-token`, stripped.
  Mirrors `run_experiment.py:1897-1902`. Verbatim.
- `:47-67` `resolve_claude_auth` — the precedence rule and the error
  message shape. Verbatim. v2's claude runtime adapter calls this exactly.

**Phase that consumes this:** Phase 1 (extracted as part of the
SpacedockSolverAgent claude-runtime adapter sub-module).

### src/razorback/agents/proxy.py — KEEP-EXTRACT

**Why keep:** `PROXY_BLOCK_ENV` and `PROXY_EXEMPT_HOSTS` are verbatim from
`run_experiment.py:1497-1525`. The smoke test asserts the claude CLI works
with EXACTLY this host list. v2's inner-runtime env-builder reuses
verbatim.

**Lines to extract:**
- `:6-11` `PROXY_EXEMPT_HOSTS` — verbatim string. **Load-bearing**: spec
  comment explicitly forbids paraphrasing the host list.
- `:14-24` `PROXY_BLOCK_ENV` — verbatim dict including HF / transformers
  / datasets offline flags.

**Phase that consumes this:** Phase 1.

### src/razorback/agents/claude_invoke.py — KEEP-EXTRACT

**Why keep:** The `DISALLOWED_TOOLS` list is verbatim from
`run_experiment.py:1531-1549`; module comment forbids paraphrasing. v2's
claude-runtime adapter sub-module reuses verbatim. The `build_claude_argv`
builder is the per-stage and per-trial argv shape.

**Lines to extract:**
- `:7` `DEFAULT_ALLOWED_TOOLS` — verbatim.
- `:10-18` `DISALLOWED_TOOLS` — **verbatim from run_experiment.py
  1531-1549**. This is the DAB-recommended `tools_denied` list that the
  v2 spec (§6.2 `tools_denied` row) names. Captains paste it into v2 specs.
- `:21-38` `build_claude_argv` — verbatim argv builder. v2 claude adapter
  reuses for `--allowedTools`, `--disallowedTools`, `--permission-mode
  bypassPermissions`, `--model` argv assembly.

**Phase that consumes this:** Phase 1 (Layer 2 leak guard, §9.4) + Phase 4
(when codex / pi sub-modules adapt the equivalent denylist surfaces).

### src/razorback/agents/seal.py — KEEP-EXTRACT

**Why keep:** Sealed-input hashing (§4.3.5). The
canonical-JSON-over-sorted-keys → sha256[:32] mechanism is verbatim; v2
expands the sealed fields but the hashing core is unchanged.

**Lines to extract:**
- `:9-15` `prompt_sha256` — `sha256:`-prefixed wire format. Verbatim.
- `:18-41` `compute_sealed_hash` — canonical-JSON encoder + sha256[:32].
  Verbatim. **Adaptation:** v2 expands the payload to add
  `solver_workflow_content_hash`, `spacedock_skill_version`,
  `harbor_agent_kwargs` (§4.3.5); the encoder shape is unchanged.
- `:44-53` `_canonicalize_sampling` — verbatim. "seed is unset" is
  pinned (not dropped) — load-bearing for v2's sampling discipline.

**Phase that consumes this:** Phase 1 (SpacedockSolverAgent extraction).

### src/razorback/agents/spacedock_solver.py — ADAPT-EXTRACT

**Why keep:** The v2 `SpacedockSolverAgent` (§4). The sealed-hash refusal,
co-mingled-auth refusal, prompt-content verification, `agent_freeze/.git`
init + per-stage commit pattern, and `phase_stats.json` schema check
ALL survive verbatim. The class signature, the inner-runtime composition
(currently hardcoded claude path), and the stage list source adapt for
v2.

**Lines to extract:**
- `:25-37` `assert_phase_stats_schema` — schema check shape (§7.2).
  **Adaptation:** v2 adds `tokens_reasoning`, `tokens_cache_read`,
  `tokens_cache_write` to the required key set (§7.2).
- `:80-86` co-mingled-auth refusal (ANTHROPIC_API_KEY and
  CLAUDE_CODE_OAUTH_TOKEN cannot both be set). Verbatim — load-bearing
  for FU-1 AC-1.
- `:91-128` `_refuse_on_resume_mismatch` — sealed-hash refusal BEFORE
  harbor I/O (§4.3.5). Verbatim. The `_find_drifted_field` shape
  (`:130-143`) survives.
- `:145-160` `verify_prompt_contents` — re-hash each prompt body, refuse
  on drift. Verbatim (FU-1 M3 AC-3 prompt-content tamper-detection).
- `:180-206` `setup` — env build (PROXY_BLOCK_ENV + extra_env), claude +
  git binary validation. Adaptation: v2's per-runtime adapter
  sub-module (§8.4 `_claude.py`) holds the inner-runtime construction;
  the parent class delegates to `inner.setup(env)`.
- `:267-284` `_init_agent_freeze_repo` — verbatim. The
  `logs_dir/agent_freeze/.git` init pattern is the v2 §4.4 contract.
- `:286-299` `_commit_stage` — verbatim. The per-stage commit shape.
- `:301-302` `_render_stage_prompt` — verbatim simple stage-prompt
  rendering.
- `:304-315` `_write_phase_stats_file` — verbatim writer. **Adaptation:**
  v2 schema gains three token-count fields.

**Adaptations (don't lift verbatim):**
- Class signature: v1 takes a hardcoded `stages = ["model", "analyze",
  "verify"]` and a `prompts: dict[str, str]` keyed by those stages. v2
  reads stages from the solver workflow README (§4.3.2) — drop the
  hardcoded list, drop the prompts dict, point at `solver_workflow`
  directory instead.
- Inner-runtime construction: v1 directly invokes `claude -p` via
  `build_claude_argv`. v2 wraps harbor's installed `claude_code`, `codex`,
  or `pi` agent based on `runtime: enum` (§4.3.1). Per-runtime adapter
  sub-modules (`_claude.py`, `_codex.py`, `_pi.py`) own kwarg
  construction (§8.4).
- Workspace bootstrap: v2 copies `solver_workflow` contents into the
  trial workspace (§4.3.2). v1 has no equivalent (it embeds prompts
  inline).
- Resume mechanic: v2 restores the workspace from the freeze's
  embedded git before invoking the inner runtime (§4.3.6). v1 has no
  workspace restore — the resume mechanism in v1 is at-spec-level
  (resume from a frozen spec), not at-workspace-level.

**Phase that consumes this:** Phase 1 (extraction skeleton) + Phase 2
(per-runtime adapter sub-modules) + Phase 4 (workspace bootstrap +
resume restore).

### src/razorback/spec/freeze.py — KEEP-EXTRACT

**Why keep:** The canonical-YAML freeze + prompt-content embedding +
sealed_hash stamping is the v2 §6 freeze format. The `derive_job_name`
mechanism (content-derived sha256[:16]) survives.

**Lines to extract:**
- `:13-31` `freeze_spec` — verbatim. Reads parsed Spec, pins prompts,
  stamps sealed_hash for SpacedockSolverAgentBlock specs.
- `:34-56` `_freeze_spacedock_prompts` — verbatim. Replaces prompt file
  paths with sha256: strings; embeds bodies under `prompt_contents`.
  Idempotent on pre-hashed input (`:40-48`) — load-bearing for
  `rk freeze` idempotency promise (§3.1).
- `:59-61` `derive_job_name` — verbatim. sha256[:16] of frozen text.

**Phase that consumes this:** Phase 1.

### src/razorback/spec/parse.py — KEEP-EXTRACT

**Why keep:** YAML → pydantic Spec, ValidationError → SpecError wrap.
Verbatim.

**Lines to extract:**
- `:13-23` `parse_spec_text` — verbatim. Catches `yaml.YAMLError` and
  `ValidationError`, re-raises as `SpecError` with exit code 10.
- `:26-27` `parse_spec_file` — verbatim trivial wrapper.

**Phase that consumes this:** Phase 1.

### src/razorback/spec/schema.py — ADAPT-EXTRACT

**Why keep:** SpacedockSolverAgentBlock (`:31-65`) survives heavily
adapted; ProvenanceBlock (`:120-132`) survives. The other agent and
benchmark blocks drop.

**Lines to extract:**
- `:10-14` `SamplingBlock` — verbatim. Temperature/top_p/seed pydantic
  block.
- `:31-65` `SpacedockSolverAgentBlock` — the load-bearing v2 agent
  block. **Adaptation:** v2 adds `runtime: enum`, `solver_workflow: path`,
  `tools_denied: list[str]`, `resume_from_freeze: path`, `max_turns: int`,
  `max_budget_usd: number`. v2 drops `stages` (read from solver workflow
  README) and changes `prompts: dict` to `solver_workflow: path` (§6.2).
  The pre/post-freeze invariants (`prompts: file path` pre-freeze, `sha256:`
  post-freeze) port to `solver_workflow` content-hash.
- `:120-132` `ProvenanceBlock` — verbatim. v2 adds
  `solver_workflow_hash` and `spacedock_skill_version` resolved fields.
- `:135-143` `Spec` top-level — verbatim shape with `model_config
  extra="forbid"`. v2 adds the `labels:`, `experiment:` (object),
  `experiment.max_budget_usd`, and removes `observers:`.

**Drop (no v2 equivalent):**
- `:17-19` `NopAgentBlock` — v2 has one agent kind.
- `:22-28` `ClaudeCliAgentBlock` — subsumed by SpacedockSolverAgentBlock.
- `:74-85` `LocalBenchmarkBlock`, `DabBenchmarkBlock` — v2 benchmarks
  are harbor-published adapters (§1.3 second bullet, §2.2). The
  `benchmark` block passes through to harbor unchanged.
- `:87-105` `AdeBenchBenchmarkBlock`, `AdeBenchTaskEntry` —
  ade-bench-specific; ports out.
- `:114-117` `ObserverBlock` — v2 has no razorback-owned observers.

**Phase that consumes this:** Phase 1.

### src/razorback/agents/claude_invoke.py — KEEP-EXTRACT

(Covered above under "Lines to extract" section.)

### src/razorback/cli/__init__.py — ADAPT-EXTRACT

**Why keep:** The Typer-wired-from-subcommand-modules pattern survives.
The specific subcommand topology adapts to v2's surface.

**Lines to extract:**
- `:8-19` Typer app + `run` subcommand wiring — pattern survives.
  Adaptation: v2 wires `freeze`, `score`, `audit`, `diff` at the top
  level; `runs list/show/cost` as a sub-app.

**Drop:**
- `:21-23` `validate` wiring — v2 has no `rk validate`.
- `:25-27` `spec` sub-app — flattens to top-level `rk freeze`.

**Phase that consumes this:** Phase 1.

### src/razorback/cli/run.py — ADAPT-EXTRACT

**Why keep:** The error→exit-code mapping (`RazorbackError.exit_code →
typer.Exit`) is the v2 CLI pattern. The body is replaced.

**Lines to extract:**
- `:22-34` error mapping pattern — verbatim. v2 `rk run` does:
  parse_spec → check_alias_drift → check_budget → exec harbor →
  surface exit code; wrap each step in the same try/except shape.

**Adapt:**
- Body replaced by alias-drift pre-check + budget pre-check + `harbor
  run` subprocess exec (§8.1). The current body
  (`execute_run(spec, runs_dir, allow_alias_drift)`) which orchestrates
  harbor.Job in-process drops entirely; v2 shells `harbor run`.

**Phase that consumes this:** Phase 1.

### src/razorback/cli/runs.py — ADAPT-EXTRACT

**Why keep:** `runs diff` Typer command + error mapping. v2 moves diff to
top-level `rk diff` and renames `runs` to `runs list|show|cost`.

**Lines to extract:**
- `:17-46` Typer app shape + error mapping — verbatim pattern; topology
  changes (move `diff` out, add `list/show/cost`).

**Phase that consumes this:** Phase 1.

### src/razorback/diff/diff.py — ADAPT-EXTRACT

**Why keep:** The compose pattern (Wilson + McNemar + bootstrap + power MDE
→ JSON) is the v2 `rk diff` JSON output shape (§8.3).

**Lines to extract:**
- `:21-35` `check_paired_seed_compatibility` — verbatim. §8.3 last paragraph
  contract.
- `:44-66` `check_paired_benchmark_kind` — verbatim. Cross-benchmark refusal.
- `:71-163` `compute_diff` — the JSON shape is the v2 wire format.
  **Adapt:**
  - add family-wise p-adjustment (Holm-Bonferroni) per §8.3, `--family-wise-alpha`
  - add `--bootstrap-cluster` enum (default `query`); v1 resamples
    `(dataset, query_id, trial_index)` which is trial-level — change
    default to query-level cluster bootstrap per §8.3 second-to-last
    paragraph
  - emit both raw per-test p and family-wise-adjusted p (§8.3)
  - emit achieved-power-at-observed-effect alongside MDE (§8.3 last bullet)

**Phase that consumes this:** Phase 4 (`rk diff` ships later per §3.2 + §10).

### src/razorback/diff/stats.py — ADAPT-EXTRACT

**Why keep:** The four statistical primitives. Wilson CI and exact
McNemar are verbatim; paired bootstrap adapts to cluster level; power
MDE survives verbatim.

**Lines to extract:**
- `:14-33` `wilson_ci` — verbatim. Wilson 1927 closed form. v2 `rk score`
  also calls this for per-stratum CIs.
- `:36-52` `exact_mcnemar_p` — verbatim binomtest-based exact McNemar.
- `:55-84` `power_mde_at_fixed_n` — verbatim closed-form MDE.
- `:87-145` `paired_bootstrap_ci` + `_build_pair_index` — **adapts**:
  v2 §8.3 mandates cluster-level resampling. v1 resamples
  (dataset, query_id, trial_index) triples (trial-level); v2 default
  is to resample at the `query` cluster level. Preserve the
  pair-index data structure + percentile method; change the resample
  unit.

**Phase that consumes this:** Phase 4 (rk diff) + Phase 1 (rk score
reuses wilson_ci verbatim).

### src/razorback/diff/pairing.py — KEEP-EXTRACT

**Why keep:** Trial pairing by (dataset, query_id, trial_index). The
`per_trial_outcomes.json` shape with `outcomes_version: 1` is the v2
wire format for diffing two runs.

**Lines to extract:**
- `:8-16` `load_run_outcomes` — verbatim. Wire-format check.
- `:19-45` `pair_outcomes` — verbatim. Pairing + error message shape.

**Phase that consumes this:** Phase 4.

### src/razorback/diff/errors.py — KEEP-EXTRACT

**Why keep:** `BenchmarkMismatchError` typed-error pattern with stable
exit code. Verbatim into v2.

**Lines to extract:** `:1-17` — verbatim.

**Phase that consumes this:** Phase 4.

### src/razorback/errors.py — ADAPT-EXTRACT

**Why keep:** ExitCode IntEnum + base errors are the stable wire surface
(§3.4). v2 keeps every existing code; adds two new codes.

**Lines to extract:**
- `:7-16` `ExitCode` IntEnum — verbatim, then add:
  - `BUDGET_EXCEEDED = 22`
  - `TAINT_FINDINGS = 23`
- `:19-21` `RazorbackError` base — verbatim.
- `:24-25` `SpecError` — verbatim.
- `:28-30` `SeedMismatchError` — verbatim.
- `:33-35` `ConstraintViolation` — verbatim.

**Add (new in v2):** `BudgetExceededError` (exit 22, §8.1
`--max-budget-usd-running`), `TaintFindingsError` (exit 23, §3.2
`rk audit --policy strict`).

**Phase that consumes this:** Phase 1.

### src/razorback/cli/constraints.py — KEEP-EXTRACT

**Why keep:** Optional `rk constraints check` Typer command. §3.2 row;
ships when consumer demands. Verbatim survives.

**Lines to extract:** `:1-39` — entire file verbatim, modulo the
top-level wiring change in `cli/__init__.py`.

**Phase that consumes this:** Optional follow-on (§3.2 third block).

### src/razorback/cli/baseline.py — KEEP-EXTRACT

**Why keep:** Optional `rk baseline promote|verify` Typer command. §3.2.

**Lines to extract:** `:1-40` — verbatim.

**Phase that consumes this:** Optional follow-on (used by experiment
workflow `conclude` stage; §5.1).

### src/razorback/cli/registry.py — KEEP-EXTRACT

**Why keep:** Optional `rk registry` Typer command. §3.2.

**Lines to extract:** `:1-49` — verbatim.

**Phase that consumes this:** Optional follow-on.

### src/razorback/constraints/check.py — KEEP-EXTRACT

**Why keep:** Engine behind `rk constraints check`. Dotted-path traversal
+ pinned + mutation_surfaces check. Verbatim.

**Lines to extract:** `:1-62` — verbatim.

**Phase that consumes this:** Optional follow-on.

### src/razorback/constraints/baseline.py — KEEP-EXTRACT

**Why keep:** Engine behind `rk baseline promote|verify`. Verbatim.

**Lines to extract:** `:1-44` — verbatim.

**Phase that consumes this:** Optional follow-on.

### src/razorback/constraints/schema.py — KEEP-EXTRACT

**Why keep:** ConstraintsFile pydantic shape. Verbatim.

**Lines to extract:** `:1-12` — verbatim.

**Phase that consumes this:** Optional follow-on.

### src/razorback/registry/store.py — KEEP-EXTRACT

**Why keep:** YAML-backed registry. Verbatim.

**Lines to extract:** `:1-70` — verbatim. The
`RAZORBACK_REGISTRY` env override + `~/.config/razorback/registry.yaml`
default is the v2 wire layout.

**Phase that consumes this:** Optional follow-on.

### src/razorback/cli/__main__.py — KEEP-EXTRACT

**Why keep:** `python -m razorback.cli` entry shim. Verbatim.

**Lines to extract:** `:1-7` — verbatim.

**Phase that consumes this:** Phase 1.

### src/razorback/__init__.py — KEEP-EXTRACT

**Why keep:** `__version__ = "0.1.0"`. v2 bumps this to align with §3.3
semver; the file shape survives.

**Phase that consumes this:** Phase 1.

### DROP modules

The following modules drop because their responsibility no longer
exists in v2:

- **src/razorback/run.py** (192 LoC) — v1 owns the harbor.Job
  orchestration loop inside `_execute_run_async`. v2 §8.1 hands the run
  loop to `harbor run` and razorback owns only the pre-checks +
  provenance artifacts.
- **src/razorback/manifest.py** (26 LoC) — v1 writes `manifest.json` at
  the run-dir root with `run_dir_version`, `experiment`, `job_name`,
  `created_at`, `benchmark_kind`. v2 §7.1: razorback writes
  `spec.frozen.yaml` and `provenance.yaml` only; the rest is harbor's.
- **src/razorback/compat/** (270 LoC: `__init__.py` + `harbor_0_6_6.py`) —
  v1's per-harbor-minor Spec → JobConfig translator. v2: razorback does not
  construct JobConfig (§8.1 last paragraph). The auth-routing invariant
  in `harbor_0_6_6.py:96-157` (auth flows via `AgentConfig.env`, never
  `kwargs`) is **load-bearing for FU-1 AC-1** — it survives as a test
  guidance asserting the same property on v2's `SpacedockSolverAgent`
  registration shape.
- **src/razorback/cli/validate.py** (72 LoC) — v1's `rk validate` warns
  on ade-bench reset surfaces and `tools_allowed` semantics. v2 has no
  `rk validate`; benchmark-specific warnings move to the adapter's own
  validation.
- **src/razorback/cli/spec.py** (8 LoC) — v1 sub-app shell for `rk spec
  freeze`. v2 flattens to top-level `rk freeze`.
- **src/razorback/agents/claude_cli.py** (118 LoC) — v1 standalone
  claude wrapper. v2 §4: razorback ships exactly one custom harbor
  agent (`SpacedockSolverAgent`). The proxy-env + co-mingled-auth refusal
  pattern (`:46-56`) survives inside the SpacedockSolverAgent claude
  runtime adapter sub-module.
- **src/razorback/agents/registry.py** (94 LoC) — v1's
  razorback-internal agent-kind registry. v2 §4.5 registers via
  harbor's `[project.entry-points."harbor.agents.installed"]`. The
  pydantic config schema for SpacedockSolver (`:37-64`) ports as v2's
  spec-block validation, but the registry mechanism itself drops.
- **src/razorback/runtime/__init__.py** (6 LoC) +
  **src/razorback/runtime/reconcile.py** (134 LoC) — v1 hosts the
  run-workflow reconciliation loop. v2 §5.2: reconciliation lives in
  the spacedock run-workflow's `reconciling` stage prompt, not in
  razorback.
- **src/razorback/observers/** (85 LoC across 4 files) — v1's EventChannel
  + drainer + JSONL / stdout observers. v2 has no razorback-owned
  event channel; harbor's run-dir publishes events.

### PORT-OUT modules

The following modules survive but their content moves to sibling
packages (per v2 §1.3 second bullet: "Razorback is not a benchmark
library"):

- **src/razorback/benchmarks/__init__.py** (2 LoC)
- **src/razorback/benchmarks/dab/\*** (5 files, ~460 LoC) — DAB harbor
  adapter content. Ports to `packages/razorback-plugin-dab/`. The
  DAB-specific `_QUERY_FORBIDDEN` list (`prepare.py:20`) is the
  leak-protection invariant; ports verbatim. The DAB stratified pass@1
  aggregator's `pass_at_k` (verbatim from
  `/Users/clkao/git/dataagentbench/data/common_scaffold/validate/pass_k.py`,
  `aggregate.py:12-23`) ports too.
- **src/razorback/benchmarks/ade_bench/\*** (4 files, ~258 LoC) — ade-bench
  harbor adapter content. Ports to `packages/razorback-plugin-ade-bench/`.
  **Specifically:** the FU-2 `docker_image_override` mechanism
  (`tasks.py:98-135` `rewrite_docker_image` + `:138-192`
  `materialize_git_task`) is the load-bearing FU-2 image-override
  acceptance-test contract per AC-0.10. The mechanism (string-rewrite
  AFTER git fetch, BEFORE harbor reads task.toml; razorback-owned
  `cache_root`) ports verbatim — the test guarding it asserts the same
  property in the harbor adapter's test suite.

## Coverage cross-check

- Every `src/razorback/**/*.py` file appears above: **YES** (60 modules
  enumerated from `find /Users/clkao/git/razorback/src/razorback -name
  '*.py'`; every entry maps to a row in the summary table).
- Every v2-spec-named artifact accounted for:
  - **`rk freeze`** (§3.2, §8.2) — KEEP-EXTRACT from
    `provenance/freeze_cmd.py` (orchestration) + `provenance/resolvers.py`
    (the six resolvers) + `provenance/provenance_yaml.py` (writer) +
    `provenance/retry.py` (backoff) + `spec/freeze.py` (canonical YAML +
    sealed_hash + prompt embedding).
  - **`rk run`** (§3.2, §8.1) — ADAPT-EXTRACT: alias-drift pre-check
    from `provenance/drift.py` (verbatim); error→exit-code shape from
    `cli/run.py`. Budget pre-check (`--max-budget-usd-running`) is
    NEW in v2 (rewritten from spec — no extraction).
  - **`rk score`** (§3.2, §8.3a) — REWRITTEN FROM SPEC. Wilson CI
    extracted from `diff/stats.py:14-33`; the stratified-mean reducer
    is a small new generic from-spec component.
  - **`rk audit`** (§3.2, §9.4 Layer 3) — REWRITTEN FROM SPEC. Ports
    dataagentbench's `benchmark/lib/taint.py` mechanism (out-of-tree;
    not in `src/razorback/`).
  - **`rk runs list|show|cost`** (§3.2) — REWRITTEN FROM SPEC. No
    existing implementation in v1 (v1 has `runs diff` only).
  - **`rk diff`** (§3.2, §8.3) — ADAPT-EXTRACT from `diff/diff.py` +
    `diff/stats.py` + `diff/pairing.py` + `diff/errors.py`. Family-wise
    correction + `--bootstrap-cluster` are new.
  - **`SpacedockSolverAgent`** (§4) — ADAPT-EXTRACT from
    `agents/spacedock_solver.py` (heavy; see per-module entry). Sealed-hash,
    auth refusal, prompt-content verification, agent_freeze/.git
    contract all survive verbatim; runtime selection + workspace
    bootstrap + resume restore are new.
  - **`rk constraints check`, `rk baseline promote|verify`, `rk
    registry`** (§3.2 optional surface) — KEEP-EXTRACT from
    `cli/constraints.py`, `cli/baseline.py`, `cli/registry.py`,
    `constraints/`, `registry/`.
  - **Workflow README templates** (§5) — REWRITTEN FROM SPEC. No
    razorback-shipped templates in v1.
