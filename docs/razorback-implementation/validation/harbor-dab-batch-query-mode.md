# harbor-DAB batch query_mode — Validation Report

**Entity:** `docs/razorback-implementation/harbor-dab-batch-query-mode.md`
**Worktree:** `.worktrees/spacedock-ensign-harbor-dab-batch-query-mode`
**Branch:** `spacedock-ensign/harbor-dab-batch-query-mode`
**Reviewed commit:** `e1c9651` (impl) + `d1779b5` (impl stage report)
**Validator:** spacedock-ensign-harbor-dab-batch-query-mode-validation
**Date:** 2026-05-21

## Verdict: PASSED (conditional)

Material implementation is correct and matches the entity's 5 ACs.
Conditional on the same host-side docker-compose plumbing caveat already
acknowledged for PKG-15 / PKG-21 (live `rk run` aborts at `docker compose
up --project-name` due to an out-of-date compose shim picked up by harbor's
subprocess; orthogonal to query_mode shape).

## Checklist results

### 1. Unit tests on worktree

The dispatched form
`uv run pytest packages/razorback-plugin-dab/tests/ tests/` does not
work cleanly because the two test trees sit under two different
`pyproject.toml` rootdirs (the dab plugin has its own pyproject) and
pytest cannot reconcile them in a single invocation (31 collection
errors from rootdir confusion, not from test failures). Splitting into
two invocations against each root resolves cleanly:

- `uv run pytest packages/razorback-plugin-dab/tests/unit/` → **128 passed, 1 skipped** (matches impl report's 128/128).
- `uv run pytest tests/unit/` → **480 passed** (matches impl report's 480/480).
- `uv run pytest packages/razorback-plugin-dab/tests/unit/test_prepare_batch_query_mode.py` → 5/5.

Sole non-unit failure on this host:
`packages/razorback-plugin-dab/tests/integration/test_mongo_init_docker.py::test_mongo_init_shim_loads_bsondump_on_first_start`
fails with `count=-1` (mongo shim BSON-load loop). The failing test
was introduced at commit `06e094e` (PKG-15 AC-1 end-to-end). It is
mongo-init plumbing, unrelated to query_mode shape; the same docker
compose host shim that bites PKG-15 / PKG-21 live ACs is the proximate
cause. **No regressions attributable to e1c9651.**

→ **PASS** (with the noted runner-shape caveat for the combined
invocation form).

### 2. Materialized batch task tree (commit e1c9651)

Inspected `_runs/goal1-spacedock-bookreview/b05be787ec5037d3/tasks/bookreview/bookreview/`:

| Expected (AC-2) | Observed |
|---|---|
| task_dir = `<dataset>` (no `-q<n>`) | `bookreview/bookreview/` — task_name `bookreview` ✓ |
| workdir has `query1/query2/query3` sibling subdirs | `steps/main/workdir/{query1,query2,query3,query_dataset}/` ✓ |
| instruction enumerates queries | `instruction.md` — "Answer ALL of the following queries… Solve every query in this single agent turn", with `### query1/2/3` sections and `q1/q2/q3` answer-key contract ✓ |
| `verify_batch.py` present | `tests/verify_batch.py` ✓ |
| `validate_qN.py` present | `tests/validate_q1.py`, `validate_q2.py`, `validate_q3.py` ✓ |
| `stratum.json` carries `query_ids: [1,2,3]` | `{"stratum": {"dataset": "bookreview", "query_ids": [1,2,3], "backends": ["postgres","sqlite"]}}` ✓ |

Mechanism end-to-end (materialization) confirmed.

→ **PASS**

### 3. Code review (material vs polish)

Reviewed the substantive code surface of commit `e1c9651`:

- `src/razorback/spec/schema.py` (+1 line) — clean `Literal["batch", "per-query"]` field with back-compat default. AC-1 met.
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/cli.py` (+15 lines) — `--query-mode` flag with `QUERY_MODES` whitelist + early `Exit(code=2)` on unknown value. Mirrors existing flag validation style.
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py` (+313 lines) — adds `query_mode` kwarg + early validation + branched dispatch to new `_materialize_batch_task_dir`. The per-query path is untouched by construction (AC-3). The batch path mirrors the per-query materializer's structure but emits one task_dir whose workdir interleaves `query{N}/` siblings next to the shared `query_dataset/` payload. `_install_batch_validator` correctly rewrites the hardened-template's loader filenames so per-query upstream copies do not collide.
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/verify/verify_batch.py` (+90 lines, new file) — JSON-decode-safe, returns empty-dict on any read failure, defaults reward=0 on missing answer key, writes both `reward.json` (mean) and `reward_per_query.json` (per-q1/q2/q3 dict). Argparse CLI surface is clean.
- `src/razorback/benchmarks/dab/aggregate.py` (+76 lines) — `trial_name_map` union typed as `tuple[str, int] | tuple[str, list[int]]`; batch branch reads `<trial_dir>/steps/main/verifier/reward_per_query.json` (with `verifier/` fallback for single-step trials) and fans one trial into N outcomes. Missing-sidecar regression yields 0.0 per declared `query_id`. The `_resolve_key` return-type widening is consistent.
- `src/razorback/translate.py` (+49 lines) — forwards `--query-mode`. Under batch, walks `<task_dir>/steps/main/workdir/query{N}/` to populate the `(dataset, list[int])` map; under per-query the existing `task_name.rsplit("-q",1)` parsing is preserved.
- `examples/specs/goal1/*/*.yaml` — 36 specs gain `query_mode: batch` (3 variants × 12 datasets). Confirmed `examples/specs/goal1/spacedock/bookreview.yaml` carries `query_mode: batch` under `benchmark:`.

Material correctness: the contract handshake (plugin emits → translator emits list-keyed map → aggregator fans into outcomes → verifier sidecar provides the per-q reward dict) is symmetric and end-to-end testable. The TDD ordering matches the plan (T0 RED schema → T1 GREEN → T2 RED materialize → T3 GREEN → T4 RED aggregator → T5 GREEN → T6 specs).

Style: ABOUTME headers present on new files; no comments narrating refactoring or "new"/"improved" framing; no dead code.

→ **PASS**

## Findings

- **Known caveat (T7 live `rk run` blocker, NOT a defect of e1c9651):**
  Live execution against `examples/specs/goal1/spacedock/bookreview.yaml`
  aborts at environment setup with `docker compose ... up --detach --wait`
  → `unknown flag: --project-name`. Host docker compose v2 (2.36.2) works
  directly; harbor's subprocess sees an older shim. Identical failure mode
  recorded for PKG-15 and PKG-21 host-side live ACs. **Out of scope for
  this entity.** Materialized run-dir confirms batch shape end-to-end up to
  docker-compose-up.

- **Runner-shape caveat for the combined unit invocation:**
  `uv run pytest packages/razorback-plugin-dab/tests/ tests/` fails
  collection across two pyproject roots. Future stage definitions
  should split into two invocations against each root.

## Recommendation

Approve and merge. Cleanup of the cross-rootdir invocation can be a
follow-on doc tweak in the workflow stage definition if desired; it is
not a blocker for this entity.

- Verdict: **PASSED** (conditional on the host-infrastructure caveat
  shared with PKG-15 / PKG-21).
- Score: matches entity-frontmatter `score: 0.9` — material correctness
  high; the 0.1 reflects only the unverified live AC, which is
  infra-blocked, not implementation-blocked.
