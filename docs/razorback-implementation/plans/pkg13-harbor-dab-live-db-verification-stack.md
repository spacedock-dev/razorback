# PKG-13: harbor-DAB live-DB verification stack (Phase 2 + Phase 4a remediation), Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Entity:** `docs/razorback-implementation/pkg13-harbor-dab-live-db-verification-stack.md`
(id `bafje0bpa1c8jvz9vtbs2q5q`).

**Goal.** Make the bookreview live-DB benchmark actually run against a
live postgres. Today the harbor-DAB plugin authors a `docker-compose.yaml`
that harbor never opens, so postgres never starts; the agent falls back to
parsing the seeded `books_info.sql` dump in Python, and substring-only
validators accept the resulting answers as correct. T14 reported 9/9
pass@1=1.0 from this configuration. PKG-13 fixes the four shipped bugs in
the plugin plus the verifier weakness that turns silent-broken into
silent-green, and re-runs T14 to produce honest numbers.

**Source of truth.** The investigation at
`docs/superpowers/plans/2026-05-20-t14-false-positive-investigation.md`
(commit `561f1c1`) with file:line evidence for each of the four layered
bugs and the validator substring leak. The v2 spec at
`docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` covers the
benchmark-adapter framing in §2 + §3 + §8.4 and the run-dir contract in
§7. Inherited adapter design from the phase2-dab-harbor-adapter plan; T7
named (but did not implement) the bookreview reachability gate.

**Harbor contract verification (mechanism check first).** Before any
implementation, this plan's first task verifies harbor's
`EnvironmentConfig` shape end-to-end against the running pinned harbor
package, not from memory:

1. `EnvironmentConfig` at
   `.venv/lib/python3.12/site-packages/harbor/models/task/config.py:127-170`
   has no `docker_compose` field. Fields are: `build_timeout_sec`,
   `docker_image`, `os`, `cpus`, `memory_mb`, `storage_mb`, `gpus`,
   `gpu_types`, `allow_internet`, `mcp_servers`, `env`, `skills_dir`,
   `healthcheck`, `workdir`, plus deprecated `memory` / `storage`. The
   plugin's `[environment].docker_compose = "docker-compose.yaml"` line in
   the emitted `task.toml` is silently dropped by pydantic.
2. Harbor's compose discovery at
   `.venv/lib/python3.12/site-packages/harbor/environments/docker/docker.py:249-301`
   hard-codes `environment_dir / "docker-compose.yaml"` (i.e.
   `<task-dir>/environment/docker-compose.yaml`) as the only task-author
   override slot.
3. Therefore the plugin must write the generated compose to
   `<task-dir>/environment/docker-compose.yaml`, and the bind-mount
   sources in that compose are resolved relative to the file, i.e.
   relative to `<task-dir>/environment/`.

T0 below codifies this as an executable assertion so the rest of the
plan's task order is defensible: if harbor changes shape between now and
implementation, T0 fails first.

**AC-to-task map.**

| AC | Task(s) | Spec / investigation cite |
|----|---------|----------------------------|
| AC-1 (compose at harbor location) | T1, T2 | invest. cause-1; harbor docker.py:249-251 |
| AC-2 (compose loading observable) | T3, T4 | invest. cause-1; harbor docker-compose project_config_files label |
| AC-3 (reachability fail-fast gate) | T5, T6 | invest. cause-4; T7 originally promised this |
| AC-4 (bind-mount path correctness) | T1, T2, T7 | invest. cause-3 |
| AC-5 (validator substring-leak hardening) | T8, T9 | invest. cause-5; spec §8.4 reward shape |
| AC-6 (T14 re-run produces honest numbers) | T10, T11 | entity body |

**Task ordering rationale (riskiest mechanism first).**

T0 verifies the harbor contract; if it fails, the rest is invalidated.
T1 to T4 land AC-1 and AC-2 together because they share the same fix
boundary (compose location + an observable loading event). T5 to T6 land
AC-3 on top of an actually-loaded compose so the gate has something to
gate on. T7 closes AC-4's bind-mount path bug as a small follow-on inside
T1's same module. T8 to T9 land AC-5 independently of the live-DB plumbing
because it's a verifier-side change and decouples from the docker stack.
T10 to T11 are the AC-6 re-run on the assembled stack. The re-run is the
smoke that proves AC-1 to AC-5 work end-to-end, and it must come last.

