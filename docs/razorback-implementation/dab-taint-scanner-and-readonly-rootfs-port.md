---

id: 8yb8fzx5549j8q1w23c7xbr9
title: Port DAB upstream's taint scanner + read-only rootfs + read-only DuckDB extension cache
status: backlog
source: '2026-05-23 7q validation cheating-audit finding + DAB upstream''s design at `~/git/dataagentbench/docs/harness/scored-run-egress-taint-and-duckdb-preinstall.md` (status `review` upstream, not yet shipped). The upstream design pairs the egress taint scanner with read-only rootfs + read-only DuckDB extension cache so attempt-time `pip install` / `INSTALL postgres` provably fail and any blocked attempt is recorded in `taint.json`. This is the structural-mechanism leak guard (vs prompt+trace which are soft layers). Auto-approve: false because it''s infrastructure-shaping; needs captain veto power.'
score: 0.85
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

Three soft layers of leak guard (sibling entities `k3` workspace-README prose + `wp` verify-stage audit + `wj` network block) deter / catch / hard-fail external lookups in different ways, but all three depend on context the agent OR the harness can in principle bypass:
- Prompt rule: agent must read + obey (opus-4.7+xhigh demonstrably can rationalize around it — see agnews)
- Trace audit: catches admitted attempts; an agent that omits its reasoning from logs might evade
- Network block: catches HTTP egress; pre-cached data inside the container image is still reachable

The structural fix is **read-only rootfs + sealed extension cache + per-attempt taint scanner emitting `taint.json`** — upstream's design at `~/git/dataagentbench/docs/harness/scored-run-egress-taint-and-duckdb-preinstall.md` (status `review`). Specifically:

- `/opt/dab/duckdb_extensions/duckdb-<ver>-<platform>-v1/` carries pre-approved extensions (`sqlite`, `postgres`, `mongo`), and `_duckdb_extension_dir(isolated=True)` points there. With read-only rootfs, attempt-time `INSTALL <ext>` provably fails — no race, no policy enforcement needed.
- `benchmark/lib/taint.py` scanner parses the per-attempt JSONL trace, categorizes findings into `public_egress` / `dynamic_install` / `answer_key_access`, emits `taint.json` (`schema_version: dab-taint-v1`) + `taint.md` per attempt root. Run-level summary fields in `summary.json` track `taint_status`, `clean_aggregate_score`, etc.
- `policy_mode` lever (`audit | taint | fail`) controls whether tainted runs are merely flagged, tainted-but-still-reported, or hard-failed at exit.

This entity ports the upstream design into razorback. Upstream isn't shipped, so we either fork it or contribute it back to dataagentbench — captain choice at plan-stage.

## Acceptance criteria

**AC-1 — `taint.py` scanner module exists in razorback (or in razorback-plugin-dab).**
A pure-function entry point `scan_attempt_taint(attempt_root: Path) -> TaintReport` that returns the upstream-design's `taint.json` shape: `schema_version`, `scanner_version`, `policy_mode`, `status`, `categories: {public_egress, dynamic_install, answer_key_access}` (each with `confirmed_count`/`suspected_count`/`suppressed_count`/`findings[]`), `findings[]` carrying `event_index`/`matched_text`/`normalized_target`/`snippet_sha256`/`rationale`, and `suppressed[]` for false-positives.
Verified by: unit tests against synthetic attempt roots covering public_egress (HF Hub fetch), dynamic_install (`pip install datasets`), answer_key_access (Read of `validate.py` / `ground_truth.csv`). Output JSON validates against upstream's schema if shipped; otherwise our schema doc.

**AC-2 — Read-only rootfs on dab-agent.**
The dab-agent docker run invocation includes `--read-only --tmpfs /tmp:size=512m` (mirrors upstream `run_experiment.py` flags). Attempt-time writes outside `/workspace` and `/tmp` fail. `pip install <anything>` fails at the filesystem layer with read-only fs error. Confirmed by smoke test inside the container.
Verified by: `docker run --rm --read-only --tmpfs /tmp:size=512m dab-agent:latest sh -c 'pip install --target /tmp/x rapidfuzz' 2>&1 | head` shows failure or success-into-/tmp (NOT into site-packages); `pip install <name>` without `--target` fails with read-only fs error.

**AC-3 — Read-only DuckDB extension cache baked into image.**
The dab-agent image carries `/opt/dab/duckdb_extensions/duckdb-<ver>-<platform>-v1/` with the three approved extensions pre-installed at build time. Per-cell DuckDB sessions point `extension_directory` at this path; `LOAD postgres` / `LOAD sqlite` / `LOAD mongo` succeed without `INSTALL`. Sibling entity `hb dab-agent-image-duckdb-extension-preinstall` (already in backlog) covers this — this entity coordinates with `hb` rather than redoing it.
Verified by: AC-2 of `hb`'s acceptance criteria.

