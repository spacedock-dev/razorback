# Staff SWE review of razorback v2

Date: 2026-05-20. Reviewer perspective: Staff SWE. Repo state: main after PKG-13 ship.

## TL;DR

The v2 architecture (`rk` as a thin pre-check/translate/delegate wrapper
around `harbor run`) is sound, and the freeze/budget/audit/score modules
are individually well-factored. But the canonical surface is in worse
shape than the recent debriefs suggest: **`rk freeze` is documented and
referenced in error messages but is not wired to the Typer app**, and
the v2 `cli/run.py` no longer writes the run-dir artifacts (`summary.json`,
`manifest.json`, `events.jsonl`, `per_trial_outcomes.json`, `lock.json`)
that `rk score`, `rk runs show`, `rk runs cost`, `rk runs diff`, and most
integration tests depend on. There is significant tombstone code:
22 unit-test files in a `collect_ignore_glob` blacklist, three empty
non-`_legacy` directories (`compat/`, `observers/`, `runtime/`) carrying
nothing but stale `.pyc` files, a v1 agent kind kept alive solely by
backwards-compat regression tests, and a parallel agent registry
(`agents/registry.py`) that no production code imports. PKG-12 and
PKG-13 closed real bugs but left the integration-test surface for the
in-tree DAB path silently broken on v2.

## Findings (classified)

### BLOCKER (should not ship to v2-canonical without addressing)

- **[F1]** *`rk freeze` is not wired into the Typer app.* Evidence:
  `src/razorback/cli/__init__.py:1-44` wires `run`, `audit`, `runs`,
  `constraints`, `baseline`, `registry`, `score` — but never imports
  or registers `freeze_command` from
  `src/razorback/provenance/freeze_cmd.py:33`. The only place
  `app.command("freeze")(freeze_command)` actually runs is
  `src/razorback/_legacy/cli/spec.py:8`, which is unreachable from
  the production CLI. The spec calls `rk freeze` a canonical
  subcommand (`docs/superpowers/specs/2026-05-19-razorback-on-harbor.md:21,
  "rk freeze | run | score | audit"`). The `cli/run.py` budget gate
  tells operators to "re-freeze with `rk freeze`"
  (`src/razorback/budget.py:106`). `uv run rk --help` does not list
  it. Fix: register `freeze_command` in `cli/__init__.py` (one line);
  delete `_legacy/cli/spec.py`.

