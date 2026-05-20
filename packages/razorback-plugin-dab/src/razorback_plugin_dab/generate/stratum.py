# ABOUTME: Per-(dataset, query) stratum metadata emitter (AC-8).
# ABOUTME: Writes tests/stratum.json; verifier's test.sh copies it to /logs/verifier/.

from __future__ import annotations

import json
from pathlib import Path


def stratum_payload(*, dataset: str, query_id: int, backends: tuple[str, ...]) -> dict:
    return {
        "stratum": {
            "dataset": dataset,
            "query_id": query_id,
            "backends": list(backends),
        }
    }


def write_stratum_file(
    *,
    tests_dir: Path,
    dataset: str,
    query_id: int,
    backends: tuple[str, ...],
) -> Path:
    payload = stratum_payload(dataset=dataset, query_id=query_id, backends=backends)
    out = tests_dir / "stratum.json"
    tests_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return out
