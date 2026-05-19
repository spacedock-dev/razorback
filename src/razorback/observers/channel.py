# ABOUTME: Single-writer asyncio channel for trial events; one drainer fans out to observers.
# ABOUTME: §6.6 — concurrent direct writes to event sinks are forbidden.

import asyncio
from typing import Protocol


class Observer(Protocol):
    async def on_event(self, payload: dict) -> None: ...
    async def aclose(self) -> None: ...


class EventChannel:
    """A bounded async queue + drainer that fans out to registered observers."""

    _SENTINEL = object()

    def __init__(self, maxsize: int = 1024) -> None:
        self._q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._observers: list[Observer] = []
        self._closed = False

    def add_observer(self, observer: Observer) -> None:
        self._observers.append(observer)

    async def publish(self, payload: dict) -> None:
        if self._closed:
            raise RuntimeError("EventChannel is closed")
        await self._q.put(payload)

    async def aclose(self) -> None:
        self._closed = True
        await self._q.put(self._SENTINEL)

    async def drain(self) -> None:
        while True:
            item = await self._q.get()
            if item is self._SENTINEL:
                break
            for obs in self._observers:
                await obs.on_event(item)
        for obs in self._observers:
            await obs.aclose()
