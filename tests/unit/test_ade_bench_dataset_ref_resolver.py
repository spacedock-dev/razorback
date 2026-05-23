# ABOUTME: RED tests for gb dataset-ref resolver against Harbor's PackageDatasetClient.
# ABOUTME: Uses fake_dataset fixture matching Harbor's flat <output_dir>/<package-name>/ layout.

from __future__ import annotations

from pathlib import Path

import pytest

from razorback.errors import SpecError


FAKE_DATASET = Path(__file__).parent.parent / "fixtures" / "ade_bench" / "fake_dataset"


def test_parse_dataset_ref_basic():
    from razorback.benchmarks.ade_bench.dataset_ref import parse_dataset_ref

    assert parse_dataset_ref("dbt-labs/ade-bench@latest") == (
        "dbt-labs",
        "ade-bench",
        "latest",
    )
    assert parse_dataset_ref("harbor/ade-bench@1.0") == (
        "harbor",
        "ade-bench",
        "1.0",
    )


def test_parse_dataset_ref_rejects_bare_name_with_canonical_example():
    from razorback.benchmarks.ade_bench.dataset_ref import parse_dataset_ref

    with pytest.raises(SpecError) as exc:
        parse_dataset_ref("ade-bench@1.0")
    msg = str(exc.value)
    assert "<org>/<name>@<ref>" in msg
    assert "dbt-labs/ade-bench@latest" in msg


def test_parse_dataset_ref_rejects_missing_ref():
    from razorback.benchmarks.ade_bench.dataset_ref import parse_dataset_ref

    with pytest.raises(SpecError) as exc:
        parse_dataset_ref("dbt-labs/ade-bench")
    msg = str(exc.value)
    assert "<org>/<name>@<ref>" in msg
    assert "dbt-labs/ade-bench@latest" in msg


def test_parse_dataset_ref_rejects_missing_name():
    from razorback.benchmarks.ade_bench.dataset_ref import parse_dataset_ref

    with pytest.raises(SpecError) as exc:
        parse_dataset_ref("@1.0")
    assert "<org>/<name>@<ref>" in str(exc.value)


def _fake_download_dataset_result():
    """Return the shape PackageDatasetClient.download_dataset emits for our fixture."""
    from harbor.models.task.id import PackageTaskId
    from harbor.registry.client.base import DownloadedDatasetItem

    return [
        DownloadedDatasetItem(
            id=PackageTaskId(
                org="dbt-labs",
                name="ade-bench-airbnb001",
                ref="sha256:a" * 64,
            ),
            downloaded_path=FAKE_DATASET / "ade-bench-airbnb001",
        ),
        DownloadedDatasetItem(
            id=PackageTaskId(
                org="dbt-labs",
                name="ade-bench-airbnb002",
                ref="sha256:b" * 64,
            ),
            downloaded_path=FAKE_DATASET / "ade-bench-airbnb002",
        ),
    ]


def _fake_dataset_metadata():
    from harbor.models.task.id import PackageTaskId
    from harbor.registry.client.base import DatasetMetadata

    return DatasetMetadata(
        name="dbt-labs/ade-bench",
        version="sha256:" + "c" * 64,
        description="",
        task_ids=[
            PackageTaskId(
                org="dbt-labs",
                name="ade-bench-airbnb001",
                ref="sha256:a" * 64,
            ),
            PackageTaskId(
                org="dbt-labs",
                name="ade-bench-airbnb002",
                ref="sha256:b" * 64,
            ),
        ],
        metrics=[],
        files=[],
        dataset_version_id="dvid-xyz",
        dataset_version_content_hash="c" * 64,
    )


