# ABOUTME: Stdout observer — prints one human-readable line per event.
# ABOUTME: Reads from the same channel as the JSONL observer (§6.6).

import sys


class StdoutObserver:
    async def on_event(self, payload: dict) -> None:
        event = payload.get("event", "?")
        trial = payload.get("trial_id", "")
        task = payload.get("task_name", "")
        sys.stdout.write(f"[{event}] trial={trial} task={task}\n")
        sys.stdout.flush()

    async def aclose(self) -> None:
        pass
