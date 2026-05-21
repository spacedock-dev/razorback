# PKG-27 — harbor.verifier vs ade-bench SQL-tests contract gap (implementation plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the semantic verifier-contract gap PKG-23's live `rk run` surfaced. After PKG-23 shipped, the airbnb001 trial reaches `harbor.verifier.verifier._resolve_tests` and short-circuits with:

```
FileNotFoundError: No test script found in: .../tests (target OS: linux)
```

(captured verbatim from PKG-23 validation, commit `7073050`, log path `_runs/probe-ade-bench-airbnb001-claude-harbor-local/6732c85b26b21a2e/airbnb001__RUEoJHU/{trial.log,exception.txt}`).

Harbor expects a `tests/test.sh` (POSIX-OS task) that, when executed in the env, writes `/logs/verifier/reward.txt` with a float. ade-bench tasks ship `tests/AUTO_*.sql` (dbt singular tests) plus a host-orchestrated runner (`shared/defaults/run-tests.sh` + ade-bench's Python parser over dbt stdout). The contract mismatch is the entity's documented layer-5 unknown-unknown.

PKG-27 lands the bridge: a synthesized `tests/test.sh` (materialized at translator time, same surface as PKG-23's `task.toml [environment.env]` synthesis) that delegates to ade-bench's upstream `run-tests.sh` in the `client` container and writes harbor's reward file. No SQL/dbt reimplementation in razorback; no parallel sidecar runner.

## Design choice: Option A (Bridge proxy via client socket)

Three options from entity §design space:

- **A. Bridge** — synthesize `test.sh` that calls ade-bench's upstream verifier verbatim (run-tests.sh in `client`), marshall the result into harbor's reward.txt.
- **B. Port** — re-implement the SQL-tests contract inside harbor's verifier shape (run SQL against `client`'s duckdb from a razorback Python harness inside `main`).
- **C. Sidecar** — bypass `harbor.verifier` entirely with a razorback-specific runner.

**Decision: A.** Rationale:

1. **Upstream-fidelity:** A invokes upstream `run-tests.sh` verbatim — same dbt seed → singular test → expected_test_count mechanism. Pass/fail is computed by counting `"N of M PASS|FAIL test_name ..."` lines from dbt stdout, exactly mirroring `ade_bench.parsers.dbt_parser.DbtParser` + `ade_bench.harness._is_resolved` (regex sources: `/Users/clkao/git/ade-bench/ade_bench/parsers/dbt_parser.py:8-32`). B reimplements dbt seed/jinja/compile/singular-filtering inside razorback — a maintenance fork of upstream's whole dbt orchestration. C drifts permanently.
2. **Cost-to-ship:** A is one synthesized shell template + a small docker-compose override (socket bind into `main`) + 2 unit tests + 1 integration. B is multi-hundred LOC reimplementing dbt's project layout, seed loading, and singular-test selection. C is similar to A in LOC but creates a parallel harbor entrypoint.
3. **AC-2 grade:** A is the only option that directly satisfies AC-2 ("upstream-faithful where possible") — the upstream verifier runs verbatim; razorback's contribution is the harbor-contract adapter shell only.
4. **AC-3 (DAB regression) is structural:** A's surface is `materialize_local_task` (called only on `AdeBenchLocalTaskEntry`) — DAB never reaches it, same gating PKG-19/20/23 already rely on.

## Architectural facts (load-bearing for the plan)

Three mechanism findings that shape the implementation, all verified against the harbor 0.6.6 vendored source under `.venv/lib/python3.12/site-packages/harbor/`:

### F1. Harbor's verifier always execs against the compose service named `main`

`harbor.environments.docker.docker.DockerEnvironment.exec` (`docker.py:572-601`) hardcodes `exec_command.append("main")` (line 596). `harbor.verifier.verifier.Verifier.verify` (`verifier.py:185-188`) calls `self._environment.exec(command=...)` to run the test script. The test script therefore runs in the `main` service, NOT in `client`.

### F2. ade-bench upstream compose has only a `client` service (no `main`); harbor stacks its base on top

`shared/defaults/docker-compose-duckdb-dbt.yaml` defines a single `services.client` block (lines 1-13). Harbor's `_docker_compose_paths` (`docker.py:254-301`) prepends `docker-compose-base.yaml` (which declares `services.main`) before the task's compose, so the merged project has BOTH `main` (harbor base) and `client` (ade-bench). This is why PKG-23's live trial got past `docker compose up --wait` (both services come up) AND past the agent turn (which runs in `main`).

### F3. Upstream ade-bench runs the harness ON THE HOST and shells into `client` via the docker SDK

`ade_bench/terminal/docker_compose_manager.py:52` (`docker.from_env()`) and `.py:128-130` (`self._client.containers.get(...)`) confirm: upstream's verifier exists as a host-side Python harness that copies `tests/`, `seeds/`, and `run-tests.sh` into `client` via `put_archive`, then opens a tmux session in `client` and runs `bash /tests/run-tests.sh`. The pass/fail signal is computed by parsing dbt stdout from the tmux pane (`ade_bench/parsers/dbt_parser.py`).

**Implication for the bridge:** the synthesized `test.sh` runs in `main` (per F1). To exercise upstream's verifier verbatim against `client` (per F3), `test.sh` must invoke `docker exec ${T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME} bash /tests/run-tests.sh ...`. This requires the host docker socket bind-mounted into `main` (a docker-compose override layer added to the materialized compose), and `docker` CLI installed in `main` (harbor's base image — verify in T1).

