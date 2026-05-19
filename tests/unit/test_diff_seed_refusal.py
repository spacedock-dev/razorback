# ABOUTME: AC-3 — runs diff refuses (typed error, exit 20) when only one run has agent.seed.default.

from pathlib import Path

import pytest
import yaml

from razorback.diff.diff import check_paired_seed_compatibility
from razorback.errors import ExitCode, SeedMismatchError


def _make_run(path: Path, *, with_seed: bool) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    agent_block: dict = {"kind": "claude-cli", "model": "claude-opus-4-5"}
    if with_seed:
        agent_block["sampling"] = {"temperature": 0.0}
        agent_block["seed"] = {"default": 42}
    spec = {
        "version": 1,
        "experiment": "t",
        "agent": agent_block,
        "benchmark": {"kind": "dab", "data_root": "/tmp", "datasets": ["bookreview"]},
    }
    (path / "spec.frozen.yaml").write_text(yaml.safe_dump(spec))
    return path


def test_seed_refusal_when_only_one_run_has_seed(tmp_path: Path) -> None:
    a = _make_run(tmp_path / "a", with_seed=False)
    b = _make_run(tmp_path / "b", with_seed=True)
    with pytest.raises(SeedMismatchError) as exc_info:
        check_paired_seed_compatibility(a, b)
    assert exc_info.value.exit_code == ExitCode.SEED_MISMATCH
    assert exc_info.value.exit_code == 20


def test_seed_refusal_reverse_orientation(tmp_path: Path) -> None:
    a = _make_run(tmp_path / "a", with_seed=True)
    b = _make_run(tmp_path / "b", with_seed=False)
    with pytest.raises(SeedMismatchError):
        check_paired_seed_compatibility(a, b)


def test_seed_ok_when_both_have_seed(tmp_path: Path) -> None:
    a = _make_run(tmp_path / "a", with_seed=True)
    b = _make_run(tmp_path / "b", with_seed=True)
    check_paired_seed_compatibility(a, b)


def test_seed_ok_when_neither_has_seed(tmp_path: Path) -> None:
    a = _make_run(tmp_path / "a", with_seed=False)
    b = _make_run(tmp_path / "b", with_seed=False)
    check_paired_seed_compatibility(a, b)
