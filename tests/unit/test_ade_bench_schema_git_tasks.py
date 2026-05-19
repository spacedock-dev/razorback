# ABOUTME: FU-1 AC-3 — AdeBenchBenchmarkBlock.tasks accepts legacy slug strings AND
# ABOUTME: structured git-task entries {path, git_url, git_commit_id} (harbor TaskConfig shape).

import pytest
from pydantic import ValidationError

from razorback.spec.schema import (
    AdeBenchBenchmarkBlock,
    AdeBenchTaskEntry,
)


GIT_URL = "https://github.com/laude-institute/harbor-datasets.git"
COMMIT = "b4e82debfdd2aba9d91c41cd96a997dd549fcbb3"


def test_legacy_slug_still_parses():
    block = AdeBenchBenchmarkBlock(
        kind="ade-bench",
        tasks_root="/tmp/ade-bench-tasks",
        tasks=["adebench-fixture-001"],
    )
    assert len(block.tasks) == 1
    assert block.tasks[0] == "adebench-fixture-001"
    assert isinstance(block.tasks[0], str)


def test_git_task_entry_parses():
    block = AdeBenchBenchmarkBlock(
        kind="ade-bench",
        tasks_root=".",
        tasks=[
            {
                "path": "datasets/ade-bench/ade-bench-airbnb001",
                "git_url": GIT_URL,
                "git_commit_id": COMMIT,
            }
        ],
    )
    [entry] = block.tasks
    assert isinstance(entry, AdeBenchTaskEntry)
    assert entry.path == "datasets/ade-bench/ade-bench-airbnb001"
    assert entry.git_url == GIT_URL
    assert entry.git_commit_id == COMMIT


def test_partial_git_entry_rejects_missing_commit_id():
    with pytest.raises(ValidationError) as exc:
        AdeBenchBenchmarkBlock(
            kind="ade-bench",
            tasks_root=".",
            tasks=[{"path": "x", "git_url": GIT_URL}],
        )
    assert "git_commit_id" in str(exc.value)


def test_partial_git_entry_rejects_missing_git_url():
    with pytest.raises(ValidationError) as exc:
        AdeBenchBenchmarkBlock(
            kind="ade-bench",
            tasks_root=".",
            tasks=[{"path": "x", "git_commit_id": COMMIT}],
        )
    assert "git_url" in str(exc.value)


def test_partial_git_entry_rejects_missing_path():
    with pytest.raises(ValidationError) as exc:
        AdeBenchBenchmarkBlock(
            kind="ade-bench",
            tasks_root=".",
            tasks=[{"git_url": GIT_URL, "git_commit_id": COMMIT}],
        )
    assert "path" in str(exc.value)


def test_git_task_entry_rejects_extra_keys():
    with pytest.raises(ValidationError) as exc:
        AdeBenchBenchmarkBlock(
            kind="ade-bench",
            tasks_root=".",
            tasks=[
                {
                    "path": "x",
                    "git_url": GIT_URL,
                    "git_commit_id": COMMIT,
                    "name": "unexpected",
                }
            ],
        )
    msg = str(exc.value).lower()
    assert "extra" in msg or "name" in msg


def test_mixed_list_parses():
    block = AdeBenchBenchmarkBlock(
        kind="ade-bench",
        tasks_root="/tmp/ade-bench-tasks",
        tasks=[
            "adebench-fixture-001",
            {
                "path": "datasets/ade-bench/ade-bench-airbnb001",
                "git_url": GIT_URL,
                "git_commit_id": COMMIT,
            },
        ],
    )
    assert len(block.tasks) == 2
    assert block.tasks[0] == "adebench-fixture-001"
    assert isinstance(block.tasks[1], AdeBenchTaskEntry)
