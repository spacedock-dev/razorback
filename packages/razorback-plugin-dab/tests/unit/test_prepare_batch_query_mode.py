# ABOUTME: AC-2 — batch query_mode emits one task per dataset with queryN/ siblings.
# ABOUTME: Mirrors DAB upstream's workspace-readme-direct-entity-output.md workdir shape.

from __future__ import annotations

import json
from pathlib import Path

import yaml

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


def _build_synthetic_three_query_data_root(root: Path) -> Path:
    """Bookreview-shaped data root carrying q1, q2, q3.

    Mirrors test_prepare_per_query.py's fixture extended to seed three queries —
    the per-query fixture's single-query shape is preserved otherwise.
    """
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
    for n in (1, 2, 3):
        q = qdir / f"query{n}"
        q.mkdir()
        (q / "query.json").write_text(
            json.dumps({"question": f"Question {n}?"})
        )
        (q / "validate.py").write_text(
            "def validate(answer):\n"
            f"    expected = 'a{n}'\n"
            "    ok = answer == expected\n"
            "    return (ok, 'ok' if ok else 'no')\n"
        )
        (q / "ground_truth.csv").write_text(f"answer\na{n}\n")
    return data_root


def test_batch_mode_emits_one_task_dir_per_dataset(tmp_path: Path) -> None:
    data_root = _build_synthetic_three_query_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        query_mode="batch",
    )
    assert len(manifest) == 1
    entry = manifest[0]
    assert entry["dataset"] == "bookreview"
    assert entry["task_name"] == "bookreview"
    assert entry.get("query_ids") == [1, 2, 3]
    assert entry["task_dir"].name == "bookreview"


def test_batch_mode_workdir_has_three_query_subdirs(tmp_path: Path) -> None:
    data_root = _build_synthetic_three_query_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        query_mode="batch",
    )
    workdir = manifest[0]["task_dir"] / "steps" / "main" / "workdir"
    assert (workdir / "query1" / "query.json").exists()
    assert (workdir / "query2" / "query.json").exists()
    assert (workdir / "query3" / "query.json").exists()
    # The flat workdir/query.json must NOT exist — batch shape uses sibling
    # queryN/ dirs per upstream workspace-readme-direct-entity-output.md.
    assert not (workdir / "query.json").exists()
    # Forbidden files must not leak under any queryN/ subdir.
    for forbidden in ("ground_truth.csv", "validate.py", "__pycache__"):
        leftover = list(workdir.rglob(forbidden))
        assert not leftover, f"{forbidden} leaked: {leftover}"


def test_batch_mode_instruction_enumerates_queries(tmp_path: Path) -> None:
    data_root = _build_synthetic_three_query_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        query_mode="batch",
    )
    task_dir = manifest[0]["task_dir"]
    for path in (task_dir / "instruction.md", task_dir / "steps" / "main" / "instruction.md"):
        text = path.read_text()
        for token in ("query1", "query2", "query3"):
            assert token in text, f"{path}: missing {token}"
        for key in ('"q1"', '"q2"', '"q3"'):
            assert key in text, f"{path}: missing answer key {key}"
        assert "answers.json" in text


def test_batch_mode_tests_dir_has_per_query_validators(tmp_path: Path) -> None:
    data_root = _build_synthetic_three_query_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        query_mode="batch",
    )
    tests_dir = manifest[0]["task_dir"] / "tests"
    assert (tests_dir / "validate_q1.py").exists()
    assert (tests_dir / "validate_q2.py").exists()
    assert (tests_dir / "validate_q3.py").exists()
    assert (tests_dir / "verify_batch.py").exists()
    assert (tests_dir / "test.sh").exists()


def test_batch_mode_stratum_payload_uses_query_ids_list(tmp_path: Path) -> None:
    data_root = _build_synthetic_three_query_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        query_mode="batch",
    )
    payload = json.loads(
        (manifest[0]["task_dir"] / "tests" / "stratum.json").read_text()
    )
    assert payload["stratum"]["dataset"] == "bookreview"
    assert payload["stratum"]["query_ids"] == [1, 2, 3]
    assert "query_id" not in payload["stratum"]
    assert payload["stratum"]["backends"] == ["postgres", "sqlite"]
