---
id: bafje0bpa1c8jvz9vtbs2q5q
title: PKG-13 — harbor-DAB live-DB verification stack (Phase 2 + Phase 4a remediation)
status: validation
source: T14 false-positive investigation 2026-05-20 (docs/superpowers/plans/2026-05-20-t14-false-positive-investigation.md)
started: 2026-05-20T16:49:49Z
completed:
verdict:
score: 1.0
worktree: .worktrees/spacedock-ensign-pkg13-harbor-dab-live-db-verification-stack
issue:
pr:
mod-block:
---

## Problem

T14 reported 100% pass@1 across 9 bookreview-claude live-DB trials. The investigation at `docs/superpowers/plans/2026-05-20-t14-false-positive-investigation.md` (commit `561f1c1`) found four layered bugs that together produce false positives without any live-DB execution:

1. **Plugin writes `docker-compose.yaml` at task-dir root, but harbor only loads `environment/docker-compose.yaml`.** The compose stack is never loaded by harbor's environment dispatch.
2. **`task.toml`'s `[environment].docker_compose` field is silently dropped** because no such field exists in harbor's EnvironmentConfig. The plugin's authored task.toml is interpreted with only `[environment].type` honored.
3. **The bind-mount path bug is moot** because compose is never loaded. The originally-reported `./workdir/query_dataset/books_info.sql` issue is real but secondary.
4. **T7's bookreview reachability gate is not implemented.** Phase 2 task #41 was marked completed, but the runtime gate that should fail-fast when postgres is unreachable does not exist in the plugin. No mechanism catches the silent compose-not-loaded state.

**Live evidence** (per investigation): no `dab-postgres` container exists in any T14 trial. The dab-agent has read-access to `books_info.sql` via a separate workdir bind-mount and produces `{"answer":"2020s"}` by parsing the SQL dump directly. The verifier passes on substring matches: q1's validator matches `"2020"` against `"2020s"`; q2 + q3's ground-truth book titles are literal strings in the SQL dump that the agent grepped.

Goal 1 (DAB paper reproduction) and Goal 2 (ade-bench Haiku) are blocked on this fix. Without it, any matrix run produces uniformly bogus reward=1.0 scores.

**Probe artifact:** `docs/superpowers/plans/2026-05-20-t14-false-positive-investigation.md` (commit `561f1c1`).

## Acceptance criteria

**AC-1 — Plugin writes compose at the harbor-expected location.**
Plugin's compose generator writes to `<task-dir>/environment/docker-compose.yaml` (or whichever path harbor's EnvironmentConfig actually loads). Verified by: a fresh `harbor task list` on a generated task dir + `harbor run` invocation produces a job-config that includes the compose services (dab-postgres, dab-mongo, main).

**AC-2 — Compose loading is observably true at run time, not structurally inferred.**
At least one of: (a) `events.jsonl` per trial contains the postgres+mongo container start events, OR (b) a `compose_loaded.jsonl` (or harbor-equivalent) sidecar records compose services brought up per trial. Verified by: a fresh T14 retry shows the loading event for each trial.

**AC-3 — Bookreview reachability gate fail-fast.**
The plugin (or razorback-DAB) implements a pre-trial gate: before the agent step runs, a smoke `psql --host dab-postgres -d bookreview_db -c "SELECT count(*) FROM books"` (or equivalent) succeeds. If it fails, the trial fails with a named error before any agent invocation. Verified by: a synthetic test that mis-configures the postgres init script and observes the gate exit non-zero with a clean error message.

**AC-4 — bind-mount path correctness.**
The compose bind-mount source path resolves to a real file at compose-up time. Verified by: docker compose config -q + a host-side check that the bind source file exists per task.

**AC-5 — Validator substring-leak hardening.**
For bookreview q1, q2, q3, the validators distinguish "agent grep'd the SQL dump" from "agent queried postgres". One approach: ground-truth answers contain values that ONLY exist in postgres's normalized form (e.g., joined-table results) and NOT in the raw SQL dump file. OR: validators consume agent-emitted SQL queries (not just final answers) and check the queries hit dab-postgres. Verified by: a synthetic attack test where the agent is forced to read books_info.sql directly via grep and the validator returns reward=0.0.