**Out-of-scope, deliberately deferred.**

- Cause-6 from the investigation (`/logs/artifacts` empty, no
  host-visible `answers.json`) is a debuggability problem rather than a
  correctness problem; filed separately rather than bundled into PKG-13.
- Re-running T15 (12-dataset matrix) and Goals 1+2 follow PKG-13's
  shipment per the entity's "blocks" list.
- Generalizing the bookreview reachability gate to ade-bench shape is
  Goal 2's blocker; not addressed here.

## Tasks

### T0: Harbor contract assertion (mechanism check)

**Spec.** Harbor's `EnvironmentConfig` and `_environment_docker_compose_path`
behavior, as observed at the pinned harbor version.

- [ ] Add `packages/razorback-plugin-dab/tests/unit/test_harbor_contract.py`
  with two failing tests:
  1. `test_environment_config_has_no_docker_compose_field`: assert
     `"docker_compose" not in EnvironmentConfig.model_fields`.
  2. `test_environment_docker_compose_path_is_environment_dir`: import
     `harbor.environments.docker.docker.DockerEnvironment`, inspect the
     `_environment_docker_compose_path` property source, and assert it
     returns `environment_dir / "docker-compose.yaml"`.
- [ ] Both pass on first run against the pinned harbor in `.venv/`.
- [ ] Commit message names this as the harbor-shape contract check that
  guards T1-T2.

This task is small but critical: it prevents a silent harbor upgrade
from re-introducing the silent-drop failure mode.

### T1: Move compose write to `environment/docker-compose.yaml` (AC-1, AC-4)

**Module.** `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py:137`
(compose write), and
`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py:54,63`
(bind-mount source paths).

- [ ] Failing test 1 (unit, `test_prepare_per_query.py`): assert
  `<task_dir>/environment/docker-compose.yaml` exists after
  `prepare_dataset_tasks` for a bookreview-shaped fixture, and
  `<task_dir>/docker-compose.yaml` does NOT exist.
- [ ] Failing test 2 (unit, `test_compose_postgres.py`): with the new
  compose location, parse the generated YAML and assert the `dab-postgres`
  volume `src` resolves (after `Path(compose_file).parent / src`) to an
  existing file on disk for the fixture. The expected source is
  `../steps/main/workdir/{sql_file}`.
- [ ] Implementation: change `prepare.py:137` to write
  `(task_dir / "environment" / "docker-compose.yaml")`. Change
  `compose.py:54,63` to emit `../steps/main/workdir/{sql_file}` /
  `../steps/main/workdir/{dump_folder}` for the postgres init volumes and
  mongo init volumes respectively (the path is now relative to
  `environment/docker-compose.yaml`, one directory deeper than before).
- [ ] Remove the now-dead `[environment].docker_compose =
  "docker-compose.yaml"` line from `_task_toml()` at
  `prepare.py:223-224`. This line is a no-op because harbor's
  `EnvironmentConfig` has no such field (verified in T0).
- [ ] Update any sibling unit tests that asserted the old root-level
  compose path. Existing tests in `test_prepare_per_query.py` and
  `test_compose_postgres.py` are the primary sites.

### T2: Generator-side schema lint for `task.toml` (AC-1 guard)

**Goal.** Prevent any future un-honoured `[environment].*` keys from being
emitted into a generated `task.toml` and silently dropped by harbor's
pydantic parse.

- [ ] Failing test (unit, `test_prepare_per_query.py`): import
  `TaskConfig` from harbor and assert that
  `TaskConfig.model_validate_toml(<generated task.toml>)` round-trips with
  `model_extra is None or empty`. With T1 done, this should pass once the
  dead `docker_compose` line is removed.
- [ ] Implementation: add a small helper in `prepare.py` that calls
  `TaskConfig.model_validate(...)` (or `model_validate_strict`) after
  generating the `task.toml` text and raises a `ComposeError` (or new
  `TaskTomlError`) on extra keys. Wire it into `prepare_dataset_tasks` as
  a post-write check.

