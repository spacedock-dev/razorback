# ABOUTME: Unit tests for the DAB extension of the spec schema.
# ABOUTME: AC-7 input shape: kind: dab, data_root: Path, datasets: list[str].

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
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets:
    - bookreview
trials: 1
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
"""


def test_parses_dab_benchmark_block():
    spec = parse_spec_text(VALID_DAB_SPEC)
    assert spec.benchmark.kind == "dab"
    assert str(spec.benchmark.data_root) == "/Users/clkao/git/dataagentbench/data"
    assert spec.benchmark.datasets == ["bookreview"]


def test_dab_data_root_expands_env_default(monkeypatch):
    monkeypatch.delenv("DATAAGENTBENCH_DATA_ROOT", raising=False)
    spec = parse_spec_text(
        VALID_DAB_SPEC.replace(
            "/Users/clkao/git/dataagentbench/data",
            '"${DATAAGENTBENCH_DATA_ROOT:-~/dataagentbench/data}"',
        )
    )
    assert spec.benchmark.data_root == Path.home() / "dataagentbench" / "data"


def test_dab_data_root_expands_env_override(tmp_path, monkeypatch):
    data_root = tmp_path / "dab-data"
    monkeypatch.setenv("DATAAGENTBENCH_DATA_ROOT", str(data_root))
    spec = parse_spec_text(
        VALID_DAB_SPEC.replace(
            "/Users/clkao/git/dataagentbench/data",
            '"${DATAAGENTBENCH_DATA_ROOT:-~/dataagentbench/data}"',
        )
    )
    assert spec.benchmark.data_root == data_root


def test_dab_rejects_unknown_subkey():
    bad = VALID_DAB_SPEC + "  task_paths: [a]\n"
    with pytest.raises(SpecError):
        parse_spec_text(bad)


def test_dab_requires_datasets():
    bad = VALID_DAB_SPEC.replace("  datasets:\n    - bookreview\n", "")
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
