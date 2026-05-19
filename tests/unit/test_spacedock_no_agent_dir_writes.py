# ABOUTME: AC-7 — razorback source never references harbor's `agent/` directory for writes.
# ABOUTME: All razorback-owned state lives under logs_dir/agent_freeze/.

import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def test_no_agent_dir_writes_in_razorback_agents():
    """Static grep: `agent_dir` is not referenced anywhere under src/razorback/agents/."""
    result = subprocess.run(
        ["grep", "-rn", "agent_dir", str(REPO / "src" / "razorback" / "agents")],
        capture_output=True, text=True,
    )
    assert result.returncode == 1, (
        f"`agent_dir` should not appear under src/razorback/agents/. "
        f"grep output:\n{result.stdout}"
    )
    assert result.stdout == ""


def test_agent_freeze_is_the_only_razorback_subtree_name():
    """Positive twin: `agent_freeze` IS referenced (Task 5 writes there)."""
    result = subprocess.run(
        ["grep", "-rln", "agent_freeze", str(REPO / "src" / "razorback" / "agents")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "spacedock_solver.py" in result.stdout
