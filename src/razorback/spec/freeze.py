# ABOUTME: M1 frozen-spec writer — echoes the parsed spec deterministically.
# ABOUTME: Full provenance resolution is deferred to M5 per design §3.2 / §6.4.

import yaml

from razorback.spec.schema import Spec


def freeze_spec(spec: Spec) -> str:
    """Return the canonical YAML for a parsed spec.

    M1 freeze is a faithful echo: it serializes the pydantic model
    in field-declaration order with all defaults materialized. Sort
    keys is intentionally False — the model already pins key order.
    Deterministic output is required for sha256-based job_name (§6.7).
    """
    return yaml.safe_dump(
        spec.model_dump(mode="json"),
        sort_keys=False,
        default_flow_style=False,
    )
