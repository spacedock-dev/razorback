---
id: 1e92ygpkdwd296tw8xt9nvt1
title: T0 cost-shape verification — Goal 1 RESUME (spacedock-first)
status: done
source: 2026-05-21 cost-shape probe note
started: 2026-05-21
completed: 2026-05-21
verdict: PASSED
score:
worktree:
issue:
pr:
mod-block:
---

# T0 cost-shape verification — Goal 1 RESUME (spacedock-first)

Date: 2026-05-21
Probe: spacedock variant × bookreview dataset × 1 trial (3 questions, q1+q2+q3).

## What ran

- spec: `examples/specs/goal1/spacedock/bookreview.frozen.yaml`
- runs-dir: `runs/goal1-resume/t0/spacedock/bookreview/`
- model alias: `claude-opus-4-7` (paid-API auth via `.env` ANTHROPIC_API_KEY, key length 108).
- HOME=$PWD/.cache_home with `.docker` symlinked to `/Users/clkao/.docker`
  (required: harbor's `_stage_harbor_home` mirrors `$HOME/.docker`; an empty
  cache_home meant docker compose CLI plugin was missing on the first attempt,
  surfaced as `unknown flag: --project-name` exit 125).
- DOCKER_HOST=unix:///Users/clkao/.colima/default/docker.sock.

## Outcome

- trials: 3/3 completed, 0 errored.
- reward: 1.0 / 1.0 / 1.0 (stratified_pass_at_1=1.0 on bookreview).
- wall: 3m 50s (Job Info total runtime).
- `summary.json` cost_usd: **null** on all 3 trials and on the job total.
- `result.json -> step_results`: **null** (claude-cli agent does not populate
  per-step `agent_result.cost_usd`).

## Finding: paid-API cost telemetry is NOT surfaced by the claude-cli agent

The entity body §Architecture paragraph "Paid-API auth" predicted `cost_usd`
would be non-null under `.env` `ANTHROPIC_API_KEY`. Empirically this is FALSE
for `agent.kind=claude-cli` (the matrix's chosen agent kind):

- `src/razorback/runs/aggregate.py:133-149` (`_trial_cost`) reads
  `step_results[*].agent_result.cost_usd`. The claude-cli agent
  (`src/razorback/agents/claude_cli.py`, 118 lines, no `cost_usd` write site)
  never populates this. Only `spacedock_solver` / `spacedock_solver_v2`
  surface per-stage `cost_usd`, and those are different agent kinds.
- The auth resolution at `src/razorback/agents/auth.py:23-67` successfully
  loaded ANTHROPIC_API_KEY from `.env` (mode=`api-key`, verified by the trial
  proceeding past the `AuthDiscoveryError` and by trials reaching
  `reward=1.0`). That confirms the auth is paid-API; what it does NOT confirm
  is per-trial cost capture.

## Implication for AC-5 (cost ≤ $100)

`--max-budget-usd-running` enforces only when per-trial cost is known
(`src/razorback/budget.py`). With `cost_usd=null` flowing from every trial,
the matrix driver's `budget.json` running total stays at 0 and the budget
gate is a no-op. AC-5's "cost ledger ≤ $100" cannot be enforced or verified
from the run artifacts alone.

This is a HARDER block than "cost too high" — it's "cost not measurable",
which means AC-5's verification step "cost ledger committed; total ≤
budget" cannot be produced.

## Recommendation (to captain via team-lead)

Three captain-decision options:

A. **Proceed with no live cost gate.** Accept that AC-5 is verified post-hoc
   via Anthropic Console usage/billing for the dispatch window (timestamp-
   bounded) rather than from in-run telemetry. Matrix dispatches anyway;
   AC-5 evidence is the console screenshot + dispatch window timestamps.

B. **Patch `claude_cli.py` to emit `cost_usd`.** Out of scope per the entity
   §Out of scope ("no new code surfaces; no new ACs beyond the ordering and
   budget changes"). Would be a PKG-style entity.

C. **Switch the matrix variant agent_kind to spacedock_solver_v2 for
   spacedock**, accepting that direct-minimal/direct-structured stay on
   claude-cli with no cost data. Mixed-shape result doc.

Per the captain's "$100 ceiling needs explicit approval if exceeded" and
"AC-5 says cost stays within budget"  — option A is cheapest path to
keeping the entity verdict PASSED with a documented caveat. Option B is
correct but expands scope.

## Empirical cost projection (wall-time-only, no $$ yet)

- bookreview spacedock: 3 questions, 3m 50s ⇒ ~77 s / question.
- 36 cells × ~10 questions median × ~80 s/question ≈ 8 hours of wall.
- Cost projection: opus-4.7 is roughly $15/M input + $75/M output. Without
  per-trial cost telemetry we cannot pin $/question. Conservative estimate
  from published opus-4.7 pricing and DAB-typical 30K-60K token budgets per
  agentic question: $0.50-$2.50 per question, i.e. $180-$900 for the matrix.
- The $100 ceiling is **likely tight to under-budget** for the full 36 cells
  at opus-4.7 paid rates. Captain confirmation needed.

## Files

- `runs/goal1-resume/t0/spacedock/bookreview/goal1-spacedock-bookreview/f45dc9edd8e37bbc/summary.json` — 3/3 reward=1.0, cost_usd=null
- `runs/goal1-resume/t0/spacedock/bookreview/goal1-spacedock-bookreview/f45dc9edd8e37bbc/result.json` — stats with cost_usd=null
- `runs/goal1-resume/t0/spacedock/bookreview/dispatch.log` — driver tail
- `runs/goal1-resume/t0/spacedock/bookreview/budget.json` — driver ledger
