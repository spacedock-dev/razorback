# ABOUTME: Pins leak-guard prose into every workspace_variant.
# ABOUTME: Any future edit that drops the forbidden-list phrases turns this RED.

import pytest

from razorback_plugin_dab.generate.workspace_readme import (
    WORKSPACE_VARIANTS,
    render_workspace_readme,
)


LEAK_GUARD_PHRASES = (
    "Use only the workspace data",
    "HuggingFace",
    "datasets.load_dataset",
    "hf://",
    "Public CSV",
    "Web search engines",
    "UNABLE TO DETERMINE",
)


@pytest.mark.parametrize("variant", WORKSPACE_VARIANTS)
@pytest.mark.parametrize("phrase", LEAK_GUARD_PHRASES)
def test_variant_carries_leak_guard_phrase(variant: str, phrase: str) -> None:
    text = render_workspace_readme(variant=variant, container_workdir="/workspace")
    assert phrase in text, (
        f"variant={variant!r} missing leak-guard phrase {phrase!r}"
    )
