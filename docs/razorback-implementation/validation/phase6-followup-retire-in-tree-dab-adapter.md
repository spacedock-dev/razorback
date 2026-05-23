# Validation: phase6-followup-retire-in-tree-dab-adapter

Validated at: 2026-05-23T05:56:10Z

Worker: `spacedock:ensign`
Role asset read: `/home/exedev/.codex/plugins/cache/spacedock/spacedock/0.12.0/skills/ensign/SKILL.md`
Worktree: `/home/exedev/razorback/.worktrees/spacedock-ensign-phase6-followup-retire-in-tree-dab-adapter`
Branch: `spacedock-ensign/phase6-followup-retire-in-tree-dab-adapter`
Reviewed range: `cdef366..0385e64`

## Worktree Baseline

Command:

```bash
git status --short --branch
```

Output:

```text
## spacedock-ensign/phase6-followup-retire-in-tree-dab-adapter
```

The worktree started clean. The `uv run` commands transiently removed the
`[options] exclude-newer` block from `uv.lock`; that tool-generated lockfile
churn was restored before writing validation artifacts.

## AC-1

Requirement: Active DAB specs route through the plugin-backed Harbor shape.

Verified by:

```bash
rg -n "razorback\.benchmarks\.dab|benchmarks/dab" src/razorback tests examples packages
```

Output:

```text
packages/razorback-plugin-dab/src/razorback_plugin_dab/verify/__init__.py:2:# ABOUTME: Ported from src/razorback/benchmarks/dab/verify.py.
```

Result: PASS.

Rationale: The only remaining hit is inside the plugin package and is an
ABOUTME provenance comment documenting the port source. There are no active
core, test, or example imports/usages of `razorback.benchmarks.dab`, and no
active `benchmarks/dab` path outside the allowed plugin-package reference.

## AC-2

Requirement: In-tree DAB adapter is legacy-only.

Verified by:

```bash
test -d src/razorback/benchmarks/dab
```

Output:

```text
<no stdout/stderr>
```

Exit code: `1`

Result: PASS.

Rationale: The required command exits non-zero because
`src/razorback/benchmarks/dab` no longer exists.

## AC-3

Requirement: DAB score/materialization tests still pass.

Verified by:

```bash
uv run pytest packages/razorback-plugin-dab/tests tests/unit/test_spec_harbor_dab_block.py tests/unit/test_generate_matrix_specs.py tests/unit/test_codex_benchmark_spec_generator.py -q
```

Output:

```text
Resolving despite existing lockfile due to removal of global exclude newer
.........................................s.............................s [ 43%]
........................................................................ [ 87%]
.....................                                                    [100%]
=============================== warnings summary ===============================
packages/razorback-plugin-dab/tests/integration/test_mongo_init_docker.py:30
  /home/exedev/razorback/.worktrees/spacedock-ensign-phase6-followup-retire-in-tree-dab-adapter/packages/razorback-plugin-dab/tests/integration/test_mongo_init_docker.py:30: PytestUnknownMarkWarning: Unknown pytest.mark.long - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = pytest.mark.long

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
163 passed, 2 skipped, 1 warning in 15.98s
```

Exit code: `0`

Result: PASS.

## Full Suite Check

The validation stage definition also calls for `uv run pytest` from the
worktree branch.

Command:

```bash
uv run pytest
```

Key output:

```text
collected 592 items
...
================ 580 passed, 12 skipped, 16 warnings in 33.83s =================
```

Exit code: `0`

Result: PASS.

## Run-Dir Contract

This entity's acceptance commands do not create a run directory or define any
new expected run-dir artifacts. No run result directories were removed. The
relevant artifact-bearing behavior remains covered by the full test suite,
including the existing run-dir artifact and runs aggregation tests that passed
in the full `uv run pytest` run above.

## Code Review

Required skill: `superpowers:requesting-code-review`.

The active Codex skill list did not expose a Superpowers `Skill` or `Task`
tool, so I read the installed skill and reviewer template from:

- `/home/exedev/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.7/skills/requesting-code-review/SKILL.md`
- `/home/exedev/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.7/skills/requesting-code-review/code-reviewer.md`

Then I ran the installed reviewer agent through the Claude CLI against the
implementation range:

```bash
claude -p --agent superpowers:code-reviewer --permission-mode bypassPermissions --tools "Bash,Read,Grep,Glob" --max-budget-usd 1 '<review prompt for cdef366..0385e64>'
```

Reviewer assessment: Ready for validation to done. No Critical findings.

Blocking findings:

- None.

Non-blocking Important findings:

- `src/razorback/_legacy/run.py:140`: the `_legacy` DAB branch still imports
  `DabBenchmarkBlock` from active schema and is now unreachable because active
  parsing rejects retired DAB kinds. This is legacy-only dead code and not an
  AC blocker.
- `src/razorback/spec/schema.py:91`: `DabBenchmarkBlock` remains importable
  from the active schema module for `_legacy` compatibility. The class is no
  longer part of the active `BenchmarkBlock` union, so this is symbol hygiene,
  not an active routing blocker.

Non-blocking Minor suggestions:

- Consider giving ADE Bench an ADE-owned default image name instead of the
  current `"dab-agent:latest"` literal.
- Tighten retired-kind parse assertions to inspect pydantic error structure
  instead of matching error-message substrings.
- Optionally encode the full AC-1 packages allowance in the static retirement
  unit test.
- Document that legacy `aggregate_synthetic` sidecar coverage is intentionally
  frozen under `_legacy`.
- If the implementation report cites full-suite results, include the exact
  full-suite command used.

## Gate Decision

PASSED.

All three acceptance criteria were independently reproduced from the assigned
worktree branch. The Superpowers code review found no blocking issues, and the
non-blocking findings are cleanup or hardening follow-ups outside this
validation gate.

## Completion Checklist

- DONE: AC-1 and AC-2 are independently verified with exact command results and rationale for any remaining allowed DAB hits.
  Evidence: AC-1 grep output has only the plugin-package ABOUTME port comment; AC-2 exited `1` with no stdout/stderr.
- DONE: AC-3 required pytest command is rerun and its actual result is recorded.
  Evidence: required pytest command exited `0` with `163 passed, 2 skipped, 1 warning in 15.98s`.
- DONE: Code review findings are classified as blocking or non-blocking, with a clear PASS/REJECTED gate recommendation.
  Evidence: Superpowers reviewer returned no Critical findings; non-blocking Important/Minor items are listed above; gate is PASSED.
