# ABOUTME: Generator tests for --reasoning-effort flag + spacedock cell shape.
# ABOUTME: Validates AC-1 of goal1-rerun-dab-spacedock-opus47-xhigh.

from __future__ import annotations

import runpy
from pathlib import Path

import yaml

from razorback_plugin_dab.dataset_def import load_definition_from


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "dab_dataset_minimal.toml"
GENERATOR = (
    Path(__file__).resolve().parents[2]
    / "examples" / "drivers" / "generate-dab-paper-matrix-specs.py"
)


def _run_generator(out_root: Path, monkeypatch, *extra_argv: str) -> None:
    fixture_def = load_definition_from(FIXTURE)
    monkeypatch.setattr(
        "razorback_plugin_dab.dataset_def.load_default_definition",
        lambda: fixture_def,
    )
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", [
        "generate-dab-paper-matrix-specs.py",
        "--out-root", str(out_root),
        *extra_argv,
    ])
    try:
        runpy.run_path(
            str(GENERATOR),
            run_name="__main__",
            init_globals={"load_default_definition": lambda: fixture_def},
        )
    except SystemExit as exc:
        assert exc.code == 0


def test_generator_default_emits_no_reasoning_effort(tmp_path: Path, monkeypatch) -> None:
    out_root = tmp_path / "out"
    out_root.mkdir()
    _run_generator(out_root, monkeypatch)

    spec_paths = list(out_root.glob("spacedock/*.yaml"))
    assert len(spec_paths) == 2, f"expected 2 spacedock specs from fixture; got {len(spec_paths)}"
    for spec_path in spec_paths:
        spec = yaml.safe_load(spec_path.read_text())
        assert "reasoning_effort" not in spec["agent"], (
            f"{spec_path}: agent block must not carry reasoning_effort by default"
        )


def test_generator_with_reasoning_effort_xhigh_injects_into_agent(
    tmp_path: Path, monkeypatch
) -> None:
    out_root = tmp_path / "out"
    out_root.mkdir()
    _run_generator(out_root, monkeypatch, "--reasoning-effort", "xhigh")

    spec_paths = list(out_root.glob("*/*.yaml"))
    assert spec_paths, "generator emitted no specs"
    for spec_path in spec_paths:
        spec = yaml.safe_load(spec_path.read_text())
        assert spec["agent"].get("reasoning_effort") == "xhigh", (
            f"{spec_path}: agent.reasoning_effort must be 'xhigh' "
            f"(got {spec['agent'].get('reasoning_effort')!r})"
        )


def test_generator_spacedock_cell_shape(tmp_path: Path, monkeypatch) -> None:
    out_root = tmp_path / "out"
    out_root.mkdir()
    _run_generator(out_root, monkeypatch, "--reasoning-effort", "xhigh")

    spec_paths = list(out_root.glob("spacedock/*.yaml"))
    assert spec_paths, "generator emitted no spacedock specs"
    for spec_path in spec_paths:
        spec = yaml.safe_load(spec_path.read_text())
        benchmark = spec["benchmark"]
        assert benchmark["kind"] == "harbor_dab"
        assert benchmark["dataset"] == "dab-fixture@0.1"
        assert benchmark["query_mode"] == "batch"
        assert benchmark["workspace_variant"] == "spacedock"
        assert "data_root" not in benchmark, (
            f"{spec_path}: legacy data_root field must not appear in regenerated spec"
        )
        assert spec["agent"]["kind"] == "spacedock_solver"
