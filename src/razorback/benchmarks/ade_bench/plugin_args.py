# ABOUTME: Typed plugin_args model contributed by the in-tree ade-bench plugin.
# ABOUTME: Registered on the `razorback.plugin_args` entry-point group as 'ade-bench'.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class AdeBenchPluginArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    docker_image_override: str | None = None
    batch_mode: Literal["per-task", "shared-context"] = "per-task"
    db_type: Literal["duckdb", "snowflake"] | None = None
    project_type: Literal["dbt", "dbt-fusion"] | None = None
