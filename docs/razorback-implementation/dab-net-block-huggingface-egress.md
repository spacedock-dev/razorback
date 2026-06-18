---

id: wjfra5rje67399g6msza9zg6
title: dab-net — block huggingface.co + dataset CDN egress at the network layer
status: backlog
source: '2026-05-23 7q validation cheating-audit finding — even after the workspace README adds leak-guard prose (sibling `k3`) and the verify stage gains an external-oracle audit (sibling `wp`), the network layer remains the irrefutable guard. agnews''s `load_dataset` call succeeded because `dab-net` bridge has unrestricted public egress to `huggingface.co`. A hard network block would have closed the attack path at the lowest layer regardless of prompt or library. Auto-approve: false because network policy is infrastructure-facing and irreversible mid-run.'
score: 0.78
auto-approve: false
worktree:
issue:
pr:
mod-block:
started:
completed:
verdict:
---

## Problem

The `dab-net` docker bridge created by `~/git/dataagentbench/benchmark/setup.sh:122-138` lets `dab-postgres` + `dab-mongo` + `dab-agent` + `dab-mlflow` talk to each other. The bridge inherits docker's default of unrestricted outbound internet. Agents inside `dab-agent` can therefore reach:
- `huggingface.co` + `*.huggingface.co` (HF Hub dataset downloads — the agnews attack)
- `raw.githubusercontent.com` (used in DAB upstream's AG News cheating example)
- `kaggle.com`, `cdn.jsdelivr.net`, any public CDN

The `--disallowedTools` block list catches Bash invocations of `curl`/`wget`/`git clone`. The workspace README prose (post sibling `k3`) catches `datasets.load_dataset` at the prompt layer. The external-oracle audit (post sibling `wp`) catches admitted attempts in the trace. But all three are SOFT: an agent could in principle find a new attack path none of them cover. A network-layer block is the HARD defense — no matter what code the agent runs, HTTP egress to forbidden hosts fails at the TCP layer.

## Acceptance criteria

**AC-1 — `dab-net` setup adds an egress allowlist or denylist that blocks dataset hosts.**
The `setup_isolation()` function in `~/git/dataagentbench/benchmark/setup.sh` (or razorback's local override) configures `dab-net` so that container egress to `huggingface.co`, `*.huggingface.co`, `raw.githubusercontent.com`, `kaggle.com`, `*.kaggle.com`, and `cdn.jsdelivr.net` fails with connection-refused. Egress to `dab-postgres:5432`, `dab-mongo:27017`, `dab-mlflow:5000`, `pypi.org` (for legitimate pip installs like `rapidfuzz`), and the Anthropic API (`api.anthropic.com`) is preserved.
Verified by: `docker run --rm --network dab-net curlimages/curl -sI https://huggingface.co --max-time 5` returns connection-refused or timeout; same against `raw.githubusercontent.com`; `docker run --rm --network dab-net curlimages/curl -sI https://pypi.org --max-time 5` returns 200 OK; `docker run --rm --network dab-net curlimages/curl -sI dab-postgres:5432 --max-time 5` connects (or returns the postgres handshake error, which is fine — proves dab-net resolution works).

**AC-2 — Razorback ships the dab-net configuration upstream-of-setup.**
Whether the block is implemented as (a) a custom docker network driver, (b) a sidecar `dab-net-firewall` container with iptables rules, (c) a docker network plugin, or (d) a fork of upstream's `setup.sh` shipped under razorback — the implementation lives in razorback's repo so razorback can re-apply it without waiting for upstream. The choice is captain-reviewable at plan-stage gate.
Verified by: razorback's repo carries the network-policy artifact (script, Dockerfile, or config); the artifact is invoked by `examples/drivers/dab-paper-matrix.sh` (or a per-cell setup hook) before any cell dispatches.

**AC-3 — Live agnews re-run is blocked at the network layer.**
Re-dispatch agnews against the post-AC-1 dab-net configuration. The agent's `load_dataset('fancyzhx/ag_news')` attempt fails with a connection error from `huggingface.co`. The `claude-code.txt` trace captures the exception. The agent reaches `"UNABLE TO DETERMINE"` (per sibling `k3`'s prompt rule) or fails gracefully.
Verified by: agnews cell's `claude-code.txt` shows the load_dataset attempt + connection-refused stack trace; final answer is either `"UNABLE TO DETERMINE"` or a non-cheating low-confidence guess; cheating-audit re-runs against the new trace as `clean`.

**AC-4 — Existing 12 DAB datasets still work end-to-end.**
The block doesn't accidentally break legitimate operation. All 12 DAB datasets (bookreview, agnews, crmarenapro, googlelocal, music_brainz_20k, stockindex, stockmarket, yelp, DEPS_DEV_V1, GITHUB_REPOS, PANCANCER_ATLAS, PATENTS) — re-run a sample of 4 (one each of: sqlite-only, postgres-needed, mongo-needed, mixed) — finish with non-zero rewards and no false-positive network failures.
Verified by: 4-cell sample run completes with each cell's `result.json` populated; no false-positive `huggingface.co connection refused` errors for cells that didn't try to access it.

**AC-5 — Docs name the egress policy.**
Razorback's README + workflow README + the v2 spec §5.3 reference the network-layer block as the second leak-guard layer (after prompt + verify-audit). Consumer-research-repo onboarding (post Phase-5 + post-`hm`) names the network policy so consumers running custom benchmarks know what their containers can reach.
Verified by: `grep -F 'huggingface.co' docs/razorback-implementation/README.md` or `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` matches.

## Test plan

- **Mechanism gate first:** prototype the network block on a throwaway docker network; confirm both blocked-host and allowed-host behavior via `curl` from an ephemeral container before touching dab-net.
- **AC-1/2/4 smoke:** bring up dab-net under the new policy; run the 4-cell sample.
- **AC-3 live agnews re-run:** ~$1-3 API spend.
- **AC-5 docs:** prose updates land alongside the code.

## Out of scope

- **DNS-layer block** vs **iptables-layer block** vs **proxy-layer block.** Plan-stage decision based on what works cleanly with docker on the captain's M-series mac (Colima) + future linux deployment. Captain may want the network policy choice presented for approval at plan gate.
- **Audit-trail capture of blocked attempts.** Nice to have (logs every connection-refused to `dispatch-failures.tsv`), but the verify-stage external-oracle audit already catches admitted attempts. Defer to a follow-on entity if useful.
- **Allowlist of additional hosts** beyond pypi.org + Anthropic API. Each new permitted host should require captain approval; this entity ships the initial minimal allowlist.
- **Captain-side egress block.** This entity scopes to dab-agent containers (where benchmark agents run); the captain-side FO + ensign sessions need their own network policy (this captain session uses Anthropic API + GitHub + Harbor Hub).

## Depends on

- **`k34cqr2myjsh6aaqm6fhz5nw` dab-workspace-readme-leak-guard-prose-port** — soft layer 1 (prompt deterrence).
- **`wpjrjfhkbp8zvqqpj83g9v5b` dab-verify-stage-external-oracle-audit** — soft layer 2 (trace audit).
- This entity is layer 3 (hard network block). Can ship before or after the soft layers; defense in depth means all three layers active.

## Resume hook

When this lands, the leak-guard discipline reaches three layers: prompt deterrence + adversarial trace audit + hard network block. An agent that tries to cheat fails at every layer — prompt says "don't"; if they try, the trace audit catches and REJECTs; if they find a way past both, the network block makes the attempt itself fail. Trustworthy benchmark numbers without depending on opus-4.7+xhigh's good faith.
