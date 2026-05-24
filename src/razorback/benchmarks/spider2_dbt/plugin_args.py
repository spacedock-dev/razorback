# ABOUTME: Typed plugin_args model contributed by the in-tree spider2-dbt plugin.
# ABOUTME: Registered on the `razorback.plugin_args` entry-point group as 'spider2'.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Spider2PluginArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    docker_image_override: str | None = None
    batch_mode: Literal["per-task", "shared-context"] = "per-task"
