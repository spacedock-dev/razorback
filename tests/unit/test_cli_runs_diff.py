# ABOUTME: AC-1, AC-2 — rk runs diff CLI: end-to-end against two fixture run-dirs.

import json
import subprocess
from pathlib import Path

import yaml


def _make_run(path: Path, outcomes: list[dict], *, with_seed: bool) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "per_trial_outcomes.json").write_text(
        json.dumps({"outcomes_version": 1, "trials": outcomes})
    )
    agent_block: dict = {"kind": "claude-cli", "model": "claude-opus-4-5"}
    if with_seed:
        agent_block["seed"] = {"default": 42}
    spec = {
        "version": 1,
        "experiment": "t",
        "agent": agent_block,
        "benchmark": {"kind": "dab", "data_root": "/tmp", "datasets": ["ds"]},
    }
    (path / "spec.frozen.yaml").write_text(yaml.safe_dump(spec))


_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_rk_runs_diff_emits_json_with_all_four_stats(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    _make_run(
        a,
        [
            {"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0},
            {"dataset": "ds", "query_id": 1, "trial_index": 1, "reward": 0.0},
            {"dataset": "ds", "query_id": 2, "trial_index": 0, "reward": 0.0},
            {"dataset": "ds", "query_id": 2, "trial_index": 1, "reward": 0.0},
        ],
        with_seed=False,
    )
    _make_run(
        b,
        [
            {"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0},
            {"dataset": "ds", "query_id": 1, "trial_index": 1, "reward": 1.0},
            {"dataset": "ds", "query_id": 2, "trial_index": 0, "reward": 1.0},
            {"dataset": "ds", "query_id": 2, "trial_index": 1, "reward": 0.0},
        ],
        with_seed=False,
    )
    cp = subprocess.run(
        [
            "uv", "run", "rk", "runs", "diff", str(a), str(b),
            "--alpha", "0.05", "--bootstrap-iters", "200",
        ],
        capture_output=True, text=True, cwd=_REPO_ROOT,
    )
    assert cp.returncode == 0, cp.stderr
    payload = json.loads(cp.stdout)
    assert payload["alpha"] == 0.05
    assert payload["bootstrap_iters"] == 200
    assert "stratified_delta_ci" in payload
    assert "per_arm_wilson_ci_by_query" in payload
    assert "exact_mcnemar_p_by_query" in payload
    assert "power_mde" in payload


def test_rk_runs_diff_exits_20_on_seed_mismatch(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    _make_run(
        a,
        [{"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0}],
        with_seed=False,
    )
    _make_run(
        b,
        [{"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0}],
        with_seed=True,
    )
    cp = subprocess.run(
        ["uv", "run", "rk", "runs", "diff", str(a), str(b)],
        capture_output=True, text=True, cwd=_REPO_ROOT,
    )
    assert cp.returncode == 20, cp.stderr
    assert "SeedMismatchError" in cp.stderr


def test_rk_runs_diff_alpha_flows_through(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    _make_run(
        a,
        [
            {"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0},
            {"dataset": "ds", "query_id": 1, "trial_index": 1, "reward": 0.0},
        ],
        with_seed=False,
    )
    _make_run(
        b,
        [
            {"dataset": "ds", "query_id": 1, "trial_index": 0, "reward": 1.0},
            {"dataset": "ds", "query_id": 1, "trial_index": 1, "reward": 1.0},
        ],
        with_seed=False,
    )
    cp = subprocess.run(
        [
            "uv", "run", "rk", "runs", "diff", str(a), str(b),
            "--alpha", "0.10", "--bootstrap-iters", "200",
        ],
        capture_output=True, text=True, cwd=_REPO_ROOT,
    )
    assert cp.returncode == 0, cp.stderr
    payload = json.loads(cp.stdout)
    assert payload["alpha"] == 0.10