def _install_dataset_client_stub(monkeypatch, *, items=None, metadata=None, raises=None):
    """Patch PackageDatasetClient.download_dataset (and get_dataset_metadata) on the module
    razorback.benchmarks.ade_bench.dataset_ref imports it from."""
    from razorback.benchmarks.ade_bench import dataset_ref as dr

    captured = {"calls": []}

    async def fake_download(self, name, overwrite=False, output_dir=None, export=False, **kwargs):
        captured["calls"].append(
            {"name": name, "overwrite": overwrite, "output_dir": output_dir, "export": export}
        )
        if raises is not None:
            raise raises
        return items if items is not None else _fake_download_dataset_result()

    async def fake_metadata(self, name):
        if raises is not None:
            raise raises
        return metadata if metadata is not None else _fake_dataset_metadata()

    monkeypatch.setattr(dr.PackageDatasetClient, "download_dataset", fake_download)
    monkeypatch.setattr(dr.PackageDatasetClient, "get_dataset_metadata", fake_metadata)
    return captured


def test_resolve_dataset_tasks_invokes_package_dataset_client(tmp_path, monkeypatch):
    from razorback.benchmarks.ade_bench.dataset_ref import resolve_dataset_tasks

    captured = _install_dataset_client_stub(monkeypatch)

    resolved = resolve_dataset_tasks(
        dataset_ref="dbt-labs/ade-bench@latest",
        tasks=None,
        cache_root=tmp_path,
    )

    assert len(captured["calls"]) == 1
    call = captured["calls"][0]
    assert call["name"] == "dbt-labs/ade-bench@latest"
    assert call["export"] is True
    assert call["output_dir"] == tmp_path

    assert len(resolved) == 2
    slugs = {r.task_slug for r in resolved}
    assert slugs == {"ade-bench-airbnb001", "ade-bench-airbnb002"}
    for r in resolved:
        assert r.path.is_dir()
        assert (r.path / "task.toml").is_file()
        assert r.content_hash and r.content_hash.startswith("sha256:")


def test_resolve_dataset_tasks_records_dataset_content_hash(tmp_path, monkeypatch):
    from razorback.benchmarks.ade_bench.dataset_ref import resolve_dataset_tasks

    _install_dataset_client_stub(monkeypatch)
    resolved = resolve_dataset_tasks(
        dataset_ref="dbt-labs/ade-bench@latest",
        tasks=None,
        cache_root=tmp_path,
    )
    # Every resolved task carries the dataset-level content hash.
    for r in resolved:
        assert r.dataset_content_hash == "c" * 64


def test_resolve_dataset_tasks_subset_by_stripped_suffix(tmp_path, monkeypatch):
    from razorback.benchmarks.ade_bench.dataset_ref import resolve_dataset_tasks

    _install_dataset_client_stub(monkeypatch)

    resolved = resolve_dataset_tasks(
        dataset_ref="dbt-labs/ade-bench@latest",
        tasks=["airbnb001"],
        cache_root=tmp_path,
    )

    assert len(resolved) == 1
    assert resolved[0].task_slug == "ade-bench-airbnb001"
    assert resolved[0].requested_slug == "airbnb001"


def test_resolve_dataset_tasks_missing_subset_lists_available(tmp_path, monkeypatch):
    from razorback.benchmarks.ade_bench.dataset_ref import resolve_dataset_tasks

    _install_dataset_client_stub(monkeypatch)

    with pytest.raises(SpecError) as exc:
        resolve_dataset_tasks(
            dataset_ref="dbt-labs/ade-bench@latest",
            tasks=["airbnb_nope"],
            cache_root=tmp_path,
        )
    msg = str(exc.value)
    assert "dbt-labs/ade-bench@latest" in msg
    assert "airbnb_nope" in msg
    # The error must list what IS available so the operator can self-correct.
    assert "ade-bench-airbnb001" in msg or "airbnb001" in msg


def test_resolve_dataset_tasks_client_failure_wraps(tmp_path, monkeypatch):
    from razorback.benchmarks.ade_bench.dataset_ref import resolve_dataset_tasks

    _install_dataset_client_stub(monkeypatch, raises=RuntimeError("registry 503"))

    with pytest.raises(SpecError) as exc:
        resolve_dataset_tasks(
            dataset_ref="dbt-labs/ade-bench@latest",
            tasks=None,
            cache_root=tmp_path,
        )
    msg = str(exc.value)
    assert "dbt-labs/ade-bench@latest" in msg
    assert "registry 503" in msg