- **[F2]** *v2 `cli/run.py` writes none of the run-dir artifacts that
  `rk score`, `rk runs show`, `rk runs cost`, and `rk runs diff`
  expect.* Evidence: `src/razorback/cli/run.py:139-312` produces only
  `spec.frozen.yaml`, `provenance.yaml`, and `_job_config.yaml`; it
  never writes `manifest.json`, `summary.json`, `events.jsonl`,
  `per_trial_outcomes.json`, or `lock.json`. Compare with
  `src/razorback/_legacy/run.py:91-162` which did (manifest, summary
  via `aggregate_job_result`, events via `EventChannel`). Concrete
  consequences:
    - `rk runs show` raises `FileNotFoundError` ("summary.json not
      found in <run-dir>") for every v2 run-dir
      (`src/razorback/runs/inspect.py:64-67`).
    - `rk runs list` filters out every v2 run-dir because
      `manifest.json` is missing
      (`src/razorback/runs/inspect.py:23-25`).
    - `rk runs diff` reads `per_trial_outcomes.json` which is never
      written by v2 (`src/razorback/diff/pairing.py:10-11`); the
      sidecar is only produced by
      `src/razorback/benchmarks/dab/aggregate.py:49,122` which is
      only invoked from `_legacy/run.py`.
    - The eight integration tests under `tests/integration/` that
      assert on `summary.json` / `manifest.json` are silently broken
      against v2 (e.g. `tests/integration/test_rk_run_nop.py:44-86`,
      `tests/integration/test_rk_run_bookreview_nop.py:40-77`).
  This was confirmed against a real v2 harbor_dab run-dir
  (`.runs/t14-harbor-dab-bookreview-n3/.../9c26daea1ada1c4d/`, which
  has `result.json`, `tasks/`, trial dirs, but no `manifest.json` or
  `summary.json`). PKG-14 / PKG-15 are queued, but this is more
  fundamental than either: v2 `rk run` does not produce the run-dir
  format the rest of the v2 CLI consumes.

- **[F3]** *22 unit-test files are silently skipped via
  `collect_ignore_glob`.* Evidence: `tests/conftest.py:14-39` lists
  21 ignore globs covering everything from `test_dab_translator*.py`
  (3 files) to `test_compat_translator.py`, `test_spec_freeze_cli*.py`,
  `test_baseline_promote_verify.py`,
  `test_cli_validate_per_trial_state_reset.py`,
  `test_constraints_check.py`, `test_run_drift_wired.py`,
  `test_translator_harbor_dab.py`. Most still import the moved
  `razorback.compat` module (`grep` finds 7 importers in `tests/unit/`).
  A spot-check (`uv run pytest --collect-only
  tests/unit/test_dab_translator.py`) returns
  `ModuleNotFoundError: No module named 'razorback.compat.harbor_0_6_6'`.
  Some files in the blacklist would actually still collect (e.g.
  `test_translator_harbor_dab.py` no longer imports `compat`); the
  blacklist is over-broad. Net effect: the test suite reports 452
  passing tests, but ~22 files of coverage are silently dropped. Fix:
  delete the test files whose subjects moved to `_legacy/` and which
  no longer correspond to a live code path; un-blacklist the rest
  and let them run.

### IMPORTANT (significant maintenance / clarity wins)

- **[F4]** *`src/razorback/agents/registry.py` is dead code.* Evidence:
  `grep -rn 'resolve_agent_kind\|AgentKindEntry\|AgentKindError'
  src/ tests/` shows zero production callers; only
  `tests/unit/test_claude_cli_registry.py` and
  `tests/unit/test_spacedock_registry.py` import it
  (`src/razorback/agents/registry.py:75-95`). The replacement
  mechanism — a pydantic discriminated union — lives at
  `src/razorback/spec/schema.py:93-101` and is what `translate.py`
  actually dispatches on. Confirmation that this registry is stale:
  `SpacedockSolverV2AgentBlock` was added to the discriminated union
  (`spec/schema.py:97-101`) but never registered in
  `agents/registry.py:75-85`. Fix: delete `agents/registry.py` and
  the two test files; the discriminated union is the source of truth.

- **[F5]** *Three empty directories under `src/razorback/` exist
  on disk only as `__pycache__` graveyards.* Evidence:
  `src/razorback/compat/`, `src/razorback/observers/`,
  `src/razorback/runtime/` each contain only a `__pycache__`
  subdirectory with stale `.pyc` files (e.g.
  `compat/__pycache__/harbor_0_6_6.cpython-312.pyc`). `git ls-files
  src/razorback/compat src/razorback/observers src/razorback/runtime`
  returns empty — these are untracked artifacts left behind when the
  modules were `git mv`'d to `_legacy/`. They shadow nothing today
  but actively confuse `grep`/`find` over the source tree. Fix:
  `rm -rf` the three directories and add the parent globs to
  `.gitignore` if not already.

- **[F6]** *Two parallel `SpacedockSolverAgent` classes (v1 and v2)
  with the same class name in different modules.* Evidence:
  `src/razorback/agents/spacedock_solver.py:39
  class SpacedockSolverAgent` and
  `src/razorback/agents/spacedock_solver_v2.py:40 class
  SpacedockSolverAgent`. Both are wired in:
  `src/razorback/translate.py:32-37` defines two import-path
  constants (`SPACEDOCK_SOLVER_IMPORT_PATH` and
  `SPACEDOCK_SOLVER_V2_IMPORT_PATH`); the spec discriminated union
  carries both `kind: "spacedock-solver"` and
  `kind: "spacedock_solver_v2"` (`spec/schema.py:39, 76`); the only
  thing keeping v1 alive is a regression test bundle
  (`tests/unit/test_v1_spacedock_solver_regression.py:1-91`).
  CLAUDE.md is explicit: "NEVER use temporal/historical context in
  names ... 'V2'", "If you name something 'new' or 'enhanced' or
  'improved', you've probably made a mistake and MUST STOP". The v2
  solver subsumes v1 (six-input sealed_hash vs four; runtime
  dispatch). Fix: pick one. Either (a) collapse the v1 class into
  v2 and drop the v1 spec-block / regression tests (the cleanest
  path given v1 has no production consumers in the workflow specs)
  or (b) rename the modules to describe what they do
  (`staged_solver.py` for v1, `runtime_dispatch_solver.py` for v2),
  not their phase ordering. Most likely correct answer is (a).

- **[F7]** *`benchmark.kind` has three overlapping spellings: `dab`,
  `in_tree_dab`, and `harbor_dab`.* Evidence: `spec/schema.py:110-131`
  declares two distinct discriminated blocks (`DabBenchmarkBlock` and
  `HarborDabBenchmarkBlock`); `spec/parse.py:13-18` adds a soft alias
  `in_tree_dab -> dab` that no one in the example specs uses except
  the now-orphaned `examples/specs/bookreview-claude-in-tree-dab.yaml`.
  The in-tree DAB translator path
  (`src/razorback/translate.py:67-77` + `benchmarks/dab/prepare.py`,
  237 LoC) duplicates concept-for-concept the plugin path
  (`packages/razorback-plugin-dab/.../generate/prepare.py`, 432 LoC):
  both materialize per-(dataset, query) harbor task dirs, both copy
  the same `_DATASET_SAFE` / `_QUERY_FORBIDDEN` lists, both write
  `task.toml` + `instruction.md` + `tests/verify.py` + `steps/main/`.
  The PKG-13 work that hardened the plugin's compose path (postgres
  reachability gate, bind-mount existence check, services sidecar)
  has no equivalent in the in-tree path — i.e. `kind: dab` and
  `kind: harbor_dab` now produce materially different task trees from
  identical spec semantics. Fix: declare the in-tree DAB path
  deprecated, file a deletion package, and drop `in_tree_dab` /
  `bookreview-claude-in-tree-dab.yaml` along with the alias.

