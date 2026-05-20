# Spec corrections from Phase 0 probes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Edit the v2 spec at `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` so its language matches harbor's actual surface as established by AC-0.2 (entry-point execution probe) and AC-0.3/4/6 (harbor source probe). The spec edits are the entire deliverable for stages `plan → implementation → validation`; no code lands under this entity. Three of the four remaining ACs are mechanical terminology / framing fixes; the fourth (AC-4 observers translation) names a translation rule with the probe doc as the citation.

**Architecture:** The corrections fall into four buckets:

1. **AC-1 — `import_path` dispatch.** Drop every mention of "entry-point group" registration; replace with the dotted-`import_path` shape harbor actually uses (`AgentConfig.import_path: "module.path:ClassName"`, `harbor/agents/factory.py:95-133`). Two spec sections carry the wrong language (§4.5 + §9.2); §4.1's `agent.kind` story is correct and stays as-is — razorback's own `kind: spacedock_solver` block is translated by `rk run`'s spec rewriter into harbor's `agents[].import_path` field.
2. **AC-2 — Benchmark-adapter offline-generator framing.** Harbor benchmark adapters have no runtime dispatch; they are standalone packages invoked via `uv run <adapter-folder>` that emit task directories consumed by `JobConfig.tasks[].path` / `datasets[].path`. The spec's existing §1.3 non-goal already states razorback ships no adapters, so the framing fix is narrow: add a single paragraph in §6.1 (where the spec's benchmark block is defined) naming the offline-generator contract and citing the probe; verify nothing in §2 + §3 + §8.4 implies runtime adapter dispatch.
3. **AC-3 — `n_attempts` vs `trials` naming.** Razorback's spec keeps `trials:` as its surface (it carries different semantics — "N independent trials per task" vs harbor's `n_attempts: int` per-trial retry count, per the source probe). The fix is to add a translation comment in §6.1's example and a translation paragraph in §6.3 (Validation) naming the field name divergence and citing the probe.
4. **AC-4 — Observers translation rule.** Razorback's `observers: list[ObserverBlock]` has no slot in harbor's `JobConfig`. Per the source probe, harbor's own publisher/event infrastructure (`harbor/publisher/`) emits per-job events; razorback's `jsonl`/`stdout` observers translate by reading harbor's per-job event stream post-`harbor run`, not by injecting into `JobConfig`. Add a paragraph in §6.3 (Validation) naming this translation rule and citing the probe.

AC-5 is dropped — it is superseded by `b5`'s AC-2 (the freeze tree moves to `_razorback/freeze/<sealed_hash>/`, outside `trials/<name>/` entirely; the §7.1 path literal fix ra's AC-5 proposed is overwritten by b5's edit before this plan executes).

**Tech Stack:** Markdown only. No Python, no harbor surfaces. The implementation stage runs `Edit` calls against `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` and `grep` to confirm AC-1's verifier passes mechanically. The validation stage re-reads each touched section cross-checked against the two probe docs and re-runs the named greps.

**Source of truth:**
- Probe doc 1 (AC-0.2): `/Users/clkao/git/razorback/docs/superpowers/plans/2026-05-19-harbor-entry-point-probe.md` — establishes import_path dispatch + offline-adapter contract.
- Probe doc 2 (AC-0.3/4/6): `/Users/clkao/git/razorback/docs/superpowers/plans/2026-05-19-harbor-source-probe.md` — establishes JobConfig field names, the `trials` vs `n_attempts` gap, and the observers translation gap.
- Entity ACs: `/Users/clkao/git/razorback/docs/razorback-implementation/spec-corrections-from-phase0-probes.md`.
- v2 spec being edited: `/Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`. Plan-time line ranges of the touch points: §4.5 (398-422), §6.1 (527-573), §6.3 (595-607), §9.2 (875-881). Line numbers will drift during the edits; the section anchors do not. b5's edits to §4.4 + §7.1 + §3.1 are running concurrently — implementation MUST re-grep section headers (`grep -n "^### 4.5"`) before each Edit rather than relying on line numbers carried in this plan.

