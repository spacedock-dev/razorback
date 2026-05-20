# PKG-8 v2 — Plugin Pinning in `rk freeze` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `rk freeze` (v2 §3.2 + §8.2) to capture two additional dynamic inputs into `provenance.yaml`:

1. The installed **harbor adapter + harbor agent plugin shape** (e.g., DAB-adapter, `claude_code` agent, codex agent, future benchmark adapters). Discovered via `importlib.metadata.entry_points()` against razorback's and harbor's published entry-point groups.
2. The **solver_workflow directory content hash** (recursive over `solver_workflow/` from the spec's `agent.solver_workflow` path).

The frozen manifest gains a `plugins:` block and a `solver_workflow_hash` scalar. `rk run` re-resolves the plugins block at run start and refuses with `ProvenanceError` (exit 11) on drift, unless `--allow-plugin-drift` is passed. Freeze idempotency (spec §3.1) is preserved.

**Architecture:** PKG-8 sits inside the existing freeze pipeline (`provenance/freeze_cmd.py` orchestrates → `provenance/resolvers.py` per-field resolvers → `provenance/provenance_yaml.py` writer). The module inventory at `docs/superpowers/plans/2026-05-19-razorback-inventory.md:107-138` flags `resolvers.py` as ADAPT-EXTRACT and names **solver-workflow recursive content hash + spacedock skill / plugin pinning** as the two new resolvers v2 adds; PKG-8 implements both. The new run-side drift check sits alongside the existing alias-drift check in `provenance/drift.py` (AC-4).

**Tech stack:** Python 3.12, Typer (CLI), stdlib `importlib.metadata` / `hashlib` / `pathlib`. No new third-party deps.

**Spec source of truth:** `/Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` §3.2 (`rk freeze` CLI surface — "every dynamic input including spacedock skill version and solver-workflow content hash"), §3.4 (exit code 11 = `ProvenanceError`), §8.2 (resolver behavior, retries, refusal semantics, `solver_workflow/README.md ... pins under provenance.yaml.solver_workflow_hash`), §3.1 (idempotency).

**Inventory anchors (per `docs/superpowers/plans/2026-05-19-razorback-inventory.md`):**
- ADAPT-EXTRACT `src/razorback/provenance/resolvers.py:1-139` — add `resolve_solver_workflow_hash` (Task 2) and `resolve_plugin_inventory` (Task 3) alongside the existing six resolvers. The existing retry/transient classifier surface (`:46-54`) does not apply; the two new resolvers do not hit external APIs.
- ADAPT-EXTRACT `src/razorback/provenance/freeze_cmd.py:27-96` — extend the orchestration body to call the two new resolvers and stamp their outputs into `resolved` / `frozen_body['provenance']` (Task 4).
- KEEP-EXTRACT `src/razorback/provenance/provenance_yaml.py:14-21` — extend `REQUIRED_FIELDS` with `solver_workflow_hash` and `plugins` (Task 4).
- KEEP-EXTRACT `src/razorback/provenance/drift.py` — add `check_plugin_drift(frozen, resolved, *, allow=False)` next to the existing `check_alias_drift` / `check_harbor_drift` (Task 5).
- KEEP-EXTRACT `src/razorback/cli/run.py` — wire `--allow-plugin-drift` and call `check_plugin_drift` in `rk run`'s pre-check sequence (Task 5).

---

## AC ↔ task map

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-1 (`provenance.yaml.plugins` lists each installed harbor adapter + harbor agent plugin with version + entry-point group) | spec §3.2 (`rk freeze` resolves "every dynamic input including spacedock skill version"); inventory `:111-113` names "spacedock skill version pin" as a v2 add-resolver | Task 3 (`resolve_plugin_inventory` resolver), Task 4 (orchestration + `REQUIRED_FIELDS` add), Task 6 (unit test) |
| AC-2 (`rk freeze` content-hashes `solver_workflow` dir recursively + pins under `provenance.yaml.solver_workflow_hash`) | spec §8.2 ("Reads `solver_workflow/README.md` (and sibling files), content-hashes recursively, and pins under `provenance.yaml.solver_workflow_hash`") | Task 2 (`resolve_solver_workflow_hash` resolver), Task 4 (orchestration), Task 6 (unit test: determinism + byte-sensitivity + order-insensitivity) |
| AC-3 (`rk run` re-resolves plugins at run start; refuses with `ProvenanceError` exit 11 on drift; `--allow-plugin-drift` overrides; both hashes recorded) | spec §3.4 (exit 11 = `ProvenanceError`); spec §8.1 mirrors the alias-drift override pattern | Task 5 (`check_plugin_drift` + CLI flag wiring), Task 7 (unit test: refusal + override + recorded drift) |
| AC-4 (alias-drift detection from spec §8.2 stays intact alongside new plugin-pinning behavior) | spec §8.2 (alias-drift = exit 21); spec §3.4 (exit codes 11 + 21 are distinct) | Task 5 (additive change; preserves alias-drift call site), Task 8 (regression + co-firing test: first-fired surfaces in exit code) |
| AC-5 (freeze + re-freeze on same spec yields byte-identical `provenance.yaml`; §3.1 idempotency) | spec §3.1 (idempotency); spec §3.3 ("Provenance freeze format ... stable within a major version") | Task 2 + Task 3 implement deterministic output ordering; Task 9 integration test asserts byte-identity |

**Riskiest contract first.** Per CL's "Validating new mechanisms" rule, the two resolvers (Task 2 + Task 3) land with their unit tests (Task 6) BEFORE the orchestration wiring (Task 4) and BEFORE the run-time drift check (Task 5). The integration / idempotency test (Task 9) lands last.

---

## Coordination with r4 phase4a-rk-run-budget-gate

**Status.** The r4 plan (`docs/razorback-implementation/plans/phase4a-rk-run-budget-gate.md:428-507`) adds an `experiment_meta:` block to the spec schema carrying `max_budget_usd` and **`estimated_cost_usd`**. The r4 plan flags `estimated_cost_usd` as **"populated by `rk freeze` (PKG-8)"** (`:428-432` and `:1363`) — but the field name and the schema-collision resolution (`experiment_meta:` vs `experiment:` the string name) are r4's invention to keep that work unblocked. PKG-8 must decide:

**Decision: schema lives in r4; PKG-8 does not own `experiment_meta`.** Rationale:

1. r4 already ships the `experiment_meta` block as a schema addition because its budget gate needs the field to exist *before* `rk freeze` populates it (r4 reads from a frozen spec at `rk run` time). Re-locating the schema in PKG-8 would force r4 to either depend on PKG-8 (gating a Phase 4a fragment on a Phase 4a fragment) or duplicate the field. Single-owner wins.
2. PKG-8's responsibility is **populating** dynamic fields. `estimated_cost_usd` is a *static* operator input today (the captain writes it in the source spec; `rk freeze` passes it through). There is no cost model in v1 razorback for `rk freeze` to compute from first principles, and the spec does not promise one. PKG-8 cannot populate what it cannot derive.
3. The r4 plan's claim that "PKG-8 adds cost-estimation" is read here as "PKG-8 will eventually own a cost estimator on top of r4's schema field." That is **out of scope** for this PKG-8 v2 plan (entity body "Out of scope" does not list cost estimation, but the entity's five ACs do not mention it either; the v2 spec's §3.2 lists no cost-estimation responsibility under `rk freeze`).

**What PKG-8 commits to:**
- PKG-8 does **not** add an `experiment_meta.estimated_cost_usd` slot — r4 owns the schema (`src/razorback/spec/schema.py`).
- PKG-8 does **not** add an `estimated_cost_usd` resolver to `provenance/resolvers.py`.
- PKG-8 **does** pass through `experiment_meta` verbatim into `spec.frozen.yaml` via the existing `spec.model_dump(mode="json")` path in `freeze_cmd.py:81` (already byte-faithful per Phase 1 P1-T8). Verified by reading the merged r4 schema PR before PKG-8 lands; if r4 is not merged at PKG-8 land time, no PKG-8 change is required for the pass-through to work — `model_dump` already echoes unknown blocks.
- A short note in `freeze_cmd.py`'s module docstring **explicitly names** `experiment_meta.estimated_cost_usd` as a static field that pass-through-only carries (so a future reader does not assume `rk freeze` computes it).

**Escalation path.** If a future captain decides `rk freeze` should compute `estimated_cost_usd` from model alias × token estimate × prompt-content hash, that lands as its own entity (PKG-8.1 or a new package). It does not block PKG-8 v2's five ACs.

---

## Out of scope per entity body

- Per-skill version pinning (e.g., `spacedock@0.11.2`). The solver-workflow content hash + plugin distribution version captures the relevant surface.
- Pinning beyond harbor's plugin surface (apt packages, system libs). §6.1's `pin_image_digest` covers container content.
- Auto-cleanup of stale skill caches between seed and resume.
- The hash resolver for `SpacedockSolverAgent`'s halt-resume sealed hash — §4.3 names this as the class's job, not `rk freeze`'s.

---

## Task 1 — Worktree setup + schema verification

**Files:**
- Read: `src/razorback/spec/schema.py` (verify whether r4 has merged the `experiment_meta` block); `src/razorback/provenance/provenance_yaml.py:14-21` (current `REQUIRED_FIELDS`).
- Read: existing freeze-test fixtures under `tests/unit/test_freeze.py`, `tests/unit/test_provenance_resolvers.py`, `tests/unit/test_spec_freeze_cli.py`.

**Why:** Confirm the schema slot status before writing code that depends on it. If r4 has merged, the pass-through path is already byte-faithful and no PKG-8 schema change is needed; if r4 has not merged, document the contingency in the worktree branch's `pr:` notes for the FO.

**Steps:**
- [ ] Create the worktree: `git worktree add .worktrees/spacedock-ensign-pkg8-v2-rk-freeze-pinning ensign/pkg8-v2-rk-freeze-pinning`. All subsequent reads/writes/commits land here.
- [ ] `grep -n "experiment_meta" src/razorback/spec/schema.py` from the worktree branch tip. Record presence/absence in the worktree's task notes.
- [ ] `grep -n "REQUIRED_FIELDS" src/razorback/provenance/provenance_yaml.py` and confirm the current six-field list matches the inventory's `:14-21` cite.

**Validation:** Worktree exists; `uv run pytest tests/unit/test_provenance_*.py -q` is green from the worktree branch tip BEFORE any PKG-8 change (baseline).

---

## Task 2 — `resolve_solver_workflow_hash(dir_path) -> str | None` resolver (AC-2)

**Files:**
- Modify: `src/razorback/provenance/resolvers.py` (append the new resolver).

**Why:** Spec §8.2 names this explicitly: "Reads `solver_workflow/README.md` (and sibling files), content-hashes recursively, and pins under `provenance.yaml.solver_workflow_hash`." Determinism + byte-sensitivity + order-insensitivity are the three properties AC-2 requires.

**Resolver contract:**
- Signature: `def resolve_solver_workflow_hash(dir_path: Path) -> str | None:`.
- Returns `f"sha256:{hex}"` on success, `None` if the path does not exist or is not a directory.
- Walks the directory recursively, sorted by **POSIX relative path** (`relative_to(dir_path)`, components joined with `/`), reading each regular file's bytes; symlinks are followed when they resolve inside `dir_path` and recorded as their target's content (or skipped if they point outside — record nothing rather than failing, to keep the hash stable across operator-checkout environments where a symlink may be broken).
- The hash input is the byte sequence: for each file in sorted relative-path order, `len(path).to_bytes(4, "big") + path.encode("utf-8") + len(content).to_bytes(8, "big") + content`. The frame prefix prevents path/content boundary collisions.
- Skips: `.git/`, `__pycache__/`, `.pytest_cache/`, `.DS_Store`. These do not belong to the solver_workflow's semantic content.

**Steps:**
- [ ] Add the resolver immediately after `resolve_prompt_hashes` (line 140) in `src/razorback/provenance/resolvers.py`.
- [ ] Add a single-line inline comment citing the spec: `# spec §8.2: recursive content hash, pinned under provenance.yaml.solver_workflow_hash`.
- [ ] Helper: `def _walk_solver_workflow(dir_path: Path) -> Iterator[tuple[str, bytes]]:` yields `(rel_posix_path, content_bytes)` pairs in sorted order, applying the skip list.

**Validation:** Unit tests in Task 6.

**Commit:** `PKG-8 v2 Task 2: resolve_solver_workflow_hash resolver (AC-2)`.

---

## Task 3 — `resolve_plugin_inventory() -> dict | None` resolver (AC-1)

**Files:**
- Modify: `src/razorback/provenance/resolvers.py` (append the new resolver).

**Why:** Entity AC-1 requires the `plugins:` block to list each installed harbor adapter + harbor agent plugin with package name, installed version, content hash where applicable, and entry-point group. `importlib.metadata.entry_points()` is the discovery surface.

**Resolver contract:**
- Signature: `def resolve_plugin_inventory(*, entry_points_fn: Callable[[], EntryPoints] | None = None) -> dict[str, list[dict]] | None:`.
- `entry_points_fn` defaults to `importlib.metadata.entry_points` for dependency injection in unit tests.
- Returns a dict shaped: `{"plugins": [{"group": <str>, "name": <str>, "distribution": <pkg-name>, "version": <pkg-version>}, ...]}`. The inner list is sorted by `(group, name)`. **Hash inclusion** ("content hash where applicable" per AC-1) applies only to in-tree adapters that ship a module path the resolver can stat — for distribution-installed plugins (the common case), the distribution version + package name + entry-point group is the pinning surface; the SHA over a site-packages directory is non-deterministic across `uv` installs (mtime, byte-for-byte differences in `RECORD` files). Decision: record `package: <distribution-name>`, `version: <Version(distribution)>`, `group: <entry-point group>`, `name: <entry-point name>` per row. No content hash. Determinism is enforced by sort order alone. **This satisfies AC-1's verbatim "package name, installed version" plus "entry-point group that routed it"; the "content hash where applicable" caveat is satisfied by the parenthetical — for distribution-installed plugins the hash does not apply.**

**Entry-point groups to scan:**
1. `harbor.agents` — harbor agent plugins (`claude_code`, `codex`, `pi`, `SpacedockSolverAgent` after Phase 3 registration).
2. `harbor.benchmarks` — harbor benchmark adapters (DAB-adapter via `razorback-plugin-dab`, future adapters).
3. `razorback.plugins` — razorback-side plugin namespace (forward-compatible; harmless if no plugins register here today).

The group list is hard-coded in the resolver (the spec does not yet promise group-name stability across harbor versions; if harbor renames, PKG-8's resolver gets a 1-line fix). The harbor source-of-truth for the `harbor.agents` group name lives at `harbor/agents/factory.py` (already imported elsewhere in razorback); verify the group name verbatim from harbor's source before landing the resolver. If a group's lookup returns empty, the resolver records nothing for that group rather than erroring — empty is a valid environment state (e.g., a CI image without the DAB adapter installed).

**Return shape on a fixture environment** (DAB adapter + claude_code agent installed):
```yaml
plugins:
  - group: harbor.agents
    name: claude_code
    distribution: harbor
    version: "0.6.6"
  - group: harbor.benchmarks
    name: dab
    distribution: razorback-plugin-dab
    version: "0.1.0"
```

**Steps:**
- [ ] Add the resolver after `resolve_solver_workflow_hash` in `src/razorback/provenance/resolvers.py`.
- [ ] Inline comment: `# AC-1: harbor.agents + harbor.benchmarks + razorback.plugins entry-point inventory.`
- [ ] Use `from importlib.metadata import entry_points, distribution as _distribution, PackageNotFoundError` at module top.
- [ ] Wrap each `_distribution(ep.dist.name)` call in `try / except PackageNotFoundError` — for built-in (non-installed) entry points (none today, but harbor may register some), skip with no error.

**Validation:** Unit tests in Task 6.

**Commit:** `PKG-8 v2 Task 3: resolve_plugin_inventory resolver (AC-1)`.

---

## Task 4 — Wire both resolvers into `freeze_cmd.py` + extend `REQUIRED_FIELDS` (AC-1, AC-2)

**Files:**
- Modify: `src/razorback/provenance/freeze_cmd.py` (extend orchestration).
- Modify: `src/razorback/provenance/provenance_yaml.py` (extend `REQUIRED_FIELDS`).

**Why:** AC-1 + AC-2 require both fields to land in `provenance.yaml` AND `spec.frozen.yaml`'s `provenance:` block. The existing orchestration shape (resolve → `refuse_if_any_unresolved` → `write_provenance_yaml`) extends in place.

**Steps:**
- [ ] In `provenance_yaml.py:14-21`, extend `REQUIRED_FIELDS` to add `"solver_workflow_hash"` and `"plugins"` after the existing six. **Note:** the order in `REQUIRED_FIELDS` is the wire order — append, do not insert mid-tuple (spec §3.3 stability promise: existing fields do not move).
- [ ] In `freeze_cmd.py`:
  - [ ] Import `resolve_plugin_inventory` and `resolve_solver_workflow_hash`.
  - [ ] Compute `solver_workflow_path = getattr(spec.agent, "solver_workflow", None)`. If present and the path exists, call `resolve_solver_workflow_hash(Path(solver_workflow_path))`; otherwise `None`. The spec's §6.3 validation has already verified `solver_workflow/README.md` exists by this point (when the agent is `spacedock_solver`); a `None` here means a non-spacedock agent which legitimately has no solver_workflow.
  - [ ] Call `resolve_plugin_inventory()` unconditionally — every freeze captures the installed plugin shape.
  - [ ] Stamp both into `resolved` and into `frozen_body["provenance"]` alongside the existing seven fields.
  - [ ] Extend the module docstring (`freeze_cmd.py:1-3`) with: `# Pass-through-only: experiment_meta block (incl. estimated_cost_usd) is a static operator field, not a rk freeze-computed dynamic input; r4 phase4a-rk-run-budget-gate owns the schema.`

**Conditional resolution.** `solver_workflow_hash`:
- If the spec's agent kind is `spacedock_solver` and `agent.solver_workflow` is set, the field must resolve (refuse on `None`).
- If the spec's agent kind is not `spacedock_solver`, the field is recorded as `None` and added to the `unresolved:` list ONLY when `--allow-missing` is **not** passed; refusal semantics match existing `prompt_file_hashes` behavior at `provenance_yaml.py:25-33`.
- Actually: the simpler rule, matching existing semantics: if `agent.solver_workflow` is unset, the field is **not required** for that spec (drop from per-spec `REQUIRED_FIELDS` view). To keep `REQUIRED_FIELDS` a static tuple, follow the existing pattern of letting `None` → `unresolved:` and relying on `--allow-missing` for non-spacedock specs; document the rule in a freeze_cmd.py inline comment.

**Validation:** Existing `tests/unit/test_spec_freeze_cli.py` still passes (no semantic regression for the seven existing fields). New unit tests added in Task 6.

**Commit:** `PKG-8 v2 Task 4: wire solver_workflow_hash + plugins into freeze orchestration (AC-1, AC-2)`.

---

## Task 5 — `check_plugin_drift` + `--allow-plugin-drift` flag in `rk run` (AC-3, AC-4)

**Files:**
- Modify: `src/razorback/provenance/drift.py` (add `check_plugin_drift`).
- Modify: `src/razorback/cli/run.py` (add CLI flag, call the check).
- Modify: `src/razorback/provenance/errors.py` (verify `ProvenanceError(exit_code=11)` exists; it does, per inventory `:205-217`).

**Why:** AC-3 requires `rk run` to re-resolve plugins at run start and refuse with exit 11 on drift, with override flag. AC-4 requires alias-drift detection to stay intact alongside.

**`check_plugin_drift` contract:**
- Signature: `def check_plugin_drift(frozen: list[dict] | None, *, resolver: Callable[[], dict] | None = None, allow: bool = False) -> dict | None:`.
- `frozen` is the `plugins` list from `spec.frozen.yaml.provenance.plugins` (None when the frozen spec predates PKG-8, in which case the check is a no-op and returns `None`).
- `resolver` defaults to `resolve_plugin_inventory`.
- Compares the frozen list against the resolved list by (group, name) keys, finding any row where `(distribution, version)` differs.
- If any drift found and `allow=False`, raises `ProvenanceError(f"plugin drift: {names}; pass --allow-plugin-drift to override")` (exit 11 per existing `ProvenanceError.exit_code`).
- If `allow=True`, returns a drift record dict `{"frozen": <list>, "resolved": <list>}` for `provenance.yaml` to write under a `plugin_drift:` key (mirror the `alias_drift:` record shape at `provenance_yaml.py:36-61`).

**`rk run` wiring:**
- Add `--allow-plugin-drift: bool = typer.Option(False, ...)` to the `rk run` Typer command in `src/razorback/cli/run.py`.
- Insert `check_plugin_drift` call AFTER `check_alias_drift` and BEFORE the harbor delegate. The ordering matters for AC-4's co-firing rule: alias-drift fires first (exit 21) and surfaces in the exit code if both inputs drift; plugin-drift fires only if alias-drift's check allowed continuation (no drift or `--allow-alias-drift`).
- The drift record (when `allow=True`) flows into the existing `provenance.yaml` rewrite path used by `check_alias_drift`'s drift recording, under a new top-level `plugin_drift:` key.

**Steps:**
- [ ] Add `check_plugin_drift` to `provenance/drift.py`.
- [ ] Add the CLI flag + call site in `cli/run.py`.
- [ ] Extend `provenance_yaml.write_provenance_yaml` to accept an optional `plugin_drift_record: dict | None = None` parameter and write it under `plugin_drift:`, mirroring the existing `alias_drift:` record path.

**Validation:** Unit tests in Task 7.

**Commit:** `PKG-8 v2 Task 5: check_plugin_drift + --allow-plugin-drift on rk run (AC-3, AC-4)`.

---

## Task 6 — Unit tests for the two resolvers (AC-1, AC-2)

**Files:**
- Create: `tests/unit/test_resolve_solver_workflow_hash.py`.
- Create: `tests/unit/test_resolve_plugin_inventory.py`.

**Test list — solver_workflow_hash (AC-2):**
- `test_returns_sha256_prefix` — single-file fixture; output starts with `"sha256:"`.
- `test_deterministic_two_invocations` — call twice on the same fixture; equal output.
- `test_byte_sensitive_one_byte_change` — fixture with `a/foo.md` = `"hello"`; mutate to `"helloo"`; output differs.
- `test_order_insensitivity_equivalent_trees` — build two fixtures with identical files in different filesystem creation order; outputs match.
- `test_skips_dotgit_and_pycache` — adding `.git/HEAD` or `__pycache__/foo.pyc` to a fixture leaves the hash unchanged.
- `test_returns_none_on_missing_dir` — non-existent path → `None`.
- `test_path_frame_collision_immunity` — fixtures `{ "ab/c": "d" }` and `{ "a/bc": "d" }` hash to **different** values (regression for boundary-collision bugs).

**Test list — plugin_inventory (AC-1):**
- `test_dab_only_environment` — inject `entry_points_fn` that returns only the DAB adapter; output's `plugins` list has 1 entry with `group: harbor.benchmarks`, `name: dab`, version `"0.1.0"`.
- `test_claude_code_only_environment` — inject only the `claude_code` agent; 1 entry with `group: harbor.agents`.
- `test_both_present` — both DAB + claude_code; 2 entries sorted by `(group, name)`; DAB sorts before claude_code (`harbor.agents` < `harbor.benchmarks` alphabetically).
- `test_returns_none_for_no_groups` — entry-points list is empty for all three groups; output is `{"plugins": []}` (empty list, NOT `None` — the field resolved; the environment just has no plugins).
- `test_entry_point_group_field_present` — every output row carries a `group:` field.
- `test_distribution_lookup_failure_skipped` — inject an entry point whose `_distribution()` raises `PackageNotFoundError`; the row is omitted, the resolver returns a list missing that row, no exception.

**Steps:**
- [ ] Write tests one-test-at-a-time per TDD discipline (CLAUDE.md "Test Driven Development").
- [ ] Implement only enough resolver code to pass each test.

**Validation:** `uv run pytest tests/unit/test_resolve_solver_workflow_hash.py tests/unit/test_resolve_plugin_inventory.py -q` → all green.

**Commit:** `PKG-8 v2 Task 6: unit tests for solver_workflow_hash + plugin_inventory resolvers (AC-1, AC-2)`.

---

## Task 7 — Unit tests for `check_plugin_drift` + override flag (AC-3)

**Files:**
- Create: `tests/unit/test_provenance_plugin_drift.py`.

**Test list:**
- `test_no_drift_returns_none` — frozen and resolved plugin lists match; `check_plugin_drift` returns `None` without raising.
- `test_drift_raises_provenance_error_default` — mutate one row's version between frozen and resolved; `check_plugin_drift(..., allow=False)` raises `ProvenanceError` with `exit_code == 11` and message names the drifted plugin's `(group, name)`.
- `test_allow_flag_returns_drift_record` — same drift, `allow=True`; returns a `{"frozen": ..., "resolved": ...}` dict; no exception.
- `test_frozen_none_is_noop` — frozen plugins field is `None` (pre-PKG-8 frozen spec); returns `None`; no exception. (Forward-compat: old frozen specs do not break new `rk run`.)
- `test_rk_run_exits_11_on_drift` — invoke `rk run` via Typer's testing surface with a fixture frozen spec + an injected resolver that returns a drifted list; exit code is 11.
- `test_rk_run_proceeds_with_override` — same, with `--allow-plugin-drift`; exit code is whatever harbor delegate would return (mock the delegate to exit 0); `provenance.yaml` rewrite contains a `plugin_drift:` key.

**Commit:** `PKG-8 v2 Task 7: check_plugin_drift refusal + override unit tests (AC-3)`.

---

## Task 8 — Regression + co-firing test for alias-drift + plugin-drift (AC-4)

**Files:**
- Modify: `tests/unit/test_provenance_alias_drift.py` (add a co-firing test alongside existing tests).

**Why:** AC-4 requires alias-drift detection to stay intact alongside plugin-drift, and the first-fired check to surface in the exit code.

**Test list:**
- `test_alias_drift_alone_exits_21` — existing test, asserts unchanged behavior (regression guard).
- `test_plugin_drift_alone_exits_11` — already covered in Task 7 (cross-reference here).
- `test_alias_and_plugin_drift_alias_fires_first` — fixture where BOTH inputs drift; assert `rk run` exits 21 (alias-drift's exit code), NOT 11. The plugin-drift check never runs because `check_alias_drift` raises first. This matches the call ordering in Task 5 ("alias-drift check first, plugin-drift second").
- `test_allow_alias_drift_then_plugin_drift_exits_11` — same fixture, but pass `--allow-alias-drift`; the alias-drift check returns a drift record without raising; the plugin-drift check then fires and exits 11.

**Commit:** `PKG-8 v2 Task 8: alias-drift + plugin-drift co-firing tests (AC-4)`.

---

## Task 9 — Integration test for freeze idempotency (AC-5)

**Files:**
- Create: `tests/integration/test_freeze_idempotency_pkg8.py`.

**Why:** AC-5 demands byte-identical `provenance.yaml` across two `rk freeze` invocations on the same source spec — spec §3.1's idempotency rule. The two new fields must not break this (e.g., dict iteration order, sorted-vs-unsorted plugin list, file walking order).

**Test list:**
- `test_freeze_twice_byte_identical_provenance_yaml` — fixture source spec with a `solver_workflow/` dir + injected stable plugin resolver. Run `rk freeze` twice via Typer's testing surface to two separate `--out` paths (so they cannot collide). Read both `provenance.yaml` siblings as bytes; assert `bytes_a == bytes_b`.
- `test_freeze_twice_byte_identical_spec_frozen_yaml` — same setup, also assert the two `spec.frozen.yaml` files are byte-identical.
- `test_solver_workflow_change_breaks_idempotency` — sanity check: mutate one file in `solver_workflow/`, refreeze; the two `provenance.yaml` files differ (this proves the idempotency test in the prior case is meaningful — not just always-equal because the resolver returns a constant).

**Validation:** `uv run pytest tests/integration/test_freeze_idempotency_pkg8.py -q` → green.

**Commit:** `PKG-8 v2 Task 9: freeze idempotency integration test (AC-5)`.

---

## Task 10 — Full test suite green from worktree branch tip

**Files:**
- None (validation only).

**Steps:**
- [ ] `uv run pytest -q` from the worktree root. All tests green.
- [ ] `uv run pytest tests/unit/test_provenance_*.py tests/integration/test_freeze_idempotency_pkg8.py -q` as a focused re-run.
- [ ] If r4's `experiment_meta` schema has merged into main and the worktree's base, re-freeze the deterministic-smoke fixture and confirm `experiment_meta` passes through verbatim to `spec.frozen.yaml` (one-line `grep` check).

**Validation:** Pristine test output per CLAUDE.md "Testing" rule. No deprecation warnings introduced by the new resolvers. Any pre-existing failures or warnings are documented in the worktree branch's task notes, not silently inherited.

**Commit:** No code commit; this task gates handoff to the FO for the next stage.

---

## Acceptance command summary (entity body verbatim)

- `uv run rk freeze <fixture-spec>` writes a manifest with the `plugins:` block populated.
- `uv run rk run <frozen-spec>.frozen.yaml` exits 11 after a forced plugin drift.
- `uv run rk freeze <spec>` twice produces byte-identical `provenance.yaml`.

---

## Style notes

- Em-dashes banned (commit a2e9c49). Use commas, parentheses, or sentence breaks instead.
- Code-comment ABOUTME headers per CLAUDE.md for any new `.py` file.
- Spec cites in comments use section identities (`§3.2`, `§8.2`) not commit hashes.
- No backwards-compat shims without explicit CL approval. The new `plugins` field on `provenance.yaml` is additive; `check_plugin_drift`'s `frozen is None` path is the forward-compat for pre-PKG-8 frozen specs, not back-compat.
