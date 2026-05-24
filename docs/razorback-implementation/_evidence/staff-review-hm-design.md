# Staff design review — `hm` generic-harbor-benchmark-surface

**Doc under review.** `docs/superpowers/specs/2026-05-23-generic-harbor-benchmark-surface.md`
@ commit `cca7608` (`hm: cycle-3 UX-first design rewrite — scenarios drive
internals`).

**Branch.** `spacedock-ensign/generic-harbor-benchmark-surface-design`,
clean tree at review time.

**Scope.** Plan / design review only. Source code, design doc, and
entity bodies are read-only. Four constructs surveyed against the
design's `kind: harbor` + `rk research new` + `_build_harbor`
proposal.

---

## Construct: batch / query_mode (DAB batch vs per-query)

### 1. What is the construct today
- `HarborDabBenchmarkBlock.query_mode: Literal["batch", "per-query"]`
  — `src/razorback/spec/schema.py:145`, defaulted to `"per-query"`.
  Sits beside `workspace_variant` (line 143) and `hints` (line 144) on
  the same DAB-specific block (lines 125-183).
- The translator at `src/razorback/translate.py:321-448`
  (`_build_harbor_dab`) reads `spec.benchmark.query_mode`
  (line 382) and threads it to the plugin via
  `--query-mode <value>` (line 394). The `batch` branch (lines
  407-423) walks `steps/main/workdir/queryNN/`, gathers integer
  query ids, and registers a `trial_name_map` entry of shape
  `(dataset, list[int])`; the `per-query` branch (lines 424-433)
  emits one task per dataset-query and registers
  `(dataset, int)` per task.
- The aggregator consumes the resulting per-query sidecar at
  `src/razorback/runs/aggregate.py:190-205`
  (`_load_reward_per_query`), reading
  `<trial_dir>/steps/main/verifier/reward_per_query.json`. That
  file's existence is precisely what `query_mode: batch` produces.
  The legacy aggregator carries the same shape at
  `src/razorback/_legacy/benchmarks/dab/aggregate.py:99-179`.

So `query_mode` is a load-bearing semantic on three layers:
schema, translator (trial fan-out shape), and aggregator
(reward_per_query.json consumption).

### 2. What does the design propose
- §2.1 (lines 333-366): the new `benchmark:` block carries
  ONLY `kind: harbor` + `dataset:` + optional
  `tasks/exclude_tasks/n_tasks`. Explicitly: "No per-benchmark
  fields. No `prep:` discriminator." `query_mode` is not mentioned.
- §2.2 (lines 396-398, on the harbor_dab migration row): DAB stays
  as a plugin escape valve under `kind: harbor` +
  `plugin: razorback-plugin-dab`. "The workspace_variant / hints /
  query_mode fields move to a `plugin_args:` sub-block on the
  benchmark."
- §2.6 (lines 506-535) shows the escape valve concretely:
  `plugin_args:` carries `workspace_variant`, `query_mode`,
  `hints`, `data_root`. `_build_harbor` "notices `plugin:` is set
  and routes to a thin subprocess shim that calls `<plugin>
  generate --out <view-dir> --args <serialized plugin_args>`".
- Aanya's `baseline.yaml` (§1.1 lines 82-105) targets dabstep
  (not DAB) and carries no `query_mode` at all. So Aanya's flow
  does NOT touch the field.

### 3. Survives cleanly?
**No — survives only under named conditions the design glosses
over.**

`query_mode` survives schematically: it moves into a free-form
`plugin_args:` map under §2.6. But the field's three load-bearing
behaviors do NOT all survive:

- **Schema validation lost.** Today the field is
  `Literal["batch", "per-query"]` — a typo rejects at parse time
  (`src/razorback/spec/schema.py:145`). Under `plugin_args:` as
  drawn in §2.6 line 518-522, it becomes a string key inside a map
  the core never types. The validation cost moves from razorback
  to the plugin's `generate` subprocess CLI.
