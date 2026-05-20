# ABOUTME: AC-3: pre-launch estimate sourced from frozen spec's experiment_meta.estimated_cost_usd.

import pytest

from razorback.budget import read_estimate_from_spec
from razorback.errors import ConfigInvalidError
from razorback.spec.parse import parse_spec_text


SPEC_WITH_ESTIMATE = """
version: 1
experiment: exp-1
agent:
  kind: nop
benchmark:
  kind: local
  task_paths: []
trials: 1
experiment_meta:
  max_budget_usd: 100.0
  estimated_cost_usd: 12.5
"""

SPEC_WITHOUT_ESTIMATE = """
version: 1
experiment: exp-1
agent:
  kind: nop
benchmark:
  kind: local
  task_paths: []
trials: 1
experiment_meta:
  max_budget_usd: 100.0
"""

SPEC_WITHOUT_META = """
version: 1
experiment: exp-1
agent:
  kind: nop
benchmark:
  kind: local
  task_paths: []
trials: 1
"""


def test_estimate_reads_from_frozen_spec_field():
    spec = parse_spec_text(SPEC_WITH_ESTIMATE)
    estimate = read_estimate_from_spec(spec)
    assert estimate == pytest.approx(12.5)


def test_missing_estimate_raises_config_invalid_naming_rk_freeze():
    spec = parse_spec_text(SPEC_WITHOUT_ESTIMATE)
    with pytest.raises(ConfigInvalidError) as exc_info:
        read_estimate_from_spec(spec)
    msg = str(exc_info.value)
    assert "estimated_cost_usd" in msg
    assert "rk freeze" in msg


def test_missing_meta_block_raises_config_invalid():
    spec = parse_spec_text(SPEC_WITHOUT_META)
    with pytest.raises(ConfigInvalidError):
        read_estimate_from_spec(spec)
