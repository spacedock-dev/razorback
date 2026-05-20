# ABOUTME: PKG-15 AC-1 end-to-end — restore.sh + bind-mount + mongo:8 actually loads BSON.
# ABOUTME: Long-marker integration. Skipped without docker; uses an in-test minimal fixture.

import shutil
import subprocess
import time
from pathlib import Path

import pytest

from razorback_plugin_dab.generate.mongo_init import render_mongo_restore_sh


def _wait_for_mongo(container: str, timeout_s: int = 30) -> None:
    deadline = time.monotonic() + timeout_s
    last_err = ""
    while time.monotonic() < deadline:
        r = subprocess.run(
            ["docker", "exec", container, "mongosh", "--quiet",
             "--eval", "db.runCommand({ping:1}).ok"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0 and "1" in r.stdout:
            return
        last_err = r.stderr
        time.sleep(1)
    raise AssertionError(f"mongo never came up in {timeout_s}s: {last_err}")


pytestmark = pytest.mark.long


def _docker_ok() -> bool:
    if shutil.which("docker") is None:
        return False
    r = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
    return r.returncode == 0


def _disk_ok(min_mb: int = 200) -> bool:
    usage = shutil.disk_usage("/tmp")
    return usage.free >= min_mb * 1024 * 1024


@pytest.mark.skipif(not _docker_ok(), reason="docker daemon not available")
@pytest.mark.skipif(not _disk_ok(), reason="<200MB free on /tmp (mongo image + dump)")
def test_mongo_init_shim_loads_bsondump_on_first_start(tmp_path: Path):
    """The smallest end-to-end exercise of the AC-1 contract.

    Mechanism under test: the .sh shim that compose.py mounts into
    /docker-entrypoint-initdb.d/00-restore-<db>.sh causes mongo:8 to
    invoke mongorestore on the BSON dump folder at first start.

    Strategy (no upstream dataset needed):
    1. Spin up a transient mongo:8, insert one doc into seed_db.things.
    2. Run mongodump against it to produce a real BSON dump dir.
    3. Tear it down.
    4. Spin up a fresh mongo:8 with:
         - the dump dir bind-mounted at /docker-entrypoint-initdb.d/seed_dump
         - the shim bind-mounted at /docker-entrypoint-initdb.d/00-restore-seed_db.sh
    5. Assert seed_db.things.countDocuments() > 0 — proves the shim ran
       mongorestore against the BSON dump on first start.
    """
    project_seed = f"pkg15seed-{tmp_path.name}"
    project_init = f"pkg15init-{tmp_path.name}"
    dump_root = tmp_path / "dump"
    dump_root.mkdir()

    try:
        # Phase 1: seed a transient mongo, dump it, tear it down.
        seed_up = subprocess.run(
            ["docker", "run", "-d", "--rm", "--name", project_seed,
             "mongo:8"],
            capture_output=True, text=True, timeout=60,
        )
        assert seed_up.returncode == 0, f"seed up failed: {seed_up.stderr}"

        _wait_for_mongo(project_seed)

        insert = subprocess.run(
            ["docker", "exec", project_seed, "mongosh", "--quiet", "--eval",
             "db.getSiblingDB('seed_db').getCollection('things').insertOne({hello: 'pkg15'})"],
            capture_output=True, text=True, timeout=60,
        )
        assert insert.returncode == 0, f"seed insert failed: {insert.stderr}"

        dump = subprocess.run(
            ["docker", "exec", project_seed, "mongodump",
             "--db", "seed_db", "--out", "/tmp/seed_dump"],
            capture_output=True, text=True, timeout=60,
        )
        assert dump.returncode == 0, f"mongodump failed: {dump.stderr}"

        cp = subprocess.run(
            ["docker", "cp", f"{project_seed}:/tmp/seed_dump/.", str(dump_root)],
            capture_output=True, text=True, timeout=60,
        )
        assert cp.returncode == 0, f"docker cp failed: {cp.stderr}"
        subprocess.run(["docker", "stop", project_seed], capture_output=True, timeout=60)

        # Phase 2: shape the dump like upstream (<dump_basename>/<db_name>/*.bson)
        dump_basename = "seed_dump"
        shaped = tmp_path / dump_basename
        shaped.mkdir()
        # docker cp puts the dump contents directly into dump_root as <db_name>/<coll>.bson.
        seed_db_dir = dump_root / "seed_db"
        assert seed_db_dir.is_dir(), f"expected {seed_db_dir} from mongodump"
        shutil.move(str(seed_db_dir), str(shaped / "seed_db"))

        # Phase 3: render the shim and run it through mongo:8's init.d.
        shim_path = tmp_path / "restore-seed_db.sh"
        shim_path.write_text(render_mongo_restore_sh(
            db_name="seed_db", dump_folder_basename=dump_basename,
        ))
        shim_path.chmod(0o755)

        run = subprocess.run(
            ["docker", "run", "-d", "--rm", "--name", project_init,
             "-v", f"{shaped}:/docker-entrypoint-initdb.d/{dump_basename}:ro",
             "-v", f"{shim_path}:/docker-entrypoint-initdb.d/00-restore-seed_db.sh:ro",
             "mongo:8"],
            capture_output=True, text=True, timeout=60,
        )
        assert run.returncode == 0, f"init run failed: {run.stderr}"

        _wait_for_mongo(project_init, timeout_s=60)
        # Poll countDocuments until init.d / mongorestore finishes.
        count = -1
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            probe = subprocess.run(
                ["docker", "exec", project_init, "mongosh", "--quiet", "--eval",
                 "db.getSiblingDB('seed_db').getCollection('things').countDocuments()"],
                capture_output=True, text=True, timeout=15,
            )
            if probe.returncode == 0:
                last = [ln for ln in probe.stdout.strip().splitlines() if ln.strip()]
                if last:
                    try:
                        count = int(last[-1].strip())
                        if count > 0:
                            break
                    except ValueError:
                        pass
            time.sleep(1)
        assert count > 0, f"shim did not load BSON; final count={count}"
    finally:
        for name in (project_init, project_seed):
            subprocess.run(["docker", "stop", name], capture_output=True, timeout=30)
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30)
