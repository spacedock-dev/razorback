---
id: b5f4zn4vd74yvrmpn207qrwk
title: Spec mitigation for harbor jobs resume conflict (§4.4)
status: plan
source: AC-0.5 probe finding (Phase 0 reconciliation plan)
started: 2026-05-20T05:58:15Z
completed:
verdict:
score: 0.95
worktree:
issue:
pr:
mod-block:
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
