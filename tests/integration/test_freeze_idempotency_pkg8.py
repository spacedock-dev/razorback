# ABOUTME: AC-5 — rk freeze run twice on the same source spec produces byte-identical
# ABOUTME: provenance.yaml and spec.frozen.yaml outputs (spec §3.1 idempotency rule).

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from razorback.provenance.freeze_cmd import freeze_command


# `rk spec freeze` is not yet wired into the v2 Typer surface (the legacy
# subcommand lives under _legacy/). For AC-5 we exercise the freeze_command
# function directly through a minimal Typer app so the byte-identity assertions
# still cover the real CLI body without depending on top-level command wiring.
_freeze_app = typer.Typer()
_freeze_app.command("freeze")(freeze_command)
runner = CliRunner()


SPEC_TEXT = """\
version: 1
experiment: pkg8-v2-idempotency
agent:
  kind: claude-cli
  model: claude-opus-4-5
benchmark:
  kind: dab
  data_root: /tmp/data
  datasets: [bookreview]
trials: 1
"""


STABLE_PLUGINS = {
    "plugins": [
        {
            "group": "harbor.agents",
            "name": "claude_code",
            "distribution": "harbor",
            "version": "0.6.6",
        },
        {
            "group": "harbor.benchmarks",
            "name": "dab",
            "distribution": "razorback-plugin-dab",
            "version": "0.1.0",
        },
    ]
}


def _stub_all(monkeypatch, sw_hash: str | None = None) -> None:
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
    monkeypatch.setattr(fc, "resolve_plugin_inventory", lambda: STABLE_PLUGINS)
    monkeypatch.setattr(fc, "resolve_solver_workflow_hash", lambda _p: sw_hash)


@pytest.fixture
def make_spec_dir(tmp_path: Path):
    counter = {"n": 0}

    def _make() -> Path:
        counter["n"] += 1
        d = tmp_path / f"spec{counter['n']}"
        d.mkdir()
        sp = d / "spec.yaml"
        sp.write_text(SPEC_TEXT)
        return sp

    return _make


def test_freeze_twice_byte_identical_provenance_yaml(make_spec_dir, monkeypatch) -> None:
    _stub_all(monkeypatch)
    a = make_spec_dir()
    b = make_spec_dir()
    r1 = runner.invoke(_freeze_app, [str(a)])
    r2 = runner.invoke(_freeze_app, [str(b)])
    assert r1.exit_code == 0, r1.output
    assert r2.exit_code == 0, r2.output
    bytes_a = (a.parent / "provenance.yaml").read_bytes()
    bytes_b = (b.parent / "provenance.yaml").read_bytes()
    assert bytes_a == bytes_b


def test_freeze_twice_byte_identical_spec_frozen_yaml(make_spec_dir, monkeypatch) -> None:
    _stub_all(monkeypatch)
    a = make_spec_dir()
    b = make_spec_dir()
    r1 = runner.invoke(_freeze_app, [str(a)])
    r2 = runner.invoke(_freeze_app, [str(b)])
    assert r1.exit_code == 0, r1.output
    assert r2.exit_code == 0, r2.output
    bytes_a = a.with_suffix(".frozen.yaml").read_bytes()
    bytes_b = b.with_suffix(".frozen.yaml").read_bytes()
    assert bytes_a == bytes_b


def test_solver_workflow_change_breaks_idempotency(make_spec_dir, monkeypatch) -> None:
    """Sanity: if the solver_workflow hash differs, outputs differ (proves the
    two prior idempotency tests are real, not always-equal constants)."""
    import razorback.provenance.freeze_cmd as fc

    _stub_all(monkeypatch, sw_hash="sha256:aaaa")
    monkeypatch.setattr(
        fc, "_solver_workflow_path", lambda _spec: Path("/tmp/fake")
    )
    a = make_spec_dir()
    r1 = runner.invoke(_freeze_app, [str(a)])
    assert r1.exit_code == 0, r1.output

    _stub_all(monkeypatch, sw_hash="sha256:bbbb")
    monkeypatch.setattr(
        fc, "_solver_workflow_path", lambda _spec: Path("/tmp/fake")
    )
    b = make_spec_dir()
    r2 = runner.invoke(_freeze_app, [str(b)])
    assert r2.exit_code == 0, r2.output

    bytes_a = (a.parent / "provenance.yaml").read_bytes()
    bytes_b = (b.parent / "provenance.yaml").read_bytes()
    assert bytes_a != bytes_b


def test_freeze_twice_byte_identical_with_solver_workflow(
    make_spec_dir, monkeypatch
) -> None:
    """AC-5 + AC-2 together: spec with a solver_workflow -> idempotent across two freezes."""
    import razorback.provenance.freeze_cmd as fc

    _stub_all(monkeypatch, sw_hash="sha256:deadbeef")
    monkeypatch.setattr(
        fc, "_solver_workflow_path", lambda _spec: Path("/tmp/fake")
    )

    a = make_spec_dir()
    b = make_spec_dir()
    r1 = runner.invoke(_freeze_app, [str(a)])
    r2 = runner.invoke(_freeze_app, [str(b)])
    assert r1.exit_code == 0, r1.output
    assert r2.exit_code == 0, r2.output
    assert (a.parent / "provenance.yaml").read_bytes() == (
        b.parent / "provenance.yaml"
    ).read_bytes()
