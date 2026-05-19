# ABOUTME: Unit tests for the M1 frozen-spec writer.
# ABOUTME: M1 freeze is a faithful echo plus razorback's envelope; no provenance yet.

import yaml

from razorback.spec.freeze import freeze_spec
from razorback.spec.parse import parse_spec_text


SPEC = """\
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
  - kind: stdout
"""


def test_freeze_round_trips_input_keys():
    spec = parse_spec_text(SPEC)
    frozen_text = freeze_spec(spec)
    frozen = yaml.safe_load(frozen_text)
    assert frozen["version"] == 1
    assert frozen["experiment"] == "m1-nop"
    assert frozen["agent"]["kind"] == "nop"
    assert frozen["benchmark"]["kind"] == "local"
    assert frozen["benchmark"]["task_paths"] == ["examples/tasks/hello-world"]
    assert frozen["trials"] == 1
    assert frozen["observers"] == [{"kind": "stdout", "path": None}]


def test_freeze_is_deterministic():
    spec = parse_spec_text(SPEC)
    assert freeze_spec(spec) == freeze_spec(spec)
