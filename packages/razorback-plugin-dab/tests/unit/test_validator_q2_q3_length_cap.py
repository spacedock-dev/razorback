# ABOUTME: PKG-13 T9 — bookreview-q2/q3 length-cap hardening (AC-5).
# ABOUTME: Reject SQL-dump-style answers; preserve canonical short answers.

import importlib.util
from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


_BOOKREVIEW_DB_CONFIG = {
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
}

_TITLES = ["Book One", "Book Two", "Book Three"]

_UPSTREAM_Q2Q3 = """
TITLES = {titles!r}

def validate(answer):
    if not isinstance(answer, str):
        return (False, 'not a string')
    missing = [t for t in TITLES if t not in answer]
    if missing:
        return (False, f'missing book title: {{missing[0]}}')
    return (True, 'ok')
""".format(titles=_TITLES)


def _scaffold(root: Path, query_id: int) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_bookreview"
    qdir.mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump(_BOOKREVIEW_DB_CONFIG))
    (qdir / "db_description.txt").write_text("schema")
    qd = qdir / "query_dataset"
    qd.mkdir()
    (qd / "books_info.sql").write_text("-- sql\n")
    (qd / "review_query.db").write_bytes(b"SQLite format 3\x00")
    q = qdir / f"query{query_id}"
    q.mkdir()
    (q / "query.json").write_text('{"question": "list titles"}')
    (q / "validate.py").write_text(_UPSTREAM_Q2Q3)
    return data_root


def _load_validate(tests_dir: Path):
    spec = importlib.util.spec_from_file_location("_dab_validate_qx", str(tests_dir / "validate.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate


@pytest.mark.parametrize("query_id", [2, 3])
def test_short_canonical_answer_passes(tmp_path: Path, query_id: int):
    data_root = _scaffold(tmp_path, query_id=query_id)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="bookreview", tasks_root=out)
    validate = _load_validate(manifest[0]["task_dir"] / "tests")
    ok, _ = validate("Book One, Book Two, Book Three")
    assert ok


@pytest.mark.parametrize("query_id", [2, 3])
def test_sql_dump_style_answer_fails(tmp_path: Path, query_id: int):
    """Substring-leak path: agent dumped the SQL file. All titles appear in
    it, but the answer is far over the length cap.
    """
    data_root = _scaffold(tmp_path, query_id=query_id)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="bookreview", tasks_root=out)
    validate = _load_validate(manifest[0]["task_dir"] / "tests")
    dump = "INSERT INTO books VALUES " + ", ".join(_TITLES) + ". " + ("x" * 4000)
    ok, reason = validate(dump)
    assert not ok
    assert "too long" in reason.lower()


@pytest.mark.parametrize("query_id", [2, 3])
def test_short_answer_missing_title_still_fails(tmp_path: Path, query_id: int):
    data_root = _scaffold(tmp_path, query_id=query_id)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="bookreview", tasks_root=out)
    validate = _load_validate(manifest[0]["task_dir"] / "tests")
    ok, reason = validate("Book One, Book Two")
    assert not ok
    assert "book three" in reason.lower() or "missing" in reason.lower()