This task makes future schema-drop bugs land at generation time, not run
time.

### T3: Compose-loading observability sidecar (AC-2)

**Goal.** Make compose loading an observable event at trial run time,
independent of structural inference.

- [ ] Failing test (integration,
  `packages/razorback-plugin-dab/tests/integration/test_compose_loaded_event.py`):
  after a `prepare_dataset_tasks` + a `docker compose -f
  <env-compose> config --services` shell-out on a synthetic
  bookreview-shaped fixture, assert the listed services include
  `dab-postgres` and `main`. This is the static check (b) from AC-2.
- [ ] Implementation: keep this lightweight. Add a small helper in
  `prepare.py` (or a new `verify_compose.py` module) that records, per
  task dir, a `<task-dir>/environment/.compose-services.json` sidecar
  enumerating the services the generator emitted. The bookreview
  reachability gate (T5-T6) and the AC-6 re-run validator both read this
  to confirm what was supposed to be running.
- [ ] The runtime side of AC-2 (compose-up event in `events.jsonl`) is
  satisfied by T5's gate, which logs a typed event when it runs.

### T4: Live `docker compose config` verification in tests (AC-2 runtime)

**Goal.** Add a single integration test that, against the
plugin-generated tree (no real DB up), runs
`docker compose -f <task-dir>/environment/docker-compose.yaml config -q`
and asserts exit 0. This catches bind-mount path resolution at compose
parse time without spinning up real containers.

- [ ] Failing test (integration,
  `tests/integration/test_compose_parses.py`): runs the docker CLI as a
  subprocess against a fixture task tree; skips with a clear message if
  `docker` is not available in CI; asserts exit 0 when it is.
- [ ] Implementation: pure test code. Catches T1's bind-mount path fix
  end-to-end without depending on a postgres image pull.

### T5: Bookreview reachability gate, plugin side (AC-3)

**Module.** New
`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/reachability.py`
plus a hook into `prepare.py` so the gate is wired per task that has a
postgres service.

**Strategy.** Harbor exposes `StepConfig.healthcheck`
(`.venv/lib/python3.12/site-packages/harbor/models/task/config.py:273-280`)
as a per-step healthcheck that runs after setup and before the agent. Use
it to run a `psql` reachability probe inside `main`. On healthcheck
failure, the step aborts cleanly with a typed error, which is exactly the
AC-3 "fail-fast" shape.

- [ ] Failing test (unit, `tests/unit/test_reachability_gate.py`):
  prepare a bookreview-shaped task and assert the generated `task.toml`
  contains a `[[steps]]` `healthcheck` block whose `test` array includes
  `psql -h dab-postgres -U dabench -d bookreview_db -tAc 'select count(*)
  from books_info'`.
- [ ] Failing test (unit, same file): for a sqlite-only dataset (e.g.
  `query_sqlite_*`), the same generator does NOT emit a healthcheck (gate
  is postgres-conditional).
- [ ] Implementation:
  1. Pass the parsed `db_config` (already loaded in `prepare.py:65-66`)
     into the task.toml generator.
  2. When `db_clients` includes a postgres client, append a step
     `healthcheck` block to `_task_toml` with the `psql` test command
     above, an `interval_sec` of `5`, `start_period_sec` of `30`, and
     `retries: 6`.
- [ ] The agent container must be able to run `psql`. The `dab-agent:latest`
  image already includes the postgres client (per upstream DAB Dockerfile);
  T0's mechanism check should add a one-line assertion that the docker
  image in use has `psql` on `$PATH`. If not, T5's implementation also
  adds it to the image build, which is a separate small change in the
  ade-bench-agent image entity (PKG-10) that already exists.

### T6: Reachability-gate negative test (AC-3 verified-by)

**Goal.** Synthetic test where postgres init script is mis-configured and
the gate exits non-zero with a clean error.