- **[F8]** *`agents/_runtime/codex.py` and `agents/_runtime/pi.py`
  exist solely to raise `NotImplementedError`.* Evidence:
  `src/razorback/agents/_runtime/codex.py:5-10` and `pi.py:5-10`
  each define a single `build_inner_agent(**kwargs)` that raises.
  `spec/schema.py:77` accepts `runtime: Literal["claude", "codex",
  "pi"]` and `spacedock_solver_v2.py:200-209` upfront-imports all
  three adapters and dispatches through a `builders` dict. YAGNI:
  the `Literal` accepts codex/pi only to fail late in
  `_build_inner_agent`. Fix: make `runtime` a `Literal["claude"]`
  until a real codex/pi consumer arrives; delete the two stub
  files; collapse the three-way dispatch in `_build_inner_agent`
  to a direct `_claude.build_inner_agent(...)` call.

- **[F9]** *`spec/freeze.py::freeze_spec` is dead code in v2.*
  Evidence: `grep -rn 'from razorback.spec.freeze' src/`
  shows the only non-`_legacy` import is `cli/run.py:28` for
  `derive_job_name`. The actual v2 freeze entrypoint is
  `provenance/freeze_cmd.py::freeze_command` (which dispatches
  through `provenance/resolvers.py`). `freeze_spec()` only handles
  `SpacedockSolverAgentBlock` (the v1 shape) and is called only by
  tests and `_legacy/run.py`. Fix: either (a) merge `freeze_spec`'s
  spacedock-prompt-hashing logic into `provenance/freeze_cmd.py`
  and delete `spec/freeze.py`, keeping `derive_job_name` somewhere
  small; or (b) at minimum rename it to make clear it's a v1-only
  helper, and document that the v2 freeze path is in `provenance/`.

- **[F10]** *`ConstraintsFile` pydantic model is defined and
  exported but never validated against.* Evidence:
  `src/razorback/constraints/schema.py:7-12` defines a strict
  pydantic model. `src/razorback/constraints/__init__.py:5-7`
  re-exports it. `grep -rn 'ConstraintsFile\(' src/` returns zero
  hits. `src/razorback/cli/constraints.py:31` parses the
  constraints file with `yaml.safe_load` and passes a raw dict to
  `check_spec_against_constraints` (which itself only does
  `.get()` lookups). Fix: either validate constraints files
  through `ConstraintsFile.model_validate()` in `cli/constraints.py`
  (so unknown keys raise instead of silently no-op) or delete
  `ConstraintsFile`.

