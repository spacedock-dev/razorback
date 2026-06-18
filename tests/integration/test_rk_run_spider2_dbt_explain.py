# ABOUTME: AC-3 — rk run --explain on a fixture spider2-dbt spec lists resolved tasks.
# ABOUTME: In-process via CliRunner; resolver is monkeypatched (offline, no env seam).
import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "tests" / "fixtures" / "spider2_dbt" / "specs" / "spider2-dbt-fixture.frozen.yaml"
SOURCE_ROOT = REPO / "tests" / "fixtures" / "spider2_dbt" / "harbor_task_minimal"


def test_rk_run_explain_lists_spider2_tasks(tmp_path, monkeypatch):
    sources = sorted(SOURCE_ROOT.glob("spider2-fixture-*"))
    n_instances = len(sources)
    assert n_instances >= 1

    # Offline + deterministic: the in-process resolver returns fixture sources.
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )

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
    # AC-3: one task entry per fixture instance.
    # task_paths nests under "prompt" (run_explain.py:254 → _prompt_plan
    # spreads **_sample_task_prompt_inputs which carries task_paths, :52).
    task_paths = payload["prompt"]["task_paths"]
    assert len(task_paths) == n_instances
    # emitted paths are materialized spider2-dbt views, not raw source dirs
    assert all(Path(p).name.startswith("spider2-dbt-") for p in task_paths)