- [ ] Failing test (integration, `tests/integration/test_reachability_gate_fails.py`):
  generate a bookreview task tree, then corrupt the `books_info.sql` to
  `SELECT 1/0;` (a runtime error during init), bring the compose stack
  up via `docker compose up --wait`, run the healthcheck command against
  the `main` container, and assert exit code non-zero and stderr contains
  `psql` / connection failure text.
- [ ] Implementation: pure test code; no production-code change.
- [ ] Skipped in CI when `docker` is unavailable; runs locally on
  Colima. Failures here mean the gate isn't actually wired into harbor's
  step lifecycle; if so, fall back to a pre-agent shell hook in
  `_test_sh` (`prepare.py:257-267`) that runs the same psql command and
  exits non-zero on failure.

### T7: Bind-mount source-file existence post-generate check (AC-4)

**Goal.** Catch any future regression where the compose bind-mount source
path resolves to a missing host file.

- [ ] Failing test (unit, `test_prepare_per_query.py`): after
  `prepare_dataset_tasks` on a bookreview fixture, iterate the parsed
  `environment/docker-compose.yaml`, resolve every `volumes[].src` against
  the compose file's parent, and assert each resolved path exists as a
  file or directory on the host.
- [ ] Implementation: add a tiny helper `_check_compose_volumes(task_dir:
  Path)` in `prepare.py`, called at the end of `_materialize_task_dir`.
  Raise `ComposeError` on any missing source.

This is the post-generate gate the investigation's fix-scope table
(cause-3) called out.

### T8: Validator hardening, q1 quantitative check (AC-5)

**Strategy.** The investigation found q1's validator accepts any string
containing `"2020"`. The hardening approach for q1 is **bounded-answer +
exact-decade match**: the validator parses the agent's answer for a
4-digit year (or 4-digit-plus-`s` decade), normalizes it, and compares
equality to the ground-truth decade. Substring is replaced with
"interprets the answer as a decade and that decade equals the ground
truth".

This is narrower than "force a DB query" but it's the smallest change that
closes the substring leak for q1 without changing what counts as a
correct answer.

- [ ] Failing tests (unit,
  `packages/razorback-plugin-dab/tests/unit/test_validator_q1_hardening.py`):
  six cases against the q1 validator-replacement:
  1. `"2020s"` → True (the canonical correct shape).
  2. `"the 2020s decade"` → True.
  3. `"2020"` alone → True (acceptable variant).
  4. `"2020-01-01"` → False (date, not a decade).
  5. `"02020"` → False.
  6. `"Around the World Mazes... published in 2020"` → False (substring
     leak from the SQL dump; an essay-style answer that quotes a year
     should not pass).
- [ ] Implementation: add a hardened q1 validator in
  `packages/razorback-plugin-dab/src/razorback_plugin_dab/verify/validators/bookreview_q1.py`
  that parses the answer as a `4-digit year[s]?` token after stripping
  surrounding whitespace and accepts only when the parsed decade exactly
  equals the ground truth (`"2020"` / `"2020s"`). When `prepare.py`
  materializes a bookreview-q1 task it copies this hardened validator
  into `tests/validate.py` instead of (or as a wrapper over) the
  upstream-vendored one.
- [ ] The wrapper approach (call the upstream validator first, then
  apply the bounded-answer check on top) is preferred over a full replace:
  it's a single explicit "the substring check is necessary but not
  sufficient" line, and it's reviewable as a one-pass diff.

### T9: Validator hardening, q2 / q3 length cap + canonical answer (AC-5)

**Strategy.** q2 and q3 pass when every ground-truth book title appears
as a substring of the answer. Today that's met by dumping the SQL file.
Hardening: cap the answer length so dumping the dataset can't pass, and
restrict the validator's input to the JSON-parsed `answer` value (already
done in `verify.py:32-33`).

- [ ] Failing tests (unit,
  `tests/unit/test_validator_q2_q3_length_cap.py`): three cases per query:
  1. A canonical short answer (the list of titles, comma-separated)
     under the length cap → True.
  2. A long answer (e.g., the entire SQL dump pasted in) → False with
     reason `"answer too long"`.
  3. A short answer missing one title → False with reason `"missing
     book title"` (existing behaviour, regression-guarded).
