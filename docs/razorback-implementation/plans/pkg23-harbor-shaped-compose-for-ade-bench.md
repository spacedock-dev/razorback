# PKG-23 — thread T_BENCH_* env vars from razorback's ade-bench materializer (implementation plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the runtime half of harbor's ade-bench task contract that PKG-20 left open. PKG-20 made `DockerEnvironment._validate_definition` pass by symlinking ade-bench's upstream `shared/defaults/docker-compose-*.yaml` into the materialized view-dir's `environment/`. Validation accepts the symlink; `docker compose up` does not — the upstream template references six `${T_BENCH_*}` env vars whose unresolved placeholders make compose-up reject the build context (Goal 2 T0 cycle 4 spike, commit `251d692` on `spacedock-ensign/goal2-ade-bench-haiku-baseline`). PKG-23 populates those six vars so compose-up resolves cleanly.

**Mechanism-precise architectural finding (load-bearing for the plan):** the entity's `## Problem` section frames this as a "translator hook" landing in `src/razorback/translate.py`. The real wire — confirmed by reading harbor's docker environment — is task.toml-side, not JobConfig-side:

- `harbor.environments.docker.docker.DockerEnvironment._run_docker_compose_command` calls `subprocess` with `env = env_vars.to_env_dict() | self._compose_task_env | …`.
- `self._compose_task_env = resolve_env_vars(task_env_config.env)` where `task_env_config` is `self._task.config.environment` — i.e., the `[environment]` block of **`task.toml`** (`harbor/trial/trial.py:206`).
- `harbor.models.task.config.EnvironmentConfig.env: dict[str, str]` (description: "Environment variables required for the task and resolved from the host at runtime. Supports ${VAR} and ${VAR:-default} template syntax.").

So the surface that actually feeds env into `docker compose up` is **the synthesized task.toml's `[environment.env]` table**, written by `materialize_local_task`/`_build_task_toml_from_yaml` in `src/razorback/benchmarks/ade_bench/tasks.py`. `translate.py` is the dispatcher that resolves per-task identity (slug, cell short-id, host paths) and threads it into the materializer call. PKG-23 lands in both files but the env-dict-producing logic is in the materializer.

This corrects two phrasings in the entity:

