# ABOUTME: FU-2 AC-2 — AdeBenchBenchmarkBlock.docker_image_override schema field.
# ABOUTME: Default None; custom string; extra="forbid" still rejects unknown keys.

import pytest
from pydantic import ValidationError

from razorback.spec.schema import AdeBenchBenchmarkBlock, AdeBenchTaskEntry


GIT_URL = "https://github.com/laude-institute/harbor-datasets.git"
COMMIT = "b4e82debfdd2aba9d91c41cd96a997dd549fcbb3"


def _git_entry() -> AdeBenchTaskEntry:
    return AdeBenchTaskEntry(
        path="datasets/ade-bench/ade-bench-airbnb001",
        git_url=GIT_URL,
        git_commit_id=COMMIT,
    )


def test_docker_image_override_default_is_none():
    block = AdeBenchBenchmarkBlock(
        kind="ade-bench",
        tasks_root="/tmp/ade-bench-tasks",
        tasks=[_git_entry()],
    )
    assert block.docker_image_override is None


def test_docker_image_override_custom_value():
    block = AdeBenchBenchmarkBlock(
        kind="ade-bench",
        tasks_root="/tmp/ade-bench-tasks",
        tasks=[_git_entry()],
        docker_image_override="custom-agent:stable",
    )
    assert block.docker_image_override == "custom-agent:stable"


def test_docker_image_override_extra_forbid_preserved():
    with pytest.raises(ValidationError) as exc_info:
        AdeBenchBenchmarkBlock(
            kind="ade-bench",
            tasks_root="/tmp/ade-bench-tasks",
            tasks=[_git_entry()],
            docker_image_override="custom-agent:stable",
            bogus_field="foo",
        )
    msg = str(exc_info.value)
    assert "bogus_field" in msg
