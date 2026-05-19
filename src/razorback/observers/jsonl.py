# ABOUTME: JSONL observer — appends one JSON object per event to a file.
# ABOUTME: Single-writer per §6.6; the drainer is the only caller.

import json
from pathlib import Path


class JsonlObserver:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._path.open("a", buffering=1)  # line-buffered

    async def on_event(self, payload: dict) -> None:
        self._fh.write(json.dumps(payload, default=str) + "\n")

    async def aclose(self) -> None:
        self._fh.close()
