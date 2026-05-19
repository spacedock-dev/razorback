# ABOUTME: Unit tests for the DAB prepare module (§6.5).
# ABOUTME: AC-2 — ground_truth.csv must NOT appear in the materialized task workdir.

from pathlib import Path

import pytest

from razorback.benchmarks.dab.prepare import prepare_dataset_tasks


def _make_fixture_dataset(root: Path) -> Path:
    """Build a minimal query_bookreview-shaped fixture under root."""
    ds = root / "query_bookreview"
    (ds / "query_dataset").mkdir(parents=True)
    (ds / "query_dataset" / "review_query.db").write_bytes(b"sqlite-stub")
    (ds / "db_config.yaml").write_text("db_clients: {}\n")
    (ds / "db_description.txt").write_text("two-databases description")
    for qid in (1, 2):
        q = ds / f"query{qid}"
        q.mkdir()
        (q / "query.json").write_text(f'"question {qid}?"')
        (q / "validate.py").write_text("def validate(s): return True, 'ok'\n")
        (q / "ground_truth.csv").write_text(f"answer-{qid}\n")
    return ds


def test_prepare_excludes_ground_truth_csv(tmp_path):
    data_root = tmp_path / "data"
    _make_fixture_dataset(data_root)
    tasks_root = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tasks_root,
    )
    assert len(manifest) == 2
    for entry in manifest:
        task_dir = entry["task_dir"]
        # AC-2: no ground_truth.csv anywhere in the task tree.
        assert not list(task_dir.rglob("ground_truth.csv"))


def test_prepare_excludes_validate_py_from_workdir(tmp_path):
    """validate.py is invisible to the agent (it lives only under /tests/)."""
    data_root = tmp_path / "data"
    _make_fixture_dataset(data_root)
    tasks_root = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tasks_root,
    )
    for entry in manifest:
        workdir = entry["task_dir"] / "workdir"
        assert not list(workdir.rglob("validate.py")), f"validate.py leaked into {workdir}"


def test_prepare_copies_safe_inputs(tmp_path):
    data_root = tmp_path / "data"
    _make_fixture_dataset(data_root)
    tasks_root = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tasks_root,
    )
    q1 = next(e for e in manifest if e["query_id"] == 1)["task_dir"]
    assert (q1 / "workdir" / "query.json").read_text() == '"question 1?"'
    assert (q1 / "workdir" / "db_config.yaml").exists()
    assert (q1 / "workdir" / "db_description.txt").exists()
    assert (q1 / "workdir" / "query_dataset" / "review_query.db").exists()


def test_prepare_writes_task_toml_and_dockerfile(tmp_path):
    data_root = tmp_path / "data"
    _make_fixture_dataset(data_root)
    tasks_root = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tasks_root,
    )
    q1 = next(e for e in manifest if e["query_id"] == 1)["task_dir"]
    task_toml = (q1 / "task.toml").read_text()
    assert 'razorback/bookreview-q1' in task_toml
    assert (q1 / "environment" / "Dockerfile").exists()
    assert (q1 / "tests" / "test.sh").exists()
    # Executable bit on test.sh.
    assert (q1 / "tests" / "test.sh").stat().st_mode & 0o111
    # validate.py and verify.py live in /tests/ (not /work/).
    assert (q1 / "tests" / "validate.py").exists()
    assert (q1 / "tests" / "verify.py").exists()


def test_prepare_returns_manifest_with_task_name(tmp_path):
    data_root = tmp_path / "data"
    _make_fixture_dataset(data_root)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
    )
    names = sorted(e["task_name"] for e in manifest)
    assert names == ["bookreview-q1", "bookreview-q2"]


def test_prepare_rejects_missing_dataset(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    with pytest.raises(FileNotFoundError):
        prepare_dataset_tasks(
            data_root=data_root,
            dataset="bookreview",
            tasks_root=tmp_path / "tasks",
        )