- [ ] Implementation: add a per-query length cap (default `2000`
  characters; q2/q3 specifically) configured via the validator file.
  Insert the length check before the substring loop in the validator
  template that `prepare.py` copies into `tests/validate.py`.
- [ ] Choose the cap by measuring: read the canonical comma-separated
  ground-truth list, multiply by 2 (slack), round to the nearest 500.
  Record the chosen value as a constant in the validator file with a
  one-line comment naming the rationale.

**Why a length cap and not "force the answer to be a SQL query string".**
The investigation's recommended alternative ("validators consume
agent-emitted SQL queries and check the queries hit dab-postgres") would
require routing the agent's SQL through the verifier, which is a much
larger change to the agent / verifier contract. The length cap is the
smallest fix that closes the specific exploit path observed in T14.

### T10: Stack-level smoke before AC-6 re-run

**Goal.** Before paying for an N=3 T14 re-run, run a single-trial smoke
that exercises the full stack (compose loaded, postgres reachable,
healthcheck passes, agent runs, verifier writes reward).

- [ ] Failing test / smoke: `uv run rk run examples/specs/bookreview-claude.frozen.yaml`
  with `trials=1`, against a fresh clean checkout of the worktree branch.
- [ ] Verify: in the run-dir, `events.jsonl` (or harbor's project log)
  shows the `dab-postgres` container start. The `environment/.compose-services.json`
  sidecar from T3 names `dab-postgres` and `main`. The healthcheck event
  fires.
- [ ] If smoke fails (compose not loaded, gate doesn't fire, etc.), stop
  and fix the upstream task. The re-run is the same shape but more
  expensive; T10 is the cheap version.

### T11: AC-6 T14 re-run + reconciliation update

**Goal.** Re-run T14 (bookreview-claude live-DB, N=3) on the assembled
stack and record headline + Wilson CI.

- [ ] `uv run rk run examples/specs/bookreview-claude.frozen.yaml`
  with `trials=3`; record run-dir.
- [ ] `uv run rk score <run-dir>` to produce summary.json with Wilson CI.
- [ ] Append a section to
  `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`
  that names this as the supersedes-T14 result; record the headline pass@1,
  Wilson CI low/high, and a one-line note that AC-1 to AC-5 landed.
- [ ] Sanity-check: open one trial's `events.jsonl` and confirm a postgres
  query from the agent appears (the agent should now `psql` against
  `dab-postgres` rather than parse the SQL dump). If no agent-emitted
  postgres query is visible, file a follow-up entity for an instrumentation
  gap; do not block AC-6 on this, because AC-6's `Verified by:` is
  satisfied by the events.jsonl showing the postgres container, not the
  agent's queries specifically (re-read the entity to confirm).

## Risk register

- **Harbor step-healthcheck shape may differ from what T5 assumes.** Pinned
  harbor exposes `StepConfig.healthcheck` per its config.py; the failure
  mode is that healthcheck runs but doesn't actually abort the step on
  failure. Mitigation: T6's negative test asserts the abort. If the abort
  doesn't fire, T5 falls back to a pre-agent shell hook in `test.sh` (or
  in a wrapper that wraps the agent command itself). Cheap to switch
  strategies; the test catches the regression.
- **`dab-agent:latest` image may not include `psql`.** T5 names this as a
  known assertion; if `psql` is missing, T5 grows a one-line image-build
  change. The smoke (T10) catches it.
- **Length cap in T9 may reject legitimate verbose answers.** The cap is
  generous (4x canonical ground-truth length) and is recorded in the
  validator file with rationale. If real future agents legitimately
  exceed it, the cap is one constant to bump.
- **The PKG-12 translator dispatch fix already landed; the plugin is
  invoked correctly.** This plan does not re-do PKG-12. It adds the
  surface area that PKG-12's correct dispatch was reaching, but which
  was internally broken.

## Acceptance command (validation stage)

```
uv run pytest packages/razorback-plugin-dab/tests/
uv run rk run examples/specs/bookreview-claude.frozen.yaml
```

Both must exit 0. The second command's run-dir must show `dab-postgres`
container start in the project log, the reachability healthcheck firing,
and `summary.json` produced by `rk score`.
