# ABOUTME: Claude CLI auth — .env-only ANTHROPIC_API_KEY discovery + ~/.claude/benchmark-token fallback.
# ABOUTME: Discipline copied verbatim from run_experiment.py:1897-1917 + 1993-2003.

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values

from razorback.errors import RazorbackError


class AuthDiscoveryError(RazorbackError):
    """No usable credential found in .env or ~/.claude/benchmark-token."""


@dataclass(frozen=True)
class AuthResolution:
    mode: Literal["api-key", "oauth", "auth-json"]
    env: dict[str, str] = field(default_factory=dict)


def _load_env_api_key(project_root: Path) -> str | None:
    """Mirror run_experiment.py:1905-1917 — .env-only, NOT os.environ.

    Returns the literal value if present and non-empty; None otherwise.
    """
    env_path = Path(project_root) / ".env"
    if not env_path.exists():
        return None
    values = dotenv_values(env_path)
    value = values.get("ANTHROPIC_API_KEY")
    if value is None or value == "":
        return None
    return value


def _load_dotenv_value(project_root: Path, name: str) -> str | None:
    env_path = Path(project_root) / ".env"
    if not env_path.exists():
        return None
    values = dotenv_values(env_path)
    value = values.get(name)
    if value is None or value == "":
        return None
    return value


def _read_claude_token(home: Path) -> str | None:
    """Mirror run_experiment.py:1897-1902 — ~/.claude/benchmark-token, stripped."""
    token_path = Path(home) / ".claude" / "benchmark-token"
    if not token_path.exists():
        return None
    contents = token_path.read_text().strip()
    return contents or None


def _readable_file(path: Path) -> Path | None:
    if not path.is_file():
        return None
    try:
        with path.open("rb"):
            pass
    except OSError:
        return None
    return path


def resolve_claude_auth(*, project_root: Path, home: Path | None = None) -> AuthResolution:
    """Resolve the single chosen auth credential per the precedence rule.

    Precedence (verbatim from run_experiment.py:1993-2003):
      1. ANTHROPIC_API_KEY from <project_root>/.env via dotenv_values.
      2. CLAUDE_CODE_OAUTH_TOKEN from ~/.claude/benchmark-token.

    NEVER both; NEVER os.environ. Raises AuthDiscoveryError if neither yields a credential.
    """
    home_path = Path.home() if home is None else Path(home)
    api_key = _load_env_api_key(project_root)
    if api_key is not None:
        return AuthResolution(mode="api-key", env={"ANTHROPIC_API_KEY": api_key})
    token = _read_claude_token(home_path)
    if token is not None:
        return AuthResolution(mode="oauth", env={"CLAUDE_CODE_OAUTH_TOKEN": token})
    raise AuthDiscoveryError(
        "no claude credentials found. Add ANTHROPIC_API_KEY to "
        f"{Path(project_root) / '.env'} or write a token to "
        f"{home_path / '.claude' / 'benchmark-token'}."
    )


def resolve_codex_auth(
    *, project_root: Path, home: Path | None = None
) -> AuthResolution:
    """Resolve Codex credentials from .env or the standard Codex auth file.

    Precedence:
      1. OPENAI_API_KEY from <project_root>/.env.
      2. CODEX_AUTH_JSON_PATH from <project_root>/.env, pointing at a readable file.
      3. <home>/.codex/auth.json, when readable.

    Harbor's Codex agent consumes OPENAI_API_KEY or CODEX_AUTH_JSON_PATH through
    AgentConfig.env and optionally honors OPENAI_BASE_URL for proxy-compatible
    endpoints.
    """
    project_root_path = Path(project_root)
    api_key = _load_dotenv_value(project_root, "OPENAI_API_KEY")
    base_url = _load_dotenv_value(project_root, "OPENAI_BASE_URL")
    if api_key is not None:
        env = {"OPENAI_API_KEY": api_key}
        if base_url is not None:
            env["OPENAI_BASE_URL"] = base_url
        return AuthResolution(mode="api-key", env=env)

    explicit_auth_path = _load_dotenv_value(project_root, "CODEX_AUTH_JSON_PATH")
    if explicit_auth_path is not None:
        auth_path = Path(explicit_auth_path).expanduser()
        if not auth_path.is_absolute():
            auth_path = project_root_path / auth_path
        readable_auth_path = _readable_file(auth_path)
        if readable_auth_path is not None:
            env = {"CODEX_AUTH_JSON_PATH": str(readable_auth_path)}
            if base_url is not None:
                env["OPENAI_BASE_URL"] = base_url
            return AuthResolution(mode="auth-json", env=env)

    home_path = Path.home() if home is None else Path(home)
    default_auth_path = _readable_file(home_path / ".codex" / "auth.json")
    if default_auth_path is not None:
        env = {"CODEX_AUTH_JSON_PATH": str(default_auth_path)}
        if base_url is not None:
            env["OPENAI_BASE_URL"] = base_url
        return AuthResolution(mode="auth-json", env=env)

    raise AuthDiscoveryError(
        "no codex credentials found. Add OPENAI_API_KEY to the project .env, "
        "set CODEX_AUTH_JSON_PATH in the project .env to a readable auth file, "
        "or create ~/.codex/auth.json."
    )
