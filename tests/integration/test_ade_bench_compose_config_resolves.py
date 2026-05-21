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


def test_docker_compose_config_resolves_t_bench_placeholders(tmp_path: Path) -> None:
    """AC-1 integration: invoke ``docker compose config`` against the
    materialized compose + the synthesized [environment.env] dict; assert no
    ${T_BENCH_*} placeholders remain in the resolved compose output."""
    ade_bench_root = Path.home() / "git" / "ade-bench"
    compose_template = (
        ade_bench_root / "shared" / "defaults" / "docker-compose-duckdb-dbt.yaml"
    )
    if not compose_template.exists():
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

    env = os.environ.copy()
    env.update(env_block)

    compose_path = materialized / "environment" / "docker-compose.yaml"
    assert compose_path.exists(), (
        "PKG-20 invariant: materialized view-dir must contain "
        "environment/docker-compose.yaml"
    )

    # PKG-27: the materialized env compose now carries a partial `main`
    # block (socket-bind override). The full stack stacks harbor's base
    # compose (which provides `main`'s image/build) underneath. Stack them
    # here so `docker compose config` reflects the same merged shape harbor
    # uses at runtime via `_docker_compose_paths`.
    import harbor.environments.docker as harbor_docker_pkg

    harbor_dir = Path(harbor_docker_pkg.__file__).parent
    base_compose = harbor_dir / "docker-compose-base.yaml"
    build_compose = harbor_dir / "docker-compose-build.yaml"
    env.setdefault("HOST_VERIFIER_LOGS_PATH", str(tmp_path / "verifier"))
    env.setdefault("HOST_AGENT_LOGS_PATH", str(tmp_path / "agent"))
    env.setdefault("HOST_ARTIFACTS_PATH", str(tmp_path / "artifacts"))
    env.setdefault("ENV_VERIFIER_LOGS_PATH", "/logs/verifier")
    env.setdefault("ENV_AGENT_LOGS_PATH", "/logs/agent")
    env.setdefault("ENV_ARTIFACTS_PATH", "/logs/artifacts")
    env.setdefault("CONTEXT_DIR", str(materialized / "environment"))
    env.setdefault("CPUS", "1")
    env.setdefault("MEMORY", "2048m")
    for k in ("HOST_VERIFIER_LOGS_PATH", "HOST_AGENT_LOGS_PATH", "HOST_ARTIFACTS_PATH"):
        Path(env[k]).mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            "docker", "compose",
            "-f", str(base_compose),
            "-f", str(build_compose),
            "-f", str(compose_path),
            "config",
        ],
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
    # PKG-27: assert the docker socket bind is present on main after merge.
    assert "/var/run/docker.sock" in result.stdout, (
        f"PKG-27: services.main must have the docker socket bind in the "
        f"merged compose; got:\n{result.stdout}"
    )
