# ABOUTME: AdeBenchBenchmarkBlock schema — extra="forbid", discriminator dispatch, defaults.
# ABOUTME: Mirrors test_dab_spec_parse.py for the second-supported benchmark adapter.

import pytest
from pydantic import ValidationError

from razorback.spec.schema import (
    AdeBenchBenchmarkBlock,
    ClaudeCliAgentBlock,
    NopAgentBlock,
    Spec,
    Spider2DbtBenchmarkBlock,
)


def test_block_round_trip():
    block = AdeBenchBenchmarkBlock(
        kind="ade-bench",
        tasks_root="/tmp/ade-bench-tasks",
        tasks=["ade-bench-airbnb001"],
    )
    assert block.kind == "ade-bench"
    assert block.tasks == ["ade-bench-airbnb001"]


def test_block_rejects_unknown_keys():
    with pytest.raises(ValidationError) as exc:
        AdeBenchBenchmarkBlock(
            kind="ade-bench",
            tasks_root="/tmp",
            tasks=["a"],
            unknown_key="boom",
        )
    assert "extra" in str(exc.value).lower() or "unknown_key" in str(exc.value)


def test_block_rejects_empty_tasks_list():
    with pytest.raises(ValidationError):
        AdeBenchBenchmarkBlock(
            kind="ade-bench",
            tasks_root="/tmp",
            tasks=[],
        )


def test_spec_dispatches_to_ade_bench_via_discriminator():
    spec = Spec(
        version=1,
        experiment="x",
        agent=NopAgentBlock(kind="nop"),
        benchmark={
            "kind": "ade-bench",
            "tasks_root": "/tmp",
            "tasks": ["foo"],
        },
    )
    assert isinstance(spec.benchmark, AdeBenchBenchmarkBlock)


def test_spec_accepts_concurrency_block():
    spec = Spec(
        version=1,
        experiment="x",
        agent=NopAgentBlock(kind="nop"),
        benchmark={
            "kind": "ade-bench",
            "tasks_root": "/tmp",
            "tasks": ["foo"],
        },
        concurrency={"trials": 3},
    )
    assert spec.concurrency.trials == 3


def test_ade_bench_rejects_retired_local_upstream_shape():
    with pytest.raises(ValidationError) as exc:
        Spec(
            version=1,
            experiment="x",
            agent=NopAgentBlock(kind="nop"),
            benchmark={
                "kind": "ade-bench",
                "tasks_root": ".",
                "ade_bench_root": "/tmp/ade-bench",
                "tasks": [{"slug": "example001"}],
            },
        )
    message = str(exc.value)
    assert "ade_bench_root" in message
    assert "slug" in message


def test_spider2_dbt_schema_defaults():
    block = Spider2DbtBenchmarkBlock(
        kind="spider2-dbt",
        tasks_root="/tmp/spider2",
        tasks=["airport001"],
    )
    assert block.kind == "spider2-dbt"
    assert block.batch_mode == "per-task"


def test_claude_agent_tools_allowed_defaults_empty():
    agent = ClaudeCliAgentBlock(kind="claude-cli")
    assert agent.tools_allowed == []


def test_claude_agent_tools_allowed_accepts_list():
    agent = ClaudeCliAgentBlock(kind="claude-cli", tools_allowed=["bash", "edit"])
    assert agent.tools_allowed == ["bash", "edit"]
