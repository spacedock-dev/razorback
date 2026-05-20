# ABOUTME: AC-2 — CLI exposes exactly three commands: generate, list, validate.
# ABOUTME: list prints a 12-entry JSON catalog; hello-fixture generate produces a harbor task tree.

import json
import subprocess
from pathlib import Path


def _uv_run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    cmd = ["uv", "run", "razorback-plugin-dab"] + args
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def test_help_lists_three_commands():
    result = _uv_run(["--help"])
    assert result.returncode == 0
    text = result.stdout
    assert "generate" in text
    assert "list" in text
    assert "validate" in text


def test_list_returns_12_entries():
    result = _uv_run(["list"])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert len(payload) == 12
    names = {entry["name"] for entry in payload}
    assert "bookreview" in names
    assert "yelp" in names


def test_generate_hello_fixture_emits_harbor_shape(tmp_path: Path):
    out = tmp_path / "out"
    result = _uv_run(["generate", "--datasets", "hello-fixture", "--out", str(out)])
    assert result.returncode == 0, result.stderr
    task_dir = out / "hello-fixture"
    assert (task_dir / "task.toml").exists()
    assert (task_dir / "instruction.md").exists()
    assert (task_dir / "tests" / "test.sh").exists()
    assert (task_dir / "environment" / "Dockerfile").exists()


def test_generate_unknown_dataset_exits_2(tmp_path: Path):
    out = tmp_path / "out"
    result = _uv_run(["generate", "--datasets", "bogus", "--data-root", str(tmp_path), "--out", str(out)])
    assert result.returncode == 2
    assert "unknown dataset" in result.stderr


def test_validate_passes_on_hello_fixture(tmp_path: Path):
    out = tmp_path / "out"
    _uv_run(["generate", "--datasets", "hello-fixture", "--out", str(out)])
    result = _uv_run(["validate", str(out)])
    assert result.returncode == 0
    assert "1 tasks validated" in result.stdout


def _build_bookreview_data_root(root: Path) -> Path:
    import yaml as _yaml

    data_root = root / "data"
    qdir = data_root / "query_bookreview"
    (qdir / "query_dataset").mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(_yaml.safe_dump({
        "db_clients": {
            "books_database": {
                "db_type": "postgres",
                "db_name": "bookreview_db",
                "sql_file": "query_dataset/books_info.sql",
            }
        }
    }))
    (qdir / "db_description.txt").write_text("Bookreview schema.")
    (qdir / "query_dataset" / "books_info.sql").write_text("CREATE TABLE books (id INT);\n")
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "How many books?"}')
    return data_root


def test_cli_materialize_bind_skips_workdir_dump(tmp_path: Path):
    data_root = _build_bookreview_data_root(tmp_path)
    out = tmp_path / "tasks"
    result = _uv_run([
        "generate", "--datasets", "bookreview",
        "--data-root", str(data_root), "--out", str(out),
        "--materialize", "bind",
    ])
    assert result.returncode == 0, result.stderr
    task_dirs = [p for p in out.iterdir() if p.is_dir()]
    assert task_dirs
    workdir = task_dirs[0] / "steps" / "main" / "workdir"
    assert not (workdir / "query_dataset" / "books_info.sql").exists()


def test_cli_materialize_copy_keeps_workdir_dump(tmp_path: Path):
    data_root = _build_bookreview_data_root(tmp_path)
    out = tmp_path / "tasks"
    result = _uv_run([
        "generate", "--datasets", "bookreview",
        "--data-root", str(data_root), "--out", str(out),
        "--materialize", "copy",
    ])
    assert result.returncode == 0, result.stderr
    task_dirs = [p for p in out.iterdir() if p.is_dir()]
    assert task_dirs
    workdir = task_dirs[0] / "steps" / "main" / "workdir"
    assert (workdir / "query_dataset" / "books_info.sql").exists()


def test_cli_materialize_default_is_bind(tmp_path: Path):
    data_root = _build_bookreview_data_root(tmp_path)
    out = tmp_path / "tasks"
    result = _uv_run([
        "generate", "--datasets", "bookreview",
        "--data-root", str(data_root), "--out", str(out),
    ])
    assert result.returncode == 0, result.stderr
    task_dirs = [p for p in out.iterdir() if p.is_dir()]
    workdir = task_dirs[0] / "steps" / "main" / "workdir"
    assert not (workdir / "query_dataset" / "books_info.sql").exists(), (
        "default materialize mode must be 'bind' (no workdir dump copy)"
    )


def test_cli_materialize_invalid_exits_2(tmp_path: Path):
    out = tmp_path / "tasks"
    result = _uv_run([
        "generate", "--datasets", "bookreview",
        "--data-root", str(tmp_path), "--out", str(out),
        "--materialize", "symlink",
    ])
    assert result.returncode == 2
    assert "materialize" in result.stderr


def test_cli_postgres_volume_mode_invalid_exits_2(tmp_path: Path):
    out = tmp_path / "tasks"
    result = _uv_run([
        "generate", "--datasets", "bookreview",
        "--data-root", str(tmp_path), "--out", str(out),
        "--postgres-volume-mode", "bogus",
    ])
    assert result.returncode == 2
    assert "postgres-volume-mode" in result.stderr


def test_cli_postgres_volume_mode_fresh_yields_per_task_volume(tmp_path: Path):
    import yaml as _yaml

    data_root = _build_bookreview_data_root(tmp_path)
    out = tmp_path / "tasks"
    result = _uv_run([
        "generate", "--datasets", "bookreview",
        "--data-root", str(data_root), "--out", str(out),
        "--postgres-volume-mode", "fresh",
    ])
    assert result.returncode == 0, result.stderr
    task_dirs = [p for p in out.iterdir() if p.is_dir()]
    compose = _yaml.safe_load(
        (task_dirs[0] / "environment" / "docker-compose.yaml").read_text()
    )
    vol_names = list(compose["volumes"].keys())
    assert len(vol_names) == 1
    assert vol_names[0].startswith("dab-postgres-data-bookreview-v1-bookreview-")
