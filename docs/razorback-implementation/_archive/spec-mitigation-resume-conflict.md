---
id: b5f4zn4vd74yvrmpn207qrwk
title: Spec mitigation for harbor jobs resume conflict (§4.4)
status: done
source: AC-0.5 probe finding (Phase 0 reconciliation plan)
started: 2026-05-20T05:58:15Z
completed: 2026-05-20T06:19:16Z
verdict: PASSED
score: 0.95
worktree: 
issue:
pr:
mod-block:
archived: 2026-05-20T06:19:16Z
---

## Problem

Phase 0's AC-0.5 probe of `harbor jobs resume` returned verdict **CONFLICT**. Harbor's resume path `rmtree`s any trial directory missing `result.json` (harbor's `job.py:220-221`) and re-runs the trial under a fresh random `trial_name`. Razorback's spec §4.4 halt-resume contract assumes `agent_freeze/` survives across resumes — under harbor's actual behavior, the freeze tree is destroyed when its parent trial is incomplete at resume time. The contract does not hold.

This is a real architectural correction, not a wording fix. The mitigation: razorback's `SpacedockSolverAgent` must mirror its freeze tree outside harbor's per-trial scratch zone, keyed by `sealed_hash` rather than `trial_name`. Phase 3's `SpacedockSolverAgent` v2 implementation is load-bearing on this design change.

A second, orthogonal finding from the same probe: `harbor jobs resume -p <path>` accepts a path argument that bypasses the spec's `jobs_dir` config field. `rk run`'s emit logic must align so `-p <path>` and `jobs_dir` resolve consistently.

**Probe artifact:** `docs/superpowers/plans/2026-05-19-harbor-resume-probe.md` (commit `1569853`).

## Acceptance criteria

**AC-1 — Spec §4.4 names the conflict and the mitigation.**
Spec §4.4 explicitly documents: (i) harbor's resume destroys incomplete trial dirs and renames trial_name; (ii) razorback's `agent_freeze/` therefore cannot live inside harbor's per-trial scratch; (iii) the mitigation is sealed_hash-keyed external freeze mirroring. Cite the probe doc.
Verified by: spec §4.4 contains the phrases `sealed_hash` and `outside harbor's per-trial scratch zone` (or equivalent that names the constraint precisely); the probe doc is cited.

**AC-2 — Spec §7.1 relocates `agent_freeze/` outside harbor's per-trial path.**
The path-literal correction from AC-0.3/4/6 follow-up #3 (`logs_dir/agent_freeze` → `trials/<name>/agent/agent_freeze`) is wrong in light of AC-0.5: the freeze tree cannot live under `trials/<name>/` at all because that directory is rmtree'd on resume. §7.1 must describe a razorback-owned freeze location (e.g., `logs_dir/_razorback/freeze/<sealed_hash>/`) that lives alongside harbor's trial scratch but outside it.
Verified by: `grep -n "agent_freeze" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` shows the new location; no remaining references to `agent_freeze/` under a `trials/` subpath.

**AC-3 — Spec §3.1 / §8 documents `rk run`'s jobs_dir / `-p <path>` alignment rule.**
`harbor jobs resume -p <path>` overrides config `jobs_dir`. `rk run` emits the spec to harbor; the emit logic must produce identical jobs_dir resolution whether the operator invokes harbor directly or via `rk run`. Spec names the rule: razorback's emit canonicalizes the jobs_dir path before invoking harbor.
Verified by: spec § that defines `rk run`'s emit semantics names the canonicalization rule; the probe doc is cited.

**AC-4 — Phase 3 plan stage acknowledges this mitigation as a load-bearing constraint.**
The Phase 3 entity (when filed) for `SpacedockSolverAgent` v2 must cite this entity in its `## Out of scope` or `## Acceptance criteria` such that the sealed_hash-keyed external freeze design is a pre-condition, not a discovery.
Verified by: when Phase 3's entity is filed, this entity's id (`b5f4zn4vd74yvrmpn207qrwk`) appears as a referenced dependency in its body.

## Test plan

- Plan stage reads the probe doc end-to-end; restates the rmtree behavior and the sealed_hash-keying decision in its own words; flags any place the proposed mitigation might conflict with other spec sections.
- Implementation stage applies the spec edits (no code) and re-greps for the search terms in AC-1, AC-2.
- Validation stage re-reads §4.4 + §7.1 + §3.1 against the probe doc; runs the verification greps; checks that the spec's mitigation is self-consistent (no §4.4 sealed_hash + §7.1 trial_name contradiction).

## Out of scope

- Implementing the mitigation in `SpacedockSolverAgent` v2 — that's Phase 3's work, gated on this spec correction landing.
- Razorback's response to harbor `jobs resume`'s rename of `trial_name` (separate from the freeze-tree question) — folded into Phase 3's plan stage discovery, not this entity.
- Patching harbor — out of scope; razorback works around harbor's behavior, not against it.

## Stage Report: plan

- DONE: Plan separates spec-edit work (§4.4 + §7.1 + §3.1) from forward-reference dependency (Phase 3 AC-4); names the file:line spec changes precisely.
  Plan at `docs/razorback-implementation/plans/spec-mitigation-resume-conflict.md` Tasks 1-3 carry the spec edits to §4.4 (pre-edit lines 373-396), §7.1 (lines 616-634), §3.1 (lines 156-170) + §8.1 (lines 678-698); Task 4 is verification-only against phase3 body lines 29-35 and 156-162.
- DONE: Plan's sealed_hash-keyed external freeze design is specific enough that Phase 3 implementation consumes it without re-discovery — names the freeze location convention, the lifecycle, and the contract between SpacedockSolverAgent and the external freeze tree.
  Plan section "Sealed_hash-keyed external freeze design (load-bearing for Phase 3)" names the location convention (`<harbor-run-dir>/_razorback/freeze/<sealed_hash>/`), a lifecycle table (first-stage, every-stage-commit, harbor-resume, cross-job resume, done, GC), and a 5-point contract Phase 3's class must satisfy.
- DONE: Plan's verification approach for AC-1 / AC-2 / AC-3 uses the grep-style commands named in the entity AC list (mechanically verifiable at validation stage).
  Task 1 Step 3 runs greps for `sealed_hash`, `outside harbor's per-trial scratch zone`, and `2026-05-19-harbor-resume-probe`; Task 2 Step 3+4 runs `grep -n "agent_freeze"` + a negative grep for trial-keyed paths; Task 3 Step 3 runs `grep -n "canonicaliz"` + the probe-doc citation count.

### Summary

Plan separates the four ACs cleanly: three spec edits (§4.4 narrative, §7.1 layout block, §3.1+§8.1 canonicalization rule) and one verification-only task against Phase 3's already-filed dependency citation. The sealed_hash-keyed external freeze design is specified at the location-convention + lifecycle + contract level so Phase 3 reads paths from this plan rather than re-deriving them. Plan also flags the supersession of `ra` AC-5 by this entity's AC-2 with a concrete reconciliation instruction for ra's plan-stage worker.

## Stage Report: implementation

- DONE: Spec §4.4, §7.1, §3.1, §8.1 edits land exactly per the plan doc — file:line targets match plan.md's named ranges; no scope creep into other sections.
  Three commits on `spacedock-ensign/spec-mitigation-resume-conflict`: `3ae7a53` (§4.4 Harbor-resume interaction subsection), `936fe08` (§7.1 layout + reconciled §4.2/§4.3/§4.4/§8.4 path strings), `b9f354f` (§3.1 bullet + §8.1 numbered step 2). All edits within the section ranges named in plan.md "AC ↔ task map".
- DONE: Mechanical greps in plan AC-1/2/3 (sealed_hash, agent_freeze, canonicalization rule) all pass against the edited spec; no leftover references to the old trial-scratch placement.
  AC-1: `grep -n "sealed_hash"` hits §4.4 lines 432/437/438/447/452/457; `grep -n "outside harbor's per-trial scratch zone"` hits line 435; `grep -n "2026-05-19-harbor-resume-probe"` hits §3.1 (line 178), §4.4 (line 455), §7.1 (line 705). AC-2: `grep -n "agent_freeze"` returns zero; bad-path negative grep returns zero; `_razorback/freeze` hits 7 places across the spec. AC-3: `grep -n "canonicaliz"` hits §3.1 line 168 and §8.1 line 761.
- DONE: Edits internally consistent: §4.4's sealed_hash-keying matches §7.1's freeze location convention matches §3.1+§8.1's emit canonicalization — no §-to-§ contradictions.
  §4.4 names location as `<harbor-run-dir>/_razorback/freeze/<sealed_hash>/` (line 417); §7.1 layout block + paragraph use identical path; §4.2 example, §4.3 contract item 4, §4.4 bullet, §8.4 sketch all updated to the same path in the §7.1 commit; §3.1 + §8.1 canonicalization rule is orthogonal (jobs_dir resolution, not freeze placement) and references §3.1 reciprocally from §8.1.

### Summary

Three commits land the four spec edits per plan.md's task map; the §7.1 commit also reconciled four downstream path strings (§4.2 spec example, §4.3 class responsibility item 4, §4.4 contract bullet, §8.4 init sketch) that contradicted the new layout — done per plan Task 2 Step 4's "fix it in the same commit" instruction. AC-4 verification confirmed Phase 3 cites this entity in both its Problem section (line 29) and Depends on section (line 158) with the load-bearing pre-condition framing intact; no Phase 3 edits needed.

## Stage Report: validation

- DONE: Run the entity's AC-1/AC-2/AC-3 verification commands (grep for sealed_hash, agent_freeze, canonicalization) and confirm each returns the expected pattern; AC-4's phase3 forward-reference is intact.
  AC-1: `sealed_hash` hits 19 lines (incl. §4.4 lines 428/430/439/444/449); `outside harbor's per-trial scratch zone` hits §4.3 line 373 and §4.4 line 427; probe doc cited §3.1/§4.4/§7.1. AC-2: `agent_freeze` grep returns empty (exit 1); negative grep for `trials/.../agent_freeze` returns empty; `_razorback/freeze` hits 7 spec locations. AC-3: `canonicaliz` hits §3.1 line 168 and §8.1 line 761; probe doc cited from §3.1. AC-4: Phase 3 cites `spec-mitigation-resume-conflict` at lines 29 (Problem) and 158 (Depends on) with load-bearing pre-condition framing.
- DONE: Cross-check internal consistency: §4.4 / §7.1 / §4.2 / §4.3 / §8.4 all reference the same _razorback/freeze/<sealed_hash>/ path; no leftover trial-scratch references; no §-to-§ contradictions.
  Path literal identical across §3.2 line 349, §4.3 line 369, §4.4 lines 399/429/449, §7.1 lines 685-690+693, §8.4 line 881. §4.4 sealed_hash-keying rationale (trial_name regenerates on resume) matches §7.1 paragraph rationale (sealed_hash derives from spec.frozen.yaml). §3.1 canonicalization (jobs_dir) stays orthogonal to AC-1/2 freeze relocation; no contradictions found.
- DONE: Run superpowers:requesting-code-review against the worktree branch; classify findings blocking vs non-blocking; recommend PASSED or REJECTED with feedback-to: implementation.
  Reviewed diff `2f6599a..3e65dc7` inline (doc-only changes, no test suite to run). Strengths: harbor source citations line-pinned, bidirectional §-cross-refs, probe doc + commit `1569853` cited from every claiming section, AC-3 stays orthogonal to AC-1/2. Findings: 0 critical, 0 important, 2 minor non-blocking (§3.1 "freeze writer" is forward-looking; "Caveat" heading reference in probe doc is auditable via pinned SHA). Decision: APPROVE to `done`.

### Summary

All four ACs verify mechanically against the verifiers the entity names; internal consistency across §3.1/§4.2/§4.3/§4.4/§7.1/§8.1/§8.4 holds with one path literal and no `trial_name`-keyed remnants. Code review finds no blocking issues. Validation report written to `docs/razorback-implementation/validation/spec-mitigation-resume-conflict.md`. Recommended gate decision: approve to `done`; the implementation worker does not need to be re-engaged.
