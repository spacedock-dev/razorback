# Validation — b5 — Spec mitigation for harbor jobs resume conflict (§4.4)

Worktree branch: `spacedock-ensign/spec-mitigation-resume-conflict`
Tip commit at validation start: `3e65dc7` (`b5: append implementation stage report`)
Validator: fresh agent, did not write the implementation
Acceptance command (entity §AC list): the grep set named in AC-1 / AC-2 / AC-3 verifications plus the forward-reference check named in AC-4.

This is a doc-only entity. No code, no tests, no `uv run pytest`. Validation
exercises the AC verifiers verbatim against the spec at
`docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` and the Phase 3 entity
at `docs/razorback-implementation/phase3-spacedock-solver-v2.md`.

## AC verification

### AC-1 — Spec §4.4 names the conflict and the mitigation — PASS

Verifier clause: "spec §4.4 contains the phrases `sealed_hash` and
`outside harbor's per-trial scratch zone` (or equivalent that names the
constraint precisely); the probe doc is cited."

Command 1: `grep -n "sealed_hash" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Output: 19 hits including §4.4 lines 428, 430, 439, 444, 449 — all inside the
"Harbor-resume interaction" subsection (lines 414-456) added by commit `3ae7a53`.

Command 2: `grep -n "outside harbor's per-trial scratch zone" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Output:
```
373:   location lives outside harbor's per-trial scratch zone so it
427:directory **outside harbor's per-trial scratch zone**, keyed by
```
The verbatim phrase appears at §4.3 item 4 (line 373) and at §4.4's mitigation
paragraph (line 427).

Command 3: `grep -n "2026-05-19-harbor-resume-probe" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Output:
```
178:  `docs/superpowers/plans/2026-05-19-harbor-resume-probe.md`,
455:`docs/superpowers/plans/2026-05-19-harbor-resume-probe.md`
705:`docs/superpowers/plans/2026-05-19-harbor-resume-probe.md`,
```
Probe doc cited from §3.1, §4.4 (the AC-1 surface), and §7.1. Commit `1569853`
is named alongside each citation.

### AC-2 — Spec §7.1 relocates `agent_freeze/` outside harbor's per-trial path — PASS

Verifier clause: "`grep -n "agent_freeze" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
shows the new location; no remaining references to `agent_freeze/` under a
`trials/` subpath."

Command 1: `grep -n "agent_freeze" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Output: empty (exit 1). Every `agent_freeze` reference is gone; the freeze
tree is renamed to `_razorback/freeze/<sealed_hash>/`.

Command 2 (negative): `grep -nE "trials/[^/]+/(agent/)?agent_freeze" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Output: empty (exit 1). No leftover trial-scratch placement.

