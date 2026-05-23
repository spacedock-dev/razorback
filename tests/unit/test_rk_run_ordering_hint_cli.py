import json
from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from razorback.cli import app


def _task_dir(tmp_path: Path, name: str) -> Path:
    path = tmp_path / "tasks" / name
    path.mkdir(parents=True)
    return path


def _write_spec(tmp_path: Path, tasks: list[Path], *, with_provenance: bool = False) -> Path:
    spec = tmp_path / "spec.frozen.yaml"
    task_lines = "".join(f"    - {task}\n" for task in tasks)
    provenance = ""
    if with_provenance:
        provenance = (
            "provenance:\n"
            "  model_resolved_version: claude-opus-4-5-20251022\n"
            "  harbor_version: 0.6.6\n"
        )
    spec.write_text(
        "version: 1\n"
        "experiment: ordering-hints\n"
        "agent:\n"
        "  kind: nop\n"
        "benchmark:\n"
        "  kind: local\n"
        "  task_paths:\n"
        f"{task_lines}"
        "trials: 2\n"
        "concurrency:\n"
        "  trials: 2\n"
        f"{provenance}"
    )
    return spec


def _write_historical_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "historical-run"
    run_dir.mkdir()
    rows = {
        "short__abc": ("short", "2026-05-23T00:00:00Z", "2026-05-23T00:00:10Z"),
        "long__abc": ("long", "2026-05-23T00:00:00Z", "2026-05-23T00:01:30Z"),
    }
    for trial_name, (task_name, started_at, finished_at) in rows.items():
        trial_dir = run_dir / trial_name
        trial_dir.mkdir()
        (trial_dir / "result.json").write_text(
            json.dumps(
                {
                    "task_name": task_name,
                    "trial_name": trial_name,
                    "started_at": started_at,
                    "finished_at": finished_at,
                }
            )
        )
    return run_dir


def _run_cli(spec: Path, runs_dir: Path, *args: str) -> Path:
    with patch("razorback.cli.run._run_canary"), patch(
        "razorback.cli.run._resolve_model_version",
        return_value=("claude-opus-4-5-20251022", "2026-05-19"),
    ), patch("razorback.cli.run.check_harbor_drift"), patch(
        "razorback.cli.run._invoke_harbor", return_value=0
    ):
        result = CliRunner(mix_stderr=False).invoke(
            app, ["run", str(spec), "--runs-dir", str(runs_dir), *args]
        )
    assert result.exit_code == 0, result.stderr or result.stdout
    run_dirs = list((runs_dir / "ordering-hints").iterdir())
    assert len(run_dirs) == 1
    return run_dirs[0]


def _serialized_task_names(run_dir: Path) -> list[str]:
    payload = json.loads((run_dir / "_job_config.yaml").read_text())
    return [Path(task["path"]).name for task in payload["tasks"]]


def test_rk_run_without_ordering_hint_preserves_input_order(tmp_path: Path) -> None:
    tasks = [_task_dir(tmp_path, name) for name in ("short", "unknown", "long")]
    spec = _write_spec(tmp_path, tasks)

    run_dir = _run_cli(spec, tmp_path / "_runs")

    assert _serialized_task_names(run_dir) == ["short", "unknown", "long"]


def test_rk_run_order_from_run_serializes_longest_known_tasks_first(tmp_path: Path) -> None:
    tasks = [_task_dir(tmp_path, name) for name in ("short", "unknown", "long")]
    spec = _write_spec(tmp_path, tasks)
    history = _write_historical_run(tmp_path)

    run_dir = _run_cli(spec, tmp_path / "_runs", "--order-from-run", str(history))
    payload = json.loads((run_dir / "_job_config.yaml").read_text())

    assert [Path(task["path"]).name for task in payload["tasks"]] == ["long", "short", "unknown"]
    assert payload["n_concurrent_trials"] == 2


def test_rk_run_records_ordering_hint_metadata_in_manifest_and_provenance(
    tmp_path: Path,
) -> None:
    tasks = [_task_dir(tmp_path, name) for name in ("short", "unknown", "long")]
    spec = _write_spec(tmp_path, tasks, with_provenance=True)
    history = _write_historical_run(tmp_path)

    run_dir = _run_cli(spec, tmp_path / "_runs", "--order-from-run", str(history))

    expected = {
        "mode": "longest-known-first",
        "source_path": str(history),
        "usable_timing_count": 2,
        "matched_task_count": 2,
        "unmatched_task_count": 1,
        "ignored_timing_count": 0,
    }
    manifest = json.loads((run_dir / "manifest.json").read_text())
    provenance = yaml.safe_load((run_dir / "provenance.yaml").read_text())
    assert manifest["ordering_hint"] == expected
    assert provenance["ordering_hint"] == expected
