# ABOUTME: AC-5 — baseline promote copies 4 artifacts + verifies; baseline verify re-runs check.

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from razorback.constraints.baseline import promote, verify
from razorback.errors import ConstraintViolation


def _make_run_dir(path: Path, *, agent_model: str = "claude-opus-4-5") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "spec.frozen.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "experiment": "t",
                "agent": {"kind": "claude-cli", "model": agent_model},
                "benchmark": {
                    "kind": "dab",
                    "data_root": "/tmp",
                    "datasets": ["bookreview"],
                },
            }
        )
    )
    (path / "provenance.yaml").write_text(
        "model_resolved_version: claude-opus-4-5-20251022\n"
    )
    (path / "summary.json").write_text(
        json.dumps(
            {
                "summary_version": 1,
                "stratified_pass_at_1": 0.5,
                "datasets": {},
            }
        )
    )


def test_promote_copies_four_artifacts_and_verifies(tmp_path: Path) -> None:
    run = tmp_path / "run-1"
    target = tmp_path / "baselines" / "codex-direct"
    constraints_path = tmp_path / "constraints.yaml"
    constraints_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "pinned": {"agent.model": "claude-opus-4-5"},
                "mutation_surfaces": [],
            }
        )
    )
    _make_run_dir(run)

    promote(run_dir=run, target=target, constraints_path=constraints_path)

    assert (target / "spec.frozen.yaml").exists()
    assert (target / "summary.json").exists()
    assert (target / "provenance.yaml").exists()
    assert (target / "constraints.yaml").exists()
    verify(target)


def test_promote_refuses_on_pinned_mismatch(tmp_path: Path) -> None:
    run = tmp_path / "run-1"
    target = tmp_path / "baselines" / "other"
    constraints_path = tmp_path / "constraints.yaml"
    constraints_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "pinned": {"agent.model": "claude-opus-4-7"},  # mismatch
                "mutation_surfaces": [],
            }
        )
    )
    _make_run_dir(run)
    with pytest.raises(ConstraintViolation):
        promote(run_dir=run, target=target, constraints_path=constraints_path)


def test_promote_refuses_on_missing_artifact(tmp_path: Path) -> None:
    run = tmp_path / "run-1"
    run.mkdir()
    (run / "spec.frozen.yaml").write_text("version: 1\n")
    # no summary.json, no provenance.yaml
    constraints_path = tmp_path / "constraints.yaml"
    constraints_path.write_text(
        "version: 1\npinned: {}\nmutation_surfaces: []\n"
    )
    with pytest.raises(Exception) as exc_info:
        promote(run_dir=run, target=tmp_path / "target", constraints_path=constraints_path)
    assert "missing artifact" in str(exc_info.value)


_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_rk_baseline_promote_verify_cli_roundtrip(tmp_path: Path) -> None:
    run = tmp_path / "run-1"
    target = tmp_path / "baselines" / "codex"
    constraints_path = tmp_path / "constraints.yaml"
    constraints_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "pinned": {"agent.model": "claude-opus-4-5"},
                "mutation_surfaces": [],
            }
        )
    )
    _make_run_dir(run)
    cp = subprocess.run(
        [
            "uv", "run", "rk", "baseline", "promote", str(run),
            "--to", str(target), "--constraints", str(constraints_path),
        ],
        capture_output=True, text=True, cwd=_REPO_ROOT,
    )
    assert cp.returncode == 0, cp.stderr
    cp2 = subprocess.run(
        ["uv", "run", "rk", "baseline", "verify", str(target)],
        capture_output=True, text=True, cwd=_REPO_ROOT,
    )
    assert cp2.returncode == 0, cp2.stderr


def test_promote_uses_m5_summary_snapshot(tmp_path: Path) -> None:
    """Integration: feed the M5 first-DAB-result snapshot through promote.

    The snapshot lives at docs/razorback-implementation/m5-first-dab-result-summary.json
    on main. It's real data — proves the promote path works against the M2/M5 shape.
    """
    snapshot = _REPO_ROOT / "docs" / "razorback-implementation" / "m5-first-dab-result-summary.json"
    assert snapshot.exists(), f"M5 snapshot missing at {snapshot}"
    run = tmp_path / "run-m5"
    run.mkdir()
    shutil.copyfile(snapshot, run / "summary.json")
    (run / "spec.frozen.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "experiment": "m5-first-dab",
                "agent": {"kind": "claude-cli", "model": "claude-opus-4-5"},
                "benchmark": {
                    "kind": "dab",
                    "data_root": "/tmp",
                    "datasets": ["bookreview"],
                },
            }
        )
    )
    (run / "provenance.yaml").write_text(
        "model_resolved_version: claude-opus-4-5-20251022\n"
    )
    constraints_path = tmp_path / "c.yaml"
    constraints_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "pinned": {"agent.model": "claude-opus-4-5"},
                "mutation_surfaces": [],
            }
        )
    )
    target = tmp_path / "baseline-m5"
    promote(run_dir=run, target=target, constraints_path=constraints_path)
    # The promoted summary.json is the real M5 snapshot, unchanged.
    promoted = json.loads((target / "summary.json").read_text())
    assert promoted["summary_version"] == 1
    verify(target)
