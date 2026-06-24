#!/usr/bin/env python3
# ABOUTME: Package upstream Spider2.0-DBT examples into Harbor task views razorback can run.
# ABOUTME: Wraps each example (dbt project + source/gold DuckDB + eval line) and runs it
# ABOUTME: through the production materializer. Does NOT run any agent — packaging only.
"""
Package Spider2.0-DBT into Harbor-shaped task views.

Upstream layout (after `setup.py`), per instance under <spider2-root>/examples/<id>/:
    dbt_project.yml, profiles.yml, models/, dbt_packages/, <name>.duckdb (source)
Per-instance instruction lives in <spider2-root>/examples/spider2-dbt.jsonl.
Per-instance gold + eval spec live under
    <spider2-root>/evaluation_suite/gold/spider2_eval.jsonl   (all instances)
    <spider2-root>/evaluation_suite/gold/<id>/<gold>.duckdb   (per instance)

For each instance this builds a staging "source task dir" of the shape
`materialize_spider2_harbor_task_view` expects:

    <staging>/<id>/
        task.toml
        instruction.md
        environment/Dockerfile
        dbt_project/        <- the entire upstream example (project + source DuckDB)
        tests/gold/spider2_eval.jsonl   <- the single eval line for THIS instance
        tests/gold/<gold>.duckdb        <- this instance's gold DuckDB

then calls the production materializer to emit a Harbor task view under <out>/.

It mutates NO razorback code and NO upstream data — it only reads upstream and
writes under <staging>/<out> (both default outside the repo).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import traceback
from pathlib import Path

# Production materializer — the same call the smoke proved end-to-end.
from razorback.benchmarks.spider2_dbt.harbor_view import (
    materialize_spider2_harbor_task_view,
)

_DOCKERFILE = """\
FROM {base_image}
RUN pip install --no-cache-dir "{dbt_spec}" "duckdb" "pyyaml"
ENV DBT_PROFILES_DIR=/app
WORKDIR /app
"""

_TASK_TOML = """\
schema_version = "1.2"

[task]
name = "spider2-dbt/{task_id}"
description = {description}

[environment]
os = "linux"
cpus = 2
memory_mb = 2048
"""


def _toml_basic_string(value: str) -> str:
    """Return a valid single-line TOML basic-string literal for `value`.

    Python's `repr()` is NOT valid TOML (it can emit single-quoted strings or
    `\\'` escapes), so escape `\\` and `"` explicitly and collapse newlines/tabs
    to spaces (TOML basic strings forbid raw control characters).
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    for ws in ("\r\n", "\r", "\n", "\t"):
        escaped = escaped.replace(ws, " ")
    return '"' + escaped + '"'


def _load_instructions(spider2_root: Path) -> dict[str, dict]:
    """instance_id -> {instruction, type} from examples/spider2-dbt.jsonl."""
    out: dict[str, dict] = {}
    path = spider2_root / "examples" / "spider2-dbt.jsonl"
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        out[obj["instance_id"]] = obj
    return out


def _load_eval_lines(spider2_root: Path) -> dict[str, dict]:
    """instance_id -> parsed eval-spec line from gold/spider2_eval.jsonl."""
    out: dict[str, dict] = {}
    path = spider2_root / "evaluation_suite" / "gold" / "spider2_eval.jsonl"
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        out[obj["instance_id"]] = obj
    return out


def _find_source_duckdb(example_dir: Path) -> Path | None:
    # The upstream source DuckDB sits at the example root; a shallow glob avoids
    # walking vendored dbt_packages/. Fall back to rglob for unexpected layouts.
    shallow = sorted(example_dir.glob("*.duckdb"))
    if shallow:
        return shallow[0]
    deep = sorted(example_dir.rglob("*.duckdb"))
    return deep[0] if deep else None


def _resolve_gold(gold_root: Path, task_id: str, eval_line: dict) -> tuple[Path, str] | None:
    """Return (gold_db_path, gold_basename_to_use) reconciling spec vs disk.

    The eval spec names a gold file (`...parameters.gold`), but the downloaded
    archive sometimes ships it under a different basename (e.g. spec says
    `xero.duckdb`, disk has `xero_new.duckdb`). Prefer the spec name; otherwise
    fall back to the single *.duckdb present in gold/<id>/ and report the
    reconciliation by using the on-disk basename.
    """
    params = eval_line.get("evaluation", {}).get("parameters", {}) or {}
    spec_name = params.get("gold")
    inst_dir = gold_root / task_id
    if spec_name and (inst_dir / spec_name).is_file():
        return inst_dir / spec_name, spec_name
    # fall back: exactly one gold duckdb under gold/<id>/
    if inst_dir.is_dir():
        cands = sorted(inst_dir.glob("*.duckdb"))
        if len(cands) == 1:
            return cands[0], cands[0].name
    return None


