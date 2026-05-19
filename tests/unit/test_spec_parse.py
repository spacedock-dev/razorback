# ABOUTME: Unit tests for the spec parser.
# ABOUTME: Covers valid M1 spec, unknown-key rejection, missing-required rejection.

import pytest

from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text


VALID_M1_SPEC = """\
version: 1
experiment: m1-nop
agent:
  kind: nop
benchmark:
  kind: local
  task_paths:
    - examples/tasks/hello-world
trials: 1
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
"""


def test_parses_valid_m1_spec():
    spec = parse_spec_text(VALID_M1_SPEC)
    assert spec.version == 1
    assert spec.experiment == "m1-nop"
    assert spec.agent.kind == "nop"
    assert spec.benchmark.kind == "local"
    assert spec.trials == 1
    assert {o.kind for o in spec.observers} == {"jsonl", "stdout"}


def test_rejects_unknown_top_level_key():
    bad = VALID_M1_SPEC + "unknown_key: foo\n"
    with pytest.raises(SpecError) as ei:
        parse_spec_text(bad)
    assert "unknown_key" in str(ei.value)


def test_rejects_missing_required_version():
    no_version = "\n".join(l for l in VALID_M1_SPEC.splitlines() if not l.startswith("version:"))
    with pytest.raises(SpecError) as ei:
        parse_spec_text(no_version)
    assert "version" in str(ei.value)
