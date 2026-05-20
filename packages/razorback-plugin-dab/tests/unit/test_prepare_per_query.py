# ABOUTME: AC-3 — task-dir shape for one (dataset, query) emission.
# ABOUTME: Asserts forbidden files (ground_truth.csv, validate.py) never reach workdir.

from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


def _build_synthetic_data_root(root: Path) -> Path:
    """Build a minimal bookreview-shaped data root with one query."""
    data_root = root / "data"
    qdir = data_root / "query_bookreview"
    qdir.mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump({
        "db_clients": {
            "books_database": {
                "db_type": "postgres",
                "db_name": "bookreview_db",
                "sql_file": "query_dataset/books_info.sql",
            },
            "review_database": {
                "db_type": "sqlite",
                "db_path": "query_dataset/review_query.db",
            },
        }
    }))
    (qdir / "db_description.txt").write_text("Bookreview schema description.")
    qd = qdir / "query_dataset"
    qd.mkdir()
    (qd / "books_info.sql").write_text("-- real sql dump\nCREATE TABLE books (id INT);\n" * 50)
    (qd / "review_query.db").write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "How many books are there?"}')
    (q1 / "validate.py").write_text(
        "def validate(answer):\n    return (answer == '5', 'ok' if answer == '5' else 'no')\n"
    )
    (q1 / "ground_truth.csv").write_text("answer\n5\n")
    return data_root


def test_task_dir_layout(tmp_path: Path):
    data_root = _build_synthetic_data_root(tmp_path)
    out = tmp_path / "tasks"

    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=out,
        workspace_variant="direct-minimal",
    )
    assert len(manifest) == 1
    entry = manifest[0]
    assert entry["dataset"] == "bookreview"
    assert entry["query_id"] == 1
    assert entry["task_name"] == "bookreview-q1"

    task_dir = entry["task_dir"]
    assert (task_dir / "task.toml").exists()
    assert (task_dir / "docker-compose.yaml").exists()
    assert (task_dir / "instruction.md").exists()
    assert (task_dir / "environment" / "Dockerfile").exists()
    assert (task_dir / "environment" / "settings.json").exists()
    assert (task_dir / "tests" / "verify.py").exists()
    assert (task_dir / "tests" / "validate.py").exists()
    assert (task_dir / "tests" / "test.sh").exists()
    assert (task_dir / "tests" / "stratum.json").exists()
    assert (task_dir / "steps" / "main" / "workdir" / "README.md").exists()


def test_task_toml_schema_and_compose_ref(tmp_path: Path):
    data_root = _build_synthetic_data_root(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=out
    )
    toml_text = (manifest[0]["task_dir"] / "task.toml").read_text()
    assert 'schema_version = "1.2"' in toml_text
    assert 'docker_compose = "docker-compose.yaml"' in toml_text
    assert 'name = "main"' in toml_text


def test_workdir_excludes_forbidden_files(tmp_path: Path):
    data_root = _build_synthetic_data_root(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=out
    )
    workdir = manifest[0]["task_dir"] / "steps" / "main" / "workdir"

    for forbidden in ("ground_truth.csv", "validate.py", "__pycache__"):
        leftover = list(workdir.rglob(forbidden))
        assert not leftover, f"{forbidden} leaked into workdir: {leftover}"


def test_workdir_carries_safe_files(tmp_path: Path):
    data_root = _build_synthetic_data_root(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=out
    )
    workdir = manifest[0]["task_dir"] / "steps" / "main" / "workdir"
    assert (workdir / "db_config.yaml").exists()
    assert (workdir / "db_description.txt").exists()
    assert (workdir / "query.json").exists()
    assert (workdir / "query_dataset").is_dir()


def test_stratum_payload_in_tests(tmp_path: Path):
    import json
    data_root = _build_synthetic_data_root(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=out
    )
    stratum = json.loads((manifest[0]["task_dir"] / "tests" / "stratum.json").read_text())
    assert stratum["stratum"]["dataset"] == "bookreview"
    assert stratum["stratum"]["query_id"] == 1
    assert stratum["stratum"]["backends"] == ["postgres", "sqlite"]


def test_unknown_dataset_rejected(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    with pytest.raises(FileNotFoundError):
        prepare_dataset_tasks(
            data_root=data_root, dataset="bookreview", tasks_root=tmp_path / "tasks"
        )
