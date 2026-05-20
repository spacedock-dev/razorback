# ABOUTME: Per-field provenance resolvers (§6.4).
# ABOUTME: Each resolver is a pure function with externals dependency-injected.
# ABOUTME: Codex/OpenAI model resolution is deferred to M6/M7.

from __future__ import annotations

import hashlib
import shutil
import subprocess
import time
from importlib.metadata import (
    PackageNotFoundError,
    distribution as _distribution,
    entry_points,
)
from pathlib import Path
from typing import Any, Callable, Iterator

from razorback.provenance.retry import retry_with_backoff


_SOLVER_WORKFLOW_SKIP_DIRS = frozenset({".git", "__pycache__", ".pytest_cache"})
_SOLVER_WORKFLOW_SKIP_FILES = frozenset({".DS_Store"})


_PLUGIN_ENTRY_POINT_GROUPS: tuple[str, ...] = (
    "harbor.agents",
    "harbor.benchmarks",
    "razorback.plugins",
)


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


# spec §8.2: recursive content hash, pinned under provenance.yaml.solver_workflow_hash
def resolve_solver_workflow_hash(dir_path: Path) -> str | None:
    """Content-hash a `solver_workflow/` directory recursively.

    Walks regular files in POSIX-relative-path sorted order. Each file frames as
    `len(path):4 + path:utf-8 + len(content):8 + content` so two files with the
    same concatenation but different path boundaries hash differently.
    Skips `.git/`, `__pycache__/`, `.pytest_cache/`, `.DS_Store` (not semantic
    content). Returns `None` when `dir_path` does not exist or is not a directory.
    """
    root = Path(dir_path)
    if not root.is_dir():
        return None
    h = hashlib.sha256()
    for rel_posix, content in _walk_solver_workflow(root):
        path_bytes = rel_posix.encode("utf-8")
        h.update(len(path_bytes).to_bytes(4, "big"))
        h.update(path_bytes)
        h.update(len(content).to_bytes(8, "big"))
        h.update(content)
    return f"sha256:{h.hexdigest()}"


def _walk_solver_workflow(root: Path) -> Iterator[tuple[str, bytes]]:
    entries: list[tuple[str, Path]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        parts = rel.parts
        if any(part in _SOLVER_WORKFLOW_SKIP_DIRS for part in parts[:-1]):
            continue
        if parts[-1] in _SOLVER_WORKFLOW_SKIP_FILES:
            continue
        entries.append(("/".join(parts), path))
    entries.sort(key=lambda item: item[0])
    for rel_posix, path in entries:
        yield rel_posix, path.read_bytes()


# AC-1: harbor.agents + harbor.benchmarks + razorback.plugins entry-point inventory.
def resolve_plugin_inventory(
    *,
    entry_points_fn: Callable[..., Any] | None = None,
    distribution_fn: Callable[[str], Any] | None = None,
) -> dict[str, list[dict[str, str]]]:
    """List installed harbor adapter + harbor agent plugins for `provenance.yaml`.

    Scans the three plugin entry-point groups (`harbor.agents`,
    `harbor.benchmarks`, `razorback.plugins`) and emits one row per entry point
    with its package distribution name, version, group, and entry-point name.
    Rows sort by `(group, name)` for determinism. Returns
    `{"plugins": []}` when no plugins are installed (a valid environment).
    """
    ep_fn = entry_points_fn or entry_points
    dist_fn = distribution_fn or _distribution
    rows: list[dict[str, str]] = []
    for group in _PLUGIN_ENTRY_POINT_GROUPS:
        try:
            eps = ep_fn(group=group)
        except TypeError:
            eps = ep_fn().select(group=group)  # py3.10 compat fallback
        for ep in eps:
            dist_name = _entry_point_distribution_name(ep)
            if dist_name is None:
                continue
            try:
                dist = dist_fn(dist_name)
            except PackageNotFoundError:
                continue
            rows.append(
                {
                    "group": group,
                    "name": ep.name,
                    "distribution": dist.metadata["Name"],
                    "version": dist.version,
                }
            )
    rows.sort(key=lambda r: (r["group"], r["name"]))
    return {"plugins": rows}


def _entry_point_distribution_name(ep: Any) -> str | None:
    dist = getattr(ep, "dist", None)
    if dist is not None:
        return getattr(dist, "name", None) or dist.metadata["Name"]
    return None
