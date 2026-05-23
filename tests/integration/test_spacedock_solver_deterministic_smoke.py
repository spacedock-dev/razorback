# ABOUTME: AC-1 walking skeleton for v2: rk run examples/specs/_deterministic-smoke-v2.frozen.yaml.
# ABOUTME: Live-API gated; mechanism covered by the canonical freeze-dir test.

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "examples" / "specs" / "_deterministic-smoke-v2.frozen.yaml"


@pytest.mark.skipif(
    not os.environ.get("RAZORBACK_RUN_DOCKER_TESTS"),
    reason="v2 deterministic smoke requires RAZORBACK_RUN_DOCKER_TESTS=1",
)
@pytest.mark.skipif(
    not (
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    ),
    reason="v2 deterministic smoke requires ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN",
)
def test_v2_deterministic_smoke_runs_end_to_end(tmp_path: Path):
    """AC-1: canonical agent.kind: spacedock_solver exits 0
    and writes <cas-root>/<sealed_hash>/sealed_hash.txt (CAS lives outside the run-dir)."""
    runs_root = tmp_path / "_runs"
    runs_root.mkdir()
    cas_root = tmp_path / "freeze-cas"

    env = {**os.environ, "RAZORBACK_FREEZE_DIR": str(cas_root)}
    result = subprocess.run(
        [
            sys.executable, "-m", "razorback.cli", "run",
            str(SPEC), "--runs-dir", str(runs_root),
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=1200,
    )

    assert result.returncode == 0, (
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )

    experiment_dir = runs_root / "_deterministic-smoke-v2"
    run_dirs = [p for p in experiment_dir.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1, run_dirs
    run_dir = run_dirs[0]

    # AC-1 mechanism: sealed_hash.txt at <cas-root>/<sealed_hash>/.
    sealed_hash = "afc50cb618884495c9063958f532b9a1"
    freeze_dir = cas_root / sealed_hash
    sealed_file = freeze_dir / "sealed_hash.txt"
    assert sealed_file.exists(), (
        f"freeze tree missing at {freeze_dir}; "
        f"cas_root contents: {list(cas_root.iterdir()) if cas_root.exists() else 'missing'}"
    )
    assert sealed_file.read_text().strip() == sealed_hash

    # AC-1 reference outcome (when bookreview data is available + API valid):
    # 3/3 trials pass, reward=1.0 each. Matches v1's recorded baseline.
    result_path = run_dir / "result.json"
    if result_path.is_file():
        harbor_result = json.loads(result_path.read_text())
        stats = harbor_result.get("stats", {})
        assert stats.get("n_errored_trials", 0) == 0, (
            f"v2 smoke reported {stats.get('n_errored_trials')} errored trials"
        )
