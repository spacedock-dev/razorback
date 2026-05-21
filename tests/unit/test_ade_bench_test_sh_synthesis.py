# ABOUTME: PKG-27 T2 — synthesized tests/test.sh proxies harbor verifier into
# ABOUTME: ade-bench upstream's run-tests.sh via the docker socket on `main`.

from pathlib import Path


FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def test_build_test_sh_invokes_docker_exec_on_client_container() -> None:
    """AC-2: test.sh delegates to upstream by `docker exec` into the client
    container — verifying upstream-faithfulness (no SQL/dbt reimplementation
    inside razorback)."""
    from razorback.benchmarks.ade_bench.tasks import _build_test_sh

    body = _build_test_sh(db_type="duckdb", project_type="dbt")
    assert 'docker exec' in body, (
        f"AC-2: test.sh must invoke `docker exec` to bridge into client; "
        f"body=\n{body}"
    )
    assert 'T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME' in body, (
        f"AC-2: test.sh must reference container env var; body=\n{body}"
    )


def test_build_test_sh_runs_upstream_run_tests_sh_verbatim() -> None:
    """AC-2: test.sh runs upstream's shared/defaults/run-tests.sh, not a
    razorback reimplementation of the dbt-test pipeline."""
    from razorback.benchmarks.ade_bench.tasks import _build_test_sh

    body = _build_test_sh(db_type="duckdb", project_type="dbt")
    assert 'run-tests.sh' in body, (
        f"AC-2: test.sh must invoke upstream run-tests.sh; body=\n{body}"
    )


def test_build_test_sh_forwards_db_and_project_type_flags() -> None:
    """AC-2: test.sh forwards --db-type/--project-type flags as ade-bench's
    run-dbt-test.sh expects (filters SQL files by db/project type)."""
    from razorback.benchmarks.ade_bench.tasks import _build_test_sh

    body = _build_test_sh(db_type="duckdb", project_type="dbt")
    assert '--db-type=duckdb' in body, (
        f"AC-2: test.sh must forward --db-type=duckdb; body=\n{body}"
    )
    assert '--project-type=dbt' in body, (
        f"AC-2: test.sh must forward --project-type=dbt; body=\n{body}"
    )


def test_build_test_sh_writes_reward_text_to_harbor_path() -> None:
    """AC-1: test.sh writes harbor's reward file at /logs/verifier/reward.txt
    (per harbor.models.trial.paths.EnvironmentPaths.reward_text_path)."""
    from razorback.benchmarks.ade_bench.tasks import _build_test_sh

    body = _build_test_sh(db_type="duckdb", project_type="dbt")
    assert '/logs/verifier' in body and 'reward.txt' in body, (
        f"AC-1: test.sh must write harbor's reward.txt path; body=\n{body}"
    )


def test_build_test_sh_emits_1_on_all_pass_stdout(tmp_path: Path) -> None:
    """AC-1: the synthesized parser writes `1` to reward.txt when dbt stdout
    shows all PASS results matching the upstream regex."""
    from razorback.benchmarks.ade_bench.tasks import _build_test_sh

    body = _build_test_sh(db_type="duckdb", project_type="dbt")
    _assert_reward_for_stdout(
        body=body,
        tmp_path=tmp_path,
        stdout="""\
[ade-bench] expected_test_count=2
1 of 2 PASS test_one ........................................................... [PASS in 0.01s]
2 of 2 PASS test_two ........................................................... [PASS in 0.01s]
Done. PASS=2 WARN=0 ERROR=0 SKIP=0 TOTAL=2
""",
        expected="1",
    )


def test_build_test_sh_emits_0_on_any_fail(tmp_path: Path) -> None:
    """AC-1: any FAIL test line collapses the reward to 0."""
    from razorback.benchmarks.ade_bench.tasks import _build_test_sh

    body = _build_test_sh(db_type="duckdb", project_type="dbt")
    _assert_reward_for_stdout(
        body=body,
        tmp_path=tmp_path,
        stdout="""\
[ade-bench] expected_test_count=2
1 of 2 PASS test_one ........................................................... [PASS in 0.01s]
2 of 2 FAIL 1 test_two ......................................................... [FAIL 1 in 0.00s]
Done. PASS=1 WARN=0 ERROR=1 SKIP=0 TOTAL=2
""",
        expected="0",
    )


def test_build_test_sh_emits_0_when_fewer_tests_than_expected(tmp_path: Path) -> None:
    """AC-1: expected_test_count mismatch (parsed < expected) → reward 0."""
    from razorback.benchmarks.ade_bench.tasks import _build_test_sh

    body = _build_test_sh(db_type="duckdb", project_type="dbt")
    _assert_reward_for_stdout(
        body=body,
        tmp_path=tmp_path,
        stdout="""\
[ade-bench] expected_test_count=5
1 of 2 PASS test_one ........................................................... [PASS in 0.01s]
2 of 2 PASS test_two ........................................................... [PASS in 0.01s]
Done. PASS=2 WARN=0 ERROR=0 SKIP=0 TOTAL=2
""",
        expected="0",
    )


def test_build_test_sh_emits_0_on_compilation_error(tmp_path: Path) -> None:
    """AC-1: dbt 'Compilation Error' in stdout → reward 0 (mirrors upstream
    DbtParser's has_compilation_error branch)."""
    from razorback.benchmarks.ade_bench.tasks import _build_test_sh

    body = _build_test_sh(db_type="duckdb", project_type="dbt")
    _assert_reward_for_stdout(
        body=body,
        tmp_path=tmp_path,
        stdout="""\
[ade-bench] expected_test_count=2
Compilation Error in model x
""",
        expected="0",
    )


