# ABOUTME: Unit tests for the single-writer event channel and observers (§6.6).
# ABOUTME: Concurrent producers serialize through the drainer without interleaving.

import asyncio
import json

import pytest

from razorback.observers.channel import EventChannel
from razorback.observers.jsonl import JsonlObserver
from razorback.observers.stdout import StdoutObserver


@pytest.mark.asyncio
async def test_drainer_serializes_concurrent_writes(colima_safe_tmp_path, capsys):
    path = colima_safe_tmp_path / "events.jsonl"
    ch = EventChannel()
    ch.add_observer(JsonlObserver(path))
    ch.add_observer(StdoutObserver())

    drain_task = asyncio.create_task(ch.drain())

    async def producer(tag: str, n: int) -> None:
        for i in range(n):
            await ch.publish({"event": tag, "i": i})

    await asyncio.gather(producer("a", 50), producer("b", 50))
    await ch.aclose()
    await drain_task

    lines = path.read_text().splitlines()
    assert len(lines) == 100
    for line in lines:
        # No partial / interleaved writes — every line parses.
        json.loads(line)
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 100


@pytest.mark.asyncio
async def test_drainer_preserves_fire_order(colima_safe_tmp_path):
    path = colima_safe_tmp_path / "events.jsonl"
    ch = EventChannel()
    ch.add_observer(JsonlObserver(path))
    drain_task = asyncio.create_task(ch.drain())

    for i in range(20):
        await ch.publish({"event": "x", "i": i})
    await ch.aclose()
    await drain_task

    seen = [json.loads(l)["i"] for l in path.read_text().splitlines()]
    assert seen == list(range(20))
