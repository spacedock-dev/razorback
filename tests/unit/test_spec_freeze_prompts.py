# ABOUTME: AC-3 — freeze_spec resolves prompt file paths to sha256: strings AND embeds
# ABOUTME: the prompt body under prompt_contents. The sealed_hash is also pinned.

from pathlib import Path

import yaml

from razorback.agents.seal import compute_sealed_hash, prompt_sha256
from razorback.spec.freeze import freeze_spec
from razorback.spec.parse import parse_spec_text


def _spec_with_prompts(tmp_path: Path) -> str:
    p = tmp_path / "prompts"
    p.mkdir()
    (p / "model.md").write_text("MODEL PROMPT\n")
    (p / "analyze.md").write_text("ANALYZE PROMPT\n")
    (p / "verify.md").write_text("VERIFY PROMPT\n")
    return f"""\
version: 1
experiment: m4-freeze
agent:
  kind: spacedock-solver
  model: claude-opus-4-5
  sampling: {{temperature: 0.0, seed: 42}}
  stages: [model, analyze, verify]
  tools_allowed: [Bash]
  prompts:
    model: {p / "model.md"}
    analyze: {p / "analyze.md"}
    verify: {p / "verify.md"}
benchmark:
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets: [bookreview]
trials: 1
"""


def test_freeze_resolves_prompt_paths_to_sha256(tmp_path):
    spec = parse_spec_text(_spec_with_prompts(tmp_path))
    frozen_text = freeze_spec(spec)
    frozen = yaml.safe_load(frozen_text)

    assert frozen["agent"]["prompts"]["model"] == prompt_sha256(b"MODEL PROMPT\n")
    assert frozen["agent"]["prompts"]["analyze"] == prompt_sha256(b"ANALYZE PROMPT\n")
    assert frozen["agent"]["prompts"]["verify"] == prompt_sha256(b"VERIFY PROMPT\n")


def test_freeze_embeds_prompt_contents(tmp_path):
    spec = parse_spec_text(_spec_with_prompts(tmp_path))
    frozen = yaml.safe_load(freeze_spec(spec))
    contents = frozen["agent"]["prompt_contents"]
    assert contents["model"] == "MODEL PROMPT\n"
    assert contents["analyze"] == "ANALYZE PROMPT\n"
    assert contents["verify"] == "VERIFY PROMPT\n"


def test_freeze_pins_sealed_hash(tmp_path):
    spec = parse_spec_text(_spec_with_prompts(tmp_path))
    frozen = yaml.safe_load(freeze_spec(spec))
    expected = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes={
            "model": prompt_sha256(b"MODEL PROMPT\n"),
            "analyze": prompt_sha256(b"ANALYZE PROMPT\n"),
            "verify": prompt_sha256(b"VERIFY PROMPT\n"),
        },
    )
    assert frozen["agent"]["sealed_hash"] == expected


def test_freeze_is_idempotent_on_already_frozen_prompts(tmp_path):
    """§3.1: re-freezing produces identical output."""
    spec_text = _spec_with_prompts(tmp_path)
    once = freeze_spec(parse_spec_text(spec_text))
    twice = freeze_spec(parse_spec_text(once))
    assert once == twice
