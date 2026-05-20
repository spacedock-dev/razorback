# ABOUTME: AC-3 + AC-4 — rk run fires check_plugin_drift after check_alias_drift,
# ABOUTME: exits 11 on plugin drift, alias-drift (exit 21) surfaces first when both drift.

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from razorback.cli import app
from razorback.provenance.errors import AliasDriftError


FROZEN_PLUGINS = [
    {
        "group": "harbor.benchmarks",
        "name": "dab",
        "distribution": "razorback-plugin-dab",
        "version": "0.1.0",
    }
]


RESOLVED_DRIFT = {
    "plugins": [
        {
            "group": "harbor.benchmarks",
            "name": "dab",
            "distribution": "razorback-plugin-dab",
            "version": "0.2.0",
        }
    ]
}


FROZEN_TEXT = """\
version: 1
experiment: pkg8-v2-run-drift
agent:
  kind: claude-cli
  model: claude-opus-4-5
benchmark:
  kind: dab
  data_root: /tmp/data
  datasets: [bookreview]
trials: 1
provenance:
  pin_model_version: true
  pin_image_digest: true
  pin_agent_cli_hash: true
  pin_git_sha: true
"""


def _write_frozen(tmp_path: Path, with_pinned: dict | None = None) -> Path:
    p = tmp_path / "spec.frozen.yaml"
    body = yaml.safe_load(FROZEN_TEXT)
    if with_pinned:
        body["provenance"].update(with_pinned)
    p.write_text(yaml.safe_dump(body))
    return p


def test_run_refuses_on_plugin_drift_default(tmp_path: Path) -> None:
    pinned = {
        "harbor_version": "0.6.6",
        "model_resolved_version": "claude-opus-4-5-20251022",
        "plugins": FROZEN_PLUGINS,
    }
    frozen_path = _write_frozen(tmp_path, with_pinned=pinned)

    runner = CliRunner()
    with patch("razorback.cli.run.check_harbor_drift", return_value=None), patch(
        "razorback.cli.run._resolve_model_version",
        return_value=("claude-opus-4-5-20251022", "2025-10-22T00:00:00Z"),
    ), patch("razorback.cli.run._run_canary", return_value=None), patch(
        "razorback.provenance.drift.resolve_plugin_inventory",
        return_value=RESOLVED_DRIFT,
    ):
        result = runner.invoke(
            app, ["run", str(frozen_path), "--runs-dir", str(tmp_path / "_runs")]
        )
    assert result.exit_code == 11, result.output
    assert "dab" in result.output


def test_run_with_allow_plugin_drift_records_in_provenance(tmp_path: Path) -> None:
    """With --allow-plugin-drift, the run proceeds past the drift check and records it."""
    pinned = {
        "harbor_version": "0.6.6",
        "model_resolved_version": "claude-opus-4-5-20251022",
        "plugins": FROZEN_PLUGINS,
    }
    frozen_path = _write_frozen(tmp_path, with_pinned=pinned)

    captured: dict[str, object] = {}

    def _capture(spec_bytes, spec, run_dir, *, plugin_drift_record=None):
        captured["plugin_drift_record"] = plugin_drift_record
        captured["run_dir"] = run_dir

    fake_job_config = type(
        "FakeJobConfig",
        (),
        {
            "agents": [],
            "model_dump_json": lambda self, indent=None: "{}",
        },
    )()

    runner = CliRunner()
    with patch("razorback.cli.run.check_harbor_drift", return_value=None), patch(
        "razorback.cli.run._resolve_model_version",
        return_value=("claude-opus-4-5-20251022", "2025-10-22T00:00:00Z"),
    ), patch("razorback.cli.run._run_canary", return_value=None), patch(
        "razorback.provenance.drift.resolve_plugin_inventory",
        return_value=RESOLVED_DRIFT,
    ), patch(
        "razorback.cli.run.spec_to_job_config", return_value=(fake_job_config, None)
    ), patch("razorback.cli.run._invoke_harbor", return_value=0), patch(
        "razorback.cli.run._write_provenance_artifacts", side_effect=_capture
    ):
        result = runner.invoke(
            app,
            [
                "run",
                str(frozen_path),
                "--runs-dir",
                str(tmp_path / "_runs"),
                "--allow-plugin-drift",
            ],
        )

    assert result.exit_code == 0, result.output
    assert captured["plugin_drift_record"] is not None
    assert captured["plugin_drift_record"]["frozen"] == FROZEN_PLUGINS
    assert captured["plugin_drift_record"]["resolved"] == RESOLVED_DRIFT["plugins"]


