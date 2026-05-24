# ABOUTME: Typed plugin_args model contributed by razorback-plugin-dab.
# ABOUTME: Registered on the `razorback.plugin_args` entry-point group as 'dab'.

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DabPluginArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_variant: Literal["direct-minimal", "direct-structured", "spacedock"] = "direct-minimal"
    query_mode: Literal["batch", "per-query"] = "per-query"
    hints: bool = False
    data_root: Path | None = None
