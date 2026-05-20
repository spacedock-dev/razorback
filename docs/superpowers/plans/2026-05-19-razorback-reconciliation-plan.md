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
- Sidelining is `git mv` only, code moves, but is preserved.
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

**AC-0.1** v1 reconciliation baseline + deterministic micro-spec
captured. Two artifacts:

(a) A full DAB-claude experiment ran against current razorback in its
current shape (in-tree adapter, dump-file mode); the run-dir headline
score and per-dataset breakdown are committed to
`docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`. This
is the **pre-correction reference**, it captures behavior on the
degraded access path and is used for Phase 2's expected-shift-band
documentation, not as the structural walking-skeleton anchor.

(b) A **deterministic smoke micro-spec** is committed at
`examples/specs/_deterministic-smoke.yaml`: one task (bookreview's
simplest query), one trial, `temperature: 0.0`, fixed seed where the
runtime honors it, content-hashed prompt content. Its expected
pass/fail outcome is recorded. **This micro-spec is the
walking-skeleton anchor for Phases 1-3**, eyeball comparison of
full-DAB headlines at N=5 is too noisy to catch a 5-10pp regression;
the deterministic smoke is.

**AC-0.2** harbor plugin contract validated by execution (resolves
D1). The entry-point group name + registration shape for external
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

**AC-0.3** harbor's spec format compatibility probed. Razorback's
current spec format is compared field-by-field against the JobConfig
harbor's `harbor run` accepts. Any razorback fields harbor does not
accept (e.g., razorback's `spacedock_solver` agent block kwargs
specifically) are documented with a translation strategy (entry-point
direct or `rk run` rewrite, decided by AC-0.2).

