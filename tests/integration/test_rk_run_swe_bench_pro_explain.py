# tests/integration/test_rk_run_swe_bench_pro_explain.py
# ABOUTME: AC-3 — rk run --explain --explain-format json lists resolved swe-bench-pro task views.
# ABOUTME: In-process via CliRunner; resolver is monkeypatched (offline, no env seam).
import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "tests" / "fixtures" / "swe_bench_pro" / "specs" / "swe-bench-pro-fixture.frozen.yaml"
SOURCE_ROOT = REPO / "tests" / "fixtures" / "swe_bench_pro" / "harbor_task_minimal"


def test_rk_run_explain_lists_swe_task_views(tmp_path, monkeypatch):
    sources = sorted(SOURCE_ROOT.glob("swe-bench-pro-fixture-*"))
    n_instances = len(sources)
    assert n_instances >= 1

    # Offline + deterministic: the in-process resolver returns fixture sources.
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )
    # `rk run` runs the runs-dir Docker canary (run.py:213, _run_canary
    # defined at run.py:50) BEFORE the --explain branch (run.py:335), and it
    # shells out to `docker run` (runs_dir_canary.py:50). Patch it so the test
    # is genuinely offline — without this it depends on a live Docker daemon
    # (the spider2 precedent only passes because the dev env has Colima).
    monkeypatch.setattr("razorback.cli.run._run_canary", lambda *a, **k: None)

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        app,
        [
            "run", str(SPEC),
            "--runs-dir", str(tmp_path / "_runs"),
            "--explain", "--explain-format", "json",
        ],
    )
    assert result.exit_code == 0, result.stderr or result.stdout

    payload = json.loads(result.stdout)
    # AC-3: one task entry per fixture instance, nested under "prompt".
    task_paths = payload["prompt"]["task_paths"]
    assert len(task_paths) == n_instances
    # emitted paths are materialized swe-bench-pro views, not raw source dirs
    assert all(Path(p).name.startswith("swe-bench-pro-") for p in task_paths)
