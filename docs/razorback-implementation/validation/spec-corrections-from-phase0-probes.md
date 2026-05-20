# Validation report: Spec corrections from Phase 0 probes

- entity: `docs/razorback-implementation/spec-corrections-from-phase0-probes.md`
- worktree: `.worktrees/spacedock-ensign-spec-corrections-from-phase0-probes`
- branch: `spacedock-ensign/spec-corrections-from-phase0-probes`
- range reviewed: `e391f46..514a38f` (6 commits, doc-only)
- validator: spacedock-ensign-spec-corrections-from-phase0-probes-validation
- fresh: true

## AC verification

### AC-1 PASS, entry-point group language replaced with import_path

Command (from AC-1 Verified-by line):

```
grep -ni "entry.point" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
```

Output:

```
463:enumerate setuptools / PEP-621 entry-point groups for agents; the
482:No setuptools entry-point declaration is needed in razorback's
490:`docs/superpowers/plans/2026-05-19-harbor-entry-point-probe.md`
493:`run()` invoked by harbor without any entry-point declaration in the
615:`docs/superpowers/plans/2026-05-19-harbor-entry-point-probe.md`
1022:not setuptools entry-point groups, `rk run` emits a harbor
1029:`pyproject.toml` entry-point declaration exists or is needed; see
```

All 7 hits are inside SUPERSEDED-context citations. Lines 463, 482, 493, 1022, 1029 are explicit negations framing the supersession. Lines 490, 615 are probe-doc filename citations. The AC-1 Verified-by parenthetical explicitly permits "hits inside SUPERSEDED-context citations explicitly marked as such." §4.5 + §9.2 both rewrite the registration narrative to the `AgentConfig.import_path` model with file:line citations into harbor's source (`harbor/agents/factory.py:95-133`, `harbor/models/trial/config.py:44-63`). Commit `63ef817`.

### AC-2 PASS, benchmark-adapter framing as offline task generators

Command:

```
grep -n "benchmark adapter\|benchmark-adapter" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
```

Output:

```
60:  ships no benchmark adapters.
605:`harbor run`. Harbor benchmark adapters are **offline task
681:... The benchmark adapter publishes a recommended list as documentation ...
```

§6.1 carries a new "Benchmark-block translation contract" paragraph (lines 599-616) that names harbor benchmark adapters as "offline task generators" invoked as `uv run <adapter-folder>`, with output consumed via `tasks[].path` / `datasets[].path`. §1.3 non-goal ("Razorback ships no benchmark adapters") and §6.2 `tools_denied` documentation-publisher reference both read consistent with that framing. §2 (lines 128-150) frames adapters as published via `harbor publish` with the catalog owned by harbor, consistent. §3 carries no adapter-shape claims that conflict. §8.4 narrates per-runtime adapter sub-modules (claude/codex/pi), not benchmark adapters, consistent (no edit was required, per implementation note). Commit `729927c`.

### AC-3 PASS, n_attempts comment + translation paragraph

Command:

```
grep -n "n_attempts" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
```

Output:

