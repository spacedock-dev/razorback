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
