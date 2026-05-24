# ABOUTME: AC-3 — Harbor preserves file-backed DB main mounts as readable and read-only.

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from harbor.environments.docker.docker import DockerEnvironment
from harbor.models.task.config import EnvironmentConfig
from harbor.models.trial.paths import TrialPaths
from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="docker not available — AC-3 file-backed DB read-only mount test",
)


def _synthetic_data_root(root: Path) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_bookreview"
    (qdir / "query_dataset").mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump({
        "db_clients": {
            "review_database": {
                "db_type": "sqlite",
                "db_path": "query_dataset/tiny.sqlite",
            }
        }
    }))
    (qdir / "db_description.txt").write_text("Bookreview schema.")
    (qdir / "query_dataset" / "tiny.sqlite").write_bytes(
        b"SQLite format 3\x00" + b"\x00" * 256
    )
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "synthetic"}')
    return data_root


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _image_available(image: str) -> bool:
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0


def test_file_backed_db_main_mount_is_readable_and_read_only(tmp_path: Path):
    image = "python:3.12"
    if not _image_available(image):
        pytest.skip(f"{image} image unavailable — AC-3 file-backed DB readonly mount test")

    data_root = _synthetic_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        docker_image=image,
        container_workdir="/workspace",
        materialize_mode="bind",
    )
    task_dir = manifest[0]["task_dir"]
    source_db = data_root / "query_bookreview" / "query_dataset" / "tiny.sqlite"
    before = _sha256(source_db)

    async def exercise_harbor() -> tuple[dict, int, str, int, str]:
        env = DockerEnvironment(
            environment_dir=task_dir / "environment",
            environment_name="rb-file-backed-db-readonly",
            session_id=f"rb-file-backed-db-readonly-{tmp_path.name}",
            trial_paths=TrialPaths(trial_dir=tmp_path / "trial"),
            task_env_config=EnvironmentConfig(
                docker_image=image,
                workdir="/workspace",
                allow_internet=True,
            ),
        )
        try:
            config_result = await env._run_docker_compose_command(
                ["config", "--format", "json"],
                timeout_sec=60,
            )
            await env.start(force_build=False)
            read = await env.exec(
                "test -r /workspace/query_dataset/tiny.sqlite && "
                "head -c 16 /workspace/query_dataset/tiny.sqlite | od -An -tx1",
                timeout_sec=30,
            )
            write = await env.exec(
                "printf X >> /workspace/query_dataset/tiny.sqlite",
                timeout_sec=30,
            )
            return (
                json.loads(config_result.stdout or "{}"),
                read.return_code,
                read.stdout or "",
                write.return_code,
                (write.stdout or "") + (write.stderr or ""),
            )
        finally:
            await env.stop(delete=False)

    try:
        compose_config, read_code, read_stdout, write_code, write_output = asyncio.run(
            exercise_harbor()
        )
    except RuntimeError as exc:
        pytest.skip(f"Harbor docker environment unavailable for AC-3: {exc}")

    main_volumes = compose_config["services"]["main"]["volumes"]
    db_mounts = [
        volume for volume in main_volumes
        if volume.get("target") == "/workspace/query_dataset/tiny.sqlite"
    ]
    assert db_mounts and db_mounts[0].get("read_only") is True
    assert read_code == 0
    assert "53 51 4c 69 74 65 20 66 6f 72 6d 61 74 20 33 00" in read_stdout
    assert write_code != 0, f"write unexpectedly succeeded: {write_output}"
    assert _sha256(source_db) == before
