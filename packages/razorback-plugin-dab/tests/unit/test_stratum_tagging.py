# ABOUTME: AC-8 — per-(dataset, query) stratum payload shape.
# ABOUTME: rk score consumes stratum.dataset, stratum.query_id, stratum.backends.

import json
from pathlib import Path

from razorback_plugin_dab.generate.stratum import stratum_payload, write_stratum_file


def test_payload_keys():
    payload = stratum_payload(dataset="bookreview", query_id=1, backends=("postgres", "sqlite"))
    assert payload == {
        "stratum": {
            "dataset": "bookreview",
            "query_id": 1,
            "backends": ["postgres", "sqlite"],
        }
    }


def test_write_stratum_file(tmp_path: Path):
    tests_dir = tmp_path / "tests"
    out = write_stratum_file(
        tests_dir=tests_dir,
        dataset="agnews",
        query_id=2,
        backends=("mongo", "sqlite"),
    )
    assert out == tests_dir / "stratum.json"
    payload = json.loads(out.read_text())
    assert payload["stratum"]["dataset"] == "agnews"
    assert payload["stratum"]["query_id"] == 2
    assert payload["stratum"]["backends"] == ["mongo", "sqlite"]
