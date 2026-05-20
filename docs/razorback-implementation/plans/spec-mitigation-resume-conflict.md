# Spec mitigation for harbor jobs resume conflict (§4.4) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Edit the v2 spec at `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` so §4.4, §7.1, and §3.1/§8.1 accurately describe how `SpacedockSolverAgent` survives `harbor jobs resume`. The spec edits are the entire deliverable for stages `plan → implementation → validation`; no code lands under this entity. AC-4 is a forward-reference acknowledgement that already exists in the Phase 3 entity and is verified rather than authored here.

**Architecture:** The mitigation has one architectural idea — the freeze tree lives in a **razorback-owned** sibling directory outside harbor's per-trial scratch zone, keyed by `sealed_hash` rather than `trial_name`. The probe at `docs/superpowers/plans/2026-05-19-harbor-resume-probe.md` (commit `1569853`) established empirically that harbor's `_maybe_init_existing_job` (`harbor/job.py:192-228`) rmtree's any trial directory missing `result.json` and regenerates `trial_name` for re-executed trials. Razorback's §4.4 freeze contract assumes `agent_freeze/` survives across `harbor jobs resume`; under harbor's actual behavior, the freeze tree is destroyed when its parent trial is incomplete at resume time. The fix is "Strategy 1" from the probe's recommendation: mirror the freeze tree to `<harbor-run-dir>/_razorback/freeze/<sealed_hash>/` at every stage commit. The `_razorback/` directory is a sibling of harbor's `trials/`, never touched by harbor's resume logic, addressable by the `sealed_hash` so the same content survives `trial_name` regeneration.

**Tech Stack:** Markdown only. No Python, no harbor surfaces. The implementation stage runs `Edit` against three spec sections and re-greps to confirm AC-1 and AC-2 verifier clauses pass. The validation stage re-reads §4.4 + §7.1 + §3.1 cross-checked against the probe doc and re-runs the same greps.

**Source of truth:** the probe doc at `/Users/clkao/git/razorback/docs/superpowers/plans/2026-05-19-harbor-resume-probe.md` (commit `1569853`) is the empirical evidence. The 4 ACs live in the entity body at `/Users/clkao/git/razorback/docs/razorback-implementation/spec-mitigation-resume-conflict.md`. The v2 spec being edited is at `/Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`; the line ranges of the three target sections at plan time are §3.1 (lines 156-170), §4.4 (lines 373-396), §7.1 (lines 616-634). Line numbers will drift during the edits; the section anchors do not.

## Supersession of `ra` AC-5

The sibling entity `spec-corrections-from-phase0-probes.md` ("ra") carries an AC-5 that proposes:

> Spec §7.1 path literal `logs_dir/agent_freeze` corrected to `trials/<name>/agent/agent_freeze`.

That correction is based on AC-0.3/4/6 follow-up #3 (harbor writes per-trial artifacts under `trials/<name>/agent/`, not directly under `logs_dir/`). It is **superseded by this entity's AC-2**: AC-0.5's probe showed that the freeze tree cannot live under `trials/<name>/` at all — that directory is rmtree'd on resume, taking `agent_freeze/` with it. The correct location is neither `logs_dir/agent_freeze` (ra's AC-5 input) nor `trials/<name>/agent/agent_freeze` (ra's AC-5 proposed output); it is `_razorback/freeze/<sealed_hash>/` (this entity's AC-2). When `ra` reaches its plan stage, AC-5 must be dropped — its verification grep (`grep -n "logs_dir/agent_freeze" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` returns zero hits) will still pass once **this entity's** AC-2 lands, but for a different reason than ra's plan would document. The ra plan-stage worker should reconcile by marking AC-5 SKIPPED with rationale "superseded by `b5f4zn4vd74yvrmpn207qrwk` AC-2; the §7.1 path literal moves outside `trials/<name>/` entirely, not to a subpath of it".

## Sealed_hash-keyed external freeze design (load-bearing for Phase 3)

Phase 3 (`phase3-spacedock-solver-v2.md`, id `d5gxb8p7eea6nk85nja5zmbr`) consumes this section as a pre-condition. The constants and contract below must be specific enough that Phase 3's implementation reads kwargs/paths from here, not re-derives them.

### Location convention