**AC-0.4** harbor installed-agent constructor probed.
`harbor.agents.installed.claude_code.ClaudeCode.__init__` signature is
documented. Razorback's runtime-adapter `SpacedockSolverAgent` MUST be
able to construct an instance via the kwargs path; if there's a
hidden coupling (mandatory kwarg razorback can't supply), it is named
and a mitigation is documented.

**AC-0.5** harbor's job-resume mechanism probed.
`harbor jobs resume` is invoked against a known-incomplete fixture
run-dir; the resume semantics are documented. Razorback's halt-resume
contract (spec §4.4) is checked against what harbor actually does on
resume. Conflicts named explicitly.

**AC-0.6** harbor's run-dir layout probed. The actual files harbor
writes per trial under `logs_dir/` are listed. Razorback's
`agent_freeze/` subtree assumption (writable under `logs_dir/`,
non-colliding) is confirmed.

**AC-0.7** D2 decided. Captain has picked: claude-only at
first-ship (codex/pi NotImplemented stubs), or all three runtimes
implemented up-front.

**AC-0.8** D5 decided. Captain has picked: sibling-package
(`packages/razorback-plugin-dab/`) or new repo for the DAB harbor
adapter.

**AC-0.9** baseline-comparator policy locked.

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

**AC-0.10** module inventory committed with file:line citations.
`src/razorback/` modules are classified KEEP-EXTRACT, ADAPT-EXTRACT,
DROP, or PORT-OUT against the v2 spec at
`docs/superpowers/plans/2026-05-19-razorback-inventory.md`. Every src
module classified; every v2-spec-named artifact accounted for. **For
each KEEP-EXTRACT and ADAPT-EXTRACT module, the inventory cites
specific file:line ranges of the proven behavior to preserve**,
especially for freeze-resolver internals (retry/backoff against
provider 503s, provider-specific error-class taxonomy, Anthropic 503
patterns vs OpenAI auth-vs-org-quota distinctions), auth handling
(the `.env`-via-`dotenv_values` discipline per FU-1 M3 AC-3), and
the FU-1/FU-2 acceptance-test contracts (image-override semantics,
`extra_env` mechanism). Phase 4 + Phase 1 extractions reference these
citations.

**AC-0.14** test classification committed. Symmetric to AC-0.10:
every test file under `tests/` is classified KEEP-VERBATIM (lift into
v2's test tree as-is, just re-pointed at v2 paths), RE-AUTHOR
(behavior survives in v2 but the test needs new framing), or DROP
(tests behavior of a module marked DROP/PORT-OUT). Committed to
`docs/superpowers/plans/2026-05-19-razorback-test-inventory.md`.
Specifically: every FU-1 / FU-2 acceptance test is KEEP-VERBATIM
unless its target behavior moves to the DAB harbor adapter (then
PORT-OUT to the adapter's test suite).

**AC-0.11** `src/razorback/_legacy/` exists. Empty (with
`__init__.py` carrying the holding-tank convention docstring).

**AC-0.12** in-flight backlog re-filed under v2 shape.
PKG-3/4/5/6/7/10 archived; PKG-1, PKG-2, PKG-8, PKG-9 re-scoped to
their v2-surviving content; razorback-implementation workflow
dispatch paused.

**AC-0.13, 2026-05-18 design doc marked SUPERSEDED** with a pointer
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

**AC-1.1** walking skeleton holds. `rk run
examples/specs/<benchmark>-claude.frozen.yaml` produces a run-dir
with `summary.json` against the in-tree DAB adapter (unchanged from
Phase 0).

**AC-1.2** `rk run` is the v2 wrapper per spec §3.2 + §8.1. Reads
frozen spec; runs alias-drift pre-check (re-resolves model alias,
refuses with `AliasDriftError` on drift unless `--allow-alias-drift`);
delegates execution to `harbor run`; passes exit code through (exit
30 reserved for harbor runtime failure); writes
`spec.frozen.yaml` + `provenance.yaml` into the harbor-produced
run-dir.

**AC-1.3** extractions preserved. Proven behavior from the current
codebase has been extracted with attribution into the v2 implementation:
- alias-drift detection (resolved-version comparison against
  `provenance.yaml.model_resolved_version`)
- auth handling (`.env` via `dotenv_values`, NEVER `os.environ`, per
  the FU-1 M3 AC-3 contract)
- run-dir creation helpers (path conventions, manifest write)

**AC-1.4** superseded `run.py` and helpers sidelined. The previous
`src/razorback/run.py` and any orchestration helpers replaced by the
new `rk run` live under `src/razorback/_legacy/` via `git mv`.

**AC-1.5, unit tests cover the alias-drift pre-check** (mocked
provider API) and the harbor-passthrough behavior. Extracted
behaviors (auth, alias-drift logic) keep their existing tests,
re-pointed at v2 paths.

**AC-1.6** `uv run pytest` exits 0.

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

## Phase 2: DAB harbor adapter, parallel sibling project

**Acceptance criteria.**

**AC-2.1** walking skeleton holds (both paths). Razorback can still
run DAB via the in-tree adapter (Phase 1 path); razorback can also run
DAB via the new harbor-DAB adapter via `rk run`. Both produce
runnable run-dirs.

**AC-2.2** DAB harbor adapter exists and publishes. The new package
(at the location D5 decided) builds; `harbor adapter list` (or
local-discovery equivalent) shows the new DAB adapter.

**AC-2.3** per-task content ported. All 12 DAB datasets are
represented as harbor task definitions in the new package; prepare,
verify, per-task environment (including the live-DB compose stack
that was PKG-3's surviving content), and per-task hook config
(DISALLOWED_TOOLS + workspace-README variants from PKG-9's surviving
content) are present.

**AC-2.4** live-DB mode confirmed. A bookreview run via the new
harbor-DAB adapter shows postgres-protocol evidence in the agent's
trajectory (a `psql --host dab-postgres` invocation or
`dab-postgres:5432` connection string in `events.jsonl`), confirming
live-DB access rather than dump-file grepping.

**AC-2.5** live-DB baseline established and promoted to canonical
anchor. The headline score and per-dataset breakdown of a full
DAB-claude run via the new harbor-DAB adapter are committed to
`docs/superpowers/plans/2026-05-19-reconciliation-baseline.md` as the
**canonical baseline from Phase 3 onward**. The v1 dump-file baseline
(AC-0.1(a)) is explicitly retired to "pre-correction reference"
status in the same file with a note explaining why
(dump-file-leakage means the v1 score is methodologically tainted
relative to the live-DB protocol).

**AC-2.6** per-dataset expected-shift bands pre-registered before
the v1-vs-v2 comparison. Before running the comparison that
produces AC-2.5's baseline, a per-dataset prediction is committed to
the baseline doc: for each of the 12 DAB datasets, the expected
direction + rough magnitude of the live-DB-vs-dump-file score shift
(e.g., bookreview: live DB **drops** score significantly because the
in-tree-adapter agent grepped `books_info.sql`; agnews: roughly
unchanged because it doesn't have a dump-file leak vector). The
comparison's acceptance criterion is "observed shifts fall within
the pre-registered direction; magnitudes within 2x of prediction",
not "scores match". A surprise reversal flags a real bug.

**AC-2.7** in-tree adapter still functional.
`src/razorback/benchmarks/dab/` is unchanged from Phase 1; an
in-tree-adapter smoke run still produces the v1-baseline-comparable
result.

**AC-2.8** cross-dataset aggregation architecture decided
(resolves D7). The DAB paper's stratified pass@1 across 12
datasets is computed by razorback's `rk diff` operating on a
**stratum-tagged trial table** the adapter emits. The adapter is
responsible for tagging each trial with its stratum metadata
(dataset name, query difficulty bucket, etc.); razorback's `rk diff`
is responsible for the stratified aggregation math. This split
keeps `rk diff` benchmark-agnostic and the adapter
benchmark-specific. Phase 2's smoke run validates the contract.

**Walking-skeleton check.** TWO smokes at Phase 2's end, in-tree
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

## Phase 3: SpacedockSolverAgent v2, runtime adapter alongside

**Acceptance criteria.**

**AC-3.1** walking skeleton holds; Phase 3 does NOT depend on Phase 2.
The v2 SpacedockSolverAgent class is exercised against the **in-tree
DAB adapter** (which is still functional per AC-2.7), Phase 3 ships
without requiring Phase 2's harbor-DAB adapter to be complete. The
deterministic micro-spec (AC-0.1(b)) passes against both
(v1-agent × in-tree adapter) and (v2-agent × in-tree adapter). When
Phase 2's harbor-DAB adapter does become available, the same v2 agent
class runs against it too (validated by Phase 6's promotion smoke);
Phase 3 itself does not block on it. This decouples the critical
path.

**AC-3.2** new `SpacedockSolverAgent` class exists and works. At
`src/razorback/agents/spacedock_solver_v2.py`, written from spec §4 +
§8.4. Routes via `agent.kind: spacedock_solver_v2` (the canonical
name `spacedock_solver` still routes to the v1 class). Constructor
validates kwargs against the pydantic schema; computes sealed_hash
from `(model, sampling, solver_workflow content hash, prompt content
hashes, spacedock skill version, harbor agent kwargs)`; refuses on
resume mismatch; constructs the inner harbor installed-agent via the
per-runtime adapter sub-module.

**AC-3.3** per-runtime adapter sub-modules exist.
`src/razorback/agents/_runtime/claude.py` is implemented (functional
per AC-3.5). `_runtime/codex.py` and `_runtime/pi.py` exist as
NotImplemented stubs per D2 if claude-only was chosen, or as
functional implementations if all-three was chosen.

**AC-3.4** extractions preserved. Proven behavior extracted from
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

**AC-3.5** claude runtime smoke succeeds against in-tree adapter.
A spec with `agent.kind: spacedock_solver_v2` + `runtime: claude` +
the **in-tree DAB adapter** + a minimal solver_workflow dir (one
stage, one mod) runs bookreview end-to-end. The inner `claude_code`
agent receives the expected kwargs (verified by instrumentation or
integration test); `sealed_hash.txt` lands in `agent_freeze/`. (When
the harbor-DAB adapter is ready, Phase 6's promotion smoke validates
the v2 class against it; Phase 3 does not block on that adapter.)

**AC-3.6** halt-resume smoke succeeds (hand-faked freeze writes).
A bookreview trial is halted at turn cap; the test harness writes
the `agent_freeze/.git` workspace snapshots and `sealed_hash.txt`
that the freeze-mod would otherwise produce; a resume spec pointing
at that freeze proceeds without `SeedMismatchError` when sealed
inputs match, and refuses with `SeedMismatchError` (exit 20) when a
sealed input is perturbed. **Halt-resume's real-mod validation
(workflow mods firing on stage-completion signals) defers with the
mod machinery to whenever the autoresearch loop's first halt-resume
hypothesis run is planned, see spec §5.2's deferral note.** Goals
1+2 run single straight-through solves and never exercise the real
freeze path; the hand-faked smoke here proves the resume mechanic
in isolation.

**AC-3.7** entry-point registration verified. Per D1's outcome
(AC-0.2): either `pyproject.toml`'s
`[project.entry-points."harbor.agents.installed"]` is set and harbor
routes `agent.kind: spacedock_solver_v2` to razorback's class; or
the fallback spec-translation pre-pass in `rk run` rewrites the
agent block before invoking `harbor run`. The chosen path works on
the smoke.

**AC-3.8** v1 SpacedockSolverAgent still functional. A spec with
`agent.kind: spacedock_solver` (v1 routing) against either adapter
still runs end-to-end. The v1 class is not edited in this phase.

**AC-3.9** `uv run pytest` exits 0.

**Walking-skeleton check.** At least two smokes, v1-class on
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
- Whether the real freeze path (workflow writing
  `agent_freeze/.git` and `phase_stats.json` at stage boundaries)
  works end-to-end. AC-3.6's halt-resume smoke uses hand-faked
  writes; the real-path validation defers with halt-resume itself
  per the spec §5.2 deferral. Not a goal-1/2 dependency.

**Sideline at phase end.** None. v1 class stays canonical until
Phase 6.

---

## Phase 4a: First-cut CLI completion (`rk score`, `rk audit`, `rk runs cost`, `rk run` budget gate, extended `rk freeze`)

**Acceptance criteria.**

**AC-4a.1, walking skeleton holds.** All cells from Phase 3 still
produce summary.json; Phase 4a adds the remaining initial CLI
surfaces: scored readout, post-hoc trajectory audit, cumulative
cost tracking, and the per-experiment budget gate on `rk run`.

**AC-4a.2, `rk score` produces spec §8.3a statistics.** Given one
harbor run-dir, output JSON carries: per-stratum (typically per-dataset)
pass@1 with Wilson 95% CI (level via `--alpha`); overall stratified
pass@1 per the adapter's stratum tagging; per-stratum trial counts
with errored-vs-completed distinction; when invoked with
`--against-constant <name=value>`, a "matches" / "outside-CI" line
per stratum. `--format markdown` produces a human-readable
equivalent. **Folds PKG-2 surviving content for counting honesty**
(errored trials not counted as fails; silent-drop guard flags missing
trials).

**AC-4a.3, fixture-driven correctness.** Hand-computed Wilson CI
values for synthetic single-run pass@1 data match `rk score`'s
output within tolerance. The `--against-constant` flag's
"inside-CI" / "outside-CI" decision matches a hand-computed
membership test.

**AC-4a.4, `rk freeze` extended with v2 sealed inputs.**
`provenance.yaml` now includes `solver_workflow_hash` (recursive
content hash of the solver_workflow dir), `spacedock_skill_version`
(from `importlib.metadata.version` with per-install-shape fallback),
and `harbor_agent_kwargs_hash` (hash of post-runtime-adapter agent
kwargs). The existing pinning (model alias resolved, image digest,
agent CLI binary hash, prompt content hashes, harbor version) is
preserved.

**AC-4a.5, extractions preserved.** Provider model-version resolution
(Anthropic + OpenAI API calls with retry), Docker image digest pinning
(`docker image inspect` wrapper), agent CLI binary hashing, prompt
content hashing, all extracted from current `provenance/` with
attribution.

**AC-4a.6, paper-reproduction readout shape works.**
`rk score <run-dir> --against-constant stratified_pass_at_1=0.577`
returns "inside-CI" or "outside-CI" with the Wilson CI bounds on the
run's stratified pass@1. This is the operational shape goal 1's
analyze step uses to answer "did we reproduce".

**AC-4a.7, `rk audit` works.** Port of dataagentbench's
`benchmark/lib/taint.py` mechanism with attribution (spec §3.2 +
§9.4). Walks a run-dir's trial traces (parent agent logs, subagent
trace manifests, recursive subagent traces); pattern-matches against
forbidden shell commands, web-search tool calls, and the same
patterns hidden inside heredocs / `python -c` strings; emits per-trial
taint status (`clean` / `suspect` / `tainted` / `coverage_missing`)
with findings. `--policy strict` exits with `TaintFindingsError`
(exit 23) on any non-`clean` trial; `--policy audit` (default)
reports without failing.

**AC-4a.8, `rk audit` fixture-driven correctness.** Hand-crafted
trial-trace fixtures exercise each pattern category: a clean
trajectory passes; a `pip install datasets` Bash command flags
tainted; the same hidden in a `python -c "subprocess.run(['pip',
'install', 'datasets'])"` flags tainted (heredoc / python-c decoder
working); a subagent trace with a forbidden invocation flags tainted
(recursive scan working); a trace with a missing manifest flags
`coverage_missing` not `clean`.

**AC-4a.9, `rk runs cost` works.** Given a directory of run-dirs,
reads each run's cost from `summary.json` (or the harbor-emitted
cost field) and emits the cumulative sum. Pairs with AC-4a.10's
budget gate.

**AC-4a.10, `rk run --max-budget-usd-running <file>` enforces
running budget.** Reads `<file>` (a running-total JSON the
matrix dispatcher passes across invocations); adds this invocation's
estimated cost; refuses with `BudgetExceededError` (exit 22) when
the total would exceed the frozen spec's `experiment.max_budget_usd`;
on completion appends the actual cost to `<file>`. Fixture test:
two sequential `rk run` invocations against a budget that allows
one but not both, the second refuses.

**AC-4a.11, agent block `tools_denied` field validated and
plumbed.** Razorback's pydantic schema for `agent.kind:
spacedock_solver` accepts `tools_denied: list[string]` (spec §6.2);
the per-runtime adapter sub-modules (Phase 3) install the list as
PreToolUse hooks in the inner harbor installed-agent. Fixture test:
a spec with `tools_denied: ["Bash(pip install datasets*)"]` produces
an inner `claude_code` agent whose configured PreToolUse hooks
include the deny pattern. Goal-1 specs hard-code DAB's full
DISALLOWED_TOOLS list in this field; this is the Layer 2 leak
guard the spec §9.4 calls out as required for goal-1 defensibility.

**AC-4a.12, matrix dispatcher script exists.**
`examples/drivers/dab-paper-matrix.sh` (or equivalent Python driver)
dispatches the 180-cell goal-1 matrix as `for spec in matrix: rk
freeze; rk run --max-budget-usd-running budget.json; rk score
--against-constant ...; rk audit --policy strict`. Failure-recovery
and partial-resume semantics are scripted, not interactive: a failed
cell logs its identity; the driver continues with the next cell;
re-running the driver skips already-completed cells (idempotent
on `rk run`'s `(jobs_dir, job_name)` content-hash determinism).

**AC-4a.13, v2-class × harbor-DAB end-to-end smoke succeeds.** A
spec with `agent.kind: spacedock_solver_v2` + `runtime: claude` +
the new harbor-DAB adapter (Phase 2) + a minimal solver_workflow
+ DAB's full `tools_denied` list runs bookreview at N=3
end-to-end. `rk freeze` produces provenance.yaml; `rk run` enforces
budget; the inner claude_code agent receives the PreToolUse hooks;
`rk score` emits per-stratum Wilson CIs; `rk audit --policy audit`
runs over the trial traces and produces `clean` (or names any
tainted trial for inspection). This is the mechanism-validation
smoke before goal-1's $300-500 burn, every initial surface
exercised against a real harbor-DAB run.

**AC-4a.14, goal-2 readout shape decided.** Captain picks: goal-2
runs at N≥3 (paying ~$60-120 more for usable per-task Wilson CIs),
or `rk score` documents a "single-trial regime" output mode for N=1
that emits only the 48-task aggregate proportion CI and suppresses
per-task CIs (per ML round-2 review M2). Decision recorded in this
plan or as a referenced amendment; goal-2's spec matrix reflects
the decision before goal-2 dispatch.

**AC-4a.15, `uv run pytest` exits 0.**

**Walking-skeleton check.** AC-4a.13 (v2-class × harbor-DAB
end-to-end smoke) is the critical integration test for goals
1+2: every initial surface (rk freeze, rk run with budget gate,
rk score with constant check, rk audit, tools_denied PreToolUse
hooks, v2 SpacedockSolverAgent + harbor-DAB adapter) ran against a
real harbor trial and produced expected outputs. The deterministic
micro-spec from AC-0.1(b) continues to pass at this phase's end
as the structural regression catcher.

**Uncertainty surfaced.**
- Whether `spacedock_skill_version` is reliably detectable across the
  plugin-vs-package install shapes spacedock uses. Fallback semantics
  documented in the implementation.
- Whether the adapter's stratum tagging (AC-2.8 contract) is rich
  enough to drive `rk score`'s stratified mean. Surfaced if `rk
  score` returns a strange value on a known DAB run; resolved by
  inspecting the stratum tags the adapter emits.

**Sideline at phase end.** Old `rk freeze` implementation files
replaced or substantially edited move to `src/razorback/_legacy/` if
there's a non-trivial divergence; otherwise extension-in-place is
fine.

---

## Phase 4b: `rk diff` paired statistics (ships when autoresearch loop needs it)

**Phase status.** Sequenced after Phases 4a/5/6/7/8. The first-ship
deliverables (paper reproduction, ade-bench Haiku baseline) do not
require paired comparison, paper reproduction is a one-sided test
against published constants (handled by `rk score
--against-constant`); ade-bench Haiku is an establishing
measurement. Paired comparison machinery lands when the
autoresearch loop's analyze stage needs it.

**Acceptance criteria (when this phase activates).**

**AC-4b.1, walking skeleton holds.** All first-ship surfaces still
work; `rk diff` ships additively without changing them.

**AC-4b.2, `rk diff` produces spec §8.3 statistics.** Given two
harbor run-dirs paired by `(task, query, trial_index)`, the output
JSON carries: per-arm per-query Wilson 95% CI on pass@1; per-query
exact-McNemar p with exact-binomial fallback for small discordant
counts AND family-wise-adjusted p-values via Holm-Bonferroni; paired
bootstrap CI on the stratified delta resampling at the cluster level
(default `query`); MDE at fixed N; achieved-power-at-observed-effect.
Refuses on seed-asymmetry.

**AC-4b.3, fixture-driven correctness, including cluster +
family-wise.** Hand-computed expected values match within tolerance.
**Cluster-bootstrap fixture is critical**: synthetic dataset
where intra-query trials are perfectly correlated shows the
trial-level bootstrap CI as anti-conservatively narrow vs. the
query-cluster bootstrap CI; test asserts the latter is wider.
**Family-wise fixture is critical**: 12-dataset synthetic with no
real effect produces ~46% uncorrected family-wise error;
Holm-Bonferroni brings it to nominal α.

**AC-4b.4, same-spec self-diff is statistically null.** Two
back-to-back runs of the same frozen spec produce paired bootstrap CI
including zero at N=5.

**AC-4b.5, same-adapter cross-class diff is statistically null** (if
v1 class still exists at this phase's ship time). Confirms v2 agent
class does not change benchmark semantics vs v1. Lands as a
regression gate, not as a feature.

**AC-4b.6, `uv run pytest` exits 0.**

**Trigger for activation.** When the autoresearch experiment workflow's
analyze stage needs to make a "hypothesis X beats baseline" claim with
paired-statistics defensibility. Until then, `rk score` against the
registered baseline run-dir (treating the baseline's headline as the
constant) is the operational shape.

---

## Phase 5: Workflow templates (no mods initial)

**Phase sequencing note.** Phase 5 lands AFTER goal-1 (paper
reproduction) and goal-2 (ade-bench Haiku baseline) ship via
captain-driven dispatch using the deterministic CLI (the
`examples/drivers/dab-paper-matrix.sh` from AC-4a.12). Goals 1+2
do not require workflow templates. Phase 5 ships the
spacedock-workflow scaffolding for the autoresearch loop's first
hypothesis runs.

**Sequencing dependency on Phase 6.** Phase 5's templates reference
`agent.kind: spacedock_solver` (the canonical name post-Phase-6).
Phase 6 (which promotes v2 to canonical and sidelines v1) must
land before Phase 5 ships, or the templates dangle pointing at the
intermediate `spacedock_solver_v2` discriminator. Plan order is
therefore Phase 6 → Phase 5, even though Phase 5's section appears
before Phase 6 in this document. The numbering reflects logical
grouping (Phase 5 = workflow templates; Phase 6 = sideline cleanup);
the dispatch order is reversed.

**Acceptance criteria.**

**AC-5.1** walking skeleton holds. Razorback continues to run DAB
end-to-end via the direct CLI; Phase 5 adds the workflow templates
without breaking direct CLI use.

**AC-5.2** workflow README templates exist.
- `docs/templates/experiment-workflow/README.md` per spec §5.1:
  six stages (pending, propose, smoke, full, analyze, conclude);
  sd-b32 ID style; `experiment.max_budget_usd` declared in the
  template spec. Per-stage prompt content carries the stage-level
  behavior the prior mod design enumerated:
  - **propose** prompt: instructs the operator-ensign on what the
    solver-workflow README must not reference (answer keys,
    ground-truth columns, per-task hints); captain reviews at the
    gate.
  - **smoke** / **full** prompts: instruct the operator to run
    `rk runs cost <root>` before dispatch and refuse if running
    total + estimate exceeds `experiment.max_budget_usd`; the
    `rk run --max-budget-usd-running <file>` flag is the
    invocation-time backstop.
  - **analyze** prompt: instructs the operator to run `rk score
    --against-constant <baseline-headline>` (initial) or
    `rk diff` (when shipped), paste the JSON output into the entity
    body, write a verdict.
- `docs/templates/run-workflow/README.md` per spec §5.2: four
  stages (pending, reconciling, completed, failed). No
  stage-completion-signal mods required because halt-resume's
  real-mod machinery defers (per AC-3.6 hand-fake note).
- Both parse against spacedock's workflow-README schema.

**AC-5.3** package data shipping. `pyproject.toml` ships
`docs/templates/` so a captain can copy templates into a new
project.

**AC-5.4** end-to-end hypothesis smoke. A captain copies the
experiment-workflow template into a fresh dir, instantiates it
against DAB via the new harbor adapter, runs ONE hypothesis
end-to-end (propose → freeze → smoke → analyze → conclude). The
full path works; propose-stage prompt + captain gate catch a
deliberate leak-guard violation; smoke-stage prompt enforces budget
via `rk runs cost`; analyze stage produces `rk score
--against-constant` output in the entity body; conclude stage is
reachable.

**AC-5.5** `uv run pytest` exits 0.

**Walking-skeleton check.** AC-5.4 (end-to-end hypothesis smoke) is
the strongest single demonstration of v2 razorback's integration
shape working as a unit.

**Uncertainty surfaced.**
- Whether per-stage prompt content alone (without razorback-shipped
  mods) is sufficient leak-guard / cost-gate discipline for
  hypothesis runs at scale. Mitigation: real consumer (the first
  autoresearch hypothesis run) surfaces gaps; missing enforcement
  can become a mod later if the prompt-driven discipline fails.
- Whether spacedock's workflow-README schema accepts razorback's
  template shape without local extensions (AC-5.2). Reference
  shape: `docs/razorback-implementation/README.md` is the working
  example.

**Sideline at phase end.** None, no legacy templates to displace.

---

## Phase 6: Promote v2 to canonical, sideline superseded v1

**Phase sequencing note.** Phase 6 dispatches *before* Phase 5 even
though Phase 5 is numbered earlier in this document, Phase 5's
workflow templates reference the canonical `agent.kind:
spacedock_solver` name, which Phase 6 produces by renaming v2.
Goals 1+2 ship from Phase 4a's end (using the intermediate
`spacedock_solver_v2` discriminator); Phase 6 lands shortly after
to clean the canonical surface; Phase 5 ships templates against
that clean surface.

**Acceptance criteria.**

**AC-6.1** walking skeleton holds. A DAB benchmark runs end-to-end
via the canonical v2 path (`agent.kind: spacedock_solver` routing to
the v2 class) after the rename + sideline.

**AC-6.2** `spacedock_solver` routes to v2.
`agent.kind: spacedock_solver` invokes the v2 runtime-adapter class.
`pyproject.toml`'s entry-point (or the `rk run` translation, per D1)
is updated. The previous `spacedock_solver_v2` discriminator is
removed.

**AC-6.3** v1 class sidelined. The previous standalone
`SpacedockSolverAgent` moves to
`src/razorback/_legacy/agents/spacedock_solver_legacy.py`. Optionally
accessible via `agent.kind: spacedock_solver_legacy` for emergency
rollback during the reconciliation window; carries a DeprecationWarning
on instantiation. **This is its own commit** (`sideline: v1
SpacedockSolverAgent → _legacy`).

**AC-6.4, non-survivor modules sidelined, one commit per logical
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

**AC-6.5** trimmed canonical surface.
`src/razorback/{spec,agents,cli}` contain only v2-spec-named
artifacts. Removed pieces are in `_legacy/`. `agents/registry.py`
holds the spacedock_solver pydantic schema only.

**AC-6.6** examples reflect v2. `examples/specs/` flips to
v2-canonical agent kinds and the harbor-DAB adapter reference.

**AC-6.7** same-canonical cross-history diff is statistically null.
A full DAB benchmark via the post-Phase-6 canonical path produces a
`rk diff` against a pre-Phase-6 v2-class-on-harbor-adapter run (Phase
3's smoke result) whose stratified-delta paired bootstrap CI includes
zero. This confirms that the rename + sideline did not change v2
behavior.

**AC-6.8** razorback-implementation workflow dispatch can resume.
The Phase 0 pause is lifted; new v2-shaped backlog entities can flow
through the dispatch path.

**AC-6.9** `uv run pytest` exits 0.

**Walking-skeleton check.** AC-6.7, full DAB benchmark via canonical
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

**AC-7.1** walking skeleton holds. A DAB benchmark runs end-to-end
via the canonical v2 path after the deletion.

**AC-7.2** `_legacy/` audited. Every module under
`src/razorback/_legacy/` has a status: imported-by-parity-test (keep
or retire test); imported-by-deprecation-alias (decide whether the
deprecation alias is still needed); unreferenced (delete).

**AC-7.3** `_legacy/` removed or trimmed. Per the audit decisions.
One commit per logical deletion group for bisect-friendliness.

**AC-7.4, `grep -r 'from razorback._legacy'` returns no hits**
(or only hits the captain explicitly chose to retain).

**AC-7.5, `uv run pytest` exits 0** after the deletion.

**Walking-skeleton check.** Post-deletion DAB smoke runs and produces
the same headline score as Phase 6's smoke.

**Uncertainty surfaced.**
- Whether external consumers of razorback have been written that
  import from `_legacy/`. Mitigation: razorback has no external
  consumers yet, so this is local-only at the time of this plan.

**Sideline at phase end.** N/A, this phase performs the deletion.

**Phase status.** Optional. The plan does not gate later work on this
phase. `_legacy/` is harmless, it doesn't pollute the canonical
surface, doesn't get imported in normal use. The captain decides
whether to execute Phase 7 at all.

---

## Phase 8: Validate end-to-end + release

**Acceptance criteria.**

**AC-8.1** `nop`-agent smoke succeeds. A spec with the simplest
possible agent (`agent.kind: claude_code` or harbor's `nop` if
available) freezes, runs, and produces a run-dir with
`provenance.yaml`.

**AC-8.2** `spacedock_solver` smoke succeeds. A spec with
`agent.kind: spacedock_solver` + a minimal solver_workflow freezes,
runs, produces `agent_freeze/sealed_hash.txt`. (`phase_stats.json`
production via real workflow mods is part of the halt-resume
deferral; the smoke writes it via the test harness if needed for
schema validation, matching AC-3.6's hand-faked discipline.)

**AC-8.3** `rk audit` smoke succeeds. `rk audit --policy strict`
runs over a clean trial trajectory and exits 0; a fixture trajectory
with a forbidden `pip install datasets` invocation flags tainted
and exits 23.

**AC-8.4** resume smoke succeeds. Halt-resume cycle on the
canonical v2 path with hand-faked freeze writes (per AC-3.6);
sealed-hash check passes; resume proceeds.

**AC-8.5** experiment-workflow smoke succeeds. Phase 5's AC-5.4
hypothesis smoke, re-run post-Phase-6/7, still works end-to-end.

**AC-8.6, `uv run pytest` exits 0** from a clean checkout.

**AC-8.7** README at repo root reflects v2.

**AC-8.8, CHANGELOG lists every sideline + every new addition,**
citing v2 spec sections.

**AC-8.9** version tag exists. Major version bump.

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
| 0, Probe, decide, baseline | unchanged | +docs |
| 1, `rk run` v2 wrapper | runs via in-tree adapter | new code from spec + extractions; sideline old `run.py` |
| 2, DAB harbor adapter (sibling) | runs via in-tree adapter AND harbor adapter | sibling +1500; razorback unchanged |
| 3, SpacedockSolverAgent v2 (alongside) | runs via both agent classes | new `_v2` module from spec + extractions; v1 stays canonical |
| 4a, First-cut CLI completion (`rk score`, `rk audit`, `rk runs cost`, `rk run` budget gate, extended `rk freeze`) | v2-class × harbor-DAB end-to-end smoke succeeds at N=3 bookreview; every initial surface exercised | new code from spec + provenance extractions + taint.py port |
| **Goals 1+2 ship here** via the matrix dispatcher (AC-4a.12), `for spec in matrix: rk freeze; rk run --max-budget-usd-running budget.json; rk score --against-constant; rk audit --policy strict` |, |, |
| 6, Promote v2, sideline v1 (lands BEFORE Phase 5 so the templates can reference canonical `agent.kind: spacedock_solver`) | canonical = v2; same-canonical cross-history null required | rename + `git mv` to `_legacy/` |
| 5, Workflow templates (no mods initial) | end-to-end hypothesis smoke runs (autoresearch loop begins) | new markdown |
| 7, Delete `_legacy/` (optional) | v2-only canonical surface; same headline score | -delete |
| 8, Validate + release | tagged release | docs + verification |
| 4b, `rk diff` paired statistics | full paired-comparison statistics available | new code from spec, sequenced after the autoresearch loop's first run surfaces the need |

**Walking-skeleton invariant.** Per AC-0.9: the invariant is
*runnability* (DAB runs end-to-end, produces non-degraded
summary.json). Score-parity is a Phase 4+ test using `rk diff` on
same-adapter, same-agent pairs, not against the v1 dump-file
baseline.

---

## Decision points

These need a captain decision; the plan does not pre-decide them.

**D1, Harbor plugin contract** (probed in AC-0.2; locked in AC-3.7).
Entry-point registration or fallback CLI spec-translation.

**D2, Codex / pi support timing** (AC-0.7). Claude-only at
first-ship with stubs, or all three runtimes implemented up-front.

**D3, Optional CLI commands** (Phase 4 / future). Whether
`rk constraints check`, `rk baseline promote/verify`, `rk registry`
ship at first or defer until a consumer surfaces.

**D4, `rk init` subcommand** (Phase 5). Whether to ship a scaffolding
command or document the copy-and-modify procedure only.

**D5, DAB harbor adapter packaging** (AC-0.8). Sibling package
(`packages/razorback-plugin-dab/`) or new repo.

**D6, `_legacy/` retention** (Phase 7). Whether to execute Phase 7
at all, or keep `_legacy/` indefinitely.

**D7, Cross-dataset stratified aggregator architecture** (AC-2.8).
Plan recommends: razorback's `rk diff` owns the stratified math; the
benchmark adapter owns stratum *tagging* (each trial emits stratum
metadata). This split keeps `rk diff` benchmark-agnostic and the
adapter benchmark-specific. Captain confirms the split or picks the
all-in-adapter alternative.

---

## Deferred review findings (Packages G, H, I, J from 2026-05-19 staff reviews)

The following findings are captured but deferred, their impact is
scoped, and the named deliverables (paper reproduction + ade-bench
Haiku baseline) work without them.

**Package G, halt-resume infra-change correctness.** The sealed-input
hash inputs (spec §4.4 + §8.4) cover model, sampling, solver_workflow
content hash, prompt content hashes, spacedock skill version, harbor
agent kwargs. Missing: docker image digest + harbor version. A
halt-resume across an image rebuild or harbor minor bump silently
mixes conditions. **Lands when:** the autoresearch loop's first
halt-resume hypothesis run is planned. Not on the path for
deliverables 1+2 (both run full trials, no halt-resume).

**Package H, multi-benchmark stratified aggregator (full architecture).**
AC-2.8 commits to the split (math in `rk diff`, strata in adapter)
but doesn't ship the full abstraction. Cross-benchmark reuse of
`rk diff` against τ-bench, HAL, etc. may surface stratification
shapes DAB doesn't cover. **Lands when:** the second benchmark's
`rk diff` consumer surfaces a stratification difference.

**Package I, paper-writing caveats.** Three items defer to paper
draft phase:
- `provider_determinism_class: seed_honored | seed_ignored | unknown`
  in provenance.yaml; `rk diff` warns when both runs are
  `seed_ignored` at low N.
- Between-run variance accounting: run the headline reproduction
  twice and report between-run variance once.
- Power analysis at observed effect, already partly addressed by
  AC-4.2's achieved-power line; richer interpretation aids defer.

**Package J, future trajectory auditing.** **Folded into the
initial surface as `rk audit`.** Phase 4a's AC-4a.7 + AC-4a.8
ship a port of dataagentbench's `benchmark/lib/taint.py` mechanism
(see spec §3.2 + §9.4). The initial audit covers shell-command
patterns, web-search tool calls, heredoc / `python -c` decoding,
and subagent-trace recursion. **Remaining deferred extensions:**
benchmark-name / dataset-name / answer-key string scanning over
trial transcripts (a separate pattern category from forbidden tool
invocations); harbor's reward_hacking-rubric `harbor analyze`
delegation as a second-layer post-hoc check. Lands when a suspected
leak surfaces that the initial audit patterns did not catch.

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
- The initial commands (`rk run`, `rk freeze`, `rk score`,
  `rk audit`, `rk runs list/show/cost`) work against real harbor
  invocations. `rk diff` ships later (Phase 4b).
- `SpacedockSolverAgent` is the v2 runtime-adapter class at the
  canonical name.
- Workflow templates (no razorback-shipped mods initial) exist as
  package data.
- A captain can copy the experiment-workflow template, instantiate
  it, and run a hypothesis end-to-end against DAB via the new harbor
  adapter (AC-5.4 + AC-8.5).
- Walking-skeleton invariant held at every phase boundary
  (runnability never broke).
- All tests pass; `uv run pytest` exits 0 from a clean checkout.
- A version tag marks the release.
