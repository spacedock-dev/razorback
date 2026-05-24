# ABOUTME: Per-cell subagent-dispatch smoke validator. Exits 0/2/3 from manifest.
# ABOUTME: Used by examples/drivers/dab-paper-matrix.sh to REJECT degraded cells.

from __future__ import annotations

import json
import sys
from pathlib import Path


EXIT_OK = 0
EXIT_DISPATCH_MISSING = 2
EXIT_MANIFEST_MISSING = 3


def validate(cell_dir: Path) -> int:
    manifest_path = Path(cell_dir) / "subagent-trace-manifest.json"
    if not manifest_path.is_file():
        print(f"manifest-missing: {manifest_path}", file=sys.stderr)
        return EXIT_MANIFEST_MISSING
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"manifest-missing: {manifest_path} ({exc})", file=sys.stderr)
        return EXIT_MANIFEST_MISSING
    captured = int(payload.get("captured") or 0)
    if captured < 1:
        print(
            f"subagent-dispatch-missing: {manifest_path} captured={captured}",
            file=sys.stderr,
        )
        return EXIT_DISPATCH_MISSING
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1:
        print("usage: python -m razorback.agents.subagent_smoke <cell-dir>", file=sys.stderr)
        return 64
    return validate(Path(args[0]))


if __name__ == "__main__":
    raise SystemExit(main())
