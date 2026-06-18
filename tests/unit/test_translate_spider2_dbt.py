# ABOUTME: Translator coverage for the spider2-dbt kind:harbor branch in _build_harbor.
# ABOUTME: Family detect, filter-then-materialize, leakage-clean views, benchmark env (AC-1/AC-2).
from razorback.translate import _is_spider2_dbt_dataset


def test_detects_spider2_dbt_fully_qualified():
    # Spec datasets with plugin=None must be fully qualified <org>/<name>@<ref>
    # (spec/schema.py:209-226). PackageReference.parse rejects the bare short
    # form, so only the qualified form is a valid spec dataset.
    assert _is_spider2_dbt_dataset("spider2-dbt/spider2-dbt@1.0") is True


def test_rejects_non_spider2_dataset():
    assert _is_spider2_dbt_dataset("adyen/dabstep@latest") is False


def test_rejects_unparseable_short_form():
    # The bare `spider2-dbt@1.0` form is the `harbor download` CLI concept,
    # NOT a valid spec dataset ref — PackageReference.parse raises on it, and
    # the helper swallows the error and returns False. Verified at plan time.
    assert _is_spider2_dbt_dataset("spider2-dbt@1.0") is False