- **[F11]** *Tests in `unit/test_rk_run_v2_pre_checks.py` mock three
  module-private functions of `cli/run.py` simultaneously.*
  Evidence: `tests/unit/test_rk_run_v2_pre_checks.py:38-89` patches
  `razorback.cli.run._resolve_model_version`,
  `razorback.cli.run._run_canary`, and
  `razorback.cli.run._invoke_harbor` together for every test.
  This is the right shape for asserting exit-code wiring, but it
  pins the test to current private-function names; any refactor
  of `cli/run.py` breaks every test in the file. Combined with
  the F2 fact that no integration test actually exercises the
  real harbor subprocess + run-dir-write sequence on v2, the
  pre-check exit codes are the only thing currently verified.
  Fix: keep the patches (they're fine for unit tests of CLI
  wiring), but add at least one integration test that runs the
  nop spec against real harbor and asserts the v2 run-dir
  artifacts F2 names — i.e. fix F2 first, then the test gap.

- **[F12]** *`cli/run.py` mutates `os.environ` inside the request
  path.* Evidence: `src/razorback/cli/run.py:273-275`:
  ```
  for agent_cfg in job_config.agents:
      for env_key, env_val in (agent_cfg.env or {}).items():
          os.environ[env_key] = env_val
  ```
  The comment (266-272) explains why — harbor's
  `_serialize_env` only templatizes values that match
  `os.environ`. But mutating process state inside a sync command
  handler is a code smell: it leaks across the test boundary
  (a test running `rk run` against a spec with API keys will
  pollute `os.environ` for every subsequent test in the same
  process), and the value is the literal secret. Fix: build the
  harbor env explicitly via `{**os.environ, **agent_env}` and
  pass it to `_invoke_harbor`; do not mutate the parent process's
  `os.environ`. Looks like it can be done in 4 lines.

- **[F13]** *`_legacy/` is not inert — `_legacy/compat/__init__.py`
  imports the non-existent `razorback.compat.harbor_0_6_6`.*
  Evidence: `src/razorback/_legacy/compat/__init__.py:4`:
  `from razorback.compat.harbor_0_6_6 import spec_to_job_config`.
  But `razorback.compat` lives at
  `src/razorback/_legacy/compat/harbor_0_6_6.py` after the Phase 1
  move. The `_legacy/__init__.py` docstring claims "code here is
  importable for parity tests and rollback only"; that claim is
  false today. Same for `_legacy/run.py:11`. Fix: either delete
  `_legacy/` outright (Phase 7 already plans this per
  `docs/razorback-implementation/phase7-delete-legacy.md`) or
  rewrite `_legacy/compat/__init__.py` to import from
  `razorback._legacy.compat.harbor_0_6_6` so the rollback claim is
  honest.

### MINOR (nits, naming, would-be-nice)

- **[F14]** *`cli/__init__.py` does mid-module imports.* Evidence:
  `src/razorback/cli/__init__.py:21,25,29,33,37,41` interleaves
  `app.command(...)` calls with `from ... import ...` statements
  rather than collecting them at the top of the module. This is a
  cosmetic nit but it's the first thing a new contributor reads.

- **[F15]** *`benchmarks/dab/prepare.py:1-237` and
  `packages/razorback-plugin-dab/.../generate/prepare.py:1-432`
  share ~80% of their structure (the per-query loop,
  `_DATASET_SAFE`/`_QUERY_FORBIDDEN`, `_task_toml`,
  `_instruction`, `_test_sh`, `_toml_escape`, the workdir
  population). Once F7 is closed by deleting the in-tree path,
  this duplication evaporates.*

- **[F16]** *`audit/cli.py:13` redefines a `_TRIAL_SENTINELS` tuple
  to do trial-root discovery, parallel to
  `audit/subagent_traces.py::iter_trace_roots` (called inside
  `taint.discover_scan_inputs`).* The two walks have different
  semantics (one yields trial roots, the other yields trace roots
  inside an attempt), but the comment at `audit/cli.py:22-23`
  hedges ("Mirrors the upstream discover_scan_inputs semantics but
  operates one level up"). It would be clearer if the discovery
  primitive lived in `audit/subagent_traces.py` next to its
  sibling.

- **[F17]** *Names with implementation-detail or temporal context
  in test files:* `test_v1_spacedock_solver_regression.py`,
  `test_rk_run_v2_pre_checks.py`, `test_rk_run_v2_harbor_cache_dir.py`,
  `test_seal_v2_six_inputs.py`, `test_spec_schema_spacedock_solver_v2.py`,
  `test_spacedock_solver_v2_class.py`,
  `test_spacedock_solver_v2_lifecycle.py`. Per CLAUDE.md, "v2 (when
  v2 should be the canonical name now)" is a smell. If F6 is closed
  by collapsing v1+v2 into a single class, half these renames
  fall out for free.

