# ABOUTME: Razorback Docker environment wrapper for build/runtime env separation.
# ABOUTME: Keeps Harbor Docker behavior while letting image builds reach the network.

import asyncio
import asyncio.subprocess

from harbor.environments.base import ExecResult
from harbor.environments.docker.docker import (
    DockerEnvironment,
    _sanitize_docker_compose_project_name,
)

from razorback.agents.proxy import PROXY_BLOCK_ENV


_BUILD_PROXY_ENV_KEYS = frozenset(
    key for key in PROXY_BLOCK_ENV if "proxy" in key.lower()
)


class ProxySeparatedDockerEnvironment(DockerEnvironment):
    """DockerEnvironment that does not pass runtime proxy blocks to builds."""

    def _compose_subprocess_env(self, command: list[str]) -> dict[str, str]:
        env = self._env_vars.to_env_dict(include_os_env=True)
        if self._compose_task_env:
            env.update(self._compose_task_env)
        if self._persistent_env:
            env.update(self._persistent_env)
        if command and command[0] == "build":
            for key in _BUILD_PROXY_ENV_KEYS:
                env.pop(key, None)
        if self._windows_container_name:
            env["HARBOR_CONTAINER_NAME"] = self._windows_container_name
        return env

    async def _run_docker_compose_command(
        self, command: list[str], check: bool = True, timeout_sec: int | None = None
    ) -> ExecResult:
        """Run docker compose with build-time proxy variables removed."""
        full_command = [
            "docker",
            "compose",
            "--project-name",
            _sanitize_docker_compose_project_name(self.session_id),
            "--project-directory",
            str(self.environment_dir.resolve().absolute()),
        ]
        for path in self._docker_compose_paths:
            full_command.extend(["-f", str(path.resolve().absolute())])
        full_command.extend(command)

        process = await asyncio.create_subprocess_exec(
            *full_command,
            env=self._compose_subprocess_env(command),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        try:
            if timeout_sec:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout_sec
                )
            else:
                stdout_bytes, stderr_bytes = await process.communicate()
        except asyncio.TimeoutError:
            process.terminate()
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=5
                )
            except asyncio.TimeoutError:
                process.kill()
                stdout_bytes, stderr_bytes = await process.communicate()
            raise RuntimeError(f"Command timed out after {timeout_sec} seconds")

        stdout = stdout_bytes.decode(errors="replace") if stdout_bytes else None
        stderr = stderr_bytes.decode(errors="replace") if stderr_bytes else None
        result = ExecResult(
            stdout=stdout,
            stderr=stderr,
            return_code=process.returncode or 0,
        )

        if check and result.return_code != 0:
            raise RuntimeError(
                f"Docker compose command failed for environment {self.environment_name}. "
                f"Command: {' '.join(full_command)}. "
                f"Return code: {result.return_code}. "
                f"Stdout: {result.stdout}. "
                f"Stderr: {result.stderr}. "
            )

        return result