def test_run_alias_drift_fires_first_when_both_drift(tmp_path: Path) -> None:
    """AC-4: when alias + plugins both drift, alias-drift (exit 21) surfaces."""
    pinned = {
        "harbor_version": "0.6.6",
        "model_resolved_version": "claude-opus-4-5-20251022",
        "plugins": FROZEN_PLUGINS,
    }
    frozen_path = _write_frozen(tmp_path, with_pinned=pinned)

    runner = CliRunner()
    with patch("razorback.cli.run.check_harbor_drift", return_value=None), patch(
        "razorback.cli.run._resolve_model_version",
        side_effect=AliasDriftError(
            model_alias="claude-opus-4-5",
            frozen="claude-opus-4-5-20251022",
            resolved="claude-opus-4-5-20260101",
        ),
    ), patch("razorback.cli.run._run_canary", return_value=None), patch(
        "razorback.provenance.drift.resolve_plugin_inventory",
        return_value=RESOLVED_DRIFT,
    ):
        result = runner.invoke(
            app, ["run", str(frozen_path), "--runs-dir", str(tmp_path / "_runs")]
        )
    assert result.exit_code == 21, result.output


def test_allow_alias_drift_then_plugin_drift_exits_11(tmp_path: Path) -> None:
    """AC-4: with --allow-alias-drift, alias-drift records but does NOT raise;
    plugin-drift then fires and exits 11 when both inputs drift."""
    pinned = {
        "harbor_version": "0.6.6",
        "model_resolved_version": "claude-opus-4-5-20251022",
        "plugins": FROZEN_PLUGINS,
    }
    frozen_path = _write_frozen(tmp_path, with_pinned=pinned)

    runner = CliRunner()
    with patch("razorback.cli.run.check_harbor_drift", return_value=None), patch(
        "razorback.cli.run._resolve_model_version",
        return_value=("claude-opus-4-5-20260101", "2026-01-01T00:00:00Z"),
    ), patch("razorback.cli.run._run_canary", return_value=None), patch(
        "razorback.provenance.drift.resolve_plugin_inventory",
        return_value=RESOLVED_DRIFT,
    ):
        result = runner.invoke(
            app,
            [
                "run",
                str(frozen_path),
                "--runs-dir",
                str(tmp_path / "_runs"),
                "--allow-alias-drift",
            ],
        )
    assert result.exit_code == 11, result.output


def test_run_no_op_when_frozen_lacks_plugins_field(tmp_path: Path) -> None:
    """Forward-compat: pre-PKG-8 frozen specs (no plugins block) skip the check."""
    pinned = {
        "harbor_version": "0.6.6",
        "model_resolved_version": "claude-opus-4-5-20251022",
    }
    frozen_path = _write_frozen(tmp_path, with_pinned=pinned)

    resolver_called = {"count": 0}

    def _resolver():
        resolver_called["count"] += 1
        return {"plugins": FROZEN_PLUGINS}

    runner = CliRunner()
    # Stop just past the drift checks by making spec_to_job_config raise. That's our
    # proof check_plugin_drift returned None silently for the missing-plugins frozen spec.
    with patch("razorback.cli.run.check_harbor_drift", return_value=None), patch(
        "razorback.cli.run._resolve_model_version",
        return_value=("claude-opus-4-5-20251022", "2025-10-22T00:00:00Z"),
    ), patch("razorback.cli.run._run_canary", return_value=None), patch(
        "razorback.provenance.drift.resolve_plugin_inventory",
        side_effect=_resolver,
    ), patch(
        "razorback.cli.run.spec_to_job_config",
        side_effect=FileNotFoundError("/tmp/data"),
    ):
        result = runner.invoke(
            app, ["run", str(frozen_path), "--runs-dir", str(tmp_path / "_runs")]
        )
    # Frozen had no plugins block -> resolver should not be consulted.
    assert resolver_called["count"] == 0
    # spec_to_job_config raised FileNotFoundError; typer surfaces non-RazorbackError as
    # non-zero exit (and propagates the exception). Exit code is non-11.
    assert result.exit_code != 11