1. AC-1's "the spawned `docker compose up` inherits an env dict" is satisfied via task.toml's `[environment.env]` (which harbor's docker environment resolves and forwards to its compose subprocess) — NOT via a translator-side subprocess `env=` argument.
2. AC-1's "`T_BENCH_REPO_ROOT` → resolved absolute path to the materialized task's view-dir (the harbor cache_root entry, NOT ~/git/ade-bench — the materialized view-dir already has ade-bench's `tests/` etc. via PKG-19's bind-mount)" — this is WRONG for the duckdb-dbt variant (the variant Goal 2's airbnb001 hits). The upstream compose has `build.context: ${T_BENCH_REPO_ROOT}` and `dockerfile: docker/base/Dockerfile.duckdb-dbt`. The view-dir does NOT contain a `docker/` subtree (PKG-19's symlinks reflect `~/git/ade-bench/tasks/<slug>/` contents only — `setup.sh`, `solution.sh`, `tests/`, `seeds/`, NOT the repo-level `docker/`). The Dockerfile lives at `~/git/ade-bench/docker/base/Dockerfile.duckdb-dbt` and is referenced relative to `T_BENCH_REPO_ROOT`. Therefore `T_BENCH_REPO_ROOT` MUST resolve to `ade_bench_root` (i.e., `~/git/ade-bench`), matching upstream ade-bench's own `DockerComposeManager` (`/Users/clkao/git/ade-bench/ade_bench/terminal/docker_compose_manager.py:86` sets `repo_root=str(REPO_ROOT)` where `REPO_ROOT` is the ade-bench checkout root). This plan adopts that value and flags the entity for clarification.

**Architecture:**
- `src/razorback/benchmarks/ade_bench/tasks.py`: extend `_build_task_toml_from_yaml` (or add a sibling helper) to emit an `[environment.env]` table from a per-task `t_bench_env: dict[str, str]` parameter; thread that dict through `materialize_local_task`'s call signature. The dict-building logic (resolving the six vars from per-task identity + paths) is a new module-private helper `_compute_t_bench_env(*, ade_bench_root, view_dir, task_slug, trial_id_short)` or similar.
- `src/razorback/translate.py`: `_build_ade_bench` computes per-task identity (image name + container name) and passes the assembled env dict into `materialize_local_task`. The container-name needs a per-cell unique short id; the translator already has the spec but not the harbor trial id. **Open design point** (see Task 1): the canonical "per-cell trial id" is harbor-side, materialized AT trial run-time, not at translator/freeze-time. So the env dict written into task.toml uses a deterministic per-task value (image name `ade-bench-client-{task_slug}:latest`) and harbor's own `_compose_task_env`/`_persistent_env` resolves runtime cell identity via `${T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME:-...default...}` templating. The task.toml value is the default; harbor's session-id can override at runtime if needed. Confirmed in Task 1 against `harbor.utils.env.resolve_env_vars`.
- `src/razorback/cli/run.py` / `src/razorback/cli/__init__.py`: no surface change. The wiring is per-spec and per-task, not per-CLI-flag.

**Tech Stack:** Python 3.12, pytest, PyYAML, harbor.models.task, docker.

**Dependency chain:**
- PKG-19 — shipped (ade-bench data bind-mount; provides `materialize_local_task` + `AdeBenchLocalTaskEntry`).
- PKG-20 — shipped (compose symlink + `_select_compose_variant`). PKG-23 KEEPS PKG-20's symlink mechanism unchanged — the upstream compose under `environment/docker-compose.yaml` stays as-is. The only new artifact is the `[environment.env]` table in the synthesized task.toml.
- `ade-bench-agent:latest` and `ade-bench-client-{variant}:latest` images — out of PKG-23 scope (see entity §Out of scope). AC-3's live smoke is allowed to fail on a NEW layer (missing client image build / docker-socket-shared layer-5 gap) per the entity.

**Spec §-cites:**
- PKG-23 entity: `docs/razorback-implementation/pkg23-harbor-shaped-compose-for-ade-bench.md` (4 ACs + Out of scope + Resume hook).
- Goal 2 T0 cycle 4 spike: commit `251d692` on `spacedock-ensign/goal2-ade-bench-haiku-baseline` — confirms the failure mode + narrows the fix to remediation (b).
- Harbor compose env hook: `harbor.environments.docker.docker.DockerEnvironment._run_docker_compose_command` (lines 321–352 of `harbor/environments/docker/docker.py`). The wire is `subprocess.create_subprocess_exec(..., env=env)` where `env` includes `_compose_task_env = resolve_env_vars(task_env_config.env)`.
- Harbor task.toml shape: `harbor.models.task.config.EnvironmentConfig.env: dict[str, str]` (line 151) — accepts `${VAR}` / `${VAR:-default}` templating via `resolve_env_vars`.
- Upstream ade-bench compose template: `~/git/ade-bench/shared/defaults/docker-compose-duckdb-dbt.yaml` — references all six T_BENCH_* placeholders. The other three variant files share the same shape with one substitution (`T_BENCH_TASK_BUILD_CONTEXT_DIR` in the base template; the others swap dockerfile path).
- Upstream ade-bench canonical values: `ade_bench/terminal/docker_compose_manager.py:74–87` (`DockerComposeEnvVars` construction). PKG-23's helper mirrors this verbatim except for `task_logs_path` (which becomes the materialized view-dir's logs subpath, NOT upstream's trial scratch dir).
- PKG-19 plan (style + structural reference): `docs/razorback-implementation/plans/pkg19-ade-bench-data-bind-mount.md` — risk-first ordering, fixture reuse, AC↔task mapping.

## AC ↔ task map

| AC    | Tasks                                                                 |
| ----- | --------------------------------------------------------------------- |
| AC-1  | T1 (mechanism review), T2 (RED — task.toml `[environment.env]` carries 6 keys), T3 (GREEN — `_compute_t_bench_env` + materializer signature change), T4 (RED — `docker compose config` resolves with no `${T_BENCH_*}` placeholders), T5 (GREEN — value-shape fixes if T4 fails) |
| AC-2  | T6 (RED — harbor-DAB translator output does NOT inject T_BENCH_* in any harbor surface), T7 (GREEN — confirm gating is structural: `_build_harbor_dab` never touches the ade-bench materializer) |
| AC-3  | T8 (RED+GREEN — live `rk run` against airbnb001 reaches Phase 3 OR documents new failure mode); validation-stage gates the actual dispatch |
| AC-4  | T9 (documentation only — the `ade-bench-client-{task_slug}` image build path lives in `~/git/ade-bench/docker/base/Dockerfile.duckdb-dbt` and is referenced via `T_BENCH_REPO_ROOT`; capture the build command + open a follow-up PKG entity) |

T10 is the full pytest regression gate. T11 is the validation-stage handoff (probe-spec / live-smoke wiring + stage report).

## File structure

| File | Responsibility | Action |
| ---- | -------------- | ------ |
| `src/razorback/benchmarks/ade_bench/tasks.py` | Add `_compute_t_bench_env(*, ade_bench_root, view_dir, task_slug)`; extend `_build_task_toml_from_yaml(task_yaml, docker_image, t_bench_env)` to emit `[environment.env]`; extend `materialize_local_task(...)` signature to accept the env dict | Modify |
| `src/razorback/translate.py` | `_build_ade_bench` computes the per-task env dict + threads it into `materialize_local_task` | Modify |
| `tests/unit/test_ade_bench_t_bench_env.py` | AC-1 unit — task.toml carries `[environment.env]` with 6 keys, values non-empty, `T_BENCH_REPO_ROOT == ade_bench_root` absolute path | Create |
| `tests/unit/test_ade_bench_translator_t_bench_env.py` | AC-1 translator-level — `spec_to_job_config` against an `AdeBenchLocalTaskEntry` produces a materialized task.toml whose `[environment.env]` carries the six keys; AC-2 gating cross-check — harbor-DAB translator output does NOT touch the ade-bench materializer | Create |
| `tests/integration/test_ade_bench_compose_config_resolves.py` | AC-1 integration — `docker compose config` against the materialized compose + env dict produces a fully-resolved compose with no `${T_BENCH_*}` placeholders (gated on `docker` binary; otherwise skipped) | Create |
| `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml` | Validation-stage probe spec (PKG-19 already shipped this; PKG-23 inherits — no new file unless the existing spec needs `db_type`/`project_type` to pin variant) | Verify / extend |
| `docs/razorback-implementation/pkg23-harbor-shaped-compose-for-ade-bench.md` | Entity body — append a §Build paths section documenting AC-4 (Dockerfile location + build command); add the entity flag noting the AC-1 `T_BENCH_REPO_ROOT` correction (`ade_bench_root`, not the view-dir) | Modify (entity body, NOT frontmatter) |

## Risk-first ordering rationale

The riskiest contract is **harbor's `[environment.env]` resolution shape**: the task.toml-side env values must satisfy `harbor.utils.env.resolve_env_vars` (literal strings or `${VAR}` / `${VAR:-default}` templates), and the resulting resolved values must satisfy `docker compose config`'s placeholder resolution. If harbor's `templatize_sensitive_env` (the env-serializer) rewrites our values during lock.json/persistence (it might — see `templatize_sensitive_env` in `harbor/utils/env.py`), or if `resolve_env_vars` rejects a value shape, every downstream test collapses.

So:

- T1: paper-only mechanism review — confirm `resolve_env_vars` accepts literal absolute paths verbatim AND that the six chosen keys are not in `is_sensitive_env_key`'s deny-list (which would trigger redaction in lock.json round-trip and break replay).
- T2 (AC-1 RED — smallest failing test): synthesize a task.toml with `[environment.env]` populated from a known per-task identity, parse it back via `tomllib`/harbor's loader, assert the six keys are present with absolute-path values. No docker required.
- T3 (AC-1 GREEN): implement `_compute_t_bench_env` + extend `_build_task_toml_from_yaml` to emit the `[environment.env]` block. Wire signature in `materialize_local_task` so the env dict is computed once per materialization.
- T4 (AC-1 integration RED, docker-gated): drive `docker compose config` against the materialized `environment/docker-compose.yaml` with the env dict exported, assert no unresolved `${T_BENCH_*}` placeholders.
- T5: value-shape iteration if T4 fails (e.g., wrong path quoting, wrong logs-path semantics).
- T6/T7 (AC-2): cross-check that the harbor-DAB translator path does NOT invoke `materialize_local_task` — gating is structural (PKG-19's translator dispatch already restricts the local-task path to `AdeBenchLocalTaskEntry`).
- T8 (AC-3): live smoke against airbnb001 (validation-stage). Implementation stage stops at unit + docker-config integration.
- T9 (AC-4): documentation only; PKG-23 explicitly does NOT build the client image.
- T10: full pytest sweep — regression gate.
- T11: validation-stage handoff.

Comprehensive runs come AFTER the smallest end-to-end mechanism check passes. Live `docker compose up` (T8) comes AFTER `docker compose config` (T4) resolves cleanly. The dependency: docker-config (offline-ish placeholder resolution) → docker-compose-up (live build + run).

---

## Task 1 — Mechanism review (no code)

**Files:** none modified.

- [ ] **Step 1: Confirm `resolve_env_vars` accepts literal absolute paths.**

Read `~/git/razorback/.venv/lib/python3.12/site-packages/harbor/utils/env.py:94-128`. Confirm:
- Literal values pass through unchanged (no `${...}` syntax required).
- The function does NOT reject paths containing `/`, `_`, `:`, or spaces.

If any of the six chosen literal values would be a `${VAR}` template (e.g., the captain wants `T_BENCH_REPO_ROOT` to interpolate `${HOME}/git/ade-bench`), use `${HOME}/git/ade-bench` — but the simpler choice is to resolve to an absolute path at translator-time (the translator already has `ade_bench_root` resolved via `Path(spec.benchmark.ade_bench_root).expanduser()`).

- [ ] **Step 2: Confirm the six chosen keys are not sensitive (no redaction on lock.json round-trip).**

Read `harbor/utils/env.py` for `is_sensitive_env_key` (or its equivalent). Confirm `T_BENCH_*` prefix is not in the deny-list (it shouldn't be — sensitive keys are typically `*_TOKEN`, `*_API_KEY`, `*_SECRET`). The serializer in `harbor.models.trial.config.EnvironmentConfig._serialize_env` calls `templatize_sensitive_env`; if `T_BENCH_REPO_ROOT` triggered templatization, the locked-spec replay would see `${T_BENCH_REPO_ROOT}` (host-resolution required) instead of the literal absolute path we want.

- [ ] **Step 3: Confirm `docker compose config` semantics with env injection.**

```bash
cd /Users/clkao/git/ade-bench
T_BENCH_REPO_ROOT=$(pwd) \
T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME=ade-bench-client-test:latest \
T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME=test-container \
T_BENCH_TEST_DIR=/tmp/tests \
T_BENCH_TASK_LOGS_PATH=/tmp/logs \
T_BENCH_CONTAINER_LOGS_PATH=/logs \
docker compose -f shared/defaults/docker-compose-duckdb-dbt.yaml config
```

Expected: prints a fully-resolved compose with no `${T_BENCH_*}` placeholders. If `docker compose config` raises on any of the six (e.g., volume-mount source-path must exist), Task 4 must address the surface mismatch — likely by precreating `T_BENCH_TASK_LOGS_PATH` directory before compose-up.

- [ ] **Step 4: Confirm the `dockerfile: docker/base/Dockerfile.duckdb-dbt` path resolves under `ade_bench_root`.**

```bash
ls ~/git/ade-bench/docker/base/Dockerfile.duckdb-dbt
```

Expected: file exists. This is the load-bearing reason `T_BENCH_REPO_ROOT` must be `ade_bench_root` (NOT the materialized view-dir).

- [ ] **Step 5: No commit. Proceed to Task 2.**

---

## Task 2 — AC-1 RED: task.toml emits `[environment.env]` with six T_BENCH_* keys

**Files:**
- Create: `tests/unit/test_ade_bench_t_bench_env.py`

- [ ] **Step 1: Write the failing test.**

```python
# ABOUTME: PKG-23 AC-1 — synthesized task.toml carries an [environment.env]
# ABOUTME: table populated with six T_BENCH_* keys from the per-task identity.

import tomllib
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def test_materialize_local_task_emits_t_bench_env_block(tmp_path: Path) -> None:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg23-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    task_toml = tomllib.loads((materialized / "task.toml").read_text())
    env = task_toml["environment"]["env"]
    expected_keys = {
        "T_BENCH_REPO_ROOT",
        "T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME",
        "T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME",
        "T_BENCH_TEST_DIR",
        "T_BENCH_TASK_LOGS_PATH",
        "T_BENCH_CONTAINER_LOGS_PATH",
    }
    assert expected_keys.issubset(set(env.keys())), (
        f"AC-1: task.toml must populate the six T_BENCH_* keys; got {sorted(env.keys())}"
    )
    for k in expected_keys:
        assert env[k] and isinstance(env[k], str), (
            f"AC-1: env[{k!r}] must be a non-empty string; got {env[k]!r}"
        )


def test_t_bench_repo_root_resolves_to_ade_bench_root(tmp_path: Path) -> None:
    """AC-1 correction: T_BENCH_REPO_ROOT must point at the ade_bench
    checkout (so docker/base/Dockerfile.duckdb-dbt resolves), NOT the
    materialized view-dir (which lacks docker/)."""
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg23-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    task_toml = tomllib.loads((materialized / "task.toml").read_text())
    env = task_toml["environment"]["env"]
    assert env["T_BENCH_REPO_ROOT"] == str(ade_bench_root), (
        f"AC-1: T_BENCH_REPO_ROOT must equal ade_bench_root absolute path; "
        f"got {env['T_BENCH_REPO_ROOT']!r}"
    )


def test_t_bench_test_dir_under_view_dir(tmp_path: Path) -> None:
    """AC-1: T_BENCH_TEST_DIR resolves to the materialized tests/ path
    (view-dir-side) so harbor's bind-mount serves the test files."""
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg23-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    task_toml = tomllib.loads((materialized / "task.toml").read_text())
    test_dir = task_toml["environment"]["env"]["T_BENCH_TEST_DIR"]
    # The materialized tests/ is either a symlink (bind mode) or a real dir;
    # either way its parent is the view-dir.
    assert Path(test_dir).name == "tests"
    assert Path(test_dir).parent == materialized, (
        f"AC-1: T_BENCH_TEST_DIR must live under the view-dir; "
        f"got {test_dir!r}, view_dir={materialized}"
    )


def test_t_bench_image_name_includes_task_slug(tmp_path: Path) -> None:
    """AC-1: image name is deterministic per task slug."""
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg23-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    task_toml = tomllib.loads((materialized / "task.toml").read_text())
    img = task_toml["environment"]["env"]["T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME"]
    assert "example001" in img, (
        f"AC-1: image name must include task slug; got {img!r}"
    )


def test_t_bench_container_logs_path_is_container_side(tmp_path: Path) -> None:
    """AC-1: T_BENCH_CONTAINER_LOGS_PATH is the container-side mount target
    (canonical upstream value: /logs)."""
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg23-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
    )
    task_toml = tomllib.loads((materialized / "task.toml").read_text())
    assert task_toml["environment"]["env"]["T_BENCH_CONTAINER_LOGS_PATH"] == "/logs"
```

- [ ] **Step 2: Run to verify the test fails.**

```bash
cd /Users/clkao/git/razorback
uv run pytest tests/unit/test_ade_bench_t_bench_env.py -v
```

Expected: all five tests FAIL with `KeyError: 'env'` (the synthesized task.toml currently has only `[environment]` with `docker_image`, no `env` sub-table).

- [ ] **Step 3: Commit (RED).**

```bash
cd /Users/clkao/git/razorback
git add tests/unit/test_ade_bench_t_bench_env.py
git commit -m "test(pkg23): RED — task.toml [environment.env] populates six T_BENCH_* keys"
```

---

## Task 3 — AC-1 GREEN: `_compute_t_bench_env` + materializer wires `[environment.env]`

**Files:**
- Modify: `src/razorback/benchmarks/ade_bench/tasks.py`

- [ ] **Step 1: Add the env-dict builder helper.**

Append to `src/razorback/benchmarks/ade_bench/tasks.py`:

```python
def _compute_t_bench_env(
    *,
    ade_bench_root: Path,
    view_dir: Path,
    task_slug: str,
) -> dict[str, str]:
    """Compute the six T_BENCH_* env vars ade-bench's upstream compose template
    references.

    Mirrors upstream `ade_bench/terminal/docker_compose_manager.py:74-87`'s
    `DockerComposeEnvVars` construction with razorback-side substitutions:

    - `T_BENCH_REPO_ROOT` — `ade_bench_root` absolute path. Upstream sets this
      to the ade-bench checkout root because the compose template's
      `dockerfile: docker/base/Dockerfile.duckdb-dbt` (and sibling variants)
      resolves relative to it. The materialized view-dir does NOT contain
      `docker/` (PKG-19 only reflects per-task contents), so this MUST stay
      at `ade_bench_root` not `view_dir`.
    - `T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME` — deterministic per-slug
      `ade-bench-client-{task_slug}:latest`. The image is NOT built by
      PKG-23 (see entity §Out of scope); follow-up entity wires the build.
    - `T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME` — deterministic per-slug
      `{task_slug}-client`. Harbor's compose project-name (the session id)
      already enforces per-trial uniqueness on the container layer, so a
      static container_name per task is safe — harbor's `--project-name`
      prefix isolates concurrent trials.
    - `T_BENCH_TEST_DIR` — absolute path to the materialized `tests/` under
      the view-dir. The upstream compose mounts this on the client side via
      the `TEST_DIR=${T_BENCH_TEST_DIR}` environment variable, so the agent's
      test-execution wiring inside the client container reads from it.
    - `T_BENCH_TASK_LOGS_PATH` — host-side per-task logs directory. Set to
      `view_dir / "logs"` (the directory is created at materialize-time so
      `docker compose up` does not fail on a missing bind-mount source).
    - `T_BENCH_CONTAINER_LOGS_PATH` — container-side mount target. Set to
      `/logs` per upstream convention (`DockerComposeManager.CONTAINER_LOGS_PATH`).
    """
    logs_path = view_dir / "logs"
    logs_path.mkdir(exist_ok=True)
    return {
        "T_BENCH_REPO_ROOT": str(ade_bench_root),
        "T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME": (
            f"ade-bench-client-{task_slug}:latest"
        ),
        "T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME": f"{task_slug}-client",
        "T_BENCH_TEST_DIR": str(view_dir / "tests"),
        "T_BENCH_TASK_LOGS_PATH": str(logs_path),
        "T_BENCH_CONTAINER_LOGS_PATH": "/logs",
    }
```

- [ ] **Step 2: Extend `_build_task_toml_from_yaml` to accept and emit `[environment.env]`.**

Change the signature:

```python
def _build_task_toml_from_yaml(
    *,
    task_yaml: dict,
    docker_image: str,
    t_bench_env: dict[str, str] | None = None,
) -> str:
```

Body: after the existing `[environment]` block, if `t_bench_env`, append:

```python
    lines = [
        'instruction = "instruction.md"',
        '',
        '[environment]',
        f'docker_image = "{docker_image}"',
    ]
    if t_bench_env:
        lines.append('')
        lines.append('[environment.env]')
        for k, v in t_bench_env.items():
            # Literal-string TOML quoting: backslash and double-quote escaping
            # is sufficient for absolute filesystem paths on darwin/linux.
            v_escaped = v.replace('\\', '\\\\').replace('"', '\\"')
            lines.append(f'{k} = "{v_escaped}"')
    return '\n'.join(lines) + '\n'
```

- [ ] **Step 3: Wire `materialize_local_task` to compute + pass the dict.**

In `materialize_local_task`, AFTER `target_dir.mkdir(parents=True)` (so the view-dir exists for `_compute_t_bench_env`'s `mkdir(logs_path)`), insert:

```python
    t_bench_env = _compute_t_bench_env(
        ade_bench_root=ade_bench_root,
        view_dir=target_dir,
        task_slug=task_slug,
    )
```

Then change the `task.toml` write to pass `t_bench_env=t_bench_env`:

```python
    (target_dir / "task.toml").write_text(
        _build_task_toml_from_yaml(
            task_yaml=task_yaml,
            docker_image=docker_image,
            t_bench_env=t_bench_env,
        )
    )
```

- [ ] **Step 4: Run to verify pass.**

```bash
uv run pytest tests/unit/test_ade_bench_t_bench_env.py -v
```

Expected: all five PASS.

- [ ] **Step 5: Run the existing PKG-19 + PKG-20 unit tests as regression gate.**

```bash
uv run pytest tests/unit/test_ade_bench_materialize_local_task.py \
              tests/unit/test_ade_bench_translator_local_root.py \
              -v
```

Expected: all PASS (PKG-19 + PKG-20 contracts unchanged).

- [ ] **Step 6: Commit (GREEN).**

```bash
git add src/razorback/benchmarks/ade_bench/tasks.py
git commit -m "feat(pkg23): GREEN — task.toml [environment.env] populates T_BENCH_* keys"
```

---

## Task 4 — AC-1 INTEGRATION RED: `docker compose config` resolves with no placeholders

**Files:**
- Create: `tests/integration/test_ade_bench_compose_config_resolves.py`

- [ ] **Step 1: Write the integration test.**

```python
# ABOUTME: PKG-23 AC-1 — docker compose config resolves the materialized
# ABOUTME: compose with no unresolved ${T_BENCH_*} placeholders.

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="requires local docker; skipped on no-docker harnesses",
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def test_docker_compose_config_resolves_t_bench_placeholders(tmp_path: Path) -> None:
    """AC-1 integration: invoke `docker compose config` against the
    materialized compose + the synthesized [environment.env] dict; assert
    no ${T_BENCH_*} placeholders remain in the resolved compose output."""
    # The fixture needs a compose template that uses T_BENCH_* placeholders;
    # reuse ~/git/ade-bench/shared/defaults/docker-compose-duckdb-dbt.yaml
    # only if the captain's checkout exists. Otherwise skip — this is an
    # integration test, not a unit test.
    ade_bench_root = Path.home() / "git" / "ade-bench"
    if not (ade_bench_root / "shared" / "defaults" / "docker-compose-duckdb-dbt.yaml").exists():
        pytest.skip(
            "requires ~/git/ade-bench checkout with shared/defaults/ compose "
            "templates (captain's local fixture; not present on CI)"
        )

    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    cache_root = tmp_path / "pkg23-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="airbnb001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
        db_type="duckdb",
        project_type="dbt",
    )
    task_toml = tomllib.loads((materialized / "task.toml").read_text())
    env_block = task_toml["environment"]["env"]

    # Compose env := host env + task env (mimics harbor's _compose_task_env
    # update on top of env_vars.to_env_dict()).
    env = os.environ.copy()
    env.update(env_block)

    compose_path = materialized / "environment" / "docker-compose.yaml"
    assert compose_path.exists(), (
        "PKG-20 invariant: materialized view-dir must contain "
        "environment/docker-compose.yaml"
    )

    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_path), "config"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"AC-1: docker compose config must resolve cleanly; "
        f"stderr={result.stderr!r}"
    )
    assert "${T_BENCH_" not in result.stdout, (
        f"AC-1: no unresolved T_BENCH_* placeholders in resolved compose; "
        f"got:\n{result.stdout}"
    )
```

- [ ] **Step 2: Run to verify.**

```bash
cd /Users/clkao/git/razorback
uv run pytest tests/integration/test_ade_bench_compose_config_resolves.py -v
```

Expected behavior matrix:
- If Task 3 GREEN is correct AND `docker` is present AND `~/git/ade-bench` exists → PASS.
- If `docker` absent → SKIPPED.
- If `~/git/ade-bench` absent → SKIPPED.
- If Task 3 GREEN missed a key or produced a wrong shape → FAIL with concrete placeholder mismatch.

- [ ] **Step 3: Iterate if RED.**

If FAIL, the most likely causes are (in order):
1. A T_BENCH_* key spelled wrong in `_compute_t_bench_env` (verify against `~/git/ade-bench/shared/defaults/docker-compose-duckdb-dbt.yaml`).
2. `docker compose config` is stricter than the upstream env-resolution and requires a bind-mount source to exist BEFORE config-time (e.g., `T_BENCH_TASK_LOGS_PATH` directory). `_compute_t_bench_env` already `mkdir`s the logs dir; verify.
3. PKG-20's `_select_compose_variant` chose a template whose placeholders differ (e.g., the snowflake variants use `T_BENCH_TASK_BUILD_CONTEXT_DIR` instead of `T_BENCH_REPO_ROOT`). Goal 2 Task 0 hits duckdb-dbt, so the duckdb-dbt variant is the load-bearing one for PKG-23; the snowflake variants are out of PKG-23's smoke scope. Mention any divergence in the entity's §Build paths section.

- [ ] **Step 4: Commit.**

```bash
git add tests/integration/test_ade_bench_compose_config_resolves.py
git commit -m "test(pkg23): AC-1 integration — docker compose config resolves T_BENCH_* placeholders"
```

---

## Task 5 — AC-1 value-shape iteration (placeholder, only if Task 4 RED)

This task is reserved for any value-shape fixes Task 4 surfaces. If Task 4 PASSED first try, skip Task 5 and proceed to Task 6.

Likely fix shapes (do NOT pre-implement):
- Wrap `T_BENCH_REPO_ROOT` in `${VAR:-default}` to allow host-env override at trial run-time. Counter-argument: harbor's lock.json replay needs a deterministic value; literal absolute path is the replay-correct choice.
- Switch `T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME` to interpolate harbor's session-id so concurrent trials don't collide on container_name. Counter-argument: harbor's `--project-name` prefix already provides per-trial isolation on the compose project layer; container_name within the project is unique by definition. Defer this unless Task 4 surfaces an actual collision.

---

## Task 6 — AC-2 RED: harbor-DAB translator output does NOT carry T_BENCH_* keys

**Files:**
- Create: `tests/unit/test_ade_bench_translator_t_bench_env.py`

- [ ] **Step 1: Write the failing/sanity test.**

```python
# ABOUTME: PKG-23 AC-1 + AC-2 — translator-level wiring + gating check.

import tomllib
from pathlib import Path

from razorback.spec.schema import (
    AdeBenchBenchmarkBlock,
    AdeBenchLocalTaskEntry,
    NopAgentBlock,
    Spec,
)
from razorback.translate import spec_to_job_config

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def _ade_bench_spec(ade_bench_root: Path) -> Spec:
    return Spec(
        version=1,
        experiment="pkg23-translator-test",
        agent=NopAgentBlock(kind="nop"),
        benchmark=AdeBenchBenchmarkBlock(
            kind="ade-bench",
            tasks_root=Path("."),
            ade_bench_root=ade_bench_root,
            tasks=[AdeBenchLocalTaskEntry(slug="example001")],
            docker_image_override="ade-bench-agent:latest",
        ),
        trials=1,
        observers=[],
    )


def test_translator_materializes_task_toml_with_t_bench_env(tmp_path: Path) -> None:
    """AC-1 translator-level: spec_to_job_config produces a TaskConfig whose
    path's task.toml carries the six T_BENCH_* env keys."""
    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    spec = _ade_bench_spec(ade_bench_root)
    cfg, _ = spec_to_job_config(
        spec=spec,
        job_name="pkg23-test",
        jobs_dir=tmp_path,
        home=tmp_path / "home",
    )
    assert len(cfg.tasks) == 1
    task_toml = tomllib.loads(
        (cfg.tasks[0].path / "task.toml").read_text()
    )
    env = task_toml["environment"]["env"]
    assert "T_BENCH_REPO_ROOT" in env
    assert env["T_BENCH_REPO_ROOT"] == str(ade_bench_root)


def test_harbor_dab_translator_does_not_invoke_ade_bench_materializer(
    tmp_path: Path, monkeypatch
) -> None:
    """AC-2 gating: harbor-DAB translator path never reaches
    materialize_local_task. Structural assertion via monkeypatch trap."""
    from razorback.benchmarks.ade_bench import tasks as ade_tasks

    def _trap(*a, **kw):
        raise AssertionError(
            "AC-2: harbor-DAB translator MUST NOT invoke ade-bench's "
            "materialize_local_task; T_BENCH_* keys must NOT leak into "
            "harbor-DAB tasks"
        )

    monkeypatch.setattr(ade_tasks, "materialize_local_task", _trap, raising=True)

    # Use the harbor-DAB test fixture path; if no fixture exists, this test
    # is documentary — the assertion's monkeypatch trap is the contract.
    # Structural review: read translate._build_harbor_dab to confirm it
    # never imports from razorback.benchmarks.ade_bench.tasks. If true,
    # the monkeypatch trap is unreachable from the harbor-DAB code path.
    import razorback.translate as translate_module
    src = Path(translate_module.__file__).read_text()
    # _build_harbor_dab is the DAB code path; assert it does NOT mention
    # materialize_local_task or _compute_t_bench_env in its body.
    dab_body_start = src.index("def _build_harbor_dab")
    dab_body_end = src.index("\n\ndef ", dab_body_start + 1) if "\n\ndef " in src[dab_body_start + 1 :] else len(src)
    dab_body = src[dab_body_start:dab_body_end]
    assert "materialize_local_task" not in dab_body
    assert "_compute_t_bench_env" not in dab_body
    assert "T_BENCH_" not in dab_body
```

- [ ] **Step 2: Run to verify.**

```bash
uv run pytest tests/unit/test_ade_bench_translator_t_bench_env.py -v
```

Expected: PASS after Task 3 GREEN (both translator-level wiring and structural gating are satisfied by the existing translator dispatch).

- [ ] **Step 3: Commit.**

```bash
git add tests/unit/test_ade_bench_translator_t_bench_env.py
git commit -m "test(pkg23): AC-2 — translator wires T_BENCH_* for ade-bench only"
```

---

## Task 7 — AC-2 GREEN: structural confirmation (no code change)

PKG-19's translator dispatch already restricts the local-task code path to `AdeBenchLocalTaskEntry`. PKG-23 does not change the dispatch — `_compute_t_bench_env` is called ONLY from `materialize_local_task`, which is called ONLY from `_build_ade_bench`, which is called ONLY when `spec.benchmark` is `AdeBenchBenchmarkBlock`. The structural gating Task 6 asserts is therefore satisfied with no code change. This task is documentation-only.

- [ ] **Step 1: Add a comment in `_compute_t_bench_env` reinforcing the gating.**

```python
def _compute_t_bench_env(
    *,
    ade_bench_root: Path,
    view_dir: Path,
    task_slug: str,
) -> dict[str, str]:
    # Called only from materialize_local_task → invoked only on
    # AdeBenchLocalTaskEntry by translate._build_ade_bench. Harbor-DAB
    # and other benchmark kinds never reach this function.
    ...
```

- [ ] **Step 2: Verify Task 6 still passes (it should, this is a comment-only change).**

- [ ] **Step 3: Commit.**

```bash
git add src/razorback/benchmarks/ade_bench/tasks.py
git commit -m "docs(pkg23): AC-2 — note ade-bench-only call site for _compute_t_bench_env"
```

---

## Task 8 — AC-3 LIVE: validation-stage smoke (placeholder)

PKG-23's implementation stage does NOT run `rk run` against airbnb001 — the live smoke is a validation-stage step. Implementation stage emits a PROBE SPEC (or confirms the PKG-19-shipped probe spec at `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml` is still correct for PKG-23's contract) and a stage-report deviation if AC-3 needs to defer.

- [ ] **Step 1: Verify the existing probe spec covers PKG-23.**

```bash
cat examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml
```

Confirm:
- `benchmark.kind: ade-bench`
- `benchmark.ade_bench_root: ~/git/ade-bench`
- `benchmark.db_type: duckdb` and `benchmark.project_type: dbt` (so PKG-20's `_select_compose_variant` picks `docker-compose-duckdb-dbt.yaml`)
- `benchmark.tasks[0].slug: airbnb001`

If `db_type`/`project_type` are missing from the existing spec (PKG-19 might have shipped before PKG-20), add them in this task.

- [ ] **Step 2: Verify the spec freezes cleanly under PKG-23 changes.**

```bash
uv run rk freeze examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml --out /tmp/pkg23-frozen.yaml
```

Expected: no errors. (No live API key required; freeze is offline.)

- [ ] **Step 3: Do NOT dispatch `rk run`.**

The live smoke runs in PKG-23's validation stage with `ANTHROPIC_API_KEY` set (.env / paid API tier per captain standing orders). Implementation stage emits a stage-report note that AC-3 is deferred to validation.

- [ ] **Step 4: If the existing spec needs amendment, commit.**

```bash
git add examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml
git commit -m "feat(pkg23): pin db_type/project_type on airbnb001 probe spec"
```

(Skip if no amendment needed.)

---

## Task 9 — AC-4 documentation: client-image build path

**Files:**
- Modify: `docs/razorback-implementation/pkg23-harbor-shaped-compose-for-ade-bench.md` (entity body, NOT frontmatter).

- [ ] **Step 1: Append a §Build paths section to the entity body.**

After the existing §Out of scope, add:

```markdown
## Build paths (AC-4 documentation)

PKG-23 wires `T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME=ade-bench-client-{task_slug}:latest`. It does NOT build the image. The build path lives in ade-bench upstream:

- **Build context:** `~/git/ade-bench/` (i.e., `T_BENCH_REPO_ROOT`).
- **Dockerfile (duckdb-dbt variant):** `docker/base/Dockerfile.duckdb-dbt`.
- **Sibling variants:** `docker/base/Dockerfile.snowflake-dbt`, `docker/base/Dockerfile.snowflake-dbtf`.
- **Build command (manual, pre-`rk run`):**

  ```bash
  cd ~/git/ade-bench
  docker build -f docker/base/Dockerfile.duckdb-dbt -t ade-bench-client-airbnb001:latest .
  ```

  Note: the upstream Dockerfile is variant-keyed (one per db_type/project_type), NOT task-keyed. A single built image with the variant-prefixed tag covers every task in that variant; razorback's per-task `ade-bench-client-{task_slug}:latest` is a per-task ALIAS pointing at the variant image (or the user can build per-task with `--build-arg`s — out of PKG-23 scope to choose).

- **Follow-up entity:** PKG-XX `ade-bench-client image build path` — wire a `razorback ade-bench setup` command analogous to dataagentbench's `benchmark/setup.sh` that pre-builds all four variant images and tags them with the razorback-side naming convention.
```

- [ ] **Step 2: Append a flag noting the AC-1 `T_BENCH_REPO_ROOT` correction.**

In the entity body's §Acceptance criteria AC-1 section (lines 67–80 area), append a note (BELOW the existing AC-1 prose, NOT a frontmatter edit):

```markdown
**AC-1 correction (PKG-23 plan §Mechanism-precise architectural finding):** `T_BENCH_REPO_ROOT` resolves to `ade_bench_root` (the `~/git/ade-bench` checkout), NOT the materialized view-dir. The view-dir lacks the `docker/` subtree that ade-bench's compose template references via `dockerfile: docker/base/Dockerfile.duckdb-dbt`. Upstream ade-bench's own `DockerComposeManager` sets `repo_root=str(REPO_ROOT)` to the same value (`ade_bench/terminal/docker_compose_manager.py:86`).
```

- [ ] **Step 3: Commit.**

```bash
git add docs/razorback-implementation/pkg23-harbor-shaped-compose-for-ade-bench.md
git commit -m "docs(pkg23): AC-4 build paths + AC-1 T_BENCH_REPO_ROOT correction"
```

---

## Task 10 — Full pytest sweep (regression gate)

**Files:** none modified.

- [ ] **Step 1: Run the full sweep.**

```bash
cd /Users/clkao/git/razorback
uv run pytest -x --timeout=60
```

Expected: all PASS. New tests landed by Tasks 2, 4, 6 must all pass; PKG-19 + PKG-20 tests must still pass.

- [ ] **Step 2: If sweep is green, no commit needed — proceed to Task 11.**

If sweep surfaces a regression in PKG-19 or PKG-20, that is a Task-3 implementation bug (the synthesized task.toml shape changed in a way that broke PKG-19's view-dir contract or PKG-20's compose-symlink contract). Diagnose + fix before proceeding.

---

## Task 11 — Validation-stage handoff (write Stage Report; do NOT run probe)

**Files:**
- Modify: `docs/razorback-implementation/pkg23-harbor-shaped-compose-for-ade-bench.md` (entity body — append `## Stage Report: implementation`).

- [ ] **Step 1: Append the implementation stage report.**

Use the ensign shared-core stage-report shape (`## Stage Report: implementation` with DONE/SKIPPED/FAILED rows for each AC + a Summary). AC-3 should be SKIPPED with rationale "live `rk run` is validation-stage scope; implementation closes AC-1/AC-2/AC-4."

- [ ] **Step 2: Verify the entity body has no edits to frontmatter.**

```bash
head -15 docs/razorback-implementation/pkg23-harbor-shaped-compose-for-ade-bench.md
```

Expected: YAML frontmatter unchanged (status: plan, started:, etc. all as-was). Only the body has new sections.

- [ ] **Step 3: Commit.**

```bash
git add docs/razorback-implementation/pkg23-harbor-shaped-compose-for-ade-bench.md
git commit -m "docs(pkg23): implementation stage report"
```

- [ ] **Step 4: Signal completion to the first officer.**

The implementation stage's terminal action is the FO completion signal (see ensign runtime adapter). Do NOT dispatch the live probe; that is the validation stage.

---

## Out-of-implementation-stage scope

- **AC-3 LIVE `rk run` against airbnb001.** Validation stage. Requires `.env` / `ANTHROPIC_API_KEY` (per captain standing orders: paid API tier).
- **Client image build (`ade-bench-client-{variant}:latest`).** Follow-up entity per Task 9; out of PKG-23 scope.
- **Layer-5 contract gap (UNKNOWN-UNKNOWN per Goal 2 spike).** Per entity §Out of scope: PKG-23 is allowed to succeed at AC-3 with the docker-socket-shared layer still broken. Validation-stage Stage Report files the next entity if the live smoke surfaces the new failure mode.
- **Multi-variant matrix dispatch.** PKG-23 ships duckdb-dbt single-variant correctness (Goal 2 T0 hits this); snowflake variants are PKG-20's scope at the variant-selection layer and are not covered by PKG-23's unit/integration tests.

## Handoff to validation stage

When implementation completes, the validation-stage worker:
1. Confirms `~/git/ade-bench` is hydrated and the `ade-bench-agent:latest` image exists locally (`docker images | grep ade-bench-agent`). If missing, validation stage stops with a captain-side dependency request.
2. Confirms `.env` carries `ANTHROPIC_API_KEY` (paid API tier per captain standing orders).
3. Builds `ade-bench-client-airbnb001:latest` per Task 9's manual command (or substitutes the variant image if the captain has it).
4. Dispatches `uv run rk run examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml`.
5. Records the verdict (CLEAN / PARTIAL / FAIL) in `## Stage Report: validation` on the entity body.
6. If the probe surfaces a NEW failure mode beyond AC-1..AC-4 (e.g., layer-5 docker-socket-shared gap), files a new pkg2X-* entity rather than re-opening PKG-23.