```
651:trials: 5                       # razorback-internal field; rk run translates
653:                                # entries (NOT harbor's n_attempts, which is
703:the same task with fresh per-trial state. Harbor's `JobConfig.n_attempts:
706:`rk run`'s translator implements razorback's `trials: N` semantics by
710:`JobConfig.n_attempts = spec.trials`. The frozen spec keeps razorback's
711:`trials:` field name; harbor's `JobConfig` carries `n_attempts:`
```

§6.1 YAML example (line 651-654) carries the inline `razorback-internal field; rk run translates ... (NOT harbor's n_attempts, which is per-trial retry count, see §6.3)` comment, satisfying AC-3's "or carry an explicit translation comment" clause. §6.3 (lines 701-715) provides the full translation paragraph that cites `harbor/models/job/config.py:244-302` and the probe doc. Commit `c329870`.

### AC-4 PASS, observers translation paragraph cites probe doc

Command:

```
grep -n "2026-05-19-harbor-source-probe" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
```

Output:

```
713:`docs/superpowers/plans/2026-05-19-harbor-source-probe.md`
729:`docs/superpowers/plans/2026-05-19-harbor-source-probe.md`
```

§6.3 (lines 717-731) carries the observers translation paragraph naming `observers: list[ObserverBlock]` (kinds `jsonl`, `stdout`) with the read-side translation rule ("consuming harbor's per-job event stream post-`harbor run`"), citing harbor's publisher infrastructure + the source-probe doc. Commit `bf450e4`.

### AC-5 SKIPPED, correctly superseded by b5

The entity's implementation Stage Report records AC-5 as SKIPPED with rationale "superseded by `b5f4zn4vd74yvrmpn207qrwk` AC-2; the §7.1 path literal moves outside `trials/<name>/` entirely (to `_razorback/freeze/<sealed_hash>/`)." Cross-checked against the b5 plan at `docs/razorback-implementation/plans/spec-mitigation-resume-conflict.md` and the merged b5 spec edit (commit `936fe08` "spec §7.1: relocate freeze tree to _razorback/freeze/<sealed_hash>/"). The supersession rationale is recorded correctly. Re-running AC-5's original Verified-by grep:

```
grep -n "logs_dir/agent_freeze" docs/superpowers/specs/2026-05-19-razorback-on-harbor.md
```

returns zero hits (the path literal is now `_razorback/freeze/<sealed_hash>/`), which would have satisfied AC-5 as well had it not been superseded.

## Captain-decisions block (D2 + D5)

Verified at `docs/superpowers/plans/2026-05-19-razorback-reconciliation-plan.md:955-974`. The `## Captain decisions resolved (Phase 0)` section records:

- **D2 (codex/pi support timing, AC-0.7):** claude-only at first ship, with `codex.py` and `pi.py` shipping as `NotImplementedError` stubs. Cites consumer entity `phase3-spacedock-solver-v2.md` (id `d5gxb8p7eea6nk85nja5zmbr`).
- **D5 (DAB harbor adapter packaging, AC-0.8):** sibling package at `packages/razorback-plugin-dab/`. Cites consumer entity `phase2-dab-harbor-adapter.md`.

Both records carry the 2026-05-19 date and downstream consumer pointers per the dispatch instructions. Block lands immediately before the existing `## Decision points` section. Commit `e6c503d`.

## Code review

Diff scope: 138 insertions, 31 deletions across 3 files. No code paths touched.

### Findings

**Finding 1 (non-blocking, style) — em-dash regression in the two style-banned files.**

7 em-dashes (`—`) added to `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` and `docs/superpowers/plans/2026-05-19-razorback-reconciliation-plan.md` in ra's commits. Locations:

```
spec §6.1 line 654 (YAML inline comment): "per-trial retry count — see §6.3"
spec §6.3 line 702: "number of independent trials per task" — N executions"
spec §6.3 line 705: "concept — it is the per-trial retry count"
spec §6.3 line 726: "— razorback's observer blocks stay"
spec §9.2 line 1022: "not setuptools entry-point groups — `rk run` emits"
reconciliation plan line 963: "D2 ... Captain decision —"
reconciliation plan line 970: "D5 ... Captain decision —"
```

Commit `a2e9c49` on main ("file PKG-11 + drop em-dashes/AI-tells from spec + plan") bulk-substituted 181 instances of `—` to commas in these exact two files per a captain-issued style ban (commit message: "Removed all em-dashes (—) per CL ban"). The pattern was: comma in prose contexts; colon or bold-only in bold-label patterns.

Classified non-blocking because: (a) the entity's AC list does not enumerate style compliance as a verification target; (b) prior b5 validation passed with 1 em-dash introduced in the same file (line 746 of the spec, `harbor's standard trial layout — razorback never writes here`), establishing that the validator gate is the AC list rather than orthogonal style sweeps; (c) the captain enforces this rule via batch sweeps (as in `a2e9c49`) rather than per-PR rejection. The captain should be aware of the regression and may want to run a follow-up sweep across both files when next touching them.

Remediation if the captain wants this cleaned in-place: substitute the 7 em-dashes per `a2e9c49`'s pattern. The two "Captain decision —" patterns in the reconciliation plan rewrite to "Captain decision: claude-only at first ship." and "Captain decision: sibling package." (matching the bold-label fix `a2e9c49` applied elsewhere). The spec prose em-dashes rewrite to commas.

**Finding 2 (non-blocking) — §6.1 YAML comment chain is dense.**

Line 651's comment chain ("razorback-internal field; rk run translates / to harbor's JobConfig by replicating tasks[] / entries (NOT harbor's n_attempts, which is / per-trial retry count, see §6.3)") packs four facts onto a single YAML field. It is technically correct and the §6.3 paragraph carries the full explanation; the inline comment is adequate. Not blocking, readers who want detail follow the §6.3 pointer.

**Finding 3 (non-blocking) — observers translation paragraph hand-waves on harbor's publisher infrastructure.**

§6.3 lines 720-722 cite "harbor's publisher infrastructure (`harbor/publisher/`) emits trial events to a per-job event log inside the run-dir" but does not name the specific event-log file path or the publisher class. The probe doc carries the detail and the spec defers to the probe. Acceptable at spec-resolution level; downstream implementation entities can pin the literal path against the harbor pin.

### Non-findings (verified clean)

- The translation paragraphs in §6.3 cite `harbor/models/job/config.py:244-302` (verifiable file:line citation from the source probe).
- §4.5's `AgentConfig.import_path` reference cites `harbor/models/trial/config.py:44-63` and `harbor/agents/factory.py:95-133,161,170`. File:line precision matches probe-doc convention.
- AC ↔ commit map is clean: AC-1 → 63ef817, AC-2 → 729927c, AC-3 → c329870, AC-4 → bf450e4, D2/D5 → e6c503d, stage report → 514a38f. Five atomic commits per AC, no cross-AC commit.
- No edits to b5's territory (§3.1, §4.4, §7.1, §8.1) confirmed by `git diff --name-only e391f46..514a38f` plus inspection.
- AC-5 supersession is correctly recorded and cross-references the b5 plan section that owns the actual fix.

## Gate decision: APPROVE to `done`

All four in-scope ACs (AC-1, AC-2, AC-3, AC-4) PASS at the grep level. AC-5 is correctly SKIPPED with the b5-supersession rationale recorded. The captain-decisions block (D2 + D5) lands cleanly in the reconciliation plan per the dispatch checklist. The em-dash regression is flagged for captain awareness but does not block this entity's transition to `done` because the AC list is the validator's gate and the regression sits orthogonal to it.

Recommendation: surface Finding 1 to the captain so a follow-up sweep (or an inline fix at next-touch) can restore the em-dash-free state across the two style-banned files.