def _stage_task(
    *,
    task_id: str,
    example_dir: Path,
    instruction: str,
    eval_line: dict,
    gold_db: Path,
    gold_basename: str,
    staging_root: Path,
    base_image: str,
    dbt_spec: str,
) -> Path:
    """Build the harbor source-task dir under staging and return its path."""
    src = staging_root / task_id
    if src.exists():
        shutil.rmtree(src)
    (src / "environment").mkdir(parents=True)
    tests_gold = src / "tests" / "gold"
    tests_gold.mkdir(parents=True)

    # dbt_project/ <- the whole upstream example (project + source DuckDB + vendored packages)
    shutil.copytree(example_dir, src / "dbt_project")

    # environment/Dockerfile (materializer appends COPY dbt_project + preflight)
    (src / "environment" / "Dockerfile").write_text(
        _DOCKERFILE.format(base_image=base_image, dbt_spec=dbt_spec)
    )

    # task.toml (no docker_image => Harbor builds from the Dockerfile). The
    # description is emitted as an escaped single-line TOML basic string.
    (src / "task.toml").write_text(
        _TASK_TOML.format(
            task_id=task_id,
            description=_toml_basic_string(instruction[:300] or task_id),
        )
    )
    (src / "instruction.md").write_text(instruction.rstrip() + "\n")

    # tests/gold/: this instance's eval line + gold DuckDB, with the gold
    # basename reconciled to what actually exists on disk.
    line = json.loads(json.dumps(eval_line))  # deep copy
    line.setdefault("evaluation", {}).setdefault("parameters", {})["gold"] = gold_basename
    (tests_gold / "spider2_eval.jsonl").write_text(json.dumps(line) + "\n")
    shutil.copy2(gold_db, tests_gold / gold_basename)
    return src


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--spider2-root",
        type=Path,
        required=True,
        help="Path to the upstream spider2-dbt checkout (post-setup.py): the dir "
        "containing examples/ and evaluation_suite/.",
    )
    ap.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output dir for the emitted Harbor task views (created if absent).",
    )
    ap.add_argument(
        "--staging",
        type=Path,
        default=None,
        help="Where per-task source dirs are staged before materialization. "
        "Default: <out>/_staging.",
    )
    ap.add_argument(
        "--tasks", type=str, default=None, help="Comma-separated instance_ids to limit to."
    )
    ap.add_argument("--base-image", type=str, default="python:3.12", help="Base Docker image.")
    ap.add_argument(
        "--dbt-spec",
        type=str,
        default="dbt-duckdb==1.9.4",
        help="pip requirement spec for dbt installed into the task image.",
    )
    ap.add_argument(
        "--debug", action="store_true", help="Print full tracebacks for per-task failures."
    )
    args = ap.parse_args()

    spider2_root: Path = args.spider2_root
    out_root: Path = args.out
    staging_root: Path = args.staging or (out_root / "_staging")
    gold_root = spider2_root / "evaluation_suite" / "gold"
    out_root.mkdir(parents=True, exist_ok=True)
    staging_root.mkdir(parents=True, exist_ok=True)

    instructions = _load_instructions(spider2_root)
    eval_lines = _load_eval_lines(spider2_root)

    want = [t.strip() for t in args.tasks.split(",")] if args.tasks else sorted(instructions)

    ok: list[str] = []
    skipped: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []

    for task_id in want:
        meta = instructions.get(task_id)
        if meta is None:
            skipped.append((task_id, "not in spider2-dbt.jsonl"))
            continue
        if meta.get("type") != "DBT":
            skipped.append((task_id, f"type={meta.get('type')} (not DBT)"))
            continue
        example_dir = spider2_root / "examples" / task_id
        if not example_dir.is_dir():
            skipped.append((task_id, "no example dir"))
            continue
        if _find_source_duckdb(example_dir) is None:
            skipped.append((task_id, "no source .duckdb"))
            continue
        eval_line = eval_lines.get(task_id)
        if eval_line is None:
            skipped.append((task_id, "no eval-spec line"))
            continue
        resolved = _resolve_gold(gold_root, task_id, eval_line)
        if resolved is None:
            skipped.append((task_id, "no gold .duckdb"))
            continue
        gold_db, gold_basename = resolved
        spec_name = eval_line["evaluation"]["parameters"].get("gold")
        note = "" if gold_basename == spec_name else f" (gold reconciled {spec_name!r}->{gold_basename!r})"

        try:
            src = _stage_task(
                task_id=task_id,
                example_dir=example_dir,
                instruction=meta.get("instruction", ""),
                eval_line=eval_line,
                gold_db=gold_db,
                gold_basename=gold_basename,
                staging_root=staging_root,
                base_image=args.base_image,
                dbt_spec=args.dbt_spec,
            )
            view = materialize_spider2_harbor_task_view(
                source_task_dir=src,
                view_root=out_root,
                task_slug=task_id,
                view_mode="copy",
            )
            ok.append(task_id)
            print(f"[ok]   {task_id} -> {view.name}{note}")
        except Exception as exc:  # noqa: BLE001 — report per-task and continue
            failed.append((task_id, f"{type(exc).__name__}: {exc}"))
            print(f"[FAIL] {task_id}: {type(exc).__name__}: {exc}", file=sys.stderr)
            if args.debug:
                traceback.print_exc()

    print("\n==== SUMMARY ====")
    print(f"packaged OK : {len(ok)}")
    print(f"skipped     : {len(skipped)}")
    for t, why in skipped:
        print(f"   - {t}: {why}")
    print(f"failed      : {len(failed)}")
    for t, why in failed:
        print(f"   - {t}: {why}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
