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
    # PKG-13 T1: compose lives under environment/, not at task-dir root, so
    # harbor's compose discovery (environment_dir / docker-compose.yaml) loads it.
    assert (task_dir / "environment" / "docker-compose.yaml").exists()
    assert not (task_dir / "docker-compose.yaml").exists()
    assert (task_dir / "instruction.md").exists()
    assert (task_dir / "environment" / "Dockerfile").exists()
    assert (task_dir / "environment" / "settings.json").exists()
    assert (task_dir / "tests" / "verify.py").exists()
    assert (task_dir / "tests" / "validate.py").exists()
    assert (task_dir / "tests" / "test.sh").exists()
    assert (task_dir / "tests" / "stratum.json").exists()
    assert (task_dir / "steps" / "main" / "workdir" / "README.md").exists()


def test_compose_bind_mount_sources_resolve_to_real_files(tmp_path: Path):
    """PKG-13 T1 / AC-4 + PKG-14 AC-1: bind-mount sources in the generated
    compose must point at existing files. Under PKG-14 bind mode (the default)
    the source is the absolute data_root path. NAMED volumes (postgres data
    volume) are skipped — docker creates them on demand.
    """
    data_root = _build_synthetic_data_root(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=out
    )
    compose_path = manifest[0]["task_dir"] / "environment" / "docker-compose.yaml"
    compose = yaml.safe_load(compose_path.read_text())
    named_volumes = set((compose.get("volumes") or {}).keys())
    pg_volumes = compose["services"]["dab-postgres"]["volumes"]
    init_volumes = [v for v in pg_volumes if v.split(":", 1)[0] not in named_volumes]
    assert init_volumes, "expected at least one postgres init volume"
    for entry in init_volumes:
        src = entry.split(":", 1)[0]
        assert "_initdb" not in src
        assert "steps/main/workdir" not in src
        resolved = Path(src) if src.startswith("/") else (compose_path.parent / src).resolve()
        assert resolved.exists(), f"bind-mount source missing: {resolved}"


def test_task_toml_schema_and_no_dead_docker_compose_key(tmp_path: Path):
    """PKG-13 T1: harbor's EnvironmentConfig has no docker_compose field, so
    the previously emitted `[environment].docker_compose` line is dead weight
    that pydantic silently drops. The emitted task.toml must not include it.
    Compose discovery happens via the file's physical location under
    environment/, not via a toml reference.
    """
    data_root = _build_synthetic_data_root(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=out
    )
    toml_text = (manifest[0]["task_dir"] / "task.toml").read_text()
    assert 'schema_version = "1.2"' in toml_text
    assert 'docker_compose' not in toml_text
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


def test_task_toml_environment_keys_are_all_honoured_by_harbor(tmp_path: Path):
    """PKG-13 T2: any [environment].* key emitted by the plugin must map to
    a real harbor EnvironmentConfig field. Future un-honoured keys (like
    the dropped `docker_compose`) should land at generation time, not as a
    silent runtime no-op.
    """
    from harbor.models.task.config import EnvironmentConfig

    data_root = _build_synthetic_data_root(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=out
    )
    import tomllib

    parsed = tomllib.loads((manifest[0]["task_dir"] / "task.toml").read_text())
    extras = set(parsed.get("environment", {})) - set(EnvironmentConfig.model_fields)
    assert not extras, f"task.toml has unknown [environment] keys: {extras}"


def test_unknown_dataset_rejected(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    with pytest.raises(FileNotFoundError):
        prepare_dataset_tasks(
            data_root=data_root, dataset="bookreview", tasks_root=tmp_path / "tasks"
        )
