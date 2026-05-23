# ABOUTME: AC-3 — Goal 1 generator emits cells matching the dataset definition.
# ABOUTME: Uses a 2x2 fixture instead of the production 3x12 to keep the test fast.

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


def test_generator_emits_cell_per_variant_dataset_from_fixture(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_def = load_definition_from(FIXTURE)

    monkeypatch.setattr(
        "razorback_plugin_dab.dataset_def.load_default_definition",
        lambda: fixture_def,
    )

    # The generator imports load_default_definition into its own module-global
    # namespace via runpy; patching the source module is not enough. Patch the
    # generator's module-global symbol too via runpy init_globals.
    out_root = tmp_path / "out"
    out_root.mkdir()
    # Ensure out_root is inside whatever REPO_ROOT the generator uses by
    # passing an absolute path; the generator's `relative_to(REPO_ROOT)` will
    # fail if out_root isn't under REPO_ROOT — work around by patching print.
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", [
        "generate-dab-paper-matrix-specs.py",
        "--out-root", str(out_root),
    ])

    try:
        runpy.run_path(
            str(GENERATOR),
            run_name="__main__",
            init_globals={"load_default_definition": lambda: fixture_def},
        )
    except SystemExit as exc:
        assert exc.code == 0

    emitted = sorted(out_root.glob("*/*.yaml"))
    assert len(emitted) == 4, f"expected 2 variants x 2 datasets = 4 specs; got {len(emitted)}"

    assert {p.parent.name for p in emitted} == {"direct-minimal", "spacedock"}
    assert {p.stem for p in emitted} == {"tinyset", "smallset"}


def test_generator_emits_dataset_ref_in_each_spec(tmp_path: Path, monkeypatch) -> None:
    fixture_def = load_definition_from(FIXTURE)
    monkeypatch.setattr(
        "razorback_plugin_dab.dataset_def.load_default_definition",
        lambda: fixture_def,
    )
    out_root = tmp_path / "out"
    out_root.mkdir()
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", [
        "generate-dab-paper-matrix-specs.py", "--out-root", str(out_root),
    ])
    try:
        runpy.run_path(
            str(GENERATOR),
            run_name="__main__",
            init_globals={"load_default_definition": lambda: fixture_def},
        )
    except SystemExit:
        pass

    for spec_path in out_root.glob("*/*.yaml"):
        spec = yaml.safe_load(spec_path.read_text())
        assert spec["benchmark"]["kind"] == "harbor_dab"
        assert spec["benchmark"]["dataset"] == "dab-fixture@0.1"
        assert spec["benchmark"]["query_mode"] == "batch"
        assert spec["benchmark"]["workspace_variant"] in {"direct-minimal", "spacedock"}
