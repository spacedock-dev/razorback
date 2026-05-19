# ABOUTME: Per-field provenance resolvers (§6.4).
# ABOUTME: Each resolver is a pure function with externals dependency-injected.
# ABOUTME: Codex/OpenAI model resolution is deferred to M6/M7.

from __future__ import annotations

import hashlib
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from razorback.provenance.retry import retry_with_backoff


def resolve_model_version(
    model_alias: str,
    *,
    client_factory: Callable[[], Any] | None = None,
    is_transient: Callable[[Exception], bool] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> tuple[str, str]:
    """Resolve a model alias to (dated_id, api_timestamp) via the Anthropic SDK.

    `client_factory` defaults to `anthropic.Anthropic()` (reads ANTHROPIC_API_KEY).
    `is_transient` defaults to "exception with status_code in (502, 503, 504)".
    """
    client = (client_factory or _default_anthropic_client)()
    sleep_fn = sleep or time.sleep
    pred = is_transient if is_transient is not None else _default_is_transient
    model = retry_with_backoff(
        lambda: client.models.retrieve(model_alias),
        is_transient=pred,
        max_attempts=5,
        base_delay=0.5,
        sleep=sleep_fn,
    )
    resolved_id = model.id
    resolved_at = (
        model.created_at if isinstance(model.created_at, str) else str(model.created_at)
    )
    return resolved_id, resolved_at


def _default_anthropic_client() -> Any:
    import anthropic

    return anthropic.Anthropic()


def _default_is_transient(exc: Exception) -> bool:
    code = getattr(exc, "status_code", None)
    return code in (502, 503, 504)


def resolve_image_digest(
    image_ref: str,
    *,
    docker: Callable[[str], str] | None = None,
) -> str | None:
    """Pin the docker image digest via `docker image inspect`."""
    runner = docker or _default_docker_inspect
    try:
        out = runner(image_ref)
    except Exception:
        return None
    return out.strip() or None


def _default_docker_inspect(image_ref: str) -> str:
    result = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{ .Id }}", image_ref],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def resolve_agent_cli_hash(
    binary_name: str,
    *,
    which: Callable[[str], str | None] | None = None,
) -> str | None:
    """SHA-256 the agent's CLI binary. Returns None if not on $PATH."""
    locator = which or shutil.which
    path = locator(binary_name)
    if path is None:
        return None
    h = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return f"sha256:{h}"


def resolve_harness_git_sha(
    repo_root: Path,
    *,
    git_runner: Callable[[Path, tuple[str, ...]], str] | None = None,
) -> str | None:
    """`git rev-parse HEAD` against the consuming repo. None on failure."""
    runner = git_runner or _default_git_runner
    try:
        out = runner(repo_root, ("git", "rev-parse", "HEAD"))
    except Exception:
        return None
    sha = out.strip()
    return sha or None


def _default_git_runner(repo_root: Path, cmd: tuple[str, ...]) -> str:
    result = subprocess.run(
        list(cmd), cwd=repo_root, capture_output=True, text=True, check=True
    )
    return result.stdout


def _import_harbor() -> Any:
    import harbor

    return harbor


def resolve_harbor_version() -> str:
    """`harbor.__version__`. Always resolvable when harbor is installed."""
    return _import_harbor().__version__


def resolve_prompt_hashes(prompt_paths: list[Path]) -> dict[str, str] | None:
    """Content-hash every prompt file referenced by the spec.

    Returns None if any path is missing. Returns an empty dict when the list is empty.
    """
    out: dict[str, str] = {}
    for p in prompt_paths:
        if not Path(p).is_file():
            return None
        h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
        out[str(p)] = f"sha256:{h}"
    return out
