# ABOUTME: Shared pytest fixtures for razorback tests.
# ABOUTME: colima_safe_tmp_path anchors test dirs under /Users so Colima bind mounts work.

import os
import shutil
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def colima_safe_tmp_path():
    """A tmp dir under /Users/... that Colima mounts into the docker VM."""
    default_base = Path(__file__).resolve().parent.parent / ".test-tmp"
    base = Path(os.environ.get("RAZORBACK_TEST_DIR", default_base))
    base.mkdir(parents=True, exist_ok=True)
    work = base / f"t-{uuid.uuid4().hex[:8]}"
    work.mkdir()
    try:
        yield work
    finally:
        shutil.rmtree(work, ignore_errors=True)