### Reward computation

Harbor's verifier reads `/logs/verifier/reward.txt` (a float) or `reward.json` (`harbor/models/trial/paths.py:36-72`). The bridge writes `1` on success, `0` on failure. The criteria mirror `ade_bench.harness._is_resolved` (`harness.py:244-280`) and `ade_bench.parsers.dbt_parser.DbtParser.get_test_status` (`dbt_parser.py:50-130`):

1. FAIL if `dbt compile` failed (line containing `Encountered an error` or `Compilation Error`).
2. FAIL if dbt stdout contains zero matches for the test-line regex `\d+\s+of\s+\d+\s+(PASS|FAIL|ERROR)\s+\S+`.
3. FAIL if `expected_test_count=N` (printed by `run-dbt-test.sh` line 59) > number of test lines parsed.
4. FAIL if any test line shows `FAIL` or `ERROR`.
5. PASS otherwise.

These five checks are 8-12 lines of shell (grep + awk). Implementation MAY alternatively call into a small in-`main` python helper that imports `ade_bench.parsers.dbt_parser` directly — but the path-of-least-friction default is the shell parse (no ade-bench-pip-install dependency in `main`). T1 picks one.

## Architecture

### File-level changes

- `src/razorback/benchmarks/ade_bench/tasks.py`:
  - Add `_build_test_sh(*, client_container_var: str, db_type: str | None, project_type: str | None) -> str` — emits the synthesized `test.sh` body (string template). Receives the env-var NAME (`T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME`) not the resolved value, because at task.toml-write time we want the test.sh to read the resolved container name from its own env at exec time, NOT bake the value.
  - In `materialize_local_task`: after the existing `(target_dir / "task.toml").write_text(...)` block, write `(target_dir / "tests" / "test.sh").write_text(...)` (creating `tests/` if it doesn't exist — for `materialize_mode="bind"` the dir is a symlink to ade-bench's upstream `tests/` and we MUST switch to a real dir for that case; see T2 design note).
  - Add `_write_docker_socket_override(target_dir: Path) -> None` — writes `environment/docker-compose-socket-override.yaml` adding `services.main.volumes: - /var/run/docker.sock:/var/run/docker.sock` to the materialized compose stack. The override path must be discovered by `harbor.environments.docker.docker.DockerEnvironment._docker_compose_paths` — confirm in T1 whether `environment/*.yaml` files beyond `docker-compose.yaml` are auto-picked up (likely NOT; harbor's `_environment_docker_compose_path` is hardcoded to `environment/docker-compose.yaml`).
  - **Open in T1:** if harbor doesn't auto-pick the override, we either (i) inline the socket-volume into the same `environment/docker-compose.yaml` we materialize (currently just a symlink to upstream's), which requires switching from symlink to a rewritten copy, OR (ii) use harbor's mounts-compose surface (`_write_mounts_compose_file` is harbor-internal — verify whether razorback can hint it through `Task.mounts` or similar).

