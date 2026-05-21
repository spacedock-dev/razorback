# ABOUTME: PKG-27 T5 — host-side integration test that runs the synthesized
# ABOUTME: tests/test.sh with a stub `docker` on PATH and asserts reward.txt.

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


FIXTURES = Path(__file__).parent.parent / "fixtures" / "ade_bench"


def _real_ade_bench_root() -> Path | None:
    candidate = Path("/Users/clkao/git/ade-bench")
    if (candidate / "shared" / "defaults" / "run-tests.sh").exists():
        return candidate
    return None


def _materialize_airbnb001(tmp_path: Path) -> Path:
    from razorback.benchmarks.ade_bench.tasks import materialize_local_task

    real_root = _real_ade_bench_root()
    if real_root is None:
        pytest.skip("ade-bench checkout missing")
    return materialize_local_task(
        ade_bench_root=real_root,
        task_slug="airbnb001",
        docker_image="ade-bench-agent:latest",
        cache_root=tmp_path / "cache",
        db_type="duckdb",
        project_type="dbt",
    )


def _run_test_sh(*, materialized: Path, tmp_path: Path, stdout: str) -> Path:
    """Invoke the materialized tests/test.sh with PATH redirected to a stub
    `docker` that echoes `stdout`. Returns the path to reward.txt."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    stdout_fixture = tmp_path / "dbt-stdout.txt"
    stdout_fixture.write_text(stdout)
    docker_stub = bin_dir / "docker"
    docker_stub.write_text(
        f"#!/bin/bash\n"
        # Drain any stdin (the test.sh pipes tar streams in for staging).
        f"if ! tty -s <&0; then cat >/dev/null 2>&1 || true; fi\n"
        f"cat {stdout_fixture}\n"
    )
    docker_stub.chmod(
        docker_stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
    )

    # Re-route REWARD_DIR to a tmp path so the test does not require root.
    reward_dir = tmp_path / "logs" / "verifier"
    reward_dir.mkdir(parents=True)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME"] = "airbnb001-client"
    env["REWARD_DIR"] = str(reward_dir)

    test_sh = materialized / "tests" / "test.sh"

    # Copy the test.sh into the cwd so its hardcoded /tests/*.sql glob resolves
    # against a tmp dir we control. We can't rewrite the script — it must run
    # as-is. Workaround: bind-equivalent of /tests/ via a chroot-ish approach
    # is overkill. Instead, the test.sh's `/tests/*.sql` glob fails silently
    # if /tests/ has no .sql files; that branch still runs the parser against
    # the stubbed docker output and emits the expected reward.
    proc = subprocess.run(
        ["bash", str(test_sh)],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"test.sh failed: rc={proc.returncode}\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )
    return reward_dir / "reward.txt"


def test_test_sh_emits_1_for_all_pass_dbt_stdout(tmp_path: Path) -> None:
    materialized = _materialize_airbnb001(tmp_path / "mat")
    reward = _run_test_sh(
        materialized=materialized,
        tmp_path=tmp_path / "run",
        stdout="""\
[ade-bench] expected_test_count=10
1 of 10 PASS test_a ............................................................ [PASS in 0.01s]
2 of 10 PASS test_b ............................................................ [PASS in 0.01s]
3 of 10 PASS test_c ............................................................ [PASS in 0.01s]
4 of 10 PASS test_d ............................................................ [PASS in 0.01s]
5 of 10 PASS test_e ............................................................ [PASS in 0.01s]
6 of 10 PASS test_f ............................................................ [PASS in 0.01s]
7 of 10 PASS test_g ............................................................ [PASS in 0.01s]
8 of 10 PASS test_h ............................................................ [PASS in 0.01s]
9 of 10 PASS test_i ............................................................ [PASS in 0.01s]
10 of 10 PASS test_j ........................................................... [PASS in 0.01s]
Done. PASS=10 WARN=0 ERROR=0 SKIP=0 TOTAL=10
""",
    )
    assert reward.read_text().strip() == "1"


def test_test_sh_emits_0_for_any_fail(tmp_path: Path) -> None:
    materialized = _materialize_airbnb001(tmp_path / "mat")
    reward = _run_test_sh(
        materialized=materialized,
        tmp_path=tmp_path / "run",
        stdout="""\
[ade-bench] expected_test_count=2
1 of 2 PASS test_a ............................................................. [PASS in 0.01s]
2 of 2 FAIL 1 test_b ........................................................... [FAIL 1 in 0.00s]
Done. PASS=1 WARN=0 ERROR=1 SKIP=0 TOTAL=2
""",
    )
    assert reward.read_text().strip() == "0"


def test_test_sh_emits_0_when_parsed_count_less_than_expected(tmp_path: Path) -> None:
    materialized = _materialize_airbnb001(tmp_path / "mat")
    reward = _run_test_sh(
        materialized=materialized,
        tmp_path=tmp_path / "run",
        stdout="""\
[ade-bench] expected_test_count=5
1 of 2 PASS test_a ............................................................. [PASS in 0.01s]
2 of 2 PASS test_b ............................................................. [PASS in 0.01s]
Done. PASS=2 WARN=0 ERROR=0 SKIP=0 TOTAL=2
""",
    )
    assert reward.read_text().strip() == "0"
