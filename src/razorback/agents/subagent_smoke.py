# ABOUTME: Per-cell/run subagent-dispatch smoke validator. Exits 0/2/3 from manifest.
# ABOUTME: Used by examples/drivers/dab-paper-matrix.sh to REJECT degraded cells.

from __future__ import annotations

import json
import sys
from pathlib import Path


EXIT_OK = 0
EXIT_DISPATCH_MISSING = 2
EXIT_MANIFEST_MISSING = 3


def _listed_trial_dirs(run_dir: Path) -> list[Path]:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        return []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    names = payload.get("per_trial_paths") if isinstance(payload, dict) else None
    if not isinstance(names, list):
        return []
    return [run_dir / str(name) for name in names]


def _manifest_captured(payload: dict) -> int:
    try:
        return int(payload.get("captured") or 0)
    except (TypeError, ValueError):
        return 0


def _validate_manifest(manifest_path: Path) -> int:
    if not manifest_path.is_file():
        print(f"manifest-missing: {manifest_path}", file=sys.stderr)
        return EXIT_MANIFEST_MISSING
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"manifest-missing: {manifest_path} ({exc})", file=sys.stderr)
        return EXIT_MANIFEST_MISSING
    captured = _manifest_captured(payload)
    if captured < 1:
        print(
            f"subagent-dispatch-missing: {manifest_path} captured={captured}",
            file=sys.stderr,
        )
        return EXIT_DISPATCH_MISSING
    return EXIT_OK


def _validate_run_dir(run_dir: Path, trial_dirs: list[Path]) -> int:
    legacy_manifest_path = run_dir / "subagent-trace-manifest.json"
    for trial_dir in trial_dirs:
        manifest_path = trial_dir / "subagent-trace-manifest.json"
        if (
            not manifest_path.is_file()
            and len(trial_dirs) == 1
            and legacy_manifest_path.is_file()
        ):
            manifest_path = legacy_manifest_path
        result = _validate_manifest(manifest_path)
        if result != EXIT_OK:
            return result
    return EXIT_OK


def validate(cell_dir: Path) -> int:
    target = Path(cell_dir)
    trial_dirs = _listed_trial_dirs(target)
    if trial_dirs:
        return _validate_run_dir(target, trial_dirs)
    return _validate_manifest(target / "subagent-trace-manifest.json")


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1:
        print(
            "usage: python -m razorback.agents.subagent_smoke <cell-or-run-dir>",
            file=sys.stderr,
        )
        return 64
    return validate(Path(args[0]))


if __name__ == "__main__":
    raise SystemExit(main())
