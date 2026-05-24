# ABOUTME: Unit tests for the plugin-backed DAB extension of the spec schema.
# ABOUTME: Active input shape: kind: harbor + plugin: dab + plugin_args.

from pathlib import Path

import pytest

from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text


VALID_DAB_SPEC = """\
version: 1
experiment: m2-bookreview-nop
agent:
  kind: nop
benchmark:
  kind: harbor
  dataset: dab@1.0
  plugin: dab
  plugin_args:
    data_root: /Users/clkao/git/dataagentbench/data
  tasks:
    - bookreview
trials: 1
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
"""


def test_parses_dab_plugin_benchmark_block():
    spec = parse_spec_text(VALID_DAB_SPEC)
    assert spec.benchmark.kind == "harbor"
    assert spec.benchmark.plugin == "dab"
    assert spec.benchmark.dataset == "dab@1.0"
    assert spec.benchmark.tasks == ["bookreview"]
    assert spec.benchmark.plugin_args["data_root"] == "/Users/clkao/git/dataagentbench/data"


def test_dab_plugin_args_data_root_env_default_string_passthrough():
    """plugin_args is a free-form dict at parse time (re-parsed against the
    plugin's typed model); env defaults stay as strings, the plugin owns
    expansion at generate-time."""
    spec = parse_spec_text(
        VALID_DAB_SPEC.replace(
            "/Users/clkao/git/dataagentbench/data",
            "${DATAAGENTBENCH_DATA_ROOT:-~/dataagentbench/data}",
        )
    )
    assert "${DATAAGENTBENCH_DATA_ROOT" in str(spec.benchmark.plugin_args["data_root"])


def test_dab_plugin_rejects_unknown_top_level_subkey():
    bad = VALID_DAB_SPEC + "  task_paths: [a]\n"
    with pytest.raises(SpecError):
        parse_spec_text(bad)


def test_dab_plugin_rejects_unknown_plugin_arg():
    bad = VALID_DAB_SPEC.replace(
        "  plugin_args:\n    data_root: /Users/clkao/git/dataagentbench/data\n",
        "  plugin_args:\n    data_root: /tmp\n    ad_hoc_field: true\n",
    )
    with pytest.raises(SpecError):
        parse_spec_text(bad)


def test_local_benchmark_still_parses():
    """Negative correlate: M1 specs (kind: local) keep parsing unchanged."""
    spec = parse_spec_text(
        "version: 1\n"
        "experiment: m1\n"
        "agent:\n  kind: nop\n"
        "benchmark:\n  kind: local\n  task_paths: [examples/tasks/hello-world]\n"
    )
    assert spec.benchmark.kind == "local"
    assert [str(p) for p in spec.benchmark.task_paths] == ["examples/tasks/hello-world"]


def test_legacy_harbor_dab_kind_is_rejected():
    """Post-migration: `kind: harbor_dab` is no longer a valid kind."""
    bad = VALID_DAB_SPEC.replace("kind: harbor\n", "kind: harbor_dab\n")
    with pytest.raises(SpecError) as exc_info:
        parse_spec_text(bad)
    msg = str(exc_info.value)
    assert "harbor_dab" in msg or "Input tag" in msg
