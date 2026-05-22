from pathlib import Path

import pytest

from razorback.harbor_tasks.leakage import LeakageError, assert_no_denied_paths
from razorback.harbor_tasks.materialize import materialize_harbor_task_view


def _write_source_task(root: Path) -> Path:
    source = root / "source"
    (source / "environment").mkdir(parents=True)
    (source / "tests" / "expected").mkdir(parents=True)
    (source / "solution").mkdir()
    (source / "data").mkdir()
    (source / "task.toml").write_text(
        "\n".join(
            [
                'schema_version = "1.2"',
                "",
                "[task]",
                'name = "fixture/source-task"',
                "",
                "[environment]",
                'docker_image = "source-image:latest"',
                "cpus = 1",
                "",
            ]
        )
    )
    (source / "instruction.md").write_text("Repair the model.\n")
    (source / "environment" / "Dockerfile").write_text("FROM python:3.12\n")
    (source / "tests" / "test.sh").write_text("exit 0\n")
    (source / "tests" / "expected" / "answer.txt").write_text("secret\n")
    (source / "solution" / "solve.sh").write_text("echo secret\n")
    (source / "data" / "input.csv").write_text("id,value\n1,a\n")
    (source / "data" / "answers.csv").write_text("id,answer\n1,secret\n")
    return source


def test_materializer_excludes_solution_and_answer_paths(tmp_path):
    source = _write_source_task(tmp_path)

    view = materialize_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        benchmark_kind="fixture-bench",
        benchmark_task_id="task-001",
        transform_name="fixture-transform",
    )

    assert not (view / "solution" / "solve.sh").exists()
    assert not (view / "data" / "answers.csv").exists()
    assert not (view / "tests" / "expected" / "answer.txt").exists()
    assert_no_denied_paths(view)

    leaked = view / "solution" / "solve.sh"
    leaked.parent.mkdir(exist_ok=True)
    leaked.write_text("echo leaked\n")
    with pytest.raises(LeakageError):
        assert_no_denied_paths(view)
