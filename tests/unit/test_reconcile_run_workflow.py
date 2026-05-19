# ABOUTME: AC-1 — reconcile_run_workflow dispatches make-up rk run calls until target trials are met.
# ABOUTME: Mocks subprocess.run so the test does not invoke real harbor.

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from razorback.runtime.reconcile import reconcile_run_workflow


def _write_run_dir(root: Path, *, n_trials: int, kind: str = "ade-bench") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.json").write_text(
        json.dumps(
            {
                "summary_version": 1,
                "benchmark_kind": kind,
                "score": 0.5,
                "n_trials": n_trials,
                "n_correct": 0,
            }
        )
    )
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "experiment": "x",
                "job_name": root.name,
                "benchmark_kind": kind,
            }
        )
    )
    return root


def _write_entity(path: Path, runs: list[Path]) -> Path:
    body = "---\nstatus: reconciling\ntarget_trials: 2\n---\n\n## Runs\n\n"
    for r in runs:
        body += f"- {r}\n"
    path.write_text(body)
    return path


def test_no_dispatch_when_already_at_target(tmp_path):
    run_a = _write_run_dir(tmp_path / "run_a", n_trials=2)
    entity = _write_entity(tmp_path / "entity.md", [run_a])

    with patch("razorback.runtime.reconcile.subprocess.run") as mock_run:
        result = reconcile_run_workflow(
            entity_path=entity,
            target_trials=2,
            spec_path=tmp_path / "spec.yaml",
            runs_dir=tmp_path / "_runs",
            max_iterations=3,
        )
    mock_run.assert_not_called()
    assert result["dispatched"] == 0
    assert result["accumulated_trials"] == 2
    assert result["target_met"] is True


def test_dispatches_one_makeup_when_short_by_one(tmp_path):
    run_a = _write_run_dir(tmp_path / "run_a", n_trials=1)
    entity = _write_entity(tmp_path / "entity.md", [run_a])
    spec = tmp_path / "spec.yaml"
    spec.write_text("version: 1\n")

    def _fake_run(cmd, **kwargs):
        new_dir = tmp_path / "_runs" / "exp" / "newjob"
        _write_run_dir(new_dir, n_trials=1)
        return type("X", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    with patch(
        "razorback.runtime.reconcile.subprocess.run", side_effect=_fake_run
    ) as mock_run:
        result = reconcile_run_workflow(
            entity_path=entity,
            target_trials=2,
            spec_path=spec,
            runs_dir=tmp_path / "_runs",
            max_iterations=3,
        )
    assert mock_run.call_count == 1
    assert result["dispatched"] == 1
    assert result["accumulated_trials"] == 2
    body = entity.read_text()
    assert "run_a" in body
    assert "newjob" in body


def test_stops_at_max_iterations(tmp_path):
    entity = _write_entity(tmp_path / "entity.md", [])
    spec = tmp_path / "spec.yaml"
    spec.write_text("version: 1\n")

    counter = {"i": 0}

    def _fake_run(cmd, **kwargs):
        counter["i"] += 1
        new_dir = tmp_path / "_runs" / "exp" / f"job{counter['i']}"
        _write_run_dir(new_dir, n_trials=0)
        return type("X", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    with patch(
        "razorback.runtime.reconcile.subprocess.run", side_effect=_fake_run
    ) as mock_run:
        result = reconcile_run_workflow(
            entity_path=entity,
            target_trials=5,
            spec_path=spec,
            runs_dir=tmp_path / "_runs",
            max_iterations=3,
        )
    assert mock_run.call_count == 3
    assert result["dispatched"] == 3
    assert result["accumulated_trials"] == 0
    assert result["target_met"] is False


def test_propagates_rk_run_failure(tmp_path):
    entity = _write_entity(tmp_path / "entity.md", [])
    spec = tmp_path / "spec.yaml"
    spec.write_text("version: 1\n")

    def _fake_run(cmd, **kwargs):
        return type(
            "X", (), {"returncode": 30, "stdout": "", "stderr": "harbor failed"}
        )()

    with patch("razorback.runtime.reconcile.subprocess.run", side_effect=_fake_run):
        with pytest.raises(RuntimeError) as exc:
            reconcile_run_workflow(
                entity_path=entity,
                target_trials=1,
                spec_path=spec,
                runs_dir=tmp_path / "_runs",
                max_iterations=3,
            )
        assert "30" in str(exc.value)
