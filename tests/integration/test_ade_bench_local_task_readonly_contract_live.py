# ABOUTME: PKG-19 AC-3 live — agent container cannot mutate bind-mounted
# ABOUTME: ade-bench-root sources; observes EROFS or equivalent. Validation stage wires this.

import os
import shutil

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None or os.environ.get("CI") == "true",
    reason="requires local docker; skipped on CI",
)


def test_agent_container_cannot_mutate_ade_bench_root() -> None:
    """AC-3 live: the agent's bind-mount of the materialized view-dir + any
    symlinked ade_bench_root paths must reject mutation attempts.

    Full wiring (docker compose up against a synthesized task + exec mutation
    probes) lands in the validation stage after the captain frees disk and
    exports `CLAUDE_CODE_OAUTH_TOKEN`. Structural T6 covers the unit-level
    contract (no RW mounts injected by the synthesized task.toml).
    """
    pytest.skip(
        "Full live wiring lands in validation stage; structural T6 covers the "
        "unit-level contract."
    )
