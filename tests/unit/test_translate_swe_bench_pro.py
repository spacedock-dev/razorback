# tests/unit/test_translate_swe_bench_pro.py
# ABOUTME: AC-1/AC-2 — swe-bench-pro kind:harbor wiring through the generic materializer.
# ABOUTME: Fixture-backed, network-free via the _resolve_harbor_dataset_tasks monkeypatch seam.
from razorback.translate import _is_swe_bench_pro_dataset


def test_detects_swe_bench_pro_fully_qualified():
    # Spec datasets with plugin=None must be fully qualified <org>/<name>@<ref>
    # (spec/schema.py:209-232). PackageReference.parse rejects the bare short
    # form, so only the qualified form is a valid spec dataset.
    assert _is_swe_bench_pro_dataset("scale-ai/swe-bench-pro@latest") is True


def test_rejects_non_swe_dataset():
    assert _is_swe_bench_pro_dataset("adyen/dabstep@latest") is False
    assert _is_swe_bench_pro_dataset("spider2-dbt/spider2-dbt@1.0") is False


def test_rejects_unparseable_bare_form():
    # The bare `swe-bench-pro@latest` form is the `harbor download` CLI concept,
    # NOT a valid spec dataset ref — PackageReference.parse raises on it, and
    # the helper swallows the error and returns False. Verified at plan time.
    assert _is_swe_bench_pro_dataset("swe-bench-pro@latest") is False
