# ABOUTME: Phase 2 AC-1, AC-2 — harbor_dab translator dispatches to the sibling plugin.
# ABOUTME: Mocks subprocess so the test does not invoke razorback-plugin-dab.

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from razorback.compat import spec_to_job_config
from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text


def _spec_text(data_root: Path, datasets: str = "[bookreview]") -> str:
    return (
        "version: 1\n"
        "experiment: phase2-translator-test\n"
        "agent:\n"
        "  kind: nop\n"
        "benchmark:\n"
        "  kind: harbor_dab\n"
        f"  data_root: {data_root}\n"
        f"  datasets: {datasets}\n"
        "  workspace_variant: direct-minimal\n"
        "trials: 1\n"
    )


class _FakeCompleted:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


def _seed_emitted_tasks(out_root: Path, dataset: str, queries: list[int]) -> None:
    target = out_root / dataset
    target.mkdir(parents=True, exist_ok=True)
    for qid in queries:
        (target / f"{dataset}-q{qid}").mkdir()


def test_harbor_dab_translator_invokes_plugin_and_builds_tasks(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    tasks_root = tmp_path / "tasks"
    spec = parse_spec_text(_spec_text(data_root))

    def fake_run(cmd, capture_output, text):
        # Verify it invoked the plugin with the expected args.
        assert cmd[:4] == ["uv", "run", "razorback-plugin-dab", "generate"]
        assert "--datasets" in cmd
        ds = cmd[cmd.index("--datasets") + 1]
        out = Path(cmd[cmd.index("--out") + 1])
        _seed_emitted_tasks(out.parent, ds, [1, 2, 3])
        return _FakeCompleted(returncode=0)

    with patch.object(subprocess, "run", side_effect=fake_run):
        cfg, trial_name_map = spec_to_job_config(
            spec,
            job_name="job-test",
            jobs_dir=tmp_path / "jobs",
            tasks_root=tasks_root,
        )

    task_paths = sorted(t.path.name for t in cfg.tasks)
    assert task_paths == ["bookreview-q1", "bookreview-q2", "bookreview-q3"]
    assert trial_name_map == {
        "bookreview-q1": ("bookreview", 1),
        "bookreview-q2": ("bookreview", 2),
        "bookreview-q3": ("bookreview", 3),
    }
    assert cfg.n_attempts == 1


def test_harbor_dab_translator_propagates_plugin_failure(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    spec = parse_spec_text(_spec_text(data_root))

    def fake_run(cmd, capture_output, text):
        return _FakeCompleted(
            returncode=2,
            stderr="razorback-plugin-dab: dataset bookreview not hydrated, found LFS pointer.",
        )

    with patch.object(subprocess, "run", side_effect=fake_run):
        with pytest.raises(SpecError) as exc_info:
            spec_to_job_config(
                spec,
                job_name="job-test",
                jobs_dir=tmp_path / "jobs",
                tasks_root=tmp_path / "tasks",
            )
    assert "exit 2" in str(exc_info.value)
    assert "not hydrated" in str(exc_info.value)


def test_harbor_dab_requires_tasks_root(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    spec = parse_spec_text(_spec_text(data_root))
    with pytest.raises(SpecError) as exc_info:
        spec_to_job_config(spec, job_name="job-test", jobs_dir=tmp_path / "jobs")
    assert "harbor_dab" in str(exc_info.value)
    assert "tasks_root" in str(exc_info.value)


def test_in_tree_dab_translator_path_unchanged(tmp_path: Path):
    """AC-7 regression: legacy `kind: dab` (and v2 alias `in_tree_dab`) still
    dispatches to _build_dab, not the new harbor branch."""
    from razorback.spec.schema import DabBenchmarkBlock
    spec = parse_spec_text(
        "version: 1\n"
        "experiment: phase2-translator-test\n"
        "agent:\n"
        "  kind: nop\n"
        "benchmark:\n"
        "  kind: in_tree_dab\n"
        f"  data_root: /Users/clkao/git/dataagentbench/data\n"
        "  datasets: [bookreview]\n"
        "trials: 1\n"
    )
    assert isinstance(spec.benchmark, DabBenchmarkBlock)
