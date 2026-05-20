# Razorback reconciliation plan

**Reconciles the current razorback codebase to the end-state described
in [`2026-05-19-razorback-on-harbor.md`](../specs/2026-05-19-razorback-on-harbor.md).**

**Date:** 2026-05-19
**Status:** Draft

---

## 0. Reconciliation strategy

### 0.1 Fresh-extract-and-sideline

The KEEP set from the current codebase against the v2 spec is small.
This plan **rewrites from the spec**, not from the existing code.
Where the existing codebase has *proven* behavior, the new v2 module
**extracts the proven code verbatim with attribution** rather than
rewriting it. Extractions are named explicitly per phase. This is
surgical re-use, not a wholesale port.

As each canonical surface gets its v2 implementation, the old
implementation moves to **`src/razorback/_legacy/`** via `git mv`.
The old code remains importable from there (for parity tests, for
rollback) but is out of razorback's canonical surface.

`_legacy/` is the holding tank, not a separate package. It lives
under `src/razorback/` so it ships with razorback during the
reconciliation window.

### 0.2 Walking-skeleton invariant

**At every phase boundary, razorback can run a DAB benchmark
end-to-end and produce a non-degraded `summary.json`.** Phase 0
captures the v1 baseline; Phase 2 establishes a v2-path baseline
(live-DB harbor adapter, which by design differs from the v1
dump-file baseline). Subsequent phases use whichever baseline
matches the path under test.

**Score-parity is a Phase 4+ test**, not a per-phase invariant. The
per-phase invariant is *runnability*. Score-parity uses `rk diff`
(which only exists from Phase 4 onward) on same-adapter, same-agent
pairs.

A phase that breaks runnability gets rolled back. Do not proceed.

### 0.3 Surfacing uncertainty early

Every uncertainty that could invalidate a later phase is probed in
the earliest phase that can detect it. Decisions made on incomplete
information are explicitly named (D1...DN) and have an "outcome
detected by..." citation pointing at the probe that resolves them.

Phase 0's task list is dominated by probes, not edits.

### 0.4 Discipline

- v2 code is **written from the spec**. Old code is referenced only
  for documented extractions.
- Every extraction names the source path + attribution in a commit
  message and (where helpful) an ABOUTME comment.
- Sidelining is `git mv` only — code moves, but is preserved.
- Each phase has explicit acceptance criteria. The plan does not
  proceed past a phase whose ACs are not all satisfied.

### 0.5 Out of scope for this plan

- The harbor-native DAB adapter implementation. Phase 2 defines its
  contract; the implementation is a parallel work stream this plan
  blocks on at Phase 2's acceptance.
- The harbor-native ade-bench adapter port. Same pattern.
- The autoresearch workflow's instantiation against DAB. Downstream
  of v2 razorback.

---

## Phase 0: Probe, decide, baseline, re-file

**Acceptance criteria.**

**AC-0.1 — v1 reconciliation baseline + deterministic micro-spec
captured.** Two artifacts:

(a) A full DAB-claude experiment ran against current razorback in its
current shape (in-tree adapter, dump-file mode); the run-dir headline
score and per-dataset breakdown are committed to
`docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`. This
is the **pre-correction reference** — it captures behavior on the
degraded access path and is used for Phase 2's expected-shift-band
documentation, not as the structural walking-skeleton anchor.

(b) A **deterministic smoke micro-spec** is committed at
`examples/specs/_deterministic-smoke.yaml`: one task (bookreview's
simplest query), one trial, `temperature: 0.0`, fixed seed where the
runtime honors it, content-hashed prompt content. Its expected
pass/fail outcome is recorded. **This micro-spec is the
walking-skeleton anchor for Phases 1-3** — eyeball comparison of
full-DAB headlines at N=5 is too noisy to catch a 5-10pp regression;
the deterministic smoke is.

**AC-0.2 — harbor plugin contract validated by execution (resolves
D1).** The entry-point group name + registration shape for external
installed agents AND external benchmark adapters are documented from
harbor's source (`cli/template-adapter/`, `cli/adapter_wizard.py`,
`publisher/publisher.py`). **Validation is by execution, not by
reading:**

(a) A 20-LoC stub `BaseAgent` subclass is written in a throwaway
package; the package's `pyproject.toml` registers it via the suspected
entry-point group; the package installs into razorback's venv.

(b) `harbor run` is invoked against a spec with `agent.kind: <stub>`.
Either the stub's `run()` is called (entry-point dispatch works) or
the invocation fails in a way that names the gap.

(c) The same is repeated for the external-benchmark-adapter
entry-point group.

If either entry-point dispatch fails, the fallback path (razorback's
`rk run` does spec translation before invoking `harbor run`) is the
chosen route. Mechanism validation precedes Phase 3's commitment.

**AC-0.3 — harbor's spec format compatibility probed.** Razorback's
current spec format is compared field-by-field against the JobConfig
harbor's `harbor run` accepts. Any razorback fields harbor does not
accept (e.g., razorback's `spacedock_solver` agent block kwargs
specifically) are documented with a translation strategy (entry-point
direct or `rk run` rewrite, decided by AC-0.2).

