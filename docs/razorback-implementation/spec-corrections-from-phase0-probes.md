---
id: ra95gn6g7fhzjfzpv3q4m3ay
title: Spec corrections from Phase 0 probes (import_path dispatch + harbor follow-ups)
status: plan
source: AC-0.2 + AC-0.3/4/6 probe findings (Phase 0 reconciliation plan)
started: 2026-05-20T06:06:58Z
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
mod-block:
---

## Problem

Phase 0's harbor probes (AC-0.2 entry-point execution probe; AC-0.3/4/6 harbor source probe) discovered the v2 spec at `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` carries language that does not match harbor's actual surface. Phase 1's plan stage cannot reliably cite spec sections until these corrections land. The corrections are small, mechanical, and well-documented in the probe artifacts.

**Probe artifacts to consume:**
- `docs/superpowers/plans/2026-05-19-harbor-entry-point-probe.md` (AC-0.2 — verdict WORKS via `AgentConfig.import_path`)
- `docs/superpowers/plans/2026-05-19-harbor-source-probe.md` (AC-0.3/4/6 — three small follow-ups)

## Acceptance criteria

**AC-1 — Spec replaces "entry-point group" language with `import_path` terminology.**
Per AC-0.2's probe: harbor has no setuptools/PEP-621 entry-point groups for agents or adapters. Dispatch is via `AgentConfig.import_path: "module.path:ClassName"`. Every spec section that mentions entry-point group registration (§4 SpacedockSolverAgent, §8 implementation notes, anywhere `entry_points` or `entry-point group` appears) updates to the `import_path` model.
Verified by: `grep -ni "entry.point" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` returns no hits after the edit (or only hits inside SUPERSEDED-context citations explicitly marked as such).

**AC-2 — Spec clarifies benchmark-adapter shape as offline task generators.**
Per AC-0.2's probe: harbor benchmark adapters have no runtime dispatch. They are offline packages whose output (task directories) is consumed via `JobConfig.tasks[].path` / `datasets[].path`. The spec's references to "external benchmark adapter entry-point" need replacing with the offline-generator framing.
Verified by: spec §2 + §3 + §8.4 (or wherever benchmark adapter shape is described) reads consistent with the entry-point-probe doc's "Implications" section.

**AC-3 — Spec uses `n_attempts`, not `trials`, where harbor's JobConfig field is `n_attempts`.**
Per AC-0.3/4/6 follow-up #1: harbor's JobConfig uses `n_attempts` for per-task trial count. Spec usage of `trials:` in spec/plan examples may need alignment.
Verified by: spec examples that translate to JobConfig field names match harbor's actual field names (or carry an explicit `# razorback-internal naming; translates to harbor's n_attempts` comment).

**AC-4 — Spec describes observers field translation per harbor's JobConfig.**
Per AC-0.3/4/6 follow-up #2: razorback's spec includes an observers concept that needs translation to harbor's JobConfig shape. The translation rule is named in `2026-05-19-harbor-source-probe.md`; the spec must cite that translation explicitly.
Verified by: a paragraph in the spec § that defines the observers translation rule, citing the probe doc.

**AC-5 — Spec §7.1 path literal `logs_dir/` corrected to `agent/`.**
Per AC-0.3/4/6 follow-up #3: harbor writes per-trial artifacts under `trials/<name>/agent/`, not directly under `logs_dir/`. Razorback's `agent_freeze/` subtree placement description in §7.1 needs the literal path corrected.
Verified by: `grep -n "logs_dir/agent_freeze" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` returns zero hits; the correct `trials/<name>/agent/agent_freeze/` shape appears.

## Test plan

- Plan stage compares each AC's spec target to the probe doc's source-cited claim; flags any reading where the spec and probe diverge beyond what this entity's AC list captures.
- Implementation stage edits the spec + plan inline (no code) and re-greps to confirm AC-1, AC-5 pass mechanically.
- Validation stage re-reads the corrected spec sections cross-checked against the probe docs; runs the `grep` commands named in AC-1 and AC-5.

## Out of scope

- Re-writing the spec from scratch; only the corrections named in the AC list land here.
- Captain decisions still open (D2 codex/pi timing, D5 DAB adapter packaging) — recorded separately in the plan body, not in this entity.
- Phase 1 implementation work (rk run v2 wrapper) — separate entity once the spec is corrected.
