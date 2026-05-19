# ABOUTME: AC-1 (CLI variant) — `rk run` against a resume spec whose sealed_hash
# ABOUTME: mismatches the run-dir's prior frozen spec exits with code 20.

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from razorback.agents.seal import compute_sealed_hash, prompt_sha256
from razorback.spec.freeze import derive_job_name, freeze_spec
from razorback.spec.parse import parse_spec_file


REPO = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO / "tests" / "fixtures" / "spacedock"
PROMPT_DIR = FIXTURE_ROOT / "prompts"


def _write_resume_spec_with_drifted_model_prompt(tmp_path: Path) -> tuple[Path, Path]:
    runs_dir = tmp_path / "_runs"
    experiment = "m4-cli-seed-mismatch"

    drifted_prompt = tmp_path / "drifted-model.md"
    drifted_prompt.write_text("DRIFTED MODEL PROMPT\n")

    resume_yaml = {
        "version": 1,
        "experiment": experiment,
        "agent": {
            "kind": "spacedock-solver",
            "model": "claude-opus-4-5",
            "sampling": {"temperature": 0.0, "top_p": None, "seed": 42},
            "stages": ["model", "analyze", "verify"],
            "tools_allowed": ["Bash", "Read", "Write", "Edit"],
            "prompts": {
                "model": str(drifted_prompt),
                "analyze": str(PROMPT_DIR / "analyze.md"),
                "verify": str(PROMPT_DIR / "verify.md"),
            },
        },
        "benchmark": {
            "kind": "dab",
            "data_root": "/Users/clkao/git/dataagentbench/data",
            "datasets": ["bookreview"],
        },
        "trials": 1,
        "observers": [],
    }
    resume_spec = tmp_path / "resume.yaml"
    resume_spec.write_text(yaml.safe_dump(resume_yaml, sort_keys=False))

    # Freeze the resume spec to derive its job_name; place the seed spec.frozen.yaml there.
    parsed = parse_spec_file(resume_spec)
    frozen_resume_text = freeze_spec(parsed)
    job_name = derive_job_name(frozen_resume_text)
    run_dir = runs_dir / experiment / job_name
    run_dir.mkdir(parents=True)

    # Build the seed frozen spec — same shape but model prompt points at the non-drifted file
    # so its sealed_hash differs from the resume's.
    model_hash = prompt_sha256((PROMPT_DIR / "model.md").read_bytes())
    analyze_hash = prompt_sha256((PROMPT_DIR / "analyze.md").read_bytes())
    verify_hash = prompt_sha256((PROMPT_DIR / "verify.md").read_bytes())
    seed_sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes={"model": model_hash, "analyze": analyze_hash, "verify": verify_hash},
    )
    seed_frozen = {
        "version": 1,
        "experiment": experiment,
        "agent": {
            "kind": "spacedock-solver",
            "model": "claude-opus-4-5",
            "sampling": {"temperature": 0.0, "top_p": None, "seed": 42},
            "stages": ["model", "analyze", "verify"],
            "tools_allowed": ["Bash", "Read", "Write", "Edit"],
            "prompts": {"model": model_hash, "analyze": analyze_hash, "verify": verify_hash},
            "sealed_hash": seed_sealed,
            "prompt_contents": {
                "model": (PROMPT_DIR / "model.md").read_text(),
                "analyze": (PROMPT_DIR / "analyze.md").read_text(),
                "verify": (PROMPT_DIR / "verify.md").read_text(),
            },
        },
        "benchmark": {
            "kind": "dab",
            "data_root": "/Users/clkao/git/dataagentbench/data",
            "datasets": ["bookreview"],
        },
        "trials": 1,
        "observers": [],
    }
    (run_dir / "spec.frozen.yaml").write_text(yaml.safe_dump(seed_frozen, sort_keys=False))
    return resume_spec, runs_dir


@pytest.mark.timeout(60)
def test_rk_run_exits_20_on_seed_mismatch(tmp_path):
    resume_spec, runs_dir = _write_resume_spec_with_drifted_model_prompt(tmp_path)
    env = {**os.environ, "ANTHROPIC_API_KEY": "sk-test-fake"}
    result = subprocess.run(
        [
            sys.executable, "-m", "razorback.cli", "run", str(resume_spec),
            "--runs-dir", str(runs_dir),
        ],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 20, (
        f"expected exit code 20 (SeedMismatchError); got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "SeedMismatchError" in result.stderr
