# ABOUTME: PKG-37 — Docker build subprocesses must not inherit runtime proxy block.
# ABOUTME: Runtime docker compose exec still carries the same proxy env into commands.

from pathlib import Path

import pytest
from harbor.environments.base import ExecResult
from harbor.models.task.config import EnvironmentConfig
from harbor.models.trial.paths import TrialPaths

from razorback.agents.proxy import PROXY_BLOCK_ENV, PROXY_EXEMPT_HOSTS
from razorback.environments.docker import ProxySeparatedDockerEnvironment


class _Process:
    returncode = 0

    async def communicate(self):
        return b"ok", b""


def _environment(tmp_path: Path) -> ProxySeparatedDockerEnvironment:
    environment_dir = tmp_path / "environment"
    environment_dir.mkdir()
    (environment_dir / "Dockerfile").write_text("FROM python:3.11-slim\n")
    trial_paths = TrialPaths(tmp_path / "trial")
    trial_paths.mkdir()
    return ProxySeparatedDockerEnvironment(
        environment_dir=environment_dir,
        environment_name="proxy-test",
        session_id="proxy-test__0",
        trial_paths=trial_paths,
        task_env_config=EnvironmentConfig(),
        persistent_env=dict(PROXY_BLOCK_ENV),
    )


@pytest.mark.asyncio
async def test_build_compose_command_removes_proxy_block_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, str] = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured.update(kwargs["env"])
        return _Process()

    monkeypatch.setattr(
        "asyncio.create_subprocess_exec", fake_create_subprocess_exec
    )

    env = _environment(tmp_path)
    await env._run_docker_compose_command(["build"])

    assert "HTTP_PROXY" not in captured
    assert "HTTPS_PROXY" not in captured
    assert "http_proxy" not in captured
    assert "https_proxy" not in captured
    assert "NO_PROXY" not in captured
    assert "no_proxy" not in captured
    assert captured["HF_HUB_OFFLINE"] == "1"


@pytest.mark.asyncio
async def test_runtime_exec_keeps_proxy_block_env(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    captured: list[str] = []

    async def fake_run(command, check=True, timeout_sec=None):
        captured.extend(command)
        return ExecResult(stdout="", stderr=None, return_code=0)

    env._run_docker_compose_command = fake_run  # type: ignore[method-assign]

    await env.exec("python -V")

    assert "HTTP_PROXY=http://127.0.0.1:1" in captured
    assert "HTTPS_PROXY=http://127.0.0.1:1" in captured
    assert f"NO_PROXY={PROXY_EXEMPT_HOSTS}" in captured
    assert "api.openai.com" in next(item for item in captured if item.startswith("NO_PROXY="))
