# ABOUTME: AC-1 — DAB dataset definition parses from dataset.toml.
# ABOUTME: Verifies inventory, variant catalog, and round-trip with the 12-dataset shape.

from razorback_plugin_dab.dataset_def import (
    DabDatasetDefinition,
    load_default_definition,
)


def test_default_definition_loads():
    definition = load_default_definition()
    assert isinstance(definition, DabDatasetDefinition)
    assert definition.name == "dab"
    assert definition.version == "1.0"


def test_default_definition_has_twelve_datasets():
    definition = load_default_definition()
    names = {d.name for d in definition.datasets}
    expected = {
        "agnews", "bookreview", "crmarenapro", "DEPS_DEV_V1",
        "GITHUB_REPOS", "googlelocal", "music_brainz_20k",
        "PANCANCER_ATLAS", "PATENTS", "stockindex", "stockmarket",
        "yelp",
    }
    assert names == expected


def test_default_definition_lists_workspace_variants():
    definition = load_default_definition()
    assert set(definition.workspace_variants) == {
        "direct-minimal", "direct-structured", "spacedock",
    }


def test_bookreview_metadata_round_trip():
    definition = load_default_definition()
    ds = definition.get_dataset("bookreview")
    assert ds.backends == ("postgres", "sqlite")
    assert ds.query_count == 3
    assert ds.query_ids == (1, 2, 3)
    assert ds.schema_version == "v1"


def test_query_ids_match_query_count_for_all_datasets():
    definition = load_default_definition()
    for ds in definition.datasets:
        assert len(ds.query_ids) == ds.query_count, (
            f"{ds.name}: query_ids length {len(ds.query_ids)} != query_count {ds.query_count}"
        )
