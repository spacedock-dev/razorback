# ABOUTME: Tests for razorback.spec.plugin_args registry — entry-point discovery
# ABOUTME: + typed re-parsing of HarborBenchmarkBlock.plugin_args via the plugin's Pydantic model.

import importlib.metadata

import pytest
from pydantic import ValidationError

from razorback.spec.plugin_args import (
    PluginArgsRegistry,
    get_plugin_args_model,
)


def test_registry_discovers_dab_plugin_via_entry_point():
    """`razorback.plugin_args` entry-point group resolves a `dab` name."""
    eps = importlib.metadata.entry_points(group="razorback.plugin_args")
    names = {ep.name for ep in eps}
    assert "dab" in names, (
        f"expected 'dab' in razorback.plugin_args entry-point group; got {names!r}"
    )


def test_get_plugin_args_model_returns_pydantic_class_for_dab():
    from pydantic import BaseModel

    model_cls = get_plugin_args_model("dab")
    assert isinstance(model_cls, type)
    assert issubclass(model_cls, BaseModel)


def test_dab_plugin_args_model_validates_workspace_variant_literal():
    """The dab-plugin's typed args reject bad workspace_variant values."""
    model_cls = get_plugin_args_model("dab")
    # Good
    instance = model_cls(workspace_variant="direct-structured", query_mode="per-query")
    assert instance.workspace_variant == "direct-structured"
    # Bad — Literal validation must reject
    with pytest.raises(ValidationError):
        model_cls(workspace_variant="ad-hoc")


def test_dab_plugin_args_model_validates_query_mode_literal():
    model_cls = get_plugin_args_model("dab")
    instance = model_cls(query_mode="batch")
    assert instance.query_mode == "batch"
    with pytest.raises(ValidationError):
        model_cls(query_mode="per-querie")  # typo


def test_get_plugin_args_model_raises_on_unknown_plugin_name():
    from razorback.spec.plugin_args import PluginNotFoundError

    with pytest.raises(PluginNotFoundError) as exc:
        get_plugin_args_model("nonexistent-plugin")
    assert "nonexistent-plugin" in str(exc.value)


def test_registry_caches_resolution():
    """Two calls return the same class object (entry-point loader runs once)."""
    a = get_plugin_args_model("dab")
    b = get_plugin_args_model("dab")
    assert a is b


def test_registry_class_lists_known_plugins():
    """PluginArgsRegistry.known_plugins() returns the discovered entry-point names."""
    registry = PluginArgsRegistry()
    known = registry.known_plugins()
    assert "dab" in known