- **[F18]** *`runs_dir_canary.py` sits at the package root rather
  than under `runs/` or `cli/`.* Evidence:
  `src/razorback/runs_dir_canary.py:1-68`. It's only imported by
  `cli/run.py:24-27`. Moving it under `cli/` or `runs/` would
  make the import tree match the directory structure.

- **[F19]** *`tests/integration/test_dab_workflow_lifecycle.py:43-49`
  calls `uv run rk validate <spec>` — `rk validate` is not a wired
  subcommand* (`rk --help` confirms). The test is skipped behind
  `RAZORBACK_RUN_DOCKER_TESTS=1` so it doesn't fail in CI, but
  anyone who flips the env var hits a USAGE error.

- **[F20]** *`docs/razorback-implementation/plans/` carries 20+
  plans from m1 through m7 plus phase1-phase8 plus pkg1-pkg13,
  all interleaved.* This is documentation sprawl that makes
  "what's the current state of the surface?" hard to answer.
  Recommend folding the m*/phase* plans into a single
  `docs/razorback-implementation/_archive/` once their entities
  ship (the pattern partially exists; the archive is empty of
  m*/phase* plans).

## Dead code candidates (with file:line)

| Path | Line range | Reason | Confidence |
|------|------------|--------|------------|
| `src/razorback/agents/registry.py` | 1-95 (whole file) | No production callers; superseded by `spec/schema.py` discriminated union; v2 agent kind missing | high |
| `src/razorback/agents/_runtime/codex.py` | 1-10 (whole file) | Only raises NotImplementedError; no consumer | high |
| `src/razorback/agents/_runtime/pi.py` | 1-10 (whole file) | Only raises NotImplementedError; no consumer | high |
| `src/razorback/constraints/schema.py::ConstraintsFile` | 7-12 | Defined + exported, never validated against anything | high |
| `src/razorback/compat/` (directory) | — | Empty; only stale .pyc files; untracked | high |
| `src/razorback/observers/` (directory) | — | Empty; only stale .pyc files; untracked | high |
| `src/razorback/runtime/` (directory) | — | Empty; only stale .pyc files; untracked | high |
| `src/razorback/_legacy/` (whole tree) | 885 LoC total | Phase 7 already plans deletion; `_legacy/compat/__init__.py:4` imports a non-existent module, so "rollback" claim is broken anyway | high |
| `src/razorback/spec/freeze.py::freeze_spec` | 13-31 | v2's actual freeze is in `provenance/freeze_cmd.py`; this is v1-only and only exercised by tests + _legacy | medium (callers in tests; `derive_job_name` lives in same file and IS used) |
| `src/razorback/benchmarks/dab/prepare.py` | 1-237 (whole file) | In-tree DAB path duplicates plugin path; only used by deprecated `kind: dab` / `in_tree_dab` benchmark block | medium (still wired through `translate.py:67`; deletion needs benchmark-block + alias removal first) |
| `src/razorback/benchmarks/dab/aggregate.py::aggregate_job_result` | 83-133 | Only called from `_legacy/run.py:143`; v2 `cli/run.py` never aggregates (which is bug F2) | medium |
| `src/razorback/benchmarks/ade_bench/aggregate.py::aggregate_job_result` | (same shape) | Only called from `_legacy/run.py:149` | medium |
| Tests in `tests/conftest.py:14-39` ignore-glob list | 21 globs | Most import the moved `razorback.compat`; tombstones from the Phase 1 move | high for the .compat ones; verify each |
| `tests/unit/test_v1_spacedock_solver_regression.py` | 1-91 | Sole consumer of v1 SpacedockSolverAgent | medium (depends on F6 decision) |
| `tests/unit/test_claude_cli_registry.py`, `test_spacedock_registry.py` | full files | Only consumers of dead `agents/registry.py` | high (paired with F4) |
| `examples/specs/bookreview-claude-in-tree-dab.yaml` | 1-19 | Sole user of `kind: in_tree_dab` alias | high (paired with F7) |
| `_runs/` (top-level, ungitignored) | — | Empty directory tracked from m1 scaffolding (`git ls-files _runs` returns nothing; `ls _runs/` returns nothing); the active runs root is `.runs/` per `cli/runs.py:25` | low (cheap to delete) |

