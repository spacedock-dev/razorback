# ABOUTME: AC-2, compute_sealed_hash takes the six canonical sealed inputs and flips on each.
# ABOUTME: Per spec §4.3.5 + §8.4. b5 plan lines 41-42 name this contract.

from razorback.agents.seal import compute_sealed_hash


BASE_INPUTS = dict(
    model="claude-opus-4-5",
    sampling={"temperature": 0.0, "top_p": None, "seed": None},
    solver_workflow_content_hash="sha256:" + "a" * 64,
    prompt_content_hashes={"readme": "sha256:" + "b" * 64},
    spacedock_skill_version="1.0.0",
    harbor_agent_kwargs={"max_turns": 200, "tools_allowed": []},
)


def test_sealed_hash_is_32_hex_chars():
    h = compute_sealed_hash(**BASE_INPUTS)
    assert len(h) == 32
    assert all(c in "0123456789abcdef" for c in h)


def test_sealed_hash_is_deterministic():
    h1 = compute_sealed_hash(**BASE_INPUTS)
    h2 = compute_sealed_hash(**BASE_INPUTS)
    assert h1 == h2


def test_perturbing_each_of_six_inputs_flips_hash():
    base = compute_sealed_hash(**BASE_INPUTS)
    perturbations = {
        "model": "claude-sonnet-4-6",
        "sampling": {"temperature": 0.1, "top_p": None, "seed": None},
        "solver_workflow_content_hash": "sha256:" + "c" * 64,
        "prompt_content_hashes": {"readme": "sha256:" + "d" * 64},
        "spacedock_skill_version": "1.0.1",
        "harbor_agent_kwargs": {"max_turns": 201, "tools_allowed": []},
    }
    for field, perturbed in perturbations.items():
        inputs = {**BASE_INPUTS, field: perturbed}
        h = compute_sealed_hash(**inputs)
        assert h != base, f"perturbing {field} did not flip the sealed_hash"


def test_null_seed_is_pinned_not_dropped():
    inputs = {**BASE_INPUTS, "sampling": {"temperature": 0.0, "top_p": None, "seed": None}}
    h_null_seed = compute_sealed_hash(**inputs)
    inputs_no_seed_key = {**BASE_INPUTS, "sampling": {"temperature": 0.0, "top_p": None}}
    h_missing_seed = compute_sealed_hash(**inputs_no_seed_key)
    # Per seal.py contract: "null is pinned, not dropped".
    assert h_null_seed == h_missing_seed, (
        "canonicalised sampling must coerce missing seed to null; the two forms seal equally"
    )


def test_harbor_agent_kwargs_key_order_irrelevant():
    a = compute_sealed_hash(
        **{**BASE_INPUTS, "harbor_agent_kwargs": {"max_turns": 200, "tools_allowed": []}}
    )
    b = compute_sealed_hash(
        **{**BASE_INPUTS, "harbor_agent_kwargs": {"tools_allowed": [], "max_turns": 200}}
    )
    assert a == b
