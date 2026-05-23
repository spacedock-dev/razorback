# ABOUTME: AC-3 — auth tokens are loaded from project-root .env via dotenv_values.
# ABOUTME: os.environ is NOT a fallback for ANTHROPIC_API_KEY discovery.

import pytest

from razorback.agents.auth import (
    AuthDiscoveryError,
    AuthResolution,
    resolve_claude_auth,
    resolve_codex_auth,
)


def test_anthropic_api_key_from_dotenv_wins(tmp_path):
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-from-dotenv\nCLAUDE_CODE_OAUTH_TOKEN=ignored\n")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "benchmark-token").write_text("oauth-from-home")

    resolution = resolve_claude_auth(project_root=tmp_path, home=home)
    assert resolution == AuthResolution(
        mode="api-key",
        env={"ANTHROPIC_API_KEY": "sk-from-dotenv"},
    )


def test_falls_back_to_oauth_when_dotenv_lacks_api_key(tmp_path):
    (tmp_path / ".env").write_text("# no api key here\n")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "benchmark-token").write_text("oauth-token-xyz")

    resolution = resolve_claude_auth(project_root=tmp_path, home=home)
    assert resolution == AuthResolution(
        mode="oauth",
        env={"CLAUDE_CODE_OAUTH_TOKEN": "oauth-token-xyz"},
    )


def test_never_co_mingles_both(tmp_path):
    """AC-2 negative — even with both inputs present, only ONE name reaches env."""
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-1\n")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "benchmark-token").write_text("oauth-2")

    resolution = resolve_claude_auth(project_root=tmp_path, home=home)
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in resolution.env
    assert resolution.env == {"ANTHROPIC_API_KEY": "sk-1"}


def test_os_environ_is_not_a_source(tmp_path, monkeypatch):
    """AC-3 verbatim: a process-env value does NOT get picked up unless also in .env."""
    (tmp_path / ".env").write_text("# empty\n")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-os-environ")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-from-os-environ")

    with pytest.raises(Exception):
        resolve_claude_auth(project_root=tmp_path, home=home)


def test_raises_when_neither_source_has_credentials(tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    with pytest.raises(Exception):
        resolve_claude_auth(project_root=tmp_path, home=home)


def test_anthropic_api_key_in_dotenv_with_empty_value_is_treated_as_missing(tmp_path):
    """dotenv_values returns '' for KEY= with no value; treat as missing."""
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=\n")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "benchmark-token").write_text("oauth")

    resolution = resolve_claude_auth(project_root=tmp_path, home=home)
    assert resolution.mode == "oauth"


def test_codex_openai_api_key_from_dotenv(tmp_path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-openai\n")
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    (home / ".codex" / "auth.json").write_text('{"tokens": "ignored"}\n')

    resolution = resolve_codex_auth(project_root=tmp_path, home=home)

    assert resolution == AuthResolution(
        mode="api-key",
        env={"OPENAI_API_KEY": "sk-openai"},
    )


def test_codex_auth_carries_openai_base_url_when_present(tmp_path):
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=sk-openai\nOPENAI_BASE_URL=https://proxy.example/v1\n"
    )

    resolution = resolve_codex_auth(project_root=tmp_path, home=tmp_path / "home")

    assert resolution.env == {
        "OPENAI_API_KEY": "sk-openai",
        "OPENAI_BASE_URL": "https://proxy.example/v1",
    }


def test_codex_auth_does_not_read_os_environ(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("# empty\n")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-os-environ")

    with pytest.raises(Exception):
        resolve_codex_auth(project_root=tmp_path, home=tmp_path / "home")


def test_codex_auth_uses_explicit_auth_json_path_from_dotenv(tmp_path):
    auth_path = tmp_path / "codex-auth.json"
    auth_path.write_text('{"tokens": "fake"}\n')
    (tmp_path / ".env").write_text(f"CODEX_AUTH_JSON_PATH={auth_path}\n")

    resolution = resolve_codex_auth(project_root=tmp_path, home=tmp_path / "home")

    assert resolution == AuthResolution(
        mode="auth-json",
        env={"CODEX_AUTH_JSON_PATH": str(auth_path)},
    )


def test_codex_auth_falls_back_to_default_home_auth_json(tmp_path):
    home = tmp_path / "home"
    auth_path = home / ".codex" / "auth.json"
    auth_path.parent.mkdir(parents=True)
    auth_path.write_text('{"tokens": "fake"}\n')
    (tmp_path / ".env").write_text("# no codex api key or explicit auth path\n")

    resolution = resolve_codex_auth(project_root=tmp_path, home=home)

    assert resolution == AuthResolution(
        mode="auth-json",
        env={"CODEX_AUTH_JSON_PATH": str(auth_path)},
    )


def test_codex_auth_missing_credentials_message_names_supported_options(tmp_path):
    with pytest.raises(AuthDiscoveryError) as exc_info:
        resolve_codex_auth(project_root=tmp_path, home=tmp_path / "home")

    message = str(exc_info.value)
    assert "OPENAI_API_KEY" in message
    assert "CODEX_AUTH_JSON_PATH" in message
    assert ".codex/auth.json" in message
