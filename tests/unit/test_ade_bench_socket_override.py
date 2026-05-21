# ABOUTME: PKG-27 T4 — synthesized environment/docker-compose.yaml adds
# ABOUTME: docker-socket bind to services.main, merging upstream verbatim.

from pathlib import Path


FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def _real_ade_bench_root() -> Path | None:
    """Return /Users/clkao/git/ade-bench if present, else None.

    These tests target the real upstream compose because the unit fixtures
    ship empty `services: {}` stubs and don't exercise the merge surface.
    """
    candidate = Path("/Users/clkao/git/ade-bench")
    if (candidate / "shared" / "defaults" / "docker-compose-duckdb-dbt.yaml").exists():
        return candidate
    return None


def test_synthesized_compose_adds_docker_socket_to_main(tmp_path: Path) -> None:
    """AC-1 (mechanism): the materialized environment/docker-compose.yaml
    carries `/var/run/docker.sock:/var/run/docker.sock` under
    services.main.volumes so the bridge test.sh can `docker exec` into
    client from inside main."""
    import yaml

    real_root = _real_ade_bench_root()
    if real_root is None:
        import pytest
        pytest.skip("ade-bench checkout missing; this test reads upstream compose")

    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    materialized = materialize_local_task(
        ade_bench_root=real_root,
        task_slug="airbnb001",
        docker_image="ade-bench-agent:latest",
        cache_root=tmp_path / "cache",
        db_type="duckdb",
        project_type="dbt",
    )
    merged = yaml.safe_load(
        (materialized / "environment" / "docker-compose.yaml").read_text()
    )
    main_volumes = merged.get("services", {}).get("main", {}).get("volumes", [])
    assert "/var/run/docker.sock:/var/run/docker.sock" in main_volumes, (
        f"AC-1: services.main.volumes must include the socket bind; "
        f"got {main_volumes}"
    )


def test_synthesized_compose_preserves_client_service(tmp_path: Path) -> None:
    """AC-2: the merge preserves upstream's services.client verbatim
    (build context, image, command, environment, volumes) so docker compose
    up still resolves the client container as upstream expects."""
    import yaml

    real_root = _real_ade_bench_root()
    if real_root is None:
        import pytest
        pytest.skip("ade-bench checkout missing")

    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    materialized = materialize_local_task(
        ade_bench_root=real_root,
        task_slug="airbnb001",
        docker_image="ade-bench-agent:latest",
        cache_root=tmp_path / "cache",
        db_type="duckdb",
        project_type="dbt",
    )
    merged = yaml.safe_load(
        (materialized / "environment" / "docker-compose.yaml").read_text()
    )
    source = yaml.safe_load(
        (real_root / "shared" / "defaults" / "docker-compose-duckdb-dbt.yaml").read_text()
    )
    assert merged["services"]["client"] == source["services"]["client"], (
        "AC-2: upstream services.client must be byte-equivalent after merge; "
        f"merged={merged['services']['client']} source={source['services']['client']}"
    )


def test_synthesized_compose_is_a_real_file_not_a_symlink(tmp_path: Path) -> None:
    """PKG-27: env compose switches from PKG-20's symlink to a real
    synthesized file (the merge requires textual emission)."""
    real_root = _real_ade_bench_root()
    if real_root is None:
        import pytest
        pytest.skip("ade-bench checkout missing")

    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    materialized = materialize_local_task(
        ade_bench_root=real_root,
        task_slug="airbnb001",
        docker_image="ade-bench-agent:latest",
        cache_root=tmp_path / "cache",
        db_type="duckdb",
        project_type="dbt",
    )
    env_compose = materialized / "environment" / "docker-compose.yaml"
    assert env_compose.is_file()
    assert not env_compose.is_symlink(), (
        "PKG-27: synthesized compose must be a real file, not a symlink"
    )
