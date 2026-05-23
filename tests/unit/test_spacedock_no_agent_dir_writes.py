# ABOUTME: AC-7 — razorback source never references harbor's `agent/` directory for writes.
# ABOUTME: All razorback-owned state lives in the sealed-hash freeze CAS.

import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def test_no_agent_dir_writes_in_razorback_agents():
    """Static grep: no razorback source writes under a path whose name is `agent_dir`.

    The agent legitimately READS `environment.env_paths.agent_dir` to derive the
    container-side bind-mount path; that read is fine (it identifies harbor's surface,
    not razorback's write target). What's forbidden is razorback constructing a path
    of the form `<...>/agent_dir/...` and writing into it, or calling `.mkdir()`,
    `.write_text()`, etc. on a variable named `agent_dir`.
    """
    forbidden_patterns = (
        r"agent_dir\.mkdir",
        r"agent_dir\.write",
        r"agent_dir / [\"']",
        r"agent_dir/[a-zA-Z]",  # path literal like "/agent_dir/foo"
    )
    sources = list((REPO / "src" / "razorback" / "agents").glob("*.py"))
    offenders: list[str] = []
    for path in sources:
        for pattern in forbidden_patterns:
            result = subprocess.run(
                ["grep", "-En", pattern, str(path)],
                capture_output=True, text=True,
            )
            if result.returncode == 0 and result.stdout:
                offenders.append(f"{path}:\n{result.stdout}")
    assert not offenders, (
        "razorback agents must not write inside harbor's agent_dir subtree. "
        f"Found:\n{''.join(offenders)}"
    )


def test_freeze_cas_is_the_only_razorback_checkpoint_surface_name():
    """Positive twin: spacedock_solver references the sealed-hash freeze CAS."""
    result = subprocess.run(
        ["grep", "-rln", "resolve_freeze_dir", str(REPO / "src" / "razorback" / "agents")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "spacedock_solver.py" in result.stdout
