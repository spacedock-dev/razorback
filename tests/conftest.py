# ABOUTME: Shared pytest fixtures for razorback tests.
# ABOUTME: colima_safe_tmp_path anchors test dirs under /Users so Colima bind mounts work.

import os
import shutil
import uuid
from pathlib import Path

import pytest


# Phase 1 AC-7: tests that exercise v1 surfaces moved under src/razorback/_legacy/.
# Per test-inventory DROP classification; Phase 6/7 owns deletion.
collect_ignore_glob = [
    "unit/test_ade_bench_translator*.py",
    "unit/test_baseline_promote_verify.py",
    "unit/test_channel_drainer.py",
    "unit/test_claude_cli_registry.py",
    "unit/test_claude_cli_required_env.py",
    "unit/test_claude_cli_supported_sampling.py",
    "unit/test_claude_cli_translator_proxy.py",
    "unit/test_claude_cli_version.py",
    "unit/test_cli_validate_per_trial_state_reset.py",
    "unit/test_cli_validate_tools_allowed.py",
    "unit/test_compat_translator.py",
    "unit/test_constraints_check.py",
    "unit/test_dab_translator*.py",
    "unit/test_manifest.py",
    "unit/test_reconcile_run_workflow.py",
    "unit/test_registry_resolve.py",
    "unit/test_run_drift_wired.py",
    "unit/test_spec_freeze_cli.py",
    "unit/test_spec_freeze_cli_pkg8.py",
    "unit/test_spacedock_cli_seed_mismatch_exit_code.py",
    # Imports razorback.compat (moved to _legacy/compat by Phase 1 AC-5).
    # The v2 translator does not yet handle the harbor_dab benchmark block;
    # Phase 2 re-integration owns the fix.
    "unit/test_translator_harbor_dab.py",
]


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
