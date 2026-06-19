---
id: h1cxe6x9zcyfq0zrs0rejsp7
title: spider2-dbt — user-facing example spec
status: validation
source: follow-up from spider2-dbt-source-resolution-and-run-wiring (no example exercises the new kind:harbor + qualified-ref path)
started: 2026-06-18T15:54:47Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-spider2-dbt-example-spec
issue:
pr: "#17"
mod-block: merge:pr-merge
---

## Problem

After `spider2-dbt-source-resolution-and-run-wiring` ships, no
user-facing example spec demonstrates the new capability:
`kind: harbor` + `dataset: spider2-dbt/spider2-dbt@1.0`. The only
existing spec, `examples/specs/pkg40-spider2-dbt-harbor-task-view-codex.yaml`,
uses `kind: harbor-local` pointing straight at a fixture dir, which
bypasses the dataset-resolution path; the qualified-ref form lives only
in an internal `nop`-agent test fixture. This task adds a real example
spec under `examples/specs/` so a user can see how to run the
spider2-dbt benchmark. A full run is gated on the PKG-40 harbor-package
checkout blocker, so the example documents that prerequisite and the AC
verifies what is checkable offline (schema-valid + freezes).

## Acceptance criteria

**AC-1 — A `kind: harbor` spider2-dbt example spec exists and freezes cleanly.**
Verified by: `uv run rk freeze examples/specs/<name>.yaml` exits 0 and
writes `examples/specs/<name>.frozen.yaml` with
`benchmark.dataset == "spider2-dbt/spider2-dbt@1.0"`.

**AC-2 — The example records the `spider2-dbt@1.0` hydration prerequisite for a full run.**
Verified by: `grep -F 'spider2-dbt@1.0' examples/specs/<name>.yaml` returns
the header note naming the harbor-package hydration step (the PKG-40
blocker), so the user knows what a live run requires.

## Test plan

A unit/integration check that the example freezes (AC-1); confirm the
frozen dataset ref is the qualified form. No live run is attempted while
the PKG-40 blocker stands.

## Out of scope

Unblocking the `spider2-dbt@1.0` harbor-package checkout (PKG-40,
externally owned). The dbt-deps/preflight parity, the verifier, and the
scored-run task-identity reconciliation (their own entities).

## Implementation plan (inline — TINY, 2 ACs, single-file deliverable)

### Deliverable

One new example spec at `examples/specs/spider2-dbt-harbor-codex.yaml`
(filename chosen to mirror the sibling `ade-bench-harbor-dataset-codex.yaml`
naming: `<bench>-harbor-<runtime>` ; it is the `kind: harbor` qualified-ref
counterpart to the existing fixture-backed `pkg40-spider2-dbt-harbor-task-view-codex.yaml`).
No production code changes. Plan stays on `main` (no worktree).

### Spec shape (pinned)

The spec MUST use the qualified-ref resolution path, NOT `harbor-local`:

```yaml
benchmark:
  kind: harbor
  dataset: spider2-dbt/spider2-dbt@1.0
```

This is the form that today lives only in the internal nop-agent fixture
`tests/fixtures/spider2_dbt/specs/spider2-dbt-fixture.frozen.yaml`. Schema
(`HarborBenchmarkBlock`, `src/razorback/spec/schema.py:169`) requires the
fully-qualified `<org>/<name>@<ref>` form when `plugin:` is unset — parse-time
validation is a pure string parse (`PackageReference.parse`), no network.

Agent block: use a real runtime agent (`kind: codex`, `model: gpt-5.5`) to
mirror the sibling ade-bench harbor example and make the example user-facing
(not a nop). Two leading `# ABOUTME:` comment lines per the repo convention,
the second of which carries the AC-2 header note (see below).

### Mechanism finding (de-risks AC-1 — verified empirically this stage)

`rk freeze` does NOT download the harbor dataset. Dataset resolution
(`_resolve_harbor_dataset_tasks` → `PackageDatasetClient.download_dataset`,
`src/razorback/translate.py:516`) happens only at **run/translate** time, which
is the PKG-40-blocked path and is out of scope. `freeze_command`
(`src/razorback/provenance/freeze_cmd.py`) writes `benchmark.dataset` verbatim
via `spec.model_dump` and only pins provenance fields. So freezing a
`kind: harbor` spider2-dbt spec is fully checkable offline and the frozen
`benchmark.dataset` is the verbatim qualified ref — exactly AC-1's check.