- `src/razorback/benchmarks/ade_bench/tasks.py` — `_compute_t_bench_env` stays unchanged from PKG-23 (the six T_BENCH_* vars). The synthesized `test.sh` reads them at runtime.

- `tests/unit/test_ade_bench_test_sh_synthesis.py` (NEW):
  - Asserts `_build_test_sh` includes `docker exec ${T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME}` invocation.
  - Asserts the synthesized script writes `/logs/verifier/reward.txt` with `1` or `0`.
  - Asserts the synthesized script forwards `--db-type=$db_type --project-type=$project_type` flags.

- `tests/unit/test_ade_bench_materialize_local_task.py` (EXTEND PKG-19 file):
  - Adds `test_materialize_local_task_writes_test_sh` — asserts `target_dir/tests/test.sh` exists, is executable-by-content (`#!/bin/bash`), and is a real file (not a symlink to upstream's `tests/`).
  - Adds `test_materialize_local_task_keeps_sql_tests_alongside_test_sh` — asserts the upstream `AUTO_*.sql` files are still present under `tests/` (they're consumed by `run-tests.sh` from `/tests/*.sql` inside `client`).

- `tests/unit/test_ade_bench_dab_regression.py` (NEW or extend existing): asserts the DAB benchmark translator path does NOT materialize a `test.sh` and does NOT add the docker-socket override (AC-3 structural gate via translator dispatch — same gating pattern as PKG-23).

- `tests/integration/test_ade_bench_verifier_test_sh_shape.py` (NEW): a host-side `bash test.sh` smoke that mocks the `docker exec` call and asserts reward.txt gets `1` (mock dbt-stdout contains all-PASS lines) or `0` (mock contains a FAIL line). Validates the parser logic without requiring a live docker daemon.

### Surface NOT changed

- `harbor.task.verifier` itself — the contract stays as-is. PKG-27 produces a task that complies with the existing contract, NOT a fork of the contract.
- DAB benchmark path — `_build_test_sh` is invoked only from `materialize_local_task` (ade-bench-only).
- PKG-19's `tests/` symlink mechanism — switched to a real dir under ade-bench tasks ONLY when synthesizing test.sh (the per-task footprint goes from a symlinked 80KB dir to a real ~10KB dir of SQL files + test.sh; immaterial vs the multi-MB seed/CSV reflinks PKG-19 owns).

## Tech Stack

Python 3.12 (typing + pathlib + textwrap for the test.sh template); pytest; PyYAML (for compose override emission); shell (bash + awk + grep for the parser; pinned to busybox-compatible flags so the test.sh works even in slim alpine bases — verify in T1).

## Dependency chain

- PKG-19 — shipped (ade-bench data bind-mount; `materialize_local_task` exists).
- PKG-20 — shipped (compose symlink + `_select_compose_variant`).
- PKG-23 — shipped (T_BENCH_* env-var threading via task.toml [environment.env]).
- harbor 0.6.6 `harbor.task.verifier` (no change).
- ade-bench upstream's `shared/defaults/run-tests.sh` + `shared/scripts/run-dbt-test.sh` (called verbatim; razorback never edits or vendors them).

## Riskiest-contract-first ordering

Per CLAUDE.md "Validating new mechanisms": the riskiest path is whether `docker exec` from inside `main` to `client` can be triggered at all, given that:

1. `docker` CLI must exist in harbor's base image (`main`).
2. `/var/run/docker.sock` must be bind-mountable into `main` via a compose-override that harbor's `_docker_compose_paths` actually discovers.
3. The bound docker socket must accept `docker exec ${T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME}` — requires that the container-name env var is in scope when the test.sh runs in `main`.

T1 verifies all three BEFORE any tests are written (mechanism-validation-first). If any fails, the plan falls back to a documented escape hatch (see "Open design points" below).

## Open design points

These resolve at T1 (mechanism investigation), not at plan time:

- **OD-1: Does harbor's `_docker_compose_paths` pick up a 2nd file under `environment/`?**
  Read confirms only `environment/docker-compose.yaml` is hardcoded (`docker.py:250-251`). Resolution: PKG-27 either (a) writes the socket-volume INTO the materialized `environment/docker-compose.yaml` (switching that file from a PKG-20 symlink to a synthesized YAML that imports the upstream via `extends` or merges its services), or (b) uses harbor's `Task.mounts` field (if any) to declare the socket bind. T1 picks one; option (a) is the default.

- **OD-2: Does harbor's `main` image have `docker` CLI?**
  Harbor's `docker-compose-build.yaml` / `docker-compose-prebuilt.yaml` references a base image. If `docker` is absent, the test.sh installs it via `apt-get install -y docker.io` as a first step (idempotent), OR razorback declares a task-side image that includes it. T1 confirms; default is the apt-get fallback (~5s overhead, one-time per trial).

- **OD-3: Does the test.sh run as root in `main`?**
  Harbor's verifier `exec` uses `default_user` (`verifier.py:185-188 comment`). If `default_user != root`, the docker-socket access requires the user be in the `docker` group OR `chmod 666` of the socket bind. T1 verifies; default fallback is to declare `default_user = root` for ade-bench tasks via task.toml's `[environment]` block (compatible with harbor's contract per `models/task/config.py`).

- **OD-4: Should the dbt-output parser live in shell or python?**
  Shell is simpler and avoids needing python in `main`; python (in-`main`) lets us `import ade_bench.parsers.dbt_parser` directly for byte-perfect upstream parity. Default: SHELL (with a documented "if we hit parser-drift, port to python"); the parser logic is ≤12 lines per F3.

- **OD-5: Where does the test.sh write reward.txt?**
  Harbor's `EnvironmentPaths.reward_text_path = /logs/verifier/reward.txt`; the test.sh writes to that absolute path. Confirm in T1 that `/logs/verifier/` is pre-created by harbor before verifier.exec (yes, per `verifier.py:130` `self._trial_paths.verifier_dir.mkdir(parents=True, exist_ok=True)` + harbor mounts that dir as `${ENV_VERIFIER_LOGS_PATH}` per `docker-compose-base.yaml`).

## AC ↔ task map

- AC-1 (non-degenerate verdict on live `rk run`) → T1 mechanism check + T4 implementation + T8 live smoke
- AC-2 (upstream-faithful) → T2 RED test asserts `test.sh` calls `docker exec ... run-tests.sh` verbatim (not a reimplementation)
- AC-3 (DAB regression) → T6 structural-gate test on DAB translator path + full pytest sweep
- AC-4 (Goal 2 48-cell matrix produces real pass@1) → resume hook only; the goal2-resume entity owns the matrix dispatch

## Task list

- [ ] **T1 — Mechanism investigation (no code).** Resolve OD-1 through OD-5 against the running PKG-23 worktree state (or a fresh clone). Bring up the airbnb001 compose under harbor's base, exec into `main`, verify: (i) `docker` CLI presence; (ii) `/var/run/docker.sock` is reachable via mount; (iii) `default_user` identity; (iv) compose-override discovery rule for `environment/*.yaml`. Output: a one-page mechanism note appended to this plan under §"T1 mechanism findings".

- [ ] **T2 — RED — `_build_test_sh` shape.** Write `tests/unit/test_ade_bench_test_sh_synthesis.py` asserting (a) the synthesized script contains `docker exec "${T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME}"`; (b) it invokes `bash /tests/run-tests.sh` with `--db-type` and `--project-type` forwarded; (c) it writes `/logs/verifier/reward.txt`; (d) the parser logic correctly detects all-PASS → `1` and any-FAIL → `0` against fixture dbt stdout strings. Confirm RED (function does not exist).

- [ ] **T3 — GREEN — `_build_test_sh` + materialize_local_task wiring.** Implement `_build_test_sh` per T1's resolved OD-set. Update `materialize_local_task` to:
  (i) materialize `tests/` as a real dir (not symlink) when synthesizing test.sh, copying ade-bench's upstream `tests/*.sql` files in;
  (ii) write `test.sh` alongside the SQL files;
  (iii) chmod 0755 the test.sh.
  Confirm T2 GREEN + PKG-19 tests stay GREEN.

- [ ] **T4 — RED+GREEN — docker-socket override.** Per T1's OD-1 resolution, either rewrite `environment/docker-compose.yaml` to merge upstream's compose with a socket-volume override (default path), or add a second compose file. Write a unit test asserting `docker compose config` on the materialized dir produces a merged compose that includes `/var/run/docker.sock:/var/run/docker.sock` under `services.main.volumes` AND retains upstream's `services.client.*` definitions verbatim (build context, image, command, environment, volumes).

- [ ] **T5 — RED+GREEN — integration smoke (mocked docker exec).** Write `tests/integration/test_ade_bench_verifier_test_sh_shape.py`: invoke `bash test.sh` on the host with a stub `docker` binary on PATH (PYTHONPATH-style: a tmp_path/docker wrapper that echoes canned dbt stdout). Assert reward.txt → `1` for all-PASS stdout, `0` for any-FAIL stdout, `0` for stdout with `total < expected_test_count`. This validates the parser branch coverage without requiring a live docker daemon.

- [ ] **T6 — RED+GREEN — AC-3 DAB-regression gate.** Write `tests/unit/test_ade_bench_translator_test_sh_gating.py` asserting the DAB translator path (`razorback.translate._build_dab` or equivalent) does NOT call `_build_test_sh` and does NOT add the docker-socket override. Same structural-gate shape as PKG-23's translator-level gating test.

- [ ] **T7 — Full pytest regression sweep.** `uv run pytest tests/unit/ tests/integration/` — assert no regression in PKG-14/15/16/17/19/20/21/23 tests. Confirm PKG-27 surfaces all GREEN.

- [ ] **T8 — AC-1 live `rk run` smoke (validation-stage scope, NOT implementation).** Per the entity's AC-1 verification: live `rk run examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml` against the goal2 T0 frozen spec produces a `summary.json` with `mean_reward = 0.0` or `1.0` (non-null, non-verifier-short-circuit). The validation stage owns this exercise (per the workflow's plan → implementation → validation pipeline); implementation-stage T7 confirms unit + integration are GREEN before handoff.

- [ ] **T9 — Stage Report + completion signal.** Per spacedock:ensign protocol — append `## Stage Report: implementation` to the entity body covering T1-T7; commit; signal team-lead.

## Risks / open questions

- **Risk R1 (high):** `docker exec` from `main` to `client` may be blocked by harbor's `network_mode: none` if `allow_internet=False` is set on the task. Verify in T1 — if blocked, the override must also remove `network_mode: none` for the verifier exec OR the bridge uses a UNIX-socket-only path which `network_mode: none` does NOT block (UNIX sockets bypass network namespaces). Default: rely on UNIX socket bypass.

- **Risk R2 (med):** ade-bench's `client` image (`ade-bench-client-airbnb001:latest`) is built on-the-fly by `docker compose up` (per PKG-23 validation §"AC-4 client image absent — not a validation blocker"). First-run cold-build is ~60-120s; subsequent runs hit docker's build cache. Goal 2's 48-cell matrix shares a single image build per variant. Documented in the resume hook.

- **Risk R3 (low):** The shell-side dbt-stdout parser (per OD-4) may drift from `ade_bench.parsers.dbt_parser.DbtParser` if upstream changes the regex shape. T2/T5 lock in the current shape with explicit fixture strings drawn from `/Users/clkao/git/ade-bench/ade_bench/parsers/dbt_parser.py:8` examples. If drift hits, port to python (per OD-4's escape hatch).

- **Risk R4 (med):** The "agent ran in `main`, dbt data lives in `client`" architectural reality (per F1+F2+F3) means even with a perfect verifier bridge, the airbnb001 reward will likely be 0.0 — the agent (running in `main`) cannot reach `client`'s duckdb to write dbt models. PKG-27's AC-1 specifies "0.0 OR 1.0" — a real 0.0 closes AC-1. The "agent runs in wrong container" gap is a separate follow-up (call it PKG-28 if it materializes) and explicitly out of PKG-27's scope.

## Out of scope (forwarded from entity)

- ade-bench-client image build path (separate follow-up; PKG-23 §Out of scope already names it).
- Goal 2's 48-cell matrix dispatch (separate goal2-resume entity after PKG-27 ships).
- Goal 1 (different adapter, harbor-DAB; not affected).
- Fixing the "agent runs in main, dbt data in client" gap (Risk R4 — separate entity if reward stays at 0.0 after PKG-27 ships).
