# Phase 6 Follow-Up: Clean Canonical Spacedock Names Validation

Date: 2026-05-23
Branch: `spacedock-ensign/phase6-followup-clean-canonical-spacedock-names`
Validator: `spacedock-ensign`

## Gate Decision

PASSED. Approve to `done`.

AC-1, AC-2, and AC-3 reproduce independently on the worktree branch. The required full `uv run pytest` sweep was also run and currently fails during collection on `tests/unit/test_task_identity_scoring.py` because `razorback.score.load` is absent; the branch does not modify that test or `src/razorback/score`, so I classify it as an existing repo-wide test-suite issue rather than a blocker for this canonical-name cleanup.

## AC-1 — Active Code Uses Canonical Spacedock Solver Names

Verified by:

```bash
rg -n "V2|v2|spacedock_solver_v2" src/razorback tests examples --glob '!**/_legacy/**'
```

Output:

```text
tests/unit/test_spec_schema_spacedock_solver.py:46:    stale_kind = "spacedock_" + "solver_v2"  # intentional historical rejection assertion
tests/unit/test_spacedock_registry.py:70:    stale_kind = "spacedock_" + "solver_v2"  # intentional historical rejection assertion
tests/unit/test_spacedock_registry.py:118:        "spacedock_" + "solver_v2",  # intentional historical rejection assertion
```

Classification: PASS. All three remaining active code/test/example hits are intentionally split-string historical rejection assertions. No class, helper, constant, runtime path, active example, or active filename retains the stale `V2` / `v2` / `spacedock_solver_v2` name.

Filename check:

```bash
rg --files src/razorback tests examples | rg 'V2|v2|spacedock_solver_v2' || true
```

Output: no matches.

## AC-2 — Behavior Is Unchanged

Required acceptance command:

```bash
uv run pytest tests/unit/test_spec_schema_spacedock_solver.py tests/unit/test_translate_spacedock_solver_import_path.py tests/unit/test_spacedock_solver_class.py tests/unit/test_spacedock_solver_lifecycle.py tests/unit/test_runtime_adapters.py -q
```

Output:

```text
....................................                                     [100%]
36 passed in 0.48s
```

Supporting schema/freeze/generator/runtime suite:

```bash
uv run pytest tests/unit/test_seal_canonical_six_inputs.py tests/unit/test_spacedock_registry.py tests/unit/test_spec_freeze_cli_pkg8.py tests/unit/test_codex_benchmark_spec_generator.py tests/integration/test_spacedock_solver_freeze_dir_mechanism.py -q
```

Output:

```text
.......................................................                  [100%]
55 passed in 1.26s
```

Example/generator checkpoint:

```bash
uv run pytest tests/unit/test_codex_benchmark_spec_generator.py tests/integration/test_spacedock_solver_deterministic_smoke.py tests/integration/test_spacedock_solver_freeze_dir_mechanism.py -q
```

Output:

```text
.......................s...........                                      [100%]
34 passed, 1 skipped in 0.43s
```

Freeze smoke:

```bash
uv run rk freeze examples/specs/_codex-smoke.yaml --out /tmp/razorback-validation-codex-smoke.frozen.yaml --allow-missing
```

Output:

```text
wrote /tmp/razorback-validation-codex-smoke.frozen.yaml
wrote examples/specs/provenance.yaml
```

Classification: PASS. The focused acceptance suite and supporting freeze/generator/runtime checks pass. The temporary frozen spec and generated `examples/specs/provenance.yaml` sidecar were removed after validation.

Additional stage-required full sweep:

```bash
uv run pytest
```

Output excerpt:

```text
collected 616 items / 1 error

ERROR tests/unit/test_task_identity_scoring.py
ModuleNotFoundError: No module named 'razorback.score.load'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 1.76s
```

Classification: FAIL for the full repo sweep, non-blocking for this entity. `git diff main...HEAD -- tests/unit/test_task_identity_scoring.py src/razorback/score/load.py src/razorback/score` has no output, so the collection failure is outside the branch's changed surface.

## AC-3 — Docs Distinguish History From Active API