def _assert_reward_for_stdout(
    *, body: str, tmp_path: Path, stdout: str, expected: str
) -> None:
    """Run test.sh against a stubbed `docker` on PATH that echoes the given
    dbt stdout. Asserts the reward.txt content matches `expected`."""
    import os
    import shutil
    import stat
    import subprocess

    work = tmp_path / "run"
    work.mkdir()
    (work / "logs" / "verifier").mkdir(parents=True)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stdout_fixture = tmp_path / "dbt-stdout.txt"
    stdout_fixture.write_text(stdout)
    docker_stub = bin_dir / "docker"
    docker_stub.write_text(
        f"#!/bin/bash\n"
        # Whatever args we get, just emit the canned stdout. The test.sh body
        # should pipe stdout through its parser.
        f"cat {stdout_fixture}\n"
    )
    docker_stub.chmod(docker_stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    test_sh = work / "test.sh"
    test_sh.write_text(body)
    test_sh.chmod(test_sh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME"] = "example-client"
    # The test.sh writes /logs/verifier/reward.txt. We point it at the
    # tmp tree by changing CWD and overriding the root path via a runtime hook.
    # The implementation MUST honor a REWARD_DIR env override so this test
    # works without root-mounting / on the host.
    env["REWARD_DIR"] = str(work / "logs" / "verifier")

    proc = subprocess.run(
        ["bash", str(test_sh)],
        env=env,
        cwd=work,
        capture_output=True,
        text=True,
        timeout=30,
    )

    reward_path = work / "logs" / "verifier" / "reward.txt"
    assert reward_path.exists(), (
        f"test.sh did not write {reward_path}; "
        f"stdout={proc.stdout!r}, stderr={proc.stderr!r}, rc={proc.returncode}"
    )
    actual = reward_path.read_text().strip()
    assert actual == expected, (
        f"reward mismatch: expected={expected!r} actual={actual!r}; "
        f"stdout={proc.stdout!r}, stderr={proc.stderr!r}"
    )


def test_materialize_local_task_writes_test_sh(tmp_path: Path) -> None:
    """AC-1 + AC-2: materialize_local_task synthesizes tests/test.sh under
    the view-dir alongside the SQL test files."""
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg27-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
        db_type="duckdb",
        project_type="dbt",
    )
    test_sh = materialized / "tests" / "test.sh"
    assert test_sh.exists() and test_sh.is_file(), (
        f"AC-1: tests/test.sh must exist as a real file; got {test_sh}"
    )
    assert not test_sh.is_symlink(), (
        f"AC-1: tests/test.sh must be a real file, not a symlink"
    )
    body = test_sh.read_text()
    assert body.startswith("#!/bin/bash") or body.startswith("#!/usr/bin/env bash"), (
        f"AC-1: test.sh must have a bash shebang; got first line: {body.splitlines()[0]!r}"
    )


def test_materialize_local_task_keeps_sql_tests_alongside_test_sh(tmp_path: Path) -> None:
    """AC-2: the upstream AUTO_*.sql files stay reachable under tests/ — they
    are consumed by run-tests.sh inside client at /tests/*.sql."""
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg27-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
        db_type="duckdb",
        project_type="dbt",
    )
    sql_files = list((materialized / "tests").glob("*.sql"))
    assert len(sql_files) > 0, (
        f"AC-2: tests/ must still contain SQL fixtures alongside test.sh; "
        f"got {list((materialized / 'tests').iterdir())}"
    )


def test_materialize_local_task_emits_verifier_env_for_t_bench_keys(tmp_path: Path) -> None:
    """PKG-27 T8 follow-up: [verifier.env] in task.toml must carry the
    T_BENCH_* keys so harbor's verifier exec sees them (the verifier exec
    path does NOT inherit [environment.env] — harbor only passes those to
    `docker compose up`)."""
    import tomllib
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=tmp_path / "pkg27-cache",
        db_type="duckdb",
        project_type="dbt",
    )
    task_toml = tomllib.loads((materialized / "task.toml").read_text())
    verifier_env = task_toml.get("verifier", {}).get("env", {})
    assert "T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME" in verifier_env, (
        f"PKG-27: [verifier.env] must forward T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME; "
        f"got verifier.env={verifier_env}"
    )


def test_materialize_local_task_emits_verifier_user_root(tmp_path: Path) -> None:
    """PKG-27 T1/OD-3: [verifier].user = 'root' so the bridge has docker
    socket access (dab-agent's default user `exedev` has a docker GID that
    does not match the colima socket's GID)."""
    import tomllib
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=tmp_path / "pkg27-cache",
    )
    task_toml = tomllib.loads((materialized / "task.toml").read_text())
    assert task_toml.get("verifier", {}).get("user") == "root", (
        f"PKG-27 OD-3: [verifier].user must be 'root'; got {task_toml.get('verifier')}"
    )


def test_materialize_local_task_test_sh_is_executable(tmp_path: Path) -> None:
    """AC-1: tests/test.sh is chmod +x so harbor's verifier can exec it."""
    import stat
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    ade_bench_root = (FIXTURES / "fixture_local_task_minimal").resolve()
    cache_root = tmp_path / "pkg27-cache"
    materialized = materialize_local_task(
        ade_bench_root=ade_bench_root,
        task_slug="example001",
        docker_image="ade-bench-agent:latest",
        cache_root=cache_root,
        db_type="duckdb",
        project_type="dbt",
    )
    test_sh = materialized / "tests" / "test.sh"
    mode = test_sh.stat().st_mode
    assert mode & stat.S_IXUSR, (
        f"AC-1: tests/test.sh must be user-executable; mode={oct(mode)}"
    )
