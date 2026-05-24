# ABOUTME: HarborBenchmarkBlock.plugin + plugin_args — registry-validated typed args.
# ABOUTME: A bad plugin_args value (typo, wrong type) raises ValidationError via the plugin's model.

import pytest
from pydantic import ValidationError

from razorback.spec.schema import (
    HarborBenchmarkBlock,
    HarborLocalBenchmarkBlock,
    NopAgentBlock,
    Spec,
)


# ---- HarborBenchmarkBlock.plugin + plugin_args ----------------------------

def test_harbor_block_accepts_plugin_dab_with_typed_args():
    block = HarborBenchmarkBlock(
        kind="harbor",
        dataset="dab@1.0",
        plugin="dab",
        plugin_args={
            "workspace_variant": "direct-structured",
            "query_mode": "per-query",
            "hints": False,
        },
    )
    assert block.plugin == "dab"
    assert block.plugin_args["workspace_variant"] == "direct-structured"


def test_harbor_block_rejects_bad_workspace_variant_via_plugin_model():
    """Bad plugin_args values trip the plugin's typed model (Literal)."""
    with pytest.raises(ValidationError) as exc:
        HarborBenchmarkBlock(
            kind="harbor",
            dataset="dab@1.0",
            plugin="dab",
            plugin_args={"workspace_variant": "ad-hoc"},
        )
    msg = str(exc.value)
    assert "workspace_variant" in msg or "ad-hoc" in msg


def test_harbor_block_rejects_bad_query_mode_via_plugin_model():
    with pytest.raises(ValidationError) as exc:
        HarborBenchmarkBlock(
            kind="harbor",
            dataset="dab@1.0",
            plugin="dab",
            plugin_args={"query_mode": "per-querie"},
        )
    msg = str(exc.value)
    assert "query_mode" in msg or "per-querie" in msg


def test_harbor_block_rejects_unknown_plugin_name():
    with pytest.raises(ValidationError) as exc:
        HarborBenchmarkBlock(
            kind="harbor",
            dataset="adyen/dabstep@latest",
            plugin="no-such-plugin",
        )
    msg = str(exc.value)
    assert "no-such-plugin" in msg


def test_harbor_block_without_plugin_accepts_no_plugin_args():
    block = HarborBenchmarkBlock(
        kind="harbor",
        dataset="adyen/dabstep@latest",
    )
    assert block.plugin is None
    assert block.plugin_args is None


def test_harbor_block_rejects_plugin_args_without_plugin_name():
    """Providing plugin_args without plugin should fail — args belong to a named plugin."""
    with pytest.raises(ValidationError) as exc:
        HarborBenchmarkBlock(
            kind="harbor",
            dataset="adyen/dabstep@latest",
            plugin_args={"workspace_variant": "direct-minimal"},
        )
    msg = str(exc.value)
    assert "plugin" in msg


def test_dab_plugin_uses_short_dataset_ref():
    """DAB's plugin-resolved dataset can use the short '<name>@<version>' form
    since registry resolution goes through the plugin, not PackageDatasetClient."""
    block = HarborBenchmarkBlock(
        kind="harbor",
        dataset="dab@1.0",
        plugin="dab",
        plugin_args={"workspace_variant": "direct-minimal"},
    )
    assert block.dataset == "dab@1.0"


def test_non_plugin_dataset_still_requires_org_slash_name_at_ref():
    """When plugin is None, dataset must be `<org>/<name>@<ref>` for registry resolution."""
    with pytest.raises(ValidationError):
        HarborBenchmarkBlock(
            kind="harbor",
            dataset="dabstep@1.0",  # missing org/
        )


# ---- HarborLocalBenchmarkBlock --------------------------------------------

def test_harbor_local_block_parses_with_tasks_root_and_tasks():
    block = HarborLocalBenchmarkBlock(
        kind="harbor-local",
        tasks_root="/tmp/my-dev-tasks",
        tasks=["my-dev-task-001", "my-dev-task-002"],
    )
    assert str(block.tasks_root).endswith("my-dev-tasks")
    assert block.tasks == ["my-dev-task-001", "my-dev-task-002"]


def test_harbor_local_requires_non_empty_tasks():
    with pytest.raises(ValidationError):
        HarborLocalBenchmarkBlock(
            kind="harbor-local",
            tasks_root="/tmp/tasks",
            tasks=[],
        )


def test_harbor_local_rejects_extra_fields():
    with pytest.raises(ValidationError):
        HarborLocalBenchmarkBlock(
            kind="harbor-local",
            tasks_root="/tmp/tasks",
            tasks=["t"],
            dataset="adyen/dabstep@latest",  # ← belongs on `kind: harbor`, not harbor-local
        )


def test_spec_dispatches_to_harbor_local_via_discriminator():
    spec = Spec(
        version=1,
        experiment="x",
        agent=NopAgentBlock(kind="nop"),
        benchmark={
            "kind": "harbor-local",
            "tasks_root": "/tmp/local-harbor",
            "tasks": ["my-task"],
        },
    )
    assert isinstance(spec.benchmark, HarborLocalBenchmarkBlock)
