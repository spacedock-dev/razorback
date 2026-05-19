# ABOUTME: Unit test for content-derived job_name (§6.7).
# ABOUTME: job_name = sha256(frozen-spec-bytes)[:16].

import hashlib

from razorback.spec.freeze import derive_job_name, freeze_spec
from razorback.spec.parse import parse_spec_text


SPEC = """\
version: 1
experiment: m1-nop
agent:
  kind: nop
benchmark:
  kind: local
"""


def test_job_name_is_sha256_prefix_of_frozen_text():
    spec = parse_spec_text(SPEC)
    frozen = freeze_spec(spec)
    expected = hashlib.sha256(frozen.encode("utf-8")).hexdigest()[:16]
    assert derive_job_name(frozen) == expected
    assert len(derive_job_name(frozen)) == 16


def test_different_specs_produce_different_job_names():
    spec_a = parse_spec_text(SPEC)
    spec_b = parse_spec_text(SPEC.replace("m1-nop", "m1-nop-2"))
    assert derive_job_name(freeze_spec(spec_a)) != derive_job_name(freeze_spec(spec_b))
