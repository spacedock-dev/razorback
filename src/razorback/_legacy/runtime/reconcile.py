# ABOUTME: reconcile_run_workflow — the run-workflow's reconciling stage driver (§2.1, §4, AC-1).
# ABOUTME: Dispatches `rk run` until accumulated trials >= target_trials or max_iterations is hit.

import json
import subprocess
from pathlib import Path


def reconcile_run_workflow(
    *,
    entity_path: Path,
    target_trials: int,
    spec_path: Path,
    runs_dir: Path,
    max_iterations: int = 5,
) -> dict:
    """Reconcile a run-workflow entity's target trial count by dispatching make-up rk run calls.

    Reads the entity's body to discover the current run-dirs, sums each run-dir's
    summary.json `n_trials` (or DAB-style trial count), and dispatches `rk run` per
    iteration until target is met. Appends each new run-dir to the entity body.

    Returns a dict {dispatched: int, accumulated_trials: int, target_met: bool}.
    Raises RuntimeError if any dispatched `rk run` exits non-zero.
    """
    runs = _read_runs_from_entity(entity_path)
    accumulated = sum(_count_trials_in_run_dir(r) for r in runs)
    dispatched = 0

    while accumulated < target_trials and dispatched < max_iterations:
        before = _existing_run_dirs(runs_dir)
        result = subprocess.run(
            ["uv", "run", "rk", "run", str(spec_path), "--runs-dir", str(runs_dir)],
            capture_output=True,
            text=True,
            timeout=3600,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"rk run failed (exit code {result.returncode}): {result.stderr}"
            )
        after = _existing_run_dirs(runs_dir)
        new_dirs = [d for d in after if d not in before]
        for new_dir in new_dirs:
            runs.append(new_dir)
            accumulated += _count_trials_in_run_dir(new_dir)
        dispatched += 1

    _write_runs_to_entity(entity_path, runs)
    return {
        "dispatched": dispatched,
        "accumulated_trials": accumulated,
        "target_met": accumulated >= target_trials,
    }


def _read_runs_from_entity(entity_path: Path) -> list[Path]:
    text = Path(entity_path).read_text()
    runs: list[Path] = []
    in_runs_section = False
    for line in text.splitlines():
        if line.strip().lower().startswith("## runs"):
            in_runs_section = True
            continue
        if in_runs_section:
            if line.startswith("##"):
                break
            if line.strip().startswith("- "):
                p = Path(line.strip()[2:])
                if p.exists():
                    runs.append(p)
    return runs


def _write_runs_to_entity(entity_path: Path, runs: list[Path]) -> None:
    text = Path(entity_path).read_text()
    lines = text.splitlines()
    out: list[str] = []
    skip = False
    found = False
    for line in lines:
        if line.strip().lower().startswith("## runs"):
            found = True
            out.append(line)
            out.append("")
            for r in runs:
                out.append(f"- {r}")
            skip = True
            continue
        if skip:
            if line.startswith("##"):
                skip = False
                out.append(line)
            continue
        out.append(line)
    if not found:
        out.append("")
        out.append("## Runs")
        out.append("")
        for r in runs:
            out.append(f"- {r}")
    Path(entity_path).write_text("\n".join(out) + "\n")


def _count_trials_in_run_dir(run_dir: Path) -> int:
    summary = Path(run_dir) / "summary.json"
    if not summary.exists():
        return 0
    data = json.loads(summary.read_text())
    if "n_trials" in data:
        return int(data["n_trials"])
    if "n_completed_trials" in data:
        return int(data["n_completed_trials"])
    if "datasets" in data:
        total = 0
        for ds in data["datasets"].values():
            for q in ds.get("queries", []):
                total += int(q.get("n_trials", 0))
        return total
    return 0


def _existing_run_dirs(runs_dir: Path) -> set[Path]:
    root = Path(runs_dir)
    if not root.exists():
        return set()
    result: set[Path] = set()
    for exp_dir in root.iterdir():
        if not exp_dir.is_dir():
            continue
        for job_dir in exp_dir.iterdir():
            if job_dir.is_dir():
                result.add(job_dir)
    return result
