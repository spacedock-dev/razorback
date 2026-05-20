# ABOUTME: AC-1 + AC-2 — rk spec freeze emits plugins block and solver_workflow_hash.
# ABOUTME: Wires resolve_plugin_inventory + resolve_solver_workflow_hash into freeze_cmd.

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from razorback.cli import app


runner = CliRunner()


SPEC_TEXT = """\
version: 1
experiment: pkg8-v2-test
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


def _stub_existing_resolvers(monkeypatch) -> None:
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


FAKE_PLUGINS = {
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


def test_freeze_writes_plugins_block(spec_file, monkeypatch) -> None:
    """AC-1: provenance.yaml carries a plugins block listing installed plugins."""
    _stub_existing_resolvers(monkeypatch)
    import razorback.provenance.freeze_cmd as fc

    monkeypatch.setattr(fc, "resolve_plugin_inventory", lambda: FAKE_PLUGINS)
    monkeypatch.setattr(fc, "resolve_solver_workflow_hash", lambda _p: None)

    result = runner.invoke(app, ["spec", "freeze", str(spec_file)])
    assert result.exit_code == 0, result.output
    prov = yaml.safe_load((spec_file.parent / "provenance.yaml").read_text())
    assert prov["plugins"] == FAKE_PLUGINS["plugins"]


def test_freeze_writes_plugins_into_spec_frozen_yaml(spec_file, monkeypatch) -> None:
    """spec.frozen.yaml's provenance block also carries the plugins list."""
    _stub_existing_resolvers(monkeypatch)
    import razorback.provenance.freeze_cmd as fc

    monkeypatch.setattr(fc, "resolve_plugin_inventory", lambda: FAKE_PLUGINS)
    monkeypatch.setattr(fc, "resolve_solver_workflow_hash", lambda _p: None)

    result = runner.invoke(app, ["spec", "freeze", str(spec_file)])
    assert result.exit_code == 0, result.output
    frozen = yaml.safe_load(spec_file.with_suffix(".frozen.yaml").read_text())
    assert frozen["provenance"]["plugins"] == FAKE_PLUGINS["plugins"]


def test_freeze_writes_solver_workflow_hash_when_present(
    spec_file, monkeypatch
) -> None:
    """AC-2: when the agent has a solver_workflow path, the hash lands in provenance.yaml."""
    _stub_existing_resolvers(monkeypatch)
    import razorback.provenance.freeze_cmd as fc

    monkeypatch.setattr(fc, "resolve_plugin_inventory", lambda: FAKE_PLUGINS)
    monkeypatch.setattr(
        fc, "resolve_solver_workflow_hash", lambda _p: "sha256:deadbeef"
    )
    # Simulate spec.agent.solver_workflow being present by directly patching the
    # path-extraction helper.
    monkeypatch.setattr(
        fc, "_solver_workflow_path", lambda _spec: Path("/tmp/sw")
    )

    result = runner.invoke(app, ["spec", "freeze", str(spec_file)])
    assert result.exit_code == 0, result.output
    prov = yaml.safe_load((spec_file.parent / "provenance.yaml").read_text())
    assert prov["solver_workflow_hash"] == "sha256:deadbeef"


def test_freeze_omits_solver_workflow_hash_for_non_spacedock_spec(
    spec_file, monkeypatch
) -> None:
    """Non-spacedock specs have no solver_workflow; field stays absent from provenance.yaml."""
    _stub_existing_resolvers(monkeypatch)
    import razorback.provenance.freeze_cmd as fc

    monkeypatch.setattr(fc, "resolve_plugin_inventory", lambda: FAKE_PLUGINS)
    monkeypatch.setattr(fc, "resolve_solver_workflow_hash", lambda _p: None)

    result = runner.invoke(app, ["spec", "freeze", str(spec_file)])
    assert result.exit_code == 0, result.output
    prov = yaml.safe_load((spec_file.parent / "provenance.yaml").read_text())
    assert "solver_workflow_hash" not in prov


def test_freeze_refuses_when_plugins_resolver_returns_none(
    spec_file, monkeypatch
) -> None:
    """plugins is in REQUIRED_FIELDS; a None return refuses with exit 11."""
    _stub_existing_resolvers(monkeypatch)
    import razorback.provenance.freeze_cmd as fc

    monkeypatch.setattr(fc, "resolve_plugin_inventory", lambda: None)
    monkeypatch.setattr(fc, "resolve_solver_workflow_hash", lambda _p: None)

    result = runner.invoke(app, ["spec", "freeze", str(spec_file)])
    assert result.exit_code == 11
    assert "plugins" in result.output