Command 3 (positive, the new location): `grep -n "_razorback/freeze" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Output: 7 hits at lines 349 (§4.2 yaml example), 369 (§4.3 contract item 4),
399 (§4.4 contract bullet), 429 (§4.4 mitigation paragraph), 449 (§4.4
consequences bullet), 693 (§7.1 paragraph), 881 (§8.4 setup sketch). The
spec's §7.1 layout block at lines 685-690 names the directory in the run-dir
tree directly.

Note: the entity's AC-2 verifier text says "the new location" generically; the
spec literal is `_razorback/freeze/<sealed_hash>/`, matching the plan's
"sealed_hash-keyed external freeze design" section.

### AC-3 — Spec §3.1 / §8 documents `rk run`'s jobs_dir / `-p <path>` alignment rule — PASS

Verifier clause: "spec § that defines `rk run`'s emit semantics names the
canonicalization rule; the probe doc is cited."

Command 1: `grep -n "canonicaliz" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
Output:
```
168:- Path canonicalization. Commands that emit a spec for harbor to
761:   path canonicalization.
```
The rule is stated as a §3.1 design rule (line 168, "Path canonicalization.
Commands that emit a spec for harbor to consume (`rk run`, the freeze writer)
resolve `jobs_dir` to an absolute, symlink-resolved path before passing it to
harbor"), and §8.1 step 2 (lines 756-761) implements the rule for `rk run`
with the concrete `Path(jobs_dir).expanduser().resolve()` recipe and a
reciprocal "See §3.1" pointer.

Command 2: probe-doc citation count in §3.1 — see AC-1 Command 3 output line
178; the design-rule paragraph names the probe doc and commit `1569853`.

### AC-4 — Phase 3 plan stage acknowledges this mitigation as a load-bearing constraint — PASS

Verifier clause: "when Phase 3's entity is filed, this entity's id
(`b5f4zn4vd74yvrmpn207qrwk`) appears as a referenced dependency in its body."

Command: `grep -nE "b5f4zn4vd74yvrmpn207qrwk|spec-mitigation-resume-conflict" docs/razorback-implementation/phase3-spacedock-solver-v2.md`
Output:
```
29:Phase 3 is load-bearing on `b5` spec-mitigation-resume-conflict: the
158:- `b5` spec-mitigation-resume-conflict (load-bearing constraint —
```

Phase 3 cites b5 in its Problem section ("Phase 3 is load-bearing on `b5`
spec-mitigation-resume-conflict: the freeze tree is sealed_hash-keyed and
mirrored outside harbor's per-trial scratch zone because `harbor jobs
resume` rmtree's incomplete trial dirs.") and in its Depends on list
("`b5` spec-mitigation-resume-conflict (load-bearing constraint —
sealed_hash-keyed external freeze location is a pre-condition, not a
discovery; per AC-4)"). Pre-condition framing is intact.

The entity AC-4 verifier matches on slug (`spec-mitigation-resume-conflict`)
not on the raw `id` field; the slug is unambiguous within this workflow and
Phase 3 spells it out twice. The implementation's stage report claim that "no
Phase 3 edits needed" reproduces.

## Internal consistency cross-check

Each spec section that references the freeze tree uses the same path literal
`_razorback/freeze/<sealed_hash>/`:

- §3.2 example yaml (line 349): `resume_from_freeze: <prior-run-dir>/_razorback/freeze/<sealed_hash>/`
- §4.3 contract item 4 (line 369): `<harbor-run-dir>/_razorback/freeze/<sealed_hash>/`
- §4.4 contract bullet (line 399): `_razorback/freeze/<sealed_hash>/`
- §4.4 mitigation paragraph (line 429): `<harbor-run-dir>/_razorback/freeze/<sealed_hash>/`
- §4.4 consequences (line 449): `_razorback/freeze/<sealed_hash>/`
- §7.1 layout (lines 685-690) + paragraph (line 693)
- §8.4 setup sketch (line 881): `<run-dir>/_razorback/freeze/<sealed_hash>/`

No `trial_name`-keyed freeze references remain anywhere. The §4.4 narrative
(sealed_hash-keyed because trial_name regenerates on resume) matches the §7.1
paragraph rationale (sealed_hash derives from `spec.frozen.yaml` which
survives resume). The §3.1 canonicalization rule (jobs_dir resolution) is
orthogonal to the freeze relocation (AC-1/2) and stays orthogonal in the
spec text — the §8.1 step 2 implementation note for canonicalization does not
collide with the §8.4 setup sketch for freeze writes.

Harbor source citations (`harbor/cli/jobs.py:1361-1430`,
`harbor/job.py:_maybe_init_existing_job:192-228`,
`harbor/models/trial/config.py:213-222`, `harbor/cli/jobs.py:1444-1477`)
are line-pinned to the AC-0.5 probe's findings; the validator did not re-run
the probe but the §4.4 narrative reads consistent with the probe artifact at
`docs/superpowers/plans/2026-05-19-harbor-resume-probe.md`.

## Code review (per superpowers:requesting-code-review)

Reviewed the diff `2f6599a..3e65dc7` (one commit per AC plus the stage
report). Scope: 5 commits, four spec sections (§3.1, §4.2/4.3/4.4, §7.1,
§8.1/8.4), and the entity stage report append.

### Strengths

- Each non-trivial behavioral claim links to a harbor source line range
  (`harbor/cli/jobs.py:1361-1430`, `harbor/job.py:_maybe_init_existing_job:192-228`,
  `harbor/models/trial/config.py:213-222`, `harbor/cli/jobs.py:1444-1477`).
- Bidirectional cross-references: §4.3 item 4 → §4.4 + §7.1; §7.1 paragraph
  → §4.4; §4.4 mitigation → §7.1; §8.1 step 2 → §3.1; §7.1 paragraph → §4.3
  + §8.4 for sealed-hash derivation.
- The probe doc + commit `1569853` is cited from §3.1, §4.4, and §7.1 — every
  section that makes a claim about harbor's resume behavior.
- AC-3 (canonicalization) stays orthogonal to AC-1/2 (freeze relocation) in
  both the spec text and the commit history.
- The §7.1 commit (`936fe08`) also reconciled four downstream path strings
  (§4.2 yaml, §4.3 item 4, §4.4 bullet, §8.4 sketch) per plan Task 2 Step 4's
  instruction to "fix it in the same commit"; no cross-§ contradictions
  remain.

### Findings

- **Minor / non-blocking:** §3.1's design-rule paragraph names "the freeze
  writer" alongside `rk run` as a command that canonicalizes — this is
  forward-looking (Phase 3 work) but reads as a present-tense rule. The §8.1
  step 2 implementation note covers `rk run` concretely; the "freeze writer"
  contract is implicit in the §3.1 rule. Acceptable for a spec document.
- **Minor / non-blocking:** The §3.1 paragraph references a "Caveat from the
  first (invalid) attempt" section heading in the probe doc; if that heading
  ever moves, the §3.1 prose still scans but the in-doc cross-reference goes
  stale. Pinned by commit SHA `1569853`, so auditable.

No Critical findings. No Important findings. No blocking issues.

### Classification

- Blocking: none
- Non-blocking: 2 minor observations above; do not require a fix to land
  this entity.

## Gate decision

**APPROVE to `done`.**

- All four ACs verified mechanically against the entity's named verification
  commands.
- Internal consistency holds: §3.1, §4.2, §4.3, §4.4, §7.1, §8.1, §8.4 all
  reference the same freeze-tree path; no `agent_freeze` or trial-keyed
  remnants.
- Phase 3's forward-reference (AC-4) is intact in both Problem and Depends-on
  sections with load-bearing pre-condition framing.
- Code review finds no blocking issues; the two minor observations do not
  block.

The implementation worker at name
`spacedock-ensign-spec-mitigation-resume-conflict-implementation` does not
need to be re-engaged.