**AC-0.4 — harbor installed-agent constructor probed.**
`harbor.agents.installed.claude_code.ClaudeCode.__init__` signature is
documented. Razorback's runtime-adapter `SpacedockSolverAgent` MUST be
able to construct an instance via the kwargs path; if there's a
hidden coupling (mandatory kwarg razorback can't supply), it is named
and a mitigation is documented.

**AC-0.5 — harbor's job-resume mechanism probed.**
`harbor jobs resume` is invoked against a known-incomplete fixture
run-dir; the resume semantics are documented. Razorback's halt-resume
contract (spec §4.4) is checked against what harbor actually does on
resume. Conflicts named explicitly.

**AC-0.6 — harbor's run-dir layout probed.** The actual files harbor
writes per trial under `logs_dir/` are listed. Razorback's
`agent_freeze/` subtree assumption (writable under `logs_dir/`,
non-colliding) is confirmed.

**AC-0.7 — D2 decided.** Captain has picked: claude-only at v2.0
(codex/pi NotImplemented stubs), or all three runtimes.

**AC-0.8 — D5 decided.** Captain has picked: sibling-package
(`packages/razorback-plugin-dab/`) or new repo for the DAB harbor
adapter.

**AC-0.9 — baseline-comparator policy locked.**

- **Phases 1-3 walking-skeleton check:** the deterministic
  micro-spec from AC-0.1(b). Its pass/fail is reproducible across
  reconciliation phases; a regression flips it. Full-DAB headlines
  at N=5 are too noisy to serve at this stage.
- **Phase 2 acceptance (live-DB vs dump-file):** per-dataset
  expected-shift bands pre-registered before the comparison (see
  AC-2.6 below). "Eyeball within X%" is replaced by named bands.
- **Phase 3+ walking-skeleton check:** Phase 2's live-DB baseline
  (AC-2.5) becomes the canonical anchor; v1 dump-file baseline
  retires to "pre-correction reference" status.
- **Phase 4+ acceptance:** `rk diff` paired-bootstrap CI (cluster
  bootstrap by query per AC-4.2) on same-adapter, same-agent pairs.

**AC-0.10 — module inventory committed with file:line citations.**
`src/razorback/` modules are classified KEEP-EXTRACT, ADAPT-EXTRACT,
DROP, or PORT-OUT against the v2 spec at
`docs/superpowers/plans/2026-05-19-razorback-inventory.md`. Every src
module classified; every v2-spec-named artifact accounted for. **For
each KEEP-EXTRACT and ADAPT-EXTRACT module, the inventory cites
specific file:line ranges of the proven behavior to preserve** —
especially for freeze-resolver internals (retry/backoff against
provider 503s, provider-specific error-class taxonomy, Anthropic 503
patterns vs OpenAI auth-vs-org-quota distinctions), auth handling
(the `.env`-via-`dotenv_values` discipline per FU-1 M3 AC-3), and
the FU-1/FU-2 acceptance-test contracts (image-override semantics,
`extra_env` mechanism). Phase 4 + Phase 1 extractions reference these
citations.

**AC-0.14 — test classification committed.** Symmetric to AC-0.10:
every test file under `tests/` is classified KEEP-VERBATIM (lift into
v2's test tree as-is, just re-pointed at v2 paths), RE-AUTHOR
(behavior survives in v2 but the test needs new framing), or DROP
(tests behavior of a module marked DROP/PORT-OUT). Committed to
`docs/superpowers/plans/2026-05-19-razorback-test-inventory.md`.
Specifically: every FU-1 / FU-2 acceptance test is KEEP-VERBATIM
unless its target behavior moves to the DAB harbor adapter (then
PORT-OUT to the adapter's test suite).

**AC-0.11 — `src/razorback/_legacy/` exists.** Empty (with
`__init__.py` carrying the holding-tank convention docstring).

**AC-0.12 — in-flight backlog re-filed under v2 shape.**
PKG-3/4/5/6/7/10 archived; PKG-1, PKG-2, PKG-8, PKG-9 re-scoped to
their v2-surviving content; razorback-implementation workflow
dispatch paused.

**AC-0.13 — 2026-05-18 design doc marked SUPERSEDED** with a pointer
to the v2 spec.

**Walking-skeleton check.** AC-0.1's baseline run itself confirms
current razorback runs DAB end-to-end.

**Uncertainty surfaced.**
- Whether harbor's plugin contract supports external installed agents
  (resolves AC-0.2 → D1)
- Whether razorback's spec format requires any translation to reach
  `harbor run` (AC-0.3)
- Whether harbor's halt-resume semantics conflict with razorback's
  sealed-input invariants (AC-0.5)
- Whether the v1 dump-file baseline is a usable comparator at all
  given the access-mode mismatch (AC-0.9)

**Sideline at phase end.** None. Phase 0 is probes + docs + decisions.

---

## Phase 1: `rk run` v2 wrapper

**Acceptance criteria.**

**AC-1.1 — walking skeleton holds.** `rk run
examples/specs/<benchmark>-claude.frozen.yaml` produces a run-dir
with `summary.json` against the in-tree DAB adapter (unchanged from
Phase 0).

**AC-1.2 — `rk run` is the v2 wrapper per spec §3.2 + §8.1.** Reads
frozen spec; runs alias-drift pre-check (re-resolves model alias,
refuses with `AliasDriftError` on drift unless `--allow-alias-drift`);
delegates execution to `harbor run`; passes exit code through (exit
30 reserved for harbor runtime failure); writes
`spec.frozen.yaml` + `provenance.yaml` into the harbor-produced
run-dir.

**AC-1.3 — extractions preserved.** Proven behavior from the current
codebase has been extracted with attribution into the v2 implementation:
- alias-drift detection (resolved-version comparison against
  `provenance.yaml.model_resolved_version`)
- auth handling (`.env` via `dotenv_values`, NEVER `os.environ`, per
  the FU-1 M3 AC-3 contract)
- run-dir creation helpers (path conventions, manifest write)

**AC-1.4 — superseded `run.py` and helpers sidelined.** The previous
`src/razorback/run.py` and any orchestration helpers replaced by the
new `rk run` live under `src/razorback/_legacy/` via `git mv`.

**AC-1.5 — unit tests cover the alias-drift pre-check** (mocked
provider API) and the harbor-passthrough behavior. Extracted
behaviors (auth, alias-drift logic) keep their existing tests,
re-pointed at v2 paths.

**AC-1.6 — `uv run pytest` exits 0.**

**Walking-skeleton check.** `rk run` against bookreview-claude
produces a runnable run-dir. The score is not parity-checked at this
phase (per the AC-0.9 policy); the test is "did it run".

**Uncertainty surfaced.**
- Whether the current `rk run` path is cleanly separable from the
  spec → JobConfig translation and the agent-registration plumbing.
  If not, the Phase 1 refactor is larger than the spec suggests.
- Whether harbor's in-process `Job.create()` / `Job.run()` invocation
  shape from a Python wrapper is what razorback assumes, or whether
  a subprocess-to-`harbor run` is the right delegation.

**Sideline at phase end.** `src/razorback/run.py` + replaced
orchestration helpers → `src/razorback/_legacy/run.py` etc.

---

## Phase 2: DAB harbor adapter — parallel sibling project

**Acceptance criteria.**

**AC-2.1 — walking skeleton holds (both paths).** Razorback can still
run DAB via the in-tree adapter (Phase 1 path); razorback can also run
DAB via the new harbor-DAB adapter via `rk run`. Both produce
runnable run-dirs.

**AC-2.2 — DAB harbor adapter exists and publishes.** The new package
(at the location D5 decided) builds; `harbor adapter list` (or
local-discovery equivalent) shows the new DAB adapter.

**AC-2.3 — per-task content ported.** All 12 DAB datasets are
represented as harbor task definitions in the new package; prepare,
verify, per-task environment (including the live-DB compose stack
that was PKG-3's surviving content), and per-task hook config
(DISALLOWED_TOOLS + workspace-README variants from PKG-9's surviving
content) are present.

**AC-2.4 — live-DB mode confirmed.** A bookreview run via the new
harbor-DAB adapter shows postgres-protocol evidence in the agent's
trajectory (a `psql --host dab-postgres` invocation or
`dab-postgres:5432` connection string in `events.jsonl`), confirming
live-DB access rather than dump-file grepping.

**AC-2.5 — live-DB baseline established and promoted to canonical
anchor.** The headline score and per-dataset breakdown of a full
DAB-claude run via the new harbor-DAB adapter are committed to
`docs/superpowers/plans/2026-05-19-reconciliation-baseline.md` as the
**canonical baseline from Phase 3 onward**. The v1 dump-file baseline
(AC-0.1(a)) is explicitly retired to "pre-correction reference"
status in the same file with a note explaining why
(dump-file-leakage means the v1 score is methodologically tainted
relative to the live-DB protocol).

**AC-2.6 — per-dataset expected-shift bands pre-registered before
the v1-vs-v2 comparison.** Before running the comparison that
produces AC-2.5's baseline, a per-dataset prediction is committed to
the baseline doc: for each of the 12 DAB datasets, the expected
direction + rough magnitude of the live-DB-vs-dump-file score shift
(e.g., bookreview: live DB **drops** score significantly because the
in-tree-adapter agent grepped `books_info.sql`; agnews: roughly
unchanged because it doesn't have a dump-file leak vector). The
comparison's acceptance criterion is "observed shifts fall within
the pre-registered direction; magnitudes within 2x of prediction",
not "scores match". A surprise reversal flags a real bug.

**AC-2.7 — in-tree adapter still functional.**
`src/razorback/benchmarks/dab/` is unchanged from Phase 1; an
in-tree-adapter smoke run still produces the v1-baseline-comparable
result.

**AC-2.8 — cross-dataset aggregation architecture decided
(resolves D7).** The DAB paper's stratified pass@1 across 12
datasets is computed by razorback's `rk diff` operating on a
**stratum-tagged trial table** the adapter emits. The adapter is
responsible for tagging each trial with its stratum metadata
(dataset name, query difficulty bucket, etc.); razorback's `rk diff`
is responsible for the stratified aggregation math. This split
keeps `rk diff` benchmark-agnostic and the adapter
benchmark-specific. Phase 2's smoke run validates the contract.

**Walking-skeleton check.** TWO smokes at Phase 2's end — in-tree
adapter path and harbor adapter path. Both produce summary.json.
Scores are NOT compared directly to each other (access mode differs
by design per AC-0.9 policy).

**Uncertainty surfaced.**
- Whether harbor's adapter format accepts DAB's per-task shape
  without major restructure (AC-2.3 risk; mitigation: port bookreview
  end-to-end first and surface mismatches before porting the other
  11).
- Whether `harbor publish` can publish externally-developed adapters,
  or whether harbor's catalog is curated and only in-tree adapters are
  discoverable (resolves under AC-0.2; Phase 2 acceptance depends on
  AC-0.2 having confirmed a feasible discovery path).
- Whether harbor's metric framework can express stratified pass@1
  natively or whether razorback owns it (AC-2.7).
- Whether the live-DB mode produces meaningfully different scores
  from dump-file mode (AC-2.4 confirms live-DB; AC-2.5 measures the
  resulting score and documents it; score difference is expected, not
  a failure).

**Sideline at phase end.** None. The in-tree DAB adapter stays at
its canonical location until Phase 6.

---

## Phase 3: SpacedockSolverAgent v2 — runtime adapter alongside

**Acceptance criteria.**

**AC-3.1 — walking skeleton holds; Phase 3 does NOT depend on Phase 2.**
The v2 SpacedockSolverAgent class is exercised against the **in-tree
DAB adapter** (which is still functional per AC-2.7) — Phase 3 ships
without requiring Phase 2's harbor-DAB adapter to be complete. The
deterministic micro-spec (AC-0.1(b)) passes against both
(v1-agent × in-tree adapter) and (v2-agent × in-tree adapter). When
Phase 2's harbor-DAB adapter does become available, the same v2 agent
class runs against it too (validated by Phase 6's promotion smoke);
Phase 3 itself does not block on it. This decouples the critical
path.

**AC-3.2 — new `SpacedockSolverAgent` class exists and works.** At
`src/razorback/agents/spacedock_solver_v2.py`, written from spec §4 +
§8.4. Routes via `agent.kind: spacedock_solver_v2` (the canonical
name `spacedock_solver` still routes to the v1 class). Constructor
validates kwargs against the pydantic schema; computes sealed_hash
from `(model, sampling, solver_workflow content hash, prompt content
hashes, spacedock skill version, harbor agent kwargs)`; refuses on
resume mismatch; constructs the inner harbor installed-agent via the
per-runtime adapter sub-module.

**AC-3.3 — per-runtime adapter sub-modules exist.**
`src/razorback/agents/_runtime/claude.py` is implemented (functional
per AC-3.5). `_runtime/codex.py` and `_runtime/pi.py` exist as
NotImplemented stubs per D2 if claude-only was chosen, or as
functional implementations if all-three was chosen.

**AC-3.4 — extractions preserved.** Proven behavior extracted from
current code:
- `compute_sealed_hash`, `prompt_sha256` from `agents/seal.py`
- `assert_phase_stats_schema` from current
  `agents/spacedock_solver.py`
- `_refuse_on_resume_mismatch` semantics (adapted to the v2
  sealed-hash inputs)
- Auth validation (ANTHROPIC_API_KEY vs CLAUDE_CODE_OAUTH_TOKEN
  exclusivity)
- FU-1 `extra_env` mechanism (auth via harbor's `extra_env` kwarg,
  env-field redaction on disk)

**AC-3.5 — claude runtime smoke succeeds against in-tree adapter.**
A spec with `agent.kind: spacedock_solver_v2` + `runtime: claude` +
the **in-tree DAB adapter** + a minimal solver_workflow dir (one
stage, one mod) runs bookreview end-to-end. The inner `claude_code`
agent receives the expected kwargs (verified by instrumentation or
integration test); `sealed_hash.txt` lands in `agent_freeze/`. (When
the harbor-DAB adapter is ready, Phase 6's promotion smoke validates
the v2 class against it; Phase 3 does not block on that adapter.)

**AC-3.6 — halt-resume smoke succeeds.** A bookreview trial is
halted at turn cap; `agent_freeze/.git` shows workspace snapshots;
a resume spec pointing at that freeze proceeds without
`SeedMismatchError` when sealed inputs match, and refuses with
`SeedMismatchError` (exit 20) when a sealed input is perturbed.

**AC-3.7 — entry-point registration verified.** Per D1's outcome
(AC-0.2): either `pyproject.toml`'s
`[project.entry-points."harbor.agents.installed"]` is set and harbor
routes `agent.kind: spacedock_solver_v2` to razorback's class; or
the fallback spec-translation pre-pass in `rk run` rewrites the
agent block before invoking `harbor run`. The chosen path works on
the smoke.

**AC-3.8 — v1 SpacedockSolverAgent still functional.** A spec with
`agent.kind: spacedock_solver` (v1 routing) against either adapter
still runs end-to-end. The v1 class is not edited in this phase.

**AC-3.9 — `uv run pytest` exits 0.**

**Walking-skeleton check.** At least two smokes — v1-class on
in-tree adapter (still works) and v2-class on harbor adapter (newly
works). Both produce summary.json. Score comparability not asserted
at this phase.

**Uncertainty surfaced.**
- Whether per-runtime kwarg construction for claude maps cleanly
  from razorback's spec block to `ClaudeCode.CLI_FLAGS` (AC-3.3 risk;
  mitigation: derive kwarg mapping from the live `CLI_FLAGS` schema,
  not from the design doc).
- Whether harbor's installed `claude_code` agent's workspace-bootstrap
  semantics let razorback copy `solver_workflow` into the trial
  workspace at a known path (AC-3.5 risk; surfaced if the test fails).
- Whether the workflow mods (Phase 5) actually fire on stage
  boundaries when the v2 class runs — this can't be fully tested
  until Phase 5 ships the mods. AC-3.6's halt-resume smoke uses
  hand-faked freeze writes; Phase 5 closes this gap.

**Sideline at phase end.** None. v1 class stays canonical until
Phase 6.

---

## Phase 4: `rk diff` and extended `rk freeze`

**Acceptance criteria.**

**AC-4.1 — walking skeleton holds.** All cells from Phase 3 still
produce summary.json; Phase 4 adds the ability to compare across them
statistically.

**AC-4.2 — `rk diff` produces spec §8.3 statistics.** Given two
harbor run-dirs paired by `(task, query, trial_index)`, the output
JSON carries: per-arm per-query Wilson 95% CI on pass@1 (level via
`--alpha`); per-query exact-McNemar p with exact-binomial fallback
for small discordant counts AND family-wise-adjusted p-values via
Holm-Bonferroni (at `--family-wise-alpha`, default 0.05) — both raw
and adjusted p's are emitted; paired bootstrap CI on the stratified
delta (B via `--bootstrap-iters`, default 10000, percentile method)
**resampling at the cluster level via `--bootstrap-cluster` (default
`query`, since N trials of the same query are not independent
observations)**; MDE at fixed N; achieved-power-at-observed-effect.
`--format markdown` produces a human-readable equivalent. Refuses on
seed-asymmetry between the two runs.

**AC-4.3 — fixture-driven correctness, including cluster +
family-wise.** Hand-computed expected values for Wilson CI, exact
McNemar p (raw + Holm-Bonferroni-adjusted), and paired bootstrap CI
(cluster-bootstrap at the query level) on synthetic paired data
match `rk diff`'s output within tolerance. Cross-checks against
`statsmodels` reference implementations where possible.
**Cluster-bootstrap fixture is load-bearing**: a synthetic dataset
where intra-query trials are perfectly correlated (all N=5 trials
agree per query) shows the trial-level bootstrap CI as
anti-conservatively narrow vs. the query-cluster bootstrap CI; the
test asserts the latter is wider, matching analytical expectation.
**Family-wise fixture is load-bearing**: 12-dataset synthetic where
no real effect exists but uncorrected per-dataset p-values produce
~46% family-wise error rate; Holm-Bonferroni-adjusted p-values bring
family-wise error to the nominal α.

**AC-4.4 — PKG-2 surviving content folded in.** The diff
implementation honors: errored-vs-completed counting (errored trials
are not counted as fails); trial-pairing under retries (a trial that
retried still pairs to its baseline counterpart correctly); silent-drop
guard (trials missing from one arm but not the other are flagged, not
silently dropped from denominators).

**AC-4.5 — `rk freeze` extended with v2 sealed inputs.**
`provenance.yaml` now includes `solver_workflow_hash` (recursive
content hash of the solver_workflow dir), `spacedock_skill_version`
(from `importlib.metadata.version` with per-install-shape fallback),
and `harbor_agent_kwargs_hash` (hash of post-runtime-adapter agent
kwargs). The existing pinning (model alias resolved, image digest,
agent CLI binary hash, prompt content hashes, harbor version) is
preserved.

**AC-4.6 — extractions preserved.** Provider model-version resolution
(Anthropic + OpenAI API calls with retry), Docker image digest pinning
(`docker image inspect` wrapper), agent CLI binary hashing, prompt
content hashing — all extracted from current `provenance/` with
attribution.

**AC-4.7 — same-spec self-diff is statistically null.** Two
back-to-back runs of the same frozen spec produce `rk diff` output
whose stratified-delta paired bootstrap CI includes zero at N=5 (the
runs may differ due to provider non-determinism but should not show
systematic bias).

**AC-4.8 — same-adapter cross-class diff is statistically null.** A
run via (v1-class + harbor adapter) and a run via (v2-class + harbor
adapter), both with the same model + sampling + solver_workflow,
produce `rk diff` output whose stratified-delta paired bootstrap CI
includes zero. **This is the load-bearing test that the v2 agent
class does not change benchmark semantics versus v1.** The comparator
is same-adapter, not against the v1 dump-file baseline.

**AC-4.9 — `uv run pytest` exits 0.**

**Walking-skeleton check.** AC-4.7 + AC-4.8 are the walking-skeleton
checks at this phase: razorback can run, freeze, and diff;
statistical equivalence under nominally-equivalent specs is
demonstrated.

**Uncertainty surfaced.**
- Whether `spacedock_skill_version` is reliably detectable across the
  plugin-vs-package install shapes spacedock uses. If not, the
  fallback names what happens; AC-4.5 includes the fallback semantics.
- Whether the same-adapter cross-class null (AC-4.8) actually holds.
  If it does not, the v2 class is doing something semantically
  different from v1 that the implementation needs to chase down
  before Phase 6 promotion.

**Sideline at phase end.** Old `rk freeze` implementation files
replaced or substantially edited by Phase 4 work move to
`src/razorback/_legacy/` if there's a non-trivial divergence;
otherwise extension-in-place is fine.

---

## Phase 5: Workflow templates + generic mods

**Acceptance criteria.**

**AC-5.1 — walking skeleton holds.** Razorback continues to run DAB
end-to-end via all Phase 4 paths.

**AC-5.2 — workflow README templates exist and declare
`experiment.max_budget_usd`.**
- `docs/templates/experiment-workflow/README.md` per spec §5.1:
  six stages (pending, propose, smoke, full, analyze, conclude);
  sd-b32 ID style; required mods named (leak-guard,
  tool-deny-runtime, baseline-compare, cost-ceiling). The template
  spec includes a `experiment.max_budget_usd` field; the
  experiment-workflow's cost-ceiling enforcement reads it.
- `docs/templates/run-workflow/README.md` per spec §5.2: four stages
  (pending, reconciling, completed, failed); required mods named
  (stage-boundary-freeze, phase-stats-writer).
- Both parse against spacedock's workflow-README schema.

**AC-5.3 — generic mods exist.** Six mods under
`docs/templates/mods/`:
- `leak-guard.md` — at propose, runs the static constraints check
  against the solver workflow README; refuses on violation.
- `tool-deny-runtime.md` — wires PreToolUse hooks into the
  spacedock-solver agent; blocks the benchmark's `DISALLOWED_TOOLS`
  list at runtime. Required alongside `leak-guard` for two-layer
  leak defense.
- `baseline-compare.md` — at analyze, invokes `rk diff` and writes
  the result into the entity body.
- `cost-ceiling.md` — at smoke and full, maintains a **running
  total** of spent budget across all dispatched runs in the
  experiment; refuses dispatch when running-total + next-estimate
  would exceed `experiment.max_budget_usd`. Per-trial enforcement
  is harbor's installed agent; per-experiment enforcement is this
  mod.
- `stage-boundary-freeze.md` — fires on the spacedock-solver's
  stage-completion signal; commits the workspace to
  `agent_freeze/.git`.
- `phase-stats-writer.md` — fires at the same boundary; writes
  per-stage tokens (in/out/reasoning/cache-read/cache-write) +
  cost + wallclock to `phase_stats.json`.

**AC-5.4 — mod schema + hook-fire tests pass for all six mods.** Each
mod parses against spacedock's mod schema; each mod's declared hook
fires on the expected event in a fixture workflow. **The
tool-deny-runtime test specifically verifies that a fixture spec with
a forbidden tool invocation (e.g., `pip install datasets`) inside
the agent's trajectory triggers a PreToolUse denial event in
`events.jsonl`.** **The cost-ceiling test verifies running-total
behavior**: two sequential dispatches each within per-trial budget but
whose sum exceeds the experiment ceiling trigger refusal on the
second dispatch.

**AC-5.5 — package data shipping.** `pyproject.toml` ships
`docs/templates/` so a captain can copy templates into a new
project.

**AC-5.6 — phase-stats integration works.** The
`stage-boundary-freeze` + `phase-stats-writer` mods, when wired into
a workflow that runs under `agent.kind: spacedock_solver_v2`, produce
`agent_freeze/.git` snapshots and a `phase_stats.json` whose schema
validates against `assert_phase_stats_schema`. This closes the gap
AC-3.6 noted (the v2 class's freeze contract was tested with
hand-faked writes; Phase 5 tests it with the real mods firing).

**AC-5.7 — end-to-end hypothesis smoke.** A captain copies the
experiment-workflow template into a fresh dir, instantiates it
against DAB via the new harbor adapter, runs ONE hypothesis
end-to-end (propose → freeze → smoke → analyze → conclude). The full
path works; the analyze stage produces a `rk diff` against a chosen
baseline; the conclude stage is reachable.

**AC-5.8 — `uv run pytest` exits 0.**

**Walking-skeleton check.** AC-5.7's end-to-end hypothesis smoke is
the strongest single demonstration of v2 razorback's integration
shape working as a unit.

**Uncertainty surfaced.**
- Whether spacedock's mod-hook contract matches what razorback's
  generic mods assume (AC-5.4 risk; reference shape:
  `docs/razorback-implementation/_mods/pr-merge.md`).
- Whether the `leak-guard` constraints file format is rich enough
  for real solver-workflow READMEs (AC-5.3; the format starts small
  — YAML allow/deny lists for paths — and expands when real workflows
  surface needs).
- Whether the `cost-ceiling` mod's cost estimate is accurate enough
  to be useful (rough estimate may over- or under-shoot real
  per-trial cost by 2x; surface the actual numbers from AC-5.7).

**Sideline at phase end.** None — no legacy templates to displace.

---

## Phase 6: Promote v2 to canonical, sideline superseded v1

**Acceptance criteria.**

**AC-6.1 — walking skeleton holds.** A DAB benchmark runs end-to-end
via the canonical v2 path (`agent.kind: spacedock_solver` routing to
the v2 class) after the rename + sideline.

**AC-6.2 — `spacedock_solver` routes to v2.**
`agent.kind: spacedock_solver` invokes the v2 runtime-adapter class.
`pyproject.toml`'s entry-point (or the `rk run` translation, per D1)
is updated. The previous `spacedock_solver_v2` discriminator is
removed.

**AC-6.3 — v1 class sidelined.** The previous standalone
`SpacedockSolverAgent` moves to
`src/razorback/_legacy/agents/spacedock_solver_legacy.py`. Optionally
accessible via `agent.kind: spacedock_solver_legacy` for emergency
rollback during the reconciliation window; carries a DeprecationWarning
on instantiation. **This is its own commit** (`sideline: v1
SpacedockSolverAgent → _legacy`).

**AC-6.4 — non-survivor modules sidelined, one commit per logical
group, in this order:**

| Commit | Sideline target | Reason |
|---|---|---|
| 1 | `src/razorback/agents/{claude_cli,codex_cli}.py` → `_legacy/agents/` | harbor's installed agents replace |
| 2 | `src/razorback/benchmarks/dab/` → `_legacy/benchmarks/dab/` | harbor-DAB adapter replaces |
| 3 | `src/razorback/benchmarks/ade_bench/` → `_legacy/benchmarks/ade_bench/` | future harbor-ade-bench adapter replaces |
| 4 | `src/razorback/compat/` → `_legacy/compat/` | per-runtime adapter sub-modules replace |
| 5 | `src/razorback/observers/` → `_legacy/observers/` | harbor's hook system replaces |
| 6 | Remaining DROP/PORT-OUT modules from Phase 0 inventory not already sidelined → `_legacy/` | sweep |

Each commit is bisect-clean: tests pass between commits (the
sidelined modules remain importable from `_legacy/`); the canonical
surface progressively shrinks. **No commit combines a sideline with
an unrelated edit; no commit combines two unrelated sidelines.**

**AC-6.5 — trimmed canonical surface.**
`src/razorback/{spec,agents,cli}` contain only v2-spec-named
artifacts. Removed pieces are in `_legacy/`. `agents/registry.py`
holds the spacedock_solver pydantic schema only.

**AC-6.6 — examples reflect v2.** `examples/specs/` flips to
v2-canonical agent kinds and the harbor-DAB adapter reference.

**AC-6.7 — same-canonical cross-history diff is statistically null.**
A full DAB benchmark via the post-Phase-6 canonical path produces a
`rk diff` against a pre-Phase-6 v2-class-on-harbor-adapter run (Phase
3's smoke result) whose stratified-delta paired bootstrap CI includes
zero. This confirms that the rename + sideline did not change v2
behavior.

**AC-6.8 — razorback-implementation workflow dispatch can resume.**
The Phase 0 pause is lifted; new v2-shaped backlog entities can flow
through the dispatch path.

**AC-6.9 — `uv run pytest` exits 0.**

**Walking-skeleton check.** AC-6.7 — full DAB benchmark via canonical
v2 path produces a statistically-null diff against the pre-promotion
v2-path run.

**Uncertainty surfaced.**
- Whether any tests import v1-class paths in ways that don't gracefully
  redirect via the `_legacy/` move. Mitigation: `grep -r 'from
  razorback._legacy'` and `grep -r 'spacedock_solver'` before each
  rename commit; resolve call sites.
- Whether the `_legacy/` namespace introduces import path conflicts
  with v2 modules of the same name (a v2 `agents/spacedock_solver.py`
  + a `_legacy/agents/spacedock_solver_legacy.py` is fine; care
  required if two modules share the same name in different
  namespaces).

**Sideline at phase end.** Explicitly listed in AC-6.3 + AC-6.4.

---

## Phase 7: Delete `_legacy/` (optional)

**Acceptance criteria.**

**AC-7.1 — walking skeleton holds.** A DAB benchmark runs end-to-end
via the canonical v2 path after the deletion.

**AC-7.2 — `_legacy/` audited.** Every module under
`src/razorback/_legacy/` has a status: imported-by-parity-test (keep
or retire test); imported-by-deprecation-alias (decide whether the
deprecation alias is still needed); unreferenced (delete).

**AC-7.3 — `_legacy/` removed or trimmed.** Per the audit decisions.
One commit per logical deletion group for bisect-friendliness.

**AC-7.4 — `grep -r 'from razorback._legacy'` returns no hits**
(or only hits the captain explicitly chose to retain).

**AC-7.5 — `uv run pytest` exits 0** after the deletion.

**Walking-skeleton check.** Post-deletion DAB smoke runs and produces
the same headline score as Phase 6's smoke.

**Uncertainty surfaced.**
- Whether external consumers of razorback have been written that
  import from `_legacy/`. Mitigation: razorback has no external
  consumers yet, so this is local-only at the time of this plan.

**Sideline at phase end.** N/A — this phase performs the deletion.

**Phase status.** Optional. The plan does not gate later work on this
phase. `_legacy/` is harmless — it doesn't pollute the canonical
surface, doesn't get imported in normal use. The captain decides
whether to execute Phase 7 at all.

---

## Phase 8: Validate end-to-end + release

**Acceptance criteria.**

**AC-8.1 — `nop`-agent smoke succeeds.** A spec with the simplest
possible agent (`agent.kind: claude_code` or harbor's `nop` if
available) freezes, runs, and produces a run-dir with
`provenance.yaml`.

**AC-8.2 — `spacedock_solver` smoke succeeds.** A spec with
`agent.kind: spacedock_solver` + a minimal solver_workflow freezes,
runs, produces `agent_freeze/sealed_hash.txt`, and the
`phase_stats.json` written by the mods is schema-valid.

**AC-8.3 — `rk diff` smoke succeeds.** Same frozen spec run twice
with `trials: 5`; `rk diff` produces the full JSON output (Wilson
CIs, McNemar p, paired bootstrap CI, MDE).

**AC-8.4 — resume smoke succeeds.** Halt-resume cycle on the
canonical v2 path; sealed-hash check passes; resume proceeds.

**AC-8.5 — experiment-workflow smoke succeeds.** Phase 5's AC-5.7
hypothesis smoke, re-run post-Phase-6/7, still works end-to-end.

**AC-8.6 — `uv run pytest` exits 0** from a clean checkout.

**AC-8.7 — README at repo root reflects v2.**

**AC-8.8 — CHANGELOG lists every sideline + every new addition,**
citing v2 spec sections.

**AC-8.9 — version tag exists.** Major version bump.

**Walking-skeleton check.** AC-8.1 through AC-8.5 collectively
exercise every public surface of v2 razorback.

**Uncertainty surfaced.** Integration bugs surface only at end-to-end
smoke. AC-8.5 (full experiment workflow) is the most comprehensive
and the most likely to surface late issues.

**Sideline at phase end.** None.

---

## Phase summary

| Phase | Walking-skeleton state | Code change shape |
|---|---|---|
| 0 — Probe, decide, baseline | unchanged | +docs |
| 1 — `rk run` v2 wrapper | runs via in-tree adapter | new code from spec + extractions; sideline old `run.py` |
| 2 — DAB harbor adapter (sibling) | runs via in-tree adapter AND harbor adapter | sibling +1500; razorback unchanged |
| 3 — SpacedockSolverAgent v2 (alongside) | runs via both agent classes | new `_v2` module from spec + extractions; v1 stays canonical |
| 4 — `rk diff` + extended `rk freeze` | freeze → run × 2 → diff works | new code from spec + provenance extractions; same-adapter cross-class null required |
| 5 — Templates + mods | end-to-end hypothesis smoke runs | new markdown |
| 6 — Promote v2, sideline v1 | canonical = v2; same-canonical cross-history null required | rename + `git mv` to `_legacy/` |
| 7 — Delete `_legacy/` (optional) | v2-only canonical surface; same headline score | -delete |
| 8 — Validate + release | tagged release | docs + verification |

**Walking-skeleton invariant.** Per AC-0.9: the invariant is
*runnability* (DAB runs end-to-end, produces non-degraded
summary.json). Score-parity is a Phase 4+ test using `rk diff` on
same-adapter, same-agent pairs, not against the v1 dump-file
baseline.

---

## Decision points

These need a captain decision; the plan does not pre-decide them.

**D1 — Harbor plugin contract** (probed in AC-0.2; locked in AC-3.7).
Entry-point registration or fallback CLI spec-translation.

**D2 — Codex / pi support timing** (AC-0.7). Claude-only at v2.0 with
stubs, or all three runtimes implemented up-front.

**D3 — Optional CLI commands** (Phase 4 / future). Whether
`rk constraints check`, `rk baseline promote/verify`, `rk registry`
ship in v2.0 or defer until a consumer surfaces.

**D4 — `rk init` subcommand** (Phase 5). Whether to ship a scaffolding
command or document the copy-and-modify procedure only.

**D5 — DAB harbor adapter packaging** (AC-0.8). Sibling package
(`packages/razorback-plugin-dab/`) or new repo.

**D6 — `_legacy/` retention** (Phase 7). Whether to execute Phase 7
at all, or keep `_legacy/` indefinitely.

**D7 — Cross-dataset stratified aggregator architecture** (AC-2.8).
Plan recommends: razorback's `rk diff` owns the stratified math; the
benchmark adapter owns stratum *tagging* (each trial emits stratum
metadata). This split keeps `rk diff` benchmark-agnostic and the
adapter benchmark-specific. Captain confirms the split or picks the
all-in-adapter alternative.

---

## Deferred review findings (Packages G, H, I, J from 2026-05-19 staff reviews)

The following findings are captured but deferred — their impact is
scoped, and the named deliverables (paper reproduction + ade-bench
Haiku baseline) work without them.

**Package G — halt-resume infra-change correctness.** The sealed-input
hash inputs (spec §4.4 + §8.4) cover model, sampling, solver_workflow
content hash, prompt content hashes, spacedock skill version, harbor
agent kwargs. Missing: docker image digest + harbor version. A
halt-resume across an image rebuild or harbor minor bump silently
mixes conditions. **Lands when:** the autoresearch loop's first
halt-resume hypothesis run is planned. Not on the path for
deliverables 1+2 (both run full trials, no halt-resume).

**Package H — multi-benchmark stratified aggregator (full architecture).**
AC-2.8 commits to the split (math in `rk diff`, strata in adapter)
but doesn't ship the full abstraction. Cross-benchmark reuse of
`rk diff` against τ-bench, HAL, etc. may surface stratification
shapes DAB doesn't cover. **Lands when:** the second benchmark's
`rk diff` consumer surfaces a stratification difference.

**Package I — paper-writing caveats.** Three items defer to paper
draft phase:
- `provider_determinism_class: seed_honored | seed_ignored | unknown`
  in provenance.yaml; `rk diff` warns when both runs are
  `seed_ignored` at low N.
- Between-run variance accounting: run the headline reproduction
  twice and report between-run variance once.
- Power analysis at observed effect — already partly addressed by
  AC-4.2's achieved-power line; richer interpretation aids defer.

**Package J — future trajectory auditing.** A `rk audit <run-dir>`
subcommand that post-hoc greps trial transcripts for benchmark-name
strings, dataset-name strings, and known answer-key fragments.
Defense-in-depth on top of the Package A + B combo. **Lands when:**
a suspected leak surfaces that runtime hooks did not catch.

---

## Out-of-band cleanup

- **Archive the 2026-05-18 design doc** in dataagentbench. Defer
  until DAB harbor adapter (Phase 2) is proven against multiple
  benchmarks.
- **Archive `dataagentbench/benchmark/`.** Once the DAB harbor
  adapter is published and the autoresearch loop runs against it.
- **Retire `~/.claude/teams/razorback-razorback-implementation-*`
  team directories.** Periodic cleanup.

---

## Whole-plan acceptance

- All Phase 0-6 ACs satisfied. (Phase 7 optional; Phase 8 required.)
- v2 razorback is the codebase on `main`.
- The 2026-05-19 v2 spec is the source of truth.
- The razorback-implementation workflow's backlog reflects v2 scope
  and is resumable.
- The five primary commands (`rk run`, `rk freeze`, `rk diff`,
  `rk runs list/show`) work against real harbor invocations.
- `SpacedockSolverAgent` is the v2 runtime-adapter class at the
  canonical name.
- Workflow templates + mods exist as package data.
- A captain can copy the experiment-workflow template, instantiate
  it, and run a hypothesis end-to-end against DAB via the new harbor
  adapter (AC-5.7 + AC-8.5).
- Walking-skeleton invariant held at every phase boundary
  (runnability never broke).
- All tests pass; `uv run pytest` exits 0 from a clean checkout.
- A version tag marks the release.
