# ABOUTME: Constraints file pydantic shape.
# ABOUTME: pinned: dotted-path -> expected value; mutation_surfaces: dotted-path prefixes.

from pydantic import BaseModel, ConfigDict, Field


class ConstraintsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    pinned: dict[str, object] = Field(default_factory=dict)
    mutation_surfaces: list[str] = Field(default_factory=list)
