# ABOUTME: AC-2 + AC-5 freeze-smoke for ade-bench dataset-ref path; no live network.
# ABOUTME: Patches PackageDatasetClient; asserts view_manifest carries dataset_ref + both hashes;
# ABOUTME: codifies the AC-5 "no submodule" invariant via in-test `git submodule status`.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
FAKE_DATASET = REPO_ROOT / "tests" / "fixtures" / "ade_bench" / "fake_dataset"
CANONICAL_SPEC = REPO_ROOT / "examples" / "specs" / "ade-bench-harbor-dataset-codex.yaml"


@pytest.fixture
def patched_dataset_client(monkeypatch):
    """Patch PackageDatasetClient where the resolver imports it."""
    from harbor.models.task.id import PackageTaskId
    from harbor.registry.client.base import DatasetMetadata, DownloadedDatasetItem

    metadata = DatasetMetadata(
        name="dbt-labs/ade-bench",
        version="sha256:" + "c" * 64,
        description="",
        task_ids=[
            PackageTaskId(
                org="dbt-labs",
                name="ade-bench-airbnb001",
                ref="sha256:" + "a" * 64,
            ),
        ],
        metrics=[],
        files=[],
        dataset_version_id="dvid-xyz",
        dataset_version_content_hash="c" * 64,
    )
    items = [
        DownloadedDatasetItem(
            id=PackageTaskId(
                org="dbt-labs",
                name="ade-bench-airbnb001",
                ref="sha256:" + "a" * 64,
            ),
            downloaded_path=FAKE_DATASET / "ade-bench-airbnb001",
        ),
    ]

    from razorback.benchmarks.ade_bench import dataset_ref as dr

    async def fake_metadata(self, name):
        return metadata

    async def fake_download(self, name, overwrite=False, output_dir=None, export=False, **kw):
        return items

    monkeypatch.setattr(dr.PackageDatasetClient, "get_dataset_metadata", fake_metadata)
    monkeypatch.setattr(dr.PackageDatasetClient, "download_dataset", fake_download)
    return {"metadata": metadata, "items": items}


def _parse_canonical_dataset_spec():
    payload = yaml.safe_load(CANONICAL_SPEC.read_text())
    # The canonical spec uses spacedock_solver_v2 + solver_workflow that may not
    # exist on every checkout; swap to nop-agent so the freeze smoke is hermetic.
    payload["agent"] = {"kind": "nop"}
    return payload


def test_canonical_dataset_ref_spec_translates_with_pinned_hashes(
    tmp_path, patched_dataset_client
):
    """AC-2: canonical dataset-ref spec materializes manifests pinning BOTH hashes."""
    from razorback.spec.schema import Spec
    from razorback.translate import spec_to_job_config

    payload = _parse_canonical_dataset_spec()
    spec = Spec.model_validate(payload)

    cfg, _ = spec_to_job_config(
        spec, job_name="freeze-smoke", jobs_dir=tmp_path, home=tmp_path / "home"
    )

    assert len(cfg.tasks) == 1
    view_dir = cfg.tasks[0].path
    manifest = json.loads((view_dir / "view_manifest.json").read_text())
    assert manifest["schema_version"] == 2
    assert manifest["dataset_ref"] == (
        "dbt-labs/ade-bench@sha256:"
        "2c1f9e6966d01b0a5de2235d1a0b64089c7eead42c85c3b7b61d0929405c2bd5"
    )
    assert manifest["dataset_content_hash"] == "c" * 64
    assert manifest["task_content_hash"] == "sha256:" + "a" * 64
    assert manifest["benchmark_kind"] == "ade-bench"
    assert manifest["benchmark_task_id"] == "airbnb001"


def test_freeze_command_writes_provenance_for_dataset_ref_spec(
    tmp_path, patched_dataset_client
):
    """Freeze CLI runs over a dataset-ref spec without calling Harbor at freeze time."""
    from razorback.provenance.freeze_cmd import freeze_command

    payload = _parse_canonical_dataset_spec()
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(payload, sort_keys=False))

    freeze_command(spec_path=spec_path, out=None, allow_missing=True)

    frozen = yaml.safe_load((tmp_path / "spec.frozen.yaml").read_text())
    assert frozen["benchmark"]["kind"] == "ade-bench"
    assert frozen["benchmark"]["dataset"] == (
        "dbt-labs/ade-bench@sha256:"
        "2c1f9e6966d01b0a5de2235d1a0b64089c7eead42c85c3b7b61d0929405c2bd5"
    )
    assert (tmp_path / "provenance.yaml").is_file()


def test_no_new_submodule_required_by_dataset_ref_path():
    """AC-5: `git submodule status` MUST not list an ade-bench / harbor-datasets submodule."""
    result = subprocess.run(
        ["git", "submodule", "status"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    stdout = result.stdout
    # Empty stdout means no submodules at all — that's the strict pass.
    if not stdout.strip():
        return
    forbidden_markers = ("ade-bench", "harbor-datasets", "ade_bench")
    for marker in forbidden_markers:
        assert marker not in stdout, (
            f"git submodule status carries forbidden marker {marker!r}:\n{stdout}"
        )
