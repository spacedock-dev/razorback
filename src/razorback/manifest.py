# ABOUTME: Run-level manifest writer. The run_dir_version pins the public contract.
# ABOUTME: See design §3.3 (stability promise) and §6.7 (created_at semantics).

import json
from datetime import datetime, timezone
from pathlib import Path

RUN_DIR_VERSION = 1


def write_manifest(path: Path, *, experiment: str, job_name: str) -> None:
    payload = {
        "run_dir_version": RUN_DIR_VERSION,
        "experiment": experiment,
        "job_name": job_name,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    Path(path).write_text(json.dumps(payload, indent=2) + "\n")