Active API grep:

```bash
rg -n "spacedock_solver_v2" README.md AGENTS.md docs/razorback-implementation \
  --glob '!docs/razorback-implementation/_archive/**' \
  --glob '!docs/razorback-implementation/validation/**' \
  --glob '!docs/razorback-implementation/plans/**' \
  --glob '!docs/razorback-implementation/_debriefs/**' \
  --glob '!docs/razorback-implementation/_evidence/**'
```

Output:

```text
docs/razorback-implementation/phase6-followup-clean-canonical-spacedock-names.md:28:Verified by: `rg -n "V2|v2|spacedock_solver_v2" src/razorback tests examples --glob '!**/_legacy/**'` returns only intentional historical assertions.
docs/razorback-implementation/phase6-followup-clean-canonical-spacedock-names.md:41:- DONE: Inventory active `V2` / `v2` / `spacedock_solver_v2` hits and classify cleanup targets versus intentional historical assertions.
docs/razorback-implementation/phase6-followup-clean-canonical-spacedock-names.md:54:- DONE: Active `V2` / `v2` / `spacedock_solver_v2` names are cleaned up from code/tests/examples except explicit historical rejection coverage.
docs/razorback-implementation/phase6-followup-clean-canonical-spacedock-names.md:55:  Evidence: `rg -n "V2|v2|spacedock_solver_v2" src/razorback tests examples --glob '!**/_legacy/**'` returns only three `stale_kind = "spacedock_" + "solver_v2"` assertions with inline historical-rejection comments.
docs/razorback-implementation/pkg22-provenance-writer-claude-cli-kind.md:5:source: Goal 2 T0 retry 2026-05-20 (worker observation on .worktrees/spacedock-ensign-goal2-ade-bench-haiku-baseline) — provenance writer at src/razorback/provenance/freeze_cmd.py:97-107 omits solver_workflow_hash / spacedock_skill_version / harbor_agent_kwargs_hash / tools_denied when agent kind != spacedock_solver_v2
```

Rationale:

- `phase6-followup-clean-canonical-spacedock-names.md` hits are this entity's AC text and prior stage reports quoting the required validation grep pattern.
- `pkg22-provenance-writer-claude-cli-kind.md:5` is YAML frontmatter `source` history. Ensign rules reserve entity frontmatter for first-officer state, and the body uses canonical `spacedock_solver` wording.
- `README.md` and `AGENTS.md` have no `spacedock_solver_v2` hits.

Broad active surface grep:

```bash
rg -n "V2|v2|spacedock_solver_v2" README.md AGENTS.md examples src/razorback tests --glob '!**/_legacy/**'
```

Output:

```text
tests/unit/test_spec_schema_spacedock_solver.py:46:    stale_kind = "spacedock_" + "solver_v2"  # intentional historical rejection assertion
tests/unit/test_spacedock_registry.py:70:    stale_kind = "spacedock_" + "solver_v2"  # intentional historical rejection assertion
tests/unit/test_spacedock_registry.py:118:        "spacedock_" + "solver_v2",  # intentional historical rejection assertion
```

Classification: PASS. Active examples, root README, AGENTS, `src/razorback`, and active tests have only intentional stale-discriminator rejection assertions.

## Code Review

Requested protocol: `superpowers:requesting-code-review`.

The skill is not registered as a callable Codex subagent/tool in this session. I read and applied the cached Superpowers instructions manually:

- `/home/exedev/.codex/.tmp/plugins/plugins/superpowers/skills/requesting-code-review/SKILL.md`
- `/home/exedev/.codex/.tmp/plugins/plugins/superpowers/skills/requesting-code-review/code-reviewer.md`

Review range: `main...HEAD` at `faf7a97`.

Blocking findings: none.

Non-blocking findings: none against this branch's changed surface. The repo-wide `uv run pytest` collection failure is recorded above as a pre-existing full-suite issue, not a code-review finding against this branch.

Assessment: Ready to merge. The implementation is a scoped canonical rename with matching schema/translate/freeze/runtime tests and explicit historical rejection coverage retained.