- **Trial fan-out shape lost.** The `_build_harbor` shim in §2.6
  is described as "thin": it just runs the subprocess and
  collects emitted task dirs. The `trial_name_map` of shape
  `(dataset, list[int])` vs `(dataset, int)` that
  `_build_harbor_dab:382-433` constructs today has NO obvious
  home in the new shim. The design is silent on whether the
  plugin returns it (out-of-band protocol the design doesn't
  define) or razorback re-derives it (impossible without
  understanding `query_mode` semantically).
- **Aggregator coupling unchanged but invisible.** §2.8 mentions
  `rk score` reads `experiment_meta.paper_baseline` but does not
  discuss `reward_per_query.json`. The reducer at
  `src/razorback/runs/aggregate.py:190` still needs to know which
  trials are batch-mode to apply the per-query split, and the
  design's `kind: harbor` block does not surface that intent
  back to the aggregator.

### 4. Friction
- **Scope-overlap / hidden coupling.** The design treats DAB as
  "pure plugin, write some args" but the field is consumed in
  three layers, not one. Spec §2.6 line 528-530 says "same shape
  as today's `_build_harbor_dab` does, but the dispatch is
  generic" — that claim is false for the `batch` branch (lines
  407-423 of translate.py), which builds `trial_name_map` by
  reading the emitted directory tree. A "thin" generic shim
  cannot reproduce that without either (a) the plugin emitting a
  manifest in a new contract the design does not specify, or
  (b) razorback retaining DAB-specific knowledge.
