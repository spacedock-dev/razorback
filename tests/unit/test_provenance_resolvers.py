# ABOUTME: Per-field resolver unit tests for the six provenance fields (§6.4).

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from razorback.provenance.resolvers import (
    resolve_agent_cli_hash,
    resolve_harbor_version,
    resolve_harness_git_sha,
    resolve_image_digest,
    resolve_model_version,
    resolve_prompt_hashes,
)


# --- model ---


def test_resolve_model_version_returns_id_and_timestamp():
    client = MagicMock()
    client.models.retrieve.return_value = MagicMock(
        id="claude-opus-4-5-20251022",
        created_at="2025-10-22T00:00:00Z",
    )
    resolved, at = resolve_model_version("claude-opus-4-5", client_factory=lambda: client)
    assert resolved == "claude-opus-4-5-20251022"
    assert at == "2025-10-22T00:00:00Z"


def test_resolve_model_version_retries_503_then_succeeds():
    client = MagicMock()

    class FakeStatusError(Exception):
        def __init__(self, status: int) -> None:
            self.status_code = status

    seq = [
        FakeStatusError(503),
        FakeStatusError(503),
        MagicMock(id="claude-opus-4-5-20251022", created_at="2025-10-22T00:00:00Z"),
    ]

    def _retrieve(_alias):
        item = seq.pop(0)
        if isinstance(item, FakeStatusError):
            raise item
        return item

    client.models.retrieve.side_effect = _retrieve

    sleeps: list[float] = []
    resolved, _at = resolve_model_version(
        "claude-opus-4-5",
        client_factory=lambda: client,
        is_transient=lambda exc: isinstance(exc, FakeStatusError) and exc.status_code == 503,
        sleep=lambda s: sleeps.append(s),
    )
    assert resolved == "claude-opus-4-5-20251022"
    assert len(sleeps) == 2


def test_resolve_model_version_404_is_hard_error():
    client = MagicMock()

    class FakeStatusError(Exception):
        def __init__(self, status: int) -> None:
            self.status_code = status

    client.models.retrieve.side_effect = FakeStatusError(404)
    with pytest.raises(FakeStatusError):
        resolve_model_version(
            "nonexistent-model",
            client_factory=lambda: client,
            is_transient=lambda exc: isinstance(exc, FakeStatusError) and exc.status_code == 503,
            sleep=lambda s: None,
        )


# --- image ---


def test_resolve_image_digest_via_docker_image_inspect():
    docker = MagicMock()
    docker.return_value = "sha256:abc123def\n"
    digest = resolve_image_digest("dab-agent", docker=docker)
    assert digest == "sha256:abc123def"
    docker.assert_called_once_with("dab-agent")


def test_resolve_image_digest_returns_none_when_inspect_fails():
    docker = MagicMock(side_effect=RuntimeError("no such image"))
    digest = resolve_image_digest("missing-image", docker=docker)
    assert digest is None


# --- agent CLI hash ---


def test_resolve_agent_cli_hash_reads_binary_and_hashes(tmp_path):
    binary = tmp_path / "claude"
    binary.write_bytes(b"#!/bin/sh\necho hi\n")
    expected = "sha256:" + hashlib.sha256(b"#!/bin/sh\necho hi\n").hexdigest()
    got = resolve_agent_cli_hash("claude", which=lambda _: str(binary))
    assert got == expected


def test_resolve_agent_cli_hash_returns_none_when_not_on_path():
    got = resolve_agent_cli_hash("nonexistent", which=lambda _: None)
    assert got is None


# --- git SHA ---


def test_resolve_harness_git_sha_returns_full_sha():
    git_runner = MagicMock(return_value="0123456789abcdef0123456789abcdef01234567\n")
    sha = resolve_harness_git_sha(Path("/repo"), git_runner=git_runner)
    assert sha == "0123456789abcdef0123456789abcdef01234567"
    git_runner.assert_called_once_with(Path("/repo"), ("git", "rev-parse", "HEAD"))


def test_resolve_harness_git_sha_returns_none_on_failure():
    git_runner = MagicMock(side_effect=RuntimeError("not a git repo"))
    assert resolve_harness_git_sha(Path("/not-repo"), git_runner=git_runner) is None


# --- harbor version ---


def test_resolve_harbor_version_returns_installed():
    with patch("razorback.provenance.resolvers._import_harbor") as imp:
        imp.return_value = MagicMock(__version__="0.6.6")
        assert resolve_harbor_version() == "0.6.6"


# --- prompt hashes ---


def test_resolve_prompt_hashes_hashes_each_file(tmp_path):
    p1 = tmp_path / "prompt-a.md"
    p2 = tmp_path / "prompt-b.md"
    p1.write_text("hello")
    p2.write_text("world")
    hashes = resolve_prompt_hashes([p1, p2])
    assert hashes[str(p1)] == "sha256:" + hashlib.sha256(b"hello").hexdigest()
    assert hashes[str(p2)] == "sha256:" + hashlib.sha256(b"world").hexdigest()


def test_resolve_prompt_hashes_returns_empty_dict_when_no_paths():
    assert resolve_prompt_hashes([]) == {}


def test_resolve_prompt_hashes_returns_none_when_a_file_is_missing(tmp_path):
    p = tmp_path / "missing.md"
    assert resolve_prompt_hashes([p]) is None
