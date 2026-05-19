# ABOUTME: AC-6 — rk runs diff refuses with typed error when run-dirs have different benchmark.kind.

import json
from pathlib import Path

import pytest

from razorback.diff.diff import check_paired_benchmark_kind
from razorback.diff.errors import BenchmarkMismatchError
from razorback.errors import ExitCode


def _write_run_dir(root: Path, *, kind: str | None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_dir_version": 1,
        "experiment": "x",
        "job_name": "abc",
    }
    if kind is not None:
        manifest["benchmark_kind"] = kind
    (root / "manifest.json").write_text(json.dumps(manifest))
    if kind == "dab":
        (root / "summary.json").write_text(
            json.dumps({"summary_version": 1, "stratified_pass_at_1": 0.5, "datasets": {}})
        )
    elif kind == "ade-bench":
        (root / "summary.json").write_text(
            json.dumps({
                "summary_version": 1,
                "benchmark_kind": "ade-bench",
                "score": 0.5,
                "n_trials": 1,
                "n_correct": 0,
            })
        )
    else:
        (root / "summary.json").write_text(json.dumps({"summary_version": 1}))
    (root / "spec.frozen.yaml").write_text(
        f"benchmark:\n  kind: {kind or 'unknown'}\n"
    )
    return root


def test_check_refuses_dab_vs_ade_bench(tmp_path):
    dab_dir = _write_run_dir(tmp_path / "dab_run", kind="dab")
    ade_dir = _write_run_dir(tmp_path / "adebench_run", kind="ade-bench")
    with pytest.raises(BenchmarkMismatchError) as exc:
        check_paired_benchmark_kind(dab_dir, ade_dir)
    msg = str(exc.value)
    assert "dab" in msg.lower()
    assert "ade-bench" in msg.lower()
    assert exc.value.exit_code == ExitCode.CONSTRAINT_VIOLATION
    assert exc.value.exit_code == 12


def test_check_proceeds_when_both_runs_share_kind(tmp_path):
    a = _write_run_dir(tmp_path / "a", kind="ade-bench")
    b = _write_run_dir(tmp_path / "b", kind="ade-bench")
    check_paired_benchmark_kind(a, b)  # must not raise


def test_check_proceeds_when_one_side_lacks_benchmark_kind(tmp_path):
    """Backwards-compat: M5/M6 fixtures synthesized without benchmark_kind continue to work."""
    a = _write_run_dir(tmp_path / "a", kind="dab")
    b = _write_run_dir(tmp_path / "b", kind=None)
    check_paired_benchmark_kind(a, b)  # must not raise


def test_check_proceeds_when_both_sides_lack_benchmark_kind(tmp_path):
    a = _write_run_dir(tmp_path / "a", kind=None)
    b = _write_run_dir(tmp_path / "b", kind=None)
    check_paired_benchmark_kind(a, b)  # must not raise
