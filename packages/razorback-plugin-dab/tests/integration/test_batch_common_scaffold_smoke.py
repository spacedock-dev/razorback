# ABOUTME: Env-backed affected DAB batch smoke for common_scaffold verifier imports.
# ABOUTME: Skips unless DAB_DATA_ROOT points at a hydrated upstream DAB data tree.

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


def test_affected_dataset_batch_emits_reward_artifacts(tmp_path: Path) -> None:
    data_root_raw = os.environ.get("DAB_DATA_ROOT")
    if not data_root_raw:
        pytest.skip("set DAB_DATA_ROOT to run the affected DAB dataset smoke")
    data_root = Path(data_root_raw)
    dataset = os.environ.get("DAB_AFFECTED_DATASET", "PANCANCER_ATLAS")
    dataset_dir = data_root / f"query_{dataset}"
    if not dataset_dir.is_dir():
        pytest.skip(f"affected DAB dataset is not available: {dataset_dir}")
    if not (data_root / "common_scaffold").is_dir():
        pytest.skip(f"common_scaffold is not available under {data_root}")

    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset=dataset,
        tasks_root=tmp_path / "tasks",
        query_mode="batch",
    )
    tests_dir = manifest[0]["task_dir"] / "tests"
    answers = tmp_path / "answers.json"
    answers.write_text("{}")
    reward_out = tmp_path / "reward.json"
    per_query_out = tmp_path / "reward_per_query.json"

    result = subprocess.run(
        [
            sys.executable,
            str(tests_dir / "verify_batch.py"),
            "--tests-dir",
            str(tests_dir),
            "--answers",
            str(answers),
            "--reward-out",
            str(reward_out),
            "--per-query-out",
            str(per_query_out),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (tests_dir / "common_scaffold" / "validate" / "levenshtein.py").exists()
    assert isinstance(json.loads(reward_out.read_text())["reward"], float)
    assert json.loads(per_query_out.read_text())
