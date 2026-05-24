# ABOUTME: kind: harbor + plugin: dab translator dispatches via plugin entry-point.
# ABOUTME: Mocks subprocess so unit tests do not invoke razorback-plugin-dab.

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text
from razorback.translate import spec_to_job_config


def _spec_text(data_root: Path, datasets: str = "[bookreview]") -> str:
    return f"""\
version: 1
experiment: dab-dispatch-smoke
agent:
  kind: nop
benchmark:
  kind: harbor
  dataset: dab@1.0
  plugin: dab
  plugin_args:
    data_root: {data_root}
    workspace_variant: direct-minimal
    query_mode: per-query
    hints: false
  tasks: {datasets}
trials: 1
"""


class _FakeCompleted:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr


def _seed_emitted_tasks(out_root: Path, dataset: str, queries: list[int]) -> None:
    """Create harbor-task-shaped directories that look like dab-plugin generate output."""
    for q in queries:
        slug = f"{dataset}-q{q}"
        task_dir = out_root / slug
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.toml").write_text(
            f'schema_version = "1.2"\n[task]\nname = "{dataset}/{slug}"\n'
        )


def test_dab_plugin_dispatch_invokes_subprocess_and_builds_tasks(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    tasks_root = tmp_path / "tasks"

    def fake_run(cmd, capture_output, text):
        # Plugin emits two per-query task dirs.
        _seed_emitted_tasks(tasks_root, "bookreview", [1, 2])
        return _FakeCompleted(returncode=0)

    spec = parse_spec_text(_spec_text(data_root))
    with patch.object(subprocess, "run", side_effect=fake_run) as mock_run:
        job_cfg, trial_name_map = spec_to_job_config(
            spec,
            job_name="dab-dispatch-smoke",
            jobs_dir=tmp_path / "jobs",
            tasks_root=tasks_root,
        )

    assert mock_run.called
    cmd = mock_run.call_args.args[0]
    assert "razorback-plugin-dab" in " ".join(cmd)
    assert "generate" in cmd
    assert len(job_cfg.tasks) == 2
    assert {p.path.name for p in job_cfg.tasks} == {"bookreview-q1", "bookreview-q2"}
    # Fallback derivation: (dataset, int) per slug.
    assert trial_name_map["bookreview-q1"] == ("bookreview", 1)
    assert trial_name_map["bookreview-q2"] == ("bookreview", 2)


def test_dab_plugin_dispatch_reads_trial_name_map_v2_when_emitted(tmp_path: Path):
    """Plugin can emit a `trial_name_map_v2.json` extension carrying the
    canonical map shape — the translator reads it instead of deriving."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    tasks_root = tmp_path / "tasks"

    def fake_run(cmd, capture_output, text):
        _seed_emitted_tasks(tasks_root, "bookreview", [1, 2, 3])
        # Plugin extension emits the canonical map shape post-generate.
        map_path = tasks_root / "trial_name_map_v2.json"
        map_path.write_text(json.dumps({
            "tasks": [
                {"slug": "bookreview-q1", "query_ids": [1]},
                {"slug": "bookreview-q2", "query_ids": [2]},
                {"slug": "bookreview-q3", "query_ids": [3]},
            ],
        }))
        return _FakeCompleted(returncode=0)

    spec = parse_spec_text(_spec_text(data_root))
    with patch.object(subprocess, "run", side_effect=fake_run):
        _, trial_name_map = spec_to_job_config(
            spec,
            job_name="dab-dispatch-smoke",
            jobs_dir=tmp_path / "jobs",
            tasks_root=tasks_root,
        )
    assert trial_name_map["bookreview-q1"] == ("bookreview", 1)
    assert trial_name_map["bookreview-q2"] == ("bookreview", 2)
    assert trial_name_map["bookreview-q3"] == ("bookreview", 3)


def test_dab_plugin_dispatch_propagates_plugin_failure(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()

    def fake_run(cmd, capture_output, text):
        return _FakeCompleted(returncode=2, stderr="plugin sad")

    spec = parse_spec_text(_spec_text(data_root))
    with patch.object(subprocess, "run", side_effect=fake_run), \
         pytest.raises(SpecError) as exc:
        spec_to_job_config(
            spec,
            job_name="dab-dispatch-smoke",
            jobs_dir=tmp_path / "jobs",
            tasks_root=tmp_path / "tasks",
        )
    assert "plugin sad" in str(exc.value)
    assert "razorback-plugin-dab" in str(exc.value)


def test_dab_plugin_dispatch_requires_tasks_root(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    spec = parse_spec_text(_spec_text(data_root))
    with pytest.raises(SpecError) as exc:
        spec_to_job_config(
            spec,
            job_name="dab-dispatch-smoke",
            jobs_dir=tmp_path / "jobs",
            tasks_root=None,
        )
    assert "tasks_root" in str(exc.value)


def test_dab_plugin_dispatch_emits_batch_mode_when_one_task_carries_many_queries(
    tmp_path: Path,
):
    """Batch mode: plugin emits one task per dataset; trial_name_map_v2 carries
    a list of query_ids so the aggregator can fan that single trial out into N
    per-query outcomes."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    tasks_root = tmp_path / "tasks"

    def fake_run(cmd, capture_output, text):
        # Batch: one task per dataset.
        task_dir = tasks_root / "bookreview"
        task_dir.mkdir(parents=True)
        (task_dir / "task.toml").write_text('[task]\nname = "bookreview/bookreview"\n')
        map_path = tasks_root / "trial_name_map_v2.json"
        map_path.write_text(json.dumps({
            "tasks": [
                {"slug": "bookreview", "query_ids": [1, 2, 3]},
            ],
        }))
        return _FakeCompleted(returncode=0)

    spec = parse_spec_text(_spec_text(data_root))
    with patch.object(subprocess, "run", side_effect=fake_run):
        _, trial_name_map = spec_to_job_config(
            spec,
            job_name="dab-dispatch-smoke",
            jobs_dir=tmp_path / "jobs",
            tasks_root=tasks_root,
        )
    assert trial_name_map["bookreview"] == ("bookreview", [1, 2, 3])
