# ABOUTME: AC-3 — catalog enumerates 12 DAB datasets with the expected backends.
# ABOUTME: Names and backend kinds are verified against /Users/clkao/git/dataagentbench/data/query_*/db_config.yaml.

from razorback_plugin_dab.datasets import DAB_DATASETS, by_name


def test_catalog_size():
    assert len(DAB_DATASETS) == 12


def test_catalog_names():
    expected = {
        "agnews", "bookreview", "crmarenapro", "DEPS_DEV_V1",
        "GITHUB_REPOS", "googlelocal", "music_brainz_20k",
        "PANCANCER_ATLAS", "PATENTS", "stockindex", "stockmarket",
        "yelp",
    }
    assert {d.name for d in DAB_DATASETS} == expected


def test_each_dataset_declares_backends():
    valid_backends = {"postgres", "mongo", "sqlite", "duckdb"}
    for d in DAB_DATASETS:
        assert d.backends, f"{d.name} has no backend declared"
        assert set(d.backends).issubset(valid_backends), (
            f"{d.name} declares unknown backends: {set(d.backends) - valid_backends}"
        )


def test_each_dataset_has_positive_query_count():
    for d in DAB_DATASETS:
        assert d.query_count > 0, f"{d.name} has non-positive query_count"


def test_by_name_round_trip():
    assert by_name("bookreview").backends == ("postgres", "sqlite")
    assert by_name("agnews").backends == ("mongo", "sqlite")


def test_by_name_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        by_name("does-not-exist")
