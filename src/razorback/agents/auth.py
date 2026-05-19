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
    mode: Literal["api-key", "oauth"]
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


def _read_claude_token(home: Path) -> str | None:
    """Mirror run_experiment.py:1897-1902 — ~/.claude/benchmark-token, stripped."""
    token_path = Path(home) / ".claude" / "benchmark-token"
    if not token_path.exists():
        return None
    contents = token_path.read_text().strip()
    return contents or None


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