```
<harbor-run-dir>/                       # harbor owns this directory
├── trials/<task>-NNNN__<uuid7>/        # harbor rmtree's this on resume if no result.json
│   └── agent/                          # razorback never writes here
├── spec.frozen.yaml                    # razorback (rk freeze) — survives resume
├── provenance.yaml                     # razorback (rk freeze) — survives resume
└── _razorback/                         # razorback's sibling directory, harbor never touches
    └── freeze/
        └── <sealed_hash>/              # one freeze tree per sealed identity
            ├── .git/                   # workspace snapshots per stage
            ├── phase_stats.json        # per-stage tokens/cost/wallclock
            └── sealed_hash.txt         # the sealed_hash literal (matches dir name)
```

`<sealed_hash>` is the first 32 hex chars of the sha256 over the six sealed inputs defined in spec §4.3 + §8.4: `(model, sampling, solver_workflow content hash, prompt content hashes, spacedock skill version, harbor agent kwargs)`. Phase 3's `compute_sealed_hash` (per `phase3-spacedock-solver-v2.md` AC-2) produces this value; this entity does not redefine it.

`<harbor-run-dir>` is the directory harbor produces for the job (i.e., `jobs_dir / job_name`). It is **the same directory harbor knows as `self.job_dir`** in `harbor/job.py`. Razorback's `_razorback/` lives at the same depth as harbor's `trials/`. Harbor's `_maybe_init_existing_job` (job.py:192-228) iterates `self.job_dir`'s subdirs and rmtree's incomplete trials; it does not enumerate or touch the `_razorback/` sibling. (Verified by the probe doc's "Post-resume on-disk state" section: any directory outside `trials/<name>__<uuid>/` is untouched by the rmtree loop.)

### Lifecycle

| When | What |
|------|------|
| **First stage of first run** | `SpacedockSolverAgent.setup` computes `sealed_hash`, creates `<run-dir>/_razorback/freeze/<sealed_hash>/`, writes `sealed_hash.txt`, `git init` inside `.git/`. |
| **Every stage commit** | The workflow's freeze mod writes the workspace tarball / git commit into `_razorback/freeze/<sealed_hash>/.git/`; appends the stage's stats row to `phase_stats.json`. |
| **`harbor jobs resume` on an incomplete trial** | Harbor rmtree's `trials/<task>-NNNN__<old_uuid>/`. `_razorback/freeze/<sealed_hash>/` is **not** under `trials/` and is **not** touched. The re-executed trial gets a new `trial_name` (e.g., `<task>-NNNN__<new_uuid>`); razorback's setup recomputes the **same** `sealed_hash` from the same sealed inputs in `spec.frozen.yaml` (which also survives resume), locates the existing freeze tree by hash, and restores the workspace from `.git/`. |
| **`rk run` with `resume_from_freeze: <path>`** | The cross-job resume case (spec §4 line 363). Razorback reads `<path>/sealed_hash.txt`, refuses on mismatch against the new spec's recomputed `sealed_hash` (`SeedMismatchError`, exit 20), otherwise restores the workspace from `<path>/.git/`. |
| **Trial reaches `done`** | The freeze tree stays in place; it is the durable artifact downstream consumers (`rk diff`, an experiment-workflow analyze stage) read via `phase_stats.json` and `sealed_hash.txt`. |
| **GC** | Out of scope for this entity and Phase 3. The freeze tree is owned by the run-dir; if the operator wants to reclaim disk, they delete the entire run-dir or the `_razorback/freeze/` subtree manually. A `rk runs gc` subcommand is a follow-on, not a v2-shipping requirement. (The spec edit names "no automatic GC; durable across resumes" so Phase 3 does not invent a GC contract.) |

### Contract between `SpacedockSolverAgent` and the external freeze tree

Phase 3's `SpacedockSolverAgent` v2 (`src/razorback/agents/spacedock_solver_v2.py`) MUST:

1. Compute `sealed_hash` in `__init__` per §4.3 + §8.4's six inputs.
2. In `setup(env)`, resolve the freeze dir as `Path(self.logs_dir).parent.parent / "_razorback" / "freeze" / self.sealed_hash`. (Rationale: harbor's `logs_dir` for a trial is `<run-dir>/trials/<trial_name>/logs/` or similar; the two `.parent` calls back out to the run-dir. The exact `logs_dir` shape is named in spec §7.1 and Phase 3 must verify against harbor's actual layout at implementation time — but the **destination root** is `<run-dir>/_razorback/freeze/<sealed_hash>/`, not a path keyed off `trial_name` or `logs_dir`.)
3. Create the freeze dir if it does not exist; `git init` inside `.git/` on first stage.
4. Write `sealed_hash.txt` with the literal hash on first stage; on subsequent stages, read it and `SeedMismatchError` (exit 20) on mismatch — same refusal contract as today's `agent_freeze/`, just at the new location.
5. The freeze dir survives `harbor jobs resume`; the trial's `agent/` subtree does **not**. Razorback never writes inside `trials/<name>/agent/`.

The workflow's freeze mod (Phase 3 out-of-scope, lands with the autoresearch loop per spec §5.2) writes into the same freeze dir using the path the class exposes via env or kwarg.

### Why `sealed_hash` and not `trial_name`

Harbor's `_init_remaining_trial_configs` (`harbor/job.py:263-293`) regenerates `trial_name` for re-executed trials (`f"{task_name[:32]}__{ShortUUID().random(length=7)}"`, `harbor/models/trial/config.py:213-222`). The probe captured this verbatim: `hello-world__qRkNdkY` became `hello-world__wMGYfz7` across one resume. Any razorback state keyed by `trial_name` would be unaddressable after resume even if it survived rmtree. `sealed_hash` is computed from sealed inputs (model, sampling, solver_workflow content, prompts, skill version, agent kwargs) that **do not change** between the initial run and the resume — `spec.frozen.yaml` is the same file, and the resume rewrites neither the spec nor the provenance. Same sealed inputs → same `sealed_hash` → addressable by the resume's new agent instance.

## `rk run` jobs_dir / `-p <path>` alignment rule (AC-3)

The probe doc names a second finding: `harbor jobs resume -p <path>` reads `<path>/config.json` for the JobConfig but then uses **the config's `jobs_dir`**, not the `-p` argument, to locate trial subdirs (`harbor/cli/jobs.py:1444-1477`). If the config's `jobs_dir` and the on-disk location of `-p <path>` disagree, the resume silently scans a different directory than the operator intended; the probe's first (invalid) attempt hit exactly this.

`rk run`'s emit logic must canonicalize the spec's `jobs_dir` field so that:

- When `rk run <frozen-spec.yaml>` invokes harbor, the spec's `jobs_dir` is the **absolute, resolved path** of the directory the run-dir physically lives in.
- An operator who later runs `harbor jobs resume -p <razorback-emitted-run-dir>` gets a resume that scans the same directory the `-p` argument points at — because `config.jobs_dir / config.job_name == realpath(-p argument)`.

