# ABOUTME: AC-4 — rk constraints check enforces pinned fields and mutation-surface coverage.

import subprocess
from pathlib import Path

import pytest
import yaml

from razorback.constraints.check import check_spec_against_constraints
from razorback.errors import ConstraintViolation, ExitCode


def _constraints(pinned: dict, mutation: list[str]) -> dict:
    return {"version": 1, "pinned": pinned, "mutation_surfaces": mutation}


def _spec(agent_model: str, image_digest: str, *, prompt_file: str = "p.md") -> dict:
    return {
        "version": 1,
        "experiment": "t",
        "agent": {
            "kind": "claude-cli",
            "model": agent_model,
            "prompt_file": prompt_file,
            "sampling": {"temperature": 0.0},
        },
        "benchmark": {"kind": "dab", "data_root": "/tmp", "datasets": ["bookreview"]},
        "environment": {
            "kind": "docker",
            "image": "x",
            "image_digest": image_digest,
        },
    }


def test_pinned_field_matching_passes() -> None:
    spec = _spec("claude-opus-4-5", "sha256:abc")
    cons = _constraints({"agent.model": "claude-opus-4-5"}, [])
    check_spec_against_constraints(spec, cons)


def test_pinned_field_mismatch_raises_constraint_violation() -> None:
    spec = _spec("claude-opus-4-5", "sha256:abc")
    cons = _constraints({"agent.model": "claude-opus-4-7"}, [])
    with pytest.raises(ConstraintViolation) as exc_info:
        check_spec_against_constraints(spec, cons)
    assert exc_info.value.exit_code == ExitCode.CONSTRAINT_VIOLATION
    assert exc_info.value.exit_code == 12
    assert "agent.model" in str(exc_info.value)


def test_pinned_nested_path_walks_through_dict() -> None:
    spec = _spec("claude-opus-4-5", "sha256:abc")
    cons = _constraints(
        {"environment.image_digest": "sha256:other"}, []
    )
    with pytest.raises(ConstraintViolation, match="environment.image_digest"):
        check_spec_against_constraints(spec, cons)


def test_mutation_surface_coverage_for_changed_field() -> None:
    """When mutation_surfaces declares agent.prompt_file, a baseline diverging there is OK."""
    baseline_spec = _spec("claude-opus-4-5", "sha256:abc", prompt_file="baseline.md")
    hypothesis_spec = _spec("claude-opus-4-5", "sha256:abc", prompt_file="hypothesis.md")
    cons_ok = _constraints({"agent.model": "claude-opus-4-5"}, ["agent.prompt_file"])
    cons_bad = _constraints({"agent.model": "claude-opus-4-5"}, [])
    check_spec_against_constraints(hypothesis_spec, cons_ok, baseline=baseline_spec)
    with pytest.raises(ConstraintViolation):
        check_spec_against_constraints(
            hypothesis_spec, cons_bad, baseline=baseline_spec,
        )


_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_rk_constraints_check_cli_exit_12_on_violation(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.yaml"
    cons_path = tmp_path / "constraints.yaml"
    spec_path.write_text(yaml.safe_dump(_spec("claude-opus-4-5", "sha256:abc")))
    cons_path.write_text(
        yaml.safe_dump(_constraints({"agent.model": "claude-opus-4-7"}, []))
    )
    cp = subprocess.run(
        [
            "uv", "run", "rk", "constraints", "check",
            str(spec_path), "--constraints", str(cons_path),
        ],
        capture_output=True, text=True, cwd=_REPO_ROOT,
    )
    assert cp.returncode == 12, cp.stderr
    assert "ConstraintViolation" in cp.stderr


def test_rk_constraints_check_cli_exit_0_on_match(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.yaml"
    cons_path = tmp_path / "constraints.yaml"
    spec_path.write_text(yaml.safe_dump(_spec("claude-opus-4-5", "sha256:abc")))
    cons_path.write_text(
        yaml.safe_dump(_constraints({"agent.model": "claude-opus-4-5"}, []))
    )
    cp = subprocess.run(
        [
            "uv", "run", "rk", "constraints", "check",
            str(spec_path), "--constraints", str(cons_path),
        ],
        capture_output=True, text=True, cwd=_REPO_ROOT,
    )
    assert cp.returncode == 0, cp.stderr
    assert "OK" in cp.stdout
