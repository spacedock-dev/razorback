# ABOUTME: AC-1 + AC-5 integration: budget gate refuses on second invocation against same file.
# ABOUTME: Uses the Phase 1 walking-skeleton smoke spec for end-to-end coverage.

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from razorback.errors import ExitCode


REPO = Path(__file__).resolve().parents[2]
SPEC_TEMPLATE = REPO / "examples" / "specs" / "_deterministic-smoke.yaml"


def _freeze_smoke_spec(target_dir: Path) -> Path:
    """Re-freeze the smoke spec into `target_dir`. Mirrors P1-T9's pattern."""
    from razorback.spec.freeze import freeze_spec
    from razorback.spec.parse import parse_spec_file

    spec = parse_spec_file(SPEC_TEMPLATE)
    frozen_text = freeze_spec(spec)
    frozen_path = target_dir / "_deterministic-smoke.frozen.yaml"
    frozen_path.write_text(frozen_text)
    return frozen_path


@pytest.mark.integration
def test_two_sequential_invocations_second_refuses(colima_safe_tmp_path: Path):
    """AC-1: first run succeeds; second run refuses with exit 22 (budget exceeded).

    The smoke spec carries experiment_meta.max_budget_usd=1.0 and
    estimated_cost_usd=0.6 — two invocations (0.6 + 0.6 = 1.2 > 1.0) trip
    the gate on the second call.
    """
    runs_dir = colima_safe_tmp_path / "_runs"
    runs_dir.mkdir()
    budget_file = colima_safe_tmp_path / "budget.json"
    frozen_path = _freeze_smoke_spec(colima_safe_tmp_path)

    env = {**os.environ}

    # First invocation: budget allows; trial runs; file gains an actual-cost record.
    rc1 = subprocess.run(
        [
            sys.executable, "-m", "razorback.cli", "run",
            str(frozen_path),
            "--runs-dir", str(runs_dir),
            "--max-budget-usd-running", str(budget_file),
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=1200,
    )
    assert rc1.returncode == 0, (
        f"first invocation stdout={rc1.stdout}\nstderr={rc1.stderr}"
    )
    body1 = json.loads(budget_file.read_text())
    assert len(body1["invocations"]) == 1
    # cost_known may be True (API-key) or False (subscription-auth);
    # either way the running total now reflects this invocation.
    assert body1["invocations"][0]["cost_known"] in (True, False)

    # Second invocation: estimate (0.6) + running total would exceed 1.0; refuse exit 22.
    rc2 = subprocess.run(
        [
            sys.executable, "-m", "razorback.cli", "run",
            str(frozen_path),
            "--runs-dir", str(runs_dir),
            "--max-budget-usd-running", str(budget_file),
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert rc2.returncode == ExitCode.BUDGET_EXCEEDED == 22, (
        f"second invocation stdout={rc2.stdout}\nstderr={rc2.stderr}"
    )
    # AC-1: file unchanged on refusal (no new invocation record).
    body2 = json.loads(budget_file.read_text())
    assert len(body2["invocations"]) == 1


@pytest.mark.integration
def test_without_flag_regression_against_smoke(colima_safe_tmp_path: Path):
    """AC-5: omitting --max-budget-usd-running runs the smoke spec unchanged from Phase 1."""
    runs_dir = colima_safe_tmp_path / "_runs-no-budget"
    runs_dir.mkdir()
    frozen_path = _freeze_smoke_spec(colima_safe_tmp_path)

    env = {**os.environ}
    rc = subprocess.run(
        [
            sys.executable, "-m", "razorback.cli", "run",
            str(frozen_path),
            "--runs-dir", str(runs_dir),
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=1200,
    )
    assert rc.returncode == 0, f"stdout={rc.stdout}\nstderr={rc.stderr}"