The spec §3.1 design-rules list (or §8.1's `rk run` description, whichever is more specific to the emit logic) names this rule: "razorback's emit canonicalizes `jobs_dir` to the absolute resolved path before invoking harbor, so `harbor jobs resume -p <run-dir>` and `harbor jobs resume` against the config resolve to the same directory." Implementation in Phase 1 (`phase1-rk-run-v2-wrapper.md`) consumes this rule.

## AC ↔ task map (1:1)

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-1 — Spec §4.4 names the conflict and the mitigation | §4.4 (lines 373-396 pre-edit); probe doc lines 127-176 ("Conflict analysis vs spec §4.4") and lines 178-211 (Recommendation) | Task 1 (riskiest contract — the §4.4 narrative anchors §7.1's path literal and Phase 3's class contract) |
| AC-2 — Spec §7.1 relocates `agent_freeze/` outside harbor's per-trial path | §7.1 (lines 616-634 pre-edit); probe doc lines 37-50 ("Harbor's resume algorithm" → rmtree) | Task 2 |
| AC-3 — Spec §3.1 / §8 documents `rk run`'s jobs_dir / `-p <path>` alignment rule | §3.1 (lines 156-170 pre-edit) or §8.1 (lines 678-698 pre-edit); probe doc lines 213-219 ("Also recommended (independent)") | Task 3 |
| AC-4 — Phase 3 plan stage acknowledges this mitigation as a load-bearing constraint | `phase3-spacedock-solver-v2.md` body lines 29-35 (already filed: "Phase 3 is load-bearing on `b5` spec-mitigation-resume-conflict...") and lines 156-162 ("Depends on: b5") | Task 4 (verification only — no authoring) |

**Riskiest contract first.** Task 1 lands §4.4's narrative because §7.1's path literal (Task 2) and Phase 3's class contract (consumed via AC-4) both inherit the conceptual framing introduced in §4.4. If §4.4's words are wrong about what harbor does or what the mitigation is, §7.1 inherits the error and Phase 3 implements against an incorrect contract. Per CL's "Validating new mechanisms" rule, the riskiest contract (the narrative that downstream sections cite) lands first.

---

## Task 1 — Edit §4.4 to name the conflict and the mitigation (AC-1)

**Files:**
- Modify: `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` §4.4 (pre-edit lines 373-396)

**Pre-condition reads (mandatory, do not skip):**
- `/Users/clkao/git/razorback/docs/superpowers/plans/2026-05-19-harbor-resume-probe.md` end-to-end. Note especially lines 37-50 (rmtree algorithm), lines 56-62 (trial_name regeneration), lines 127-176 (Conflict analysis), and lines 178-211 (Recommendation).
- The current §4.4 of `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` (lines 373-396).
- `phase3-spacedock-solver-v2.md` lines 29-35 to confirm the framing Phase 3 already cites.

- [ ] **Step 1: Locate §4.4 in the spec**

Run: `grep -n "^### 4.4" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: one match returning the §4.4 header line.

- [ ] **Step 2: Insert "Harbor-resume interaction" subsection after the existing §4.4 body, before §4.5**

Use `Edit` to append the following block immediately after §4.4's last paragraph (currently ending with "...covers most of the picture.") and before the `### 4.5 Registration with harbor` header:

```markdown
**Harbor-resume interaction.** `harbor jobs resume`
(`harbor/cli/jobs.py:1361-1430` → `harbor/job.py:_maybe_init_existing_job:192-228`)
rmtree's any trial directory that lacks `result.json` and re-runs the
trial under a freshly randomised `trial_name`
(`harbor/models/trial/config.py:213-222`). Razorback's freeze tree
therefore cannot live inside harbor's per-trial scratch zone: if a
`SpacedockSolverAgent` halts mid-trial (process killed, container
evicted, `harbor run` Ctrl-C'd) before `result.json` is written,
harbor's resume destroys the trial directory and every razorback file
under it, and the re-executed trial gets a new `trial_name` that
would not match any `trial_name`-keyed sibling store.

The mitigation: razorback writes the freeze tree to a sibling
directory **outside harbor's per-trial scratch zone**, keyed by
`sealed_hash` rather than `trial_name`. The freeze location is
`<harbor-run-dir>/_razorback/freeze/<sealed_hash>/` (see §7.1).
`sealed_hash` is the §4.3 + §8.4 sealed-input hash, identical across
the initial run and any subsequent `harbor jobs resume` because the
sealed inputs (model, sampling, solver_workflow content, prompts,
spacedock skill version, harbor agent kwargs) are read from
`spec.frozen.yaml`, which itself survives resume.

Consequences:

- **In-place resume of a halted trial is supported.** The re-executed
  trial recomputes `sealed_hash` from the unchanged `spec.frozen.yaml`,
  locates the existing freeze tree at the same path, and restores the
  workspace from its embedded `.git/` before invoking the inner
  runtime.
- **Cross-job `resume_from_freeze` is supported the same way.** The
  cross-job resume reads `<path>/sealed_hash.txt`, refuses on
  mismatch (`SeedMismatchError`, exit 20), and restores from
  `<path>/.git/` otherwise. The two resume mechanisms share the same
  freeze layout.
- **No partial-credit recovery on rmtree'd stages remains acceptable.**
  Stage commits are written to `_razorback/freeze/<sealed_hash>/`
  immediately as the freeze mod produces them, so per-stage cost
  attribution survives the rmtree even though the trial's `agent/`
  subtree does not.

Empirically verified by AC-0.5's probe at
`docs/superpowers/plans/2026-05-19-harbor-resume-probe.md`
(commit `1569853`).
```

- [ ] **Step 3: Run AC-1's verifier grep**

Run: `grep -n "sealed_hash" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: at least one match inside §4.4's new subsection.

Run: `grep -n "outside harbor's per-trial scratch zone" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: at least one match inside §4.4's new subsection.

Run: `grep -n "2026-05-19-harbor-resume-probe" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: at least one match (the citation in §4.4's new subsection).

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
git commit -m "spec §4.4: name harbor-resume rmtree + sealed_hash-keyed freeze mitigation (b5 AC-1)"
```

---

## Task 2 — Edit §7.1 to relocate `agent_freeze/` outside harbor's per-trial path (AC-2)

**Files:**
- Modify: `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` §7.1 (pre-edit lines 616-634; line numbers may have drifted after Task 1)

**Pre-condition reads:**
- §7.1's current layout block (lines 616-634 pre-edit).
- The "Location convention" section of this plan above (the layout tree and the rationale for keying by `sealed_hash`).

- [ ] **Step 1: Locate §7.1's layout block**

Run: `grep -n "^### 7.1 Layout" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: one match.

- [ ] **Step 2: Replace the §7.1 layout block**

Use `Edit` to replace the existing §7.1 layout block with the corrected version. The OLD block is:

```
<harbor-run-dir>/
├── (harbor's standard run-dir layout)
├── spec.frozen.yaml              # razorback writes at `rk freeze`
├── provenance.yaml               # razorback writes at `rk freeze`
└── trials/<task>-NNNN/
    ├── (harbor's standard trial layout)
    └── logs_dir/
        └── agent_freeze/         # SpacedockSolverAgent contract
            ├── .git/             # workspace snapshots per stage (mods write)
            ├── phase_stats.json  # per-stage tokens/cost/wallclock (mods write)
            └── sealed_hash.txt   # sealed-input hash (class writes at first stage)
```

The NEW block is:

````markdown
```
<harbor-run-dir>/
├── (harbor's standard run-dir layout)
├── trials/<task>-NNNN__<uuid7>/  # harbor owns; rmtree'd on resume if incomplete
│   └── (harbor's standard trial layout — razorback never writes here)
├── spec.frozen.yaml              # razorback writes at `rk freeze`
├── provenance.yaml               # razorback writes at `rk freeze`
└── _razorback/                   # razorback's sibling directory; harbor never touches
    └── freeze/
        └── <sealed_hash>/        # SpacedockSolverAgent contract; survives `harbor jobs resume`
            ├── .git/             # workspace snapshots per stage (mods write)
            ├── phase_stats.json  # per-stage tokens/cost/wallclock (mods write)
            └── sealed_hash.txt   # sealed-input hash (class writes at first stage)
```

`_razorback/freeze/<sealed_hash>/` is the only razorback-owned subtree
under harbor's run-dir layout. It lives **outside** harbor's
`trials/<name>/` so that `harbor jobs resume`'s rmtree of incomplete
trials (`harbor/job.py:_maybe_init_existing_job:192-228`) cannot
destroy the freeze tree. The directory is keyed by `sealed_hash` (the
§4.3 + §8.4 sealed-input hash) rather than by `trial_name`, because
`harbor jobs resume` regenerates `trial_name` for re-executed trials
(`harbor/models/trial/config.py:213-222`); `sealed_hash` is derived
from `spec.frozen.yaml`, which itself survives resume, so the same
freeze tree is addressable by the re-executed agent instance. See
§4.4's "Harbor-resume interaction" subsection for the empirical
basis (AC-0.5 probe at
`docs/superpowers/plans/2026-05-19-harbor-resume-probe.md`,
commit `1569853`). Razorback does not modify harbor's `trials/`,
`agent/`, `verifier/`, or `artifacts/` subtrees.
````

Note the surrounding paragraph (the one starting "`logs_dir/agent_freeze/` is the only razorback-owned subtree..." in the pre-edit version) is **replaced** by the new paragraph above; it must not be left in the file.

- [ ] **Step 3: Run AC-2's verifier greps**

Run: `grep -n "agent_freeze" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: the only hits should be the new `_razorback/freeze/<sealed_hash>/` block and any back-references that explicitly cite "the former `agent_freeze/` layout" — there should be **no** remaining `trials/<name>/agent/agent_freeze` or `logs_dir/agent_freeze` strings.

Run: `grep -n "trials/<.*>/.*agent_freeze\|trials/<.*>/agent/agent_freeze\|logs_dir/agent_freeze" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: zero hits.

Run: `grep -n "_razorback/freeze" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: at least one hit inside §7.1 and one back-reference inside §4.4.

- [ ] **Step 4: Sweep §4 + §7 + §8 for any remaining `agent_freeze` path strings keyed off trial_name or logs_dir**

Run: `grep -n "agent_freeze" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md | grep -v "_razorback/freeze"`
Expected output: each remaining hit, if any, must be either a back-reference to "the former `agent_freeze/` layout" for historical context, or a path under `_razorback/freeze/<sealed_hash>/`. If any hit is a path like `logs_dir/agent_freeze` or `trials/.../agent_freeze` outside `_razorback/`, fix it in the same commit.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
git commit -m "spec §7.1: relocate freeze tree to _razorback/freeze/<sealed_hash>/ (b5 AC-2)"
```

---

## Task 3 — Document `rk run`'s jobs_dir / `-p <path>` alignment rule (AC-3)

**Files:**
- Modify: `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` §3.1 design rules and §8.1 `rk run` description

**Pre-condition reads:**
- §3.1 (pre-edit lines 156-170): the design-rules bullet list for the CLI surface.
- §8.1 (pre-edit lines 678-698): `rk run`'s pass-through description.
- Probe doc lines 17-26 (the `-p <job-dir>` vs config-`jobs_dir` mismatch) and lines 213-219 (the alignment recommendation).

- [ ] **Step 1: Add the canonicalization rule to §3.1's design-rules bullet list**

Use `Edit` to add a new bullet to §3.1's bullet list, immediately after the bullet starting "Stable exit codes. ...". The new bullet:

```markdown
- Path canonicalization. Commands that emit a spec for harbor to
  consume (`rk run`, the freeze writer) resolve `jobs_dir` to an
  absolute, symlink-resolved path before passing it to harbor. This
  ensures that `harbor jobs resume -p <run-dir>` and `harbor jobs
  resume` against the config resolve to the same directory; harbor's
  resume reads the config's `jobs_dir` to enumerate trial subdirs
  (`harbor/cli/jobs.py:1444-1477`), and a mismatch between the `-p`
  argument's on-disk location and the config's `jobs_dir` causes the
  resume to silently scan a different directory than the operator
  intended (see AC-0.5 probe at
  `docs/superpowers/plans/2026-05-19-harbor-resume-probe.md`,
  commit `1569853`, "Caveat from the first (invalid) attempt").
```

- [ ] **Step 2: Add the same canonicalization rule to §8.1's `rk run` description**

Use `Edit` to add a new numbered step to §8.1's numbered list, between the existing steps 1 (Reads the frozen spec) and 2 (Re-resolves the model alias). Re-number subsequent steps accordingly. The new step:

```markdown
2. Canonicalizes the frozen spec's `jobs_dir` to an absolute,
   symlink-resolved path (`Path(jobs_dir).expanduser().resolve()`)
   before invoking harbor. This keeps `harbor jobs resume -p
   <run-dir>` and `harbor jobs resume` against the config in
   agreement on which directory to scan. See §3.1 design-rule on
   path canonicalization.
```

- [ ] **Step 3: Run AC-3's verifier**

Per the entity AC-3 verifier clause: "spec § that defines `rk run`'s emit semantics names the canonicalization rule; the probe doc is cited."

Run: `grep -n "canonicaliz" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: at least two hits — one in §3.1 and one in §8.1.

Run: `grep -n "2026-05-19-harbor-resume-probe" /Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Expected: at least three hits total now (one from §4.4 via Task 1, one from §7.1 via Task 2, one from §3.1 via this task) — the probe doc is cited from all three sections that this entity touches.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
git commit -m "spec §3.1 + §8.1: rk run canonicalizes jobs_dir before harbor invocation (b5 AC-3)"
```

---

## Task 4 — Verify Phase 3's pre-existing acknowledgement of this entity as a load-bearing constraint (AC-4)

**Files:**
- Read-only verification: `docs/razorback-implementation/phase3-spacedock-solver-v2.md`

This task does **not** edit Phase 3's entity. The Phase 3 entity is in `backlog`; its frontmatter and body are owned by the FO and by Phase 3's own plan-stage worker (when that entity is greenlit). The acknowledgement is already filed (lines 29-35 and lines 156-162 of `phase3-spacedock-solver-v2.md`); this task verifies it is present and well-formed.

- [ ] **Step 1: Verify Phase 3's body cites this entity's id**

Run: `grep -n "b5f4zn4vd74yvrmpn207qrwk\|b5 spec-mitigation-resume-conflict\|spec-mitigation-resume-conflict" /Users/clkao/git/razorback/docs/razorback-implementation/phase3-spacedock-solver-v2.md`
Expected: at least two matches (one in the Problem section's load-bearing paragraph, one in the Depends on section).

- [ ] **Step 2: Verify the citation names the sealed_hash-keyed external freeze design as a pre-condition (not a discovery)**

Run: `grep -n "load-bearing\|pre-condition\|outside harbor's per-trial scratch zone\|sealed_hash-keyed external freeze" /Users/clkao/git/razorback/docs/razorback-implementation/phase3-spacedock-solver-v2.md`
Expected: at least one match in Phase 3's Problem section (currently "Phase 3 is load-bearing on `b5` spec-mitigation-resume-conflict: the freeze tree is sealed_hash-keyed and mirrored outside harbor's per-trial scratch zone...") and at least one in the AC-5 verifier clause referencing `b5`.

- [ ] **Step 3: No commit (verification only)**

If both greps return the expected hits, AC-4 is verified. If either is missing, raise to the FO via `SendMessage(to="team-lead")` — Phase 3's body needs an amendment before this entity can pass AC-4, and that amendment is owned by the FO on main, not by this plan-stage worker.

---

## Self-Review (run after all tasks drafted, before sending the stage report)

**1. Spec coverage.** Each AC maps 1:1 to a task. AC-1 → Task 1 (§4.4). AC-2 → Task 2 (§7.1). AC-3 → Task 3 (§3.1 + §8.1). AC-4 → Task 4 (verification of Phase 3 body).

**2. Verifier-clause coverage.** AC-1's verifier ("spec §4.4 contains the phrases `sealed_hash` and `outside harbor's per-trial scratch zone` ... the probe doc is cited") is hit by Task 1 Step 3's three greps. AC-2's verifier (`grep -n "agent_freeze" ... shows the new location; no remaining references to agent_freeze/ under a trials/ subpath`) is hit by Task 2 Step 3 + Step 4's greps. AC-3's verifier ("spec § that defines `rk run`'s emit semantics names the canonicalization rule; the probe doc is cited") is hit by Task 3 Step 3's two greps. AC-4's verifier (Phase 3's body cites `b5f4zn4vd74yvrmpn207qrwk` as a referenced dependency) is hit by Task 4 Step 1's grep.

**3. Probe-doc citation count.** After all three spec-edit tasks land, the spec contains at least three citations of `2026-05-19-harbor-resume-probe.md` (in §4.4, §7.1, and §3.1). This is the citation rule from AC-1 / AC-2 / AC-3's verifier clauses.

**4. No code, no test, no harbor-side change.** This entity ships spec edits only. Implementation in Phase 3 (sealed_hash-keyed external freeze layout) and Phase 1 (`rk run` canonicalization) consume the spec edits but are out of scope here.

**5. ra AC-5 supersession.** Named at the top of this plan in the "Supersession of `ra` AC-5" section. When ra reaches its plan stage, that worker marks AC-5 SKIPPED with the rationale spelled out there.

**6. Forward-reference dependency.** AC-4 verifies that Phase 3's entity already names this entity's id; no authoring under this entity. If Phase 3's body needs amendment, escalate to FO rather than editing Phase 3's body from this plan.

## Execution Handoff

Plan complete and saved to `docs/razorback-implementation/plans/spec-mitigation-resume-conflict.md`. Implementation stage is small (three `Edit` calls + four greps + three commits) and contains no code; subagent-driven dispatch is overkill. Recommend **inline execution** at implementation stage using `superpowers:executing-plans` (single fresh dispatch executes all three tasks sequentially with the greps as the checkpoint between tasks).
