# swe-bench-pro Leakage Probe Note (Task 0 evidence)

> Network-free probe. We CANNOT hydrate `scale-ai/swe-bench-pro`, so this
> records what is knowable offline, derives the STANDALONE curated deny-glob
> set, and pins the task-root-sibling-file assumption. The fixture models it.

## (a) SWE-bench-Pro instance format

Each SWE-bench-Pro instance carries (from the public dataset schema):
- a gold `patch` — the reference solution diff applied to the repo,
- a `test_patch` — the hidden grading tests applied on top,
- `FAIL_TO_PASS` / `PASS_TO_PASS` — JSON lists of test ids used by the verifier.

These are the answer/grading artifacts; an agent that reads them trivially
"solves" the task. They MUST NOT reach the agent-visible task view.

## (b) KEY fact — answer artifacts are TASK-ROOT sibling files

Harbor serializes these as sibling files at the TASK ROOT (next to the repo
checkout), NOT inside the repo the agent edits. E1's fixture already models
this with `solution/gold_patch.diff` at the task root. Consequence: the deny
set is **task-root-scoped and STANDALONE** — it never inherits the shared
`DEFAULT_SOLUTION_DENY_GLOBS` broad cross-`/` globs.

## (c) Why STANDALONE, not `DEFAULT + (...)` (fnmatch evidence)

`matches_denied_path` uses `fnmatch.fnmatch(rel_posix, pattern)`
(`src/razorback/harbor_tasks/leakage.py:21-23`), where `*` CROSSES `/`.
Reproduced offline:

```
True  '**/answer*'   'src/answer_engine.py'   <- legit nested repo file STRIPPED
True  '**/solution.*' 'pkg/solution.cfg'      <- legit nested repo file STRIPPED
True  '**/*answers*'  'config/myanswers_schema.json' <- legit nested repo file STRIPPED
False 'answer*'       'src/answer_engine.py'   <- root-anchored is SAFE
True  'answer*'       'answer.json'            <- still catches the task-root answer
```

swe-bench-pro tasks ARE real repos (django, astropy, sympy, …) that ship such
nested files. Inheriting the default's broad `**/answer*` / `**/solution.*` /
`**/*answers*` would corrupt the task. We therefore curate only ROOT-ANCHORED
globs (one path segment, no `**/`).

### The DERIVED STANDALONE set (becomes Task 1)

```
SWE_BENCH_PRO_DENY_GLOBS = (
    "solution/**", "solutions/**", "tests/expected/**",
    "solution.*", "answer*", "answers*",
    "gold/**", "gold_patch*", "gold.patch", "test_patch*",
    "FAIL_TO_PASS*", "PASS_TO_PASS*", "patch", "patch.diff", "solution.patch",
)
```

Verified live over 17 deny paths (all match) + 21 allow paths (all clean,
incl. `src/answer_engine.py`, `lib/myanswers.py`, `pkg/solution_helpers.py`).

## (d) Captain-verifiable assumption + root-token collision surface

- **Assumption (decision 1):** exact harbor answer filenames. We assume harbor
  lands `gold/`, `gold_patch.diff`/`gold.patch`, `test_patch.diff`,
  `FAIL_TO_PASS.json`, `PASS_TO_PASS.json`, and/or `patch`/`patch.diff`/
  `solution.patch`/`answer*` at the task root. If real filenames differ, the
  captain amends the root-anchored names before merge.
- **No blanket `**/*.patch` / `**/*.diff` (decision 2):** would strip legit
  repo fixtures (`docs/changelog.diff`, `lib/patches/*.patch`). Covered only by
  root-anchored answer names.
- **Root-token collision residual (decision 3):** root-anchored globs deny a
  TOP-LEVEL repo file with these prefixes (`answer*`, `answers*`, `gold_patch*`,
  `test_patch*`, `gold.patch`, `solution.*`, `patch`, `patch.diff`,
  `FAIL_TO_PASS*`, `PASS_TO_PASS*`). NESTED forms are NOT denied (proven in the
  allow-list test). Acceptable: answer data lives at the task root, repo source
  rarely does. Captain may narrow `answer*`→`answer.json` if a real task root
  collides.

## (e) Escalation decision

Patches are root sibling files → path globs are the correct defense → PROCEED.
The inline-patch HALT (decision 4) only triggers if real data shows the gold/
test patch lives inline in `task.toml` / verifier metadata / an env var. We
have no live data contradicting the sibling-file assumption, so we DOCUMENT the
assumption and proceed; no live hydration attempted. IF a future hydration
shows inline patches, that is a captain escalation (defense-in-depth audit
layer or a view content transform — both out of E2 scope), NOT an E2 code edit.
