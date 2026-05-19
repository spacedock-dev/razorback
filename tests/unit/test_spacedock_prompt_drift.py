# ABOUTME: AC-3 — at run time, the agent re-hashes prompt_contents.<stage> and refuses
# ABOUTME: if the recomputed hash differs from the frozen prompts.<stage> sha256 string.

import pytest

from razorback.agents.seal import compute_sealed_hash, prompt_sha256
from razorback.agents.spacedock_solver import (
    SpacedockSolverAgent,
    SpacedockSolverAgentError,
)


def test_run_refuses_when_prompt_contents_hash_does_not_match_pinned_hash(tmp_path):
    body_a = b"MODEL PROMPT A\n"
    body_b = b"MODEL PROMPT B (TAMPERED)\n"
    pinned_a = prompt_sha256(body_a)
    pinned_analyze = prompt_sha256(b"ANALYZE\n")
    pinned_verify = prompt_sha256(b"VERIFY\n")

    sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes={"model": pinned_a, "analyze": pinned_analyze, "verify": pinned_verify},
    )

    agent = SpacedockSolverAgent(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        tools_allowed=[],
        prompts={"model": pinned_a, "analyze": pinned_analyze, "verify": pinned_verify},
        sealed_hash=sealed,
        extra_env={"ANTHROPIC_API_KEY": "sk-test"},
        prompt_contents={
            "model": body_b.decode("utf-8"),   # drifted
            "analyze": "ANALYZE\n",
            "verify": "VERIFY\n",
        },
        prior_frozen_spec_path=None,
    )
    with pytest.raises(SpacedockSolverAgentError) as exc:
        agent.verify_prompt_contents()
    msg = str(exc.value)
    assert pinned_a in msg
    assert "model" in msg


def test_run_passes_when_prompt_contents_hash_matches(tmp_path):
    body = b"MODEL PROMPT\n"
    pinned = prompt_sha256(body)
    pinned_a = prompt_sha256(b"A\n")
    pinned_v = prompt_sha256(b"V\n")
    sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes={"model": pinned, "analyze": pinned_a, "verify": pinned_v},
    )
    agent = SpacedockSolverAgent(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        tools_allowed=[],
        prompts={"model": pinned, "analyze": pinned_a, "verify": pinned_v},
        sealed_hash=sealed,
        extra_env={"ANTHROPIC_API_KEY": "sk-test"},
        prompt_contents={"model": "MODEL PROMPT\n", "analyze": "A\n", "verify": "V\n"},
        prior_frozen_spec_path=None,
    )
    agent.verify_prompt_contents()
