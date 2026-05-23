# Phase 6 Follow-Up: Clean Canonical Spacedock Names Validation

Date: 2026-05-23
Branch: `spacedock-ensign/phase6-followup-clean-canonical-spacedock-names`

## AC-1 Active Code/Test/Example Grep

Command:

```bash
rg -n "V2|v2|spacedock_solver_v2" src/razorback tests examples --glob '!**/_legacy/**'
```

Result: 3 hits, all intentional stale-discriminator rejection assertions.

```text
tests/unit/test_spec_schema_spacedock_solver.py:46:    stale_kind = "spacedock_" + "solver_v2"  # intentional historical rejection assertion
tests/unit/test_spacedock_registry.py:70:    stale_kind = "spacedock_" + "solver_v2"  # intentional historical rejection assertion
tests/unit/test_spacedock_registry.py:118:        "spacedock_" + "solver_v2",  # intentional historical rejection assertion
```

Filename check:

```bash
rg --files src/razorback tests examples | rg 'V2|v2|spacedock_solver_v2' || true
```

Result: no active file paths contain `V2`, `v2`, or `spacedock_solver_v2`.

## AC-2 Focused Behavior Checks

Required suite:

```bash
uv run pytest tests/unit/test_spec_schema_spacedock_solver.py tests/unit/test_translate_spacedock_solver_import_path.py tests/unit/test_spacedock_solver_class.py tests/unit/test_spacedock_solver_lifecycle.py tests/unit/test_runtime_adapters.py -q
```

Result: `36 passed in 0.66s`.

Supporting suite:

```bash
uv run pytest tests/unit/test_seal_canonical_six_inputs.py tests/unit/test_spacedock_registry.py tests/unit/test_spec_freeze_cli_pkg8.py tests/unit/test_codex_benchmark_spec_generator.py tests/integration/test_spacedock_solver_freeze_dir_mechanism.py -q
```

Result: `55 passed in 1.22s`.

Example/generator checkpoint:

```bash
uv run pytest tests/unit/test_codex_benchmark_spec_generator.py tests/integration/test_spacedock_solver_deterministic_smoke.py tests/integration/test_spacedock_solver_freeze_dir_mechanism.py -q
```

Result: `34 passed, 1 skipped in 0.40s`.

Freeze refresh:

```bash
uv run rk freeze examples/specs/_codex-smoke.yaml --out examples/specs/_codex-smoke.frozen.yaml --allow-missing
```

Result: exit 0; wrote `examples/specs/_codex-smoke.frozen.yaml`. The generated `provenance.yaml` sidecar was removed because it is a local freeze artifact.

## AC-3 Docs Grep Rationale

Active API grep:

```bash
rg -n "spacedock_solver_v2" README.md AGENTS.md docs/razorback-implementation \
  --glob '!docs/razorback-implementation/_archive/**' \
  --glob '!docs/razorback-implementation/validation/**' \
  --glob '!docs/razorback-implementation/plans/**' \
  --glob '!docs/razorback-implementation/_debriefs/**' \
  --glob '!docs/razorback-implementation/_evidence/**'
```

Result: no `README.md` or `AGENTS.md` hits. Remaining hits are:

- `docs/razorback-implementation/pkg22-provenance-writer-claude-cli-kind.md:5`: historical observation in YAML frontmatter `source`; not edited because ensign rules reserve entity frontmatter for first-officer state.
- `docs/razorback-implementation/phase6-followup-clean-canonical-spacedock-names.md:28,41`: this entity's acceptance criteria and plan-stage report quote the validation grep pattern.

Broad docs grep:

```bash
rg -n "V2|v2|spacedock_solver_v2" README.md AGENTS.md docs/razorback-implementation \
  --glob '!docs/razorback-implementation/_archive/**' \
  --glob '!docs/razorback-implementation/validation/**' \
  --glob '!docs/razorback-implementation/plans/**'
```

Result: remaining workflow `v2` hits are generic release/spec labels, protected historical debrief/evidence records, this task's own AC text, or YAML frontmatter source/title fields. Active README/AGENTS surfaces and actionable backlog ACs now name `spacedock_solver`.
