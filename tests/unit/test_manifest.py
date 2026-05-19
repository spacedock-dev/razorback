# ABOUTME: Unit tests for the run-level manifest writer (§3.3, §6.7).
# ABOUTME: Validates run_dir_version: 1 and ISO 8601 created_at with timezone.

import json
import re
from datetime import datetime

from razorback.manifest import RUN_DIR_VERSION, write_manifest


def test_manifest_has_run_dir_version_1(colima_safe_tmp_path):
    out = colima_safe_tmp_path / "manifest.json"
    write_manifest(out, experiment="m1-nop", job_name="abc1234567890def")
    data = json.loads(out.read_text())
    assert data["run_dir_version"] == 1
    assert RUN_DIR_VERSION == 1


def test_manifest_created_at_is_iso8601_with_tz(colima_safe_tmp_path):
    out = colima_safe_tmp_path / "manifest.json"
    write_manifest(out, experiment="m1-nop", job_name="abc1234567890def")
    data = json.loads(out.read_text())
    # ISO 8601 with timezone (Z or ±HH:MM)
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$", data["created_at"])
    parsed = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
    assert parsed.tzinfo is not None


def test_manifest_records_experiment_and_job_name(colima_safe_tmp_path):
    out = colima_safe_tmp_path / "manifest.json"
    write_manifest(out, experiment="m1-nop", job_name="abc1234567890def")
    data = json.loads(out.read_text())
    assert data["experiment"] == "m1-nop"
    assert data["job_name"] == "abc1234567890def"
