# ABOUTME: AC-8 — rk score JSON output schema is semver-stable within major version.
# ABOUTME: Snapshot pins the key set; additions allowed, renames/removals fail.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from razorback.cli import app

FIXTURE_ROOT = Path(__file__).parent.parent / "fixtures" / "score"
SNAPSHOT = FIXTURE_ROOT / "snapshots" / "score_report_v1.json"
MIXED = FIXTURE_ROOT / "mixed_trial_run_dir"


def _recursive_keys(obj: Any, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            keys.add(path)
            keys.update(_recursive_keys(v, path))
    return keys


def test_score_report_v1_snapshot_key_set_preserved() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["score", str(MIXED), "--alpha", "0.05"])
    assert result.exit_code == 0, result.output
    actual = json.loads(result.output)
    expected = json.loads(SNAPSHOT.read_text())

    # The snapshot pins per-stratum keys against `strata.<dataset>.*`. To check
    # adapter-agnostically, compare the abstract path set (replace stratum
    # label with `*`).
    def abstract(keys: set[str]) -> set[str]:
        return {_replace_stratum_label(k) for k in keys}

    expected_keys = abstract(_recursive_keys(expected))
    actual_keys = abstract(_recursive_keys(actual))
    missing = expected_keys - actual_keys
    assert not missing, f"snapshot keys missing from output: {sorted(missing)}"


def test_score_version_pinned_to_one() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["score", str(MIXED), "--alpha", "0.05"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["score_version"] == 1


def _replace_stratum_label(path: str) -> str:
    parts = path.split(".")
    if len(parts) >= 2 and parts[0] == "strata":
        parts[1] = "*"
    return ".".join(parts)