## Supersession of AC-5

The entity's AC-5 proposes: "Spec §7.1 path literal `logs_dir/` corrected to `agent/`." That correction is superseded by `b5 spec-mitigation-resume-conflict`'s AC-2 (plan at `docs/razorback-implementation/plans/spec-mitigation-resume-conflict.md`, supersession block lines 13-19). b5's AC-2 moves the freeze tree to `<harbor-run-dir>/_razorback/freeze/<sealed_hash>/` — outside `trials/<name>/` entirely. The §7.1 path literal ra's AC-5 named (`logs_dir/agent_freeze` → `trials/<name>/agent/agent_freeze`) is irrelevant after b5 lands because the destination is neither location; it is `_razorback/freeze/<sealed_hash>/`.

**This plan does not implement AC-5.** The implementation stage marks AC-5 SKIPPED in its stage report with the rationale: "superseded by `b5f4zn4vd74yvrmpn207qrwk` AC-2; the §7.1 path literal moves outside `trials/<name>/` entirely, not to a subpath of it (b5 plan lines 13-19)." The entity AC-5's grep verifier (`grep -n "logs_dir/agent_freeze"` returns zero hits) will pass after b5's AC-2 lands, but this entity does not claim credit for that grep.

## Captain decisions resolved (Phase 0)

Per the entity's out-of-scope note, two captain decisions referenced in this entity's framing have been resolved during Phase 0 and are recorded here for downstream entity authors (Phase 1, Phase 2, Phase 3) to cite:

- **D2 (codex/pi support timing, AC-0.7):** Captain decision — **claude-only at first ship.** `codex.py` and `pi.py` adapter sub-modules ship as `NotImplementedError` stubs in the first cut. Functional implementations land when a consumer (a second-runtime experiment, a paper-reproduction targeting codex) demands them. Per reconciliation plan line 148; consumed by `phase3-spacedock-solver-v2.md` (id `d5gxb8p7eea6nk85nja5zmbr`).
- **D5 (DAB harbor adapter packaging, AC-0.8):** Captain decision — **sibling package.** The DAB adapter ships as `packages/razorback-plugin-dab/`, a parallel sibling package to razorback's core, not as a subpackage. Per reconciliation plan line 152; consumed by `phase2-dab-harbor-adapter.md`.

Neither decision changes the spec's text directly (the spec already reads consistent with both — §1.3's non-goals state razorback ships no adapters; §8.4's per-runtime adapter sub-modules paragraph admits per-runtime variability). This plan does not edit the spec for D2/D5; the paragraph above is the durable record so downstream plan authors can cite "ra plan §Captain decisions resolved" rather than re-derive.

