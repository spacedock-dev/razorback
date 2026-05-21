# ABOUTME: PKG-27 generator smoke tests for Codex DAB and ade-bench matrix specs.
# ABOUTME: Keeps dry-run enumeration portable before any live Codex budget burn.

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "examples" / "drivers" / "generate-codex-benchmark-specs.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("codex_benchmark_specs", GENERATOR)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_dab_dry_run_enumerates_twelve_datasets(tmp_path: Path) -> None:
    generator = _load_generator()

    rows = generator.plan_dab_specs(data_root=tmp_path / "dab-data")

    assert len(rows) == 12
    assert [row.dataset for row in rows] == [
        "agnews",
        "bookreview",
        "crmarenapro",
        "DEPS_DEV_V1",
        "GITHUB_REPOS",
        "googlelocal",
        "music_brainz_20k",
        "PANCANCER_ATLAS",
        "PATENTS",
        "stockindex",
        "stockmarket",
        "yelp",
    ]
    assert all(row.trials == 1 for row in rows)
    assert all(row.data_root == tmp_path / "dab-data" for row in rows)


def test_ade_bench_dry_run_enumerates_discovered_local_task_slugs(tmp_path: Path) -> None:
    generator = _load_generator()
    tasks_root = tmp_path / "ade-bench" / "tasks"
    for slug in ("task_b", "task_a"):
        task_dir = tasks_root / slug
        task_dir.mkdir(parents=True)
        (task_dir / "task.yaml").write_text(f"task_id: {slug}\n")

    rows = generator.plan_ade_bench_specs(ade_bench_root=tmp_path / "ade-bench")

    assert [row.task_slug for row in rows] == ["task_a", "task_b"]
    assert all(row.trials == 1 for row in rows)
    assert all(row.ade_bench_root == tmp_path / "ade-bench" for row in rows)


def test_emit_dab_codex_spec_uses_solver_v2_codex_and_harbor_dab(tmp_path: Path) -> None:
    generator = _load_generator()
    row = generator.plan_dab_specs(data_root=tmp_path / "dab-data")[1]

    spec_path = generator.emit_dab_spec(row, out_dir=tmp_path / "out")
    payload = yaml.safe_load(spec_path.read_text())

    assert payload["agent"]["kind"] == "spacedock_solver_v2"
    assert payload["agent"]["runtime"] == "codex"
    assert payload["agent"]["model"] == "gpt-5.5"
    assert payload["agent"]["solver_workflow"] == "./examples/solver_workflows/codex-benchmark-solver"
    assert payload["benchmark"]["kind"] == "harbor_dab"
    assert payload["benchmark"]["datasets"] == ["bookreview"]
    assert payload["benchmark"]["data_root"] == str(tmp_path / "dab-data")
    assert payload["trials"] == 1


def test_emit_dab_codex_spec_allows_model_override(tmp_path: Path) -> None:
    generator = _load_generator()
    row = generator.plan_dab_specs(data_root=tmp_path / "dab-data")[0]

    spec_path = generator.emit_dab_spec(
        row, out_dir=tmp_path / "out", model="gpt-future-codex"
    )
    payload = yaml.safe_load(spec_path.read_text())

    assert payload["agent"]["model"] == "gpt-future-codex"


def test_display_path_handles_relative_and_external_out_roots(tmp_path: Path) -> None:
    generator = _load_generator()

    assert (
        generator._display_path(Path("runs/goal3/specs/dab/bookreview.yaml"))
        == "runs/goal3/specs/dab/bookreview.yaml"
    )
    assert (
        generator._display_path(
            generator.REPO_ROOT / "runs" / "goal3" / "specs" / "dab" / "agnews.yaml"
        )
        == "runs/goal3/specs/dab/agnews.yaml"
    )
    external = tmp_path / "specs" / "dab" / "agnews.yaml"
    assert generator._display_path(external) == str(external.resolve())


def test_emit_ade_bench_codex_spec_uses_local_task_entry(tmp_path: Path) -> None:
    generator = _load_generator()
    tasks_root = tmp_path / "ade-bench" / "tasks"
    task_dir = tasks_root / "example001"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text("task_id: example001\n")
    row = generator.plan_ade_bench_specs(ade_bench_root=tmp_path / "ade-bench")[0]

    spec_path = generator.emit_ade_bench_spec(row, out_dir=tmp_path / "out")
    payload = yaml.safe_load(spec_path.read_text())

    assert payload["agent"]["kind"] == "spacedock_solver_v2"
    assert payload["agent"]["runtime"] == "codex"
    assert payload["agent"]["model"] == "gpt-5.5"
    assert payload["benchmark"]["kind"] == "ade-bench"
    assert payload["benchmark"]["ade_bench_root"] == str(tmp_path / "ade-bench")
    assert payload["benchmark"]["tasks"] == [{"slug": "example001"}]
    assert payload["trials"] == 1