**AC-4 — Per-cell `taint.json` + `taint.md` emitted alongside `provenance.yaml`.**
The matrix dispatcher (post sibling `wp` verify-stage hook + `ne`'s smoke-gate dispatcher pattern) invokes `scan_attempt_taint` after rk-run and emits the artifacts. `summary.json` carries the upstream-design's `taint_status` / `tainted_dataset_count` / `clean_aggregate_score` / `clean_stratified_score` roll-up fields.
Verified by: synthetic agnews-shaped trace produces `taint.json` with `categories.public_egress.confirmed_count >= 1` + named `huggingface.co` URL; clean cell produces `taint.json` with `status: clean`.

**AC-5 — `policy_mode` lever.**
Razorback's CLI (`rk run` or `rk audit`) accepts a `--taint-policy {audit|taint|fail}` flag mirroring upstream. `audit` mode logs but does not affect headline; `taint` mode flags affected cells in the captain-facing report; `fail` mode exits non-zero on any tainted cell. Default for paper-comparable runs: `taint`.
Verified by: dispatcher with `--taint-policy fail` against a synthetic tainted cell exits non-zero; `--taint-policy audit` exits 0 and writes the artifact only.

**AC-6 — Provenance pins the cache identity.**
Per-cell `provenance.yaml` records `duckdb_extension_cache: {duckdb_version, platform, cache_path, cache_version, approved_extensions, manifest_sha256}` per upstream design. When the image is unavailable (host mode), record `available: false` + `reason` rather than omit.
Verified by: provenance schema-test for the new fields against a real run and against a fixture host-mode run.

## Test plan

- **Mechanism gate first:** prototype `scan_attempt_taint` against the existing agnews trace (the cheating-confirmed cell from 7q). Must emit `public_egress.confirmed_count == 1` + the `huggingface.co` URL. Cheap; no infra changes.
- **Read-only rootfs smoke:** test that the dab-agent image runs cleanly under `--read-only --tmpfs /tmp:size=512m`. Validate that legitimate workloads (sqlite read, postgres ATTACH, agent writes to `/workspace`) still work. This is where the entity touches the most infrastructure surface.
- **Coordinate with `hb`:** sibling entity owns the extension cache; this entity owns the rootfs + scanner. Plan-stage decides whether `hb` ships first or alongside.
- **Live 4-cell sample:** confirm the new infra + scanner pass through clean cells and flag the planted-cheating cell.
- **Captain-facing report integration:** `summary.json` + the goal1-style report carry the `taint_status` + `clean_*` fields.

## Out of scope

- **Captain-side egress block.** This entity scopes to dab-agent containers.
- **Contribute the design back upstream.** If razorback ships this before upstream, captain may want a PR to dataagentbench. Plan-stage decision; not in this entity.
- **Network-layer block of huggingface.co.** Sibling entity `wj`. Both can land — they're complementary.
- **Workspace README leak-guard prose.** Sibling entity `k3`.
- **Verify-stage external-oracle audit.** Sibling entity `wp`. The scanner here is more comprehensive (3 categories, structured findings, policy lever); `wp`'s simpler audit is the cheap deterrent that runs even without the full taint infra.
- **Other workspace_variant naming.** Same as `k3`.
- **agnews-only re-run of 7q.** Sibling entity to file after the leak-guard quad lands.

## Depends on

- **`hb dab-agent-image-duckdb-extension-preinstall`** — read-only extension cache infra. Ideally `hb` ships first; this entity then coordinates the rootfs read-only + scanner.
- **`k3 dab-workspace-readme-leak-guard-prose-port`** — soft layer 1.
- **`wp dab-verify-stage-external-oracle-audit`** — soft layer 2. Shipped audit module can be reused by this entity's scanner as the `public_egress` detector subroutine.
- **`wj dab-net-block-huggingface-egress`** — hard layer 3. Network block is independent; both can ship.
- **Upstream design** at `~/git/dataagentbench/docs/harness/scored-run-egress-taint-and-duckdb-preinstall.md` (status `review`). If upstream ships first, this entity ports + integrates.

## Resume hook

When this lands, razorback's leak-guard discipline reaches structural-mechanism parity with DAB upstream's design — agents cannot install packages or download canonical datasets at attempt time without the act being recorded in `taint.json` + (in `fail` mode) the attempt itself crashing. Captain-facing reports surface taint status. Trustworthy benchmark numbers no longer depend on opus-4.7+xhigh's good faith OR on the captain catching the cheating manually OR on the prompt rule alone.