- **Contract violation.** §2.1 line 363 says "No `prep:`
  discriminator." But §2.6 introduces a `plugin:` discriminator
  in spirit (the field that toggles "thin shim vs PackageDataset
  resolution") without calling it that. The naming difference
  papers over the same shape.
- **Lost fidelity.** Today, `rk freeze` against a DAB spec types
  `query_mode` and refuses junk. After migration to
  `plugin_args: { query_mode: ... }`, freeze accepts anything
  and the plugin discovers the typo at run-time, after spec
  freeze has already pinned the wrong sealed_hash.

### 5. Recommendation
**Survives-with-named-changes-needed.** The design should:
- Define the `plugin:` ↔ `_build_harbor` contract explicitly —
  either the plugin emits a manifest (shape TBD) OR razorback's
  shim is per-plugin (defeats §2.1's "no per-benchmark fields"
  claim).
- Decide whether `query_mode` typing migrates with the field or
  whether the plugin's CLI is now the type oracle. If the latter,
  spec the freeze-time validation contract (plugin CLI must
  return non-zero with a typed error message; razorback wraps
  in `SpecError`).
- Re-spec how `trial_name_map` is produced under the generic
  shim. Without this, the aggregator's batch-mode reducer breaks
  silently when migrated specs reach it.

---

## Construct: freeze / sealed_hash / freeze CAS

### 1. What is the construct today
- `compute_sealed_hash` at `src/razorback/agents/seal.py:18-93`
  hashes a canonical-JSON payload of: `model`, `sampling`,
  `solver_workflow_content_hash`, `prompt_content_hashes`,
  `spacedock_skill_version`, `harbor_agent_kwargs`, plus an
  optional `task_identity` block (`benchmark_kind`,
  `benchmark_task_id`, `batch_mode`, `child_task_ids_hash`,
  lines 68-82). Returns first 32 hex chars of sha256
  (line 93).
- `freeze_spec` at `src/razorback/spec/freeze.py:16-78` is the
  spec-side freeze: it canonicalises the YAML and, when the
  agent is `spacedock_solver`, computes the
  `solver_workflow_content_hash` (recursive sha256 over the
  workflow directory contents, lines 64-78) and the
  `sealed_hash` (lines 54-61). NOTE: `benchmark_kind` /
  `benchmark_task_id` / `batch_mode` are NOT passed by
  `_freeze_spacedock_solver` (lines 30-61) — they enter the
  sealed_hash at agent-construction time, not at freeze time
  (see `SpacedockSolverAgent.__init__` at
  `src/razorback/agents/spacedock_solver.py:117-129`).
- The freeze CAS lives at the path returned by
  `SpacedockSolverAgent.resolve_freeze_dir()`
  (`spacedock_solver.py:185-197`): `<cas-root>/<sealed_hash>/`,
  with cas-root resolving via `$RAZORBACK_FREEZE_DIR` →
  `$XDG_DATA_HOME/razorback/freeze` → `~/.local/share/razorback/
  freeze`. Resume mismatch raises `SeedMismatchError`
  (lines 152-165 + 320-326).

So the seal payload's "benchmark" coupling is:
benchmark_kind (string), benchmark_task_id (string), batch_mode
(string), child_task_ids_hash (string). All four enter as
optional kwargs and are discovered post-hoc from the view
manifest (`_discover_task_identity_from_manifest`,
`spacedock_solver.py:214-245`).

### 2. What does the design propose
- §2.4 (lines 474-490): `_build_harbor` resolves the dataset ref
  via `PackageDatasetClient.download_dataset`, emits one
  `TaskConfig(path=...)` per task. The design states
  "`HarborBenchmarkBlock` schema in commit `6cbcaa8` also stays
  (matches §2.1 exactly)". Already in tree at
  `src/razorback/spec/schema.py:301-381`.
- §2.5 (lines 491-503): `kind: harbor-local` is a "minimal" dev
  escape with `tasks_root:` + `tasks:`.
- §2.6 (lines 506-535): plugin escape valve, see prior
  construct.
- The design does not mention freeze. It does not say what the
  sealed_hash inputs become under `kind: harbor`. It does not
  discuss whether `dataset:` should seal. It does not discuss
  whether `tasks` / `exclude_tasks` / `n_tasks` should seal. It
  does not discuss whether `tasks_root:` (a local absolute path,
  not portable across machines) should seal. §2.4's "stays"
  claim does not extend to freeze semantics.

### 3. Survives cleanly?
**Mostly — by accident, because freeze today is agent-payload-only
for the spec-side computation.** The spec-side
`_freeze_spacedock_solver` (`freeze.py:30-61`) does NOT include
benchmark fields in `sealed_hash`. Migrating `kind: ade-bench` /
`kind: harbor_dab` / `kind: spider2-dbt` → `kind: harbor` does
not perturb the spec-side `sealed_hash` value at all, because the
benchmark block was never part of the spec-side computation.

The agent-side `task_identity` block (seal.py:68-82) IS exercised
at agent-construction time, populated from
`_discover_task_identity_from_manifest`
(`spacedock_solver.py:214-245`), which reads
`<run_dir>/_razorback/task_views/*/view_manifest.json` for
`benchmark_kind`, `benchmark_task_id`, `child_task_ids_hash`,
`batch_mode`. The view manifest is written by
`materialize_ade_harbor_task_view` (preserved per §2.7 line
552-555). The `benchmark_kind` field will now read `"harbor"` for
migrated specs instead of `"ade-bench"` / `"harbor_dab"` /
`"spider2-dbt"`. That changes the agent-side sealed_hash for
otherwise-identical workloads — i.e. resuming a pre-migration
run-dir with a post-migration agent will `SeedMismatchError`.

The design's §2.11 sequence does not call this out. It is a
no-backwards-compat migration, so the breakage is permissible by
captain directive; but the design should name it.

### 4. Friction
- **Hidden coupling / semantic drift.** The view-manifest
  `benchmark_kind` string flows into the agent's sealed_hash
  (seal.py:73-82). Renaming `kind: ade-bench` → `kind: harbor`
  silently shifts every sealed_hash for migrated specs. The
  freeze CAS at `<cas-root>/<sealed_hash>/` becomes a write-only
  graveyard for the old kinds; nothing in the design plans a
  cleanup or signposts the discontinuity.
- **Lost-fidelity for `harbor-local`.** §2.5's
  `HarborLocalBenchmarkBlock` carries `tasks_root: Path` (already
  in schema.py:326). `_expand_path` (schema.py:15-24) expands env
  vars / `~` at parse time, but the resulting absolute path
  varies per developer machine. Two devs with the same workflow
  but different `tasks_root` produce different specs hashing to
  different sealed-hashes — defeating "harbor-local is the dev
  escape, migrate to `kind: harbor` when published" since their
  freeze trees are non-portable. The design does not surface
  this. (It is also true of the existing
  `HarborDabBenchmarkBlock.data_root` and `AdeBenchBenchmarkBlock.tasks_root`
  today, so this is inherited rather than introduced — but the
  design's §2.5 wave-of-the-hand "intentionally minimal" misses
  the chance to call out the portability gap.)
- **Plugin escape — sealed_hash gap.** Under §2.6's plugin
  escape valve, `plugin_args:` is a free-form map. If it isn't
  in the spec-side freeze canonicalization, two specs with
  different `plugin_args` freeze identically. If it IS, the
  contract for how the plugin's CLI version contributes to the
  hash is undefined. Today's `HarborDabBenchmarkBlock` ducks
  this because `query_mode` etc. don't enter the
  spec-side sealed_hash; agent-side, they enter as
  `batch_mode`. Migrating to `plugin_args:` loses both anchors.
- **`tasks` / `exclude_tasks` / `n_tasks` not discussed.**
  §2.1 line 354-360 says `--n-tasks` is a CLI flag and records
  as a `provenance.yaml` annotation — so explicitly NOT part of
  the spec / seal, good. But spec-side `tasks: [...]` and
  `exclude_tasks: [...]` ARE on the block (schema.py:327-328).
  They CHANGE the task set materially; whether they should seal
  is a design decision the doc does not make. (Note: today's
  spec-side freeze never sealed benchmark fields, so they don't
  seal by default — but the design's silence implies "no" by
  inheritance rather than by deliberate choice.)

### 5. Recommendation
**Survives-with-named-changes-needed.** The design needs to:
- Add a one-paragraph §2.x on freeze inputs under `kind: harbor`:
  state explicitly that `dataset:`, `tasks:`, `exclude_tasks:`
  do NOT enter the spec-side `sealed_hash` (inheriting today's
  agent-block-only contract) but DO enter via the view manifest
  → agent-side `benchmark_task_id` / `child_task_ids_hash` route.
- Name the agent-side sealed_hash discontinuity for migrated
  specs (old `benchmark_kind` strings vs new `"harbor"`). State
  that pre-migration freeze trees become orphaned — fine under
  captain's "no backwards compat", but not implicit.
- For §2.6 plugin escape, decide: are `plugin_args` part of the
  spec-side canonical YAML (so they round-trip into the file
  hash but not the agent sealed_hash)? Or do they enter the
  agent-side seal via the plugin manifest? The design is silent;
  someone implementing §2.11 commit 4 will have to invent a
  contract.

---

## Construct: taint scanner

### 1. What is the construct today
- **Already shipped in razorback** (the prompt described it as
  "planned via sibling entity `8y`", but the worktree carries it
  in source): `src/razorback/audit/taint.py` (Phase 4a port from
  dataagentbench, header lines 1-8). Companion module
  `src/razorback/audit/subagent_traces.py` ports the read-side
  closure.
- Plan doc at
  `docs/razorback-implementation/plans/phase4a-rk-audit-taint-port.md`
  describes the surface: `rk audit <run-dir>` walks per-trial
  traces; emits per-trial `clean` / `tainted` / `coverage_missing`;
  pattern categories per Phase 4a plan are
  `forbidden_lookup` and related (taint.py:20+) — NOT the
  `{public_egress, dynamic_install, answer_key_access}` triple
  the prompt described (that taxonomy is the `8y` proposal, not
  what's in tree). `--policy strict` exits 23 via
  `TaintFindingsError`.
- No `taint.json` per-cell file shape in current source; the
  current `rk audit` is a stand-alone post-hoc walker, not a
  per-trial sidecar emitter.
- No reference to `taint_status` / `clean_aggregate_score` in
  current source (`grep -rln "taint" src/razorback` returns
  only `audit/taint.py`).

### 2. What does the design propose
- The design doc does not mention "taint", "leak", "policy_mode",
  "public_egress", "answer_key", or "audit" anywhere
  (verified via grep on the file). §2.1, §2.3 (scaffold), §2.8
  (autoresearch hook), and §2.10 (spec amendment scope) are all
  silent on the taint surface.
- §2.7 line 549-551 mentions deny-globs only as a runtime hook
  on the spacedock-solver agent, not as a scanner.
- §1.1 Step 2 (lines 109-127) shows Aanya's `rk score` output —
  it returns `stratified_pass_at_1` + `verdict (vs paper=...)`.
  No `taint_status`, no clean-vs-dirty aggregate.

### 3. Survives cleanly?
**Yes, by being orthogonal — and that is itself the problem.**
The `rk audit` CLI is a separate top-level command on a
post-hoc run-dir; nothing in the new `kind: harbor` block, new
`_build_harbor` translator, or new `rk research new` scaffold
interacts with it. The scaffold's `README.md.j2` template
(§2.3, lines 432-443) does NOT mention `rk audit` as a step in
the autoresearch lifecycle, and `rk score` (§2.8) does not gate
on taint status.

So the contract for `rk audit` is intact: it still walks a
run-dir and decides taint state. But the design's
captain-facing report shape (Aanya's verdict in §1.1 Step 2,
Ben's verdict in §1.2 Step 3) silently DROPS taint. A
researcher following the scaffold's README will reproduce a
paper baseline and ship the verdict without ever running
`rk audit`.

### 4. Friction
- **Scope-overlap (omission).** The design's autoresearch
  lifecycle (§2.8 + §2.3 scaffold README) is the new
  canonical-path; if it does not call `rk audit`, the taint
  scanner becomes shelfware for the new-researcher persona. The
  Phase 4a plan (`phase4a-rk-audit-taint-port.md`, line listing
  AC ↔ task map) names the contract — the design under review
  does not honor it.
- **Naming gap.** The prompt's `8y` taxonomy
  (`public_egress`, `dynamic_install`, `answer_key_access`,
  `policy_mode: {audit|taint|fail}`) does not match what's in
  `audit/taint.py` today (`FORBIDDEN_SHELL_PATTERNS` keyed by
  `forbidden_lookup` etc., taint.py:19+). If `8y` ships, the
  field names will change underneath `rk audit` without the
  `hm` design accommodating either.
- **Captain report shape underspecified.** §1.1 Step 2's `rk
  score` output (lines 122-127) is the design's only
  captain-facing artifact shape. It carries no place for
  `taint_status` or a `clean_aggregate_score` (e.g.
  "stratified_pass_at_1: 0.412 across N=450, of which K=N-T are
  clean"). Retrofit will be needed; the design did not
  anticipate it.
- **Scaffold pre-wiring missing.** §2.3's scaffold drops a
  `drivers/matrix.sh.tmpl` (line 442) but the template's
  contents are not specified, and the README.j2 does not call
  `rk audit` as a step. A new researcher gets no nudge toward
  the taint surface at all.

### 5. Recommendation
**Survives-clean for `rk audit` itself, but
survives-with-named-changes-needed for the captain-facing
report shape.** Concretely:
- Add a §2.x to the design: "After `rk run`, before `rk score`
  / `rk diff`, the autoresearch loop calls `rk audit
  <run-dir>` and aborts the lifecycle on
  `--policy strict` exit 23." Include this in
  `docs/templates/research-project/README.md.j2`.
- Extend §1.1 Step 2 + §1.2 Step 3 sample `rk score` output to
  show a `taint_status:` line (even if just `clean`). Otherwise
  the design implicitly trains researchers to skip audit.
- Coordinate with the `8y` entity (if/when it lands) on the
  field-name set, so the scaffold's README + the scaffold's
  defaults table either lead or follow `8y`'s taxonomy — not
  diverge.

---

## Construct: spacedock-solver (+ `ne`'s in-flight FO dispatch wiring)

### 1. What is the construct today
- `SpacedockSolverAgent` at
  `src/razorback/agents/spacedock_solver.py:46-372` extends
  `harbor.agents.base.BaseAgent`. `__init__` (lines 50-141)
  computes `sealed_hash` from six canonical inputs + task
  identity (lines 117-129), refuses cross-job resume mismatches
  (lines 134-138), and defers inner-agent construction to
  `_build_inner_agent` (lines 273-290), which dispatches
  to `_runtime/claude.py` (`RazorbackClaudeCode`),
  `_runtime/codex.py`, or `_runtime/pi.py`.
- `_compose_run_instruction` (lines 300-307) prepends the
  solver workflow's `README.md` text under a
  `# Solver workflow instructions` header before the harbor task
  instruction. That is the ENTIRE composition surface today on
  this branch — no ROLE prefix, no FO plugin-dir, no spacedock
  skill mount, no subagent_smoke gate.
- `run()` (lines 345-354) calls `_inner.run(composed_instruction,
  ...)` and commits `run/before-agent` + `run/after-agent`
  checkpoints to the freeze repo.
- `git log src/razorback/agents/spacedock_solver.py
  src/razorback/agents/_runtime/` on this worktree shows the
  last touch is commit `5eba250` ("add codex shell lookup
  guard") — `ne`'s `first-officer` + `--plugin-dir` + smoke-gate
  work is NOT in this branch's source. The runtime adapter
  `RazorbackClaudeCode` at `_runtime/claude.py:22-131` carries
  no FO / plugin-dir / spacedock-skill-mount wiring either.

### 2. What does the design propose
- Aanya's `baseline.yaml` (§1.1 lines 82-105) sets
  `agent.kind: spacedock_solver`, `runtime: claude`, `model:
  claude-haiku-4-5`, `solver_workflow: ./solver_workflows/
  baseline`, `max_turns: 16`, `max_budget_usd: 2`. Ben's spec
  (§1.2 lines 236-261) sets the same `kind` with `runtime: claude`,
  `model: claude-opus-4-7`, `max_turns: 40`, `max_budget_usd: 12`,
  `reasoning_effort: xhigh`.
- §2.3's scaffold writes a `solver_workflows/baseline/README.md`
  (the directory shape is shown in §1.1 lines 71-72; the
  template lives at
  `docs/templates/research-project/solver_workflows/baseline/
  README.md.j2` per §2.3 lines 434-436). The design says
  "generic spacedock workflow shape" and does not enumerate
  what that shape contains.
- §2.4 (lines 474-490) describes `_build_harbor` purely on the
  benchmark side — it does not interact with
  `_compose_run_instruction` or with the agent block at all.
- §2.8 (autoresearch hook, lines 558-571) discusses `rk score` +
  `rk diff` only — no spacedock-skill / FO-plugin step.
- §2.9 (lines 572-585): scaffold drops a
  `drivers/matrix.sh.tmpl`. Contents unspecified; no mention of
  a subagent_smoke gate.

### 3. Survives cleanly?
**Does not survive cleanly — the design implicitly assumes `ne`
ships AND the scaffold's templates match `ne`'s shape, neither of
which is named.**

- Aanya's `baseline.yaml` sets
  `agent.kind: spacedock_solver` and points
  `solver_workflow:` at a directory. On this branch, the only
  thing `_compose_run_instruction` does with that directory is
  read its `README.md` (spacedock_solver.py:292-307). If `ne`
  has not shipped, the scaffold's
  `solver_workflows/baseline/README.md.j2` becomes the entire
  contract — and the design does not say what it contains. The
  template is the load-bearing artifact and is undefined.
- If `ne` HAS shipped (per the debrief), then
  `_compose_run_instruction` will gain a ROLE prefix +
  spacedock-skill mount, and the README.j2 template must NOT
  re-include those (else duplication). The design does not
  acknowledge the dependency in §2.3 or §2.11.
- §1.2 step 3 (lines 287-298) shows the matrix dispatcher
  running 500 trials at concurrency 4. The just-shipped
  subagent_smoke gate (`ne`) fires before dispatch on a
  trace-shape assertion. The design's §2.9 does not mention
  this; if the scaffolded `drivers/matrix.sh.tmpl` does not
  pre-wire the smoke gate hook, the user gets no protection
  against the "spacedock crew didn't load" silent-fail.
- Ben's spec uses `agent.kind: spacedock_solver`. There is no
  `agent.kind: claude-cli` scenario in §1 or §2. The design
  does not discuss what happens if a researcher picks
  `claude-cli` (`ClaudeCliAgentBlock` at schema.py:39-45) —
  notably whether the smoke-gate in `ne`'s matrix dispatcher
  still fires correctly without an inner spacedock crew loop
  to gate. The design assumes `spacedock_solver` is the only
  agent path; it isn't.

### 4. Friction
- **Hidden coupling on a sibling entity.** §2.3's scaffold
  ships `solver_workflows/baseline/README.md.j2` (line 435).
  Its contents are exactly what `ne` is finalising (ROLE prefix,
  spacedock skill mount, post-`run()` manifest write). The
  design's §2.11 commit sequence pre-supposes `ne` lands; it
  does not list `ne` as a dependency commit, nor does it gate
  commit 2 (the scaffold) on `ne` completion.
- **Naming-collision risk.** `solver_workflows/baseline` (the
  on-disk directory in Aanya's repo, §1.1 line 71) and the
  scaffold template's `baseline/` dir share a name. Researchers
  copying baseline → `h0001-duckdb-examples` (§1.1 line 153)
  invalidate the `solver_workflow_content_hash`
  (freeze.py:64-78) — which is correct behavior, but the
  scaffold's README needs to teach this. The design is silent.
- **Smoke-gate dispatch coverage.** The matrix dispatcher
  template `drivers/matrix.sh.tmpl` (§2.9 line 577) is the user-
  edited surface — it is the only place to wire the subagent
  smoke-gate per-cell. Without an opinionated template, a new
  researcher's first 500-trial swe-bench run silently degrades
  to the claude-CLI bare path if their spacedock skill mount
  doesn't fire — exactly the failure mode `ne` is shipping to
  prevent. The design does not anchor the contract.
- **`_build_harbor` ↔ `_compose_run_instruction` interaction
  unstated.** Today they don't interact (good). Under `ne`, the
  composed instruction depends on the spacedock skill mount and
  the FO plugin-dir, neither of which is benchmark-side. The
  design's §2.4 cleanly partitions benchmark vs agent; that
  partition holds. But the captain-decision-point (c) in §3
  ("post-migration BenchmarkBlock shape") does not pair with a
  captain-decision-point on the agent-block shape, which is
  where `ne`'s changes land. The design treats the agent block
  as a black box.

### 5. Recommendation
**Survives-with-named-changes-needed bordering on
does-not-survive-needs-redesign.** Specifically:
- Add §2.3.x: enumerate what
  `solver_workflows/baseline/README.md.j2` MUST contain at
  scaffold time. Pin the contract to whatever `ne` ships
  (post-merge), or pin to today's pre-`ne` shape and add a
  follow-up commit. Without this, the scaffold ships a stub
  that may or may not work end-to-end.
- Add §2.11 commit-0: explicitly depend on `ne` merging before
  commit 2 (scaffold) lands. Or: define the scaffold to be
  `ne`-agnostic by writing only the harbor-task-side knobs and
  leaving solver wiring as a `# TODO` for the researcher.
- Add §2.3.y: the scaffolded `drivers/matrix.sh.tmpl` MUST
  include the subagent_smoke gate hook from `ne`. Otherwise
  the design is shipping a silent-fail-by-default dispatcher.
- Add a brief note on `agent.kind: claude-cli` — does the
  scaffold support it (with what defaults)? If not, refuse at
  `rk research new` with a clear error. If yes, define the
  smoke-gate's behavior in the no-spacedock path.

---

## Cross-construct findings

1. **The design's "thin shim" framing for §2.6 (plugin escape
   valve) is the structural defect that cascades into both the
   `query_mode` and the freeze constructs.** The plugin-args
   map is free-form precisely because the design wants to push
   complexity out of razorback core; but `query_mode` requires
   typed validation + trial_name_map construction, and `freeze`
   requires a canonical contribution to the sealed_hash.
   Pinning the plugin-shim contract — its CLI invocation,
   manifest emission, and seal contribution — early matters
   more than the design recognizes. Both Construct A and
   Construct B's friction collapses if §2.6 is tightened to a
   defined manifest-out + per-plugin-version contract.

2. **The autoresearch lifecycle (§2.8 + §2.3 scaffold README)
   is the design's normative path, but it omits two surfaces
   that already exist (`rk audit`) or are mid-flight (`ne`'s
   FO/smoke-gate).** §1.1 + §1.2 walk a researcher through
   `rk freeze` → `rk run` → `rk score` → `rk diff`. Neither
   `rk audit` (taint) nor the spacedock-skill / subagent_smoke
   gate appears in the walk. Both are protections against
   silent-fail modes (leakage, no-spacedock-mount). The design
   trains researchers to ship verdicts without them.

3. **`benchmark_kind` is a hidden cross-construct coupling.**
   The view-manifest field `benchmark_kind` enters the
   agent-side sealed_hash (seal.py:73-82) via
   `_discover_task_identity_from_manifest`
   (spacedock_solver.py:214-245). The `_build_harbor` translator
   writes that manifest (per §2.7 line 552-555,
   `materialize_ade_harbor_task_view` stays). After migration,
   every migrated spec gets a NEW sealed_hash for otherwise-
   identical workloads. The design's "no backwards compat" rule
   covers this, but the design does not NAME the side effect —
   so researchers carrying half-run freeze trees from
   pre-migration runs will hit `SeedMismatchError` (exit 20)
   with no in-doc forewarning.

4. **Scaffold templates are the load-bearing surface, and
   their contents are unspecified.** §2.3 lists the template
   tree (lines 429-443) but defines NOTHING about the inner
   shape of `solver_workflows/baseline/README.md.j2`,
   `drivers/matrix.sh.tmpl`, or
   `specs/baseline.yaml.j2`'s defaults for non-tabled
   benchmarks. The design's `rk research new` UX promise rests
   entirely on those templates being correct — and three
   reviewers (taint, freeze, solver) all need different things
   to be IN those templates. The design needs a §2.3.x
   sub-section: per-template contract.

---

## Summary verdict

**design-needs-named-changes.**

The benchmark-block collapse + `_build_harbor` translator
shipped in §2.1, §2.4, §2.5 are clean (already in tree at
commits `6cbcaa8`, `f9f3143`). The scaffold (§2.3) and the
plugin escape valve (§2.6) carry enough underspecification
that a downstream implementer of §2.11 commits 2-5 will have
to invent contracts the design declined to make — and three of
the four constructs surveyed will be silently weakened in the
process. Tighten §2.6 (plugin manifest contract), §2.3 (per-
template contents), and add a one-paragraph §2.x on freeze
inputs + a one-paragraph §2.x on the audit/smoke-gate hooks in
the autoresearch lifecycle. With those, the design ships.