## AC ↔ task map (1:1 minus dropped AC-5)

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-1 — replace "entry-point group" language with `import_path` | §4.5 (lines 398-422 pre-edit) + §9.2 (lines 875-881 pre-edit); probe doc 1 lines 28-60 (entry-point group names section) | Task 1 (riskiest contract — §4.5 is the spec's whole story on how harbor finds razorback's class; if this is wrong, Phase 3 implements against an invented contract) |
| AC-2 — benchmark-adapter offline-generator framing | §6.1 (lines 527-573 pre-edit; the benchmark block example); §1.3 + §2 already correct; probe doc 1 lines 48-56 + 161-190 ("Adapter dispatch probe" section) | Task 2 |
| AC-3 — `n_attempts` vs `trials` translation comment | §6.1 example (line 562 carries `trials: 5`) + §6.3 Validation paragraph; probe doc 2 line 79 (the `trials: int` vs `n_attempts` gap row) | Task 3 |
| AC-4 — observers translation rule | §6.3 Validation paragraph (a sibling paragraph to AC-3's); probe doc 2 line 80 (the observers gap row) | Task 4 |
| AC-5 — SUPERSEDED | n/a | (no task; SKIPPED in implementation report per supersession above) |

**Riskiest contract first.** Task 1 lands the import_path fix because §4.5 is the spec's whole narrative on how harbor finds and instantiates razorback's `SpacedockSolverAgent`. If §4.5's words are wrong about the mechanism (entry-point groups vs import_path), Phase 3's class registration ACs inherit the error. The other three tasks are local terminology / paragraph additions whose blast radius is contained to one or two sections each. Per CL's "Validating new mechanisms" rule, the riskiest contract (the registration mechanism Phase 3 implements against) lands first.

---

## Task 1 — Replace "entry-point group" language with `import_path` (AC-1)

**Files:**
- Modify: `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` §4.5 (pre-edit lines 398-422) and §9.2 (pre-edit lines 875-881)

**Pre-condition reads (mandatory, do not skip):**
- `/Users/clkao/git/razorback/docs/superpowers/plans/2026-05-19-harbor-entry-point-probe.md` end-to-end. Note especially lines 28-60 ("Entry-point group names" — names the actual mechanism), lines 192-239 ("Implications" — names what razorback's `rk run` translator emits), and lines 73-88 (probe `pyproject.toml` showing no entry-point declaration).
- The current §4.5 (lines 398-422) and §9.2 (lines 875-881) of `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`.

- [ ] **Step 1: Locate §4.5 and §9.2**

Run: `grep -n "^### 4.5 Registration with harbor\|^### 9.2" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: two matches.

- [ ] **Step 2: Replace §4.5's body**

Use `Edit` to replace the entire §4.5 body (everything from the line after `### 4.5 Registration with harbor` up to but not including the next `---` separator) with the corrected text. The OLD body to find (verbatim, including the open question and fallback paragraphs):

```
`SpacedockSolverAgent` registers with harbor via harbor's agent-plugin
discovery mechanism. The expected shape is a `pyproject.toml` entry-point
group that harbor scans at `harbor run` time; razorback's package
declares:

```toml
[project.entry-points."harbor.agents.installed"]
spacedock_solver = "razorback.agents.spacedock_solver:SpacedockSolverAgent"
```

Users write `agent.kind: spacedock_solver` in their spec and harbor
routes to razorback's class. No harbor monorepo PR is required.

**Open question.** The exact entry-point group name and registration
shape depends on harbor's published plugin contract. Razorback's
`harbor publish` / `cli/template-adapter` surface implies such a
mechanism exists, but the contract must be confirmed against the
pinned harbor version before implementation. **Fallback if no
plugin contract exists:** razorback's CLI grows a thin spec-translation
pre-pass (`rk run` rewrites `agent.kind: spacedock_solver` to
`agent.kind: claude_code` with appropriate kwargs, then invokes
`harbor run`). This trades the wire-through cleanness for keeping the
solver-agent abstraction owned by razorback.
```

The NEW body:

````markdown
`SpacedockSolverAgent` registers with harbor via harbor's
**`import_path` dispatch mechanism** (`harbor/agents/factory.py:95-133`,
`AgentFactory.create_agent_from_import_path`). Harbor does **not**
enumerate setuptools / PEP-621 entry-point groups for agents; the
dispatch surface is a Python dotted import-path string on the harbor
`JobConfig`. Specifically, `AgentConfig.import_path: "module.path:ClassName"`
(`harbor/models/trial/config.py:44-63`) names the class harbor loads
and instantiates per trial. The class must subclass
`harbor.agents.base.BaseAgent` and implement `name()`, `version()`,
`setup()`, `run()`.

Razorback's `rk run` is a thin **spec translator**. It rewrites
razorback's spec.yaml shape into a harbor `JobConfig`:

- razorback's singular `agent: { kind: spacedock_solver, ... }` block
  becomes harbor's plural
  `agents: [{ import_path: "razorback.agents.spacedock_solver:SpacedockSolverAgent", kwargs: { ... } }]`.
- razorback-only fields on the agent block (`model`, `sampling`,
  `solver_workflow`, `tools_allowed`, `tools_denied`, etc.) flow
  through harbor's `AgentConfig.kwargs` dict, which `AgentFactory`
  splats into the class constructor (`harbor/agents/factory.py:161,170`).

No setuptools entry-point declaration is needed in razorback's
`pyproject.toml`. Harbor finds `SpacedockSolverAgent` by import path
because razorback's package is installed into the same Python
environment as harbor; harbor calls `importlib.import_module` against
the `module.path` half of `import_path` and `getattr`s the `ClassName`
half (`harbor/agents/factory.py:95-133`).

Empirically verified by AC-0.2's probe at
`docs/superpowers/plans/2026-05-19-harbor-entry-point-probe.md`
("Agent dispatch probe" section): an external pip-installed package
with `import_path: probe_agent:ProbeAgent` had its `setup()` and
`run()` invoked by harbor without any entry-point declaration in the
package's `pyproject.toml`.
````

- [ ] **Step 3: Replace §9.2's body**

Use `Edit` to replace §9.2's body. The OLD body to find:

```
`SpacedockSolverAgent` registers via `[project.entry-points."harbor.agents.installed"]`.
This is the documented harbor extension contract. If harbor changes the
entry-point group name or the registration shape, razorback's
`pyproject.toml` updates and the change propagates to users via a
razorback release.
```

The NEW body:

```markdown
`SpacedockSolverAgent` registers via harbor's `AgentConfig.import_path`
dispatch (`harbor/agents/factory.py:95-133`). The dispatch surface is
not setuptools entry-point groups — `rk run` emits a harbor
`JobConfig` with
`agents: [{ import_path: "razorback.agents.spacedock_solver:SpacedockSolverAgent", kwargs: {...} }]`
and harbor's `AgentFactory` resolves the class by Python import. If
harbor changes its `AgentConfig` schema or its factory's resolution
shape, razorback's `rk run` translator updates and the change
propagates to users via a razorback release. No razorback
`pyproject.toml` entry-point declaration exists or is needed; see
§4.5 for the mechanism and AC-0.2's probe doc for empirical
verification.
```

- [ ] **Step 4: Run AC-1's verifier grep**

Per entity AC-1: `grep -ni "entry.point" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` returns no hits after the edit (or only hits inside SUPERSEDED-context citations explicitly marked as such).

Run: `grep -ni "entry.point\|entry_point\|entry point" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: zero hits.

If any hit remains, fix it in the same commit before proceeding. The probe doc itself is **not** edited — it carries the discovery; the spec is what changes.

- [ ] **Step 5: Sanity check — `import_path` appears**

Run: `grep -n "import_path" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: at least three hits — one in §4.5's new body, one in §9.2's new body, possibly one in the cross-reference list.

Run: `grep -n "2026-05-19-harbor-entry-point-probe" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: at least one hit (the citation in §4.5's new body).

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
git commit -m "spec §4.5 + §9.2: replace entry-point-group language with import_path dispatch (ra AC-1)"
```

---

## Task 2 — Benchmark-adapter offline-generator framing (AC-2)

**Files:**
- Modify: `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` §6.1 (pre-edit lines 527-573; line numbers may have drifted after Task 1) — add an offline-generator framing paragraph immediately before the §6.1 example yaml block, naming the contract.

**Pre-condition reads:**
- §6.1's current text and example yaml (lines 527-573 pre-edit).
- Probe doc 1 lines 48-56 ("External benchmark adapters (offline, task-generator pattern)") and lines 161-190 ("Adapter dispatch probe").
- §1.3 lines 58-60 (existing non-goal: "Razorback ships no benchmark adapters") — for consistency check.

- [ ] **Step 1: Locate §6.1**

Run: `grep -n "^### 6.1 Top-level shape" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: one match.

- [ ] **Step 2: Inspect §6.1's current narrative**

Read the lines from `### 6.1 Top-level shape` through the next blank line before the yaml fence. The narrative currently reads (pre-edit lines 521-526):

```
## 6. Spec format

A spec is a YAML file passed to `rk freeze` and then to `harbor run`.
The spec is razorback-extended where razorback adds value; the rest
passes through to harbor.

### 6.1 Top-level shape
```

- [ ] **Step 3: Insert offline-generator framing paragraph after §6.1's header, before the yaml example**

Use `Edit` to insert the following paragraph immediately after the `### 6.1 Top-level shape` header line and before the existing example yaml. The exact insertion point is the blank line between `### 6.1 Top-level shape` and the first line of the example (currently `\`\`\`yaml`).

The paragraph to insert:

```markdown
**Benchmark-block translation contract.** Razorback's `benchmark:`
block names a benchmark by `dataset:` + `tasks:` (or `path:`); `rk
run` translates the block into harbor's `JobConfig.tasks: list[TaskConfig]`
/ `JobConfig.datasets: list[DatasetConfig]` shape before invoking
`harbor run`. Harbor benchmark adapters are **offline task
generators**, not runtime dispatch targets: a harbor adapter is a
standalone package invoked as `uv run <adapter-folder>` that emits
task directories on disk (`<output>/<task-id>/{task.toml,
instruction.md, environment/Dockerfile, tests/test.sh, ...}`); harbor
consumes the emitted directories at run time via `tasks[].path` or
`datasets[].path`. Razorback ships no adapter (per §1.3); the `rk
run` translator's job is to resolve razorback's `benchmark:` block
into a concrete list of task paths the adapter has already emitted on
disk. Empirically verified by AC-0.2's probe at
`docs/superpowers/plans/2026-05-19-harbor-entry-point-probe.md`
("Adapter dispatch probe" section).
```

- [ ] **Step 4: Verify §2 + §3 + §8.4 do not contradict the offline-generator framing**

Run: `grep -n "benchmark adapter\|benchmark.adapter" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: each remaining hit should be either (a) the new §6.1 paragraph, (b) §1.3's non-goal ("Razorback ships no benchmark adapters"), (c) §9.4's references to the adapter as the publisher of `tools_denied` / taint lists (which is documentation, not runtime dispatch — consistent with the offline contract), or (d) §10's LoC table. If any hit implies runtime adapter dispatch (e.g., "harbor loads the benchmark adapter at run time"), fix it in the same commit.

Run: `grep -n "external benchmark adapter entry-point\|adapter entry.point" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: zero hits.

- [ ] **Step 5: Sanity check — citation present**

Run: `grep -n "2026-05-19-harbor-entry-point-probe" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: at least two hits now (one from Task 1's §4.5, one from this task's §6.1).

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
git commit -m "spec §6.1: name harbor benchmark-adapter offline-generator contract (ra AC-2)"
```

---

## Task 3 — `n_attempts` vs `trials` translation comment (AC-3)

**Files:**
- Modify: `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` §6.1 example yaml (the line `trials: 5` at pre-edit line 562) + §6.3 Validation paragraph (pre-edit lines 595-607).

**Pre-condition reads:**
- §6.1 example yaml (lines 527-573 pre-edit), specifically the `trials: 5` and `concurrency: { trials: 4 }` lines.
- §6.3 Validation paragraph (lines 595-607 pre-edit).
- Probe doc 2 line 79 (the `trials: int` vs `n_attempts` gap row in the field-by-field gap table) and line 99 (`n_attempts=1, # NOT spec.trials — open question`) and line 106 (the open question filed in the probe summary).

- [ ] **Step 1: Locate §6.1's `trials:` line and §6.3's body**

Run: `grep -n "^trials:\|^### 6.3 Validation" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: two matches — the `trials: 5` line in §6.1 example, and the §6.3 header.

- [ ] **Step 2: Add the translation comment to §6.1's `trials: 5` example line**

Use `Edit` to append an inline comment to the `trials: 5` line in §6.1's example yaml. The OLD line:

```
trials: 5
```

The NEW line:

```
trials: 5                       # razorback-internal field; rk run translates
                                # to harbor's JobConfig by replicating tasks[]
                                # entries (NOT harbor's n_attempts, which is
                                # per-trial retry count — see §6.3)
```

(Match indentation to the existing example yaml — the line sits at column 0 inside the fenced block.)

- [ ] **Step 3: Append a `trials` → harbor translation paragraph to §6.3**

Use `Edit` to append a paragraph at the end of §6.3 (after the existing line "Other blocks (`benchmark`, `environment`, `trials`, `concurrency`) pass through to harbor; harbor validates them at `harbor run` time." but before the `---` separator that ends the section). The paragraph to append:

```markdown
**`trials` → harbor field-name translation.** Razorback's `trials: int`
field means "number of independent trials per task" — N executions of
the same task with fresh per-trial state. Harbor's `JobConfig.n_attempts:
int` (`harbor/models/job/config.py:244-302`) is **not** the same
concept — it is the per-trial retry count after agent failure.
`rk run`'s translator implements razorback's `trials: N` semantics by
duplicating `JobConfig.tasks[]` entries N times (or by invoking
`harbor run` N times against a single-pass JobConfig, whichever harbor
supports more cleanly at the pinned version); it does **not** set
`JobConfig.n_attempts = spec.trials`. The frozen spec keeps razorback's
`trials:` field name; harbor's `JobConfig` carries `n_attempts:`
unchanged. Verified by AC-0.3/4/6's source probe at
`docs/superpowers/plans/2026-05-19-harbor-source-probe.md`
("Field-by-field gap" table, `trials: int` → `n_attempts: int` row,
and the "open question" filed in the probe summary).
```

- [ ] **Step 4: Run AC-3's verifier (mechanical)**

Per the entity AC-3 verifier clause: "spec examples that translate to JobConfig field names match harbor's actual field names (or carry an explicit `# razorback-internal naming; translates to harbor's n_attempts` comment)."

Run: `grep -nB1 -A4 "^trials: 5" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: the comment from Step 2 appears next to the `trials: 5` line.

Run: `grep -n "n_attempts" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: at least two hits — the inline comment in §6.1 and the §6.3 paragraph.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
git commit -m "spec §6.1 + §6.3: name trials vs n_attempts translation (ra AC-3)"
```

---

## Task 4 — Observers translation rule (AC-4)

**Files:**
- Modify: `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` §6.3 Validation section (immediately after Task 3's added paragraph; same section).

**Pre-condition reads:**
- §6.3 Validation paragraph in its post-Task-3 state.
- Probe doc 2 line 80 (the observers gap row: razorback's `jsonl`/`stdout` observers map to harbor's publisher / event log; gap to confirm whether razorback subscribes to harbor's event stream post-`harbor run`) and line 266 (the observers open question in the probe summary).
- The current spec's only mention of observers is in §6's schema (the spec carries a `provenance` block but no first-class observer block in the v2 spec text — the observer block lives in razorback's pydantic schema at `src/razorback/spec/schema.py:135-143` per probe doc 2 line 58). The translation rule names the runtime behavior; it does not introduce an observer block to the v2 spec.

- [ ] **Step 1: Locate the post-Task-3 §6.3 paragraph for the append point**

Run: `grep -n "trials. → harbor field-name translation" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: one match (the paragraph added in Task 3 Step 3).

- [ ] **Step 2: Append the observers translation paragraph**

Use `Edit` to append a sibling paragraph immediately after the Task-3 paragraph, before the `---` separator that closes §6.3. The paragraph to append:

```markdown
**`observers` → harbor event-stream translation.** Razorback's
`observers: list[ObserverBlock]` (kinds `jsonl`, `stdout`) has no slot
in harbor's `JobConfig` (`harbor/models/job/config.py:244-302`).
Razorback's observers translate by **consuming harbor's per-job event
stream** post-`harbor run`: harbor's publisher infrastructure
(`harbor/publisher/`) emits trial events to a per-job event log inside
the run-dir; razorback's `jsonl` observer reifies the events to a
named JSONL file, and the `stdout` observer prints a summary line per
trial. The translation is **read-side, not injected into `JobConfig`**
— razorback's observer blocks stay in `spec.frozen.yaml` for
provenance and are interpreted by `rk run`'s post-invocation reader,
not by harbor. Verified by AC-0.3/4/6's source probe at
`docs/superpowers/plans/2026-05-19-harbor-source-probe.md`
("Field-by-field gap" table, `observers` row, and the observers open
question in the probe summary).
```

- [ ] **Step 3: Run AC-4's verifier**

Per the entity AC-4 verifier clause: "a paragraph in the spec § that defines the observers translation rule, citing the probe doc."

Run: `grep -n "observers. → harbor event-stream translation\|observers" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: at least one hit on the new paragraph header phrase.

Run: `grep -n "2026-05-19-harbor-source-probe" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: at least two hits — one from Task 3's §6.3 paragraph, one from this task's §6.3 paragraph.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
git commit -m "spec §6.3: name observers → harbor event-stream translation (ra AC-4)"
```

---

## Self-Review (run after all tasks drafted, before sending the stage report)

**1. Spec coverage.** Each non-superseded AC maps 1:1 to a task. AC-1 → Task 1 (§4.5 + §9.2). AC-2 → Task 2 (§6.1 paragraph). AC-3 → Task 3 (§6.1 inline comment + §6.3 paragraph). AC-4 → Task 4 (§6.3 sibling paragraph). AC-5 is dropped per the supersession block; the implementation stage's report marks it SKIPPED with the named rationale.

**2. Verifier-clause coverage.** AC-1's verifier (`grep -ni "entry.point" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` returns no hits) is hit by Task 1 Step 4. AC-2's verifier ("spec §2 + §3 + §8.4 reads consistent with the entry-point-probe doc's Implications section") is hit by Task 2 Step 4's two greps + the framing paragraph in §6.1. AC-3's verifier ("spec examples carry the translation comment") is hit by Task 3 Step 4's two greps. AC-4's verifier ("a paragraph defines the translation rule, citing the probe") is hit by Task 4 Step 3's two greps.

**3. Probe-doc citation count.** After all four tasks land, the spec contains at least:
- Two citations of `2026-05-19-harbor-entry-point-probe.md` (Task 1 §4.5, Task 2 §6.1).
- Two citations of `2026-05-19-harbor-source-probe.md` (Task 3 §6.3, Task 4 §6.3).
This is the citation pattern AC-1 / AC-2 / AC-3 / AC-4's verifier clauses require.

**4. b5 supersession.** AC-5 is dropped, not re-derived. The supersession block at the top of this plan names `b5f4zn4vd74yvrmpn207qrwk` as the entity whose AC-2 makes ra's AC-5 obsolete. The implementation stage's report explicitly marks AC-5 SKIPPED.

**5. No edits to §7.1.** This plan does **not** touch §7.1 — that section is owned by b5's plan (b5 Task 2 lands the layout block + path-literal rewrite simultaneously). If b5's implementation lands first (which it should, since b5 is also running its implementation concurrently per the dispatch context), ra's implementation sees a §7.1 that already reads `_razorback/freeze/<sealed_hash>/`; if b5 lands second, ra sees the pre-b5 §7.1 — either way ra does not edit §7.1.

**6. Concurrency-safe with b5.** b5 edits §4.4 + §7.1 + §3.1; ra edits §4.5 + §6.1 + §6.3 + §9.2. The two plans touch disjoint sections, so concurrent or sequential execution produces the same final spec text. The implementation stage worker MUST `grep -n "^### N.N"` before each Edit to confirm section anchors (since line numbers drift with b5's edits), but the section bodies do not overlap.

**7. No code, no test, no harbor-side change.** This entity ships spec edits only. The Phase 1 (rk run translator) and Phase 3 (SpacedockSolverAgent v2) implementations consume the spec edits but are out of scope here. The captain decisions (D2/D5) section above is the durable record for downstream entity authors.

## Execution Handoff

Plan complete and saved to `docs/razorback-implementation/plans/spec-corrections-from-phase0-probes.md`. Implementation stage is four `Edit` calls + greps + four commits, all inside one markdown file; subagent-driven dispatch is overkill. Recommend **inline execution** at implementation stage using `superpowers:executing-plans` (single fresh dispatch executes all four tasks sequentially with the greps as the checkpoint between tasks, and re-greps section headers before each Edit to handle line drift from b5's concurrent edits).
