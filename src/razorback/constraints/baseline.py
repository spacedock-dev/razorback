# ABOUTME: Baseline promote/verify (§3.2).
# ABOUTME: promote copies frozen spec, summary, per-dataset scores (via summary), provenance; verifies constraints.

import shutil
from pathlib import Path

import yaml

from razorback.constraints.check import check_spec_against_constraints
from razorback.errors import RazorbackError


_REQUIRED_ARTIFACTS = ("spec.frozen.yaml", "summary.json", "provenance.yaml")


def promote(*, run_dir: Path, target: Path, constraints_path: Path) -> None:
    """Copy the four artifacts plus the constraints file into a baseline directory,
    then verify the frozen spec satisfies the constraints (§3.2).

    The four artifacts:
      - spec.frozen.yaml   (the frozen spec; M5 contract)
      - summary.json       (the aggregated stratified pass@1 + per-dataset scores; M2)
      - provenance.yaml    (M5 resolved-version + alias-drift surface)
      - constraints.yaml   (the constraints file the baseline is bound to; M6)
    """
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    for name in _REQUIRED_ARTIFACTS:
        src = Path(run_dir) / name
        if not src.exists():
            raise RazorbackError(f"run-dir missing artifact {name}")
        shutil.copyfile(src, target / name)
    shutil.copyfile(constraints_path, target / "constraints.yaml")
    spec = yaml.safe_load((target / "spec.frozen.yaml").read_text())
    cons = yaml.safe_load((target / "constraints.yaml").read_text())
    check_spec_against_constraints(spec, cons)


def verify(target: Path) -> None:
    """Re-run the constraints check against the bound baseline directory."""
    target = Path(target)
    spec = yaml.safe_load((target / "spec.frozen.yaml").read_text())
    cons = yaml.safe_load((target / "constraints.yaml").read_text())
    check_spec_against_constraints(spec, cons)
