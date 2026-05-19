# ABOUTME: AC-1 — SpacedockSolverAgent.__init__ refuses to resume when the resume spec's
# ABOUTME: sealed_hash does not match the seed run's frozen-spec sealed_hash.

from pathlib import Path

import pytest
import yaml

from razorback.agents.seal import compute_sealed_hash, prompt_sha256
from razorback.agents.spacedock_solver import SpacedockSolverAgent
from razorback.errors import ExitCode, SeedMismatchError


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "spacedock"
PROMPT_DIR = FIXTURE_ROOT / "prompts"


def _materialize_seed_spec(tmp_path: Path) -> Path:
    template = (FIXTURE_ROOT / "seed-frozen-spec.yaml").read_text()
    model_hash = prompt_sha256((PROMPT_DIR / "model.md").read_bytes())
    analyze_hash = prompt_sha256((PROMPT_DIR / "analyze.md").read_bytes())
    verify_hash = prompt_sha256((PROMPT_DIR / "verify.md").read_bytes())
    sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes={"model": model_hash, "analyze": analyze_hash, "verify": verify_hash},
    )
    rendered = (
        template.replace("SEED_MODEL_HASH_PLACEHOLDER", model_hash)
        .replace("SEED_ANALYZE_HASH_PLACEHOLDER", analyze_hash)
        .replace("SEED_VERIFY_HASH_PLACEHOLDER", verify_hash)
        .replace("SEED_SEALED_HASH_PLACEHOLDER", sealed)
    )
    spec_path = tmp_path / "seed.frozen.yaml"
    spec_path.write_text(rendered)
    return spec_path


def _materialize_resume_mismatch_spec(tmp_path: Path) -> Path:
    template = (FIXTURE_ROOT / "resume-mismatch-frozen-spec.yaml").read_text()
    drifted_model_body = b"DRIFTED MODEL PROMPT\n"
    drifted_model_hash = prompt_sha256(drifted_model_body)
    analyze_hash = prompt_sha256((PROMPT_DIR / "analyze.md").read_bytes())
    verify_hash = prompt_sha256((PROMPT_DIR / "verify.md").read_bytes())
    sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes={
            "model": drifted_model_hash,
            "analyze": analyze_hash,
            "verify": verify_hash,
        },
    )
    rendered = (
        template.replace("RESUME_MODEL_HASH_PLACEHOLDER", drifted_model_hash)
        .replace("RESUME_ANALYZE_HASH_PLACEHOLDER", analyze_hash)
        .replace("RESUME_VERIFY_HASH_PLACEHOLDER", verify_hash)
        .replace("RESUME_SEALED_HASH_PLACEHOLDER", sealed)
    )
    spec_path = tmp_path / "resume.frozen.yaml"
    spec_path.write_text(rendered)
    return spec_path


def _agent_kwargs_from_frozen_spec(spec_path: Path) -> dict:
    spec = yaml.safe_load(spec_path.read_text())
    agent = spec["agent"]
    return {
        "model": agent["model"],
        "sampling": dict(agent["sampling"]),
        "stages": list(agent["stages"]),
        "tools_allowed": list(agent["tools_allowed"]),
        "prompts": dict(agent["prompts"]),
        "sealed_hash": agent["sealed_hash"],
        "resolved_auth_env": {"ANTHROPIC_API_KEY": "sk-test"},
    }


def test_agent_init_refuses_when_resume_sealed_hash_mismatches_seed(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    seed_spec = _materialize_seed_spec(tmp_path)
    (run_dir / "spec.frozen.yaml").write_bytes(seed_spec.read_bytes())

    resume_spec = _materialize_resume_mismatch_spec(tmp_path)
    kwargs = _agent_kwargs_from_frozen_spec(resume_spec)

    with pytest.raises(SeedMismatchError) as exc:
        SpacedockSolverAgent(
            logs_dir=tmp_path / "agent_logs",
            model_name=kwargs["model"],
            prior_frozen_spec_path=run_dir / "spec.frozen.yaml",
            **kwargs,
        )

    msg = str(exc.value)
    assert "prompts.model" in msg or "sealed_hash" in msg
    assert exc.value.exit_code == ExitCode.SEED_MISMATCH


def test_agent_init_succeeds_when_sealed_hash_matches(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    seed_spec = _materialize_seed_spec(tmp_path)
    (run_dir / "spec.frozen.yaml").write_bytes(seed_spec.read_bytes())

    kwargs = _agent_kwargs_from_frozen_spec(seed_spec)
    agent = SpacedockSolverAgent(
        logs_dir=tmp_path / "agent_logs",
        model_name=kwargs["model"],
        prior_frozen_spec_path=run_dir / "spec.frozen.yaml",
        **kwargs,
    )
    assert agent.sealed_hash == kwargs["sealed_hash"]


def test_agent_init_succeeds_when_no_prior_frozen_spec(tmp_path):
    seed_spec = _materialize_seed_spec(tmp_path)
    kwargs = _agent_kwargs_from_frozen_spec(seed_spec)
    agent = SpacedockSolverAgent(
        logs_dir=tmp_path / "agent_logs",
        model_name=kwargs["model"],
        prior_frozen_spec_path=None,
        **kwargs,
    )
    assert agent.sealed_hash == kwargs["sealed_hash"]


def test_agent_refusal_happens_before_any_harbor_io(tmp_path, monkeypatch):
    """AC-1: refusal happens BEFORE harbor.Job.create is called."""
    from harbor.job import Job

    async def _explode(*a, **kw):
        raise AssertionError("Job.create called — refusal did NOT happen before harbor I/O")

    monkeypatch.setattr(Job, "create", _explode)

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    seed_spec = _materialize_seed_spec(tmp_path)
    (run_dir / "spec.frozen.yaml").write_bytes(seed_spec.read_bytes())
    resume_spec = _materialize_resume_mismatch_spec(tmp_path)
    kwargs = _agent_kwargs_from_frozen_spec(resume_spec)

    with pytest.raises(SeedMismatchError):
        SpacedockSolverAgent(
            logs_dir=tmp_path / "agent_logs",
            model_name=kwargs["model"],
            prior_frozen_spec_path=run_dir / "spec.frozen.yaml",
            **kwargs,
        )