CAVEAT (flag for validation stage): plain `uv run rk freeze <spec>` exits
**11** in an offline environment with no `ANTHROPIC_API_KEY`, because
`resolve_model_version` can't resolve the model alias and
`refuse_if_any_unresolved` rejects the missing `model_resolved_version`. This
was reproduced this stage against both a probe spec AND the existing
`examples/specs/ade-bench-claude.yaml` (both exit 11 offline). The
committed `*.frozen.yaml` files were produced with API/network access.
Per the ensign "no hidden machine dependencies" rule, the offline-reproducible
AC-1 verify command is `uv run rk freeze <spec> --allow-missing` (exits 0;
the frozen `benchmark.dataset` is identical either way). The entity's AC-1 text
says plain `rk freeze ... exits 0` — validation should accept `--allow-missing`
as the offline-honest form, or run plain freeze in an environment with
`ANTHROPIC_API_KEY` set. This is the single open decision for the captain/FO.

### Steps (map 1:1 to ACs)

1. **AC-2 first (cheap, no tooling):** Author `examples/specs/spider2-dbt-harbor-codex.yaml`
   with the `kind: harbor` + `dataset: spider2-dbt/spider2-dbt@1.0` block and a
   header `# ABOUTME:` note that literally contains `spider2-dbt@1.0` and names
   the harbor-package hydration prerequisite / PKG-40 blocker for a live run.
   Proof: `grep -F 'spider2-dbt@1.0' examples/specs/spider2-dbt-harbor-codex.yaml`
   returns the header note line.
2. **AC-1 (riskiest contract — freeze resolves to the qualified ref):**
   Run `uv run rk freeze examples/specs/spider2-dbt-harbor-codex.yaml --allow-missing`
   (offline-reproducible form; see caveat). Proof: exits 0 and writes
   `examples/specs/spider2-dbt-harbor-codex.frozen.yaml` whose
   `benchmark.dataset == "spider2-dbt/spider2-dbt@1.0"`. Commit BOTH the source
   spec and the `.frozen.yaml` (the repo convention commits frozen siblings).
3. **No live run** while PKG-40 stands — `rk run` would trigger the blocked
   dataset download; do not attempt it.

### Files to touch

- ADD `examples/specs/spider2-dbt-harbor-codex.yaml` (source spec)
- ADD `examples/specs/spider2-dbt-harbor-codex.frozen.yaml` (freeze output of AC-1)
- (a `provenance.yaml` sibling is also written by freeze under `examples/specs/`;
  the implementation stage decides whether to commit/ignore it — existing
  `examples/specs/provenance.yaml` precedent exists)

### Spec §-cites / source references governing each step

- Qualified-ref requirement + parse validation: `HarborBenchmarkBlock`
  `src/razorback/spec/schema.py:169-228`
- Freeze writes dataset verbatim, no download: `freeze_command`
  `src/razorback/provenance/freeze_cmd.py:35-122`
- Dataset download is the run-time (PKG-40-blocked) path:
  `_build_harbor` / `_resolve_harbor_dataset_tasks` `src/razorback/translate.py:299-569`
- Qualified-ref precedent (internal only today):
  `tests/fixtures/spider2_dbt/specs/spider2-dbt-fixture.frozen.yaml`,
  `tests/unit/test_translate_spider2_dbt.py:61`
- Sibling shape to mirror: `examples/specs/ade-bench-harbor-dataset-codex.yaml`

## Stage Report: plan

- DONE: Map both ACs 1:1 to the example-spec file + offline checks: AC-1 (`uv run rk freeze examples/specs/<name>.yaml` exits 0 and writes <name>.frozen.yaml with benchmark.dataset == "spider2-dbt/spider2-dbt@1.0"), AC-2 (`grep -F 'spider2-dbt@1.0'` returns a header note naming the harbor-package hydration prerequisite / PKG-40 blocker)
  Inline plan steps 1-2 map AC-2→header-note authoring and AC-1→`rk freeze` (frozen `benchmark.dataset` verbatim); freeze path verified to NOT download the dataset (`freeze_cmd.py` vs run-time `translate.py:516`).
- DONE: Pick the example filename under examples/specs/ and pin the spec shape: kind: harbor + dataset: spider2-dbt/spider2-dbt@1.0 (the qualified-ref path), NOT kind: harbor-local — mirror the qualified-ref form currently living only in the internal nop-agent test fixture. Note the no-live-run-while-PKG-40-blocked constraint.
  Filename `examples/specs/spider2-dbt-harbor-codex.yaml`; shape pinned to `kind: harbor` + qualified ref mirroring the nop fixture; step 3 forbids the live run while PKG-40 stands.

### Summary

Tiny inline plan for one new `kind: harbor` + `dataset: spider2-dbt/spider2-dbt@1.0`
example spec under `examples/specs/`, exercising the qualified-ref resolution path
the existing `harbor-local` example bypasses. Verified empirically that `rk freeze`
writes the dataset ref verbatim without any network download (the PKG-40-blocked
download is a run-time-only path), so AC-1 is offline-checkable. One open decision
flagged for validation/captain: plain `rk freeze` exits 11 offline with no
`ANTHROPIC_API_KEY` (reproduced against an existing example too), so the
offline-reproducible AC-1 command is `rk freeze --allow-missing` — the frozen
`benchmark.dataset` is identical either way.
