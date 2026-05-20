# ABOUTME: AC-1 unit tests for resolve_plugin_inventory (spec §3.2 + §8.2).
# ABOUTME: Discovers harbor.agents + harbor.benchmarks + razorback.plugins entry points.

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from types import SimpleNamespace

from razorback.provenance.resolvers import resolve_plugin_inventory


def _ep(name: str, dist_name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, dist=SimpleNamespace(name=dist_name))


def _dist_factory(versions: dict[str, str]):
    def _resolve(name: str) -> SimpleNamespace:
        if name not in versions:
            raise PackageNotFoundError(name)
        return SimpleNamespace(metadata={"Name": name}, version=versions[name])
    return _resolve


def _ep_fn_factory(by_group: dict[str, list[SimpleNamespace]]):
    def _ep_fn(*, group: str):
        return by_group.get(group, [])
    return _ep_fn


def test_dab_only_environment() -> None:
    eps = {
        "harbor.benchmarks": [_ep("dab", "razorback-plugin-dab")],
    }
    dists = _dist_factory({"razorback-plugin-dab": "0.1.0"})
    out = resolve_plugin_inventory(
        entry_points_fn=_ep_fn_factory(eps), distribution_fn=dists
    )
    assert out == {
        "plugins": [
            {
                "group": "harbor.benchmarks",
                "name": "dab",
                "distribution": "razorback-plugin-dab",
                "version": "0.1.0",
            }
        ]
    }


def test_claude_code_only_environment() -> None:
    eps = {"harbor.agents": [_ep("claude_code", "harbor")]}
    dists = _dist_factory({"harbor": "0.6.6"})
    out = resolve_plugin_inventory(
        entry_points_fn=_ep_fn_factory(eps), distribution_fn=dists
    )
    assert len(out["plugins"]) == 1
    row = out["plugins"][0]
    assert row["group"] == "harbor.agents"
    assert row["name"] == "claude_code"
    assert row["distribution"] == "harbor"
    assert row["version"] == "0.6.6"


def test_both_present_sorted_by_group_then_name() -> None:
    eps = {
        "harbor.benchmarks": [_ep("dab", "razorback-plugin-dab")],
        "harbor.agents": [_ep("claude_code", "harbor")],
    }
    dists = _dist_factory({"razorback-plugin-dab": "0.1.0", "harbor": "0.6.6"})
    out = resolve_plugin_inventory(
        entry_points_fn=_ep_fn_factory(eps), distribution_fn=dists
    )
    # harbor.agents sorts before harbor.benchmarks alphabetically.
    assert [r["group"] for r in out["plugins"]] == [
        "harbor.agents",
        "harbor.benchmarks",
    ]
    assert [r["name"] for r in out["plugins"]] == ["claude_code", "dab"]


def test_returns_empty_list_for_no_groups() -> None:
    out = resolve_plugin_inventory(
        entry_points_fn=_ep_fn_factory({}), distribution_fn=_dist_factory({})
    )
    assert out == {"plugins": []}


def test_every_row_carries_group_field() -> None:
    eps = {
        "harbor.benchmarks": [_ep("dab", "razorback-plugin-dab")],
        "harbor.agents": [_ep("claude_code", "harbor")],
    }
    dists = _dist_factory({"razorback-plugin-dab": "0.1.0", "harbor": "0.6.6"})
    out = resolve_plugin_inventory(
        entry_points_fn=_ep_fn_factory(eps), distribution_fn=dists
    )
    for row in out["plugins"]:
        assert "group" in row and row["group"]


def test_distribution_lookup_failure_skipped() -> None:
    eps = {
        "harbor.benchmarks": [_ep("dab", "razorback-plugin-dab")],
        "harbor.agents": [_ep("ghost", "uninstalled-package")],
    }
    dists = _dist_factory({"razorback-plugin-dab": "0.1.0"})
    out = resolve_plugin_inventory(
        entry_points_fn=_ep_fn_factory(eps), distribution_fn=dists
    )
    assert len(out["plugins"]) == 1
    assert out["plugins"][0]["name"] == "dab"


def test_sort_is_stable_across_two_calls() -> None:
    eps = {
        "harbor.agents": [
            _ep("codex", "harbor"),
            _ep("claude_code", "harbor"),
            _ep("pi", "harbor"),
        ],
    }
    dists = _dist_factory({"harbor": "0.6.6"})
    a = resolve_plugin_inventory(
        entry_points_fn=_ep_fn_factory(eps), distribution_fn=dists
    )
    b = resolve_plugin_inventory(
        entry_points_fn=_ep_fn_factory(eps), distribution_fn=dists
    )
    assert a == b
    assert [r["name"] for r in a["plugins"]] == ["claude_code", "codex", "pi"]


def test_razorback_plugins_group_scanned() -> None:
    """Forward-compat: a razorback-side plugin registers under razorback.plugins."""
    eps = {"razorback.plugins": [_ep("fake_plugin", "razorback-side-pkg")]}
    dists = _dist_factory({"razorback-side-pkg": "1.2.3"})
    out = resolve_plugin_inventory(
        entry_points_fn=_ep_fn_factory(eps), distribution_fn=dists
    )
    assert len(out["plugins"]) == 1
    assert out["plugins"][0]["group"] == "razorback.plugins"