## Patterns worth keeping (don't break these)

- *Discriminated-union spec schema.* `src/razorback/spec/schema.py:93-101`
  + `spec/schema.py:154-157` use pydantic `Annotated[Union[...],
  Field(discriminator="kind")]` to validate agent and benchmark
  blocks. Adding a kind is one block + one entry in the union; the
  translator's `isinstance(...)` chain in
  `src/razorback/translate.py:63-98` reads top-down. This is the
  right pattern; resist the temptation to layer a separate registry
  on top (see F4).

- *Typed errors → exit code mapping.* `src/razorback/errors.py:7-19`
  defines `ExitCode(IntEnum)`; every raise site uses
  `typer.Exit(exc.exit_code)`. Tests assert numeric codes directly
  (`tests/unit/test_cli_exit_codes.py`). Clean wire surface;
  protects backwards compat for downstream workflow consumers.

- *Dependency-injection on resolvers.*
  `src/razorback/provenance/resolvers.py` accepts callable factories
  for the docker probe, git runner, anthropic client, and entry-point
  lookup. Each resolver is a pure function with the externals
  injected. This is what lets the unit tests skip the real network /
  docker / git surface without resorting to `unittest.mock.patch`
  string spelunking.

- *PKG-13 lint-at-generation-time pattern.*
  `packages/razorback-plugin-dab/.../generate/prepare.py:297-316`
  reflects on harbor's `EnvironmentConfig.model_fields` and refuses
  to write a `task.toml` that carries `[environment]` keys harbor
  will silently drop. Cheap structural check that prevents the
  silent no-op class of bugs that motivated PKG-13. Keep.

- *Spec → harbor JobConfig is a single dispatching translator.*
  `src/razorback/translate.py:41-98` does the `if isinstance(spec.benchmark,
  LocalBenchmarkBlock): ... elif ...` walk in one place. Easy to
  read top-down; no factory/builder ceremony. F7's collapse of the
  in-tree DAB path will simplify this further.

## Surface metrics (informational)

- Total LoC, `src/razorback/`: 7373.
  - Non-`_legacy` v2 surface: 6488 LoC.
  - `_legacy/` holding tank: 885 LoC.
- Plugin LoC (`packages/razorback-plugin-dab/.../*.py`): 1103.
- Test files under `tests/`: 134 (113 unit + 18 integration + conftests).
  - Plugin tests: 23 files.
  - **22 test files in `collect_ignore_glob` blacklist (~16% of total)**.
- YAML spec files in `examples/specs/`: 18, ranging 13-56 lines (sum 460).
  - 8 use `kind: dab` (legacy in-tree).
  - 7 use `kind: harbor_dab` (current path).
  - 1 uses `kind: in_tree_dab` (alias; orphaned).
  - 1 uses `kind: ade-bench`. 1 uses `kind: local`. 1 frozen smoke.
- CLI subcommands and their option counts:
  - `rk run` — 4 options (`--runs-dir`, `--allow-alias-drift`,
    `--allow-plugin-drift`, `--max-budget-usd-running`).
  - `rk audit` — 2 options (`--policy`, `--format`).
  - `rk score` — 3 options (`--alpha`, `--format`, `--against-constant`).
  - `rk runs` — 4 subcommands: `list` (2), `cost` (2), `show` (0 +
    arg), `diff` (4).
  - `rk constraints check` — 2 options.
  - `rk baseline {promote, verify}` — 2 + 0 options.
  - `rk registry {list, resolve, add, remove}` — 0 options.
  - **`rk freeze` — declared in the spec, NOT WIRED** (see F1).
- ExitCode enum values: 11 distinct codes (0, 1, 2, 10-12, 20-24, 30).
- Largest non-`_legacy` files (LoC): `audit/taint.py` (569; ported
  verbatim from dataagentbench), `cli/run.py` (312),
  `agents/spacedock_solver.py` (315), `translate.py` (395),
  `agents/spacedock_solver_v2.py` (268), `budget.py` (274),
  `audit/subagent_traces.py` (237), `provenance/resolvers.py` (244).
  Nothing exceeds 600; mix-of-concerns is contained.
- Test-suite collection vs claim: pytest reports `452 tests collected`
  but the blacklist drops at least 21 files of unit tests for code
  that lives in `_legacy/` or has moved.
