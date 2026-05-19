# ABOUTME: AC-1, AC-2 — rk spec freeze CLI surface.

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from razorback.cli import app


runner = CliRunner()


SPEC_TEXT = """\
version: 1
experiment: m5-test
agent:
  kind: claude-cli
  model: claude-opus-4-5
benchmark:
  kind: dab
  data_root: /tmp/data
  datasets: [bookreview]
trials: 1
"""


@pytest.fixture
def spec_file(tmp_path: Path) -> Path:
    p = tmp_path / "spec.yaml"
    p.write_text(SPEC_TEXT)
    return p


def _stub_all_resolved(monkeypatch):
    """Stub all six resolvers to succeed."""
    import razorback.provenance.freeze_cmd as fc

    monkeypatch.setattr(
        fc,
        "resolve_model_version",
        lambda alias, **_: ("claude-opus-4-5-20251022", "2025-10-22T00:00:00Z"),
    )
    monkeypatch.setattr(fc, "resolve_image_digest", lambda _ref, **_: "sha256:abc")
    monkeypatch.setattr(fc, "resolve_agent_cli_hash", lambda _bin, **_: "sha256:def")
    monkeypatch.setattr(
        fc, "resolve_harness_git_sha", lambda _root, **_: "0123456789abcdef"
    )
    monkeypatch.setattr(fc, "resolve_harbor_version", lambda: "0.6.6")
    monkeypatch.setattr(fc, "resolve_prompt_hashes", lambda _paths: {})


def test_freeze_all_resolved_writes_frozen_and_provenance(spec_file, monkeypatch):
    _stub_all_resolved(monkeypatch)
    result = runner.invoke(app, ["spec", "freeze", str(spec_file)])
    assert result.exit_code == 0, result.output
    frozen = spec_file.with_suffix(".frozen.yaml")
    prov = spec_file.parent / "provenance.yaml"
    assert frozen.exists()
    assert prov.exists()
    prov_doc = yaml.safe_load(prov.read_text())
    assert prov_doc["model_resolved_version"] == "claude-opus-4-5-20251022"
    assert prov_doc["harbor_version"] == "0.6.6"
    assert "unresolved" not in prov_doc


def test_freeze_refuses_when_field_missing(spec_file, monkeypatch):
    """AC-1: any one unresolved field → exit 11, neither output written."""
    import razorback.provenance.freeze_cmd as fc

    monkeypatch.setattr(
        fc,
        "resolve_model_version",
        lambda alias, **_: ("claude-opus-4-5-20251022", "2025-10-22T00:00:00Z"),
    )
    monkeypatch.setattr(fc, "resolve_image_digest", lambda _ref, **_: None)
    monkeypatch.setattr(fc, "resolve_agent_cli_hash", lambda _bin, **_: "sha256:def")
    monkeypatch.setattr(
        fc, "resolve_harness_git_sha", lambda _root, **_: "0123456789abcdef"
    )
    monkeypatch.setattr(fc, "resolve_harbor_version", lambda: "0.6.6")
    monkeypatch.setattr(fc, "resolve_prompt_hashes", lambda _paths: {})

    result = runner.invoke(app, ["spec", "freeze", str(spec_file)])
    assert result.exit_code == 11
    assert "image_digest" in result.output
    assert not spec_file.with_suffix(".frozen.yaml").exists()
    assert not (spec_file.parent / "provenance.yaml").exists()


def test_freeze_allow_missing_writes_with_unresolved_marker(spec_file, monkeypatch):
    """AC-2: --allow-missing writes both files, provenance.yaml records the unresolved field."""
    import razorback.provenance.freeze_cmd as fc

    monkeypatch.setattr(fc, "resolve_model_version", lambda alias, **_: (None, None))
    monkeypatch.setattr(fc, "resolve_image_digest", lambda _ref, **_: "sha256:abc")
    monkeypatch.setattr(fc, "resolve_agent_cli_hash", lambda _bin, **_: "sha256:def")
    monkeypatch.setattr(
        fc, "resolve_harness_git_sha", lambda _root, **_: "0123456789abcdef"
    )
    monkeypatch.setattr(fc, "resolve_harbor_version", lambda: "0.6.6")
    monkeypatch.setattr(fc, "resolve_prompt_hashes", lambda _paths: {})

    result = runner.invoke(app, ["spec", "freeze", str(spec_file), "--allow-missing"])
    assert result.exit_code == 0, result.output
    prov = yaml.safe_load((spec_file.parent / "provenance.yaml").read_text())
    assert "model_resolved_version" in prov["unresolved"]
