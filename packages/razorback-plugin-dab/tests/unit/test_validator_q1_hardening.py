# ABOUTME: PKG-13 T8 — bookreview-q1 hardened validator (AC-5).
# ABOUTME: Bounded-decade parse rejects substring leaks from the SQL dump.

import importlib.util
import shutil
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

# Upstream q1 validator: any answer containing "2020" or "2020s" passes. The
# hardened wrapper must accept only answers that PARSE as the ground-truth
# decade.
_UPSTREAM_Q1 = """
def validate(answer):
    if not isinstance(answer, str):
        return (False, 'not a string')
    if '2020' in answer:
        return (True, 'ok')
    return (False, 'missing 2020')
"""


def _scaffold(root: Path) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_bookreview"
    qdir.mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump(_BOOKREVIEW_DB_CONFIG))
    (qdir / "db_description.txt").write_text("schema")
    qd = qdir / "query_dataset"
    qd.mkdir()
    (qd / "books_info.sql").write_text("-- sql\n")
    (qd / "review_query.db").write_bytes(b"SQLite format 3\x00")
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "decade?"}')
    (q1 / "validate.py").write_text(_UPSTREAM_Q1)
    return data_root


def _load_validate(tests_dir: Path):
    spec = importlib.util.spec_from_file_location("_dab_validate_q1", str(tests_dir / "validate.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate


@pytest.fixture
def hardened_validate(tmp_path: Path):
    data_root = _scaffold(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="bookreview", tasks_root=out)
    tests_dir = manifest[0]["task_dir"] / "tests"
    assert (tests_dir / "_upstream_validate.py").exists(), "expected upstream wrapper sidecar"
    return _load_validate(tests_dir)


def test_canonical_2020s_passes(hardened_validate):
    ok, _ = hardened_validate("2020s")
    assert ok


def test_2020_decade_string_passes(hardened_validate):
    ok, _ = hardened_validate("2020")
    assert ok


def test_2020_with_essay_text_fails(hardened_validate):
    """Substring-leak path: agent grepped books_info.sql and quoted a year
    inside an essay answer. Upstream substring match would pass; hardened
    bounded-decade match must reject.
    """
    ok, reason = hardened_validate("Around the World Mazes... published in 2020")
    assert not ok
    assert "decade" in reason.lower()


def test_date_string_fails(hardened_validate):
    ok, _ = hardened_validate("2020-01-01")
    assert not ok


def test_zero_padded_year_fails(hardened_validate):
    ok, _ = hardened_validate("02020")
    assert not ok


def test_descriptive_decade_phrase_fails(hardened_validate):
    """`the 2020s decade` matches the upstream substring check but is not a
    bare decade token; the wrapper must require a tight token parse.
    """
    ok, reason = hardened_validate("the 2020s decade")
    assert not ok
    assert "decade" in reason.lower()


def test_upstream_failure_propagates(hardened_validate):
    """When the upstream check fails (no 2020 at all), the hardened
    wrapper does not get a second chance to invent a pass.
    """
    ok, reason = hardened_validate("nineteen-nineties")
    assert not ok
