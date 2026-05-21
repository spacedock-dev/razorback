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