**AC-6 — T14 re-run produces honest numbers.**
After AC-1 through AC-5 land, re-run T14 (bookreview-claude live-DB, N=3) and record headline + Wilson CI in `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`. Supersedes the previous T14 result. Verified by: events.jsonl shows actual postgres queries from the agent.

## Test plan

- Plan stage reads the investigation doc end-to-end; reproduces the four-layer diagnosis against a fresh compose-up + harbor run; writes the AC↔task map.
- Implementation stage applies fixes per AC, TDD-first per task.
- Validation stage re-runs T14 from a clean checkout; confirms AC-6's events.jsonl evidence; runs the AC-5 substring-leak attack test.

## Out of scope

- Re-running T15 (12-dataset matrix) and Goals 1+2 — those follow PKG-13's shipment.
- Auditing other harbor adapters (τ-bench, LogicStar, terminal-bench-2, ade-bench) for similar bugs — file separately if surfaced.
- Generalizing the bookreview reachability gate to ade-bench shape — Goal 2's blocker, separate entity.

## Depends on

- 51 phase2-dab-harbor-adapter (done; this fixes the four shipped bugs without rewriting the package)
- PKG-12 harbor-DAB translator dispatch fix (already landed on main)

## Blocks

- Goal 1 — DAB paper reproduction (entity `ay`)
- Goal 2 — ade-bench Haiku baseline (entity `jj`; may need separate ade-bench fix)
- T15 — Phase 2 12-dataset matrix reconciliation (deferred earlier)

## Stage Report: plan

- DONE: Plan reads the investigation doc end-to-end. Each of the four root causes maps to a concrete fix task; the AC-task map covers all 6 ACs.
  Plan at docs/razorback-implementation/plans/pkg13-harbor-dab-live-db-verification-stack.md; AC-to-task table covers AC-1..AC-6; investigation causes 1/2/3/4/5 map to T1/T2/T7/T5+T6/T8+T9 respectively (cause-6 explicitly out of scope).
- DONE: Plan distinguishes plugin-side fixes from harbor-side requirements. Harbor's EnvironmentConfig contract verified end-to-end against the pinned harbor in .venv.
  EnvironmentConfig at harbor/models/task/config.py:127-170 has no `docker_compose` field; harbor's compose discovery at docker.py:249-251 hard-codes `environment_dir / "docker-compose.yaml"`. Plan T1 moves the plugin's compose write to `<task-dir>/environment/docker-compose.yaml` and drops the dead `[environment].docker_compose` line. T0 codifies the contract as a failing-test assertion that guards future harbor upgrades.
- DONE: AC-5 hardening strategy chosen and motivated. Riskiest-mechanism-first ordering: AC-1+AC-2+AC-3 land before AC-6 re-run.
  AC-5 split into T8 (q1 bounded-decade match wrapping the upstream substring check) and T9 (q2/q3 length cap on the canonical answer string). Rejected the "validators consume agent-emitted SQL" alternative as too large a contract change; chose bounded-answer as the smallest fix closing the specific T14 exploit. Task ordering: T0 (harbor contract) -> T1-T4 (compose location + observability + AC-4 bind-mount) -> T5-T6 (reachability gate) -> T7 (post-generate bind-mount existence check) -> T8-T9 (validators) -> T10 (single-trial stack smoke) -> T11 (AC-6 N=3 re-run + reconciliation update).

### Summary

Wrote a separate plan doc at docs/razorback-implementation/plans/pkg13-harbor-dab-live-db-verification-stack.md (6 ACs > 3 threshold). Plan opens with a harbor contract verification block (no `docker_compose` field; compose at `environment/docker-compose.yaml`) and codifies it as the first failing-test task (T0) so the rest of the plan's ordering is defensible. Eleven tasks total, ordered riskiest-mechanism-first; AC-1+AC-2+AC-3 land before AC-6's re-run. No em-dashes; "load-bearing" replaced with "critical" per the recent style cleanup.
