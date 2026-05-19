# ABOUTME: AC-3, AC-4 — drift checks fire BEFORE Job.create in rk run.

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from razorback.provenance.errors import AliasDriftError, HarborDriftError


FROZEN_TEXT = """\
version: 1
experiment: m5-run-drift
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


def test_run_refuses_on_harbor_drift(tmp_path):
    from razorback.run import execute_run
    from razorback.spec.parse import parse_spec_file

    pinned = {
        "harbor_version": "0.6.6",
        "model_resolved_version": "claude-opus-4-5-20251022",
    }
    frozen_path = _write_frozen(tmp_path, with_pinned=pinned)
    spec = parse_spec_file(frozen_path)

    with patch(
        "razorback.run.check_harbor_drift",
        side_effect=HarborDriftError(frozen="0.6.6", installed="1.0.0"),
    ):
        with pytest.raises(HarborDriftError):
            execute_run(spec=spec, runs_dir=tmp_path / "_runs")


def test_run_refuses_on_alias_drift_by_default(tmp_path):
    from razorback.run import execute_run
    from razorback.spec.parse import parse_spec_file

    pinned = {
        "harbor_version": "0.6.6",
        "model_resolved_version": "claude-opus-4-5-20251022",
    }
    frozen_path = _write_frozen(tmp_path, with_pinned=pinned)
    spec = parse_spec_file(frozen_path)

    with patch("razorback.run.check_harbor_drift", return_value=None):
        with patch(
            "razorback.run.check_alias_drift",
            side_effect=AliasDriftError(
                model_alias="claude-opus-4-5",
                frozen="claude-opus-4-5-20251022",
                resolved="claude-opus-4-5-20260101",
            ),
        ):
            with pytest.raises(AliasDriftError):
                execute_run(
                    spec=spec,
                    runs_dir=tmp_path / "_runs",
                    allow_alias_drift=False,
                )
