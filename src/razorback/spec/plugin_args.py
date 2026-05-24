# ABOUTME: PluginArgsRegistry — discovers typed Pydantic args models contributed by
# ABOUTME: razorback plugins via the `razorback.plugin_args` entry-point group.

from __future__ import annotations

import importlib.metadata
from typing import Type

from pydantic import BaseModel


_PLUGIN_ARGS_GROUP = "razorback.plugin_args"


class PluginNotFoundError(LookupError):
    """Raised when a plugin name is not registered on `razorback.plugin_args`."""


class PluginArgsRegistry:
    """Resolves plugin names to their typed args Pydantic models.

    Each plugin contributes a single `BaseModel` subclass via the
    `razorback.plugin_args` entry-point group. `HarborBenchmarkBlock`'s
    `model_validator` uses the registry to re-parse `plugin_args` against
    the plugin's own schema at spec validation time.
    """

    def __init__(self) -> None:
        self._cache: dict[str, Type[BaseModel]] = {}

    def known_plugins(self) -> list[str]:
        return sorted({ep.name for ep in importlib.metadata.entry_points(group=_PLUGIN_ARGS_GROUP)})

    def get(self, plugin_name: str) -> Type[BaseModel]:
        cached = self._cache.get(plugin_name)
        if cached is not None:
            return cached
        for ep in importlib.metadata.entry_points(group=_PLUGIN_ARGS_GROUP):
            if ep.name != plugin_name:
                continue
            loaded = ep.load()
            if not isinstance(loaded, type) or not issubclass(loaded, BaseModel):
                raise TypeError(
                    f"razorback.plugin_args entry-point {plugin_name!r} resolved to "
                    f"{loaded!r}, which is not a pydantic.BaseModel subclass"
                )
            self._cache[plugin_name] = loaded
            return loaded
        known = self.known_plugins()
        raise PluginNotFoundError(
            f"no razorback plugin registered as {plugin_name!r}; "
            f"known plugins (group=razorback.plugin_args): {known!r}"
        )


_DEFAULT_REGISTRY = PluginArgsRegistry()


def get_plugin_args_model(plugin_name: str) -> Type[BaseModel]:
    """Module-level convenience over the default registry."""
    return _DEFAULT_REGISTRY.get(plugin_name)
